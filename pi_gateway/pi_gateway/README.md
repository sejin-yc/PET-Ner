
---

젯슨에서 실행

```
cd ~/pi_gateway
source /opt/ros/humble/setup.bash
source ~/pi_gateway/.venv_cpu/bin/activate

export BE_WS_URL="wss://i14c203.p.ssafy.io/ws"
export PI_GATEWAY_PUBLIC_URL="https://i14c203.p.ssafy.io"
export BE_USER_ID="1"
export CAMERA_TOPIC="/front_cam/compressed"
export VIDEO_SAVE_DIR="/home/ssafy/videos"

python3 scripts/cat_detection_service.py \
  --ckpt models/swin_tiny_best.pt \
  --yolo-pose models/yolo_pose.pt

source .venv_cpu/bin/activate
pip install -r requirements.txt
pip install requests aiohttp ultralytics

source /opt/ros/humble/setup.bash
export BE_WS_URL=wss://i14c203.p.ssafy.io/ws
export PI_GATEWAY_PUBLIC_URL=https://i14c203.p.ssafy.io
export BE_USER_ID=1
export VIDEO_SAVE_DIR=/home/ssafy/videos
export CAMERA_TOPIC=/front_cam/compressed
export VIDEO_UPLOAD_URL=https://i14c203.p.ssafy.io/api/videos/upload

python3 scripts/cat_detection_webrtc.py \
  --ckpt models/swin_tiny_best.pt \
  --yolo-pose models/yolo_pose.pt \
  --record-sec 15 \
  --prebuffer 3 \
  --fps 15


```
---

## 구현 상태

- 통신 구조 및 안전 정책: **설계 완료**
- UART 프로토콜: **명세 기반 구현**
- 제어 로직: **단계적 확장 구조**

AI 추론 지연, 네트워크 오류 상황에서도  
로봇의 **주행 안정성과 안전성**을 보장하도록 설계되었다.

---

## 제어 / 통신 흐름 요약

### 제어 명령 흐름 (Downstream)

```

Web UI / Backend / AI 이벤트
→ Raspberry Pi Gateway

* 제어 모드 판단 (teleop / auto)
* 안전 정책 적용 (E-STOP / danger)
  → UART 바이너리 명령
  → STM32 모터 제어

```

- 상위 시스템은 **“무엇을 할지”**만 전달
- Raspberry Pi가 **“어떻게 안전하게 실행할지”**를 결정

---

### 상태 보고 흐름 (Upstream)

```

STM32 센서 / 상태
→ UART 텔레메트리
→ Raspberry Pi 디코딩
→ Backend / Web (JSON)

```

- 센서 바이트 파싱은 **Raspberry Pi에서만 수행**
- Backend / Web은 **JSON 형태의 상태 데이터만 사용**

---

## Interface Contract

이 섹션에 정의된 변수명과 이벤트명은  
**Web / Backend / Gateway / STM32 간 공통 인터페이스 규약**.

---

### 제어 입력 변수 (공통)

**참고:** 현재 구현에서는 WebSocket `/ws/teleop`이 버튼/조이스틱 이벤트를 받아 내부적으로 `vx`, `vy`, `wz`로 변환합니다.  
Backend나 다른 시스템에서 직접 속도 명령을 보낼 경우를 위한 공통 인터페이스 규약:

| key | type | 설명 |
|---|---|---|
| vx | float | 전/후 이동 속도 (+전진) |
| vy | float | 좌/우 이동 속도 (+방향 팀 합의 필요) |
| wz | float | 회전 속도 (+CCW) |
| control_mode | string | `teleop` / `auto` |
| estop | bool | true면 즉시 정지 |
| timestamp | float | epoch time (debug용) |

