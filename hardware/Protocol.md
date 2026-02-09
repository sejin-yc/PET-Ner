# 📝 Communication Protocol

## 1. STM32 -> PC (Feedback Data)
로봇의 현재 상태를 피드백합니다. 전방 엔코더 하드웨어 이슈로 인해 **소프트웨어 추정값(Virtual Encoder)**을 전송합니다.

**Format:**
`KEY:[Command] | FL:[Value] RL:[Value] FR:[Value] RR:[Value] | V:[Voltage]`

**Example:**
`KEY:w | FL:1500 RL:1500 FR:1480 RR:1480 | V:12.4V`

### 🧠 Virtual Encoder Logic (Software Patch)
`main.c` 내부에서 전방(FL, FR) 엔코더의 값을 후방(RL, RR) 엔코더 값과 현재 주행 명령(Command)을 기반으로 역산하여 전송합니다.

* **직진/후진 (w, x):** `FL = RL`, `FR = RR`
* **좌 평행이동 (a):** `FL = RR`, `FR = -RL` (메카넘 기구학 대칭성 이용)
* **우 평행이동 (d):** `FL = RR`, `FR = RL`
* **제자리 회전 (q, e):** `FL = RL`, `FR = RR`

## 2. PC -> STM32 (Control Command)
단일 문자(char)를 통해 로봇의 기동을 제어합니다.

| Key | Action | Motor PWM State (FL/FR/RL/RR) |
| :--- | :--- | :--- |
| **'w'** | 전진 | (+, +, +, +) |
| **'x'** | 후진 | (-, -, -, -) |
| **'a'** | 좌 평행이동 | (-, +, +, -) |
| **'d'** | 우 평행이동 | (+, -, -, +) |
| **'s'** | 정지 | (0, 0, 0, 0) |

