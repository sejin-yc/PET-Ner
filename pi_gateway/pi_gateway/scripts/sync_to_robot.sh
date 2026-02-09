#!/bin/bash
# 수정한 파일을 라즈베리파이로 빠르게 동기화하는 스크립트

# 설정 (로봇 IP/계정 받으면 수정)
ROBOT_USER="${ROBOT_USER:-c203}"
ROBOT_IP="${ROBOT_IP:-192.168.100.254}"
ROBOT_PATH="${ROBOT_PATH:-~/pi_gateway}"

# 프로젝트 루트
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo "Pi Gateway → 라즈베리파이 동기화"
echo "=========================================="
echo "로봇: ${ROBOT_USER}@${ROBOT_IP}"
echo "경로: ${ROBOT_PATH}"
echo "=========================================="
echo ""

# rsync로 변경된 파일만 전송 (빠름)
rsync -av --delete \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.git/' \
  --exclude='*.tgz' \
  --exclude='*.log' \
  "${PROJECT_ROOT}/" \
  ${ROBOT_USER}@${ROBOT_IP}:${ROBOT_PATH}/

echo ""
echo "✅ 동기화 완료!"
echo ""
echo "로봇에서 확인:"
echo "  ssh ${ROBOT_USER}@${ROBOT_IP}"
echo "  cd ${ROBOT_PATH}"
echo "  ls -la src/ros_telemetry_bridge.py"
