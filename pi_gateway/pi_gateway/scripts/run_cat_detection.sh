#!/bin/bash
# 고양이 탐지 서비스 실행
# 모델은 models/ 폴더에 두세요. (models/README.md 참고)

set -e
cd "$(dirname "$0")/.."

# 모델 경로: models/ 우선
CKPT="${CKPT:-./models/swin_tiny_best/best.pt}"
YOLO_POSE="${YOLO_POSE:-./models/yolo_pose.pt}"

# Swin: models/ 없으면 이전 경로
if [ ! -f "$CKPT" ] && [ ! -d "${CKPT%.pt}" ]; then
  if [ -f "./models/swin_tiny_best/best.pt" ] || [ -d "./models/swin_tiny_best/best" ]; then
    CKPT="./models/swin_tiny_best/best.pt"
  elif [ -f "/home/ssafy/Downloads/swin_tiny_best/best.pt" ] || [ -d "/home/ssafy/Downloads/swin_tiny_best/best" ]; then
    CKPT="/home/ssafy/Downloads/swin_tiny_best/best.pt"
    echo "[run_cat_detection] swin: models/ 없음, Downloads 사용"
  fi
fi

# YOLO: models/yolo_pose.pt 또는 models/yolo_pose-xxx/ (폴더) 지원
if [ ! -f "$YOLO_POSE" ]; then
  if [ -d "./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome" ]; then
    YOLO_POSE="./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best"
    echo "[run_cat_detection] yolo: 폴더 형식 사용"
  elif [ -f "./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt" ]; then
    YOLO_POSE="./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt"
  elif [ -f "/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt" ]; then
    YOLO_POSE="/home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt"
    echo "[run_cat_detection] yolo: models/ 없음, Downloads 사용"
  fi
fi

# swin_tiny_best가 폴더 형식(best/)이면 경로 조정
if [ ! -f "$CKPT" ]; then
  ALT="${CKPT%.pt}"
  if [ -d "$ALT" ]; then
    CKPT="$ALT"
    echo "[run_cat_detection] 폴더 형식 체크포인트 사용: $CKPT"
  fi
fi

# Spring 연동 (있으면 POST /api/videos)
export BE_SERVER_URL="${BE_SERVER_URL:-}"
export BE_USER_ID="${BE_USER_ID:-1}"

# Pi Gateway 주소 (필수). 영상 URL에 사용. 미설정 시 프론트 재생 불가
export PI_GATEWAY_PUBLIC_URL="${PI_GATEWAY_PUBLIC_URL:-}"

# MQTT (있으면 /sub/robot/cat_state 발행)
export MQTT_HOST="${MQTT_HOST:-}"

# 영상 저장 폴더
export CLIPS_DIR="${CLIPS_DIR:-./cat_clips}"

# 젯슨에서 WebRTC 사용 시 MJPEG 끄기 (jetson_webrtc.py와 함께 실행할 때)
# export SERVE_MJPEG=0
export SERVE_MJPEG="${SERVE_MJPEG:-1}"

echo "[run_cat_detection] ckpt=$CKPT"
echo "[run_cat_detection] yolo_pose=$YOLO_POSE"
echo "[run_cat_detection] clips_dir=$CLIPS_DIR"

python3 scripts/cat_detection_service.py \
  --ckpt "$CKPT" \
  --yolo_pose "$YOLO_POSE" \
  --camera 0 \
  --show
