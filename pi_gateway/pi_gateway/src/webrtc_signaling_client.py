"""
WebRTC 시그널링 서버 클라이언트.
프론트엔드가 버튼을 누르면 시그널링 서버에 스트리밍 시작 요청을 보내고,
Pi Gateway가 이를 받아서 robot_webrtc.py를 시작합니다.

프론트엔드가 버튼을 누르면:
1. 시그널링 서버의 /pub/robot/stream/start 토픽에 메시지 전송
2. 이 클라이언트가 메시지를 받으면 robot_webrtc.py를 시작
3. robot_webrtc.py가 Offer를 발행하면 프론트엔드가 Answer를 보내서 연결 완료
"""

import json
import logging
import os
import ssl
import subprocess
import sys
import threading
import time

try:
    import websocket
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).error("websocket-client 없음. pip install websocket-client")
    websocket = None

log = logging.getLogger(__name__)

# 설정
SIGNALING_SERVER_URL = os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws")
ROBOT_ID = os.getenv("ROBOT_ID", "1")
CAMERA_TOPIC = os.getenv("CAMERA_TOPIC", "/front_cam/compressed")

_webrtc_process = None
_webrtc_lock = threading.Lock()


def start_webrtc_streaming():
    """WebRTC 스트리밍 프로세스 시작."""
    global _webrtc_process
    
    with _webrtc_lock:
        if _webrtc_process is not None:
            try:
                if _webrtc_process.poll() is None:  # 실행 중이면
                    log.info("WebRTC 스트리밍이 이미 실행 중입니다")
                    return
            except Exception:
                pass
        
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "..", "scripts", "robot_webrtc.py"
            )
            
            # 환경 변수 설정
            env = os.environ.copy()
            env["BE_WS_URL"] = SIGNALING_SERVER_URL
            env["CAMERA_TOPIC"] = CAMERA_TOPIC
            env["ROBOT_ID"] = ROBOT_ID
            
            # ROS2 환경 설정
            if "ROS_DISTRO" not in env:
                env["ROS_DISTRO"] = "humble"
            
            # 프로세스 시작
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            _webrtc_process = process
            log.info("WebRTC 스트리밍 시작됨 (PID: %s)", process.pid)
        except Exception as e:
            log.error("WebRTC 스트리밍 시작 실패: %s", e, exc_info=True)


def stop_webrtc_streaming():
    """WebRTC 스트리밍 프로세스 중지."""
    global _webrtc_process
    
    with _webrtc_lock:
        if _webrtc_process is None:
            return
        
        try:
            if _webrtc_process.poll() is None:  # 프로세스가 실행 중이면
                _webrtc_process.terminate()
                try:
                    _webrtc_process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    _webrtc_process.kill()
                    _webrtc_process.wait()
                log.info("WebRTC 스트리밍 중지됨")
        except Exception as e:
            log.error("WebRTC 스트리밍 중지 실패: %s", e)
        finally:
            _webrtc_process = None


def parse_stomp_message(msg: str):
    """STOMP 메시지 파싱."""
    lines = msg.split("\n")
    command = lines[0] if lines else ""
    
    # 본문 찾기
    body_start = msg.find("\n\n")
    if body_start == -1:
        return command, None, None
    
    headers_str = msg[:body_start]
    body = msg[body_start + 2:].replace("\x00", "").strip()
    
    # 헤더 파싱
    headers = {}
    for line in headers_str.split("\n")[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    
    return command, headers, body


def on_message(ws, message):
    """시그널링 서버 메시지 수신."""
    try:
        command, headers, body = parse_stomp_message(message)
        
        if command == "CONNECTED":
            log.info("시그널링 서버 연결됨")
            # 스트리밍 시작 요청 토픽 구독
            subscribe_frame = "SUBSCRIBE\nid:sub-stream-start\ndestination:/sub/robot/stream/start\n\n\x00"
            ws.send(subscribe_frame)
            log.info("스트리밍 시작 요청 토픽 구독 시작 (/sub/robot/stream/start)")
            return
        
        if command == "MESSAGE":
            destination = headers.get("destination", "")
            
            # 스트리밍 시작 요청 수신
            if destination == "/sub/robot/stream/start":
                log.info("스트리밍 시작 요청 수신 - robot_webrtc.py 시작")
                start_webrtc_streaming()
                return
    
    except Exception as e:
        log.error("메시지 처리 오류: %s", e, exc_info=True)


def on_error(ws, error):
    """WebSocket 에러 처리."""
    log.error("시그널링 서버 연결 오류: %s", error)


def on_close(ws, close_status_code, close_msg):
    """WebSocket 연결 종료."""
    log.info("시그널링 서버 연결 종료")
    # 재연결 시도
    time.sleep(3)
    start_signaling_client()


def on_open(ws):
    """WebSocket 연결 시작."""
    log.info("시그널링 서버 연결 시도 중...")
    # STOMP 연결 프레임 전송
    connect_frame = "CONNECT\naccept-version:1.1,1.0\n\n\x00"
    ws.send(connect_frame)


def start_signaling_client():
    """시그널링 서버 클라이언트 시작."""
    if websocket is None:
        log.error("websocket-client 모듈이 없습니다. pip install websocket-client")
        return
    
    try:
        ws = websocket.WebSocketApp(
            SIGNALING_SERVER_URL,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE} if SIGNALING_SERVER_URL.startswith("wss") else None)
    except Exception as e:
        log.error("시그널링 클라이언트 시작 실패: %s", e, exc_info=True)
        time.sleep(5)
        start_signaling_client()


def run_signaling_client():
    """시그널링 클라이언트를 별도 스레드에서 실행."""
    th = threading.Thread(target=start_signaling_client, daemon=True)
    th.start()
    return th