**실제 WebSocket 구현 (`/ws/teleop`):**
- `press` 이벤트: `{"type": "press", "key": "up|down|left|right|rot_l|rot_r", "down": bool, "timestamp": float}`
- `joy` 이벤트: `{"type": "joy", "joy_x": float, "joy_y": float, "joy_active": bool, "timestamp": float}`
- `mode` 이벤트: `{"type": "mode", "mode": "teleop|auto", "timestamp": float}`
- `estop` 이벤트: `{"type": "estop", "value": bool, "timestamp": float}`
- `feed` 이벤트: `{"type": "feed", "level": 1~3, "timestamp": float}`

---

### 이벤트 코드 (Backend → Gateway)

**실제 Backend/Frontend에서 사용하는 형식 (MQTT `/pub/robot/control`):**

Backend는 MQTT를 통해 다음 형식으로 명령을 보냅니다:
- `{"type": "MOVE", "linear": float, "angular": float}` - 이동 명령
- `{"type": "STOP"}` - 즉시 정지
- `{"type": "MODE", "value": "auto"|"manual"}` - 모드 전환

MQTT 브릿지(`scripts/mqtt_pi_bridge.py`)가 이를 Pi Gateway 형식으로 변환합니다:
- `MOVE` → WebSocket `press` 이벤트 (up/down/left/right)
- `STOP` → 모든 `press` 해제
- `MODE` → `POST /control/mode` API 호출

**Pi Gateway에서 직접 사용하는 형식:**
- **WebSocket `/ws/teleop`**: 
  - `{"type": "mode", "mode": "teleop"|"auto"}`
  - `{"type": "estop", "value": true|false}`
  - `{"type": "feed", "level": 1~3}`
- **REST API**: 
  - `POST /control/estop` → `{"value": true|false}`
  - `POST /control/mode` → `{"mode": "teleop"|"auto"}`
  - `POST /action/feed` → `{"level": 1~3}`
- **ROS 모드**: ROS 토픽을 통한 제어 (`cmd_vel_teleop`, `cmd_vel_auto`, `patrol/*` 등)

**참고:** README에 있던 `SET_MODE_TELEOP`, `SET_MODE_AUTO`, `AI_DANGER`, `PATROL_START`, `PATROL_STOP`, `FEED_TRIGGER` 같은 이벤트 코드는 실제로 사용되지 않습니다. Backend는 `MOVE`, `STOP`, `MODE`만 사용합니다.

---

### 텔레메트리 변수 (Gateway → Backend / Web)

**공통 인터페이스 규약 (Backend/Web에서 사용하는 형식):**

| key | type | 설명 |
|---|---|---|
| battery_v | float | 배터리 전압 (V) |
| battery_pct | int | 배터리 잔량 (%) |
| charging | bool | 충전 중 여부 |
| enc_fl | int | 앞좌 엔코더 누적 tick |
| enc_fr | int | 앞우 엔코더 누적 tick |
| enc_rl | int | 뒤좌 엔코더 누적 tick |
| enc_rr | int | 뒤우 엔코더 누적 tick |
| yaw | float | IMU yaw (rad). telemetry/imu 수신 시 포함. /odom 산출 및 pose 방향에 사용. |
| timestamp | float | 텔레메트리 수집 시각 (epoch time) |

**참고:** 실제 Gateway 구현에서는 중첩 구조로 반환되지만, Backend/Web 인터페이스에서는 위의 평면 형식을 사용합니다.

**실제 Gateway API 반환 형식 (WebSocket `/ws/telemetry`, HTTP `/telemetry/latest`):**

```json
{
  "type": "telemetry",
  "battery": {
    "type": "battery",
    "vbat_V": 11.7,
    "vbat_mV": 11700,
    "soc_percent": 62,
    "charging": false,
    "error_code": 0
  },
  "imu": {
    "type": "imu",
    "yaw": 1.24,
    "pitch": 0.0,
    "roll": 0.0,
    "acc_x": 0.0,
    "acc_y": 0.0,
    "acc_z": 9.8
  },
  "encoders": {
    "type": "encoder",
    "enc_fl": 12345,
    "enc_fr": 12350,
    "enc_rl": 12340,
    "enc_rr": 12355
  },
  "ts": 1737700001.21
}
```

