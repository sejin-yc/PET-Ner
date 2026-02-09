# STM32 모터 완료 감지 방법

STM32가 모터를 제어할 때 작업 완료를 어떻게 감지하는지 설명합니다.

---

## 서보모터 (급식, 츄르)

### 서보모터의 특징

**서보모터는 위치 피드백이 있습니다!**

```
STM32 → 서보모터: "90도로 가라" (PWM 신호)
서보모터: 현재 각도 읽기 가능 (위치 피드백)
STM32: 현재 각도 = 목표 각도 → 완료!
```

### STM32 코드 예시

```c
// 급식 작업 시작
void feed_start(uint8_t level) {
    // level에 따라 목표 각도 설정
    uint16_t target_angle;
    switch(level) {
        case 1: target_angle = 30; break;   // 작은 양
        case 2: target_angle = 60; break;   // 중간 양
        case 3: target_angle = 90; break;   // 큰 양
    }
    
    // 서보모터 목표 위치 설정
    servo_set_target_angle(target_angle);
    feed_state = FEED_IN_PROGRESS;
}

// 주기적으로 호출 (예: 10ms마다)
void feed_check() {
    if (feed_state == FEED_IN_PROGRESS) {
        // 서보모터 현재 각도 읽기 (위치 피드백)
        uint16_t current_angle = servo_get_current_angle();
        uint16_t target_angle = servo_get_target_angle();
        
        // 목표 위치 도달 확인 (오차 범위 ±2도)
        if (abs(current_angle - target_angle) <= 2) {
            // 완료!
            feed_state = FEED_COMPLETE;
            
            // Pi에게 완료 알림
            uint8_t payload[3] = {0x01, 0x01, 0x00};  // JOB_COMPLETE, 급식
            uart_send_frame(0x84, payload, 3);
        }
    }
}
```

**핵심:**
- 서보모터는 **현재 각도를 읽을 수 있음** (위치 피드백)
- 목표 각도와 현재 각도 비교 → 도달하면 완료

---

## 서보모터 위치 피드백 원리

### 방법 1: 내장 포텐셔미터 (가장 일반적)

```
서보모터 내부 구조:
- 모터 → 기어박스 → 출력축
- 출력축에 포텐셔미터 연결
- 포텐셔미터 전압 → 각도 변환

STM32:
- ADC로 포텐셔미터 전압 읽기
- 전압 → 각도 변환 (예: 0V = 0도, 3.3V = 180도)
- 현재 각도 = (ADC값 / 4095) * 180
```

### 방법 2: 외부 엔코더

```
서보모터 출력축에 엔코더 장착
STM32: 엔코더 펄스 카운트 → 각도 계산
```

### 방법 3: 타이머 기반 (위치 피드백 없을 때)

```
서보모터 위치 피드백이 없으면:
- 목표 각도 설정
- 일정 시간 대기 (예: 500ms)
- 완료 가정

단점: 정확하지 않음 (부하에 따라 속도 다름)
```

---

## DC 모터 (바퀴)

**현재 프로젝트에서는:**
- DC 모터는 바퀴 구동용
- 엔코더로 위치 추적 (이미 구현됨: `ID_ENCODER`)
- 완료 감지는 "목표 위치 도달"로 판단

**예시 (순찰 중 특정 위치 도착):**
```c
// 목표 위치 설정
float target_x = 1.5;  // 목표 x 좌표
float target_y = 2.0;  // 목표 y 좌표

// 엔코더로 현재 위치 계산
float current_x = calculate_x_from_encoder();
float current_y = calculate_y_from_encoder();

// 목표 위치 도달 확인
if (abs(current_x - target_x) < 0.1 && abs(current_y - target_y) < 0.1) {
    // 목표 도착!
    send_status(0x01, 0x05, 0x00);  // 순찰 경로 완료 (예시)
}
```

---

## 스텝모터 (로봇팔 관절, 현재 미사용)

**스텝모터는:**
- 스텝 수로 위치 제어
- 스텝 카운트로 완료 감지 가능

```c
// 목표 스텝 수 설정
uint32_t target_steps = 1000;

// 현재 스텝 수 확인
uint32_t current_steps = step_motor_get_count();

if (current_steps >= target_steps) {
    // 완료!
}
```

---

## 요약: 모터별 완료 감지 방법

| 모터 타입 | 완료 감지 방법 | 현재 사용 |
|----------|----------------|----------|
| **서보모터** | 위치 피드백 (포텐셔미터/엔코더) | 급식, 츄르 |
| **DC 모터** | 엔코더로 위치 추적 | 바퀴 구동 |
| **스텝모터** | 스텝 카운트 | 로봇팔 (젯슨 제어) |

---

## STM32 담당자에게 전달할 내용

**서보모터 완료 감지 구현 예시:**

```c
// 서보모터 제어 함수
void servo_set_target_angle(uint16_t angle) {
    // PWM으로 목표 각도 설정
    // (서보모터 라이브러리 사용)
}

uint16_t servo_get_current_angle(void) {
    // 포텐셔미터 전압 읽기 (ADC)
    uint16_t adc_value = HAL_ADC_Read(&hadc1);
    
    // ADC 값 → 각도 변환
    // 예: 0~4095 → 0~180도
    uint16_t angle = (adc_value * 180) / 4095;
    return angle;
}

// 급식 완료 체크
void feed_check(void) {
    if (feed_state == FEED_IN_PROGRESS) {
        uint16_t current = servo_get_current_angle();
        uint16_t target = servo_get_target_angle();
        
        if (abs(current - target) <= 2) {
            // 완료!
            send_status(0x01, 0x01, 0x00);  // JOB_COMPLETE, 급식
            feed_state = FEED_IDLE;
        }
    }
}
```

**핵심:**
- 서보모터는 **위치 피드백**이 있어서 현재 각도를 읽을 수 있음
- 목표 각도와 현재 각도 비교 → 도달하면 완료
- "모터가 안 움직인다"가 아니라 "목표 위치에 도달했다"로 판단
