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
  echo "[run_gateway] Creating venv at ${VENV_DIR} ..."
  python3 -m venv "${VENV_DIR}"
fi

# 2. 의존성 설치 (venv pip 사용)
echo "[run_gateway] Installing deps (venv) ..."
"${VENV_PIP}" install -q -r "${ROOT}/requirements.txt"

# 3. venv Python으로 실행 (모듈로 실행해 src import 보장)
# UART 실기기 사용 시 UART_ENABLED=1 (기본 활성화)
export UART_ENABLED=1
echo "[run_gateway] Starting gateway ..."
exec "${VENV_PY}" -m src.main "$@"
