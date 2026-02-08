#!/bin/bash
# 젯슨 WebRTC 스트리밍 실행 (MJPEG 대신 WebRTC 사용)
# cat_detection_service.py와 함께 실행: SERVE_MJPEG=0 으로 cat_detection 실행

set -e
cd "$(dirname "$0")/.."

export BE_WS_URL="${BE_WS_URL:-wss://i14c203.p.ssafy.io/ws}"
export ROBOT_ID="${ROBOT_ID:-1}"
export CAMERA_DEVICE="${CAMERA_DEVICE:-0}"

# CSI 카메라용 GStreamer 파이프라인 (필요 시 설정)
# export GSTREAMER_PIPELINE="nvarguscamerasrc ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink"

echo "[run_jetson_webrtc] BE_WS_URL=$BE_WS_URL"
echo "[run_jetson_webrtc] ROBOT_ID=$ROBOT_ID"
echo "[run_jetson_webrtc] CAMERA_DEVICE=$CAMERA_DEVICE"

python3 scripts/jetson_webrtc.py
