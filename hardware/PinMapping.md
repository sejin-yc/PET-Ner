# 📍 Pin Configuration & Mapping

> **STM32F446RE (Nucleo-64)** 핀 할당 상세 내역입니다.
> 하드웨어 배선 및 펌웨어 디버깅 시 이 문서를 참조하십시오.

## 1. DC Motor Drive System (Mecanum Wheel)

메카넘 휠 구동을 위한 DC 모터 제어 핀입니다. (PWM 속도 제어 + GPIO 방향 제어)

| Motor Location | PWM Pin (Speed) | Timer Channel | DIR Pin (Direction) | GPIO Port |
| --- | --- | --- | --- | --- |
| **Front Left (FL)** | **PC6** | TIM8_CH1 | **PB0** | GPIO_Output |
| **Front Right (FR)** | **PC7** | TIM8_CH2 | **PB1** | GPIO_Output |
| **Rear Left (RL)** | **PC8** | TIM8_CH3 | **PB2** | GPIO_Output |
| **Rear Right (RR)** | **PC9** | TIM8_CH4 | **PB10** | GPIO_Output |

* **PWM Frequency:** 20kHz (Center-aligned recommended for H-Bridge)
* **Logic:** DIR High/Low for CW/CCW

---

## 2. Encoder Interface (Feedback)

모터 회전수 피드백을 위한 엔코더 입력 핀입니다. (Quadrature Encoder Mode)

| Encoder Location | Phase A Pin | Phase B Pin | Associated Timer |
| --- | --- | --- | --- |
| **FL Encoder** | **PA0** | **PA1** | TIM2 or TIM5 |
| **FR Encoder** | **PB6** | **PB7** | TIM4 |
| **RL Encoder** | **PA6** | **PA7** | TIM3 |
| **RR Encoder** | **PA8** | **PA9** | TIM1 |

---

## 3. Robot Arm & Actuators (Servo)

사료 공급기 및 주사기 제어를 위한 서보모터 PWM 핀입니다.

| Function | Pin Name | Timer Channel | Note |
| --- | --- | --- | --- |
| **Servo (180°)** | **PB14** | TIM12_CH1 | 주사기 제어용 |
| **Servo (360°)** | **PB15** | TIM12_CH2 | 사료 공급기 구동용 |

* **PWM Frequency:** 50Hz (Period: 20ms)

---

## 4. Communication & Sensors (IMU / UART)

상위 제어기(RPi/Jetson) 통신 및 IMU 센서 연결 핀입니다.

| Function | Interface | TX / SCL Pin | RX / SDA Pin | Description |
| --- | --- | --- | --- | --- |
| **Main Comm** | **UART4** | **PC10** | **PC11** | ROS2 통신 (to RPi/Jetson) |
| **Debug Console** | **USART2** | **PA2** | **PA3** | ST-Link Virtual Com Port (Log) |
| **IMU Sensor** | **I2C1** | **PB8** | **PB9** | BNO080 / MPU6050 연결 |

### 🧭 IMU Control Pins

I2C 통신 외에 IMU 모듈 제어를 위해 할당된 추가 GPIO입니다.

* **IMU_INT (Interrupt):** `PC13` (Active Low/High check required)
* **IMU_RST (Reset):** `PC14`

---

## 5. System & Debug

| Pin Name | Function | Description |
| --- | --- | --- |
| **PA13** | **SWDIO** | Serial Wire Debug Data (ST-Link) |
| **PA14** | **SWCLK** | Serial Wire Debug Clock (ST-Link) |
| **PH0/PH1** | **OSC_IN/OUT** | High Speed External Clock (HSE) |
| **NRST** | **Reset** | Hardware Reset Button |