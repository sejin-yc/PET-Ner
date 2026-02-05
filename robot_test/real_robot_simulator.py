import asyncio
import json
import logging
import cv2
import math
import numpy as np
import aiohttp 
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCIceCandidate
from av import VideoFrame

# --- [설정] 서버 주소 (포트 9999 설정) ---
# ✅ SSH 터널링을 통해 AWS의 8080포트를 로컬 9999로 연결했다고 가정
SERVER_URL = "localhost:9999" 

DATA_WS_URL = f"ws://{SERVER_URL}/ros2/vehicle/status"   # 로봇 데이터 전송용
SIGNAL_WS_URL = f"ws://{SERVER_URL}/signal"             # WebRTC 시그널링용

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RobotSim")

# --- [전역 변수] 로봇 상태 ---
robot_x = 37.7749  # 초기 위도
robot_y = -122.4194 # 초기 경도
battery = 100.0
current_mode = "manual"
pc = None 

# --- 1. 가짜 비디오 트랙 (공 튀기기 + 정보 표시) ---
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
        status_text = f"BAT: {int(battery)}% | MODE: {current_mode}"
        cv2.putText(frame, "SSAFY ROBOT VIEW (WebRTC)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, status_text, (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

# --- 2. 로봇 데이터 전송 (WebSocket) ---
async def run_data_simulation():
    global robot_x, robot_y, battery
    
    logger.info(f"📡 [DATA] 연결 시도: {DATA_WS_URL}")
    
    while True: # 연결 끊기면 재접속 시도 루프
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(DATA_WS_URL) as ws:
                    logger.info("✅ [DATA] 서버 연결 성공!")
                    
                    while True:
                        # 물리 이동 시뮬레이션
                        robot_x += np.random.uniform(-0.0001, 0.0001)
                        robot_y += np.random.uniform(-0.0001, 0.0001)
                        battery = max(0, battery - 0.05)

                        # 규격서 기반 JSON 생성
                        payload = {
                            "vehicleId": 101,
                            "rentId": 1001,
                            "isArrived": False,
                            "currentLocation": {"x": robot_x, "y": robot_y},
                            "autonomousArrivalPoint": {"x": 37.7755, "y": -122.4190},
                            "estimatedArrivalTime": "2026-01-26T12:00:00Z",
                            "status": {
                                "vehicleStatus": {
                                    "batteryLevel": int(battery),
                                    "lightIntensity": 80
                                },
                                "module": {
                                    "moduleId": 201,
                                    "moduleType": "CAMERA_MODULE",
                                    "status": "ACTIVE"
                                }
                            }
                        }

                        await ws.send_json(payload)
                        await asyncio.sleep(1.0) # 1초 주기 전송
        except Exception as e:
            logger.error(f"⚠️ [DATA] 연결 실패 (3초 후 재시도): {e}")
            await asyncio.sleep(3)

# --- 3. WebRTC 시그널링 (WebSocket) ---
async def run_webrtc_signaling():
    global pc
    logger.info(f"📹 [WebRTC] 시그널링 연결 시도: {SIGNAL_WS_URL}")

    while True: # 재접속 루프
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(SIGNAL_WS_URL) as ws:
                    logger.info("✅ [WebRTC] 시그널링 서버 연결 성공!")

                    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
                    pc = RTCPeerConnection(configuration=config)
                    pc.addTrack(BouncingBallTrack())

                    # Offer 전송
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    
                    offer_payload = {"type": "offer", "sdp": pc.localDescription.sdp}
                    await ws.send_json(offer_payload)
                    logger.info("📡 [WebRTC] Offer 전송함.")

                    # 메시지 수신
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "answer":
                                logger.info("📩 [WebRTC] Answer 수신!")
                                desc = RTCSessionDescription(sdp=data["sdp"], type="answer")
                                await pc.setRemoteDescription(desc)
                            elif data.get("candidate"):
                                candidate = RTCIceCandidate(candidate=data["candidate"], sdpMid=data["sdpMid"], sdpMLineIndex=data["sdpMLineIndex"])
                                await pc.addIceCandidate(candidate)
        except Exception as e:
            logger.error(f"⚠️ [WebRTC] 연결 실패 (3초 후 재시도): {e}")
            await asyncio.sleep(3)

# --- 메인 실행 ---
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        logger.info("🚀 로봇 시뮬레이터 시작 (Port 9999)")
        group = asyncio.gather(run_data_simulation(), run_webrtc_signaling())
        loop.run_until_complete(group)
    except KeyboardInterrupt:
        logger.info("👋 종료")
    finally:
        if pc: loop.run_until_complete(pc.close())
        loop.close()