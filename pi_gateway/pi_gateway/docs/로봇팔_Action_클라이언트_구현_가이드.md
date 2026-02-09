# 로봇팔 Action 클라이언트 구현 가이드

## 개요

Pi Gateway에 로봇팔 팀의 Action 서버와 통신하기 위한 Action 클라이언트를 추가했습니다.

## 구현 내용

### 변경 파일

**`src/ros_cmdvel.py`**:
- `ArmControlBridge` 클래스에 Action 클라이언트 추가
- `/arm/cmd` 토픽 구독 추가 (패트롤 노드에서 로봇팔 작업 요청)
- `/arm/done` 토픽 발행 추가 (작업 완료 신호)

---

## 통신 구조

### Action 클라이언트

**액션 서버**: `execute_vla_task`
**액션 타입**: `catbot_interfaces/action/VlaTask`

**동작 흐름**:
```
패트롤 노드
    ↓
/arm/cmd 토픽 발행 (자연어 프롬프트)
    ↓
Pi Gateway (ArmControlBridge)
    ├─ /arm/cmd 구독
    ├─ Action 클라이언트로 작업 요청
    ├─ 로봇팔 동작 시작 → 바퀴 잠금
    ├─ Action 서버에서 작업 완료 대기
    └─ 작업 완료 → /arm/done 발행 → 바퀴 해제
        ↓
패트롤 노드
    └─ /arm/done 구독 → 다음 단계 진행
```

---

## 사용 방법

### 방법 1: 토픽으로 작업 요청 (패트롤 노드에서)

패트롤 노드에서 `/arm/cmd` 토픽에 자연어 프롬프트를 발행:

```python
from std_msgs.msg import String

arm_cmd_pub = self.create_publisher(String, '/arm/cmd', 10)

# 삽 집기
msg = String()
msg.data = "Pick up the shovel from the right holder."
arm_cmd_pub.publish(msg)
```

### 방법 2: 직접 함수 호출 (Pi Gateway 내부)

```python
arm_bridge = ArmControlBridge(uart, cmdvel_bridge)

# 삽 집기
arm_bridge.execute_vla_task("Pick up the shovel from the right holder.")
```

---

## 주요 작업 프롬프트

### 화장실 청소 작업

```python
tasks = [
    "Pick up the shovel from the right holder.",
    "Scoop the brown snack from the center box using the shovel.",
    "Move the shovel to the left box and discard the snack.",
    "Return the shovel to the right holder."
]
```

### 물 급수 작업

```python
tasks = [
    "Pick up the clear plastic water cup",
    "Pour out the water from the cup",
    "Place the cup under the dispenser",
    "place the cup on the floor"
]
```

---

## 작업 완료 신호

### `/arm/done` 토픽 발행

**토픽**: `/arm/done` (std_msgs/Bool)
**발행 시점**: Action 작업 완료 시
**값**:
- `True`: 작업 성공
- `False`: 작업 실패

**수신자**: 패트롤 노드 (`/arm/done` 구독)

---

## 바퀴 잠금 처리

### 자동 처리

로봇팔 작업 시작 시:
- `arm_active = True` 설정
- `cmdvel_bridge.set_arm_start_active(True)` 호출
- 바퀴 모터 자동 잠금

로봇팔 작업 완료 시:
- `arm_active = False` 설정
- `cmdvel_bridge.set_arm_start_active(False)` 호출
- 바퀴 모터 자동 해제

---

## 의존성

### 필수 패키지

**ROS2 패키지**: `catbot_interfaces`
- Action 인터페이스 정의 (`VlaTask`)

**설치 방법**:
```bash
# 로봇팔 팀의 ROS2 워크스페이스에서 빌드
cd /path/to/catbotArm_ws
colcon build --packages-select catbot_interfaces
source install/setup.bash
```

**Pi Gateway에서 사용**:
- `catbot_interfaces` 패키지가 없어도 동작 (기존 토픽 기반 통신 유지)
- Action 클라이언트는 패키지가 있을 때만 활성화

---

## 코드 구조

### ArmControlBridge 클래스

