import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        # 나중에 런치 파일에서 IP를 바꿀 수 있도록 파라미터로 설정합니다.
        self.declare_parameter('udp_ip', '192.168.100.254')
        self.declare_parameter('udp_port', 5000)
        
        udp_ip = self.get_parameter('udp_ip').get_parameter_value().string_value
        udp_port = self.get_parameter('udp_port').get_parameter_value().integer_value
        
        url = f"udp://{udp_ip}:{udp_port}"
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.bridge = CvBridge()
        self.publisher_ = self.create_publisher(Image, '/camera/image_raw', 10)
        
        self.create_timer(0.1, self.timer_callback)
        self.get_logger().info(f'🚀 카메라 노드 시작: {url}')

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            self.publisher_.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(CameraNode())
    rclpy.shutdown()
