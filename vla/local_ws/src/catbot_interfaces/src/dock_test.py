#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist, PoseStamped
from std_msgs.msg import Bool, Int32, Float32
from tf2_ros import Buffer, TransformListener, TransformException
import rclpy.duration

from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def wrap_pi(a):
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def quat_to_rotmat(qx, qy, qz, qw):
    # normalized rotation matrix (marker frame expressed in base frame)
    n = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if n < 1e-9:
        return [[1,0,0],[0,1,0],[0,0,1]]
    qx, qy, qz, qw = qx/n, qy/n, qz/n, qw/n
    xx, yy, zz = qx*qx, qy*qy, qz*qz
    xy, xz, yz = qx*qy, qx*qz, qy*qz
    wx, wy, wz = qw*qx, qw*qy, qw*qz
    return [
        [1 - 2*(yy+zz),     2*(xy - wz),     2*(xz + wy)],
        [    2*(xy + wz), 1 - 2*(xx+zz),     2*(yz - wx)],
        [    2*(xz - wy),     2*(yz + wx), 1 - 2*(xx+yy)],
    ]


class DockController(Node):
    """
    /aruco/pose + /aruco/id 기반 도킹 컨트롤러

    단계:
      1) Y(횡이동) 먼저 맞춤
      2) Yaw(회전) 정렬: /aruco/pose.orientation로 마커 평면(노멀) 기준 정렬
      3) X(전/후진) 접근 (pulse)

    주의:
      - 로봇은 yaw만 제어 가능 → roll/pitch는 물리적으로 못 맞춤
      - 네 게이트웨이(1축 선택 + deadband) 시스템에 맞춰 min_v/min_w를 둠
    """

    def __init__(self):
        super().__init__("dock_controller")

        # -------- topics --------
        self.declare_parameter("aruco_pose_topic", "/aruco/pose")
        self.declare_parameter("aruco_id_topic", "/aruco/id")
        self.declare_parameter("cmd_topic", "/cmd_vel_aruco")
        self.declare_parameter("enable_topic", "/dock/enable")
        self.declare_parameter("done_topic", "/dock/done")

        self.declare_parameter("target_id_topic", "/dock/aruco_id")
        self.declare_parameter("target_dist_topic", "/dock/target_dist")
        self.declare_parameter("target_y_topic", "/dock/target_y")
        self.declare_parameter("target_z_topic", "/dock/target_z")

        # -------- frames --------
        self.declare_parameter("base_frame", "base_link")

        # -------- control --------
        self.declare_parameter("control_hz", 20.0)

        self.declare_parameter("k_x", 0.8)
        self.declare_parameter("k_y", 0.8)

        self.declare_parameter("max_vx", 0.18)
        self.declare_parameter("max_vy", 0.18)

        # 게이트웨이 deadband/정지마찰 회피
        self.declare_parameter("min_vx", 0.10)
        self.declare_parameter("min_vy", 0.10)

        # -------- yaw align (NEW) --------
        self.declare_parameter("stage_yaw_align", True)
        self.declare_parameter("k_yaw", 1.5)
        self.declare_parameter("max_wz", 0.6)
        self.declare_parameter("min_wz", 0.12)     # deadband 회피용
        self.declare_parameter("tol_yaw", 0.03)    # rad (약 5~6도)

        # orientation에서 yaw를 어떻게 뽑을지
        #  - "normal": 마커 평면의 normal(마커 +Z)을 base XY로 투영해 yaw 정렬 (추천)
        #  - "quat_yaw": quaternion yaw(그냥 euler yaw) 사용(환경 따라 헷갈릴 수 있음)
        self.declare_parameter("yaw_from", "normal")
        # 회전 방향이 반대로 느껴지면 -1.0로 바꾸기
        self.declare_parameter("yaw_sign", 1.0)

        # -------- tolerances --------
        self.declare_parameter("tol_x", 0.03)
        self.declare_parameter("tol_y", 0.03)
        self.declare_parameter("tol_z", 0.25)

        # -------- freshness --------
        self.declare_parameter("pose_timeout", 1.0)
        self.declare_parameter("id_timeout", 1.0)

        # -------- pulse --------
        self.declare_parameter("stage_y_first", True)

        self.declare_parameter("x_pulse_enable", True)
        self.declare_parameter("x_pulse_move_sec", 0.20)
        self.declare_parameter("x_pulse_stop_sec", 0.25)

        self.declare_parameter("y_pulse_enable", True)
        self.declare_parameter("y_pulse_move_sec", 0.20)
        self.declare_parameter("y_pulse_stop_sec", 0.10)

        self.declare_parameter("yaw_pulse_enable", True)
        self.declare_parameter("yaw_pulse_move_sec", 0.18)
        self.declare_parameter("yaw_pulse_stop_sec", 0.12)

        # -------- safety --------
        self.declare_parameter("min_x_safety", 0.22)

        # -------- done robustness --------
        self.declare_parameter("done_repeat_sec", 2.0)
        self.declare_parameter("done_repeat_hz", 20.0)
        self.declare_parameter("hold_after_done", True)

        # -------- read params --------
        self.pose_topic = self.get_parameter("aruco_pose_topic").value
        self.id_topic = self.get_parameter("aruco_id_topic").value
        self.cmd_topic = self.get_parameter("cmd_topic").value
        self.enable_topic = self.get_parameter("enable_topic").value
        self.done_topic = self.get_parameter("done_topic").value

        self.target_id_topic = self.get_parameter("target_id_topic").value
        self.target_dist_topic = self.get_parameter("target_dist_topic").value
        self.target_y_topic = self.get_parameter("target_y_topic").value
        self.target_z_topic = self.get_parameter("target_z_topic").value

        self.base_frame = self.get_parameter("base_frame").value

        hz = float(self.get_parameter("control_hz").value)
        self.dt = 1.0 / max(1.0, hz)

        self.k_x = float(self.get_parameter("k_x").value)
        self.k_y = float(self.get_parameter("k_y").value)
        self.max_vx = float(self.get_parameter("max_vx").value)
        self.max_vy = float(self.get_parameter("max_vy").value)
        self.min_vx = float(self.get_parameter("min_vx").value)
        self.min_vy = float(self.get_parameter("min_vy").value)

        self.stage_yaw_align = bool(self.get_parameter("stage_yaw_align").value)
        self.k_yaw = float(self.get_parameter("k_yaw").value)
        self.max_wz = float(self.get_parameter("max_wz").value)
        self.min_wz = float(self.get_parameter("min_wz").value)
        self.tol_yaw = float(self.get_parameter("tol_yaw").value)
        self.yaw_from = str(self.get_parameter("yaw_from").value).strip()
        self.yaw_sign = float(self.get_parameter("yaw_sign").value)

        self.tol_x = float(self.get_parameter("tol_x").value)
        self.tol_y = float(self.get_parameter("tol_y").value)
        self.tol_z = float(self.get_parameter("tol_z").value)

        self.pose_timeout = float(self.get_parameter("pose_timeout").value)
        self.id_timeout = float(self.get_parameter("id_timeout").value)

        self.stage_y_first = bool(self.get_parameter("stage_y_first").value)

        self.x_pulse_enable = bool(self.get_parameter("x_pulse_enable").value)
        self.x_pulse_move_sec = float(self.get_parameter("x_pulse_move_sec").value)
        self.x_pulse_stop_sec = float(self.get_parameter("x_pulse_stop_sec").value)

        self.y_pulse_enable = bool(self.get_parameter("y_pulse_enable").value)
        self.y_pulse_move_sec = float(self.get_parameter("y_pulse_move_sec").value)
        self.y_pulse_stop_sec = float(self.get_parameter("y_pulse_stop_sec").value)

        self.yaw_pulse_enable = bool(self.get_parameter("yaw_pulse_enable").value)
        self.yaw_pulse_move_sec = float(self.get_parameter("yaw_pulse_move_sec").value)
        self.yaw_pulse_stop_sec = float(self.get_parameter("yaw_pulse_stop_sec").value)

        self.min_x_safety = float(self.get_parameter("min_x_safety").value)

        self.done_repeat_sec = float(self.get_parameter("done_repeat_sec").value)
        self.done_repeat_hz = float(self.get_parameter("done_repeat_hz").value)
        self.hold_after_done = bool(self.get_parameter("hold_after_done").value)

        # -------- tf --------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # -------- QoS --------
        self.qos_default = QoSProfile(depth=10)
        self.qos_default.reliability = QoSReliabilityPolicy.RELIABLE
        self.qos_default.durability = QoSDurabilityPolicy.VOLATILE

        self.qos_done = QoSProfile(depth=1)
        self.qos_done.reliability = QoSReliabilityPolicy.RELIABLE
        self.qos_done.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL

        # -------- pubs/subs --------
        self.pub_cmd = self.create_publisher(Twist, self.cmd_topic, self.qos_default)
        self.pub_done = self.create_publisher(Bool, self.done_topic, self.qos_done)

        self.sub_pose = self.create_subscription(PoseStamped, self.pose_topic, self.cb_pose, self.qos_default)
        self.sub_id = self.create_subscription(Int32, self.id_topic, self.cb_id, self.qos_default)
        self.sub_enable = self.create_subscription(Bool, self.enable_topic, self.cb_enable, self.qos_default)

        self.sub_target_id = self.create_subscription(Int32, self.target_id_topic, self.cb_target_id, self.qos_default)
        self.sub_target_dist = self.create_subscription(Float32, self.target_dist_topic, self.cb_target_dist, self.qos_default)
        self.sub_target_y = self.create_subscription(Float32, self.target_y_topic, self.cb_target_y, self.qos_default)
        self.sub_target_z = self.create_subscription(Float32, self.target_z_topic, self.cb_target_z, self.qos_default)

        # -------- state --------
        self.enabled = False
        self.last_pose = None
        self.last_pose_t = None
        self.last_id = -1
        self.last_id_t = None

        self.target_id = -1
        self.target_dist = 0.50
        self.target_y = 0.0
        self.target_z = 0.0

        self.done_sent = False
        self.done_deadline = None
        self.done_timer = None

        # pulse state (축별 토글)
        self._pulse_axis = None       # "x" / "y" / "yaw"
        self._pulse_moving = False
        self._pulse_next_t = None
        self._pulse_sign = 0

        self.timer = self.create_timer(self.dt, self.on_timer)

        self.get_logger().info(
            f"DockController: y_first={self.stage_y_first}, yaw_align={self.stage_yaw_align} "
            f"(yaw_from={self.yaw_from}, yaw_sign={self.yaw_sign})"
        )

    # ---------- callbacks ----------
    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def cb_pose(self, msg: PoseStamped):
        self.last_pose = msg
        self.last_pose_t = self.now_sec()

    def cb_id(self, msg: Int32):
        self.last_id = int(msg.data)
        self.last_id_t = self.now_sec()

    def cb_enable(self, msg: Bool):
        prev = self.enabled
        self.enabled = bool(msg.data)

        if prev and (not self.enabled):
            self.stop()
            self._stop_done_repeat()
            self.done_sent = False
            self._reset_pulse()

    def cb_target_id(self, msg: Int32):
        self.target_id = int(msg.data)

    def cb_target_dist(self, msg: Float32):
        self.target_dist = float(msg.data)

    def cb_target_y(self, msg: Float32):
        self.target_y = float(msg.data)

    def cb_target_z(self, msg: Float32):
        self.target_z = float(msg.data)

    # ---------- helpers ----------
    def stop(self):
        try:
            self.pub_cmd.publish(Twist())
        except Exception:
            pass

    def _pose_fresh(self):
        if self.last_pose is None or self.last_pose_t is None:
            return False
        return (self.now_sec() - self.last_pose_t) <= self.pose_timeout

    def _id_ok(self):
        if self.target_id < 0:
            return True
        if self.last_id_t is None:
            return False
        if (self.now_sec() - self.last_id_t) > self.id_timeout:
            return False
        return self.last_id == self.target_id

    def _start_done_repeat(self):
        self.done_sent = True
        self.done_deadline = self.now_sec() + max(0.1, self.done_repeat_sec)

        if self.done_timer is None:
            dt = 1.0 / max(1.0, self.done_repeat_hz)
            self.done_timer = self.create_timer(dt, self._on_done_timer)

        self.pub_done.publish(Bool(data=True))

    def _stop_done_repeat(self):
        if self.done_timer is not None:
            try:
                self.done_timer.cancel()
            except Exception:
                pass
            self.done_timer = None
        self.done_deadline = None

    def _on_done_timer(self):
        if self.done_deadline is None:
            return
        if self.now_sec() > self.done_deadline:
            self._stop_done_repeat()
            return
        self.pub_done.publish(Bool(data=True))

    def _reset_pulse(self):
        self._pulse_axis = None
        self._pulse_moving = False
        self._pulse_next_t = None
        self._pulse_sign = 0

    def _pulse_gate(self, axis: str, want_sign: int, enable: bool, move_sec: float, stop_sec: float) -> bool:
        now = self.now_sec()
        if not enable or want_sign == 0:
            self._reset_pulse()
            return True

        if self._pulse_axis != axis or self._pulse_sign != want_sign:
            self._pulse_axis = axis
            self._pulse_sign = want_sign
            self._pulse_moving = True
            self._pulse_next_t = now + max(0.01, move_sec)
            return True

        if self._pulse_next_t is None:
            self._pulse_moving = True
            self._pulse_next_t = now + max(0.01, move_sec)
            return True

        if now < self._pulse_next_t:
            return self._pulse_moving

        # switch
        if self._pulse_moving:
            self._pulse_moving = False
            self._pulse_next_t = now + max(0.01, stop_sec)
            return False
        else:
            self._pulse_moving = True
            self._pulse_next_t = now + max(0.01, move_sec)
            return True

    def _compute_yaw_err(self, ps_base: PoseStamped) -> float:
        """
        yaw_err 계산 (목표: 마커 평면이 로봇/카메라를 정면으로 보도록 yaw만 정렬)
        - normal 모드: marker +Z(normal) 벡터를 base XY에 투영하여, 그 방향이 -X(로봇쪽)로 향하도록 맞춤
        """
        q = ps_base.pose.orientation
        qx, qy, qz, qw = float(q.x), float(q.y), float(q.z), float(q.w)

        if self.yaw_from == "quat_yaw":
            # 단순 euler yaw (환경 따라 정의가 헷갈릴 수 있음)
            siny_cosp = 2.0 * (qw * qz + qx * qy)
            cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            # 목표 yaw=0으로 본다(필요하면 이 부분을 바꿔야 함)
            return wrap_pi(yaw)

        # default: "normal"
        R = quat_to_rotmat(qx, qy, qz, qw)

        # marker +Z axis in base frame (normal vector)
        nx = R[0][2]
        ny = R[1][2]
        # nz = R[2][2]  # 참고용(roll/pitch 큰지 볼 때)

        # XY로 투영
        ang = math.atan2(ny, nx)         # normal 방향 각도
        target = math.pi                 # -X 방향의 각도(atan2(0,-1)=pi)
        yaw_err = wrap_pi(ang - target)

        # 방향이 반대면 yaw_sign=-1로 뒤집기
        yaw_err *= float(self.yaw_sign)
        return yaw_err

    # ---------- core loop ----------
    def on_timer(self):
        if not self.enabled:
            return

        if self.done_sent and self.hold_after_done:
            self.stop()
            return

        pose_ok = self._pose_fresh()
        id_ok = self._id_ok()

        if (not pose_ok) or (not id_ok):
            # 여기서는 도킹 제어 중에 "찾기 회전"을 하지 않음(원하면 따로 추가 가능)
            self.pub_cmd.publish(Twist())
            self._reset_pulse()
            return

        ps = self.last_pose
        if ps is None:
            self.stop()
            self._reset_pulse()
            return

        # base frame 변환 (이미 base면 스킵)
        if ps.header.frame_id == self.base_frame:
            ps_base = ps
        else:
            try:
                ps_base = self.tf_buffer.transform(
                    ps, self.base_frame,
                    timeout=rclpy.duration.Duration(seconds=0.15)
                )
            except TransformException:
                self.stop()
                self._reset_pulse()
                return

        x = float(ps_base.pose.position.x)
        y = float(ps_base.pose.position.y)
        z = float(ps_base.pose.position.z)

        if self.min_x_safety > 0.0 and x < self.min_x_safety:
            self.stop()
            self._reset_pulse()
            self.get_logger().warn(f"🛑 SAFETY STOP: x={x:.3f} < {self.min_x_safety:.3f}")
            return

        ex = x - self.target_dist
        ey = y - self.target_y
        ez = z - self.target_z

        # 완료 판정(기본)
        done = (abs(ex) <= self.tol_x) and (abs(ey) <= self.tol_y) and (abs(ez) <= self.tol_z)
        if done:
            self.stop()
            self._reset_pulse()
            if not self.done_sent:
                self.get_logger().info("✅ DOCK DONE -> publish /dock/done")
                self._start_done_repeat()
            return

        # ---------- Stage 1: Y 먼저 ----------
        need_y = abs(ey) > self.tol_y
        if self.stage_y_first and need_y:
            vy = clamp(self.k_y * ey, -self.max_vy, self.max_vy)
            if abs(vy) < self.min_vy:
                vy = math.copysign(self.min_vy, ey)

            want_sign = 1 if vy > 0 else -1
            moving = self._pulse_gate("y", want_sign, self.y_pulse_enable, self.y_pulse_move_sec, self.y_pulse_stop_sec)
            cmd = Twist()
            if moving:
                cmd.linear.y = float(vy)
            else:
                cmd.linear.y = 0.0
            cmd.angular.z = 0.0
            self.pub_cmd.publish(cmd)
            return

        # ---------- Stage 2: Yaw 정렬 (orientation 기반) ----------
        if self.stage_yaw_align:
            yaw_err = self._compute_yaw_err(ps_base)
            if abs(yaw_err) > self.tol_yaw:
                wz = clamp(self.k_yaw * yaw_err, -self.max_wz, self.max_wz)
                if abs(wz) < self.min_wz:
                    wz = math.copysign(self.min_wz, yaw_err)

                want_sign = 1 if wz > 0 else -1
                moving = self._pulse_gate("yaw", want_sign, self.yaw_pulse_enable, self.yaw_pulse_move_sec, self.yaw_pulse_stop_sec)

                cmd = Twist()
                cmd.linear.x = 0.0
                cmd.linear.y = 0.0
                cmd.angular.z = float(wz) if moving else 0.0
                self.pub_cmd.publish(cmd)
                return

        # ---------- Stage 3: X 접근 (pulse) ----------
        vx = clamp(self.k_x * ex, -self.max_vx, self.max_vx)
        if abs(vx) < self.min_vx:
            vx = math.copysign(self.min_vx, ex)

        want_sign = 1 if vx > 0 else -1
        moving = self._pulse_gate("x", want_sign, self.x_pulse_enable, self.x_pulse_move_sec, self.x_pulse_stop_sec)

        cmd = Twist()
        cmd.linear.x = float(vx) if moving else 0.0
        cmd.linear.y = 0.0
        cmd.angular.z = 0.0
        self.pub_cmd.publish(cmd)


def main():
    rclpy.init()
    node = DockController()
    try:
        rclpy.spin(node)
    finally:
        try:
            node.stop()
            node.destroy_node()
        except Exception:
            pass
        rclpy.shutdown()


if __name__ == "__main__":
    main()

