import sys
import os
import platform

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

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

# ✅ 설정
SERVER_URL = "https://i14c203.p.ssafy.io/ws"
WS_URL = "wss://i14c203.p.ssafy.io/ws"
IMAGE_TOPIC = "/front_cam/compressed"
ROBOT_ID = "1"

logging.basicConfig(level=logging.INFO)

class ImageSubscriber(Node):
    def __init__(self):
        super().__init__('webrtc_image_subscriber')

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.subscription = self.create_subscription(
            CompressedImage,
            IMAGE_TOPIC,
            self.listener_callback,
            qos_profile
        )
        self.latest_frame = None
        self.frame_count = 0
        self.get_logger().info(f"Waiting for Image on {IMAGE_TOPIC}")
    
    def listener_callback(self, msg):
        try:
            # 1. 바이트 데이터를 numpy 배열로 변환
            np_arr = np.frombuffer(msg.data, np.uint8)
            # 2. 이미지 디코딩 (Compressed -> BGR)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                self.latest_frame = frame
                self.frame_count += 1
                if self.frame_count % 100 == 0: pass
        except Exception as e:
            self.get_logger().error(f"Image Decode Error: {e}")

class RosStreamTrack(VideoStreamTrack):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
                                            
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.ros_node.latest_frame
        
        if frame is None:
            # 카메라 오류 시 대기 화면
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for ROS Topic", (50, 240), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def run_robot(ros_node):
    while True:
        pc = None
        ws = None
        session = None

        try:
            print("🔄 [Robot] 서버 연결 시도 중...")

            session = aiohttp.ClientSession()
            ws = await session.ws_connect(WS_URL, heartbeat=30.0)

            print(f"✅ [Robot] 소켓 연결 성공!")

            await ws.send_str("CONNECT\naccept-version:1.1,1.0\n\n\x00")
            await ws.send_str("SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/answer\n\n\x00")

            pc = RTCPeerConnection()
            pc.addTrack(RosStreamTrack(ros_node))

            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                print(f"📡 WebRTC 상태 변경: {pc.connectionState}")

                if pc.connectionState in ["failed", "closed"]:
                    print("⚠️ 연결 끊김 감지! 리셋 준비...")
                    await pc.close()
            
            last_offer_time = 0

            while not ws.closed:
                if pc.connectionState == "closed":
                    break

                current_time = time.time()
                if pc.connectionState != "connected" and (current_time - last_offer_time > 2.0):
                    try:
                        offer = await pc.createOffer()
                        await pc.setLocalDescription(offer)

                        payload = json.dumps({
                            "sdp": pc.localDescription.sdp,
                            "type": pc.localDescription.type,
                            "robotId": ROBOT_ID
                        })

                        frame = f"SEND\ndestination:/pub/peer/offer\ncontent-type:application/json\n\n{payload}\x00"
                        await ws.send_str(frame)
                        print("📤 [Robot] Offer 전송 (연결 대기 중...)")
                        last_offer_time = current_time
                    except Exception as e:
                        print(f"Offer 생성 실패 (재시도 예정): {e}")
                
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=1.0)

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        if "MESSAGE" in msg.data and "destination:/sub/peer/answer" in msg.data:
                            body = msg.data.split("\n\n")[-1].replace("\x00", "")

                            if body:
                                answer = json.loads(body)
                                print("📩 [Robot] Answer 수신!")

                                if pc.signalingState == "stable":
                                    print("⚠️ 이미 연결됨. 재협상(Reset) 필요.")
                                    break

                                desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                                await pc.setRemoteDescription(desc)
                                print("🎥 [Robot] P2P 연결 성공! 스트리밍 시작")
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        print("❌ 소켓 끊김")
                        break
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    print(f"❌ 메시지 처리 에러: {e}")
                    break
        except Exception as e:
            print(f"❌ 실행 중 오류: {e}")
        finally:
            print("♻️ 리소스 정리 및 재시작...")
            if pc: await pc.close()
            if ws: await ws.close()
            if session: await session.close()
            await asyncio.sleep(2)

def ros_spin_thread(node):
    rclpy.spin(node)

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
        ros_node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()