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
                if self.frame_count % 30 == 0:
                    print(f"Frame Received: {frame.shape}")
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
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, "QoS: Best Effort", (50, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def run_robot(ros_node):
    while True:
        pc = None
        try:
            ws_url = "wss://i14c203.p.ssafy.io/ws"
            print("🔄 [Robot] 서버 연결 시도 중...")

            pc = RTCPeerConnection()
            pc.addTrack(RosStreamTrack(ros_node))

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, heartbeat=30.0) as ws:
                    print(f"✅ [Robot] 서버 연결 성공!")

                    # 1. STOMP 연결 프레임 (필수)
                    connect_frame = "CONNECT\naccept-version:1.1,1.0\n\n\x00"
                    await ws.send_str(connect_frame)

                    # 2. Offer 생성 및 전송
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    
                    payload = json.dumps({
                        "sdp": pc.localDescription.sdp,
                        "type": pc.localDescription.type,
                        "robotId": ROBOT_ID
                    })
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
                                try:
                                    body = msg.data.split("\n\n")[-1].replace("\x00", "")
                                    answer = json.loads(body)
                                    desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                                    await pc.setRemoteDescription(desc)
                                    print("🎥 [Robot] P2P 연결 성공!")
                                except Exception as e:
                                    print(f"❌ WebRTC 핸드쉐이크 에러: {e}")
                        
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            print(f"❌ 로봇 실행 중 오류 발생: {e}")
        finally:
            # 리소스 정리 후 재시도
            if pc: await pc.close()
            print("⏳ 3초 후 재접속합니다...")
            await asyncio.sleep(3)

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