**매핑 관계:**
- `battery_v` ← `battery.vbat_V`
- `battery_pct` ← `battery.soc_percent`
- `charging` ← `battery.charging`
- `enc_fl` ← `encoders.enc_fl`
- `enc_fr` ← `encoders.enc_fr`
- `enc_rl` ← `encoders.enc_rl`
- `enc_rr` ← `encoders.enc_rr`
- `yaw` ← `imu.yaw`
- `timestamp` ← `ts`

---

## JSON 인터페이스 예시

### Teleop 제어 (Web → Gateway, WebSocket `/ws/teleop`)

**버튼 입력:**
```json
{
  "type": "press",
  "key": "up",
  "down": true,
  "timestamp": 1737700000.12
}
```

**조이스틱 입력:**
```json
{
  "type": "joy",
  "joy_x": 0.5,
  "joy_y": 0.0,
  "joy_active": true,
  "timestamp": 1737700000.12
}
```

**모드 전환:**
```json
{
  "type": "mode",
  "mode": "teleop",
  "timestamp": 1737700000.12
}
```

**참고:** Backend에서 직접 속도 명령을 보낼 경우를 위한 이론적 형식 (현재 미구현):
```json
{
  "type": "control",
  "control_mode": "teleop",
  "vx": 0.2,
  "vy": 0.0,
  "wz": 0.1,
  "estop": false,
  "timestamp": 1737700000.12
}
```

---

### 이벤트 트리거 (Backend → Gateway)

**참고:** 현재 구현에서는 WebSocket 이벤트나 REST API를 사용합니다. 아래는 이론적 형식 (향후 확장 가능):

```json
{
  "type": "event",
  "event": "AI_DANGER",
  "reason": "cat_near_stairs",
  "timestamp": 1737700001.02
}
```

**실제 구현 예시:**
- 급식: `POST /action/feed` → `{"level": 1~3}`
- E-STOP: `POST /control/estop` → `{"value": true|false}`
- 모드 전환: `POST /control/mode` → `{"mode": "teleop"|"auto"}`
- WebSocket: `/ws/teleop` → `{"type": "feed", "level": 1~3, "timestamp": ...}`

---

### 텔레메트리 업로드 (Gateway → Backend / Web)

**공통 인터페이스 형식 (Backend/Web에서 기대하는 형식):**

```json
{
  "type": "telemetry",
  "battery_v": 11.7,
  "battery_pct": 62,
  "charging": false,
  "enc_fl": 12345,
  "enc_fr": 12350,
  "enc_rl": 12340,
  "enc_rr": 12355,
  "yaw": 1.24,
  "timestamp": 1737700001.21
}
```

**참고:** 실제 Gateway API는 중첩 구조로 반환하지만, Backend/Web 인터페이스에서는 위의 평면 형식을 사용합니다. MQTT 브릿지나 다른 변환 레이어에서 중첩 구조를 평면 형식으로 변환합니다.

---

## STM32

* STM32는 Raspberry Pi와 **UART 바이너리 프로토콜만** 사용

### 현재 Gateway에 구현된 UART ID (코드와 동일)

