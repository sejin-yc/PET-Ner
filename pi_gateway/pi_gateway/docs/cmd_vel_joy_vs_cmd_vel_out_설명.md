# /cmd_vel_joy vs /cmd_vel_out 설명

## 개요

Pi Gateway가 발행하는 두 토픽의 차이와 역할을 설명합니다.

---

## 두 토픽 비교

### `/cmd_vel_joy`
- **역할**: ROS2 폴더의 `twist_mux` 입력
- **경로**: `twist_mux` → `/cmd_vel` → `twist_to_stm_uart_bridge.py` → UART
- **특징**: 우선순위 통합 (아루코 > 웹 > 패트롤)

### `/cmd_vel_out`
- **역할**: ROS2 폴더의 `gateway_sj.cpp` 입력
- **경로**: `gateway_sj.cpp` → UART (직접)
- **특징**: 직접 UART 전송 (w/x/a/d/q/e/s 변환)

---

## 현재 구조

```
웹 대시보드 (WASD 입력)
    ↓
Pi Gateway CmdVelMux
    ├─ /cmd_vel_joy 발행
    │   ↓
    │   twist_mux (우선순위 통합)
    │   ├─ /cmd_vel_nav (패트롤, priority 10)
    │   ├─ /cmd_vel_joy (웹, priority 50)
    │   ├─ /cmd_vel_aruco (아루코, priority 80)
    │   └─ /cmd_vel 발행 (통합)
    │       ↓
    │   twist_to_stm_uart_bridge.py
    │   └─ UART 전송
    │
    └─ /cmd_vel_out 발행
        ↓
        gateway_sj.cpp
        └─ UART 전송 (w/x/a/d/q/e/s)
```

---

## 웹 대시보드에서 WASD 입력 시

### 동작 흐름

1. **웹 대시보드에서 WASD 입력**
   - WebSocket으로 Pi Gateway에 전송
   - `/cmd_vel_teleop` 토픽으로 변환

2. **Pi Gateway CmdVelMux**
   - `/cmd_vel_teleop` 구독
   - 통합하여 **두 개의 토픽 발행**:
     - `/cmd_vel_joy` → twist_mux 경로
     - `/cmd_vel_out` → gateway_sj.cpp 경로

3. **두 경로 모두 동작**
   - **경로 1**: twist_mux → `/cmd_vel` → `twist_to_stm_uart_bridge.py` → UART
   - **경로 2**: `gateway_sj.cpp` → UART (w/x/a/d/q/e/s 변환)

---

## 문제점

### ⚠️ 중복 전송 가능성

**두 개의 UART 브릿지가 동시에 동작**:
- `twist_to_stm_uart_bridge.py`: `/cmd_vel` 구독 → UART 전송
- `gateway_sj.cpp`: `/cmd_vel_out` 구독 → UART 전송

**결과**: STM32에 두 개의 명령이 동시에 전송될 수 있음!

---

## 해결 방안

### 방안 1: 하나만 사용 (권장) ✅

**옵션 A: twist_mux 경로만 사용**
```
Pi Gateway
    └─ /cmd_vel_joy 발행만
        ↓
twist_mux → /cmd_vel → twist_to_stm_uart_bridge.py
```

**변경**: `/cmd_vel_out` 발행 제거

**옵션 B: gateway_sj.cpp 경로만 사용**
```
Pi Gateway
    └─ /cmd_vel_out 발행만
        ↓
gateway_sj.cpp
```

**변경**: `/cmd_vel_joy` 발행 제거, twist_mux 사용 안 함

### 방안 2: 둘 다 사용하되, 하나만 실행

**조건부 실행**:
- ROS2 폴더에서 `twist_mux` + `twist_to_stm_uart_bridge.py` 실행 시: `/cmd_vel_joy`만 발행
- ROS2 폴더에서 `gateway_sj.cpp`만 실행 시: `/cmd_vel_out`만 발행

---

## 권장 사항

### ✅ 방안 1-A: twist_mux 경로만 사용

**이유**:
1. 우선순위 통합 자동화
2. 아루코 마커, 패트롤과 통합 가능
3. 단일 UART 브릿지 사용

**변경**:
- Pi Gateway: `/cmd_vel_joy`만 발행
- `/cmd_vel_out` 발행 제거

---

## 요약

### 현재 상태
- **웹 대시보드 WASD 입력**: ✅ 동작함
- **두 경로 모두 발행**: ⚠️ 중복 전송 가능

### 권장 상태
- **웹 대시보드 WASD 입력**: ✅ 동작함
- **twist_mux 경로만 사용**: ✅ 단일 경로, 우선순위 통합

---

## 작성일

2026-01-27
