import time
import json
import os
import gc
from pathlib import Path
import numpy as np
from dataclasses import dataclass
import threading

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from catbot_interfaces.action import VlaTask

from sensor_msgs.msg import CompressedImage # Image 대신
from cv_bridge import CvBridge
import cv2

import torch
import draccus
from huggingface_hub import hf_hub_download, snapshot_download
import lerobot.robots.so_follower

# ==================================================================================
# [CRITICAL HOTFIX] 설정 강제 등록 함수
# ==================================================================================
def manual_register(base_class, key, child_class):
    try:
        if hasattr(base_class, "_choice_registry"):
            base_class._choice_registry[key] = child_class
    except Exception as e:
        print(f"⚠️ 등록 실패: {e}")

try:
    from lerobot.robots.utils import make_robot_from_config
    from lerobot.utils.utils import get_safe_torch_device
    from lerobot.robots.config import RobotConfig
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.processor.rename_processor import rename_stats

    try:
        from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
    except ImportError:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

    # 1. 로봇 설정 등록
    try:
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobotConfig, ManipulatorRobot
    except ImportError:
        try:
            from lerobot.robots.manipulator import ManipulatorRobotConfig, ManipulatorRobot
        except ImportError:
            ManipulatorRobotConfig = None

    if ManipulatorRobotConfig:
        @dataclass
        class So101FollowerConfig(ManipulatorRobotConfig):
            def instantiate(self): return ManipulatorRobot(self)
        manual_register(RobotConfig, "so101_follower", So101FollowerConfig)

    # 2. 카메라 설정 등록
    try:
        from lerobot.common.robot_devices.cameras.configs import CameraConfig
    except ImportError:
        try:
            from lerobot.cameras.configs import CameraConfig
        except ImportError:
            CameraConfig = None

    try:
        from lerobot.common.robot_devices.cameras.opencv import OpenCVCameraConfig, OpenCVCamera
    except ImportError:
        try:
            from lerobot.cameras.opencv import OpenCVCameraConfig, OpenCVCamera
        except ImportError:
            OpenCVCameraConfig = None

    if CameraConfig and OpenCVCameraConfig:
        manual_register(CameraConfig, "opencv", OpenCVCameraConfig)

    # 3. 모델/데이터셋 import
    try:
        from lerobot.common.datasets.lerobot_dataset import LeRobotDatasetMetadata
    except ImportError:
        from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata

    try:
        from lerobot.common.policies.smolvla.configuration_smolvla import SmolVLAConfig
        from lerobot.common.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    except ImportError:
        from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

except ImportError as e:
    print(f"\n[CRITICAL ERROR] 라이브러리 경로 문제 발생: {e}")
    raise
# ==================================================================================


class SafeDatasetMetadata:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.stats = {}
        self.features = {}
        self._load_safe()

    def _load_safe(self):
        stats_path = self.root / "meta/stats.json"
        if stats_path.exists():
            with open(stats_path, "r") as f: self.stats = json.load(f)
        else:
            raise FileNotFoundError(f"stats.json을 찾을 수 없습니다: {stats_path}")

        info_path = self.root / "meta/info.json"
        if info_path.exists():
            with open(info_path, "r") as f:
                data = json.load(f)
                self.features = data.get("features", {})

