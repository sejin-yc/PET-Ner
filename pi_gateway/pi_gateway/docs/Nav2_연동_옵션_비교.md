# Nav2 연동 옵션 비교

Nav2와 연동하는 방법은 두 가지가 있습니다.

---

## 🔄 옵션 비교

### 옵션 1: Nav2가 `cmd_vel_auto` 발행 (현재 방식)

**방법:**
- Nav2 설정에서 출력 토픽을 `cmd_vel_auto`로 변경
- 또는 토픽 리매핑: `ros2 run topic_tools relay /cmd_vel cmd_vel_auto`

**장점:**
- Pi Gateway 코드 수정 불필요
- `cmd_vel_teleop`과 `cmd_vel_auto` 구분 가능

**단점:**
- Nav2 담당자가 설정 변경 필요
- 표준과 다른 토픽 이름 사용

---

### 옵션 2: Pi Gateway가 `/cmd_vel` 구독 (더 간단)

**방법:**
- Pi Gateway 코드에서 `cmd_vel_auto` → `/cmd_vel`로 변경

**장점:**
- Nav2 담당자에게 요청 불필요 (표준 사용)
- 더 간단하고 표준적

**단점:**
- Pi Gateway 코드 수정 필요

**참고:** 현재 구현에서는 `PatrolLoop`가 `cmd_vel_auto`를 발행하지 않습니다. Nav2가 `cmd_vel_auto`를 발행하고, `PatrolLoop`는 액션 실행만 담당합니다 (`patrol/waypoint_reached`, `patrol/aruco_aligned` 구독, `patrol/action_complete` 발행).

---

## 💡 추천: 옵션 2 (표준 `/cmd_vel` 사용)

**이유:**
- Nav2 담당자에게 요청할 필요 없음 (표준 토픽 사용)
- 수정이 매우 간단함 (한 줄만 변경)
- 표준 ROS2 관례를 따름

**수정 방법:**
- `CmdVelMux`의 472줄: `"cmd_vel_auto"` → `"/cmd_vel"`로 변경
- Nav2는 이미 표준 `/cmd_vel`을 발행하므로 추가 설정 불필요

**현재 구현 (옵션 1):**
- Nav2가 `cmd_vel_auto` 토픽 발행 (비표준)
- `CmdVelMux`가 `cmd_vel_auto` 구독
- `PatrolLoop`는 액션 실행만 담당 (이동 명령 발행 안 함)

---

## 🎯 결론

**옵션 2 추천 (표준 `/cmd_vel` 사용):**
- Pi Gateway 코드 한 줄만 수정 (`CmdVelMux`의 472줄)
- Nav2 담당자에게 요청 불필요 (표준 토픽 사용)
- 표준 ROS2 관례를 따름

**수정 내용:**
```python
# src/ros_cmdvel.py 472줄
# 변경 전:
self.sub_a = self.create_subscription(Twist, "cmd_vel_auto", self.on_auto, 10)
# 변경 후:
self.sub_a = self.create_subscription(Twist, "/cmd_vel", self.on_auto, 10)
```

**현재 구현 (옵션 1):**
- Nav2가 `cmd_vel_auto` 토픽 발행 (비표준)
- Nav2 담당자에게 `cmd_vel_auto` 발행 요청 필요
