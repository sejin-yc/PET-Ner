# SLAM 맵 생성 실행 순서

SLAM 맵을 따기 위한 전체 실행 순서입니다.

---

## 📋 전체 실행 순서

### 1단계: Pi Gateway 실행 (터미널 1)

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"

# ROS2 환경 설정 (필수!)
source /opt/ros/humble/setup.bash

# 실기기 연결 시
export DEMO_MODE=0
export ROS_ENABLED=1
export UART_ENABLED=1
export UART_PORT=/dev/serial0
export UART_BAUD=115200

# 또는 데모 모드 (가짜 데이터)
# export DEMO_MODE=1
# export ROS_ENABLED=1

# Pi Gateway 실행
python3 src/main.py
```

**확인:**
- 콘솔에 `[ROS] started.` 메시지 확인
- `TelemetryRosPublisher initialized` 확인
- `EncoderOdomNode initialized` 확인

---

### 2단계: ROS2 토픽 확인 (터미널 2)

```bash
# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# 토픽 목록 확인
ros2 topic list

# 필수 토픽 확인
ros2 topic echo /odom          # Odometry 확인
ros2 topic echo /telemetry/imu # IMU 확인
ros2 topic echo /telemetry/encoder # 엔코더 확인
```

**필수 토픽:**
- `/odom` - Odometry (SLAM 입력)
- `/telemetry/imu` - IMU 데이터
- `/telemetry/encoder` - 엔코더 데이터

---

### 3단계: robot_localization EKF 실행 (터미널 3, 선택사항)

**권장**: wheel odom + IMU 융합하여 더 정확한 odometry 제공

```bash
# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# robot_localization 설치 확인
ros2 pkg list | grep robot_localization

# 설치되어 있지 않으면
sudo apt install ros-humble-robot-localization

# IMU 토픽 리맵 (telemetry/imu → imu/data)
ros2 run topic_tools relay /telemetry/imu /imu/data &

# EKF 실행
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
ros2 run robot_localization ekf_node --ros-args --params-file config/ekf.yaml
```

**확인:**
```bash
ros2 topic echo /odometry/filtered
```

---

### 4단계: SLAM 실행 (터미널 4)

```bash
# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# SLAM 실행 (예: slam_toolbox)
ros2 launch slam_toolbox online_async_launch.py

# 또는 cartographer
# ros2 launch cartographer_ros cartographer.launch.py
```

**입력 토픽:**
- `/odom` 또는 `/odometry/filtered` (EKF 사용 시)
- `/scan` (라이다 스캔)
- `/imu/data` (IMU, 선택사항)

---

### 5단계: 맵 저장 (SLAM 실행 중)

```bash
# 맵 저장 서비스 호출
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: 'my_map'}}"

# 또는 cartographer
# ros2 run cartographer_ros cartographer_pbstream_to_ros_map -pbstream_filename map.pbstream -map_filestem my_map
```

---

## 🚀 빠른 실행 (한 번에)

### 스크립트 생성

```bash
# 실행 스크립트 생성
cat > /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway/scripts/start_slam.sh << 'EOF'
#!/bin/bash

# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# Pi Gateway 실행
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=0
export ROS_ENABLED=1
export UART_ENABLED=1
export UART_PORT=/dev/serial0
export UART_BAUD=115200

python3 src/main.py
EOF

chmod +x scripts/start_slam.sh
```

---

## 📊 실행 순서 다이어그램

```
[터미널 1] Pi Gateway
    ↓
[터미널 2] 토픽 확인
    ↓
[터미널 3] EKF (선택)
    ↓
[터미널 4] SLAM
    ↓
[맵 저장]
```

---

## 🔍 각 단계별 확인 사항

### 1단계: Pi Gateway

**확인:**
- `[ROS] started.` 메시지
- `[WEB] starting uvicorn on 0.0.0.0:8000`
- UART 연결 성공 (실기기 연결 시)

### 2단계: 토픽 확인

**확인:**
```bash
ros2 topic list | grep -E "odom|telemetry|imu|encoder"
ros2 topic hz /odom
```

### 3단계: EKF (선택)

**확인:**
```bash
ros2 topic echo /odometry/filtered
# vx, vy, wz 값이 정상적으로 계산되는지 확인
```

### 4단계: SLAM

**확인:**
- SLAM 노드 실행 확인
- `/map` 토픽 발행 확인
- RViz에서 맵 시각화 확인

---

## 💡 실기기 연결 시 주의사항

### UART 포트 확인

```bash
# UART 포트 확인
ls -la /dev/serial* /dev/ttyUSB* /dev/ttyACM*

# 권한 설정
sudo chmod 666 /dev/serial0
```

### UART 연결 테스트

```bash
# UART 연결 확인
dmesg | grep tty
# 또는
sudo dmesg | tail -20
```

---

## 🧪 데모 모드 테스트

실기기 없이 테스트:

```bash
# 터미널 1: Pi Gateway (데모 모드)
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
export PYTHONPATH="$(pwd):$PYTHONPATH"
source /opt/ros/humble/setup.bash
export DEMO_MODE=1
export ROS_ENABLED=1
python3 src/main.py

# 터미널 2: 토픽 확인
source /opt/ros/humble/setup.bash
ros2 topic echo /odom
```

**주의**: 데모 모드에서는 가짜 데이터만 생성되므로 실제 맵 생성은 어렵습니다.

---

## 📝 요약

1. **Pi Gateway 실행** (ROS2 활성화)
2. **토픽 확인** (`/odom`, `/telemetry/imu` 등)
3. **EKF 실행** (선택, 더 정확한 odometry)
4. **SLAM 실행** (`/odom` 또는 `/odometry/filtered` 사용)
5. **맵 저장** (SLAM 실행 중)

---

## 🔧 문제 해결

### 토픽이 없을 때

```bash
# ROS2 환경 확인
source /opt/ros/humble/setup.bash
ros2 daemon status

# Pi Gateway 실행 확인
ps aux | grep main.py
```

### Odometry가 이상할 때

```bash
# EncoderOdomNode 파라미터 확인
ros2 param list /encoder_odom_node
ros2 param get /encoder_odom_node use_imu_yaw
ros2 param get /encoder_odom_node encoder_filter_alpha
```

### SLAM이 맵을 생성하지 않을 때

```bash
# Odometry 확인
ros2 topic echo /odom
# vx, vy, wz 값이 정상적으로 변하는지 확인

# 라이다 스캔 확인
ros2 topic echo /scan
```
