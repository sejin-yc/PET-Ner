# SLAM 맵 생성 실행 순서 (간단 버전)

SLAM 맵을 따기 위한 빠른 실행 가이드입니다.

---

## 🚀 빠른 실행 순서

### 1단계: Pi Gateway 실행 (터미널 1)

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway

# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# 실기기 연결 시
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=0
export ROS_ENABLED=1
export UART_ENABLED=1
export UART_PORT=/dev/serial0
export UART_BAUD=115200

# 실행
python3 src/main.py
```

**또는 스크립트 사용:**
```bash
./scripts/start_slam.sh
```

**확인:**
- `[ROS] started.` 메시지 확인
- `EncoderOdomNode initialized` 확인

---

### 2단계: 토픽 확인 (터미널 2)

```bash
# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# 필수 토픽 확인
ros2 topic list | grep -E "odom|telemetry"

# Odometry 확인
ros2 topic echo /odom
```

**필수 토픽:**
- `/odom` ✅ (SLAM 입력)
- `/telemetry/imu` ✅
- `/telemetry/encoder` ✅

---

### 3단계: SLAM 실행 (터미널 3)

```bash
# ROS2 환경 설정
source /opt/ros/humble/setup.bash

# SLAM 실행 (예: slam_toolbox)
ros2 launch slam_toolbox online_async_launch.py
```

**입력 토픽:**
- `/odom` - Odometry
- `/scan` - 라이다 스캔
- `/imu/data` - IMU (선택사항)

---

### 4단계: 맵 저장

SLAM 실행 중에:

```bash
# 맵 저장
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: 'my_map'}}"
```

---

## 📋 전체 실행 순서 (상세)

### 터미널 1: Pi Gateway

```bash
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
source /opt/ros/humble/setup.bash
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DEMO_MODE=0
export ROS_ENABLED=1
export UART_ENABLED=1
export UART_PORT=/dev/serial0
python3 src/main.py
```

### 터미널 2: 토픽 확인

```bash
source /opt/ros/humble/setup.bash
ros2 topic list
ros2 topic echo /odom
ros2 topic hz /odom
```

### 터미널 3: EKF (선택, 권장)

```bash
source /opt/ros/humble/setup.bash

# IMU 토픽 리맵
ros2 run topic_tools relay /telemetry/imu /imu/data &

# EKF 실행
cd /home/ssafy/Downloads/pi_gateway_spec_aligned/pi_gateway
ros2 run robot_localization ekf_node --ros-args --params-file config/ekf.yaml
```

**확인:**
```bash
ros2 topic echo /odometry/filtered
```

### 터미널 4: SLAM

```bash
source /opt/ros/humble/setup.bash

# SLAM 실행
ros2 launch slam_toolbox online_async_launch.py

# 또는 cartographer
# ros2 launch cartographer_ros cartographer.launch.py
```

**RViz에서 확인:**
```bash
ros2 run rviz2 rviz2
# Fixed Frame: map
# Add: Map, LaserScan, Odometry
```

---

## ✅ 각 단계별 확인 체크리스트

### 1단계: Pi Gateway ✅

- [ ] `[ROS] started.` 메시지 확인
- [ ] `EncoderOdomNode initialized` 확인
- [ ] UART 연결 성공 (실기기 연결 시)

### 2단계: 토픽 확인 ✅

- [ ] `/odom` 토픽 발행 확인
- [ ] `/telemetry/imu` 토픽 발행 확인
- [ ] `/telemetry/encoder` 토픽 발행 확인
- [ ] Odometry 값이 정상적으로 변하는지 확인

### 3단계: EKF (선택) ✅

- [ ] `/odometry/filtered` 토픽 발행 확인
- [ ] 융합된 odometry 값 확인

### 4단계: SLAM ✅

- [ ] SLAM 노드 실행 확인
- [ ] `/map` 토픽 발행 확인
- [ ] RViz에서 맵 시각화 확인

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

### UART 연결 문제

```bash
# UART 포트 확인
ls -la /dev/serial* /dev/ttyUSB*

# 권한 설정
sudo chmod 666 /dev/serial0
```

---

## 💡 핵심 포인트

1. **ROS2 환경 설정 필수**: `source /opt/ros/humble/setup.bash`
2. **ROS_ENABLED=1**: ROS2 모드 활성화
3. **UART 연결**: 실기기 연결 시 UART 포트 확인
4. **Odometry 확인**: `/odom` 토픽이 정상적으로 발행되는지 확인
5. **SLAM 입력**: `/odom` 또는 `/odometry/filtered` 사용

---

## 📝 요약

```
1. Pi Gateway 실행 (ROS2 활성화)
   ↓
2. 토픽 확인 (/odom 확인)
   ↓
3. EKF 실행 (선택, 더 정확한 odometry)
   ↓
4. SLAM 실행 (/odom 사용)
   ↓
5. 맵 저장
```