| 방향 | ID | 이름 | Payload 형식 | 설명 |
|------|-----|------|-------------|------|
| Pi→STM | 0x01 | CMD_VEL | float32×3 (vx,vy,wz) | 이동 속도 명령 |
| Pi→STM | 0x02 | HEARTBEAT | payload 없음 | STM 워치독/연결 확인용, Pi가 약 5Hz 전송 |
| Pi→STM | 0x05 | FEED | uint8 level (1~3) | 급식 (Nav2 신호 기반, 젯슨이 사료량 계산) |
| Pi→STM | 0x06 | ARM_START | uint8 action_id (0=정지, 1=변 치우기) | 로봇팔 동작 시작/정지 (젯슨이 제어) |
| Pi→STM | 0x07 | ARM_POSITION_CORRECT | float32×3 (dx,dy,dz) | 로봇 위치 보정 (젯슨이 제어) |
| Pi→STM | 0x08 | CHURU | uint8 enable (0=정지, 1=츄르 주기) | 츄르(간식) 주기 (웹 API로만 호출) |
| Pi→STM | 0x09 | ARM_WATER | uint8 action (0~4) | 급수 단계별 제어 (젯슨이 제어) |
| Pi→STM | 0x10 | ESTOP | uint8 value (0/1) | 비상정지 (value=1: 정지, value=0: 해제) |
| STM→Pi | 0x81 | BATTERY | uint16 mV, uint8 soc, uint8 charging, uint8 error | 배터리 상태 |
| STM→Pi | 0x82 | ENCODER | enc_fl,enc_fr,enc_rl,enc_rr (각 int32, 16B) | 앞좌/앞우/뒤좌/뒤우 4륜 누적 틱 |
| STM→Pi | 0x83 | IMU | float32×6 (yaw,pitch,roll,accx,accy,accz) | IMU 센서 데이터 |
| STM→Pi | 0x84 | STATUS | uint8 status_type, uint8 status_code, uint8 flags (3B) | 작업 완료/실패, 에러, 상태 |

프레임 형식: `0xAA 0x55` + msg_id + length + payload + XOR checksum (`uart_frames.py` 참고. ID·decode 포함).

**ROS 모드**에서는 위 텔레메트리(BATTERY/ENCODER/IMU/STATUS)가 `telemetry/battery`, `telemetry/encoder`, `telemetry/imu`, `telemetry/status` 토픽으로 publish됨.  
엔코더 누적 틱은 `EncoderOdomNode`가 `telemetry/encoder`를 구독해 (vx,vy,wz) 계산, **`telemetry/imu`의 yaw**로 body→world 변환 및 pose.orientation 적용 후 **`nav_msgs/Odometry`** 형식으로 **`/odom`**에 publish. (yaw는 IMU 사용, wz 적분 안 함.) 파라미터(`config/params.yaml`의 `encoder`: `meters_per_tick`, `odom_lx`, `odom_ly`)로 휠/기체 치수에 맞게 조정.

**Nav2 연동:**
- Pi Gateway는 Nav2의 `cmd_vel_auto` 토픽을 구독하여 자율 주행 명령을 받습니다.
- Nav2가 `patrol/waypoint_reached` 토픽을 발행하면 Pi Gateway가 액션(급식, 변 치우기, 급수)을 실행합니다.
- Pi Gateway는 `patrol/action_complete` 토픽을 발행하여 Nav2에 액션 완료를 알립니다.
- 자세한 내용: `docs/Nav2_토픽_명세.md` 참고

**젯슨 연동:**
- 로봇팔 제어: 젯슨이 `arm/start`, `arm/water`, `arm/position_correct` 토픽을 발행하면 Pi Gateway가 UART로 STM32에 전송합니다.
- 급식 사료량 계산: Pi Gateway가 `feed/request` 토픽을 발행하면 젯슨이 FEED_AI 모델로 사료량을 계산하여 `feed/amount` 토픽으로 발행합니다.
- 작업 완료 신호: 젯슨이 `arm/job_complete` 토픽을 발행하여 변 치우기/급수 완료를 알립니다.
- 자세한 내용: `docs/젯슨_파이_DDS_통신.md`, `docs/급식_젯슨_연동_가이드.md` 참고

### STATUS 메시지 상세

**Payload 구조 (3바이트):**
- `status_type` (uint8): 상태 타입
  - `0x01`: 작업 완료 (`JOB_COMPLETE`)
  - `0x02`: 작업 실패 (`JOB_FAILED`)
  - `0x03`: 에러 발생 (`ERROR`)
  - `0x04`: 상태 변경 (`STATE`)
