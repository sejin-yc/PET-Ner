import time
import json
import os
import gc
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from catbot_interfaces.action import VlaTask
import torch
import draccus
from huggingface_hub import hf_hub_download, snapshot_download
from transformers import AutoTokenizer

try:
    from lerobot.robots.utils import make_robot_from_config
    from lerobot.utils.utils import get_safe_torch_device
    from lerobot.robots.config import RobotConfig
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.processor.rename_processor import rename_stats
    import lerobot.robots.so_follower 
    import lerobot.cameras.opencv.configuration_opencv
    
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

class VlaActionServer(Node):
    def __init__(self):
        super().__init__('vla_action_server')
        
        self.get_logger().info('🚀 [Init] 모델 로딩 시작... (약 3~5초 소요)')
        self.target_device = get_safe_torch_device("cuda")
        self.policy_path = "ddubbae/cat_toilet_smolvla" 
        self.dataset_repo_id = "ddubbae/cat_toilet"
        
        self._action_server = ActionServer(
            self,
            VlaTask,
            'execute_vla_task',
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup()
        )
        self.get_logger().info('✅ VLA Action Server 대기 중... (메모리 절약 모드)')

    def execute_callback(self, goal_handle):
        task_prompt = goal_handle.request.task_type
        self.get_logger().info(f'⚡ 작업 요청 수신: "{task_prompt}"')
        feedback_msg = VlaTask.Feedback()
        
        # 리소스 변수 초기화
        robot = None
        policy = None
        postprocessor = None
        tokenizer = None

        try:
            # [Step 1] 리소스 동적 로드
            self.get_logger().info('📥 리소스 로딩 시작...')
            
            # 1. Config 로드 (Device=None으로 CPU 우선 로드)
            config_file_path = hf_hub_download(repo_id=self.policy_path, filename="config.json")
            with open(config_file_path, "r") as f: cfg_dict = json.load(f)
            if "type" in cfg_dict: del cfg_dict["type"]
            policy_cfg = draccus.decode(SmolVLAConfig, cfg_dict)
            policy_cfg.pretrained_path = self.policy_path
            policy_cfg.device = None 

            # 2. 메타데이터 및 이름 매핑
            meta_root = snapshot_download(repo_id=self.dataset_repo_id, repo_type="dataset", allow_patterns="meta/*", local_dir=None)
            ds_meta = LeRobotDatasetMetadata(meta_root)
            rename_map = {
                "observation.images.left": "observation.images.camera1",
                "observation.images.wrist": "observation.images.camera2",
                "observation.images.right": "observation.images.camera3"
            }
            keys_to_rename = list(ds_meta.features.keys())
            for old_key in keys_to_rename:
                if old_key in rename_map:
                    ds_meta.features[rename_map[old_key]] = ds_meta.features.pop(old_key)
            ds_meta.stats = rename_stats(ds_meta.stats, rename_map)

            # 3. 모델 생성 및 GPU 이동
            policy = SmolVLAPolicy.from_pretrained(self.policy_path, config=policy_cfg, dataset_meta=ds_meta, device=None)
            policy.to(self.target_device)
            policy.eval()

            # 4. 후처리기 및 토크나이저
            _, postprocessor = make_pre_post_processors(policy_cfg=policy_cfg, pretrained_path=self.policy_path, dataset_stats=ds_meta.stats)
            try: tokenizer = AutoTokenizer.from_pretrained(self.policy_path)
            except: tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolVLM2-500M-Video-Instruct")

            # 5. 로봇 연결
            calibration_dir = Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()
            robot_config_dict = {
                "type": "so101_follower", "port": "/dev/ttyACM0", "id": "follower",
                "calibration_dir": str(calibration_dir),
                "cameras": {
                    "camera2": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"},
                    "camera1": {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"},
                    "camera3": {"type": "opencv", "index_or_path": 4, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}
                }
            }
            robot = make_robot_from_config(draccus.decode(RobotConfig, robot_config_dict))
            robot.connect()
            self.get_logger().info('🔌 리소스 준비 완료! 추론 시작.')

            # [Step 2] 추론 루프
            start_time = time.time()
            max_duration = 60.0
            min_duration = 3.0
            return_tolerance = 0.5
            fps = 30
            dt = 1.0 / fps
            
            # 텍스트 토큰화
            lang_feat = policy.config.input_features.get("observation.language.tokens")
            max_len = lang_feat.shape[0] if lang_feat else 512
            text_tokens = tokenizer(task_prompt, return_tensors="pt", padding="max_length", max_length=max_len, truncation=True)
            tokens_tensor = text_tokens["input_ids"].to(self.target_device)
            mask_tensor = text_tokens["attention_mask"].to(self.target_device).bool()

            # 초기 자세 저장 (복귀 확인용)
            init_obs = robot.get_observation()
            joint_names = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos"]
            start_joints = [init_obs[k] for k in joint_names]

            while (time.time() - start_time) < max_duration:
                loop_start = time.time()
                elapsed = loop_start - start_time

                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    return VlaTask.Result(success=False, message="Canceled")

                # 관측 및 종료 조건 체크
                raw_obs = robot.get_observation()
                if elapsed > min_duration:
                    curr_joints = [raw_obs[k] for k in joint_names]
                    diff = sum(abs(c - s) for c, s in zip(curr_joints, start_joints))
                    if diff < return_tolerance:
                        self.get_logger().info(f"✅ 초기 자세 복귀 확인 (오차: {diff:.2f}) -> 종료")
                        break

                # 입력 전처리
                policy_input = {"observation.language.tokens": tokens_tensor, "observation.language.attention_mask": mask_tensor}
                for cam in ["camera1", "camera2", "camera3"]:
                    img = torch.from_numpy(raw_obs[cam]).float() / 255.0
                    policy_input[f"observation.images.{cam}"] = img.permute(2, 0, 1).unsqueeze(0).to(self.target_device)
                
                state_vec = [raw_obs[k] for k in joint_names + ["gripper.pos"]]
                policy_input["observation.state"] = torch.tensor(state_vec, dtype=torch.float32, device=self.target_device).unsqueeze(0)

                # 추론 및 후처리(Unnormalization)
                with torch.inference_mode():
                    action = policy.select_action(policy_input)
                action = postprocessor(action)
                action_numpy = action.squeeze(0).cpu().numpy()
                
                # 액션 전송
                robot.send_action({k: action_numpy[i] for i, k in enumerate(joint_names + ["gripper.pos"])})
                
                feedback_msg.status = f"Working... (T={elapsed:.1f}s)"
                goal_handle.publish_feedback(feedback_msg)
                
                if dt - (time.time() - loop_start) > 0: time.sleep(dt - (time.time() - loop_start))

            goal_handle.succeed()
            return VlaTask.Result(success=True, message="Completed")

        except Exception as e:
            self.get_logger().error(f"❌ Error: {e}")
            goal_handle.abort()
            return VlaTask.Result(success=False, message=str(e))
        
        finally:
            # [Step 3] 리소스 해제
            self.get_logger().info('🧹 리소스 정리 중...')
            if robot: robot.disconnect()
            del policy, postprocessor, tokenizer, robot
            gc.collect()
            torch.cuda.empty_cache()
            self.get_logger().info('✨ 메모리 반환 완료.')

    def cancel_callback(self, goal_handle): return CancelResponse.ACCEPT

def main(args=None):
    rclpy.init(args=args)
    from rclpy.executors import MultiThreadedExecutor
    rclpy.spin(VlaActionServer(), executor=MultiThreadedExecutor())
    rclpy.shutdown()

if __name__ == '__main__': main()