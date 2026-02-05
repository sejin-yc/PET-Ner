import os
import asyncio
import json
import logging
import cv2
import math
import numpy as np
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCIceCandidate
from av import VideoFrame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotSim")

env_mode = os.getenv("ROBOT_ENV", "local")

# --- [설정] 네트워크 및 토픽 ---
IS_LOCAL = (env_mode != "server")
MQTT_BROKER = "localhost"
if IS_LOCAL:
    MQTT_PORT = 1883
    logger.info(f"🔧 [모드] 로컬 개발 환경 (Port: {MQTT_PORT})")
else:
    MQTT_PORT = 9999
    logger.info(f"🔧 [모드] 서버 터널링 환경 (Port: {MQTT_PORT})")

TOPIC_DATA = "/sub/robot/status"       # 로봇 -> React (상태 정보)
TOPIC_CONTROL = "/pub/robot/control"   # React -> 로봇 (제어 명령)
TOPIC_OFFER = "/sub/peer/offer"        # 로봇 -> React (영상 연결 요청)
TOPIC_ANSWER = "/pub/peer/answer"      # React -> 로봇 (영상 연결 수락)
TOPIC_ICE = "/sub/peer/ice"            # 로봇 -> React (네트워크 후보군)
TOPIC_ICE_IN = "/pub/peer/ice"         # React -> 로봇 (네트워크 후보군)

# --- [전역 변수] 로봇 상태 ---
current_linear = 0.0
current_angular = 0.0
robot_x = 50.0  
robot_y = 50.0
battery = 100.0
current_mode = "manual"  # 초기 모드는 수동
loop = None
pc = None 

# --- 1. 가짜 비디오 트랙 (공 튀기기) ---
class BouncingBallTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.width = 640
        self.height = 480
        self.ball_x = 320
        self.ball_y = 240
        self.dx = 6
        self.dy = 6

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 공 이동
        self.ball_x += self.dx
        self.ball_y += self.dy
        if self.ball_x <= 20 or self.ball_x >= self.width-20: self.dx *= -1
        if self.ball_y <= 20 or self.ball_y >= self.height-20: self.dy *= -1
        
        # 그리기
        cv2.circle(frame, (int(self.ball_x), int(self.ball_y)), 20, (0, 255, 0), -1)
        
        # 정보 텍스트 표시
        status_text = f"MODE: {current_mode.upper()} | BAT: {int(battery)}%"
        cv2.putText(frame, "SSAFY ROBOT VIEW", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, status_text, (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

# --- 2. MQTT 핸들러 ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"✅ MQTT 연결 성공 (Port: {MQTT_PORT})")
        client.subscribe(TOPIC_CONTROL)
        client.subscribe(TOPIC_ANSWER)
        client.subscribe(TOPIC_ICE_IN)
    else:
        logger.error(f"❌ MQTT 연결 실패: {rc}")

def on_message(client, userdata, msg):
    global current_linear, current_angular, pc, current_mode
    try:
        payload = json.loads(msg.payload.decode())

        # 2-1. 로봇 제어 명령 수신
        if msg.topic == TOPIC_CONTROL:
            cmd_type = payload.get("type")
            
            # 이동 명령 (수동 모드일 때만 동작하도록 해도 됨)
            if cmd_type == "MOVE":
                current_linear = payload.get("linear", 0.0)
                current_angular = payload.get("angular", 0.0)
                
            # 정지 명령
            elif cmd_type == "STOP":
                current_linear = 0.0
                current_angular = 0.0
                
            # [중요] 모드 변경 명령 처리
            elif cmd_type == "MODE":
                new_mode = payload.get("value")
                logger.info(f"🔄 모드 변경 요청: {current_mode} -> {new_mode}")
                current_mode = new_mode

        # 2-2. WebRTC Answer 수신 (연결 수립)
        elif msg.topic == TOPIC_ANSWER:
            logger.info("📩 WebRTC Answer 수신됨!")
            if pc and loop:
                desc = RTCSessionDescription(sdp=payload["sdp"], type=payload["type"])
                asyncio.run_coroutine_threadsafe(pc.setRemoteDescription(desc), loop)

        # 2-3. ICE Candidate 수신
        elif msg.topic == TOPIC_ICE_IN:
            if pc and loop and payload:
                candidate = RTCIceCandidate(
                    candidate=payload["candidate"],
                    sdpMid=payload["sdpMid"],
                    sdpMLineIndex=payload["sdpMLineIndex"]
                )
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(candidate), loop)
                
    except Exception as e:
        logger.error(f"메시지 처리 에러: {e}")

client.username_pw_set("ssafy", "1")
client.on_connect = on_connect
client.on_message = on_message
# 터널링 포트로 접속
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# --- 3. WebRTC 메인 로직 ---
async def run_webrtc():
    global pc
    
    config = RTCConfiguration(iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ])

    while True:
        # 연결이 없거나 끊기면 재연결 시도
        if pc is None or pc.connectionState in ["closed", "failed"]:
            logger.info("🔄 WebRTC 연결 초기화...")
            pc = RTCPeerConnection(configuration=config)
            
            # 트랙 추가
            pc.addTrack(BouncingBallTrack())

            # Offer 생성
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Offer 전송 (MQTT)
            offer_payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
            client.publish(TOPIC_OFFER, json.dumps(offer_payload))
            logger.info("📡 Offer 전송함 (React 접속 대기 중...)")

        # 너무 자주 재시작하지 않도록 대기
        await asyncio.sleep(3.0)

# --- 4. 로봇 데이터 & 움직임 시뮬레이션 ---
async def run_data_simulation():
    global robot_x, robot_y, battery, current_mode, current_linear, current_angular
    tick = 0
    while True:
        # --- [자동 주행 로직] ---
        if current_mode == 'auto':
            # 자동 모드일 때는 스스로 속도를 조절
            tick += 0.1
            current_linear = 0.8  # 전진 속도
            current_angular = math.sin(tick) * 1.5 # 좌우로 흔들면서 전진
        
        # --- [물리 이동 계산] ---
        # React 지도 좌표계에 맞춰 이동 (X, Y 단순 이동)
        robot_y -= current_linear * 1.0 
        robot_x -= current_angular * 1.0 
        
        # 벽에 부딪히면 멈춤 (0 ~ 100 범위 제한)
        robot_x = max(0, min(100, robot_x))
        robot_y = max(0, min(100, robot_y))

        # 배터리 소모
        drain = 0.05 if (current_linear != 0 or current_angular != 0) else 0.00
        battery = max(0, battery - drain)

        # --- [데이터 전송] ---
        status_data = {
            "batteryLevel": int(battery),
            "temperature": float(np.random.normal(36.5, 0.5)),
            "charging": False,
            "x": round(robot_x, 2),
            "y": round(robot_y, 2),
            "mode": current_mode  # ✅ 현재 모드를 정확히 보고함
        }
        client.publish(TOPIC_DATA, json.dumps(status_data))
        
        # 0.1초마다 상태 업데이트
        await asyncio.sleep(0.1)

# --- 메인 실행 ---
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        logger.info("🚀 로봇 시뮬레이터 시작")
        loop.create_task(run_data_simulation())
        loop.create_task(run_webrtc())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if pc:
            loop.run_until_complete(pc.close())
        client.loop_stop()
        logger.info("👋 시뮬레이터 종료")