- `status_code` (uint8): 상태 코드 (타입별 의미 다름)
  - 작업 완료: `0x01`=급식, `0x02`=츄르 (변 치우기/급수는 젯슨이 arm/job_complete로 처리)
  - 작업 실패: `0x01`=급식, `0x02`=츄르 (변 치우기/급수는 젯슨이 arm/job_complete로 처리)
  - 에러: `0x01`=모터, `0x02`=센서, `0x03`=통신타임아웃, `0x04`=과부하
- `flags` (uint8): 상태 플래그 (bitmask)
  - `0x01`: 로봇팔 동작 중 (`FLAG_ARM_ACTIVE`)
  - `0x02`: 바퀴 잠금 (`FLAG_WHEELS_LOCKED`)
  - `0x04`: 비상정지 활성화 (`FLAG_EMERGENCY_STOP`)

**예시:**
- 급식 완료: `status_type=0x01, status_code=0x01, flags=0x00` (STM32가 서보모터 제어 완료)
- 츄르 주기 완료: `status_type=0x01, status_code=0x02, flags=0x00` (STM32가 서보모터 제어 완료)
- 변치우기 중 (바퀴 잠금): `status_type=0x04, status_code=0x00, flags=0x03` (ARM_ACTIVE + WHEELS_LOCKED)

**작업 완료 신호 발신자:**
- **급식/츄르**: STM32가 STATUS 메시지로 완료 신호 전송 (STM32가 서보모터 제어)
- **변 치우기/급수**: 젯슨이 `arm/job_complete` ROS2 토픽으로 완료 신호 발행 (젯슨이 로봇팔 제어)

---

## 실행 (데모 모드: STM / ROS 없이 동작)

> 기본값은 ROS 모드 (`ROS_ENABLED=1`, `DEMO_MODE=0`). 데모 모드는 `DEMO_MODE=1`로 선택 가능.

### Pi 권장: 스크립트 한 번에 (venv 자동)

```bash
cd pi_gateway
chmod +x scripts/run_gateway.sh
./scripts/run_gateway.sh
```

- venv 없으면 `.venv` 생성 후 `pip install -r requirements.txt` 실행
- venv Python으로 `python3 -m src.main` 실행  
- Pi에서 실행 안 될 때: `docs/파이_Raspberry_Pi_실행_가이드.md` 참고

### 수동 (venv 생성 → 설치 → 실행)

```bash
cd pi_gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# ROS 모드 실행 (기본값)
python3 -m src.main
```

**`ModuleNotFoundError: No module named 'src'`** 이 나오면 프로젝트 루트에서 `python3 -m src.main` 사용.  
**웹 ↔ Gateway 연결만** 테스트할 땐 데모 모드(`DEMO_MODE=1`)로 실행하면 ROS/UART 없이 WebSocket·REST 동작.

* Health Check: `GET /health`
* WebSocket: `/ws/teleop`
* E-STOP: `POST /control/estop`  (`{"value": true|false}`)
* 모드 전환: `POST /control/mode` (`{"mode":"teleop"|"auto"}`)
* 급식 실행: `POST /action/feed` (`{"level":1~3}`) - **현재 사용 안 함**. 급식은 Nav2 신호 기반으로 자동 실행됩니다 (Nav2 waypoint 도착 → Pi Gateway가 젯슨에 `feed/request` 발행 → 젯슨이 FEED_AI 모델로 사료량 계산 → `feed/amount` 발행 → Pi Gateway가 UART로 STM32 전송). 웹 UI에는 급식 버튼 없음. 향후 웹에서 시간 설정 시 급식장소로 이동하여 급식하는 기능에 사용 예정.
* 츄르(간식) 주기: `POST /feed/fill` (`{"enable":0|1}`) - 웹 UI에서 버튼 클릭 시 즉시 실행 (젯슨 연동 없음, Pi Gateway → STM32 직접 제어)

### 환경변수

