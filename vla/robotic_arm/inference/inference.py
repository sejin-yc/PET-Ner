import time
import argparse
import torch
from pathlib import Path

# LeRobot 라이브러리 임포트
from lerobot.common.policies.factory import make_policy
from lerobot.common.robot_devices.robots.factory import make_robot
from lerobot.common.utils.utils import init_logging, get_safe_torch_device

def main():
    # 1. 설정 (사용자 요구사항을 기본값으로 반영)
    parser = argparse.ArgumentParser(description="Run inference with a pretrained policy on SO-ARM100")
    
    # 로봇 설정
    parser.add_argument("--robot-type", type=str, default="so101_follower")
    parser.add_argument("--robot-port", type=str, default="/dev/ttyACM0")
    
    # 정책 설정
    parser.add_argument("--policy-path", type=str, default="ddubbae/cat_toilet_smolvla")
    parser.add_argument("--device", type=str, default="cuda") # Jetson 등에서는 cuda 필수
    parser.add_argument("--fps", type=int, default=30)
    
    args = parser.parse_args()

    init_logging()
    device = get_safe_torch_device(args.device)
    print(f"Using device: {device}")

    # 2. 로봇 구성 (하드코딩된 카메라 설정 반영)
    # 사용자가 제공한 카메라 설정을 딕셔너리로 구성
    robot_overrides = {
        "cameras": {
            "camera2": {
                "type": "opencv", 
                "index_or_path": 0, 
                "width": 640, 
                "height": 480, 
                "fps": 30, 
                "fourcc": "MJPG"
            },
            "camera1": {
                "type": "opencv", 
                "index_or_path": 2, 
                "width": 640, 
                "height": 480, 
                "fps": 30, 
                "fourcc": "MJPG"
            },
            "camera3": {
                "type": "opencv", 
                "index_or_path": 4, 
                "width": 640, 
                "height": 480, 
                "fps": 30, 
                "fourcc": "MJPG"
            }
        }
    }

    print(f"Initializing robot: {args.robot_type} on {args.robot_port}")
    robot = make_robot(
        args.robot_type,
        overrides=robot_overrides,
        # robot_port가 kwargs로 전달되거나 overrides에 포함될 수 있습니다. 
        # so101_follower config 구조에 따라 port 설정이 다를 수 있으나, 
        # 일반적인 overrides 방식으로 포트 주입을 시도합니다.
    )
    # 만약 make_robot이 포트를 직접 인자로 받지 않는 구조라면 robot.connect() 전에 포트를 수동 설정해야 할 수 있습니다.
    # 여기서는 lerobot의 일반적인 factory 패턴을 따릅니다.
    # (참고: 로봇 설정 파일에 포트가 명시되어 있지 않다면 아래와 같이 연결 시 지정하거나 config를 수정해야 함)
    if hasattr(robot, "leader_arm"):
        # so_arm100 같은 경우 leader/follower 구조일 수 있음
        pass 
    
    # 3. 정책(Policy) 로드
    print(f"Loading policy from: {args.policy_path}")
    policy = make_policy(
        pretrained_model_name_or_path=args.policy_path,
        device=device
    )
    policy.eval() # 추론 모드 설정

    # 4. 로봇 연결
    print("Connecting to robot...")
    robot.connect()
    print("Robot connected.")

    # 5. 추론 루프 설정
    dt = 1.0 / args.fps
    print(f"Starting inference loop at {args.fps} FPS. Press Ctrl+C to stop.")

    try:
        while True:
            loop_start_time = time.perf_counter()

            # A. 관측(Observation) 가져오기
            # robot.capture_observation()은 딕셔너리 형태(numpy array)를 반환합니다.
            observation = robot.capture_observation()

            # B. 텐서 변환 및 배치 차원 추가 (H, W, C -> B, C, H, W 등 처리)
            # LeRobot의 capture_observation은 보통 HWC numpy를 반환하므로, 
            # Policy에 넣기 위해 Torch Tensor로 변환하고 Device로 옮겨야 합니다.
            for key in observation:
                if isinstance(observation[key], (int, float)):
                    observation[key] = torch.tensor(observation[key], device=device).unsqueeze(0)
                else:
                    # 이미지나 배열인 경우
                    obs_tensor = torch.from_numpy(observation[key]).to(device)
                    # 이미지가 채널 마지막(H,W,C)인 경우 채널 첫번째(C,H,W)로 변환 필요할 수 있음
                    # LeRobot의 make_policy로 만든 정책은 내부적으로 전처리를 수행하거나,
                    # robot.capture_observation이 이미 규격에 맞는 데이터를 줄 수 있습니다.
                    # 일반적인 LeRobot 흐름: Numpy -> Tensor -> Add Batch Dim -> Select Action
                    observation[key] = obs_tensor.unsqueeze(0)

            # C. 정책 추론 (Action 계산)
            with torch.inference_mode():
                # select_action은 내부적으로 전처리(Normalize) -> 모델 추론 -> 후처리(Un-normalize)를 수행합니다.
                action = policy.select_action(observation)

            # D. 행동 수행
            # Action Tensor (Batch, Dim) -> Numpy (Dim) 변환
            action_numpy = action.squeeze(0).cpu().numpy()
            
            # 로봇에게 명령 전송
            robot.send_action(action_numpy)

            # E. FPS 유지 (Sleep)
            # 주기적인 제어 루프를 위해 남은 시간만큼 대기
            process_time = time.perf_counter() - loop_start_time
            sleep_time = max(dt - process_time, 0)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopping inference...")
    
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 6. 안전 종료
        print("Disconnecting robot...")
        robot.disconnect()
        print("Done.")

if __name__ == "__main__":
    main()