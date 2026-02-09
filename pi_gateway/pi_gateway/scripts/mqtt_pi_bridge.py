#!/usr/bin/env python3
"""
MQTT ↔ Pi Gateway 브리지 (별도 스크립트).

FE/BE가 사용하는 MQTT /pub/robot/control, /sub/robot/status 와
Pi Gateway(HTTP + /ws/teleop) 사이를 이어준다.

- MQTT /pub/robot/control 구독:
  - MOVE { linear, angular } → Pi /ws/teleop (type: press; up/down/rot_l/rot_r)
  - STOP → press 전부 해제
  - MODE { value: "manual"|"auto" } → Pi POST /control/mode

- Pi /health, /telemetry/latest 주기 수집 → MQTT /sub/robot/status 발행

환경 변수:
  PI_GATEWAY_URL   Pi base URL (기본: http://localhost:8000)
  MQTT_HOST        MQTT 브로커 호스트 (기본: localhost)
  MQTT_PORT        MQTT 브로커 포트 (기본: WSS 시 9000, 비WSS 시 1883)
  MQTT_USE_WSS     1 이면 MQTT over WebSocket Secure, 포트 9000 사용 (기본: 1)
  MQTT_WS_PATH     WebSocket 경로 (기본: /mqtt, 브로커에 따라 /ws 등)
  MQTT_USERNAME    MQTT 브로커 사용자명 (선택)
  MQTT_PASSWORD    MQTT 브로커 비밀번호 (선택)
  STATUS_INTERVAL  상태 발행 주기(초) (기본: 0.2)
  MQTT_DEBUG       1 이면 발행 payload 로그 출력 (기본: 0)

  # HTTP 모드 (기본: 1. MQTT 쓰려면 BE_USE_HTTP=0)
  BE_USE_HTTP      1 이면 HTTP API, 0 이면 MQTT (기본: 1)
  BE_SERVER_URL    백엔드 서버 URL (기본: https://i14c203.p.ssafy.io)
  BE_USER_ID       userId (기본: 1)
  CONTROL_POLL_INTERVAL  제어 폴링 주기(초) (기본: 0.1)

실행 (프로젝트 루트에서):
  python3 scripts/mqtt_pi_bridge.py

  # MQTT over WSS (기본: 포트 9000)
  BE_USE_HTTP=0 MQTT_HOST=broker.example.com python3 scripts/mqtt_pi_bridge.py

  # MQTT WSS + 자체 서명 인증서 (검증 생략)
  BE_USE_HTTP=0 MQTT_HOST=... MQTT_TLS_INSECURE=1 python3 scripts/mqtt_pi_bridge.py

  # HTTP 모드 (기본)
  BE_SERVER_URL=https://i14c203.p.ssafy.io python3 scripts/mqtt_pi_bridge.py

  # MQTT 일반 TCP (1883)
  BE_USE_HTTP=0 MQTT_USE_WSS=0 MQTT_PORT=1883 MQTT_HOST=... python3 scripts/mqtt_pi_bridge.py
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import threading
import time

try:
    import paho.mqtt.client as mqtt
    import requests
    import websocket
except ImportError as e:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("pi_gateway.mqtt_bridge").error(
        "pip install paho-mqtt requests websocket-client: %s", e
    )
    raise SystemExit(1) from e

log = logging.getLogger(__name__ if __name__ != "__main__" else "pi_gateway.mqtt_bridge")

# --- 설정 ---
PI_GATEWAY_URL = os.getenv("PI_GATEWAY_URL", "http://localhost:8000").rstrip("/")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_USE_WSS = os.getenv("MQTT_USE_WSS", "1").strip().lower() in ("1", "true", "yes")
# WSS 기본 포트 9000, 일반 MQTT 기본 1883
MQTT_PORT = int(os.getenv("MQTT_PORT", "9000" if MQTT_USE_WSS else "1883"))
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt")  # WebSocket 경로 (기본: /mqtt)
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
STATUS_INTERVAL = float(os.getenv("STATUS_INTERVAL", "0.2"))
MQTT_DEBUG = os.getenv("MQTT_DEBUG", "0").strip() in ("1", "true", "yes")

# HTTP 모드 (기본: True. 1883 막힌 Lightsail 대응. MQTT 쓰려면 BE_USE_HTTP=0)
BE_USE_HTTP = os.getenv("BE_USE_HTTP", "1").strip() in ("1", "true", "yes")
BE_SERVER_URL = os.getenv("BE_SERVER_URL", "https://i14c203.p.ssafy.io").rstrip("/")
BE_USER_ID = int(os.getenv("BE_USER_ID", "1"))
CONTROL_POLL_INTERVAL = float(os.getenv("CONTROL_POLL_INTERVAL", "0.1"))

TOPIC_CONTROL = "/pub/robot/control"
TOPIC_STATUS = "/sub/robot/status"
TOPIC_JOBS = "/sub/robot/jobs"  # 작업 이벤트 토픽

# http를 ws로 변환
WS_BASE = PI_GATEWAY_URL.replace("https://", "wss://").replace("http://", "ws://")
WS_TELEOP = f"{WS_BASE}/ws/teleop"


# --- Pi Gateway 연동 ---
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


# --- 제어 전송 (HTTP POST /robot/control 사용, WebSocket 404 회피) ---
def _control_send(obj: dict) -> bool:
    """제어 명령을 Pi Gateway에 HTTP로 전송."""
    return _pi_post("/robot/control", obj)


# --- MQTT /pub/robot/control → Pi ---
def _on_control(payload: dict):
    """제어 명령 적용. payload: MQTT 또는 HTTP에서 온 dict."""
    t = payload.get("type")
    log.info("[MQTT] 제어 수신: type=%s payload=%s", t, payload)
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


# --- Pi → MQTT /sub/robot/status ---
def _build_status() -> dict:
    health = _pi_get("/robot/health")
    tele = _pi_get("/telemetry/latest")
    if health is None and tele is None:
        return {
            "status": {
                "vehicleStatus": {
                    "batteryLevel": 0,
                    "isCharging": False,
                },
                "module": {"status": "INACTIVE"},
            },
            "currentLocation": {"x": 0.0, "y": 0.0},
        }
    # health 응답 형식: {"resultCode": "SUCCESS", "message": "...", "data": {...}}
    health_data = (health or {}).get("data", {}) if isinstance(health, dict) else {}
    mode = health_data.get("mode", "teleop")
    if mode == "teleop":
        mode = "manual"
    elif mode == "auto":
        mode = "auto"
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
            "module": {
                "status": mode_str
            }
        },
        "currentLocation": {
            "x": loc_x,
            "y": loc_y,
            "theta": theta
        }
    }


# --- HTTP 모드 (BE_USE_HTTP=1) ---
def _be_post_status(payload: dict) -> bool:
    """백엔드 POST /api/robot/status 로 상태 전송."""
    body = {**payload, "userId": BE_USER_ID}
    try:
        r = requests.post(f"{BE_SERVER_URL}/api/robot/status", json=body, timeout=3.0)
        return r.status_code in (200, 201)
    except Exception as e:
        log.debug("BE POST status 실패: %s", e)
        return False


def _be_poll_control() -> dict | None:
    """백엔드 GET /api/robot/control 로 제어 명령 폴링. 없으면 None."""
    try:
        r = requests.get(
            f"{BE_SERVER_URL}/api/robot/control",
            params={"userId": BE_USER_ID},
            timeout=2.0,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _http_status_loop():
    """HTTP 모드: 상태 POST 루프."""
    publish_count = 0
    last_error_time = 0.0
    while True:
        time.sleep(STATUS_INTERVAL)
        payload = _build_status()
        ok = _be_post_status(payload)
        if ok:
            publish_count += 1
            if publish_count % 10 == 0:
                log.info("상태 전송 중... (횟수: %s)", publish_count)
            if MQTT_DEBUG and publish_count % 25 == 0:
                log.info("[HTTP] POST status payload: %s", json.dumps({**payload, "userId": BE_USER_ID}, ensure_ascii=False))
        else:
            if time.time() - last_error_time > 5.0:
                log.warning("BE POST status 실패")
                last_error_time = time.time()


def _http_control_loop():
    """HTTP 모드: 제어 폴링 루프."""
    while True:
        time.sleep(CONTROL_POLL_INTERVAL)
        cmd = _be_poll_control()
        if cmd and cmd.get("type"):
            log.info("[HTTP] 제어 수신: type=%s payload=%s", cmd.get("type"), cmd)
            _on_control(cmd)


def _run_http_mode() -> int:
    """HTTP 모드 실행 (상태 POST + 제어 폴링)."""
    log.info("HTTP 모드: Pi=%s BE=%s userId=%s", PI_GATEWAY_URL, BE_SERVER_URL, BE_USER_ID)
    th_status = threading.Thread(target=_http_status_loop, daemon=True)
    th_control = threading.Thread(target=_http_control_loop, daemon=True)
    th_status.start()
    th_control.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    return 0


def _status_loop(mqttc: mqtt.Client):
    """상태 발행 루프. 주기적으로 /sub/robot/status 토픽에 발행."""
    publish_count = 0
    last_error_time = 0.0
    last_jobs_check = 0.0
    last_job_id = 0  # 마지막으로 전송한 작업 ID
    last_reconnect_attempt = 0.0
    
    while True:
        time.sleep(STATUS_INTERVAL)
        payload = _build_status()
        try:
            # 연결 상태 확인
            if not mqttc.is_connected():
                # 재연결 시도 (5초마다)
                now = time.time()
                if now - last_reconnect_attempt >= 5.0:
                    log.warning("MQTT 연결 끊김 감지, 재연결 시도...")
                    try:
                        mqttc.reconnect()
                        last_reconnect_attempt = now
                    except Exception as e:
                        log.debug("재연결 실패: %s", e)
                        last_reconnect_attempt = now
                continue  # 연결될 때까지 발행 스킵
            
            result = mqttc.publish(TOPIC_STATUS, json.dumps(payload), qos=0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                publish_count += 1
                if publish_count % 10 == 0:
                    log.info("상태 발행 중... (발행 횟수: %s)", publish_count)
            else:
                if time.time() - last_error_time > 5.0:
                    log.warning("상태 발행 실패: rc=%s (연결 상태: %s)", result.rc, "연결됨" if mqttc.is_connected() else "끊김")
                    last_error_time = time.time()
        except Exception as e:
            if time.time() - last_error_time > 5.0:
                log.warning("상태 발행 예외: %s", e)
                last_error_time = time.time()
        
        # 작업 이벤트 주기적 수집 및 전송 (1초마다) - 폴링 방식
        # 참고: Pi Gateway에서 직접 BE로 HTTP POST하는 방식도 가능 (더 실시간)
        now = time.time()
        if now - last_jobs_check >= 1.0:
            last_jobs_check = now
            try:
                jobs_data = _pi_get("/robot/jobs")
                if jobs_data and jobs_data.get("resultCode") == "SUCCESS":
                    jobs = jobs_data.get("data", {}).get("jobs", [])
                    # 새로운 작업만 전송
                    for job in jobs:
                        job_id = job.get("jobId", 0)
                        if job_id > last_job_id:
                            try:
                                result = mqttc.publish(TOPIC_JOBS, json.dumps(job), qos=0)
                                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                                    last_job_id = max(last_job_id, job_id)
                            except Exception as e:
                                pass  # 조용히 실패
            except Exception:
                pass  # 조용히 실패


# --- MQTT ---
def on_connect(client, userdata, flags, *args):
    reason_code = args[0] if args else 0
    if reason_code != 0:
        log.warning("연결 실패: reason_code=%s (%s)", reason_code, _get_reason_code_name(reason_code))
        return
    log.info("연결 성공, 토픽 구독: %s", TOPIC_CONTROL)
    client.subscribe(TOPIC_CONTROL)


def _get_reason_code_name(code) -> str:
    """MQTT 연결 실패 원인 코드 설명. paho-mqtt v2는 ReasonCode 객체를 넘길 수 있음."""
    codes = {
        1: "잘못된 프로토콜 버전",
        2: "클라이언트 ID 거부",
        3: "서버 사용 불가",
        4: "잘못된 사용자명/비밀번호",
        5: "인증 실패",
    }
    try:
        val = int(getattr(code, "value", code))
    except (TypeError, ValueError):
        return f"알 수 없는 오류 (코드: {code})"
    return codes.get(val, f"알 수 없는 오류 (코드: {val})")


def on_disconnect(client, userdata, rc, *args):
    """MQTT 연결 끊김 콜백."""
    if rc != 0:
        log.warning("MQTT 연결 끊김: rc=%s (자동 재연결 시도 중...)", rc)
    else:
        log.info("MQTT 연결 정상 종료")


def on_message(client, userdata, msg):
    if msg.topic == TOPIC_CONTROL:
        try:
            payload = json.loads(msg.payload.decode()) if isinstance(msg.payload, bytes) else msg.payload
        except Exception:
            return
        _on_control(payload)


def main():
    # 스크립트 단독 실행 시 로깅 설정 (src.log_config와 동일 포맷)
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if BE_USE_HTTP:
        return _run_http_mode()

    # 포트 기반 자동 감지: 포트 9000/8080 등은 WebSocket, 1883은 TCP
    # 단, MQTT_USE_WSS 환경변수로 명시적으로 제어 가능
    # 포트 9000에서 TCP도 지원하는 브로커가 있을 수 있으므로, 기본값은 MQTT_USE_WSS 설정 따름
    use_websocket = MQTT_USE_WSS
    # 포트가 명확히 WebSocket 포트이고 MQTT_USE_WSS가 명시되지 않았을 때만 자동 감지
    if MQTT_PORT in (9000, 8080, 8083, 8084) and os.getenv("MQTT_USE_WSS") is None:
        use_websocket = True
        log.info("포트 %s 감지: WebSocket transport 자동 사용", MQTT_PORT)
    transport = "websockets" if use_websocket else "tcp"
    transport_name = "WSS" if MQTT_USE_WSS else ("WS" if use_websocket else "TCP")
    log.info("Pi=%s MQTT=%s:%s (%s) WS=%s", PI_GATEWAY_URL, MQTT_HOST, MQTT_PORT, transport_name, WS_TELEOP)

    try:
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport=transport)
    except (TypeError, ValueError):
        # 구버전 paho: transport만 넘기거나 기본 Client
        mqttc = mqtt.Client(transport=transport) if transport == "websockets" else mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_message = on_message

    if use_websocket:
        # WebSocket 경로 설정 (일부 브로커는 /mqtt, /ws 등 필요)
        try:
            mqttc.ws_set_options(path=MQTT_WS_PATH)
            log.info("WebSocket 경로 설정: %s", MQTT_WS_PATH)
        except AttributeError:
            # 구버전 paho-mqtt는 ws_set_options 미지원
            log.warning("ws_set_options 미지원 (구버전 paho-mqtt), 경로=%s 무시됨", MQTT_WS_PATH)
        
        # WSS: TLS 설정 (MQTT_USE_WSS=1일 때만)
        if MQTT_USE_WSS:
            tls_insecure = os.getenv("MQTT_TLS_INSECURE", "0").strip().lower() in ("1", "true", "yes")
            if tls_insecure:
                mqttc.tls_set(cert_reqs=ssl.CERT_NONE)
                mqttc.tls_insecure_set(True)
            else:
                mqttc.tls_set()

    if MQTT_USERNAME and MQTT_PASSWORD:
        mqttc.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        log.info("인증 정보 설정: username=%s", MQTT_USERNAME)

    try:
        log.info("연결 시도: %s:%s (%s, path=%s)", MQTT_HOST, MQTT_PORT, transport_name, MQTT_WS_PATH if use_websocket else "N/A")
        mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
        # 자동 재연결 활성화
        mqttc.reconnect_delay_set(min_delay=1, max_delay=120)
    except Exception as e:
        log.error("connect 실패: %s (HOST=%s PORT=%s USERNAME=%s)", e, MQTT_HOST, MQTT_PORT, "설정됨" if MQTT_USERNAME else "없음")
        return 1

    # WS drain 스레드 (선택: 보내기만 하고 recv 안 해도 동작하지만, 파이프 비우려고)
    # drain = threading.Thread(target=_ws_drain_thread, daemon=True)
    # drain.start()

    # 상태 발행 스레드
    th = threading.Thread(target=_status_loop, args=(mqttc,), daemon=True)
    th.start()

    mqttc.loop_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
