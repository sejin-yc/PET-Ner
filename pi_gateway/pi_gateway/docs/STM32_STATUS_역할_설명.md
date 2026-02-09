# STM32 STATUS 메시지 역할 설명

STM32의 STATUS 메시지가 무엇을 하는지, 언제 보내는지 설명합니다.

---

## STATUS 메시지의 역할

**STATUS = STM32가 Pi에게 "이런 일이 일어났어!"라고 알리는 메시지**

STM32는 하드웨어를 직접 제어하므로, 작업 완료/실패/에러를 가장 먼저 알 수 있습니다.  
이 정보를 Pi에게 전달하는 것이 STATUS 메시지입니다.

---

## STM32가 STATUS를 보내는 시점

### 1. 작업 완료 시 (JOB_COMPLETE)

**STM32 코드 예시 (급식):**
```c
// 급식 작업 시작
void feed_start(uint8_t level) {
    // 서보모터 목표 각도 설정
    servo_set_target_angle(level_to_angle(level));
    feed_state = FEED_IN_PROGRESS;
}

// 서보모터 위치 확인 (주기적으로 호출)
void feed_check() {
    if (feed_state == FEED_IN_PROGRESS) {
        // 서보모터 현재 각도 읽기
        uint16_t current_angle = servo_get_current_angle();
        uint16_t target_angle = servo_get_target_angle();
        
        // 목표 위치 도달 확인 (오차 범위 내)
        if (abs(current_angle - target_angle) < 2) {
            // 완료!
            feed_state = FEED_COMPLETE;
            
            // Pi에게 완료 알림
            uint8_t status_payload[3] = {0x01, 0x01, 0x00};  // JOB_COMPLETE, 급식, flags=0
            uart_send_frame(0x84, status_payload, 3);
        }
    }
}
```

**핵심:** STM32가 작업 완료를 감지하면 **명시적으로 STATUS를 보냅니다**.

---

### 2. 작업 실패 시 (JOB_FAILED)

**STM32 코드 예시 (급식 실패):**
```c
void feed_check() {
    if (feed_state == FEED_IN_PROGRESS) {
        // 서보모터 위치 확인
        uint16_t current_angle = servo_get_current_angle();
        uint16_t target_angle = servo_get_target_angle();
        
        // 타임아웃 체크 (5초 이상 목표 도달 못하면 실패)
        if (feed_timeout > 5000) {
            feed_state = FEED_FAILED;
            
            // Pi에게 실패 알림
            uint8_t status_payload[3] = {0x02, 0x01, 0x00};  // JOB_FAILED, 급식, flags=0
            uart_send_frame(0x84, status_payload, 3);
        }
    }
}
```

---

### 3. 에러 발생 시 (ERROR)

**STM32 코드 예시 (모터 오류):**
```c
void motor_check() {
    // 모터 전류 확인
    uint16_t motor_current = adc_read_motor_current();
    
    if (motor_current > MOTOR_MAX_CURRENT) {
        // 모터 오류 감지!
        motor_error = true;
        
        // Pi에게 에러 알림
        uint8_t status_payload[3] = {0x03, 0x01, 0x00};  // ERROR, 모터오류, flags=0
        uart_send_frame(0x84, status_payload, 3);
    }
}
```

---

### 4. 상태 변경 시 (STATE)

**STM32 코드 예시 (바퀴 잠금):**
```c
void arm_start(uint8_t action_id) {
    if (action_id == 1) {
        // 변 치우기 시작 → 바퀴 잠금
        wheels_locked = true;
        arm_active = true;
        
        // Pi에게 상태 변경 알림
        uint8_t status_payload[3] = {0x04, 0x00, 0x03};  // STATE, flags=ARM_ACTIVE|WHEELS_LOCKED
        uart_send_frame(0x84, status_payload, 3);
    } else if (action_id == 0) {
        // 변 치우기 완료 → 바퀴 해제
        wheels_locked = false;
        arm_active = false;
        
        // Pi에게 상태 변경 알림
        uint8_t status_payload[3] = {0x04, 0x00, 0x00};  // STATE, flags=0 (해제)
        uart_send_frame(0x84, status_payload, 3);
    }
}
```

---

## STM32가 완료를 감지하는 방법

### 급식/츄르 (STM32가 직접 제어)

