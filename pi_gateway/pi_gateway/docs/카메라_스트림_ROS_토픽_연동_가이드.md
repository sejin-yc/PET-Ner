# 카메라 스트림 ROS 토픽 연동 가이드

**목적**: 젯슨 카메라 → Pi Gateway → 웹 실시간 영상 (MJPEG)

---

## 1. 전체 흐름

```
[젯슨] 카메라 → /camera/image_compressed (sensor_msgs/CompressedImage)
                    ↓
[Pi Gateway] ROS 구독 → latest_jpeg 저장 → /stream.mjpeg (MJPEG HTTP 스트림)
                    ↓
[웹] <img src="http://PI_URL/stream.mjpeg">
```

---

## 2. 젯슨에서 발행

### 2.0 젯슨 → 웹 직접 (Pi 거치지 않음)

**jetson_mjpeg_server.py** (젯슨에서 실행):

```bash
# 젯슨
cd /path/to/pi_gateway
pip install flask opencv-python
export STREAM_PORT=8080
python3 scripts/jetson_mjpeg_server.py
```

- 웹: `<img src="http://192.168.100.253:8080/stream.mjpeg">`
- 같은 LAN(192.168.100.x)에서 접속 가능
- Pi 거치지 않음

### 2.0-2 젯슨 → Pi → 웹 (A안: 고양이 탐지 + ROS 토픽)

카메라가 젯슨에 연결되어 있으면 **cat_detection_service.py**만 실행하면 됨:

```bash
# 젯슨
cd /path/to/pi_gateway
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0     # Pi Gateway와 동일하게
export PUBLISH_CAMERA_TOPIC=1  # 기본값 1, /camera/image_compressed 자동 발행
python3 scripts/cat_detection_service.py --ckpt models/swin_tiny_best/best --yolo_pose models/yolo_pose.pt
```

- 고양이 탐지 + `/camera/image_compressed` 발행을 **한 프로세스**에서 처리
- `camera_publisher.py`는 스트림만 따로 보고 싶을 때만 사용

**B안 (스트림만)**: `camera_publisher.py` 단독 실행

### 2.1 발행할 토픽

| 항목 | 값 |
|------|-----|
| 토픽명 | `/camera/image_compressed` |
| 메시지 타입 | `sensor_msgs/CompressedImage` |
| 포맷 | JPEG (msg.data = JPEG 바이트) |
| 프레임레이트 | 10~15fps (MVP, 30fps는 이후) |
| 해상도 | 640x480 (MVP) |

### 2.2 예시 (usb_cam)

```bash
# ROS2 usb_cam 사용 시
ros2 run usb_cam usb_cam_node_exe --ros-args \
  -p image_width:=640 \
  -p image_height:=480 \
  -p framerate:=15.0
```

`/image_raw/compressed` 또는 `/image_raw` 발행 시, `image_transport`로 `/camera/image_compressed`에 republish하거나, Pi 구독 토픽을 맞춰주세요.

### 2.3 복붙용 요청 문구

```
Pi Gateway는 /camera/image_compressed (sensor_msgs/CompressedImage) 토픽을 구독해서
웹에 MJPEG 스트림으로 전달합니다.
젯슨에서 해당 토픽을 10~15fps, 640x480 JPEG로 발행해 주세요.
```

---

## 3. Pi Gateway

### 3.1 구현 내용

- `_TelemetrySub` 노드에서 `/camera/image_compressed` 구독
- 수신 시 `_latest_jpeg`에 저장 (스레드 안전)
- `GET /stream.mjpeg` → multipart/x-mixed-replace MJPEG 스트림

### 3.2 확인

```bash
# Pi Gateway 실행 후
curl -N http://localhost:8000/stream.mjpeg
# 또는 브라우저에서
# http://localhost:8000/stream.mjpeg
```

---

## 4. 웹 (React) 사용법

### 4.1 단순 img

```tsx
<img 
  src={`${PI_GATEWAY_URL}/stream.mjpeg`} 
  alt="실시간 카메라" 
  style={{ width: '100%', maxWidth: 640 }}
/>
```

`PI_GATEWAY_URL`: 예) `http://192.168.x.x:8000` (Pi Gateway 주소)

### 4.2 토글 버튼 (영상 시작/중지)

```tsx
const [showStream, setShowStream] = useState(false);
const PI_GATEWAY_URL = 'http://localhost:8000'; // 또는 env

return (
  <>
    <button onClick={() => setShowStream(!showStream)}>
      {showStream ? '영상 중지' : '영상 시작'}
    </button>
    {showStream && (
      <img 
        src={`${PI_GATEWAY_URL}/stream.mjpeg`} 
        alt="실시간 카메라"
        style={{ width: '100%', maxWidth: 640 }}
      />
    )}
  </>
);
```

### 4.3 CORS

- Pi Gateway(FastAPI)에서 웹 도메인에 CORS 허용 필요
- `web_ws_server`에 이미 CORS 미들웨어가 있으면 별도 설정 불필요
- 웹과 Pi가 다른 origin이면 FastAPI에 `CORSMiddleware` 추가

---

## 5. 트러블슈팅

| 증상 | 원인 | 조치 |
|------|------|------|
| 검은 화면/로딩 | 토픽 미발행 | `ros2 topic echo /camera/image_compressed` 확인 |
| 느림/끊김 | fps/해상도 과다 | 10~15fps, 640x480 권장 |
| CORS 에러 | cross-origin | FastAPI CORS 설정 확인 |

---

