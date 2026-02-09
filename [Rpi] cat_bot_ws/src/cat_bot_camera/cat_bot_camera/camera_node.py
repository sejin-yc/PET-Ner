#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from cv_bridge import CvBridge
import cv2

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        
        # ✅ QoS 설정: "밀린 데이터는 버리고 최신 데이터만 보낸다" (랙 제거 핵심)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # ✅ 토픽 이름 변경: /front_cam/compressed (압축 이미지임)
        self.publisher_ = self.create_publisher(CompressedImage, '/front_cam/compressed', qos_profile)
        
        # 카메라 설정 (V4L2 + MJPG + 30FPS)
        self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.cap.set(cv2.CAP_PROP_FPS, 15)          # 15 FPS 요청
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320) # 해상도 320x240
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        
        self.bridge = CvBridge()
        
        # 30 FPS에 맞춰 타이머 설정 (0.033초)
        self.timer = self.create_timer(0.066, self.timer_callback)
        self.get_logger().info('🚀 고성능 모드 시작: 압축전송 + QoS BestEffort + 15FPS')

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            # 안전장치: 해상도 강제 조정
            if frame.shape[1] != 320 or frame.shape[0] != 240:
                frame = cv2.resize(frame, (320, 240))
            
            # ✅ JPEG 압축 (화질 50% - 속도 최우선)
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "camera_frame"
            msg.format = "jpeg"
            msg.data = buffer.tobytes()
            
            self.publisher_.publish(msg)
        else:
            self.get_logger().warn('⚠️ 프레임 읽기 실패')

def main():
    rclpy.init()
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.cap.isOpened():
            node.cap.release()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
