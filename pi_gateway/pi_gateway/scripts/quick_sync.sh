#!/bin/bash
# 특정 파일만 빠르게 전송 (수정한 파일만)

ROBOT_USER="${ROBOT_USER:-c203}"
ROBOT_IP="${ROBOT_IP:-192.168.100.254}"
ROBOT_PATH="${ROBOT_PATH:-~/pi_gateway}"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 수정한 파일만 전송 (예시)
FILES=(
  "src/ros_telemetry_bridge.py"
  "src/main.py"
  "config/params.yaml"
  "config/ekf.yaml"
)

echo "수정한 파일만 전송 중..."

for file in "${FILES[@]}"; do
  if [ -f "${PROJECT_ROOT}/${file}" ]; then
    echo "  → ${file}"
    scp "${PROJECT_ROOT}/${file}" ${ROBOT_USER}@${ROBOT_IP}:${ROBOT_PATH}/${file}
  else
    echo "  ⚠️  ${file} 없음"
  fi
done

echo ""
echo "✅ 전송 완료!"
