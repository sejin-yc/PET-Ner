#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2

# ==========================================
# 1. Wrist Camera Node (Raw Image)
#    - 기존 첫 번째 코드 (인덱스 0, Raw Image 발행)
# ==========================================
class WristCamNode(Node):
    def __init__(self):
        super().__init__('wrist_cam_node')
        
        # 파라미터 설정
        self.declare_parameter('cam_index', 0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30)
        self.declare_parameter('topic', 'wrist_cam')

        self.index = self.get_parameter('cam_index').value
        self.w = self.get_parameter('width').value
        self.h = self.get_parameter('height').value
        self.fps = self.get_parameter('fps').value
        topic_name = self.get_parameter('topic').value

        # 퍼블리셔 (Raw Image)
        self.pub = self.create_publisher(Image, topic_name, 10)
        self.bridge = CvBridge()

        # 카메라 연결
        self.cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().error(f"❌ [Wrist] 카메라(Index {self.index}) 연결 실패!")
        else:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.get_logger().info(f"✅ [Wrist] '{topic_name}' 발행 시작 (Index: {self.index})")

        # 타이머 설정
        period = 1.0 / max(self.fps, 1)
        self.timer = self.create_timer(period, self.loop)

    def loop(self):
        if not self.cap.isOpened(): return
        
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.get_logger().warn("[Wrist] 프레임 읽기 실패", throttle_duration_sec=2.0)
            return

        # Raw Image 발행
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "wrist_camera_link"
        self.pub.publish(msg)


# ==========================================
# 2. Front Camera Node (Compressed Image)
#    - 기존 두 번째 코드 (인덱스 6, Compressed Image 발행, 리사이즈)
# ==========================================
class FrontCamNode(Node):
    def __init__(self):
        super().__init__('front_cam_node')

        # 파라미터 설정
        self.declare_parameter('cam_index', 6)
        self.declare_parameter('topic', '/front_cam/compressed')

        self.index = self.get_parameter('cam_index').value
        topic_name = self.get_parameter('topic').value

        # QoS 설정 (Best Effort -> 전송 속도 우선)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # 퍼블리셔 (Compressed Image)
        self.pub = self.create_publisher(CompressedImage, topic_name, qos_profile)

        # 카메라 연결
        self.cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().error(f"❌ [Front] 카메라(Index {self.index}) 연결 실패!")
        else:
            # MJPG 설정 (대역폭 절약)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.get_logger().info(f"✅ [Front] '{topic_name}' 발행 시작 (Index: {self.index})")

        # 타이머 (30fps)
        self.timer = self.create_timer(0.033, self.loop)

    def loop(self):
        if not self.cap.isOpened(): return

        ret, frame = self.cap.read()
        if ret:
            # 리사이즈 (320x240) -> 전송량 감소
            if frame.shape[1] != 320 or frame.shape[0] != 240:
                frame = cv2.resize(frame, (320, 240))
            
            # JPEG 압축
            success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            
            if success:
                msg = CompressedImage()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.header.frame_id = "front_camera_link"
                msg.format = "jpeg"
                msg.data = buffer.tobytes()
                
                self.pub.publish(msg)
                # print(f"✅ [Front] 발행 중... {len(msg.data)} bytes", end='\r')
        else:
            self.get_logger().warn("[Front] 프레임 읽기 실패", throttle_duration_sec=2.0)


# ==========================================
# Main Execution
# ==========================================
def main(args=None):
    rclpy.init(args=args)

    # 두 개의 노드 생성
    wrist_node = WristCamNode()
    front_node = FrontCamNode()

    # MultiThreadedExecutor를 사용하여 두 노드를 병렬 실행
    executor = MultiThreadedExecutor()
    executor.add_node(wrist_node)
    executor.add_node(front_node)

    try:
        print("📸 듀얼 카메라 노드 시작 (Ctrl+C로 종료)")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        # 종료 처리
        wrist_node.cap.release()
        front_node.cap.release()
        wrist_node.destroy_node()
        front_node.destroy_node()
        rclpy.shutdown()
        print("\n🛑 카메라 노드 종료됨.")

if __name__ == '__main__':
    main()
