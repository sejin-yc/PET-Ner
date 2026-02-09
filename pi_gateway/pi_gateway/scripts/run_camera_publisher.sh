#!/bin/bash
# 젯슨에서 카메라 → /camera/image_compressed 발행
# Pi Gateway와 같은 ROS_DOMAIN_ID 사용

set -e
cd "$(dirname "$0")/.."

export CAMERA_ID="${CAMERA_ID:-0}"
export CAMERA_WIDTH="${CAMERA_WIDTH:-640}"
export CAMERA_HEIGHT="${CAMERA_HEIGHT:-480}"
export CAMERA_FPS="${CAMERA_FPS:-15}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"

echo "[run_camera_publisher] CAMERA_ID=$CAMERA_ID ${CAMERA_WIDTH}x${CAMERA_HEIGHT} ${CAMERA_FPS}fps"
echo "[run_camera_publisher] Pi Gateway와 ROS_DOMAIN_ID=$ROS_DOMAIN_ID 로 맞출 것"

source /opt/ros/humble/setup.bash 2>/dev/null || true
exec python3 scripts/camera_publisher.py
