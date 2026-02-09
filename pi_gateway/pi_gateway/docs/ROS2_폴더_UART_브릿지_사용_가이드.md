# ROS2 폴더 UART 브릿지 사용 가이드

## 개요

ROS2 폴더의 `twist_to_stm_uart_bridge.py`를 사용하여 UART 전송을 담당하도록 변경했습니다.

---

## 변경 사항

### 1. CmdVelMux 변경

**변경 전**:
- `/cmd_vel_out` 토픽 발행
- Pi Gateway의 `RosCmdVelBridge`가 구독하여 UART 전송

**변경 후**:
- `/cmd_vel` 토픽 발행
- ROS2 폴더의 `twist_to_stm_uart_bridge.py`가 구독하여 UART 전송

**코드 변경**:
```python
# 변경 전
self.pub_out = self.create_publisher(Twist, "cmd_vel_out", 10)
self.sub_a = self.create_subscription(Twist, "/cmd_vel", self.on_auto, 10)

# 변경 후
self.pub_out = self.create_publisher(Twist, "/cmd_vel", 10)  # ROS2 폴더 브릿지가 구독
self.sub_a = self.create_subscription(Twist, "/cmd_vel_nav", self.on_auto, 10)  # 패트롤 노드 명령 구독
```

---

### 2. RosCmdVelBridge 변경

**변경 전**:
- `/cmd_vel_out` 구독하여 UART로 전송
- cmd_vel UART 전송 담당

**변경 후**:
- `/cmd_vel_out` 구독 제거
- cmd_vel UART 전송 제거
- **유지**: Heartbeat, Feed, Estop, 로봇팔 바퀴 잠금

**코드 변경**:
```python
# 변경 전
self.sub_cmd = self.create_subscription(Twist, "cmd_vel_out", self.on_cmd_vel, 10)
# cmd_vel UART 전송 로직

# 변경 후
# cmd_vel 구독 제거 (ROS2 폴더 브릿지가 담당)
# Heartbeat, Feed, Estop, 로봇팔 바퀴 잠금만 유지
```

---

### 3. HomingController 변경

**변경 전**:
- `/cmd_vel_nav` 토픽 발행 (추정)

**변경 후**:
- `/cmd_vel_nav` 토픽 발행 (패트롤 노드와 동일한 토픽)
- CmdVelMux가 통합하여 `/cmd_vel`로 발행

---

## 통신 구조

### 변경 후 구조

```
웹 대시보드
    ↓
Pi Gateway
    ├─ /cmd_vel_teleop 발행 (웹 명령)
    └─ CmdVelMux
        ├─ /cmd_vel_teleop 구독 (웹)
        ├─ /cmd_vel_nav 구독 (패트롤 + 홈 이동)
        └─ /cmd_vel 발행 (통합)
            ↓
ROS2 폴더 (twist_to_stm_uart_bridge.py)
    ├─ /cmd_vel 구독
    └─ UART → STM32
```

---

## Pi Gateway의 역할

### ✅ 담당하는 것

1. **웹 대시보드 통신**
   - WebSocket 서버 운영
   - 수동 조작 명령 수신

2. **명령 통합 (Mux)**
   - 웹 명령 + 패트롤 명령 통합
   - `/cmd_vel` 토픽 발행

3. **UART 제어 (cmd_vel 제외)**
   - Heartbeat 전송
   - Feed 명령 전송
   - Estop 처리
   - 로봇팔 동작 중 바퀴 잠금 (cmd_vel=0)

4. **WebRTC 스트리밍 제어**
   - 프론트엔드 요청 수신
   - 스트리밍 프로세스 관리

5. **MQTT 브릿지**
   - 백엔드와 통신

6. **작업 완료 신호 발행**
   - `/arm/done`, `/dock/done`, `/servo/done`

### ❌ 담당하지 않는 것

1. **cmd_vel UART 전송**
   - ROS2 폴더의 `twist_to_stm_uart_bridge.py`가 담당

---

## ROS2 폴더 브릿지 설정

### 실행 방법

ROS2 폴더의 `twist_to_stm_uart_bridge.py`를 실행해야 합니다:

```bash
# ROS2 워크스페이스에서
cd /path/to/S14P11C203-ROS2/[Local] mission
source /opt/ros/humble/setup.bash
ros2 run priority twist_to_stm_uart_bridge
```

### 설정 확인

**토픽 구독**: `/cmd_vel` (Pi Gateway가 발행)

**UART 포트**: `/dev/ttyAMA0` 또는 `/dev/ttyUSB0` (설정에 따라)

---

## 테스트 방법

### 1. 토픽 확인

```bash
# ROS2 도메인 설정
export ROS_DOMAIN_ID=1

# Pi Gateway가 발행하는 토픽 확인
ros2 topic echo /cmd_vel

# ROS2 폴더 브릿지가 구독하는지 확인
ros2 topic hz /cmd_vel
```

### 2. 통신 흐름 확인

```bash
# 웹 대시보드에서 수동 조작
# → /cmd_vel_teleop 발행 확인
ros2 topic echo /cmd_vel_teleop

# 패트롤 노드에서 자동 주행
# → /cmd_vel_nav 발행 확인
ros2 topic echo /cmd_vel_nav

# 통합된 명령 확인
# → /cmd_vel 발행 확인
ros2 topic echo /cmd_vel
```

---

## 주의사항

### 1. ROS2 폴더 브릿지 실행 필수

**중요**: ROS2 폴더의 `twist_to_stm_uart_bridge.py`가 실행되어야 합니다.

**없으면**:
- `/cmd_vel` 토픽은 발행되지만 UART로 전송되지 않음
- STM32가 명령을 받지 못함

### 2. 토픽명 일치

**Pi Gateway**: `/cmd_vel` 발행
**ROS2 폴더 브릿지**: `/cmd_vel` 구독

**일치 확인 필요**:
- ROS2 폴더 브릿지의 `twist_topic` 파라미터가 `/cmd_vel`인지 확인

### 3. 로봇팔 바퀴 잠금

**현재 구현**:
- 로봇팔 동작 중 Pi Gateway가 직접 `cmd_vel=0`을 UART로 전송
- ROS2 폴더 브릿지를 통하지 않고 직접 전송

**이유**:
- 즉시 바퀴를 잠가야 하므로 직접 전송 필요

---

## 요약

### 변경 사항

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| **CmdVelMux 발행** | `/cmd_vel_out` | `/cmd_vel` |
| **CmdVelMux 구독** | `/cmd_vel` (Nav2) | `/cmd_vel_nav` (패트롤) |
| **UART 전송** | Pi Gateway | ROS2 폴더 브릿지 |
| **Pi Gateway 역할** | UART 전송 포함 | 명령 통합만 |

### 통신 흐름

```
웹 대시보드 → /cmd_vel_teleop
패트롤 노드 → /cmd_vel_nav
    ↓
Pi Gateway (CmdVelMux)
    └─ /cmd_vel 발행 (통합)
        ↓
ROS2 폴더 브릿지
    └─ UART → STM32
```

---

## 작성일

2026-01-27
