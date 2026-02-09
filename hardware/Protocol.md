# 🤖 PetNer - Low Level Control Firmware

## 📝 Overview

**PetNer** 로봇의 하위 제어 시스템(Low-Level Control System)입니다.
PC 및 RPi(ROS2)로부터 수신한 단일 문자 명령(Char Command)을 해석하여 **메카넘 휠의 벡터 주행**과 **주사기(Syringe) 및 로봇팔 서보**를 제어합니다.

> **System:** STM32F446RE (Nucleo-64)
> **Actuator:** 4x DC Motors (Mecanum), 2x Servos
> **Communication:** Dual UART (PC Debug / RPi Command)

---

## 📡 Communication Protocol

소스코드(`main.c`)에 구현된 실제 통신 프로토콜입니다.

### 1. Control Command (Input)

PC(`USART2`) 또는 RPi(`UART4`)에서 단일 문자를 전송하여 제어합니다.

| Key | Function | Detail |
| --- | --- | --- |
| **`w` / `x**` | 전/후진 속도 | Linear Velocity X (±400 step) |
| **`a` / `d**` | 좌/우 평행이동 | Linear Velocity Y (±400 step) |
| **`q` / `e**` | 제자리 회전 | Angular Velocity Z (±400 step) |
| **`s`** | **비상 정지** | 모든 속도 초기화 (Zero Vector) |
| **`k`** | **주사기 제어** | 각도 순차 변경 (5°  40°  ...  145°  5°) |
| **`i`** | 서보1 동작 | CW 회전 (10초 후 자동 정지) |
| **`u` / `o**` | 서보1 수동 | CCW / CW 수동 설정 |
| **`p`** | PWM 모드 | (PC Only) 목표 속도값 직접 입력 모드 진입 |

### 2. Feedback Data (Output)

로봇이 현재 수행 중인 **모터 출력값(PWM)**과 **주사기 상태**를 0.2초 간격으로 리턴합니다.

* **Format:** `KEY:[LastCommand] | FL:[PWM] FR:[PWM] | Syringe:[Angle] deg`
* **Example:** `KEY:w | FL:400 FR:400 | Syringe:5 deg`
* `FL/FR`: 계산된 모터 출력 PWM (Range: -999 ~ +999)
* `Syringe`: 현재 주사기 서보 각도 (Range: 5 ~ 145)



---

## ⚙️ Hardware Specification

펌웨어 코드(`MX_TIMx_Init`)에 정의된 하드웨어 매핑입니다.

| Component | Port / Pin | Timer | Channel | Note |
| --- | --- | --- | --- | --- |
| **Motor FL** | PC6 | TIM8 | CH1 | Front Left |
| **Motor FR** | PC7 | TIM8 | CH2 | Front Right |
| **Motor RL** | PC8 | TIM8 | CH3 | Rear Left |
| **Motor RR** | PC9 | TIM8 | CH4 | Rear Right |
| **Syringe Servo** | PB14 | TIM12 | CH1 | 500~2500us Pulse |
| **Arm Servo** | PB15 | TIM12 | CH2 | 360 Rotation |
| **PC UART** | PA2 / PA3 | USART2 | - | 115200bps (Debug) |
| **RPi UART** | PC10 / PC11 | UART4 | - | 115200bps (ROS2) |

---

## 🚀 Key Logic Description

### 1. Mecanum Kinematics Implementation

입력받은 3가지 속도 벡터()를 합성하여 4개 모터의 PWM 출력을 계산합니다.

```c
// main.c line 192 (Kinematics Formula)
int cal_fl = current_vx - current_vy - current_omega;
int cal_fr = current_vx + current_vy + current_omega;
int cal_rl = current_vx + current_vy - current_omega;
int cal_rr = current_vx - current_vy + current_omega;

```

* 계산된 값은 `clamp()` 함수를 통해 PWM 한계값(±999) 내로 안전하게 제한됩니다.

### 2. Syringe Control (State Machine)

`k` 키 입력 시 주사기 각도를 35도씩 증가시키며, 최대각 도달 시 초기화합니다.

* **Logic:** `Angle += 35` (Loop: 5  145  5)
* **Servo Map:** 각도를 500~2500us 펄스폭으로 변환 (`map()` 함수 사용)

### 3. Dual UART Handling (Interrupt)

* **UART4 (RPi):** `HAL_UART_RxCpltCallback`을 통해 ROS2 상위 제어기의 명령을 실시간 수신.
* **USART2 (PC):** 디버깅 및 수동 제어를 위한 터미널 인터페이스 제공. `p` 입력 시 PWM 직접 제어 모드로 전환되는 기능 포함.

---

## 🛠 Development Environment

* **IDE:** STM32CubeIDE
* **MCU:** STM32F446RETx
* **Language:** C (HAL Library)
* **Clock:** 180MHz (Max Performance)