* `ROS_ENABLED=1` : ROS 모드 활성화 (기본값: True)
* `DEMO_MODE=0` : 데모 모드 비활성화 (기본값: False). `DEMO_MODE=1`로 설정하면 ROS/UART 미연결 데모 모드
* `UART_ENABLED=1` : UART 활성화 (기본값: params.yaml의 `uart.enabled` 값)
* `HOST=0.0.0.0`
* `PORT=8000`
* `UART_PORT=/dev/ttyAMA0` : UART 포트 (기본값: params.yaml의 `uart.port` 값)
* `UART_BAUD=115200` : UART 보드레이트 (기본값: params.yaml의 `uart.baudrate` 값)
* `UART_DEBUG_TX=1` : UART 전송 시마다 `[UART TX] <hex>` 로그 (실기기 전송 중에도 확인용)
* `UART_DEBUG_RX=1` : UART 수신 시마다 `[UART RX] <hex>` 로그

---

## 실행 모드

### ROS 모드 (기본값)

ROS 모드가 기본입니다. ROS2가 설치되어 있으면 자동으로 활성화됩니다.

```bash
# 기본 실행 (ROS 모드)
python3 -m src.main

# UART 포트 지정 (필요 시)
export UART_PORT=/dev/ttyAMA0   # GPIO 직결(PA9/PA10 ↔ GPIO14/15) 시
# 또는 /dev/ttyUSB0 (USB-UART 동글 사용 시)
export UART_ENABLED=1
python3 -m src.main
```

### 데모 모드 (선택사항)

웹 ↔ Gateway 연결만 테스트할 때 사용:

```bash
export DEMO_MODE=1
python3 -m src.main
```

시리얼 TX가 잘 나가는지 로그로 확인하려면 `UART_DEBUG_TX=1` 을 추가한 뒤 실행.  
자세한 확인 방법은 `docs/UART_통신_확인_가이드.md` 참고.

> ROS 의존성(`rclpy`, `geometry_msgs`)은
> pip이 아닌 ROS 배포판(apt) 기반 설치 권장 (`requirements_ros.txt` 참고)

---

## 파이로 코드 보내기 & 실행

**수정한 코드 → 파이 전송**
```bash
cd pi_gateway
ROBOT_USER=c203 ROBOT_IP=192.168.100.254 ROBOT_PATH=~/pi_gateway ./scripts/sync_to_robot.sh
```
(계정/IP/경로는 환경에 맞게 변경. `scripts/sync_to_robot.sh` 기본값 사용 가능)

**파이에서 Gateway 실행**
```bash
ssh c203@192.168.100.254
cd ~/pi_gateway
./scripts/run_gateway.sh
```

자세한 절차·설정·문제 해결: `docs/파이_코드_보내기_및_실행_가이드.md`

---

## 급식 vs 츄르

| 구분 | 급식 (FEED) | 츄르 (CHURU) |
|------|------------|-------------|
| 실행 방식 | Nav2 신호 기반 자동 실행 | 웹 UI 버튼 클릭 (수동) |
| 통신 경로 | Nav2 → Pi → 젯슨 → Pi → STM32 | 웹 API → Pi → STM32 |
| 사료량 계산 | 젯슨 FEED_AI 모델 사용 | 없음 (고정량) |
| ROS2 토픽 | `feed/request`, `feed/amount` 사용 | 사용 안 함 |
| UART ID | `ID_FEED = 0x05` | `ID_CHURU = 0x08` |
| 완료 신호 | STM32 STATUS | STM32 STATUS |

자세한 내용: `docs/급식_로직_전체_흐름.md` 참고

---

## 요약

| 계층           | 역할                   |
| ------------ | -------------------- |
| Frontend     | UI / 사용자 입력 / 상태 표시  |
| Backend      | 인증 / 로직 / 이벤트 라우팅    |
| Nav2         | 경로 계획 / 자율 주행 / cmd_vel_auto 발행 |
| Jetson       | AI 추론 / 로봇팔 제어 / 사료량 계산 |
| Raspberry Pi | 제어 정책 / 안전 / 프로토콜 변환 / Nav2-젯슨-STM32 브릿지 |
| STM32        | 모터 / 센서 / 저수준 안전     |




