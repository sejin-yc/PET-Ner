# ROS2 폴더와 동시 실행 가이드

## 개요

ROS2 폴더의 브릿지와 Pi Gateway를 동시에 실행할 때의 동작 및 충돌 방지 방법을 설명합니다.

---

## 현재 구조 분석

### ROS2 폴더의 구성

1. **`twist_mux.yaml`** (설정 파일)
   - 입력 토픽:
     - `/cmd_vel_nav` (priority 10) - 패트롤 명령
     - `/cmd_vel_joy` (priority 50) - 조이스틱 명령
     - `/cmd_vel_aruco` (priority 80) - 아루코 마커 명령
   - 출력 토픽: `/cmd_vel` (추정)

2. **`twist_to_stm_uart_bridge.py`**
   - 구독: `/cmd_vel`
   - 동작: UART로 전송

3. **`primitive_mission_manager_fixed_pwm.py`** (패트롤 노드)
   - 발행: `/cmd_vel_nav`

---

## 충돌 시나리오

### ⚠️ 문제 상황

**시나리오 1: twist_mux 실행 시**
```
ROS2 폴더:
  twist_mux → /cmd_vel 발행
  twist_to_stm_uart_bridge → /cmd_vel 구독 → UART 전송

Pi Gateway:
  CmdVelMux → /cmd_vel 발행

결과: 두 개가 동시에 /cmd_vel 발행 → 충돌 가능!
```

**시나리오 2: twist_mux 미실행 시**
```
ROS2 폴더:
  twist_to_stm_uart_bridge → /cmd_vel 구독 → UART 전송

Pi Gateway:
  CmdVelMux → /cmd_vel 발행

결과: 정상 동작 (Pi Gateway가 발행, ROS2 브릿지가 구독)
```

---

## 해결 방안

### 방안 1: Pi Gateway가 twist_mux 입력 토픽으로 발행 (권장) ✅

**개념**:
- Pi Gateway는 `/cmd_vel`을 발행하지 않음
- 대신 twist_mux의 입력 토픽으로 발행
- twist_mux가 통합하여 `/cmd_vel` 발행

**구조**:
```
웹 대시보드
    ↓
Pi Gateway
    └─ /cmd_vel_joy 발행 (twist_mux 입력)
        ↓
ROS2 폴더
    ├─ twist_mux
    │   ├─ /cmd_vel_nav 구독 (패트롤)
    │   ├─ /cmd_vel_joy 구독 (Pi Gateway)
    │   └─ /cmd_vel 발행 (통합)
    └─ twist_to_stm_uart_bridge
        └─ /cmd_vel 구독 → UART 전송
```

**장점**:
- ✅ twist_mux와 통합 가능
- ✅ 우선순위 관리 (twist_mux가 처리)
- ✅ 충돌 없음

**단점**:
- ⚠️ twist_mux가 실행되어야 함

---

### 방안 2: Pi Gateway가 `/cmd_vel` 발행, twist_mux 미사용

**개념**:
- ROS2 폴더에서 twist_mux를 실행하지 않음
- Pi Gateway의 CmdVelMux가 `/cmd_vel` 발행
- ROS2 브릿지가 `/cmd_vel` 구독

**구조**:
```
웹 대시보드
    ↓
Pi Gateway
    └─ CmdVelMux
        ├─ /cmd_vel_teleop 구독 (웹)
        ├─ /cmd_vel_nav 구독 (패트롤)
        └─ /cmd_vel 발행 (통합)
            ↓
ROS2 폴더
    └─ twist_to_stm_uart_bridge
        └─ /cmd_vel 구독 → UART 전송
```

**장점**:
- ✅ Pi Gateway가 모든 통합 담당
- ✅ twist_mux 불필요

**단점**:
- ⚠️ ROS2 폴더의 twist_mux 설정을 사용하지 않음

---

### 방안 3: Pi Gateway가 다른 토픽명 사용

**개념**:
- Pi Gateway는 `/cmd_vel_gateway` 발행
- ROS2 폴더의 twist_mux가 `/cmd_vel_gateway`를 입력으로 추가
- twist_mux가 `/cmd_vel` 발행

