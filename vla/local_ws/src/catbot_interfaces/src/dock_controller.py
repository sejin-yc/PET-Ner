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


class DockController(Node):
    """
    /aruco/pose + /aruco/id 기반 도킹 컨트롤러

    핵심:
    - 회전(wz) 금지(기본): cmd.angular.z = 0
    - 목표: (target_dist, target_y, target_z)
    - ✅ Y(횡이동) 먼저 정렬 → X(전/후진) 접근
    - ✅ X 접근은 펄스(짧게 이동 후 정지) 옵션 지원 (고정 PWM 시스템에 유리)
    - done는 transient_local + 반복 송신
    """

    def __init__(self):
        super().__init__("dock_controller")

        # ---------------- params: topics ----------------
        self.declare_parameter("aruco_pose_topic", "/aruco/pose")
        self.declare_parameter("aruco_id_topic", "/aruco/id")

        self.declare_parameter("cmd_topic", "/cmd_vel_aruco")
        self.declare_parameter("enable_topic", "/dock/enable")
        self.declare_parameter("done_topic", "/dock/done")

        self.declare_parameter("target_id_topic", "/dock/aruco_id")
        self.declare_parameter("target_dist_topic", "/dock/target_dist")
        self.declare_parameter("target_y_topic", "/dock/target_y")
        self.declare_parameter("target_z_topic", "/dock/target_z")

        # ---------------- params: frames ----------------
        self.declare_parameter("base_frame", "base_link")

        # ---------------- params: control ----------------
        self.declare_parameter("control_hz", 20.0)

        self.declare_parameter("k_x", 0.8)
        self.declare_parameter("k_y", 0.8)

        self.declare_parameter("max_vx", 0.18)
        self.declare_parameter("max_vy", 0.18)

        # ✅ 최소 속도(게이트웨이 deadband/정지마찰 방지)
        self.declare_parameter("min_vx", 0.10)
        self.declare_parameter("min_vy", 0.10)

        # ---------------- params: tolerances ----------------
        self.declare_parameter("tol_x", 0.03)  # m
        self.declare_parameter("tol_y", 0.03)  # m
        self.declare_parameter("tol_z", 0.25)  # m (완료판정용, 로봇은 z로 못 움직임)

        # ---------------- params: freshness / search ----------------
        self.declare_parameter("pose_timeout", 1.0)
        self.declare_parameter("id_timeout", 1.0)

        self.declare_parameter("search_rotate", False)
        self.declare_parameter("wz_search", 0.25)

        # ---------------- params: done robustness ----------------
        self.declare_parameter("done_repeat_sec", 2.0)
        self.declare_parameter("done_repeat_hz", 20.0)
        self.declare_parameter("hold_after_done", True)

        # ---------------- ✅ params: staged control ----------------
        # Y 먼저 정렬한 뒤 X 접근
        self.declare_parameter("stage_y_first", True)

        # X 접근 펄스(고정 PWM에서 과전진 방지에 매우 도움)
        self.declare_parameter("x_pulse_enable", True)
        self.declare_parameter("x_pulse_move_sec", 0.20)  # 전진/후진을 이 시간만큼
        self.declare_parameter("x_pulse_stop_sec", 0.20)  # 그 다음 정지해서 pose 업데이트 기다림

        # Y 정렬도 펄스로 하고 싶으면 ON (기본은 연속 정렬)
        self.declare_parameter("y_pulse_enable", True)
        self.declare_parameter("y_pulse_move_sec", 0.20)
        self.declare_parameter("y_pulse_stop_sec", 0.10)

        # ✅ 안전거리 가드: x가 이 값보다 작아지면(너무 가까움) 무조건 정지(벽 박기 방지)
        # target_dist=0.30이면 보통 0.20~0.25 권장
        self.declare_parameter("min_x_safety", 0.28)

        # ---------------- read params ----------------
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

        self.tol_x = float(self.get_parameter("tol_x").value)
        self.tol_y = float(self.get_parameter("tol_y").value)
        self.tol_z = float(self.get_parameter("tol_z").value)

        self.pose_timeout = float(self.get_parameter("pose_timeout").value)
        self.id_timeout = float(self.get_parameter("id_timeout").value)

        self.search_rotate = bool(self.get_parameter("search_rotate").value)
        self.wz_search = float(self.get_parameter("wz_search").value)

        self.done_repeat_sec = float(self.get_parameter("done_repeat_sec").value)
        self.done_repeat_hz = float(self.get_parameter("done_repeat_hz").value)
        self.hold_after_done = bool(self.get_parameter("hold_after_done").value)

        self.stage_y_first = bool(self.get_parameter("stage_y_first").value)

        self.x_pulse_enable = bool(self.get_parameter("x_pulse_enable").value)
        self.x_pulse_move_sec = float(self.get_parameter("x_pulse_move_sec").value)
        self.x_pulse_stop_sec = float(self.get_parameter("x_pulse_stop_sec").value)

        self.y_pulse_enable = bool(self.get_parameter("y_pulse_enable").value)
        self.y_pulse_move_sec = float(self.get_parameter("y_pulse_move_sec").value)
        self.y_pulse_stop_sec = float(self.get_parameter("y_pulse_stop_sec").value)

        self.min_x_safety = float(self.get_parameter("min_x_safety").value)

        # min이 max보다 크면 의미 없어서 보정
        self.min_vx = max(0.0, min(self.min_vx, self.max_vx))
        self.min_vy = max(0.0, min(self.min_vy, self.max_vy))

        # ---------------- tf ----------------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ---------------- QoS ----------------
        self.qos_default = QoSProfile(depth=10)
        self.qos_default.reliability = QoSReliabilityPolicy.RELIABLE
        self.qos_default.durability = QoSDurabilityPolicy.VOLATILE

        self.qos_done = QoSProfile(depth=1)
        self.qos_done.reliability = QoSReliabilityPolicy.RELIABLE
        self.qos_done.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL

        # ---------------- pubs/subs ----------------
        self.pub_cmd = self.create_publisher(Twist, self.cmd_topic, self.qos_default)
        self.pub_done = self.create_publisher(Bool, self.done_topic, self.qos_done)

        self.sub_pose = self.create_subscription(PoseStamped, self.pose_topic, self.cb_pose, self.qos_default)
        self.sub_id = self.create_subscription(Int32, self.id_topic, self.cb_id, self.qos_default)

        self.sub_enable = self.create_subscription(Bool, self.enable_topic, self.cb_enable, self.qos_default)
        self.sub_target_id = self.create_subscription(Int32, self.target_id_topic, self.cb_target_id, self.qos_default)
        self.sub_target_dist = self.create_subscription(Float32, self.target_dist_topic, self.cb_target_dist, self.qos_default)
        self.sub_target_y = self.create_subscription(Float32, self.target_y_topic, self.cb_target_y, self.qos_default)
        self.sub_target_z = self.create_subscription(Float32, self.target_z_topic, self.cb_target_z, self.qos_default)

        # ---------------- state ----------------
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

        # 펄스 상태 (x/y 공용)
        self._pulse_axis = None          # "x" or "y"
        self._pulse_moving = False
        self._pulse_next_t = None
        self._pulse_sign = 0             # 방향 바뀌면 리셋하려고

        self.timer = self.create_timer(self.dt, self.on_timer)

        self.get_logger().info(
            f"DockController staged: y_first={self.stage_y_first} "
            f"x_pulse={self.x_pulse_enable} (move={self.x_pulse_move_sec:.2f}s stop={self.x_pulse_stop_sec:.2f}s) "
            f"min_vx={self.min_vx:.2f} min_vy={self.min_vy:.2f} min_x_safety={self.min_x_safety:.2f}"
        )

    # ---------------- callbacks ----------------
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
            # disable: 한 번 정지 보내고 이후 publish 중단(트위스트먹스 timeout으로 우선순위 풀리게)
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

    # ---------------- helpers ----------------
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

    # ---- pulse helpers ----
    def _reset_pulse(self):
        self._pulse_axis = None
        self._pulse_moving = False
        self._pulse_next_t = None
        self._pulse_sign = 0

    def _pulse_gate(self, axis: str, want_sign: int, enable: bool, move_sec: float, stop_sec: float) -> bool:
        """
        return True if "move command" should be published now, False if "stop" should be published now.
        - axis: "x" or "y"
        - want_sign: -1 or +1 (direction), 0 means no move -> resets
        """
        now = self.now_sec()

        if not enable or want_sign == 0:
            self._reset_pulse()
            return True  # gating off -> caller uses continuous cmd (or stop)

        # 축/방향 바뀌면 펄스 상태 리셋 후 move부터 시작
        if self._pulse_axis != axis or self._pulse_sign != want_sign:
            self._pulse_axis = axis
            self._pulse_sign = want_sign
            self._pulse_moving = True
            self._pulse_next_t = now + max(0.01, move_sec)
            return True

        # 타이밍에 따라 move/stop 토글
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

    # ---------------- core loop ----------------
    def on_timer(self):
        if not self.enabled:
            return

        if self.done_sent and self.hold_after_done:
            self.stop()
            return

        pose_ok = self._pose_fresh()
        id_ok = self._id_ok()

        if (not pose_ok) or (not id_ok):
            # 마커 못 보거나 id 불일치면 정지(또는 search_rotate)
            cmd = Twist()
            if self.search_rotate and (not pose_ok or not id_ok):
                cmd.angular.z = float(self.wz_search)
            self.pub_cmd.publish(cmd)
            self._reset_pulse()
            return

        ps = self.last_pose
        if ps is None:
            self.stop()
            self._reset_pulse()
            return

        # base frame으로 변환 (이미 base면 스킵)
        if ps.header.frame_id == self.base_frame:
            ps_base = ps
        else:
            try:
                ps_base = self.tf_buffer.transform(
                    ps,
                    self.base_frame,
                    timeout=rclpy.duration.Duration(seconds=0.15)
                )
            except TransformException:
                self.stop()
                self._reset_pulse()
                return

        x = float(ps_base.pose.position.x)
        y = float(ps_base.pose.position.y)
        z = float(ps_base.pose.position.z)

        # ✅ 안전 가드: 너무 가까워지면 무조건 정지 (벽 박기 방지)
        if self.min_x_safety > 0.0 and x < self.min_x_safety:
            self.stop()
            self._reset_pulse()
            self.get_logger().warn(f"🛑 SAFETY STOP: x={x:.3f} < min_x_safety={self.min_x_safety:.3f}")
            return

        ex = x - self.target_dist
        ey = y - self.target_y
        ez = z - self.target_z

        # 완료 판정
        done = (abs(ex) <= self.tol_x) and (abs(ey) <= self.tol_y) and (abs(ez) <= self.tol_z)
        if done:
            self.stop()
            self._reset_pulse()
            if not self.done_sent:
                self.get_logger().info("✅ DOCK DONE -> publish /dock/done (robust)")
                self._start_done_repeat()
            return

        # ---------------- staged control ----------------
        # 1) y 먼저 정렬(횡이동)
        need_y = abs(ey) > self.tol_y
        need_x = abs(ex) > self.tol_x

        vx = 0.0
        vy = 0.0

        if self.stage_y_first and need_y:
            # Y 정렬 단계
            vy = clamp(self.k_y * ey, -self.max_vy, self.max_vy)

            # tol 밖이면 min_vy 보장(게이트웨이 deadband 방지)
            if abs(vy) < self.min_vy and self.min_vy > 0.0:
                vy = math.copysign(self.min_vy, ey)

            # 펄스 게이팅(옵션)
            want_sign = 1 if vy > 0 else (-1 if vy < 0 else 0)
            moving_now = self._pulse_gate("y", want_sign, self.y_pulse_enable, self.y_pulse_move_sec, self.y_pulse_stop_sec)
            if not moving_now:
                vy = 0.0

        else:
            # X 접근 단계 (y는 tol 내라고 가정 or y_first=False일 때도 여기로 올 수 있음)
            if need_x:
                vx = clamp(self.k_x * ex, -self.max_vx, self.max_vx)

                # tol 밖이면 min_vx 보장
                if abs(vx) < self.min_vx and self.min_vx > 0.0:
                    vx = math.copysign(self.min_vx, ex)

                # ✅ X는 기본 펄스 접근(과전진/벽박기 방지에 매우 도움)
                want_sign = 1 if vx > 0 else (-1 if vx < 0 else 0)
                moving_now = self._pulse_gate("x", want_sign, self.x_pulse_enable, self.x_pulse_move_sec, self.x_pulse_stop_sec)
                if not moving_now:
                    vx = 0.0
            else:
                # x도 필요 없으면(거의 done인데 z 때문에) 안전하게 정지
                self._reset_pulse()

        cmd = Twist()
        cmd.linear.x = float(vx)
        cmd.linear.y = float(vy)
        cmd.angular.z = 0.0  # 회전 금지
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
