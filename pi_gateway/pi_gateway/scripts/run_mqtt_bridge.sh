#!/bin/bash
# Pi Gateway ↔ 백엔드 브리지 실행 (MQTT 또는 HTTP 모드)
# 사용: ./scripts/run_mqtt_bridge.sh
#
# HTTP 모드 (기본, 1883 막힌 Lightsail 대응):
#   BE_SERVER_URL=https://i14c203.p.ssafy.io ./scripts/run_mqtt_bridge.sh
#
# MQTT 모드 (1883 열려 있을 때):
#   BE_USE_HTTP=0 MQTT_HOST=i14c203.p.ssafy.io MQTT_USERNAME=ssafy MQTT_PASSWORD=ssafy1 ./scripts/run_mqtt_bridge.sh
#   SSH 터널: MQTT_HOST=localhost MQTT_PORT=1884 BE_USE_HTTP=0 ...
#
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export PI_GATEWAY_URL="${PI_GATEWAY_URL:-http://localhost:8000}"
export MQTT_HOST="${MQTT_HOST:-localhost}"
python3 scripts/mqtt_pi_bridge.py
