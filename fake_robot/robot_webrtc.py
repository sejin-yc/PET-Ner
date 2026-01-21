import asyncio
import json
import cv2
import logging
import aiohttp
import time
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

# ✅ 설정
SERVER_URL = "http://localhost:8080/ws"
WEBCAM_INDEX = 0 

logging.basicConfig(level=logging.INFO)

class CameraStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(WEBCAM_INDEX)
        
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        
        if not ret:
            # 카메라 오류 시 빨간 화면
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (0, 0, 255)
            cv2.putText(frame, "No Camera", (200, 240), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        else:
            # 정상 작동 시 시간 표시
            cv2.putText(frame, f"LIVE: {time.strftime('%H:%M:%S')}", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def run_robot():
    while True: # 🔄 [추가] 무한 재접속 루프 (절대 안 꺼짐)
        pc = None
        try:
            print("🔄 [Robot] 서버 연결 시도 중...")
            pc = RTCPeerConnection()
            pc.addTrack(CameraStreamTrack())

            async with aiohttp.ClientSession() as session:
                ws_url = SERVER_URL.replace("http", "ws")
                
                # ✅ [추가] heartbeat=30.0 (30초마다 생존신호 보내서 끊김 방지)
                async with session.ws_connect(ws_url, heartbeat=30.0) as ws:
                    print(f"✅ [Robot] 서버 연결 성공!")

                    # 1. STOMP 연결 프레임 (필수)
                    connect_frame = "CONNECT\naccept-version:1.1,1.0\n\n\x00"
                    await ws.send_str(connect_frame)

                    # 2. Offer 생성 및 전송
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    
                    payload = json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})
                    send_frame = f"SEND\ndestination:/pub/peer/offer\ncontent-type:application/json\n\n{payload}\x00"
                    await ws.send_str(send_frame)
                    print("📤 [Robot] Offer 전송 완료")

                    # 3. Answer 구독
                    sub_frame = "SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/answer\n\n\x00"
                    await ws.send_str(sub_frame)

                    # 4. 메시지 수신 대기
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            if "MESSAGE" in msg.data and "destination:/sub/peer/answer" in msg.data:
                                if pc.signalingState == "stable":
                                    continue
                                
                                try:
                                    body = msg.data.split("\n\n")[-1].replace("\x00", "")
                                    answer = json.loads(body)
                                    desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                                    await pc.setRemoteDescription(desc)
                                    print("🎥 [Robot] P2P 연결 성공! 영상 송출 중...")
                                except Exception as e:
                                    print(f"❌ WebRTC 핸드쉐이크 에러: {e}")
                        
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print("❌ 웹소켓 에러 발생, 재접속합니다.")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print("❌ 서버가 연결을 끊었습니다.")
                            break

        except Exception as e:
            print(f"❌ 로봇 실행 중 오류 발생: {e}")
        
        finally:
            # 리소스 정리 후 재시도
            if pc:
                await pc.close()
            print("⏳ 3초 후 재접속합니다...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(run_robot())
    except KeyboardInterrupt:
        print("방송 종료")