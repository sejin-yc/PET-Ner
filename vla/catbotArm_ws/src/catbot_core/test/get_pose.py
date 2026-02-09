import sys
import os
import time
from pathlib import Path
from dataclasses import dataclass
import draccus

# [중요 1] 라이브러리 경로 확보
sys.path.append(os.path.expanduser('~/lerobot'))

# [중요 2] 사용자님이 말씀하신 모듈 임포트 (이게 있으면 기본 등록이 됩니다)
try:
    import lerobot.robots.so_follower
except ImportError:
    pass

# ==================================================================================
# [CRITICAL HOTFIX] 설정 강제 등록 (서버 코드와 동일한 로직)
# "so101_follower"라는 이름을 확실하게 인식시키기 위함입니다.
# ==================================================================================
def manual_register(base_class, key, child_class):
    try:
        if hasattr(base_class, "_choice_registry"):
            base_class._choice_registry[key] = child_class
    except Exception as e:
        print(f"⚠️ 등록 실패: {e}")

try:
    from lerobot.robots.utils import make_robot_from_config
    from lerobot.robots.config import RobotConfig

    # 1. ManipulatorRobotConfig 가져오기
    try:
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobotConfig, ManipulatorRobot
    except ImportError:
        try:
            from lerobot.robots.manipulator import ManipulatorRobotConfig, ManipulatorRobot
        except ImportError:
            ManipulatorRobotConfig = None

    # 2. 'so101_follower'라는 이름으로 강제 등록
    if ManipulatorRobotConfig:
        @dataclass
        class So101FollowerConfig(ManipulatorRobotConfig):
            def instantiate(self):
                return ManipulatorRobot(self)
        
        manual_register(RobotConfig, "so101_follower", So101FollowerConfig)

except ImportError as e:
    print(f"❌ 라이브러리 임포트 에러: {e}")
    sys.exit(1)
# ==================================================================================

def main():
    print("🔌 로봇 연결 시도 중...")
    
    calibration_dir = Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()
    
    # [설정] 서버 코드와 똑같은 'so101_follower' 타입을 사용
    robot_config_dict = {
        "type": "so101_follower",
        "port": "/dev/ttyACM0",
        "id": "follower",
        "calibration_dir": str(calibration_dir),
        "cameras": {} # 자세만 읽을 것이므로 카메라는 끕니다.
    }
    
    try:
        # 설정 디코딩 (이제 so101_follower를 인식합니다)
        robot_cfg = draccus.decode(RobotConfig, robot_config_dict)
        # 로봇 생성 및 연결
        robot = make_robot_from_config(robot_cfg)
        robot.connect()
        
    except Exception as e:
        print(f"\n❌ 로봇 연결 실패: {e}")
        print("힌트: 로봇 전원이 켜져 있는지, USB가 연결되어 있는지 확인하세요.")
        return

    print("\n🤖 로봇 연결 성공! 현재 관절 각도를 읽습니다...")
    time.sleep(1) # 데이터 안정화 대기
    
    obs = robot.get_observation()
    
    # 5축 관절 이름 (Gripper 제외하고 자세 비교용)
    joint_names = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos"]
    
    # 값 읽기 및 출력
    formatted_values = []
    print("\n" + "="*60)
    print("✅ 현재 로봇 자세 (복사해서 vla_action_server.py에 붙여넣으세요)")
    print("="*60)
    
    for name in joint_names:
        val = float(obs[name])
        print(f"  - {name:<20}: {val:.4f}")
        formatted_values.append(f"{val:.4f}")
        
    print("-" * 60)
    # 복사하기 좋게 리스트 형태로 출력
    print(f"target_joints = [{', '.join(formatted_values)}]")
    print("="*60 + "\n")
    
    robot.disconnect()
    print("🔌 연결 해제 완료.")

if __name__ == "__main__":
    main()