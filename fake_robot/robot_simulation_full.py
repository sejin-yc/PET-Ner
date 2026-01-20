import asyncio
import json
import logging
import time
import cv2
import numpy as np
import random
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from av import VideoFrame

# --- 설정 ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# React(Stomp)와 채널 맞추기 (이 부분 아주 잘 작성하셨습니다!)
TOPIC_DATA = "/sub/robot/status"       # Python -> React (상태 전송)
TOPIC_CONTROL = "/pub/robot/control"   # React -> Python (조종 명령)
TOPIC_OFFER = "/sub/peer/offer"        # Python -> React (영상 제안)
TOPIC_ANSWER = "/pub/peer/answer"      # React -> Python (영상 수락)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotSim")

# --- 전역 변수 ---
current_linear = 0.0
current_angular = 0.0
robot_x = 50.0  
robot_y = 50.0
battery = 100.0
is_webrtc_connected = False # 🚨 연결 상태 확인용 변수 추가
loop = None

# --- 1. 가짜 비디오 트랙 ---
class BouncingBallTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.width = 640
        self.height = 480
        self.ball_x = 320
        self.ball_y = 240
        self.dx = 4
        self.dy = 4

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        self.ball_x += self.dx
        self.ball_y += self.dy
        if self.ball_x <= 0 or self.ball_x >= self.width: self.dx *= -1
        if self.ball_y <= 0 or self.ball_y >= self.height: self.dy *= -1
        
        cv2.circle(frame, (int(self.ball_x), int(self.ball_y)), 20, (0, 255, 0), -1)
        
        # 현재 속도 표시
        status_text = f"Spd: {current_linear:.1f} | Ang: {current_angular:.1f}"
        cv2.putText(frame, status_text, (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

# --- 2. MQTT 설정 ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_message(client, userdata, msg):
    global current_linear, current_angular
    try:
        if msg.topic == TOPIC_CONTROL:
            payload = json.loads(msg.payload.decode())
            cmd_type = payload.get("type")
            
            if cmd_type == "MOVE":
                current_linear = payload.get("linear", 0.0)
                current_angular = payload.get("angular", 0.0)
                logger.info(f"🕹️ 명령 수신: 선속도={current_linear}, 각속도={current_angular}")
            elif cmd_type == "STOP":
                current_linear = 0.0
                current_angular = 0.0
                logger.info("🛑 비상 정지!")
                
    except Exception as e:
        logger.error(f"메시지 처리 에러: {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("✅ MQTT 연결 성공!")
        client.subscribe(TOPIC_ANSWER)  
        client.subscribe(TOPIC_CONTROL) 
    else:
        logger.info(f"❌ MQTT 연결 실패: {rc}")

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# --- 3. WebRTC (핵심 수정됨: 재시도 로직 추가) ---
async def run_webrtc():
    global is_webrtc_connected
    
    # STUN 서버 설정 (필수)
    config = RTCConfiguration(iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ])
    pc = RTCPeerConnection(configuration=config)
    pc.addTrack(BouncingBallTrack())

    # Answer를 받을 큐 생성
    answer_queue = asyncio.Queue()

    def answer_handler(c, u, msg):
        if msg.topic == TOPIC_ANSWER:
            try:
                payload = json.loads(msg.payload.decode())
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(answer_queue.put(payload), loop)
            except Exception as e:
                logger.error(f"Answer 파싱 에러: {e}")

    client.message_callback_add(TOPIC_ANSWER, answer_handler)

    # 🚨 [수정됨] 연결될 때까지 Offer를 반복해서 보냄
    # React 페이지가 늦게 켜져도 연결되게 하기 위함
    logger.info("📡 WebRTC 연결 대기 중... (Offer 전송 시작)")
    
    while not is_webrtc_connected:
        try:
            # 매번 새로운 Offer 생성하지 않고, 같은 Offer를 재전송해도 됨
            # 하지만 안전하게 세션 갱신을 위해 체크
            if pc.signalingState == "stable" or pc.signalingState == "have-local-offer":
                 # Offer 생성 및 전송
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                
                offer_payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
                client.publish(TOPIC_OFFER, json.dumps(offer_payload))
                logger.info("... Offer 재전송 중 ...")

            # Answer가 오는지 3초 동안 기다림
            try:
                answer_data = await asyncio.wait_for(answer_queue.get(), timeout=3.0)
                
                # Answer 도착!
                logger.info("📩 Answer 수신됨! 연결 시도...")
                remote_desc = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
                await pc.setRemoteDescription(remote_desc)
                
                is_webrtc_connected = True
                logger.info("✅ WebRTC 영상 연결 성공! (초록 공이 튀어야 함)")
                
            except asyncio.TimeoutError:
                # 3초 동안 답장 없으면 루프 돌면서 재전송
                continue

        except Exception as e:
            logger.error(f"WebRTC 연결 시도 중 에러: {e}")
            await asyncio.sleep(1)

    # 연결된 후에는 계속 유지
    while True:
        await asyncio.sleep(1)
        # 혹시 연결 끊기면 다시 처리하는 로직을 넣을 수도 있음

# --- 4. 데이터 시뮬레이션 ---
async def run_data_simulation():
    global robot_x, robot_y, battery
    
    while True:
        # 키보드 입력(W/S/A/D)에 따른 이동
        # 좌표계: React Map에서 위쪽이 y가 작아지는 방향일 수 있으나
        # 여기서는 일반적인 2D 좌표계(위=y증가) or 화면좌표(위=y감소)에 따라 다름
        # 일단 React 코드에 맞춰서 동작 확인 필요
        robot_y -= current_linear * 0.5 
        robot_x -= current_angular * 0.5 
        
        robot_x = max(0, min(100, robot_x))
        robot_y = max(0, min(100, robot_y))

        drain = 0.01 if (current_linear == 0 and current_angular == 0) else 0.05
        battery = max(0, battery - drain)

        status_data = {
            "batteryLevel": int(battery),
            "temperature": 36.5,
            "isCharging": False,
            "x": round(robot_x, 2),
            "y": round(robot_y, 2),
            "mode": "manual"
        }
        client.publish(TOPIC_DATA, json.dumps(status_data))
        await asyncio.sleep(0.1) 

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.create_task(run_data_simulation())
        loop.create_task(run_webrtc())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()