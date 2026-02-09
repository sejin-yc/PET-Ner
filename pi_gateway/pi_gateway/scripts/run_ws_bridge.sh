#!/bin/bash
# Pi Gateway ↔ Backend WebSocket(STOMP) 브리지
# 1883 막혀 있을 때 WebSocket(443)으로 연동
#
# 사용: ./scripts/run_ws_bridge.sh
#
# SSAFY: BE_WS_URL=wss://i14c203.p.ssafy.io/ws PI_GATEWAY_URL=http://localhost:8000 ./scripts/run_ws_bridge.sh
#
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export PI_GATEWAY_URL="${PI_GATEWAY_URL:-http://localhost:8000}"
export BE_WS_URL="${BE_WS_URL:-wss://i14c203.p.ssafy.io/ws}"
python3 scripts/ws_pi_bridge.py
