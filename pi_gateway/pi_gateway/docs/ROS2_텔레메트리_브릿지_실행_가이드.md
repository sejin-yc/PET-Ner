# ROS2 텔레메트리 브릿지 실행 가이드

`/telemetry/imu` 토픽이 발행되려면 텔레메트리 브릿지 노드를 실행해야 합니다.

---

## 🔍 문제 상황

```
WARNING: topic [/telemetry/imu] does not appear to be published yet
```

**원인:**
- ROS2 텔레메트리 브릿지 노드가 실행되지 않음
- UART 연결이 없어서 데이터가 들어오지 않음

---

## ✅ 해결 방법

### 방법 1: 별도 스크립트로 실행 (권장)

텔레메트리 브릿지는 별도 프로세스로 실행하는 것이 일반적입니다:

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway

# UART 포트 설정 (실기기 연결 시)
export UART_PORT=/dev/serial0
export UART_BAUD=115200

# 텔레메트리 브릿지 실행
python3 -m src.ros_telemetry_bridge --port ${UART_PORT:-/dev/serial0} --baud ${UART_BAUD:-115200}
```

**또는 직접 실행:**
```bash
python3 src/ros_telemetry_bridge.py --port /dev/serial0 --baud 115200
```

### 방법 2: 데모 모드 (UART 없이)

UART 없이 테스트하려면:

```bash
# 데모 모드로 Pi Gateway 실행
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=1
export ROS_ENABLED=1
python3 src/main.py
```

**주의**: 데모 모드에서는 실제 UART 데이터가 없으므로 텔레메트리 토픽이 비어있을 수 있습니다.

---

## 🚀 전체 실행 순서

### 1. Pi Gateway 실행

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=1
export ROS_ENABLED=1
python3 src/main.py
```

### 2. 텔레메트리 브릿지 실행 (새 터미널)

**실기기 연결 시:**
```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.ros_telemetry_bridge --port /dev/serial0 --baud 115200
```

**데모 모드 (UART 없이):**
```bash
# 텔레메트리 브릿지는 실제 UART 데이터가 필요하므로
# 데모 모드에서는 실행하지 않거나, 가상 데이터를 발행하는 노드 필요
```

### 3. EncoderOdomNode 실행 (새 터미널, 선택사항)

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Python에서 직접 실행
python3 << EOF
import rclpy
from src.ros_telemetry_bridge import EncoderOdomNode

rclpy.init()
node = EncoderOdomNode(
    use_imu_yaw=True,
    use_imu_gyro=True,
    encoder_filter_alpha=0.7,
    fl_estimation_method="rr"
)
rclpy.spin(node)
EOF
```

---

## 🔍 토픽 확인

### ROS2 토픽 목록 확인

```bash
ros2 topic list
```

**예상 토픽:**
- `/telemetry/battery`
- `/telemetry/imu`
- `/telemetry/encoder`
- `/telemetry/raw`
- `/odom` (EncoderOdomNode 실행 시)

### 특정 토픽 확인

```bash
# IMU 토픽 확인
ros2 topic echo /telemetry/imu

# 엔코더 토픽 확인
ros2 topic echo /telemetry/encoder

# Odometry 확인
ros2 topic echo /odom
```

### 토픽 정보 확인

```bash
ros2 topic info /telemetry/imu
ros2 topic hz /telemetry/imu
```

---

## 🔧 문제 해결

### ROS2가 실행되지 않을 때

```bash
# ROS2 환경 설정 확인
echo $ROS_DOMAIN_ID
source /opt/ros/humble/setup.bash

# ROS2 데몬 확인
ros2 daemon status
```

### UART 포트 문제

```bash
# UART 포트 확인
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM*

# 권한 확인
sudo chmod 666 /dev/serial0
```

### 텔레메트리 데이터가 없을 때

**데모 모드:**
- 실제 UART 데이터가 없으므로 텔레메트리 토픽이 비어있을 수 있음
- 가상 데이터를 발행하는 노드 필요

**실기기 연결:**
- STM32에서 UART로 텔레메트리 데이터가 전송되는지 확인
- UART 연결 상태 확인

---

## 📝 참고

### 텔레메트리 브릿지 역할

1. **UART 수신**: STM32에서 텔레메트리 데이터 수신
2. **ROS2 발행**: `/telemetry/*` 토픽으로 발행
3. **데이터 변환**: 바이너리 → JSON 변환

### EncoderOdomNode 역할

1. **토픽 구독**: `/telemetry/encoder`, `/telemetry/imu`
2. **Odometry 계산**: 엔코더 + IMU → `/odom` 발행
3. **SLAM/nav2 지원**: 표준 odometry 형식 제공

---

## 💡 빠른 테스트

```bash
# 1. ROS2 환경 설정
source /opt/ros/humble/setup.bash

# 2. Pi Gateway 실행 (터미널 1)
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=1
export ROS_ENABLED=1
python3 src/main.py

# 3. 텔레메트리 브릿지 실행 (터미널 2)
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.ros_telemetry_bridge --port /dev/serial0 --baud 115200

# 4. 토픽 확인 (터미널 3)
ros2 topic list
ros2 topic echo /telemetry/imu
```
