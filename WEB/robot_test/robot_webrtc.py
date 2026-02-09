import sys
import os
import platform

# ROS 2 라이브러리 경로 설정
ros_distro = os.environ.get("ROS_DISTRO", "humble")
py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
ros_site_packages = f"/opt/ros/{ros_distro}/lib/{py_version}/site-packages"

if os.path.exists(ros_site_packages):
    if ros_site_packages not in sys.path:
        sys.path.append(ros_site_packages)

import asyncio
import json
import cv2
import logging
import aiohttp
import time
import numpy as np
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from av import VideoFrame

# ✅ [설정] 서버 주소 (Nginx 설정을 따름)
WS_URL = "wss://i14c203.p.ssafy.io/ws"
IMAGE_TOPIC = "/front_cam/compressed"
ROBOT_ID = "1"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("RobotWebRTC")

class ImageSubscriber(Node):
    """ROS 2 이미지 토픽 구독 노드"""
    def __init__(self):
        super().__init__('webrtc_image_subscriber')
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.subscription = self.create_subscription(
            CompressedImage, IMAGE_TOPIC, self.listener_callback, qos_profile
        )
        self.latest_frame = None
        log.info(f"📷 [ROS] Waiting for images on {IMAGE_TOPIC}")
    
    def listener_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is not None:
                self.latest_frame = frame
        except Exception:
            pass

class RosStreamTrack(VideoStreamTrack):
    """WebRTC로 전송할 비디오 트랙"""
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
                                            
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.ros_node.latest_frame
        
        # 카메라 데이터가 아직 없으면 검은 화면에 텍스트 출력
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for Camera...", (50, 240), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def run_robot(ros_node):
    # ✅ [STUN 서버 설정] Google STUN 서버를 사용하여 NAT/방화벽 문제 해결
    ice_servers = [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    rtc_config = RTCConfiguration(iceServers=ice_servers)

    while True:
        session = None
        ws = None
        pc = None

        try:
            log.info(f"🔄 [WebSocket] 연결 시도: {WS_URL}")
            session = aiohttp.ClientSession()
            ws = await session.ws_connect(WS_URL, ssl=False, heartbeat=20.0)
            log.info("✅ [WebSocket] 연결 성공!")

            # 1. STOMP 프로토콜 핸드쉐이크
            await ws.send_str("CONNECT\naccept-version:1.1,1.0\nheart-beat:10000,10000\n\n\x00")
            await ws.send_str("SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/answer\n\n\x00")

            # 2. WebRTC PeerConnection 생성
            pc = RTCPeerConnection(configuration=rtc_config)
            pc.addTrack(RosStreamTrack(ros_node))

            # 3. Offer 생성 및 전송
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            payload = json.dumps({
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
                "robotId": ROBOT_ID
            })
            
            # STOMP SEND 프레임 전송
            send_msg = f"SEND\ndestination:/pub/peer/offer\ncontent-type:application/json\n\n{payload}\x00"
            await ws.send_str(send_msg)
            log.info("📤 [WebRTC] Offer 전송 완료. Answer 대기 중...")

            # ICE 상태 모니터링 로그
            async def on_ice_connection_state_change():
                log.info(f"📡 ICE State: {pc.iceConnectionState}")
            pc.on("iceconnectionstatechange", on_ice_connection_state_change)

            # 4. 메시지 수신 루프
            while not ws.closed:
                try:
                    # 2초 타임아웃으로 주기적 상태 체크
                    msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                except asyncio.TimeoutError:
                    # 연결이 끊어지면 루프 탈출 -> 재접속 시도
                    if pc.connectionState in ["closed", "failed"]:
                        log.warning("⚠️ WebRTC 연결 종료 감지. 재접속합니다.")
                        break
                    continue

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    if "MESSAGE" in data and "/sub/peer/answer" in data:
                        try:
                            # STOMP 메시지 파싱
                            parts = data.split("\n\n")
                            if len(parts) > 1:
                                body = parts[-1].replace("\x00", "")
                                answer = json.loads(body)
                                
                                # ✅ [Clean Code] 이제 오타 처리는 필요 없음. 정석대로 처리.
                                if pc.signalingState == "have-local-offer":
                                    desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                                    await pc.setRemoteDescription(desc)
                                    log.info("🎥 [WebRTC] P2P 연결 성립! 스트리밍 중...")
                                else:
                                    # 프론트엔드가 중복 전송하더라도 무시
                                    pass
                        except Exception as e:
                            log.error(f"❌ Answer 처리 실패: {e}")

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    log.error("❌ 서버 소켓 연결 종료")
                    break

        except Exception as e:
            log.error(f"❌ 실행 중 오류: {e}")
        finally:
            log.info("♻️ 리소스 정리 및 3초 후 재접속...")
            try:
                if pc: await pc.close()
                if ws: await ws.close()
                if session: await session.close()
            except:
                pass
            await asyncio.sleep(3)

def ros_spin_thread(node):
    try:
        rclpy.spin(node)
    except:
        pass

def main():
    rclpy.init()
    ros_node = ImageSubscriber()
    t = threading.Thread(target=ros_spin_thread, args=(ros_node, ), daemon=True)
    t.start()
    
    try:
        asyncio.run(run_robot(ros_node))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ros_node.destroy_node()
            rclpy.shutdown()
        except:
            pass

if __name__ == "__main__":
    main()
