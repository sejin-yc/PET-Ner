# ROS2 폴더 구현 상태 분석

## 개요

S14P11C203-ROS2 폴더에 이미 구현된 노드들을 분석하여 Pi Gateway의 역할을 명확히 합니다.

---

## ROS2 폴더에 이미 구현된 노드들

### 1. `twist_to_stm_uart_bridge.py` ⚠️ **중복 가능성**

**역할**: ROS2 토픽 → UART 변환

**구독 토픽**:
- `/cmd_vel` (geometry_msgs/Twist)

**동작**:
- `/cmd_vel` 토픽을 구독하여 STM32로 UART 전송
- 고정 PWM 방식 사용

**Pi Gateway와의 관계**:
- ⚠️ **중복**: Pi Gateway의 `RosCmdVelBridge`와 동일한 역할
- **차이점**: 
  - ROS2 폴더: ROS2 노드로 실행
  - Pi Gateway: 웹 대시보드 통신 포함

---

### 2. `primitive_mission_manager_fixed_pwm.py` ✅ **패트롤 담당**

**역할**: 패트롤 경로 계획 및 실행

**발행 토픽**:
- `/cmd_vel_nav` (geometry_msgs/Twist) - 자동 주행 명령
- `/gateway/allow_strafe` (std_msgs/Bool) - 횡이동 허용
- `/arm/cmd` (std_msgs/String) - 로봇팔 작업 요청
- `/servo/cmd` (std_msgs/String) - 서보 작업 요청

**구독 토픽**:
- `/arm/done` (std_msgs/Bool) - 로봇팔 작업 완료
- `/dock/done` (std_msgs/Bool) - 도킹 완료
- `/servo/done` (std_msgs/Bool) - 서보 작업 완료

**Pi Gateway와의 관계**:
- ✅ **패트롤 팀 담당**: 경로 계획 및 주행 명령 발행
- ✅ **Pi Gateway 역할**: `/cmd_vel_nav` 구독, `/arm/done` 발행

---

### 3. `homing.py` ✅ **이미 구현됨**

**역할**: 홈 이동 로직

**동작**:
- TF를 사용하여 현재 위치 확인
- 홈 위치로 이동 후 회전

**Pi Gateway와의 관계**:
- ✅ **이미 구현됨**: Pi Gateway의 `HomingController`와 동일한 로직
- **선택**: Pi Gateway의 구현을 사용하거나 ROS2 폴더의 것을 사용

---

### 4. `aruco_pose_node.py` ✅ **아루코 마커 담당**

**역할**: 아루코 마커 감지 및 위치 정보 발행

**발행 토픽**:
- `/aruco/pose` (geometry_msgs/PoseStamped)
- `/aruco/id` (std_msgs/Int32)

**Pi Gateway와의 관계**:
- ✅ **아루코 팀 담당**: 마커 감지 및 위치 정보 발행
- ⚠️ **Pi Gateway**: 필요 시 구독 가능 (현재는 사용 안 함)

---

## Pi Gateway의 실제 역할

### ✅ 필수 역할 (ROS2 폴더에 없음)

#### 1. 웹 대시보드 통신 ⭐ **핵심**

**이유**: ROS2 폴더에는 웹 대시보드 통신 기능이 없음

**Pi Gateway만 가능**:
- WebSocket (FastAPI) 서버 운영
- 웹 명령 수신 → ROS2 토픽 변환
- 텔레메트리 전송

---

#### 2. 명령 통합 (Mux) ⭐ **핵심**

**이유**: 여러 입력 소스를 통합해야 함

**입력 소스**:
- 웹 대시보드 (`/cmd_vel_teleop`)
- 패트롤 노드 (`/cmd_vel_nav`)

**Pi Gateway만 가능**:
- `CmdVelMux`로 두 명령 통합
- 우선순위 관리 (teleop vs auto)

---

#### 3. WebRTC 스트리밍 제어 ⭐ **핵심**

**이유**: ROS2 폴더에는 웹 통신 기능이 없음

**Pi Gateway만 가능**:
- 프론트엔드 요청 수신
- `robot_webrtc.py` 프로세스 관리

---

#### 4. MQTT 브릿지 ⭐ **중요**

**이유**: 백엔드와 통신 필요

**Pi Gateway만 가능**:
- ROS2 토픽 ↔ MQTT 변환

---

### ⚠️ 중복 가능성 (ROS2 폴더에도 있음)

#### 1. UART 브릿지

**ROS2 폴더**: `twist_to_stm_uart_bridge.py`
- ROS2 노드로 실행
- `/cmd_vel` 구독 → UART 전송

**Pi Gateway**: `RosCmdVelBridge`
- 웹 대시보드 통신 포함
- `/cmd_vel_out` 구독 → UART 전송

**해결 방안**:
- **옵션 1**: ROS2 폴더의 것을 사용 (권장)
  - Pi Gateway는 `/cmd_vel_out` 발행만
  - ROS2 폴더의 브릿지가 `/cmd_vel` 구독하여 UART 전송
- **옵션 2**: Pi Gateway의 것을 사용
  - ROS2 폴더의 브릿지는 사용 안 함

---

## 권장 구조

### 구조 1: ROS2 폴더의 UART 브릿지 사용 (권장)

```
웹 대시보드
    ↓
Pi Gateway
    ├─ /cmd_vel_teleop 발행
    └─ CmdVelMux
        ├─ /cmd_vel_teleop 구독
        ├─ /cmd_vel_nav 구독 (패트롤)
        └─ /cmd_vel 발행 (통합)
            ↓
ROS2 폴더 (twist_to_stm_uart_bridge.py)
    ├─ /cmd_vel 구독
    └─ UART → STM32
```

