# 📌 Pin Mapping & Wiring

최종 확정된 회로 설계를 기반으로 한 STM32 Nucleo-F401RE 핀 할당 정의서입니다.

## 🛠️ 물리적 배선 이미지
| 제어 보드 전면 (Layout) | 제어 보드 후면 (Wiring) |
| :---: | :---: |
| ![Front](./images/hardware/hardware_front_layout.jpg) | ![Back](./images/hardware/hardware_wiring_back.jpg) |

## 📍 핀 할당 상세 (4WD Mecanum)
| 분류 | 기능 | 핀 | 비고 |
| :--- | :--- | :--- | :--- |
| **Drive** | 4-CH PWM | PA8, PA9, PA10, PA11 | TIM1 (1/2/3/4) |
| | Direction | PB4, PB5, PB10, PB13 | GPIO Out |
| **Encoder** | Enc 1 (FL) | PC6, PC7 | TIM3 |
| | Enc 2 (FR) | PB6, PB7 | TIM4 |
| | Enc 3 (RL) | PA5, PB3 | TIM2 |
| | Enc 4 (RR) | PA0, PA1 | TIM5 |
| **Comms** | RPi 5 | PA2, PA3 | USART2 (TX, RX) |
| **Sensing** | Battery ADC| PC0 | ADC1_IN10 |
| **I2C** | BNO085(IMU)| PB8, PB9 | I2C1 (SCL, SDA) |

## ⚠️ 하드웨어 특징
- **E5V Interface:** 22AWG 배선을 통해 외부 5V 전원을 공급받음.
- **Common Ground:** 대전류 대응을 위해 메인 GND 버스를 납땜 보강함. 