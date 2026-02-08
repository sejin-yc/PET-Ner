#!/bin/bash
# 고양이 탐지 + WebRTC 통합 서비스 실행 (한 터미널로 둘 다)
# cat_detection + robot_webrtc 통합본

set -e
cd "$(dirname "$0")/.."

CKPT="${CKPT:-./models/swin_tiny_best/best.pt}"
YOLO_POSE="${YOLO_POSE:-./models/yolo_pose.pt}"

# Swin: models/swin_tiny_best.pt 또는 models/swin_tiny_best/best 지원
if [ ! -f "$CKPT" ] && [ ! -d "${CKPT%.pt}" ]; then
  if [ -f "./models/swin_tiny_best.pt" ]; then
    CKPT="./models/swin_tiny_best.pt"
  elif [ -f "./models/swin_tiny_best/best.pt" ] || [ -d "./models/swin_tiny_best/best" ]; then
    CKPT="./models/swin_tiny_best/best.pt"
  elif [ -d "./models/swin_tiny_best" ]; then
    CKPT="./models/swin_tiny_best/best"
    echo "[run_cat_detection_webrtc] Swin 폴더 형식: $CKPT"
  elif [ -f "/home/ssafy/Downloads/swin_tiny_best/best.pt" ] || [ -d "/home/ssafy/Downloads/swin_tiny_best/best" ]; then
    CKPT="/home/ssafy/Downloads/swin_tiny_best/best"
    echo "[run_cat_detection_webrtc] Swin: models/ 없음, Downloads 사용"
  elif [ -d "/home/ssafy/Downloads/swin_tiny_best" ]; then
    CKPT="/home/ssafy/Downloads/swin_tiny_best"
    echo "[run_cat_detection_webrtc] Swin: $CKPT"
  fi
fi

# YOLO: models/ 없으면 Downloads fallback
if [ ! -f "$YOLO_POSE" ] && [ ! -d "$YOLO_POSE" ]; then
  if [ -d "./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome" ]; then
    YOLO_POSE="./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best"
  elif [ -d "./models/yolo_pose" ]; then
    YOLO_POSE="./models/yolo_pose"
  elif [ -d "/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome" ]; then
    YOLO_POSE="/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best"
    echo "[run_cat_detection_webrtc] YOLO: models/ 없음, Downloads 사용"
  elif [ -f "/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt" ]; then
    YOLO_POSE="/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt"
    echo "[run_cat_detection_webrtc] YOLO: .pt 파일 사용"
  fi
fi

# Swin 폴더 형식 (best/ 내부 data.pkl)
if [ ! -f "$CKPT" ]; then
  ALT="${CKPT%.pt}"
  if [ -d "$ALT" ]; then
    CKPT="$ALT"
  fi
fi

export BE_SERVER_URL="${BE_SERVER_URL:-https://i14c203.p.ssafy.io}"
export BE_WS_URL="${BE_WS_URL:-wss://i14c203.p.ssafy.io/ws}"
export BE_USER_ID="${BE_USER_ID:-1}"
export ROBOT_ID="${ROBOT_ID:-1}"
export PI_GATEWAY_PUBLIC_URL="${PI_GATEWAY_PUBLIC_URL:-}"
export MQTT_HOST="${MQTT_HOST:-i14c203.p.ssafy.io}"
export CLIPS_DIR="${CLIPS_DIR:-./cat_clips}"
export CAMERA_TOPIC="${CAMERA_TOPIC:-/front_cam/compressed}"
export SERVE_MJPEG="${SERVE_MJPEG:-1}"

echo "[run_cat_detection_webrtc] ckpt=$CKPT"
echo "[run_cat_detection_webrtc] yolo_pose=$YOLO_POSE"
echo "[run_cat_detection_webrtc] BE_WS_URL=$BE_WS_URL"
echo "[run_cat_detection_webrtc] ROS 토픽 사용 (--camera 미지정 시). 로컬 테스트: --camera 0 --show 추가"

python3 scripts/cat_detection_webrtc.py \
  --ckpt "$CKPT" \
  --yolo_pose "$YOLO_POSE" \
  "$@"
