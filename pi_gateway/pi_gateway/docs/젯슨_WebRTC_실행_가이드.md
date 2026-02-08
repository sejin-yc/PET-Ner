# 젯슨 WebRTC 스트리밍 실행 가이드

**목적**: 젯슨에서 MJPEG 대신 WebRTC로 영상 스트리밍 (고양이 탐지와 함께 실행)

## 아키텍처

- **cat_detection_service.py**: 고양이 탐지 + cat_state 전송 (MQTT/HTTP)
- **jetson_webrtc.py**: 카메라 → WebRTC → FE (MJPEG 대체)

## 실행 방법

### 터미널 1: 고양이 탐지 (MJPEG 끄기)

```bash
cd pi_gateway

export SERVE_MJPEG=0   # WebRTC 사용 시 MJPEG 비활성화
export BE_SERVER_URL=https://i14c203.p.ssafy.io
export MQTT_HOST=i14c203.p.ssafy.io
export BE_USER_ID=1

./scripts/run_cat_detection.sh
```

### 터미널 2: WebRTC 스트리밍

```bash
cd pi_gateway

export BE_WS_URL=wss://i14c203.p.ssafy.io/ws
export ROBOT_ID=1
export CAMERA_DEVICE=0

./scripts/run_jetson_webrtc.sh
```

## 카메라 공유

두 프로세스가 동일 카메라를 사용할 때:

- **USB 카메라**: V4L2에 따라 두 프로세스 접근이 가능할 수 있음
- **CSI 카메라**: 단일 프로세스만 접근 가능한 경우가 많음

CSI 카메라 사용 시:

1. **방법 A**: ROS 카메라 퍼블리셔를 젯슨에서 실행 → `/front_cam/compressed` 발행  
   - cat_detection: `--camera -1` (ROS 구독)  
   - jetson_webrtc: 카메라 직접 캡처 (단, CSI는 1프로세스만 가능하면 jetson_webrtc만 사용)

2. **방법 B**: 하나만 실행  
   - WebRTC만 필요하면 `jetson_webrtc.py`만 실행  
   - 고양이 탐지만 필요하면 `cat_detection_service.py`만 실행 (MJPEG 또는 WebRTC 미사용)

3. **방법 C**: GStreamer 파이프라인 (CSI)  
   ```bash
   export GSTREAMER_PIPELINE="nvarguscamerasrc ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink"
   ./scripts/run_jetson_webrtc.sh
   ```

## 환경 변수

| 변수 | jetson_webrtc | cat_detection (WebRTC 모드) |
|------|---------------|-----------------------------|
| BE_WS_URL | ✓ wss://... | - |
| ROBOT_ID | ✓ | - |
| CAMERA_DEVICE | ✓ 0 | - |
| SERVE_MJPEG | - | 0 (WebRTC 사용 시) |
| MQTT_HOST | - | ✓ |
| BE_SERVER_URL | - | ✓ |

## 의존성

```bash
pip install aiortc av aiohttp opencv-python
```
