# MQTT vs WebSocket 사용 가이드

## 🎯 핵심 답변

**Pi Gateway는 WebSocket을 제공합니다.**

**FE/BE는 MQTT를 사용하고, MQTT 브릿지가 WebSocket으로 변환합니다.**

---

## 현재 시스템 구조

### 통신 흐름

```
FE/BE (React, Java)
    ↓ MQTT
    /pub/robot/control
    /sub/robot/status
    ↓
MQTT 브릿지 (scripts/mqtt_pi_bridge.py)
    ↓ 변환
    WebSocket /ws/teleop
    HTTP POST /control/mode
    ↓
Pi Gateway (FastAPI + WebSocket)
    ↓ UART
    STM32
```

---

## 각 컴포넌트의 역할

### 1. FE/BE (프론트엔드/백엔드)
- **사용하는 프로토콜**: **MQTT**
- **토픽**:
  - 발행: `/pub/robot/control` (제어 명령)
  - 구독: `/sub/robot/status` (로봇 상태)
- **역할**: 사용자 입력을 MQTT로 전송

### 2. MQTT 브릿지 (`scripts/mqtt_pi_bridge.py`)
- **역할**: MQTT ↔ Pi Gateway 변환
- **동작**:
  - MQTT `/pub/robot/control` 구독
  - Pi Gateway WebSocket `/ws/teleop`으로 변환해서 전송
  - Pi Gateway HTTP `/health`, `/telemetry/latest` 수집
  - MQTT `/sub/robot/status`로 발행

### 3. Pi Gateway
- **제공하는 인터페이스**: **WebSocket + HTTP**
- **엔드포인트**:
  - WebSocket: `/ws/teleop` (제어 명령)
  - HTTP: `/control/mode`, `/health`, `/telemetry/latest`
- **역할**: WebSocket/HTTP로 명령 받아서 UART로 STM32에 전송

---

## 답변: 어떤 걸 써야 하나요?

### Pi Gateway 개발자 입장 (당신)

**→ WebSocket을 제공하면 됩니다!**

- ✅ **WebSocket `/ws/teleop`**: 제어 명령 수신
- ✅ **HTTP API**: 모드 전환, 상태 조회
- ❌ **MQTT 직접 지원 불필요**: MQTT 브릿지가 변환해줌

**이유:**
- FE/BE는 MQTT를 사용
- MQTT 브릿지가 MQTT → WebSocket 변환
- Pi Gateway는 WebSocket만 제공하면 됨

---

### FE/BE 개발자 입장

**→ MQTT를 사용합니다!**

- ✅ **MQTT `/pub/robot/control`**: 제어 명령 발행
- ✅ **MQTT `/sub/robot/status`**: 로봇 상태 구독
- ❌ **WebSocket 직접 연결 불필요**: MQTT 브릿지가 처리

---

## 실제 사용 시나리오

### 시나리오 1: FE/BE에서 로봇 제어

```
1. FE (React) → MQTT `/pub/robot/control` 발행
2. MQTT 브릿지가 구독 → WebSocket `/ws/teleop`으로 변환
3. Pi Gateway가 WebSocket으로 받음 → UART로 STM32에 전송
```

**→ FE/BE는 MQTT만 사용하면 됨!**

---

### 시나리오 2: 직접 WebSocket으로 제어 (테스트용)

```
1. 직접 WebSocket 클라이언트 → `/ws/teleop` 연결
2. Pi Gateway가 WebSocket으로 받음 → UART로 STM32에 전송
```

**→ MQTT 브릿지 없이도 가능!**

---

## 결론

### Pi Gateway 개발자 (당신)가 해야 할 일

1. ✅ **WebSocket `/ws/teleop` 제공** (이미 구현됨)
2. ✅ **HTTP API 제공** (이미 구현됨)
3. ❌ **MQTT 직접 지원 불필요** (MQTT 브릿지가 처리)

### FE/BE 개발자가 해야 할 일

1. ✅ **MQTT 사용** (이미 구현됨)
2. ✅ **MQTT 브릿지 실행** (별도 스크립트)
3. ❌ **WebSocket 직접 연결 불필요**

---

## MQTT 브릿지 실행 방법

**MQTT 브릿지는 별도로 실행해야 합니다:**

```bash
# Pi Gateway와 MQTT 브릿지 모두 실행
python3 src/main.py              # Pi Gateway (WebSocket 제공)
python3 scripts/mqtt_pi_bridge.py  # MQTT 브릿지 (변환)
```

**또는:**
```bash
./scripts/run_gateway.sh         # Pi Gateway
./scripts/run_mqtt_bridge.sh     # MQTT 브릿지
```

---

## 요약

| 컴포넌트 | 사용하는 프로토콜 | 역할 |
|---------|------------------|------|
| **FE/BE** | MQTT | 제어 명령 발행, 상태 구독 |
| **MQTT 브릿지** | MQTT + WebSocket | 프로토콜 변환 |
| **Pi Gateway** | **WebSocket + HTTP** | **제어 명령 수신, UART 전송** |

**→ Pi Gateway는 WebSocket을 제공하면 됩니다!** ✅

MQTT는 FE/BE가 사용하고, MQTT 브릿지가 변환해줍니다.