**서보모터 위치 피드백:**
```c
// 서보모터는 위치 피드백이 있어서 현재 각도를 읽을 수 있음
uint16_t current_angle = servo_get_current_angle();  // 현재 각도
uint16_t target_angle = servo_get_target_angle();   // 목표 각도

if (abs(current_angle - target_angle) < 2) {
    // 목표 위치 도달 → 완료!
    send_status_complete(JOB_FEED_COMPLETE);
}
```

**타이머 기반 (대안):**
```c
// 서보모터 위치 피드백이 없으면 타이머 사용
void feed_start(uint8_t level) {
    servo_set_target_angle(level_to_angle(level));
    feed_timer = 0;
}

void feed_check() {
    feed_timer++;
    if (feed_timer > FEED_DURATION_MS) {
        // 시간 경과 → 완료 가정
        send_status_complete(JOB_FEED_COMPLETE);
    }
}
```

---

### 변 치우기/급수 (젯슨이 제어)

**젯슨에서 완료 신호 받기:**
```c
// 방법 1: 젯슨이 직접 STM32에 신호 (GPIO 또는 UART)
void on_jetson_complete_signal() {
    // 젯슨이 완료 신호 보냄
    send_status_complete(JOB_LITTER_CLEAN_COMPLETE);
}

// 방법 2: Pi를 경유 (현재 구조)
// Pi가 arm/start(action_id=0) 받으면 STM32에 완료 신호 전송
// STM32가 받아서 STATUS로 확인 응답
```

**핵심:** 젯슨이 제어하는 작업은 젯슨이 완료를 판단하고 STM32에 알려야 합니다.

---

## Gateway가 STATUS를 받으면 하는 일

### 1. 작업 이벤트 업데이트

```python
# main.py의 on_frame()
if status_type == 0x01:  # JOB_COMPLETE
    job_type = obj.get("job_type")  # "feed", "litter_clean" 등
    JOB_EVENTS.update_job_by_type(job_type, "success")
```

**결과:**
- 웹 API `/robot/jobs`에서 완료 상태 확인 가능
- Backend에 작업 완료 로그 자동 전송
- Frontend UI 업데이트

### 2. ROS 토픽 발행

```python
# ros_telemetry_bridge.py
if t == "status":
    self.pub_status.publish(msg)  # telemetry/status 토픽에 발행
```

**결과:**
- 다른 ROS 노드에서 구독 가능
- 작업 완료 시 다음 작업 자동 시작 가능

### 3. 에러 로깅

```python
if status_type == 0x03:  # ERROR
    print(f"[STATUS] STM32 에러 발생: {error_type}")
```

**결과:**
- 에러 로그 출력
- 필요 시 자동 E-STOP 가능

---

## 정리: STATUS의 역할

| 역할 | 설명 |
|------|------|
| **작업 완료 알림** | STM32가 작업 완료 감지 → Pi에 알림 |
| **작업 실패 알림** | STM32가 작업 실패 감지 → Pi에 알림 |
| **에러 알림** | STM32가 에러 감지 → Pi에 알림 |
| **상태 변경 알림** | 바퀴 잠금/해제 등 상태 변경 → Pi에 알림 |

**핵심:**
- STATUS는 **STM32 코드에서 명시적으로 보내는 메시지**
- STM32가 작업 완료/실패/에러를 감지하는 로직은 **STM32 코드에 구현**되어야 함
- Gateway는 STATUS를 받아서 **작업 이벤트 업데이트, ROS 토픽 발행, 로깅**만 함

---

## STM32 담당자에게 전달할 내용

**STM32 코드에 추가해야 할 것:**

1. **급식 완료 감지:**
   ```c
   // 서보모터 위치 피드백으로 완료 감지
   if (servo_reached_target()) {
       send_status(0x01, 0x01, 0x00);  // JOB_COMPLETE, 급식
   }
   ```

2. **변 치우기 완료 (젯슨 신호 받기):**
   ```c
   // 젯슨에서 완료 신호 받으면
   void on_litter_clean_complete() {
       send_status(0x01, 0x02, 0x00);  // JOB_COMPLETE, 변치우기
   }
   ```

3. **에러 감지:**
   ```c
   // 모터/센서 오류 감지 시
   if (motor_error) {
       send_status(0x03, 0x01, 0x00);  // ERROR, 모터오류
   }
   ```

**STATUS 전송 함수 예시:**
```c
void send_status(uint8_t status_type, uint8_t status_code, uint8_t flags) {
    uint8_t payload[3] = {status_type, status_code, flags};
    uart_send_frame(0x84, payload, 3);
}
```
