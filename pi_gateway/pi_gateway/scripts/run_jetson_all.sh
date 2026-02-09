#!/bin/bash
# 젯슨 전용 통합 실행 스크립트
# - 고양이 탐지 + cat_state + 갤러리 저장
# - WebRTC 스트리밍
#
# 사용법:
#   1) ROS2 /front_cam/compressed 발행 중이면: ./scripts/run_jetson_all.sh ros
#   2) USB 카메라 직접 사용 (ROS 없음):        ./scripts/run_jetson_all.sh camera
#
# ros 모드: cat_detection, robot_webrtc 둘 다 /front_cam/compressed 구독
# camera 모드: cat_detection --camera 0, jetson_webrtc 카메라 0 (두 프로세스, 터미널 분리)

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export PYTHONPATH="${ROOT}:${ROOT}/src:${PYTHONPATH}"

MODE="${1:-camera}"
BE_URL="${BE_SERVER_URL:-https://i14c203.p.ssafy.io}"
BE_WS_URL="${BE_WS_URL:-wss://i14c203.p.ssafy.io/ws}"
MQTT_HOST="${MQTT_HOST:-i14c203.p.ssafy.io}"
USER_ID="${BE_USER_ID:-1}"
ROBOT_ID="${ROBOT_ID:-1}"

# 모델 경로
CKPT="${CKPT:-./models/swin_tiny_best/best}"
YOLO_POSE="${YOLO_POSE:-./models/yolo_pose.pt}"
for p in "./models/swin_tiny_best/best" "./models/swin_tiny_best/best.pt"; do
  [ -f "$p" ] || [ -d "$p" ] && CKPT="$p" && break
done
for p in "./models/yolo_pose.pt" "./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best"; do
  [ -f "$p" ] || [ -d "$p" ] && YOLO_POSE="$p" && break
done

export BE_SERVER_URL="$BE_URL"
export BE_WS_URL="$BE_WS_URL"
export BE_USER_ID="$USER_ID"
export MQTT_HOST="$MQTT_HOST"
export ROBOT_ID="$ROBOT_ID"
export PI_GATEWAY_PUBLIC_URL="${PI_GATEWAY_PUBLIC_URL:-}"
export CLIPS_DIR="${CLIPS_DIR:-./cat_clips}"
export SERVE_MJPEG=0  # WebRTC 사용 시 MJPEG 끄기

echo "=========================================="
echo "  젯슨 실행 모드: $MODE"
echo "  BE_SERVER_URL=$BE_SERVER_URL"
echo "  MQTT_HOST=$MQTT_HOST"
echo "  BE_USER_ID=$BE_USER_ID"
echo "=========================================="

if [ "$MODE" = "ros" ]; then
  # ROS2 /front_cam/compressed 구독 모드
  # 전제: 젯슨에서 /front_cam/compressed 발행 중 (usb_cam, image_transport 등)
  echo ""
  echo "[1/2] 고양이 탐지 (ROS 토픽 구독) - 백그라운드"
  python3 scripts/cat_detection_service.py \
    --ckpt "$CKPT" \
    --yolo_pose "$YOLO_POSE" \
    --camera -1 \
    --camera_topic /front_cam/compressed \
    --show &
  CAT_PID=$!
  sleep 3

  echo ""
  echo "[2/2] WebRTC 스트리밍 (ROS 토픽 구독)"
  if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
  fi
  export CAMERA_TOPIC=/front_cam/compressed
  python3 scripts/robot_webrtc.py

  kill $CAT_PID 2>/dev/null || true

else
  # camera 모드: USB 카메라 직접 사용 (ROS 없음)
  echo ""
  echo "터미널 2개에서 실행하세요."
  echo ""
  echo "  [터미널 1] 고양이 탐지 + 갤러리 저장:"
  echo "    export SERVE_MJPEG=0 BE_SERVER_URL=$BE_URL MQTT_HOST=$MQTT_HOST BE_USER_ID=$USER_ID"
  echo "    python3 scripts/cat_detection_service.py --ckpt $CKPT --yolo_pose $YOLO_POSE --camera 0 --show"
  echo ""
  echo "  [터미널 2] WebRTC 스트리밍:"
  echo "    export BE_WS_URL=$BE_WS_URL ROBOT_ID=$ROBOT_ID"
  echo "    python3 scripts/jetson_webrtc.py"
  echo ""
  echo "같은 카메라를 두 프로세스가 쓰면 충돌할 수 있습니다."
  echo "ROS2 /front_cam/compressed가 있으면: ./scripts/run_jetson_all.sh ros"
  exit 0
fi
