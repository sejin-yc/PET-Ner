# cmd_vel 토픽 구조 정리

Pi Gateway에서 사용하는 이동 명령 토픽들의 역할과 흐름을 정리합니다.

---

## 📡 토픽 흐름도

```
Nav2 (자율 주행)
  ↓ 발행: /cmd_vel
CmdVelMux (구독)
  ↓
  ↓ 선택 (mode에 따라)
  ↓
  ↓ 발행: cmd_vel_out
RosCmdVelBridge (구독)
  ↓ UART 전송
STM32 (모터 제어)

TeleopPublisher (수동 조종)
  ↓ 발행: cmd_vel_teleop
CmdVelMux (구독)
  ↓
```

---

## 🔍 각 토픽 설명

### 1. `/cmd_vel` (Nav2 → CmdVelMux)

**발행자**: Nav2  
**구독자**: `CmdVelMux`  
**용도**: 자율 주행 명령 (Nav2가 경로 계획 후 발행)

**특징**:
- ROS2 표준 토픽 이름
- Nav2가 자동으로 발행함
- `mode="auto"`일 때만 사용됨

---

### 2. `cmd_vel_teleop` (TeleopPublisher → CmdVelMux)

**발행자**: `TeleopPublisher` (main.py 내부 클래스)  
**구독자**: `CmdVelMux`  
**용도**: 수동 조종 명령 (웹 UI 버튼/조이스틱 입력)

**특징**:
- 웹 UI에서 버튼이나 조이스틱 입력 시 발행
- `mode="teleop"`일 때만 사용됨
- `TeleopPublisher`가 WebState를 읽어서 변환

---

### 3. `cmd_vel_out` (CmdVelMux → RosCmdVelBridge)

**발행자**: `CmdVelMux`  
**구독자**: `RosCmdVelBridge`  
**용도**: 최종 선택된 이동 명령 (Mux가 선택한 것)

**특징**:
- `CmdVelMux`가 `/cmd_vel`과 `cmd_vel_teleop` 중 하나를 선택해서 발행
- `mode="auto"` → `/cmd_vel` 사용
- `mode="teleop"` → `cmd_vel_teleop` 사용
- `estop=true` → `(0, 0, 0)` 발행 (정지)

---

## 🔄 CmdVelMux의 역할

`CmdVelMux`는 **Multiplexer (다중 선택기)** 역할을 합니다:

1. **두 입력 구독**:
   - `/cmd_vel` (Nav2 자율 주행)
   - `cmd_vel_teleop` (수동 조종)

2. **mode에 따라 선택**:
   - `mode="auto"`: `/cmd_vel` 사용 (Nav2 명령)
   - `mode="teleop"`: `cmd_vel_teleop` 사용 (수동 명령)

3. **최종 명령 발행**:
   - 선택한 명령을 `cmd_vel_out`으로 발행

---

## 📋 토픽 이름 비교표

| 토픽 이름 | 발행자 | 구독자 | 용도 | 모드 |
|---------|--------|--------|------|------|
| `/cmd_vel` | Nav2 | CmdVelMux | 자율 주행 명령 | auto |
| `cmd_vel_teleop` | TeleopPublisher | CmdVelMux | 수동 조종 명령 | teleop |
| `cmd_vel_out` | CmdVelMux | RosCmdVelBridge | 최종 선택된 명령 | auto/teleop |

---

## ⚠️ 주의사항

### `cmd_vel_auto`는 더 이상 사용 안 함

**이전 (옵션 1)**:
- Nav2가 `cmd_vel_auto` 발행 (비표준)
- `CmdVelMux`가 `cmd_vel_auto` 구독

**현재 (옵션 2)**:
- Nav2가 `/cmd_vel` 발행 (표준)
- `CmdVelMux`가 `/cmd_vel` 구독

**변경 이유**:
- Nav2 담당자에게 요청할 필요 없음 (표준 토픽 사용)
- 표준 ROS2 관례를 따름

---

## 💡 요약

1. **`/cmd_vel`**: Nav2가 발행하는 자율 주행 명령 (표준 토픽)
2. **`cmd_vel_teleop`**: 웹 UI 입력을 변환한 수동 조종 명령
3. **`cmd_vel_out`**: Mux가 선택한 최종 명령 (UART로 전송됨)

**핵심**: `CmdVelMux`가 두 입력 중 하나를 선택해서 `cmd_vel_out`으로 내보냅니다!
