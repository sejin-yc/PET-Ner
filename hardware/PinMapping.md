# 🔌 STM32G431RB Pin Mapping

## 1. Motor Control (Actuator)
현재 모터의 제어 신호는 만능기판의 기존 배선과 충돌을 피하기 위해 **점퍼선을 사용하여 모터 드라이버와 직결**되었습니다.

| Motor Position | Signal | STM32 Pin | Timer/Channel | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Front Left (FL)** | PWM | PA2 or PB14* | TIM15 CH1 | `htim15` 제어 |
| | DIR | **PB4** | GPIO Output | |
| **Front Right (FR)** | PWM | PA3 or PB15* | TIM15 CH2 | `htim15` 제어 |
| | DIR | **PB5** | GPIO Output | |
| **Rear Left (RL)** | PWM | PB8 | TIM16 CH1 | `htim16` 제어 |
| | DIR | **PB10** | GPIO Output | |
| **Rear Right (RR)** | PWM | PB9 | TIM17 CH1 | `htim17` 제어 |
| | DIR | **PC3** | GPIO Output | |

*(*Note: PWM 핀은 CubeMX 설정에 따르며, 코드상에서는 `htim15`, `htim16`, `htim17`의 채널을 통해 제어됨)*

## 2. Encoders (Sensor)
엔코더 카운팅을 위해 STM32의 타이머 엔코더 모드를 사용합니다.

| Encoder | STM32 Timer | Resolution | Status |
| :--- | :--- | :--- | :--- |
| **FL Encoder** | TIM1 | 16-bit | ⚠️ 하드웨어 신호 불안정 (가상값 대체) |
| **FR Encoder** | TIM3 | 16-bit | ⚠️ 하드웨어 신호 불안정 (가상값 대체) |
| **RL Encoder** | TIM2 | 16-bit | ✅ 정상 동작 (마스터 기준) |
| **RR Encoder** | TIM4 | 16-bit | ✅ 정상 동작 (마스터 기준) |

## 3. Communication
| Function | Pin | Peripheral | Use Case |
| :--- | :--- | :--- | :--- |
| **PC/RPi UART** | PA2 (TX), PA3 (RX) | USART2 | Debugging & Main Control |
| **Sub UART** | PA9 (TX), PA10 (RX) | USART1 | RPi Secondary (Optional) |

