import asyncio
import json
import logging
import time
import cv2
import numpy as np
import random
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaRelay
from av import VideoFrame

# --- 설정 ---
MQTT_BROKER = "i14c203.p.ssafy.io"
MQTT_PORT = 1883

TOPIC_DATA = "/sub/robot/status"       # 보낼 데이터 (상태)
TOPIC_CONTROL = "/pub/robot/control"   # 받을 데이터 (명령) ✅ 추가됨
TOPIC_OFFER = "/sub/peer/offer"
TOPIC_ANSWER = "/pub/peer/answer"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotSim")

# --- 전역 변수 (로봇 상태) ---
current_linear = 0.0
current_angular = 0.0
robot_x = 50.0  # 중앙 시작
robot_y = 50.0
battery = 100.0

# --- 1. 가짜 비디오 트랙 (동일) ---
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

# ✅ 명령 수신 콜백 함수
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
        client.subscribe(TOPIC_ANSWER)  # WebRTC Answer
        client.subscribe(TOPIC_CONTROL) # ✅ 제어 명령 구독
    else:
        logger.info(f"❌ MQTT 연결 실패: {rc}")

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# --- 3. WebRTC (동일) ---
async def run_webrtc():
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    pc.addTrack(BouncingBallTrack())

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    offer_payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    client.publish(TOPIC_OFFER, json.dumps(offer_payload))
    
    answer_queue = asyncio.Queue()
    def answer_handler(c, u, msg):
        if msg.topic == TOPIC_ANSWER:
            payload = json.loads(msg.payload.decode())
            asyncio.run_coroutine_threadsafe(answer_queue.put(payload), loop)

    client.message_callback_add(TOPIC_ANSWER, answer_handler)

    try:
        answer_data = await answer_queue.get()
        remote_desc = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
        await pc.setRemoteDescription(remote_desc)
        logger.info("✅ WebRTC 영상 연결됨!")
        while True: await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebRTC 에러: {e}")
    finally:
        await pc.close()

# --- 4. 데이터 시뮬레이션 (수정됨: 명령에 따라 움직임) ---
async def run_data_simulation():
    global robot_x, robot_y, battery
    
    while True:
        # ✅ 랜덤 이동 삭제 -> 명령 받은 속도(current_linear/angular)대로 이동
        # 시뮬레이션 상: Linear(위아래), Angular(좌우)로 매핑 (간소화)
        robot_y -= current_linear * 0.5  # W 누르면 위로 (Y값 감소가 위쪽)
        robot_x -= current_angular * 0.5 # D 누르면 오른쪽
        
        # 맵 밖으로 안 나가게 제한 (0~100)
        robot_x = max(0, min(100, robot_x))
        robot_y = max(0, min(100, robot_y))

        # 움직이면 배터리 더 빨리 닳음
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
        await asyncio.sleep(0.1) # 0.1초마다 갱신 (부드러운 움직임)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(run_data_simulation())
        loop.create_task(run_webrtc())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()