```python
class ArmControlBridge(Node):
    def __init__(self, uart, cmdvel_bridge):
        # Action 클라이언트 초기화
        self._action_client = ActionClient(self, VlaTask, 'execute_vla_task')
        
        # 작업 완료 신호 발행
        self.pub_arm_done = self.create_publisher(Bool, '/arm/done', 10)
        
        # Action 요청 토픽 구독
        self.sub_arm_cmd = self.create_subscription(String, 'arm/cmd', self.on_arm_cmd, 10)
    
    def execute_vla_task(self, task_prompt: str):
        """Action 서버에 작업 요청"""
        # 바퀴 잠금
        # Action 요청
        # 결과 대기
    
    def on_arm_cmd(self, msg: String):
        """/arm/cmd 토픽 수신 → Action 요청"""
        self.execute_vla_task(msg.data)
```

---

## 패트롤 노드 연동

### 패트롤 노드에서 로봇팔 작업 요청

패트롤 노드가 `/arm/cmd` 토픽에 자연어 프롬프트를 발행하면, Pi Gateway가 자동으로 Action 서버에 요청합니다.

**예시**:
```python
# 패트롤 노드에서
arm_cmd_pub = self.create_publisher(String, '/arm/cmd', 10)

# 삽 집기 요청
msg = String()
msg.data = "Pick up the shovel from the right holder."
arm_cmd_pub.publish(msg)

# 작업 완료 대기
arm_done_sub = self.create_subscription(Bool, '/arm/done', self.on_arm_done, 10)

def on_arm_done(self, msg: Bool):
    if msg.data:
        # 작업 성공 → 다음 단계 진행
        self.get_logger().info("로봇팔 작업 완료")
    else:
        # 작업 실패 → 에러 처리
        self.get_logger().error("로봇팔 작업 실패")
```

---

## 테스트 방법

### 1. Action 서버 확인

```bash
# ROS2 도메인 설정
export ROS_DOMAIN_ID=1

# Action 서버 확인
ros2 action list
ros2 action info /execute_vla_task
```

### 2. Pi Gateway 실행

```bash
# Pi Gateway 실행
python3 -m src.main

# 또는 도커
docker-compose up -d
```

### 3. 작업 요청 테스트

```bash
# 터미널에서 직접 토픽 발행
ros2 topic pub /arm/cmd std_msgs/String "data: 'Pick up the shovel from the right holder.'"
```

### 4. 작업 완료 확인

```bash
# 작업 완료 신호 확인
ros2 topic echo /arm/done
```

---

## 문제 해결

### 문제 1: Action 클라이언트 초기화 실패

**증상**: "catbot_interfaces 패키지가 없습니다" 경고

**해결책**:
```bash
# catbot_interfaces 패키지 빌드
cd /path/to/catbotArm_ws
colcon build --packages-select catbot_interfaces
source install/setup.bash
```

### 문제 2: Action 서버를 찾을 수 없음

**증상**: "로봇팔 Action 서버를 찾을 수 없습니다" 에러

**해결책**:
- 로봇팔 팀의 Action 서버가 실행 중인지 확인
- ROS2 도메인 ID 확인 (`ROS_DOMAIN_ID=1`)
- 네트워크 연결 확인

### 문제 3: 작업 완료 신호가 발행되지 않음

**증상**: `/arm/done` 토픽에 메시지가 없음

**해결책**:
- Action 작업이 실제로 완료되었는지 확인
- 로그에서 "로봇팔 작업 완료" 메시지 확인
- Action 서버의 결과 확인

---

## 요약

### 구현된 기능

- ✅ Action 클라이언트 추가
- ✅ `/arm/cmd` 토픽 구독 (패트롤 노드 요청)
- ✅ `/arm/done` 토픽 발행 (작업 완료 신호)
- ✅ 바퀴 잠금/해제 자동 처리
- ✅ 기존 토픽 기반 통신 유지 (하위 호환성)

### 통신 흐름

1. 패트롤 노드 → `/arm/cmd` 토픽 발행
2. Pi Gateway → Action 서버에 작업 요청
3. 로봇팔 동작 시작 → 바퀴 잠금
4. Action 서버 작업 완료
5. Pi Gateway → `/arm/done` 토픽 발행 → 바퀴 해제
6. 패트롤 노드 → 다음 단계 진행

---

## 작성일

2026-01-27
