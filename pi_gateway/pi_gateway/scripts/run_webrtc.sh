#!/usr/bin/env bash
set -e

# 프로젝트 루트(pi_gateway)에서 실행한다고 가정
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export PYTHONPATH="${ROOT}:${ROOT}/src:${PYTHONPATH}"

VENV_DIR="${ROOT}/.venv"
VENV_PY="${VENV_DIR}/bin/python3"
VENV_PIP="${VENV_DIR}/bin/pip"

# 1. venv 없으면 생성
if [ ! -d "${VENV_DIR}" ]; then
  echo "[run_webrtc] Creating venv at ${VENV_DIR} ..."
  python3 -m venv "${VENV_DIR}"
fi

# 2. 의존성 설치 (venv pip 사용)
echo "[run_webrtc] Installing deps (venv) ..."
"${VENV_PIP}" install -q -r "${ROOT}/requirements.txt"

# 3. ROS2 환경 설정
if [ -f "/opt/ros/humble/setup.bash" ]; then
  source /opt/ros/humble/setup.bash
fi

# 4. 환경 변수 설정 (선택적)
export BE_WS_URL="${BE_WS_URL:-wss://i14c203.p.ssafy.io/ws}"
export CAMERA_TOPIC="${CAMERA_TOPIC:-/front_cam/compressed}"
export ROBOT_ID="${ROBOT_ID:-1}"

# 5. WebRTC 스트리밍 실행
echo "[run_webrtc] Starting WebRTC streaming ..."
exec "${VENV_PY}" scripts/robot_webrtc.py "$@"
