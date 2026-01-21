import asyncio
import json
import logging
import cv2
import numpy as np
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCIceCandidate
from av import VideoFrame

# --- 설정 ---
MQTT_BROKER = "localhost" # 🚨 AWS 배포 시엔 "i14c203.p.ssafy.io" (외부 주소) 사용!
MQTT_PORT = 1883

TOPIC_DATA = "/sub/robot/status"
TOPIC_CONTROL = "/pub/robot/control"
TOPIC_OFFER = "/sub/peer/offer"
TOPIC_ANSWER = "/pub/peer/answer"
TOPIC_ICE = "/sub/peer/ice"     # 📤 Python -> React (내 경로 보냄)
TOPIC_ICE_IN = "/pub/peer/ice"  # 📥 React -> Python (상대 경로 받음)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotSim")

current_linear = 0.0
current_angular = 0.0
robot_x = 50.0  
robot_y = 50.0
battery = 100.0
loop = None
pc = None # 전역 PC 객체

# --- 1. 가짜 비디오 트랙 ---
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
        
        self.ball_x += self.dx
        self.ball_y += self.dy
        if self.ball_x <= 20 or self.ball_x >= self.width-20: self.dx *= -1
        if self.ball_y <= 20 or self.ball_y >= self.height-20: self.dy *= -1
        
        cv2.circle(frame, (int(self.ball_x), int(self.ball_y)), 20, (0, 255, 0), -1)
        
        # 상태 표시
        cv2.putText(frame, "LIVE SIMULATION", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, f"SPD: {current_linear:.1f} | ANG: {current_angular:.1f}", (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

# --- 2. MQTT 핸들러 ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("✅ MQTT 연결 성공")
        client.subscribe(TOPIC_CONTROL)
        client.subscribe(TOPIC_ANSWER)
        client.subscribe(TOPIC_ICE_IN)
    else:
        logger.error(f"❌ MQTT 연결 실패: {rc}")

def on_message(client, userdata, msg):
    global current_linear, current_angular, pc
    try:
        payload = json.loads(msg.payload.decode())

        # 1. 로봇 제어 명령
        if msg.topic == TOPIC_CONTROL:
            cmd_type = payload.get("type")
            if cmd_type == "MOVE":
                current_linear = payload.get("linear", 0.0)
                current_angular = payload.get("angular", 0.0)
            elif cmd_type == "STOP":
                current_linear = 0.0
                current_angular = 0.0

        # 2. WebRTC Answer 수신
        elif msg.topic == TOPIC_ANSWER:
            logger.info("📩 Answer 수신됨!")
            if pc and loop:
                desc = RTCSessionDescription(sdp=payload["sdp"], type=payload["type"])
                asyncio.run_coroutine_threadsafe(pc.setRemoteDescription(desc), loop)

        # 3. WebRTC ICE Candidate 수신 (React -> Python)
        elif msg.topic == TOPIC_ICE_IN:
            if pc and loop and payload:
                # aiortc 용 Candidate 객체로 변환
                candidate = RTCIceCandidate(
                    candidate=payload["candidate"],
                    sdpMid=payload["sdpMid"],
                    sdpMLineIndex=payload["sdpMLineIndex"]
                )
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(candidate), loop)
                
    except Exception as e:
        logger.error(f"메시지 처리 에러: {e}")

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# --- 3. WebRTC 메인 로직 ---
async def run_webrtc():
    global pc
    
    config = RTCConfiguration(iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302")
    ])

    while True:
        # 연결이 없거나 닫혀있으면 새로 생성
        if pc is None or pc.connectionState in ["closed", "failed"]:
            logger.info("🔄 WebRTC 연결 초기화...")
            pc = RTCPeerConnection(configuration=config)
            pc.addTrack(BouncingBallTrack())

            # 3-1. ICE Candidate 찾으면 전송 (Python -> React)
            # aiortc는 'onicecandidate' 이벤트가 없어서 트릭이 필요하지만,
            # 일단 Offer/Answer 과정에서 자동으로 수집된 것을 사용합니다.
            
            # 3-2. Offer 생성 및 전송
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            offer_payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
            client.publish(TOPIC_OFFER, json.dumps(offer_payload))
            logger.info("📡 Offer 전송함 (대기 중...)")

        # 연결 상태 확인하며 대기
        await asyncio.sleep(2.0)

# --- 4. 로봇 데이터 시뮬레이션 ---
async def run_data_simulation():
    global robot_x, robot_y, battery
    
    while True:
        # React 지도에 맞게 좌표 이동 (속도 조절)
        robot_y -= current_linear * 1.0 
        robot_x -= current_angular * 1.0 
        
        robot_x = max(0, min(100, robot_x))
        robot_y = max(0, min(100, robot_y))

        drain = 0.05 if (current_linear != 0 or current_angular != 0) else 0.01
        battery = max(0, battery - drain)

        status_data = {
            "batteryLevel": int(battery),
            "temperature": float(np.random.normal(36.5, 0.5)),
            "charging": False, # 필드명 주의 (isCharging -> charging)
            "x": round(robot_x, 2),
            "y": round(robot_y, 2),
            "mode": "manual"
        }
        client.publish(TOPIC_DATA, json.dumps(status_data))
        await asyncio.sleep(0.1)

# --- 메인 실행 ---
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
        if pc:
            loop.run_until_complete(pc.close())
        client.loop_stop()