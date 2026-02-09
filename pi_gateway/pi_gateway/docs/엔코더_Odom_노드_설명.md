# 엔코더 Odom 노드 설명

엔코더와 IMU 데이터를 사용하여 오도메트리를 계산하고 발행하는 노드입니다.

---

## 📋 실제 구현 정보

### 파일 위치
- **파일**: `src/ros_telemetry_bridge.py`
- **클래스**: `EncoderOdomNode`
- **노드 이름**: `encoder_odom_node`

---

## 📥 입력 토픽

### 1. `telemetry/encoder` (std_msgs/String, JSON)

**메시지 형식:**
```json
{
  "type": "encoder",
  "enc_fl": 12345,  // 앞왼쪽 누적 틱
  "enc_fr": 12350,  // 앞오른쪽 누적 틱
  "enc_rl": 12340,  // 뒤왼쪽 누적 틱
  "enc_rr": 12345   // 뒤오른쪽 누적 틱
}
```

**구독 코드:**
```python
# src/ros_telemetry_bridge.py:74
self._sub_enc = self.create_subscription(
    String, "telemetry/encoder", self._on_encoder, 10
)
```

### 2. `telemetry/imu` (std_msgs/String, JSON)

**메시지 형식:**
```json
{
  "type": "imu",
  "yaw": 1.57  // yaw 각도 (rad)
}
```

**구독 코드:**
```python
# src/ros_telemetry_bridge.py:75
self._sub_imu = self.create_subscription(
    String, "telemetry/imu", self._on_imu, 10
)
```

---

## 🔄 계산 과정

### 1단계: 델타 틱 계산

```python
# src/ros_telemetry_bridge.py:106-109
d_fl = (int(fl) - self._prev[0]) * self._meters_per_tick
d_fr = (int(fr) - self._prev[1]) * self._meters_per_tick
d_rl = (int(rl) - self._prev[2]) * self._meters_per_tick
d_rr = (int(rr) - self._prev[3]) * self._meters_per_tick
```

**계산:**
- 이전 틱과 현재 틱의 차이 계산
- `meters_per_tick`를 곱하여 델타 거리로 변환

### 2단계: 4륜 선속도 계산

```python
# src/ros_telemetry_bridge.py:110-111
v_fl, v_fr = d_fl / dt, d_fr / dt
v_rl, v_rr = d_rl / dt, d_rr / dt
```

**계산:**
- 델타 거리를 시간(dt)으로 나누어 선속도 계산

### 3단계: 메카넘 역기구학 (4륜 → vx, vy, wz)

```python
# src/ros_telemetry_bridge.py:112-115
vx = (v_fl + v_fr + v_rl + v_rr) / 4.0
vy = (-v_fl + v_fr - v_rl + v_rr) / 4.0
den = 4.0 * (self._lx + self._ly)
wz = (-v_fl + v_fr + v_rl - v_rr) / den if den > 1e-9 else 0.0
```

**계산:**
- `vx`: 앞뒤 속도 (4륜 평균)
- `vy`: 좌우 속도 (메카넘 역기구학)
- `wz`: 회전 각속도 (메카넘 역기구학)

### 4단계: Yaw 계산

```python
# src/ros_telemetry_bridge.py:116-120
if self._imu_yaw is not None:
    yaw = self._imu_yaw  # IMU yaw 우선 사용
else:
    self._yaw += wz * dt  # IMU 없으면 wz 적분
    yaw = self._yaw
```

**계산:**
- **IMU yaw 우선**: IMU가 있으면 IMU yaw 사용
- **wz 적분**: IMU가 없으면 wz를 적분하여 yaw 계산

### 5단계: 위치 적분 (x, y)

```python
# src/ros_telemetry_bridge.py:121-122
self._x += (vx * math.cos(yaw) - vy * math.sin(yaw)) * dt
self._y += (vx * math.sin(yaw) + vy * math.cos(yaw)) * dt
```

**계산:**
- `(vx, vy)`를 yaw로 회전하여 지도 좌표계로 변환
- 적분하여 `(x, y)` 위치 계산

---

## 📤 출력 토픽

### `odom` (nav_msgs/Odometry)

**토픽 이름**: `odom` (ROS2에서는 `/odom`과 동일)

**메시지 형식:**
```python
nav_msgs/msg/Odometry:
  header:
    stamp: Time
    frame_id: "odom"  # 파라미터에서 설정
  child_frame_id: "base_link"  # 파라미터에서 설정
  pose:
    pose:
      position:
        x: float  # 계산된 x 위치 (m)
        y: float  # 계산된 y 위치 (m)
        z: 0.0
      orientation:
        x: 0.0
        y: 0.0
        z: sin(yaw / 2.0)
        w: cos(yaw / 2.0)  # yaw를 quaternion으로 변환
    covariance: [0] * 36  # -1로 설정 (불확실성 표시)
  twist:
    twist:
      linear:
        x: float  # vx (m/s)
        y: float  # vy (m/s)
        z: 0.0
      angular:
        x: 0.0
        y: 0.0
        z: float  # wz (rad/s)
    covariance: [0] * 36  # -1로 설정
```

