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
from catbot_interfaces.action import VlaTask

from sensor_msgs.msg import Image
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
    # rename_stats는 이제 필요 없으므로 제거해도 되지만, 임포트 에러 방지용으로 둠
    from lerobot.processor.rename_processor import rename_stats

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

    # ACT 모듈 임포트
    try:
        from lerobot.common.policies.act.configuration_act import ACTConfig
        from lerobot.common.policies.act.modeling_act import ACTPolicy
    except ImportError:
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy

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

class ActActionServer(Node):
    def __init__(self):
        super().__init__('act_action_server')
        self.get_logger().info('🚀 [Init] ACT 서버 초기화 (No Rename Mode)')
        
        # --- [1] 기본 설정 ---
        self.target_device = get_safe_torch_device("cuda")
        
        self.policy_path = "ddubbae/cat_toilet_act" 
        self.dataset_repo_id = "ddubbae/cat_toilet"
        
        # 자세 좌표
        self.POSE_START = [-3.6485, -94.5717, 98.6395, 69.3162, 2.0269]
        self.POSE_MID   = [-2.9039, 4.5802, 98.1859, -85.8974, 2.0269]
        self.POSE_TOLERANCE = 15
        self.MOTION_THRESHOLD = 50.0 
        
        # --- [2] Wrist Cam 구독 ---
        self.bridge = CvBridge()
        self.latest_wrist_img = None
        self.img_lock = threading.Lock()
        
        self.create_subscription(
            Image, 'wrist_cam', self.wrist_cam_callback, 10,
            callback_group=ReentrantCallbackGroup()
        )

        # --- [3] 로봇 설정 ---
        self.robot_type = "so101_follower"
        self.robot_overrides = {
            "cameras": {
                # camera1(Wrist) 제거 (토픽 사용)
                "camera2": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"},
                "camera3": {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}
            }
        }
        self.joint_names = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos"]

        # --- [4] 리소스 로드 ---
        self.load_resources()

        # --- [5] 서버 시작 ---
        self._action_server = ActionServer(
            self, VlaTask, 'execute_vla_task',
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup()
        )
        self.get_logger().info('✅ ACT Action Server 준비 완료!')

    def wrist_cam_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            with self.img_lock:
                self.latest_wrist_img = cv_image
        except Exception as e:
            self.get_logger().error(f"이미지 변환 실패: {e}")

    def load_resources(self):
        try:
            self.get_logger().info('📥 1. ACT 모델 설정 다운로드...')
            config_file_path = hf_hub_download(repo_id=self.policy_path, filename="config.json")
            with open(config_file_path, "r") as f:
                cfg_dict = json.load(f)
            if "type" in cfg_dict: del cfg_dict["type"]
            
            policy_cfg = draccus.decode(ACTConfig, cfg_dict)
            policy_cfg.pretrained_path = self.policy_path
            policy_cfg.device = "cpu"

            self.get_logger().info('📥 2. 메타데이터 로드...')
            meta_root = snapshot_download(repo_id=self.dataset_repo_id, repo_type="dataset", allow_patterns="meta/*.json", local_dir=None)
            ds_meta = SafeDatasetMetadata(meta_root)
            
            # [삭제됨] rename_stats 로직 제거!
            # 학습할 때 rename을 안 했으므로, 원본 데이터셋의 키(wrist, left, right 등)를 그대로 사용해야 함.
            
            self.get_logger().info('🧠 3. ACT 정책 로드 (GPU)...')
            self.policy = ACTPolicy.from_pretrained(self.policy_path, config=policy_cfg, dataset_meta=ds_meta, device=None)
            self.policy.to(self.target_device)
            self.policy.eval()

            self.get_logger().info('🔧 4. 전/후처리기 생성...')
            self.preprocessor, self.postprocessor = make_pre_post_processors(
                policy_cfg=policy_cfg,
                dataset_stats=ds_meta.stats
            )

            self.get_logger().info('🔌 5. 로봇 연결...')
            calibration_dir = Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()
            robot_config_dict = {
                "type": self.robot_type, "port": "/dev/ttyACM0", "id": "follower",
                "calibration_dir": str(calibration_dir), **self.robot_overrides
            }
            robot_cfg = draccus.decode(RobotConfig, robot_config_dict)
            self.robot = make_robot_from_config(robot_cfg)
            self.robot.connect()
            
        except Exception as e:
            self.get_logger().error(f"❌ 리소스 로드 실패: {e}")
            raise e

    def execute_callback(self, goal_handle):
        task_prompt = goal_handle.request.task_type.lower()
        self.get_logger().info(f'⚡ ACT 작업 요청: "{task_prompt}"')
        feedback_msg = VlaTask.Feedback()
        
        try:
            self.policy.reset() 

            start_time = time.time()
            max_duration = 120.0
            fps = 30
            dt = 1.0 / fps

            total_motion = 0.0
            prev_joints = None
            is_success = False
            
            self.get_logger().info('▶️ 루프 시작')

            while (time.time() - start_time) < max_duration:
                loop_start = time.perf_counter()
                elapsed = time.time() - start_time

                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    return VlaTask.Result(success=False, message="Canceled")

                # A. 관측
                raw_obs = self.robot.get_observation()
                with self.img_lock:
                    if self.latest_wrist_img is not None:
                        raw_obs["camera1"] = self.latest_wrist_img.copy()
                    else:
                        raw_obs["camera1"] = np.zeros((480, 640, 3), dtype=np.uint8)

                curr_joints = [raw_obs[k] for k in self.joint_names]

                # Motion Delta 계산
                if prev_joints is not None:
                    step_delta = sum(abs(c - p) for c, p in zip(curr_joints, prev_joints))
                    total_motion += step_delta
                prev_joints = curr_joints

                # B. 종료 조건 체크
                diff_to_start = sum(abs(c - t) for c, t in zip(curr_joints, self.POSE_START))
                diff_to_mid   = sum(abs(c - t) for c, t in zip(curr_joints, self.POSE_MID))
                TOLERANCE = 20.0
                
                # 조건 로직
                if "shovel" in task_prompt or "dispenser" in task_prompt:
                    if total_motion > self.MOTION_THRESHOLD and diff_to_start < TOLERANCE:
                        self.get_logger().info(f"✅ 복귀 완료 (Diff: {diff_to_start:.1f})")
                        is_success = True
                        break
                elif "water cup" in task_prompt or "pour" in task_prompt:
                    if total_motion > self.MOTION_THRESHOLD and diff_to_mid < TOLERANCE:
                        self.get_logger().info(f"✅ 도달 완료 (Diff: {diff_to_mid:.1f})")
                        is_success = True
                        break
                else: 
                    if total_motion > self.MOTION_THRESHOLD and diff_to_start < TOLERANCE:
                        self.get_logger().info(f"✅ 기본 복귀 완료")
                        is_success = True
                        break
                
                # C. 입력 구성 (물리적 카메라 -> 모델이 아는 키 이름으로 매핑)
                # [중요] 학습 시 rename을 안 했으므로, 데이터셋의 원래 키 이름(wrist, left, right)을 사용해야 합니다.
                policy_input = {}
                
                # 매핑 정의: (물리적 카메라 이름) -> (모델이 학습한 이름)
                # 데이터셋이 'observation.images.wrist' 등으로 되어 있다고 가정
                cam_mapping = {
                    "camera1": "wrist",  # 손목 카메라
                    "camera2": "right",   # 왼쪽 카메라
                    "camera3": "left"   # 오른쪽 카메라
                }

                for phys_cam, model_cam in cam_mapping.items():
                    if phys_cam in raw_obs:
                        img = torch.from_numpy(raw_obs[phys_cam]).float() / 255.0
                        # 키 이름 생성: observation.images.wrist 등
                        policy_input[f"observation.images.{model_cam}"] = img.permute(2, 0, 1).unsqueeze(0)
                
                state_vec = [raw_obs[k] for k in self.joint_names + ["gripper.pos"]]
                policy_input["observation.state"] = torch.tensor(state_vec, dtype=torch.float32).unsqueeze(0)
                
                # D. 전처리 & 추론
                policy_input = self.preprocessor(policy_input)
                for key in policy_input:
                    if isinstance(policy_input[key], torch.Tensor):
                        policy_input[key] = policy_input[key].to(self.target_device, non_blocking=True)

                with torch.inference_mode():
                    action = self.policy.select_action(policy_input)
                
                # E. 후처리 및 전송
                action = self.postprocessor(action)
                action_numpy = action.squeeze(0).cpu().numpy()
                self.robot.send_action({k: action_numpy[i] for i, k in enumerate(self.joint_names + ["gripper.pos"])})
                
                feedback_msg.status = f"ACT: {elapsed:.0f}s | Motion: {total_motion:.0f}"
                goal_handle.publish_feedback(feedback_msg)
                
                process_time = time.perf_counter() - loop_start
                if dt - process_time > 0: time.sleep(dt - process_time)

            if is_success:
                goal_handle.succeed()
                return VlaTask.Result(success=True, message="ACT Task Completed")
            else:
                self.get_logger().warn("⏰ ACT Timeout")
                goal_handle.abort()
                return VlaTask.Result(success=False, message="Timeout")

        except Exception as e:
            self.get_logger().error(f"❌ Error: {e}")
            goal_handle.abort()
            return VlaTask.Result(success=False, message=str(e))

    def destroy_node(self):
        if hasattr(self, 'robot') and self.robot:
            try: self.robot.disconnect()
            except: pass
        super().destroy_node()

    def cancel_callback(self, goal_handle): return CancelResponse.ACCEPT

def main(args=None):
    rclpy.init(args=args)
    from rclpy.executors import MultiThreadedExecutor
    
    # 서버 실행
    server = ActActionServer()
    executor = MultiThreadedExecutor()
    try:
        rclpy.spin(server, executor=executor)
    except KeyboardInterrupt:
        pass
    finally:
        server.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__': main()