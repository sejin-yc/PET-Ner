# SLAM+nav2 최적화 가이드 (실무 관점)

왼쪽 앞바퀴(fl) 고장 시 SLAM+nav2 환경에서 안정적이고 정확한 odometry 계산 방법입니다.

---

## ✅ "진짜로 추천" (바로 적용해도 이득 큰 것)

### 1) IMU yaw + gyro_z(wz) 우선 사용 ✅✅✅

**필수에 가까움**. 특히 메카넘 + 슬립 환경에서 SLAM 맵 품질을 좌우함.

- `yaw`: 위치 추정에 사용
- `gyro_z(wz)`: 각속도 측정 (엔코더보다 정확)
- 엔코더 yaw는 "fallback" 정도로만 사용

**구현:**
```python
# IMU에서 gyro_z 우선 사용
if self._use_imu_gyro and self._imu_gyro_z is not None:
    wz_raw = self._imu_gyro_z  # 엔코더 wz 대신 IMU 사용

# IMU yaw 우선 사용
if self._use_imu_yaw and self._imu_yaw is not None:
    yaw = self._imu_yaw  # 엔코더 yaw는 fallback
```

---

### 2) FL 추정값으로 4륜식 유지 ✅✅✅

**가중치 기반 보정보다 안정적**. 튜닝 지옥 방지.

**방법:**
- `v_fl = v_rr` (대칭 위치 가정, 기본값)
- 또는 `v_fl = (v_fr + v_rl + v_rr) / 3` (평균)

**이유:**
- 4륜식 공식 유지로 안정성 확보
- 가중치는 환경/동작에 따라 최적값이 달라져 편향 발생 가능
- EKF가 공분산으로 신뢰도 조절하는 방식이 더 안정적

**구현:**
```python
v_fl_est = self._estimate_fl_velocity(v_fr, v_rl, v_rr)
# 4륜식 공식 유지
vx = (v_fl_est + v_fr + v_rl + v_rr) / 4.0
vy = (-v_fl_est + v_fr - v_rl + v_rr) / 4.0
wz = (-v_fl_est + v_fr + v_rl - v_rr) / (4 * (lx + ly))
```

---

### 3) 속도 필터링(EMA) ✅✅

`vx, vy`에 EMA 거는 건 유효하지만, **SLAM/내비는 지연에 민감**.

**권장 설정:**
- 시작값: `alpha = 0.6~0.75`
- nav2 경로추종이 "늦게 반응"하면 alpha를 올려(=필터 약화)
- 너무 세게 걸면 컨트롤이 둔해질 수 있음

**구현:**
```python
vx = 0.7 * vx_raw + 0.3 * vx_prev  # alpha=0.7
```

---

### 4) 공분산 설정 ✅✅✅

"3륜 모드라 더 불확실"을 공분산으로 표현하는 건 **정석**.

**목적:**
- EKF(robot_localization)가 "wheel odom을 덜 믿도록" 만들기
- SLAM이 wheel odom의 불확실성을 고려하도록

**구현:**
```python
# pose covariance: 위치 불확실성
odom.pose.covariance[0] = 0.1   # x
odom.pose.covariance[7] = 0.1   # y
odom.pose.covariance[35] = 0.2  # yaw (FL 추정값 사용으로 증가)

# twist covariance: 속도 불확실성
odom.twist.covariance[0] = 0.05   # vx
odom.twist.covariance[7] = 0.08   # vy (비대칭으로 인해 더 높음)
odom.twist.covariance[35] = 0.1   # wz (IMU 사용 시 낮아짐)
```

---

## ⚠️ "부분 추천" (조건부로만)

### 5) 이상치 제거 / 속도 제한 ✅ (조건부)

갑자기 튀는 tick, 순간 속도 폭주를 막는 건 좋음.

**주의:**
- nav2에서 "급정지/급회전" 같은 상황에서 클리핑이 과하면 추종이 이상해질 수 있음
- "점프 제거"는 추천: `abs(v - prev_v) > threshold`면 제한
- "하드 클리핑"은 너무 빡세게 하지 말기

---

## ❌ "비추" (정확도 개선이라기보다 리스크 큼)

### 6) 가중치(weight_fr=1.2 등) ❌❌

**튜닝 지옥 가능성 큼**.

**이유:**
- FR이 "FL의 대칭"이라는 이유로 가중치를 주는 건 물리적으로 보장되는 관계가 아님
- 메카넘은 횡이동/회전에서 바퀴별 역할이 계속 바뀌고 슬립도 바뀜
- 가중치는 환경/동작에 따라 최적값이 달라져서 "고정 가중치"는 쉽게 편향을 만듦

