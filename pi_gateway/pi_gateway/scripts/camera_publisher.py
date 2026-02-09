#!/usr/bin/env python3
"""
젯슨에서 실행: 카메라 → /camera/image_compressed 발행.
구독해서 /stream.mjpeg로 웹에 전달.

실행 (Jetson, ROS2 환경):
  source /opt/ros/humble/setup.bash
  pip install opencv-python  # 또는 apt install python3-opencv
  python3 scripts/camera_publisher.py

환경 변수:
  CAMERA_ID=0           카메라 디바이스 (기본 0)
  CAMERA_WIDTH=640      해상도 가로
  CAMERA_HEIGHT=480     해상도 세로
  CAMERA_FPS=15         목표 fps
  ROS_DOMAIN_ID=0       Pi와 동일하게
"""

import os
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import cv2
except ImportError:
    print("[ERROR] opencv-python 필요: pip install opencv-python")
    sys.exit(1)

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import CompressedImage
    from std_msgs.msg import Header
except ImportError as e:
    print(f"[ERROR] ROS2 필요: source /opt/ros/humble/setup.bash - {e}")
    sys.exit(1)


def main():
    camera_id = int(os.getenv("CAMERA_ID", "0"))
    width = int(os.getenv("CAMERA_WIDTH", "640"))
    height = int(os.getenv("CAMERA_HEIGHT", "480"))
    target_fps = float(os.getenv("CAMERA_FPS", "15"))
    period = 1.0 / max(1.0, target_fps)

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[ERROR] 카메라 열기 실패: device={camera_id}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, target_fps)

    rclpy.init()
    node = Node("camera_publisher")
    pub = node.create_publisher(CompressedImage, "/camera/image_compressed", 10)

    print(f"[camera_publisher] 시작: device={camera_id} {width}x{height} ~{target_fps}fps → /camera/image_compressed")

    try:
        while rclpy.ok():
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            _, jpeg = cv2.imencode(".jpg", frame)
            msg = CompressedImage()
            msg.header.stamp = node.get_clock().now().to_msg()
            msg.header.frame_id = "camera"
            msg.format = "jpeg"
            msg.data = jpeg.tobytes()
            pub.publish(msg)

            elapsed = time.time() - t0
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        node.destroy_node()
        rclpy.shutdown()
    print("[camera_publisher] 종료")


if __name__ == "__main__":
    main()
