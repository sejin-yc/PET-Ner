import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage # [변경] CompressedImage 메시지 사용
from cv_bridge import CvBridge
import cv2
import numpy as np # [추가] 데이터 변환용

class CamPublisher(Node):
    def __init__(self):
        super().__init__('cam_publisher')

        # 파라미터 설정
        self.declare_parameter('cam_index', 0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30)
        self.declare_parameter('topic', 'wrist_cam') 
        self.declare_parameter('quality', 50) # [추가] JPG 압축 품질 (0~100, 낮을수록 용량 작음)

        cam_index = int(self.get_parameter('cam_index').value)
        width = int(self.get_parameter('width').value)
        height = int(self.get_parameter('height').value)
        fps = int(self.get_parameter('fps').value)
        base_topic = str(self.get_parameter('topic').value)
        self.quality = int(self.get_parameter('quality').value)

        # [변경] CompressedImage 퍼블리셔 생성
        # 관례적으로 원본 토픽명 뒤에 "/compressed"를 붙입니다.
        full_topic = f"{base_topic}/compressed"
        self.pub = self.create_publisher(CompressedImage, full_topic, 10)
        
        self.bridge = CvBridge()

        # 카메라 열기
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().error(f"❌ 카메라(Index {cam_index})를 열 수 없습니다!")
            raise RuntimeError(f"Cannot open camera index {cam_index}")

        # 카메라 속성 설정
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        period = 1.0 / max(fps, 1)
        self.timer = self.create_timer(period, self.loop)

        self.get_logger().info(f"📡 '{full_topic}' 발행 중... (Quality: {self.quality})")

    def loop(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.get_logger().warn("프레임 읽기 실패")
            return

        # [핵심] 이미지를 JPG 포맷으로 압축
        # cv2.imencode returns (success, encoded_image)
        success, encoded_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])

        if success:
            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "wrist_camera_link"
            msg.format = "jpeg"
            msg.data = encoded_img.tobytes() # numpy array를 bytes로 변환
            
            self.pub.publish(msg)

def main():
    rclpy.init()
    node = CamPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.cap.release()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()