class VlaActionServer(Node):
    def __init__(self):
        super().__init__('vla_action_server')
        self.get_logger().info('🚀 [Init] 서버 초기화 중... (데이터셋 분리 적용)')
        
        self.SMOOTHING_ALPHA = 0.3
        self.prev_action = None     

        self.server_active = True 

        # --- [1] 기본 설정 ---
        self.target_device = get_safe_torch_device("cuda")
        
        # 1) AI 모델용 (학습된 가중치 + 통계 정보)
        self.policy_path = "ddubbae/petner_smolvla_v3" 
        self.dataset_repo_id = "ddubbae/petner"
        
        # 2) 리플레이용 (단순 재생할 데이터셋 ID)
        self.replay_repo_id = "ddubbae/petner_scoop"
        
        # 3) 리플레이 데이터셋 객체 (초기값은 반드시 None)
        self.replay_dataset = None
        
        # [설정] 종료 자세 좌표
        self.POSE_START = [-3.6485, -94.5717, 98.6395, 69.3162, 2.0269]
        self.POSE_MID   = [-4.3931, -1.1874, 98.9116, -90.6838, 0.8059]
        self.POSE_DISPENSER = [-3.4252, 43.1722, 46.5760, -65.9829, -0.3175]
        self.POSE_SHOVEL_READY = [-3.0529, 10.9415, 8.5714, 87.1795, -0.1709]
        self.POSE_SHOVEL_MID = [-1.7870, -0.8482, 98.8209, -93.4188, 4.5665]
        
        self.JOINT_TOLERANCE = 13.0
        self.MOTION_THRESHOLD = 80.0
        
        self.bridge = CvBridge()
        self.latest_wrist_img = None
        self.img_lock = threading.Lock()
        
        self.create_subscription(
            CompressedImage, # 타입 변경
            'wrist_cam/compressed', # 토픽 이름 변경 (/compressed 추가)
            self.wrist_cam_callback, 
            10,
            callback_group=ReentrantCallbackGroup()
        )

        self.robot_type = "so101_follower"
        self.robot_overrides = {
            "cameras": {
                "camera2": {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"},
                "camera3": {"type": "opencv", "index_or_path": 4, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}
            }
        }
        self.joint_names = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos"]

        self.load_resources()

        self._action_server = ActionServer(
            self, VlaTask, 'execute_vla_task',
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup()
        )
        self.get_logger().info('✅ VLA Action Server 준비 완료!')

    def wrist_cam_callback(self, msg):
        try:
            # [변경] CompressedImage -> CV2 이미지 변환
            # bridge.compressed_imgmsg_to_cv2 함수 사용
            cv_image = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # (이후 로직은 동일)
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            with self.img_lock:
                self.latest_wrist_img = cv_image
        except Exception as e:
            self.get_logger().warn(f"이미지 디코딩 실패: {e}")

    def load_resources(self):
        try:
            # 여기서는 모델용 데이터셋(dataset_repo_id)을 써야 합니다. (통계 정보 일치)
            config_file_path = hf_hub_download(repo_id=self.policy_path, filename="config.json")
            with open(config_file_path, "r") as f:
                cfg_dict = json.load(f)
            if "type" in cfg_dict: del cfg_dict["type"]
            policy_cfg = draccus.decode(SmolVLAConfig, cfg_dict)
            policy_cfg.pretrained_path = self.policy_path
            policy_cfg.device = "cpu"

            # 모델 통계용 데이터셋 다운로드
            meta_root = snapshot_download(repo_id=self.dataset_repo_id, repo_type="dataset", allow_patterns="meta/*.json", local_dir=None)
            ds_meta = SafeDatasetMetadata(meta_root)
            
            rename_map = {
                "observation.images.wrist": "observation.images.camera1",
                "observation.images.left": "observation.images.camera2",
                "observation.images.right": "observation.images.camera3"
            }
            if ds_meta.features:
                keys_to_rename = list(ds_meta.features.keys())
                for old_key in keys_to_rename:
                    if old_key in rename_map:
                        ds_meta.features[rename_map[old_key]] = ds_meta.features.pop(old_key)
            ds_meta.stats = rename_stats(ds_meta.stats, rename_map)

            self.policy = SmolVLAPolicy.from_pretrained(self.policy_path, config=policy_cfg, dataset_meta=ds_meta, device=None)
            self.policy.to(self.target_device)
            self.policy.eval()

            try:
                self.get_logger().info("🚀 모델 컴파일 시작...")
                self.policy = torch.compile(self.policy, mode="reduce-overhead")
                self.get_logger().info("✅ 모델 컴파일 완료!")
            except Exception as e:
                pass

            self.preprocessor, self.postprocessor = make_pre_post_processors(policy_cfg=policy_cfg, dataset_stats=ds_meta.stats)

            calibration_dir = Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()
            robot_config_dict = {
                "type": self.robot_type, "port": "/dev/ttyACM0", "id": "follower",
                "calibration_dir": str(calibration_dir), **self.robot_overrides
            }
            robot_cfg = draccus.decode(RobotConfig, robot_config_dict)
            self.robot = make_robot_from_config(robot_cfg)
            self.robot.connect()
        except Exception as e:
            self.get_logger().error(f"Error loading resources: {e}")
            raise e

    def prepare_replay_dataset(self):
        # [방어 코드] 문자열로 잘못 설정된 경우 초기화
        if isinstance(self.replay_dataset, str):
             self.replay_dataset = None

        if self.replay_dataset is None:
            # [수정됨] 여기서 self.replay_repo_id ("ddubbae/petner_scoop")를 사용합니다.
            target_repo = self.replay_repo_id 
            
            self.get_logger().info(f"📂 리플레이 데이터셋 로딩 중: {target_repo}")
            try:
                self.replay_dataset = LeRobotDataset(target_repo, root="data")
                self.get_logger().info(f"✅ 데이터셋 준비 완료! (총 {self.replay_dataset.num_episodes} 에피소드)")
            except Exception as e:
                self.get_logger().error(f"❌ 데이터셋 로드 실패: {e}")
                self.replay_dataset = None
                return False
        return True

    def execute_callback(self, goal_handle):
        task_prompt = goal_handle.request.task_type.lower().strip()
        self.get_logger().info(f'⚡ 작업 요청 수신: "{task_prompt}"')
        feedback_msg = VlaTask.Feedback()
        
        if task_prompt.startswith("replay"):
            return self.execute_replay(goal_handle, task_prompt)

        # === AI Inference Logic ===
        try:
            self.policy.reset()
            self.prev_action = None
            start_time = time.time()
            dt = 1.0 / 30.0

            total_motion = 0.0
            prev_joints = None
            
            while rclpy.ok() and self.server_active:
                loop_start = time.perf_counter()
                elapsed = time.time() - start_time

                if goal_handle.is_cancel_requested:
                    self.get_logger().warn('🛑 작업 취소 요청!')
                    goal_handle.canceled()
                    return VlaTask.Result(success=False, message="Canceled by Client")

                # A. Observation
                t1 = time.perf_counter()
                raw_obs = self.robot.get_observation()
                with self.img_lock:
                    if self.latest_wrist_img is not None:
                        raw_obs["camera1"] = self.latest_wrist_img.copy()
                    else:
                        raw_obs["camera1"] = np.zeros((480, 640, 3), dtype=np.uint8)
                t2 = time.perf_counter()
                t_obs = t2 - t1

                curr_joints = [raw_obs[k] for k in self.joint_names]
                if prev_joints is not None:
                    step_delta = sum(abs(c - p) for c, p in zip(curr_joints, prev_joints))
                    total_motion += step_delta
                prev_joints = curr_joints

                max_diff_start = max(abs(c - t) for c, t in zip(curr_joints, self.POSE_START))
                max_diff_mid = max(abs(c - t) for c, t in zip(curr_joints, self.POSE_MID))
                max_diff_disp = max(abs(c - t) for c, t in zip(curr_joints, self.POSE_DISPENSER))
                max_diff_shovel_ready = max(abs(c - t) for c, t in zip(curr_joints, self.POSE_SHOVEL_READY))
                max_diff_shovel_mid = max(abs(c - t) for c, t in zip(curr_joints, self.POSE_SHOVEL_MID))
                
                finished = False
                target_diff = max_diff_start
                
                if "pick" in task_prompt and "cup" in task_prompt:
                    target_diff = max_diff_mid  
                    if total_motion > self.MOTION_THRESHOLD and max_diff_mid < 20.0:
                        self.get_logger().info(f"✅ [Pick Cup] 완료 (MaxErr={max_diff_mid:.1f})")
                        finished = True
                elif "pour" in task_prompt:
                    target_diff = max_diff_mid 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_mid < self.JOINT_TOLERANCE and elapsed > 10.0:
                        self.get_logger().info(f"✅ [Pour] 완료 (MaxErr={max_diff_mid:.1f})")
                        finished = True
                elif "dispenser" in task_prompt:
                    target_diff = max_diff_disp 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_disp < 12.0:
                        self.get_logger().info(f"✅ [Dispenser] 완료 (MaxErr={max_diff_disp:.1f})")
                        finished = True
                elif "place" in task_prompt and "floor" in task_prompt:
                    target_diff = max_diff_start 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_start < self.JOINT_TOLERANCE:
                        self.get_logger().info(f"✅ [Place Floor] 완료 (MaxErr={max_diff_start:.1f})")
                        finished = True
                elif "shovel" in task_prompt and "pick" in task_prompt:
                    target_diff = max_diff_shovel_ready 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_shovel_ready < self.JOINT_TOLERANCE:
                        finished = True
                elif "scoop" in task_prompt:
                    target_diff = max_diff_mid 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_mid < self.JOINT_TOLERANCE:
                        finished = True
                elif "discard" in task_prompt:
                    target_diff = max_diff_shovel_mid 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_shovel_mid < self.JOINT_TOLERANCE:
                        finished = True
                elif "return" in task_prompt:
                    target_diff = max_diff_start 
                    if total_motion > self.MOTION_THRESHOLD and max_diff_start < self.JOINT_TOLERANCE:
                        finished = True

                if finished:
                    break
                
                # C. Inference
                policy_input = {}
                for cam in ["camera1", "camera2", "camera3"]:
                    if cam in raw_obs:
                        img = torch.from_numpy(raw_obs[cam]).float() / 255.0
                        policy_input[f"observation.images.{cam}"] = img.permute(2, 0, 1).unsqueeze(0)
                
                state_vec = [raw_obs[k] for k in self.joint_names + ["gripper.pos"]]
                policy_input["observation.state"] = torch.tensor(state_vec, dtype=torch.float32).unsqueeze(0)
                policy_input["task"] = task_prompt

                policy_input = self.preprocessor(policy_input)
                for key in policy_input:
                    if isinstance(policy_input[key], torch.Tensor):
                        policy_input[key] = policy_input[key].to(self.target_device, non_blocking=True)

                t3 = time.perf_counter()
                with torch.inference_mode():
                    action = self.policy.select_action(policy_input)
                t4 = time.perf_counter()
                t_infer = t4 - t3
                
                action = self.postprocessor(action)
                action_numpy = action.squeeze(0).cpu().numpy()

                if self.prev_action is None:
                    smoothed_action = action_numpy
                else:
                    smoothed_action = (action_numpy * self.SMOOTHING_ALPHA) + \
                                      (self.prev_action * (1.0 - self.SMOOTHING_ALPHA))
                self.prev_action = smoothed_action

                self.robot.send_action({k: smoothed_action[i] for i, k in enumerate(self.joint_names + ["gripper.pos"])}) 
                feedback_msg.status = f"Motion: {total_motion:.0f} | TargetMaxErr: {target_diff:.1f}"
                goal_handle.publish_feedback(feedback_msg)
                
                process_time = time.perf_counter() - loop_start
                if dt - process_time > 0: time.sleep(dt - process_time)
                
                if process_time > 0.5:
                    self.get_logger().error(f"🚨 렉: {process_time:.3f}s (Cam:{t_obs:.3f}, Infer:{t_infer:.3f})")

            result_msg = f"Motion: {total_motion:.1f}"
            self.get_logger().info(f"✅ 작업 완료: {result_msg}")
            goal_handle.succeed()
            return VlaTask.Result(success=True, message=result_msg)

        except Exception as e:
            self.get_logger().error(f"Error: {e}")
            goal_handle.abort()
            return VlaTask.Result(success=False, message=str(e))

    def execute_replay(self, goal_handle, task_prompt):
        try:
            parts = task_prompt.split()
            episode_idx = 0
            if len(parts) > 1 and parts[1].isdigit():
                episode_idx = int(parts[1])
            
            self.get_logger().info(f"🎬 Replay 모드: Episode {episode_idx} 준비 중...")

            if not self.prepare_replay_dataset():
                goal_handle.abort()
                return VlaTask.Result(success=False, message="Dataset Load Failed")

            # [핵심 수정] Filter 대신 Meta 데이터 사용 (훨씬 빠르고 정확함)
            # LeRobotDataset은 meta 속성에 모든 에피소드의 시작/끝 인덱스를 가지고 있습니다.
            
            if episode_idx >= self.replay_dataset.num_episodes:
                self.get_logger().error(f"❌ 요청한 에피소드 {episode_idx}는 존재하지 않습니다. (총 {self.replay_dataset.num_episodes}개)")
                goal_handle.abort()
                return VlaTask.Result(success=False, message="Episode Out of Range")

            # 메타데이터에서 해당 에피소드의 구간 정보 가져오기
            ep_meta = self.replay_dataset.meta.episodes[episode_idx]
            from_idx = ep_meta['dataset_from_index']
            to_idx = ep_meta['dataset_to_index']
            
            # 안전하게 정수형으로 변환 (Tensor인 경우 대비)
            if hasattr(from_idx, 'item'): from_idx = from_idx.item()
            if hasattr(to_idx, 'item'): to_idx = to_idx.item()
            from_idx, to_idx = int(from_idx), int(to_idx)

            self.get_logger().info(f"🔎 데이터 추출 구간: {from_idx} ~ {to_idx} (총 {to_idx - from_idx} 프레임)")

            # 데이터셋에서 해당 구간만 쏙 빼오기 (슬라이싱)
            # select_columns로 필요한 것만 가져오면 더 빠름
            actions = self.replay_dataset.hf_dataset.select_columns(["action"])[from_idx:to_idx]["action"]
            num_frames = len(actions)
            
            if num_frames == 0:
                self.get_logger().error(f"❌ 데이터 추출 실패 (구간 {from_idx}~{to_idx} 비어있음)")
                goal_handle.abort()
                return VlaTask.Result(success=False, message="Empty Episode Data")

            self.get_logger().info(f"▶️ 재생 시작! 총 {num_frames} 프레임")

            fps = getattr(self.replay_dataset, "fps", 30)
            dt = 1.0 / fps
            
            feedback_msg = VlaTask.Feedback()

            for frame_idx in range(num_frames):
                loop_start = time.perf_counter()
                
                if goal_handle.is_cancel_requested:
                    self.get_logger().warn("🛑 Replay 중지됨")
                    goal_handle.canceled()
                    return VlaTask.Result(success=False, message="Replay Canceled")

                current_action = actions[frame_idx]
                
                # Numpy 변환 (혹시 Tensor일 경우 대비)
                if isinstance(current_action, torch.Tensor):
                    current_action = current_action.tolist()
                elif isinstance(current_action, np.ndarray):
                    current_action = current_action.tolist()

                action_dict = {
                    k: current_action[i] 
                    for i, k in enumerate(self.joint_names + ["gripper.pos"])
                }
                
                self.robot.send_action(action_dict)
                
                feedback_msg.status = f"Replay: {frame_idx}/{num_frames} (Ep {episode_idx})"
                goal_handle.publish_feedback(feedback_msg)

                process_time = time.perf_counter() - loop_start
                if dt - process_time > 0:
                    time.sleep(dt - process_time)

            result_msg = f"Replay Finished (Ep {episode_idx})"
            self.get_logger().info(f"✅ {result_msg}")
            goal_handle.succeed()
            return VlaTask.Result(success=True, message=result_msg)

        except Exception as e:
            self.get_logger().error(f"Replay Error: {e}")
            goal_handle.abort()
            return VlaTask.Result(success=False, message=str(e))

    def destroy_node(self):
        self.server_active = False
        if hasattr(self, 'robot') and self.robot:
            try: self.robot.disconnect()
            except: pass
        super().destroy_node()

    def cancel_callback(self, goal_handle): 
        self.get_logger().info('⚠️ 취소 요청이 들어왔습니다. 작업을 중단합니다.')
        return CancelResponse.ACCEPT

def main(args=None):
    rclpy.init(args=args)
    server = VlaActionServer() 
    executor = MultiThreadedExecutor()
    try:
        rclpy.spin(server, executor=executor)
    except KeyboardInterrupt:
        pass
    finally:
        server.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__': main()