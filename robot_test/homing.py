#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
import rclpy.time

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

from tf2_ros import Buffer, TransformListener, TransformException


def wrap_pi(a):
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def yaw_from_quat(qx, qy, qz, qw):
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def sgn(x: float) -> float:
    if x > 0.0:
        return 1.0
    if x < 0.0:
        return -1.0
    return 0.0


class HomingFixedPWM(Node):
    """
    Home로 이동 후 yaw_deg(절대각)로 회전하는 단일 미션 노드
    - 수정됨: Y축(좌우) 우선 정렬 후 X축(전후) 이동
    """

    def __init__(self):
        super().__init__("homing_fixed_pwm")

        # -------------------------
        # Params
        # -------------------------
        self.declare_parameter("global_frame", "map")
        self.declare_parameter("base_frame", "base_link")

        self.declare_parameter("cmd_topic", "/cmd_vel_nav")
        self.declare_parameter("allow_strafe_topic", "/gateway/allow_strafe")

        # home target
        self.declare_parameter("home_x", 1.2)
        self.declare_parameter("home_y", 1.7)
        self.declare_parameter("home_yaw_deg", -180.0)

        # control
        self.declare_parameter("control_hz", 20.0)

        # fixed magnitudes
        self.declare_parameter("fixed_vx", 0.20)
        self.declare_parameter("fixed_vy", 0.20)
        self.declare_parameter("fixed_wz", 0.60)

        # tolerances
        self.declare_parameter("tol_axis", 0.03)
        self.declare_parameter("tol_perp", 0.06)
        self.declare_parameter("tol_yaw", 0.05)  # rad

        # pulse
        self.declare_parameter("pulse_enable", True)
        self.declare_parameter("pulse_near_axis", 0.12)
        self.declare_parameter("pulse_near_yaw", 0.25)
        self.declare_parameter("pulse_on_sec", 0.12)
        self.declare_parameter("pulse_off_sec", 0.08)

        # timeouts
        self.declare_parameter("goto_timeout", 60.0)
        self.declare_parameter("rotate_timeout", 20.0)

        # auto start
        self.declare_parameter("auto_start", True)

        # -------------------------
        # Read params
        # -------------------------
        self.global_frame = self.get_parameter("global_frame").value
        self.base_frame = self.get_parameter("base_frame").value
        self.cmd_topic = self.get_parameter("cmd_topic").value
        self.allow_strafe_topic = self.get_parameter("allow_strafe_topic").value

        self.home_x = float(self.get_parameter("home_x").value)
        self.home_y = float(self.get_parameter("home_y").value)
        self.home_yaw_deg = float(self.get_parameter("home_yaw_deg").value)
        self.home_yaw = wrap_pi(math.radians(self.home_yaw_deg))

        hz = float(self.get_parameter("control_hz").value)
        self.dt = 1.0 / max(1.0, hz)

        self.fixed_vx = float(self.get_parameter("fixed_vx").value)
        self.fixed_vy = float(self.get_parameter("fixed_vy").value)
        self.fixed_wz = float(self.get_parameter("fixed_wz").value)

        self.tol_axis = float(self.get_parameter("tol_axis").value)
        self.tol_perp = float(self.get_parameter("tol_perp").value)
        self.tol_yaw = float(self.get_parameter("tol_yaw").value)

        self.pulse_enable = bool(self.get_parameter("pulse_enable").value)
        self.pulse_near_axis = float(self.get_parameter("pulse_near_axis").value)
        self.pulse_near_yaw = float(self.get_parameter("pulse_near_yaw").value)
        self.pulse_on_sec = float(self.get_parameter("pulse_on_sec").value)
        self.pulse_off_sec = float(self.get_parameter("pulse_off_sec").value)

        self.goto_timeout = float(self.get_parameter("goto_timeout").value)
        self.rotate_timeout = float(self.get_parameter("rotate_timeout").value)

        self.auto_start = bool(self.get_parameter("auto_start").value)

        # -------------------------
        # TF
        # -------------------------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # -------------------------
        # Pub
        # -------------------------
        self.pub_cmd = self.create_publisher(Twist, self.cmd_topic, 10)
        self.pub_allow_strafe = self.create_publisher(Bool, self.allow_strafe_topic, 10)

        # -------------------------
        # State
        # -------------------------
        self.state = "IDLE"   # IDLE -> GOTO -> ROTATE -> DONE
        self.t0 = self.now_sec()

        self.pulse_on = True
        self.pulse_next_t = None

        self.set_allow_strafe(False)
        self.stop()

        self.timer = self.create_timer(self.dt, self.on_timer)

        self.get_logger().info(
            f"home=({self.home_x:.3f},{self.home_y:.3f}), yaw_deg={self.home_yaw_deg:.1f} (abs), Y-First Priority"
        )

        if self.auto_start:
            self.start()

    # -------------------------
    # Utils
    # -------------------------
    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def stop(self):
        self.pub_cmd.publish(Twist())

    def set_allow_strafe(self, on: bool):
        self.pub_allow_strafe.publish(Bool(data=bool(on)))

    def _reset_pulse(self):
        self.pulse_on = True
        self.pulse_next_t = None

    def _pulse_update(self) -> bool:
        if not self.pulse_enable:
            return True
        now = self.now_sec()
        if self.pulse_next_t is None:
            self.pulse_on = True
            self.pulse_next_t = now + self.pulse_on_sec
            return True
        if now >= self.pulse_next_t:
            self.pulse_on = not self.pulse_on
            self.pulse_next_t = now + (self.pulse_on_sec if self.pulse_on else self.pulse_off_sec)
        return self.pulse_on

    def get_pose_map(self):
        try:
            tf = self.tf_buffer.lookup_transform(
                self.global_frame,
                self.base_frame,
                rclpy.time.Time()
            )
            x = tf.transform.translation.x
            y = tf.transform.translation.y
            q = tf.transform.rotation
            yaw = yaw_from_quat(q.x, q.y, q.z, q.w)
            return x, y, yaw
        except TransformException:
            return None

    def map_err_to_base(self, dx, dy, yaw):
        # map error(dx,dy) -> base (ex,ey)
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        ex = cy * dx + sy * dy
        ey = -sy * dx + cy * dy
        return ex, ey

    # -------------------------
    # Mission
    # -------------------------
    def start(self):
        self.state = "GOTO"
        self.t0 = self.now_sec()
        self._reset_pulse()
        self.get_logger().info("HOMING START (GOTO -> ROTATE)")

    # -------------------------
    # Main loop
    # -------------------------
    def on_timer(self):
        if self.state in ("IDLE", "DONE"):
            return

        pose = self.get_pose_map()
        if pose is None:
            self.stop()
            return

        cx, cy, cyaw = pose

        # -------------------------
        # 1) GOTO HOME (Y-axis Priority)
        # -------------------------
        if self.state == "GOTO":
            if (self.now_sec() - self.t0) > self.goto_timeout:
                self.get_logger().error("GOTO TIMEOUT -> stop")
                self.state = "DONE"
                self.set_allow_strafe(False)
                self.stop()
                return

            dx = self.home_x - cx
            dy = self.home_y - cy
            ex, ey = self.map_err_to_base(dx, dy, cyaw)

            # [수정된 부분] Y축 우선 정렬 로직
            # ey(횡방향 오차)가 허용범위(tol_perp)보다 크면 무조건 Y축 이동 모드로 설정
            if abs(ey) > self.tol_perp:
                axis = "y"
            else:
                axis = "x"

            if axis == "x":
                e_axis = ex
                e_perp = ey
                cmd_val = self.fixed_vx
                self.set_allow_strafe(False)
            else:
                e_axis = ey
                e_perp = ex
                cmd_val = self.fixed_vy
                self.set_allow_strafe(True)

            # 도달 판정 (X, Y 둘 다 오차 범위 내여야 함)
            if abs(e_axis) <= self.tol_axis and abs(e_perp) <= self.tol_perp:
                self.stop()
                self.set_allow_strafe(False)
                self.state = "ROTATE"
                self.t0 = self.now_sec()
                self._reset_pulse()
                self.get_logger().info("ARRIVED HOME -> ROTATE")
                return

            # near면 pulse
            if abs(e_axis) < self.pulse_near_axis:
                on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True

            cmd = Twist()
            if not on:
                self.pub_cmd.publish(cmd)
                return

            if axis == "x":
                cmd.linear.x = sgn(e_axis) * abs(cmd_val)
            else:
                cmd.linear.y = sgn(e_axis) * abs(cmd_val)

            cmd.angular.z = 0.0
            self.pub_cmd.publish(cmd)
            return

        # -------------------------
        # 2) ROTATE to ABS YAW
        # -------------------------
        if self.state == "ROTATE":
            if (self.now_sec() - self.t0) > self.rotate_timeout:
                self.get_logger().error("ROTATE TIMEOUT -> stop")
                self.state = "DONE"
                self.set_allow_strafe(False)
                self.stop()
                return

            yaw_err = wrap_pi(self.home_yaw - cyaw)

            if abs(yaw_err) <= self.tol_yaw:
                self.stop()
                self.set_allow_strafe(False)
                self.state = "DONE"
                self.get_logger().info("HOMING DONE ✅")
                return

            if abs(yaw_err) < self.pulse_near_yaw:
                on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True

            cmd = Twist()
            self.set_allow_strafe(False)

            if not on:
                self.pub_cmd.publish(cmd)
                return

            cmd.angular.z = sgn(yaw_err) * abs(self.fixed_wz)
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            self.pub_cmd.publish(cmd)
            return


def main():
    rclpy.init()
    node = HomingFixedPWM()
    try:
        rclpy.spin(node)
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()