**장점**:
- 역할 분리 명확
- ROS2 폴더는 ROS2만 담당
- Pi Gateway는 웹 통신 담당

**Pi Gateway 역할**:
- 웹 대시보드 통신
- 명령 통합 (Mux)
- `/cmd_vel` 발행 (ROS2 폴더 브릿지가 구독)

---

### 구조 2: Pi Gateway의 UART 브릿지 사용

```
웹 대시보드
    ↓
Pi Gateway
    ├─ /cmd_vel_teleop 발행
    ├─ CmdVelMux
    │   ├─ /cmd_vel_teleop 구독
    │   ├─ /cmd_vel_nav 구독 (패트롤)
    │   └─ /cmd_vel_out 발행
    └─ RosCmdVelBridge
        ├─ /cmd_vel_out 구독
        └─ UART → STM32
```

**장점**:
- 모든 통신이 Pi Gateway에서 관리
- 중앙 집중식 제어

**단점**:
- ROS2 폴더의 브릿지와 중복

---

## Pi Gateway의 최소 필수 역할

### ✅ 반드시 필요한 것

1. **웹 대시보드 서버** (FastAPI/WebSocket)
   - 사용자 인터페이스 제공
   - 수동 조작 명령 수신
   - 텔레메트리 전송

2. **명령 통합 (Mux)**
   - 웹 명령 + 패트롤 명령 통합
   - 우선순위 관리

3. **WebRTC 스트리밍 제어**
   - 프론트엔드 요청 수신
   - 스트리밍 프로세스 관리

4. **MQTT 브릿지**
   - 백엔드와 통신

5. **작업 완료 신호 발행**
   - `/arm/done`, `/dock/done`, `/servo/done`
   - 패트롤 노드가 필요로 함

### ⚠️ 선택사항 (ROS2 폴더에도 있음)

1. **UART 브릿지**
   - ROS2 폴더의 것을 사용하거나 Pi Gateway의 것을 사용
   - 둘 중 하나만 사용

2. **Homing 로직**
   - ROS2 폴더의 `homing.py` 사용 가능
   - 또는 Pi Gateway의 `HomingController` 사용

---

## 최종 권장 구조

### Pi Gateway의 역할

```
Pi Gateway (필수)
├─ 웹 대시보드 서버 (FastAPI/WebSocket) ✅ 필수
├─ 명령 통합 (CmdVelMux) ✅ 필수
│   ├─ /cmd_vel_teleop 구독 (웹)
│   ├─ /cmd_vel_nav 구독 (패트롤)
│   └─ /cmd_vel 발행 (통합)
├─ WebRTC 스트리밍 제어 ✅ 필수
├─ MQTT 브릿지 ✅ 필수
└─ 작업 완료 신호 발행 ✅ 필수
    ├─ /arm/done 발행
    ├─ /dock/done 발행
    └─ /servo/done 발행
```

### ROS2 폴더의 역할

```
ROS2 폴더
├─ 패트롤 노드 (primitive_mission_manager_fixed_pwm.py)
│   ├─ 경로 계획
│   ├─ /cmd_vel_nav 발행
│   └─ /arm/cmd 발행
├─ UART 브릿지 (twist_to_stm_uart_bridge.py)
│   ├─ /cmd_vel 구독
│   └─ UART → STM32
├─ 아루코 마커 (aruco_pose_node.py)
└─ 홈 이동 (homing.py)
```

---

## 결론

### Pi Gateway는 여전히 필수입니다

**이유**:
1. **웹 대시보드 통신**: ROS2 폴더에는 없음
2. **명령 통합**: 여러 입력 소스 통합 필요
3. **WebRTC 스트리밍**: 웹 통신 필요
4. **MQTT 브릿지**: 백엔드 통신 필요
5. **작업 완료 신호**: 패트롤 노드가 필요로 함

### 중복 제거 방안

**UART 브릿지**:
- ROS2 폴더의 `twist_to_stm_uart_bridge.py` 사용 권장
- Pi Gateway는 `/cmd_vel` 발행만 담당
- UART 전송은 ROS2 폴더 브릿지가 담당

**Homing**:
- ROS2 폴더의 `homing.py` 사용 가능
- 또는 Pi Gateway의 `HomingController` 사용
- 둘 중 하나만 사용

---

## 요약

| 기능 | ROS2 폴더 | Pi Gateway | 비고 |
|------|----------|------------|------|
| 패트롤 경로 계획 | ✅ | ❌ | 패트롤 팀 담당 |
| 자동 주행 명령 | ✅ 발행 | ✅ 구독 | Pi Gateway는 구독만 |
| 웹 대시보드 통신 | ❌ | ✅ | **Pi Gateway만 가능** |
| 명령 통합 (Mux) | ❌ | ✅ | **Pi Gateway만 가능** |
| UART 브릿지 | ✅ | ✅ | **둘 중 하나만 사용** |
| WebRTC 스트리밍 | ❌ | ✅ | **Pi Gateway만 가능** |
| MQTT 브릿지 | ❌ | ✅ | **Pi Gateway만 가능** |
| 작업 완료 신호 | ❌ 구독 | ✅ 발행 | **Pi Gateway만 가능** |

**결론**: ROS2 폴더에 많은 것이 구현되어 있더라도, **Pi Gateway는 여전히 필수적인 통신 브릿지** 역할을 합니다.

---

## 작성일

2026-01-27
