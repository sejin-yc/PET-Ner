#!/usr/bin/env python3
import os
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.task import Future

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int32, Float32, String
# [중요] 인터페이스 임포트 (빌드된 패키지가 있어야 함)
from catbot_interfaces.action import VlaTask  

from tf2_ros import Buffer, TransformListener
from tf2_ros import TransformException
import rclpy.time

from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy


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


class PrimitiveMissionManagerFixedPWM(Node):
    """
    고정 PWM 시스템용 미션 매니저 (Action Client 기능 추가됨)
    """

    def __init__(self):
        super().__init__("primitive_mission_manager_fixed_pwm")

        # ---------- params ----------
        self.declare_parameter("points_yaml", "")
        self.declare_parameter("mission_yaml", "")
        self.declare_parameter("auto_start", True)

        self.declare_parameter("global_frame", "map")
        self.declare_parameter("base_frame", "base_link")

        self.declare_parameter("cmd_topic", "/cmd_vel_nav")
        self.declare_parameter("allow_strafe_topic", "/gateway/allow_strafe")

        self.declare_parameter("dock_enable_topic", "/dock/enable")
        self.declare_parameter("dock_done_topic", "/dock/done")
        self.declare_parameter("dock_target_id_topic", "/dock/aruco_id")
        self.declare_parameter("dock_target_dist_topic", "/dock/target_dist")
        self.declare_parameter("dock_target_y_topic", "/dock/target_y")
        self.declare_parameter("dock_target_z_topic", "/dock/target_z")

        self.declare_parameter("arm_cmd_topic", "/arm/cmd")
        self.declare_parameter("arm_done_topic", "/arm/done")
        self.declare_parameter("servo_cmd_topic", "/servo/cmd")
        self.declare_parameter("servo_done_topic", "/servo/done")
        
        # [추가] 액션 서버 이름 파라미터
        self.declare_parameter("vla_action_server_name", "execute_vla_task")

        self.declare_parameter("control_hz", 20.0)

        self.declare_parameter("fixed_vx", 0.20)
        self.declare_parameter("fixed_vy", 0.20)
        self.declare_parameter("fixed_wz", 0.60)

        self.declare_parameter("tol_axis", 0.01)
        self.declare_parameter("tol_perp", 0.01)
        self.declare_parameter("tol_yaw", 0.05)

        self.declare_parameter("pulse_enable", True)
        self.declare_parameter("pulse_near_axis", 0.12)
        self.declare_parameter("pulse_near_yaw", 0.25)
        self.declare_parameter("pulse_on_sec", 0.12)
        self.declare_parameter("pulse_off_sec", 0.08)

        self.declare_parameter("uart_port", "/dev/ttyAMA0")
        self.declare_parameter("uart_baud", 115200)

        # ---------- read params ----------
        self.points_yaml = self.get_parameter("points_yaml").value
        self.mission_yaml = self.get_parameter("mission_yaml").value
        self.auto_start = bool(self.get_parameter("auto_start").value)

        self.global_frame = self.get_parameter("global_frame").value
        self.base_frame = self.get_parameter("base_frame").value

        self.cmd_topic = self.get_parameter("cmd_topic").value
        self.allow_strafe_topic = self.get_parameter("allow_strafe_topic").value

        self.dock_enable_topic = self.get_parameter("dock_enable_topic").value
        self.dock_done_topic = self.get_parameter("dock_done_topic").value
        self.dock_target_id_topic = self.get_parameter("dock_target_id_topic").value
        self.dock_target_dist_topic = self.get_parameter("dock_target_dist_topic").value
        self.dock_target_y_topic = self.get_parameter("dock_target_y_topic").value
        self.dock_target_z_topic = self.get_parameter("dock_target_z_topic").value

        self.arm_cmd_topic = self.get_parameter("arm_cmd_topic").value
        self.arm_done_topic = self.get_parameter("arm_done_topic").value
        self.servo_cmd_topic = self.get_parameter("servo_cmd_topic").value
        self.servo_done_topic = self.get_parameter("servo_done_topic").value
        
        self.vla_action_server_name = self.get_parameter("vla_action_server_name").value

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

        # ---------- tf ----------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ---------- pubs/subs ----------
        self.pub_cmd = self.create_publisher(Twist, self.cmd_topic, 10)
        self.pub_allow_strafe = self.create_publisher(Bool, self.allow_strafe_topic, 10)

        self.pub_dock_enable = self.create_publisher(Bool, self.dock_enable_topic, 10)
        self.pub_dock_id = self.create_publisher(Int32, self.dock_target_id_topic, 10)
        self.pub_dock_dist = self.create_publisher(Float32, self.dock_target_dist_topic, 10)
        self.pub_dock_y = self.create_publisher(Float32, self.dock_target_y_topic, 10)
        self.pub_dock_z = self.create_publisher(Float32, self.dock_target_z_topic, 10)

        self.pub_arm_cmd = self.create_publisher(String, self.arm_cmd_topic, 10)
        self.pub_servo_cmd = self.create_publisher(String, self.servo_cmd_topic, 10)
        
        # [추가] Action Client 초기화
        self._action_client = ActionClient(self, VlaTask, self.vla_action_server_name)

        qos_done = QoSProfile(depth=1)
        qos_done.reliability = QoSReliabilityPolicy.RELIABLE
        qos_done.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        self.sub_dock_done = self.create_subscription(Bool, self.dock_done_topic, self._on_dock_done, qos_done)
        self.sub_arm_done = self.create_subscription(Bool, self.arm_done_topic, self._on_arm_done, 10)
        self.sub_servo_done = self.create_subscription(Bool, self.servo_done_topic, self._on_servo_done, 10)

        # ---------- mission data ----------
        self.points = {}
        self.steps = []

        # ---------- state ----------
        self.state = "IDLE"
        self.step_i = 0
        self.step_started = False
        self.t_step0 = self.now_sec()

        # async done flags
        self.dock_done = False
        self.arm_done = False
        self.servo_done = False
        
        # [추가] Action 상태 관리용 변수
        self.action_goal_handle = None
        self.action_result_future = None
        self.action_done = False

        self.yaw_target = None
        self.rel_target = None
        self.pulse_on = True
        self.pulse_next_t = None

        self.set_allow_strafe(False)
        self.set_dock_enable(False)
        self.stop()

        self._load_yaml()

        self.timer = self.create_timer(self.dt, self.on_timer)

        if self.auto_start:
            self.start()

    # ---------- util ----------
    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def stop(self):
        self.pub_cmd.publish(Twist())

    def set_allow_strafe(self, on: bool):
        self.pub_allow_strafe.publish(Bool(data=bool(on)))

    def set_dock_enable(self, on: bool):
        self.pub_dock_enable.publish(Bool(data=bool(on)))

    def set_dock_target(self, aruco_id: int, target_dist: float, target_y: float = 0.0, target_z: float = 0.0):
        self.pub_dock_id.publish(Int32(data=int(aruco_id)))
        self.pub_dock_dist.publish(Float32(data=float(target_dist)))
        self.pub_dock_y.publish(Float32(data=float(target_y)))
        self.pub_dock_z.publish(Float32(data=float(target_z)))

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
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        ex = cy * dx + sy * dy
        ey = -sy * dx + cy * dy
        return ex, ey

    # ---------- yaml ----------
    def _load_yaml(self):
        try:
            import yaml
        except ImportError:
            raise RuntimeError("PyYAML not installed")

        if not self.mission_yaml or not os.path.exists(self.mission_yaml):
            raise RuntimeError(f"mission_yaml not found: {self.mission_yaml}")

        with open(self.mission_yaml, "r") as f:
            mission = yaml.safe_load(f)

        raw_dt = mission.get("dock_targets", {}) or {}
        self.dock_targets = {}
        if isinstance(raw_dt, dict):
            for k, v in raw_dt.items():
                try:
                    kid = int(k)
                except Exception:
                    continue
                if not isinstance(v, dict):
                    continue
                d = v.get("dist", v.get("target_dist", 0.50))
                y = v.get("y", v.get("target_y", 0.0))
                z = v.get("z", v.get("target_z", 0.0))
                self.dock_targets[kid] = {
                    "dist": float(d),
                    "y": float(y),
                    "z": float(z),
                }

        points_yaml_in_mission = (mission.get("points_yaml") or "").strip()
        points_yaml = points_yaml_in_mission if points_yaml_in_mission else (self.points_yaml or "").strip()
        if not points_yaml:
            raise RuntimeError("points_yaml is empty")

        if not os.path.isabs(points_yaml):
            base_dir = os.path.dirname(os.path.abspath(self.mission_yaml))
            points_yaml = os.path.join(base_dir, points_yaml)

        if not os.path.exists(points_yaml):
            raise RuntimeError(f"points_yaml not found: {points_yaml}")

        with open(points_yaml, "r") as f:
            pdata = yaml.safe_load(f)

        self.global_frame = str(pdata.get("frame_id", self.global_frame))

        pts = pdata.get("points", {})
        self.points = {}
        for name, v in pts.items():
            self.points[str(name)] = (float(v["x"]), float(v["y"]))

        self.steps = mission.get("steps", [])
        if not isinstance(self.steps, list) or len(self.steps) == 0:
            raise RuntimeError("mission.yaml steps empty.")

        self.get_logger().info(f"[LOAD] points={len(self.points)} from {points_yaml}")
        self.get_logger().info(f"[LOAD] steps={len(self.steps)} from {self.mission_yaml}")

    # ---------- mission control ----------
    def start(self):
        self.state = "RUNNING"
        self.step_i = 0
        self.step_started = False
        self.t_step0 = self.now_sec()
        self.dock_done = False
        self.arm_done = False
        self.servo_done = False
        # Action 상태 리셋
        self.action_done = False
        self.action_goal_handle = None
        self.action_result_future = None
        
        self.yaw_target = None
        self.rel_target = None
        self._reset_pulse()
        self.set_dock_enable(False)
        self.set_allow_strafe(False)
        self.stop()
        self.get_logger().info("MISSION START")

    def _cur_step(self):
        if 0 <= self.step_i < len(self.steps):
            return self.steps[self.step_i]
        return None

    def _step_timeout(self, step):
        return float(step.get("timeout", 30.0))

    def _advance(self):
        self.stop()
        self.set_dock_enable(False)
        self.set_allow_strafe(False)

        self.step_i += 1
        self.step_started = False
        self.t_step0 = self.now_sec()

        self.yaw_target = None
        self.rel_target = None
        
        # Action 상태 리셋
        self.action_done = False
        self.action_goal_handle = None
        self.action_result_future = None
        
        self._reset_pulse()

        if self.step_i >= len(self.steps):
            self.state = "DONE"
            self.stop()
            self.set_dock_enable(False)
            self.set_allow_strafe(False)
            self.get_logger().info("MISSION COMPLETE")
        else:
            self.get_logger().info(f"STEP[{self.step_i+1}/{len(self.steps)}] {self.steps[self.step_i]}")

    def _enter_step(self, step):
        self.t_step0 = self.now_sec()
        self._reset_pulse()

        stype = str(step.get("type", "")).strip()

        if stype == "rotate":
            pose = self.get_pose_map()
            if pose is None: return
            _, _, cyaw = pose
            if "yaw_deg" in step:
                yaw_deg = float(step.get("yaw_deg", 0.0))
                self.yaw_target = wrap_pi(math.radians(yaw_deg))
            else:
                deg = float(step.get("deg", 0.0))
                self.yaw_target = wrap_pi(cyaw + math.radians(deg))

        elif stype == "move_rel":
            pose = self.get_pose_map()
            if pose is None: return
            cx, cy, cyaw = pose
            axis = str(step.get("axis", "x")).lower()
            meters = float(step.get("meters", 0.0))
            if axis == "x":
                gx = cx + math.cos(cyaw) * meters
                gy = cy + math.sin(cyaw) * meters
            else:
                gx = cx + (-math.sin(cyaw)) * meters
                gy = cy + ( math.cos(cyaw)) * meters
            self.rel_target = (gx, gy)

        elif stype == "dock":
            self.dock_done = False
            aruco_id = int(step.get("aruco_id", -1))
            cfg = self.dock_targets.get(aruco_id, {}) if hasattr(self, "dock_targets") else {}
            base_dist = float(cfg.get("dist", 0.50))
            base_y = float(cfg.get("y", 0.0))
            base_z = float(cfg.get("z", 0.0))

            if "target_dist" in step or "dist" in step:
                target_dist = float(step.get("target_dist", step.get("dist", base_dist)))
            else: target_dist = base_dist

            if "target_y" in step or "y" in step:
                target_y = float(step.get("target_y", step.get("y", base_y)))
            else: target_y = base_y

            if "target_z" in step or "z" in step:
                target_z = float(step.get("target_z", step.get("z", base_z)))
            else: target_z = base_z

            self.set_dock_target(aruco_id, target_dist, target_y, target_z)
            self.set_allow_strafe(True)
            self.set_dock_enable(True)
            self.stop()
            self.get_logger().info(f"DOCK START id={aruco_id} dist={target_dist:.2f} y={target_y:+.3f} z={target_z:+.3f}")

        elif stype == "arm":
            self.arm_done = False
            cmd = str(step.get("cmd", "")).strip()
            if cmd:
                self.pub_arm_cmd.publish(String(data=cmd))
                self.get_logger().info(f"ARM CMD: {cmd}")

        elif stype == "servo":
            self.servo_done = False
            cmd = str(step.get("cmd", "")).strip()
            if cmd:
                self.pub_servo_cmd.publish(String(data=cmd))
                self.get_logger().info(f"SERVO CMD: {cmd}")

        # --- [추가] Action Step 처리 ---
        elif stype == "action":
            self.action_done = False
            task_type = str(step.get("task", "")).strip()
            
            if not task_type:
                self.get_logger().error("Action step에 'task' 필드가 없습니다.")
                self.action_done = True # 건너뛰기
                return

            self.get_logger().info(f"ACTION SEND: {task_type}")
            
            # 액션 서버 연결 확인
            if not self._action_client.wait_for_server(timeout_sec=5.0):
                self.get_logger().error("액션 서버를 찾을 수 없습니다!")
                # 실패 처리하거나 다음 스텝으로 넘어갈 수 있음
                return

            goal_msg = VlaTask.Goal()
            goal_msg.task_type = task_type
            
            self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self._action_feedback_callback)
            self._send_goal_future.add_done_callback(self._action_goal_response_callback)

    # ---------- callbacks ----------
    def _on_dock_done(self, msg: Bool):
        if msg.data: self.dock_done = True
    def _on_arm_done(self, msg: Bool):
        if msg.data: self.arm_done = True
    def _on_servo_done(self, msg: Bool):
        if msg.data: self.servo_done = True

    # --- [추가] Action Callbacks ---
    def _action_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('액션 요청이 거부되었습니다.')
            self.action_done = True # 중단 또는 다음으로
            return

        self.get_logger().info('액션 요청 승인됨. 실행 중...')
        self.action_goal_handle = goal_handle
        
        self.action_result_future = goal_handle.get_result_async()
        self.action_result_future.add_done_callback(self._action_get_result_callback)

    def _action_get_result_callback(self, future):
        try:
            result = future.result().result
            status = future.result().status
            if result.success:
                self.get_logger().info(f"Action 성공: {result.message}")
            else:
                self.get_logger().error(f"Action 실패: {result.message}")
        except Exception as e:
            self.get_logger().error(f"Action 결과 수신 중 에러: {e}")
        
        self.action_done = True  # 메인 루프에 완료 신호 전달

    def _action_feedback_callback(self, feedback_msg):
        # 피드백 로그 (필요 시 주석 해제)
        # feedback = feedback_msg.feedback
        # self.get_logger().info(f"Action Feedback: {feedback.status}")
        pass

    # ---------- core loop ----------
    def on_timer(self):
        if self.state in ("IDLE", "DONE"):
            return

        step = self._cur_step()
        if step is None:
            self.state = "DONE"
            self.stop()
            return

        if not self.step_started:
            self.step_started = True
            self._enter_step(step)

        # 타임아웃 체크 (액션 포함)
        if (self.now_sec() - self.t_step0) > self._step_timeout(step):
            self.get_logger().error(f"STEP TIMEOUT -> 미션 중단. step={step}")
            
            # 액션이 실행 중이었다면 취소 요청
            if step.get("type") == "action" and self.action_goal_handle:
                 self.get_logger().warn("실행 중인 액션 취소 요청...")
                 self.action_goal_handle.cancel_goal_async()

            self.state = "DONE"
            self.stop()
            self.set_dock_enable(False)
            self.set_allow_strafe(False)
            return

        stype = str(step.get("type", "")).strip()

        # 비동기 작업 대기 (Dock, Arm, Servo)
        if stype == "dock":
            if self.dock_done:
                self.get_logger().info("DOCK DONE")
                self.set_dock_enable(False)
                self.set_allow_strafe(False)
                self._advance()
            else:
                self.stop()
            return

        if stype == "arm":
            if self.arm_done:
                self.get_logger().info("ARM DONE")
                self._advance()
            return

        # [수정] Servo 15초 대기 로직 추가
        if stype == "servo":
            # 1. 실제 하드웨어에서 완료 신호가 오면 즉시 통과
            if self.servo_done:
                self.get_logger().info("SERVO DONE (Signal Received)")
                self._advance()
                return
            
            # 2. 신호가 없어도 15초가 지나면 강제로 통과 (Sleep 효과)
            if (self.now_sec() - self.t_step0) >= 15.0:
                self.get_logger().info("SERVO DONE (15s Time Passed)")
                self._advance()
            return
            
        # --- [추가] Action 완료 체크 ---
        if stype == "action":
            if self.action_done:
                self.get_logger().info("ACTION STEP 완료")
                self._advance()
            return

        # --- [추가] Sleep 완료 체크 (여기!! 중요) ---
        if stype == "sleep":
            duration = float(step.get("duration", 1.0))
            if (self.now_sec() - self.t_step0) >= duration:
                self.get_logger().info(f"SLEEP DONE ({duration}s)")
                self._advance()
            return

        # ... (이하 기존 이동 로직: goto, move_rel, rotate 유지) ...
        
        # 1) pose 필요
        pose = self.get_pose_map()
        if pose is None:
            self.stop()
            return

        cx, cy, cyaw = pose

        # ---- GOTO ----
        if stype == "goto":
            point = str(step["point"])
            axis = str(step.get("axis", "auto")).lower()
            tol_axis = float(step.get("tol_axis", self.tol_axis))
            tol_perp = float(step.get("tol_perp", self.tol_perp))

            if point not in self.points:
                self.get_logger().error(f"Unknown point: {point}")
                self.state = "DONE"
                self.stop()
                return

            gx, gy = self.points[point]
            dx = gx - cx
            dy = gy - cy
            ex, ey = self.map_err_to_base(dx, dy, cyaw)

            if axis == "auto":
                axis = "x" if abs(ex) >= abs(ey) else "y"
            if axis not in ("x", "y"): axis = "x"

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

            if abs(e_axis) <= tol_axis and abs(e_perp) <= tol_perp:
                self.stop()
                self._advance()
                return

            if abs(e_axis) < self.pulse_near_axis: on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True

            cmd = Twist()
            if not on:
                self.pub_cmd.publish(cmd)
                return

            if axis == "x": cmd.linear.x = sgn(e_axis) * abs(cmd_val)
            else: cmd.linear.y = sgn(e_axis) * abs(cmd_val)
            cmd.angular.z = 0.0
            self.pub_cmd.publish(cmd)
            return

        # ---- MOVE_REL ----
        if stype == "move_rel":
            axis = str(step.get("axis", "x")).lower()
            tol_axis = float(step.get("tol_axis", self.tol_axis))
            tol_perp = float(step.get("tol_perp", self.tol_perp))
            if axis not in ("x", "y"): axis = "x"

            if self.rel_target is None:
                self._enter_step(step)
                if self.rel_target is None:
                    self.stop()
                    return

            gx, gy = self.rel_target
            dx = gx - cx
            dy = gy - cy
            ex, ey = self.map_err_to_base(dx, dy, cyaw)

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

            if abs(e_axis) <= tol_axis and abs(e_perp) <= tol_perp:
                self.stop()
                self._advance()
                return

            if abs(e_axis) < self.pulse_near_axis: on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True

            cmd = Twist()
            if not on:
                self.pub_cmd.publish(cmd)
                return

            if axis == "x": cmd.linear.x = sgn(e_axis) * abs(cmd_val)
            else: cmd.linear.y = sgn(e_axis) * abs(cmd_val)
            cmd.angular.z = 0.0
            self.pub_cmd.publish(cmd)
            return

        # ---- ROTATE ----
        if stype == "rotate":
            tol_yaw = float(step.get("tol_yaw", self.tol_yaw))
            if self.yaw_target is None:
                self._enter_step(step)
                if self.yaw_target is None:
                    self.stop()
                    return

            yaw_err = wrap_pi(self.yaw_target - cyaw)

            if abs(yaw_err) <= tol_yaw:
                self.stop()
                self.set_allow_strafe(False)
                self._advance()
                return

            if abs(yaw_err) < self.pulse_near_yaw: on = self._pulse_update()
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

        # unknown
        self.get_logger().error(f"Unknown step type: {stype}")
        self.state = "DONE"
        self.stop()
        self.set_dock_enable(False)
        self.set_allow_strafe(False)


def main():
    rclpy.init()
    node = PrimitiveMissionManagerFixedPWM()
    try:
        rclpy.spin(node)
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()