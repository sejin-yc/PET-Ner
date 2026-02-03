import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist, PoseStamped
import json
import paho.mqtt.client as mqtt
import math
import time

MQTT_BROKER_IP = "i14c203.p.ssafy.io"
MQTT_PORT = 1883

ROBOT_ID = "1"

TOPIC_STATUS = f"robot/{ROBOT_ID}/status"
TOPIC_CONTROL = f"robot/{ROBOT_ID}/control"
TOPIC_EVENT = f"robot/{ROBOT_ID}/cat_state"

POS_TOPIC = "/amcl_pose"
CMD_VEL_TOPIC = "/cmd_vel"
GOAL_TOPIC = "/goal_pose"

class MqttBridge(Node):
    def __init__(self):
        super().__init__('mqtt_bridge_node')

        # --- [1] ROS 2 Publisher (명령 발신) ---
        self.cmd_vel_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.goal_pub = self.create_publisher(PoseStamped, GOAL_TOPIC, 10)

        # --- [2] ROS 2 Subscriber (상태 수신) ---
        msg_type = PoseWithCovarianceStamped if "amcl" in POS_TOPIC else Odometry
        self.create_subscription(msg_type, POS_TOPIC, self.listener_callback, 10)

        # --- [3] MQTT 설정 ---
        self.current_mode = "manual"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        try:
            self.client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            self.get_logger().error(f"❌ Connection Failed: {e}")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.get_logger().info(f"✅ MQTT Connected to {MQTT_BROKER_IP}")
            self.get_logger().info(f"Subscribing to: {TOPIC_CONTROL}")
            client.subscribe(TOPIC_CONTROL)
        else:
            self.get_logger().error(f"❌ Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            command_type = payload.get("type")

            if command_type == "EMERGENCY_STOP":
                self.get_logger().warn("🚨 EMERGENCY STOP RECEIVED!")
                self.stop_robot()
                self.current_mode = "manual"
            elif command_type == "MODE_CHANGE":
                new_mode = payload.get("mode", "manual")
                self.get_logger().info(f"🔄 Mode Changed: {new_mode}")
                self.current_mode = new_mode

                if new_mode == "auto":
                    self.go_to_origin()
                else:
                    self.stop_robot()
            elif command_type == "MOVE":
                if self.current_mode == "manual":
                    linear = float(payload.get("linear", 0.0))
                    angular = float(payload.get("angular", 0.0))
                    self.move_robot(linear, angular)
                else:
                    self.get_logger().warn("⚠️ Ignored manual command (Current mode is AUTO)")
        except Exception as e:
            self.get_logger().error(f"⚠️ Message parsing error: {e}")
    
    def stop_robot(self):
        twist = Twist()
        self.cmd_vel_pub.publish(twist)
    
    def move_robot(self, linear, angular):
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.cmd_vel_pub.publish(twist)
    
    def go_to_origin(self):
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()

        goal.pose.position.x = 0.0
        goal.pose.position.y = 0.0
        goal.pose.orientation.w = 1.0

        self.goal_pub.publish(goal)
    
    def listener_callback(self, msg):
        if "amcl" in POS_TOPIC:
            position = msg.pose.pose.position
            orientation = msg.pose.pose.orientation
        else:
            position = msg.pose.pose.position
            orientation = msg.pose.pose.orientation
        
        _, _, yaw = self.euler_from_quaternion(orientation)

        status_payload = {
            "userId": int(ROBOT_ID),
            "robotId": ROBOT_ID,
            "x": round(position.x, 3),
            "y": round(position.y, 3),
            "theta": round(yaw, 3),
            "battery": 80,
            "mode": self.current_mode,
            "isOnline": True
        }

        self.client.publish(TOPIC_STATUS, json.dumps(status_payload))
    
    def euler_from_quaternion(self, q):
        t0 = 2.0 * (q.w * q.z + q.x * q.y)
        t1 = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        roll_x = math.atan2(t0, t1)

        t2 = 2.0 * (q.w * q.y - q.z * q.x)
        t2 = 1.0 if t2 > 1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)

        t3 = 2.0 * (q.w * q.z + q.x * q.y)
        t4 = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw_z = math.atan2(t3, t4)

        return roll_x, pitch_y, yaw_z

def main(args=None):
    rclpy.init(args=args)
    node = MqttBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.client.loop_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()