**대안:**
- FL 추정값을 넣어서 4륜식 유지
- 공분산으로 "덜 믿게" 처리
- EKF가 최종 융합

---

### 7) 비대칭 보정 계수(asymmetry_factor) ❌

`vy`가 커질 때만 보정하는 건 "증상 치료".

**문제:**
- 특정 동작에선 맞고 특정 동작에선 틀리는 문제
- EKF에서 공분산/차분 모드로 대응하거나 SLAM이 보정하게 두는 게 일반적으로 낫다

---

### 8) 칼만 필터 직접 구현 ❌

**robot_localization EKF 쓰는 게 정답**.

**이유:**
- 이미 ROS 생태계에서 검증됨
- 파라미터만 잘 넣으면 됨
- SLAM/nav2 연결도 정석

---

## ✅ SLAM+nav2용 권장 구성

### 전체 아키텍처

```
[STM32] → UART → [ros_telemetry_bridge]
                          ↓
              [EncoderOdomNode] → /odom (wheel odom)
                          ↓
              [IMU] → /imu/data
                          ↓
              [robot_localization EKF] → /odometry/filtered
                          ↓
              [SLAM] → /map
                          ↓
              [nav2] → /cmd_vel
```

### 1. wheel_odom (`EncoderOdomNode`)

- 3개 엔코더(fr, rl, rr) + FL 추정으로 vx/vy 계산
- EMA 필터링 (alpha=0.6~0.75)
- IMU yaw + gyro_z(wz) 우선 사용
- 공분산으로 불확실성 표현

### 2. IMU

- `yaw` (rad): 회전 각도
- `gyro_z` (rad/s): 각속도 (wz)

### 3. EKF (`robot_localization`)

- wheel_odom(속도 위주, differential mode) + IMU(yaw/wz) 융합
- 최종 `/odometry/filtered` 발행

### 4. SLAM/nav2

- `/odometry/filtered` 사용
- 공분산을 고려하여 맵 품질 향상

---

## 📝 핵심 원칙

> **"가중치 기반 보정보다, EKF에서 공분산과 differential 모드로 wheel odom 신뢰도를 조절하는 방식이 더 안정적이며, SLAM/nav2에서 튜닝 비용이 낮다."**

---

## 🔧 설정 파일

### `config/ekf.yaml`

robot_localization EKF 설정 파일 (복붙용):

- `odom0`: `/odom` (wheel odom, differential mode)
- `imu0`: `/imu/data` (yaw + gyro_z만 사용)
- 출력: `/odometry/filtered`

### 토픽 리맵 (launch 파일)

```xml
<!-- telemetry/imu → imu/data 리맵 -->
<node pkg="topic_tools" type="relay" name="imu_relay">
  <remap from="/input" to="/telemetry/imu"/>
  <remap from="/output" to="/imu/data"/>
</node>
```

---

## 🧪 테스트 방법

### 1. wheel odom 확인

```bash
ros2 topic echo /odom
# vx, vy, wz 값 확인
# 공분산 확인
```

### 2. EKF 확인

```bash
ros2 topic echo /odometry/filtered
# 융합된 odometry 확인
```

### 3. SLAM 맵 품질 확인

```bash
# SLAM 실행 후 맵 품질 확인
# 맵이 깨지거나 비틀리지 않는지 확인
```

---

## 💡 파라미터 튜닝 가이드

### EMA 필터링 강도

```python
# 부드러운 동작 (노이즈 제거 우선, 지연 증가)
encoder_filter_alpha = 0.6

# 빠른 반응 (정확도 우선, nav2 반응성 향상)
encoder_filter_alpha = 0.75
```

### FL 추정 방법

```python
# 대칭 위치 가정 (기본값)
fl_estimation_method = "rr"  # v_fl = v_rr

# 평균 사용
fl_estimation_method = "avg"  # v_fl = 평균
```

### 공분산 조정

```python
# 불확실성 증가 (EKF가 덜 믿도록)
odom.pose.covariance[35] = 0.3  # yaw 불확실성 증가

# 불확실성 감소 (EKF가 더 믿도록)
odom.pose.covariance[35] = 0.1  # yaw 불확실성 감소
```

---

## 📚 참고

- **robot_localization**: ROS2 표준 EKF 패키지
- **differential mode**: 위치 대신 속도 위주로 사용 (슬립 보정)
- **공분산**: 불확실성 표현 (EKF가 신뢰도 조절)