**구조**:
```
웹 대시보드
    ↓
Pi Gateway
    └─ /cmd_vel_gateway 발행
        ↓
ROS2 폴더
    ├─ twist_mux
    │   ├─ /cmd_vel_nav 구독
    │   ├─ /cmd_vel_gateway 구독 (Pi Gateway)
    │   └─ /cmd_vel 발행
    └─ twist_to_stm_uart_bridge
        └─ /cmd_vel 구독 → UART 전송
```

**장점**:
- ✅ 명확한 역할 분리
- ✅ 충돌 없음

**단점**:
- ⚠️ twist_mux.yaml 수정 필요

---

## 권장 방안: 방안 1 (twist_mux 입력 토픽 사용)

### 변경 사항

**Pi Gateway CmdVelMux 변경**:
```python
# 변경 전
self.pub_out = self.create_publisher(Twist, "/cmd_vel", 10)

# 변경 후
self.pub_out = self.create_publisher(Twist, "/cmd_vel_joy", 10)  # twist_mux 입력
```

**twist_mux.yaml 확인**:
- `/cmd_vel_joy` 토픽이 이미 설정되어 있음 (priority 50)
- Pi Gateway가 `/cmd_vel_joy`로 발행하면 자동으로 통합됨

---

## 실행 시나리오별 동작

### 시나리오 A: ROS2 폴더만 실행 (시연 담당자)

```
ROS2 폴더:
  ├─ primitive_mission_manager → /cmd_vel_nav 발행
  ├─ twist_mux → /cmd_vel_nav 구독 → /cmd_vel 발행
  └─ twist_to_stm_uart_bridge → /cmd_vel 구독 → UART 전송

결과: 패트롤 정상 동작 ✅
```

### 시나리오 B: Pi Gateway만 실행

```
Pi Gateway:
  └─ CmdVelMux → /cmd_vel 발행

ROS2 폴더:
  └─ twist_to_stm_uart_bridge → /cmd_vel 구독 → UART 전송

결과: 웹 대시보드 정상 동작 ✅
```

### 시나리오 C: 둘 다 실행 (방안 1 적용 시)

```
Pi Gateway:
  └─ CmdVelMux → /cmd_vel_joy 발행

ROS2 폴더:
  ├─ primitive_mission_manager → /cmd_vel_nav 발행
  ├─ twist_mux
  │   ├─ /cmd_vel_nav 구독 (패트롤, priority 10)
  │   ├─ /cmd_vel_joy 구독 (Pi Gateway, priority 50)
  │   └─ /cmd_vel 발행 (통합, 우선순위 적용)
  └─ twist_to_stm_uart_bridge → /cmd_vel 구독 → UART 전송

결과: 
- 패트롤 정상 동작 ✅
- 웹 대시보드 정상 동작 ✅
- 우선순위: 아루코(80) > 웹(50) > 패트롤(10)
```

---

## 우선순위 설명

**twist_mux.yaml 우선순위**:
- `aruco_marker`: priority 80 (최우선)
- `manual_drive` (`/cmd_vel_joy`): priority 50
- `navigation` (`/cmd_vel_nav`): priority 10 (최하위)

**의미**:
- 아루코 마커 제어 중: 다른 명령 무시
- 웹 대시보드 수동 조작: 패트롤 명령 무시
- 패트롤: 다른 명령이 없을 때만 동작

---

## 결론

### ✅ 권장: 방안 1 (twist_mux 입력 토픽 사용)

**이유**:
1. ROS2 폴더의 기존 구조 활용
2. 우선순위 관리 자동화
3. 충돌 없음
4. 시연 담당자와 동시 실행 가능

**변경 필요**:
- Pi Gateway CmdVelMux: `/cmd_vel` → `/cmd_vel_joy` 발행

**실행 방법**:
- ROS2 폴더: twist_mux + twist_to_stm_uart_bridge 실행
- Pi Gateway: CmdVelMux가 `/cmd_vel_joy` 발행

---

## 작성일

2026-01-27
