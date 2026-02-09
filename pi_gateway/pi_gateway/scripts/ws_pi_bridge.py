#!/usr/bin/env python3
"""
Pi Gateway ↔ Backend WebSocket(STOMP) 브리지.

1883 막혀 있을 때 WebSocket(443)으로 상태·제어 연동.
- Pi 상태 → SEND /pub/robot/status → Backend → WebSocket → Frontend
- Frontend 제어 → Backend → SEND /sub/robot/{userId}/control → Pi SUBSCRIBE

환경 변수:
  PI_GATEWAY_URL   Pi base URL (기본: http://localhost:8000)
  BE_WS_URL        Backend WebSocket URL (기본: wss://i14c203.p.ssafy.io/ws)
  BE_USER_ID       userId (기본: 1)
  STATUS_INTERVAL  상태 전송 주기(초) (기본: 0.2)

실행:
  BE_WS_URL=wss://i14c203.p.ssafy.io/ws PI_GATEWAY_URL=http://localhost:8000 python3 scripts/ws_pi_bridge.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time

try:
    import requests
    import websocket
except ImportError as e:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("pi_gateway.ws_bridge").error("pip install requests websocket-client: %s", e)
    raise SystemExit(1) from e

log = logging.getLogger(__name__ if __name__ != "__main__" else "pi_gateway.ws_bridge")

# --- 설정 ---
PI_GATEWAY_URL = os.getenv("PI_GATEWAY_URL", "http://localhost:8000").rstrip("/")
BE_WS_URL = os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws").rstrip("/")
BE_USER_ID = int(os.getenv("BE_USER_ID", "1"))
STATUS_INTERVAL = float(os.getenv("STATUS_INTERVAL", "0.2"))


def _pi_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{PI_GATEWAY_URL}{path}", timeout=2.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _pi_post(path: str, body: dict) -> bool:
    try:
        r = requests.post(f"{PI_GATEWAY_URL}{path}", json=body, timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _control_send(obj: dict) -> bool:
    return _pi_post("/robot/control", obj)


def _on_control(payload: dict):
    t = payload.get("type")
    log.info("[WS] 제어 수신: type=%s payload=%s", t, payload)
    if t == "MOVE":
        linear = float(payload.get("linear") or 0.0)
        angular = float(payload.get("angular") or 0.0)
        ts = time.time()
        presses = [
            ("up", linear > 0),
            ("down", linear < 0),
            ("left", angular > 0),
            ("right", angular < 0),
            ("rot_l", False),
            ("rot_r", False),
        ]
        for key, down in presses:
            _control_send({"type": "press", "key": key, "down": down, "timestamp": ts})
    elif t == "STOP":
        ts = time.time()
        for key in ("up", "down", "left", "right", "rot_l", "rot_r"):
            _control_send({"type": "press", "key": key, "down": False, "timestamp": ts})
    elif t == "MODE":
        v = str(payload.get("value", "manual")).lower()
        mode = "teleop" if v == "manual" else "auto"
        _pi_post("/robot/mode", {"mode": mode})


def _build_status() -> dict:
    health = _pi_get("/robot/health")
    tele = _pi_get("/telemetry/latest")
    if health is None and tele is None:
        return {
            "status": {"vehicleStatus": {"batteryLevel": 0, "isCharging": False}, "module": {"status": "INACTIVE"}},
            "currentLocation": {"x": 0.0, "y": 0.0, "theta": 0.0},
        }
    health_data = (health or {}).get("data", {}) if isinstance(health, dict) else {}
    mode = health_data.get("mode", "teleop")
    mode = "auto" if mode == "auto" else "manual"
    batt = (tele or {}).get("battery") or {}
    odom = (tele or {}).get("odom") or {}
    amcl = (tele or {}).get("amcl_pose") or {}
    mode_str = "ACTIVE" if mode == "auto" else "INACTIVE"
    # 맵 좌표는 amcl_pose 우선 (SLAM 맵 기준), 없으면 odom
    pose_src = amcl if isinstance(amcl, dict) and amcl.get("x") is not None else odom
    loc_x = float(pose_src.get("x", 0.0)) if isinstance(pose_src, dict) else 0.0
    loc_y = float(pose_src.get("y", 0.0)) if isinstance(pose_src, dict) else 0.0
    theta = float(pose_src.get("yaw", 0.0)) if isinstance(pose_src, dict) else 0.0
    return {
        "status": {
            "vehicleStatus": {
                "batteryLevel": int(batt.get("soc_percent", 0)),
                "isCharging": bool(batt.get("charging", False)),
            },
            "module": {"status": mode_str},
        },
        "currentLocation": {"x": loc_x, "y": loc_y, "theta": theta},
    }


# --- STOMP 프레임 ---
def stomp_connect() -> str:
    return "CONNECT\naccept-version:1.2\nheart-beat:10000,10000\n\n\x00"


def stomp_send(dest: str, body: str) -> str:
    return f"SEND\ndestination:{dest}\ncontent-type:application/json\ncontent-length:{len(body)}\n\n{body}\x00"


def stomp_subscribe(dest: str, sub_id: str) -> str:
    return f"SUBSCRIBE\nid:{sub_id}\ndestination:{dest}\n\n\x00"


def stomp_disconnect() -> str:
    return "DISCONNECT\n\n\x00"


def parse_stomp_frame(data: str) -> tuple[str, dict, str]:
    """STOMP 프레임 파싱. (command, headers, body) 반환."""
    lines = data.split("\n")
    if not lines:
        return ("", {}, "")
    cmd = lines[0]
    headers = {}
    i = 1
    while i < len(lines) and lines[i]:
        m = re.match(r"([^:]+):(.*)", lines[i])
        if m:
            headers[m.group(1).lower()] = m.group(2).strip()
        i += 1
    i += 1  # blank line
    body = "\n".join(lines[i:]).rstrip("\x00") if i < len(lines) else ""
    return (cmd, headers, body)


class StompWsBridge:
    def __init__(self):
        self.ws: websocket.WebSocketApp | None = None
        self.connected = False
        self._lock = threading.Lock()
        self._buf = ""
        self._send_lock = threading.Lock()

    def _on_message(self, ws, message):
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")
        with self._lock:
            self._buf += message
        while "\x00" in self._buf:
            idx = self._buf.index("\x00")
            frame = self._buf[:idx]
            self._buf = self._buf[idx + 1 :]
            self._handle_frame(frame)

    def _handle_frame(self, frame: str):
        cmd, headers, body = parse_stomp_frame(frame)
        if cmd == "CONNECTED":
            self.connected = True
            log.info("STOMP 연결됨")
        elif cmd == "MESSAGE":
            dest = headers.get("destination", "")
            if "/control" in dest:
                try:
                    payload = json.loads(body)
                    _on_control(payload)
                except Exception as e:
                    log.warning("제어 메시지 파싱 실패: %s", e)

    def _on_error(self, ws, error):
        log.error("WebSocket 에러: %s", error)

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        log.warning("WebSocket 종료: %s %s", close_status_code, close_msg)

    def _on_open(self, ws):
        ws.send(stomp_connect(), opcode=websocket.ABNF.OPCODE_TEXT)

    def send(self, data: str):
        with self._send_lock:
            if self.ws and self.ws.sock and self.ws.sock.connected:
                self.ws.send(data, opcode=websocket.ABNF.OPCODE_TEXT)

    def run(self):
        log.info("Pi=%s BE_WS=%s userId=%s", PI_GATEWAY_URL, BE_WS_URL, BE_USER_ID)
        self.ws = websocket.WebSocketApp(
            BE_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )
        # CONNECTED 수신 후 SUBSCRIBE/SEND (약간 대기)
        def wait_and_subscribe():
            for _ in range(50):
                time.sleep(0.1)
                if self.connected:
                    break
            if self.connected:
                self.send(stomp_subscribe(f"/sub/robot/{BE_USER_ID}/control", "sub-control"))
                log.info("구독: /sub/robot/%s/control", BE_USER_ID)
            else:
                log.warning("CONNECTED 대기 시간 초과")

        threading.Thread(target=wait_and_subscribe, daemon=True).start()

        def status_loop():
            publish_count = 0
            while True:
                time.sleep(STATUS_INTERVAL)
                if not self.connected:
                    continue
                payload = _build_status()
                body = json.dumps({**payload, "userId": BE_USER_ID}, ensure_ascii=False)
                self.send(stomp_send("/pub/robot/status", body))
                publish_count += 1
                if publish_count % 10 == 0:
                    log.info("상태 전송 중... (횟수: %s)", publish_count)

        threading.Thread(target=status_loop, daemon=True).start()

        self.ws.run_forever()


def main():
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    bridge = StompWsBridge()
    try:
        bridge.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