**발행 코드:**
```python
# src/ros_telemetry_bridge.py:76, 123-137
self._pub = self.create_publisher(Odometry, "odom", 10)
# ...
odom = Odometry()
odom.header.stamp = now.to_msg()
odom.header.frame_id = self._odom_frame
odom.child_frame_id = self._child_frame
odom.pose.pose.position.x = self._x
odom.pose.pose.position.y = self._y
odom.pose.pose.orientation = _yaw_to_quat(yaw)
odom.twist.twist.linear.x, odom.twist.twist.linear.y = vx, vy
odom.twist.twist.angular.z = wz
self._pub.publish(odom)
```

---

## ⚙️ 파라미터

**파일**: `config/params.yaml`

```yaml
encoder:
  meters_per_tick: 4.86e-4   # 1틱당 이동거리(m). (π×0.097)/(11×57) = 0.0004858
  odom_lx: 0.12            # m, 로봇 앞뒤 반거리
  odom_ly: 0.15            # m, 로봇 좌우 반거리
  odom_frame_id: "odom"    # 기본값 (파라미터에서 설정 가능)
  child_frame_id: "base_link"  # 기본값 (파라미터에서 설정 가능)
```

**초기화 코드:**
```python
# src/main.py:246-252
odom_node = EncoderOdomNode(
    meters_per_tick=float(enc_p.get("meters_per_tick", 1e-5)),
    odom_lx=float(enc_p.get("odom_lx", 0.1)),
    odom_ly=float(enc_p.get("odom_ly", 0.1)),
    odom_frame_id=str(enc_p.get("odom_frame_id", "odom")),
    child_frame_id=str(enc_p.get("child_frame_id", "base_link")),
)
```

---

## ✅ 사용자가 말한 내용 확인

### 맞는 내용 ✅

1. ✅ **입력**: `telemetry/encoder` (4륜 누적 틱), `telemetry/imu` (yaw)
2. ✅ **계산 과정**: 델타 틱 → 델타 거리 → 4륜 선속도 → 메카넘으로 vx, vy, wz → yaw로 회전해서 적분 → x, y
3. ✅ **출력**: `nav_msgs/Odometry` → `/odom` (또는 `odom`)
4. ✅ **파라미터**: `meters_per_tick`, `odom_lx`, `odom_ly`, `odom_frame_id`, `child_frame_id`
5. ✅ **meters_per_tick 계산**: `(π × 휠지름) / (ppr × 기어비)`

### 약간 다른 내용 ⚠️

1. ⚠️ **파일 이름**: 
   - 사용자: `src/encoder_odom_node.py`
   - 실제: `src/ros_telemetry_bridge.py` (클래스: `EncoderOdomNode`)

2. ⚠️ **입력 메시지 타입**:
   - 사용자: 직접적인 숫자 값
   - 실제: `std_msgs/String` (JSON 형식)
   - 예: `{"type": "encoder", "enc_fl": 12345, ...}`

3. ⚠️ **토픽 이름**:
   - 사용자: `/odom`
   - 실제: `odom` (ROS2에서는 `/odom`과 동일하게 동작)

---

## 💡 SLAM 담당자에게 전달할 내용

**Pi Gateway가 `/odom` 토픽에 `nav_msgs/Odometry` 메시지를 발행합니다.**
**SLAM이 이 토픽을 구독하여 오도메트리 정보를 사용하세요.**

**구독 방법:**
```bash
# 토픽 확인
ros2 topic list | grep odom
ros2 topic echo /odom

# 메시지 정보 확인
ros2 topic info /odom
ros2 topic hz /odom
```

**메시지 구조:**
- `pose.pose.position`: (x, y, z=0.0) - 계산된 위치
- `pose.pose.orientation`: yaw를 quaternion으로 변환
- `twist.twist.linear`: (vx, vy, z=0.0) - 현재 속도
- `twist.twist.angular`: (x=0.0, y=0.0, z=wz) - 회전 각속도

**frame_id:**
- `header.frame_id`: "odom" (기본값)
- `child_frame_id`: "base_link" (기본값)

**간단히 말하면:**
> "Pi Gateway가 `/odom` 토픽에 `nav_msgs/msg/Odometry` 메시지를 **발행**합니다.
> SLAM이 이 토픽을 **구독**하여 오도메트리 정보를 사용하세요."

---

## ✅ 요약

**사용자가 말한 내용은 대부분 정확합니다!**

- ✅ 입력 토픽: `telemetry/encoder`, `telemetry/imu`
- ✅ 계산 과정: 정확히 설명됨
- ✅ 출력 토픽: `/odom` (또는 `odom`)
- ✅ 메시지 타입: `nav_msgs/Odometry`
- ✅ 파라미터: 모두 정확

**약간의 차이:**
- 파일 이름이 `ros_telemetry_bridge.py`에 포함되어 있음 (별도 파일 아님)
- 입력 메시지가 JSON 형식의 String임 (내부적으로 파싱)

**SLAM/Nav2 담당자에게는:**
> "Pi Gateway가 `/odom` 토픽에 `nav_msgs/Odometry` 메시지를 발행합니다. 
> 엔코더와 IMU 데이터를 사용하여 계산한 오도메트리 정보입니다."
