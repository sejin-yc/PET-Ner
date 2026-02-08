# gateway_sj.cpp 분석

## 개요

ROS2 폴더의 `gateway_sj.cpp` 파일을 분석합니다.

---

## 파일 분석

### 파일명
- `gateway_sj.cpp` (실제 파일명)
- 주석: `serial_bridge_cmd_vel_out.cpp`

### 역할
**UART 브릿지** (수동조작 노드 아님)

### 동작
1. **구독**: `/cmd_vel_out` 토픽 (또는 파라미터로 지정된 토픽)
2. **변환**: `Twist` 메시지 → 1바이트 문자 (w/x/a/d/q/e/s)
3. **전송**: UART로 STM32에 전송

### 명령 매핑
```cpp
w: 전진 (vx > 0)
x: 후진 (vx < 0)
a: 좌측 횡이동 (vy > 0)
d: 우측 횡이동 (vy < 0)
q: 좌회전 (wz > 0)
e: 우회전 (wz < 0)
s: 정지 (모든 값이 0에 가까움)
```

### 특징
- **우선순위**: 가장 큰 축만 선택 (안전)
- **Deadband**: 선형 0.08, 각속도 0.08
- **Watchdog**: 주기적으로 마지막 명령 재전송 (STM 타임아웃 방지)

---

## 결론

### ❌ 수동조작 노드 아님

`gateway_sj.cpp`는:
- 수동조작 입력을 받지 않음
- `/cmd_vel_out` 토픽을 구독하여 UART로 전송하는 브릿지
- `twist_to_stm_uart_bridge.py`와 유사한 역할 (C++ 버전)

### ✅ 실제 역할

```
다른 노드 → /cmd_vel_out 발행
    ↓
gateway_sj.cpp (구독)
    ↓
UART → STM32
```

---

## 수동조작 노드 찾기

### 가능성

1. **다른 파일**: ROS2 폴더의 다른 위치에 있을 수 있음
2. **다른 패키지**: 별도의 ROS2 패키지로 존재할 수 있음
3. **조이스틱 패키지**: 표준 ROS2 조이스틱 패키지 사용 가능
   - `joy` 패키지
   - `teleop_twist_keyboard` 패키지

### 확인 방법

```bash
# ROS2 토픽 확인
ros2 topic list | grep cmd_vel

# /cmd_vel_joy 발행자 확인
ros2 topic info /cmd_vel_joy

# 실행 중인 노드 확인
ros2 node list
```

---

## Pi Gateway와의 관계

### 현재 구조

```
Pi Gateway
    └─ /cmd_vel_joy 발행 (웹 대시보드 수동조작)
        ↓
twist_mux
    └─ /cmd_vel 발행
        ↓
twist_to_stm_uart_bridge.py
    └─ UART 전송
```

### gateway_sj.cpp 사용 시

```
다른 노드
    └─ /cmd_vel_out 발행
        ↓
gateway_sj.cpp
    └─ UART 전송
```

**주의**: `gateway_sj.cpp`는 `/cmd_vel_out`을 구독하므로, Pi Gateway와는 다른 경로입니다.

---

## 작성일

2026-01-27
