# ROS 쪽 "명령" 흐름: cmd_vel_teleop / /cmd_vel → mux → cmd_vel_out → UART.
# CmdVelMux, ControlTopicBridge, PatrolLoop(액션 실행), RosCmdVelBridge(UART 전송).

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Twist, Vector3
from std_msgs.msg import String, Bool, UInt8
from tf2_ros import Buffer, TransformListener, TransformException
import rclpy.time

# 로봇팔 Action 인터페이스 (catbot_interfaces 패키지 필요)
try:
    from catbot_interfaces.action import VlaTask
    CATBOT_INTERFACES_AVAILABLE = True
except ImportError:
    CATBOT_INTERFACES_AVAILABLE = False
    VlaTask = None

from src.uart_frames import (
    make_cmd_vel_frame, make_estop_frame, make_feed_frame, make_heartbeat_frame,
    make_arm_start_frame, make_arm_position_correct_frame, make_arm_water_frame,
    make_churu_frame
)
from src.uart_link import UartLink


# ---------- Patrol (Nav2 연동, 액션 실행만 담당) ----------
@dataclass
class PatrolSegment:
    """패턴 한 구간. duration_s 동안 (vx_mps, wz_rps) 유지."""
    duration_s: float
    vx_mps: float
    wz_rps: float

@dataclass
class PatrolActionSchedule:
    """패트롤 중 액션 스케줄 설정."""
    litter_clean_every_patrol: bool = True  # 변치우기: 매번 순찰할 때마다 실행 (True) 또는 비활성화 (False)
    feed_every_patrol: bool = True          # 급식: 매번 순찰할 때마다 실행 (True) 또는 비활성화 (False)
    feed_level: int = 2                      # 급식 레벨 (1~3)
    water_every_patrol: bool = False         # 급수: 매번 순찰할 때마다 실행 (True) 또는 비활성화 (False)

@dataclass
class PatrolConfig:
    """패턴(segments) + 주기 실행. Nav2/SLAM 전에는 이걸로, 붙은 뒤엔 cmd_vel_auto만 유지."""
    rate_hz: float = 30.0
    segments: List[PatrolSegment] | None = None
    action_schedule: PatrolActionSchedule | None = None

    def __post_init__(self):
        if self.segments is None:
            self.segments = [
                PatrolSegment(duration_s=2.0, vx_mps=0.15, wz_rps=0.0),
                PatrolSegment(duration_s=1.2, vx_mps=0.0, wz_rps=0.7),
            ]
        if self.action_schedule is None:
            self.action_schedule = PatrolActionSchedule()

class PatrolProfile:
    """경과 시간 기준으로 구간 재생, (vx, wz) 내보냄."""
    def __init__(self, cfg: PatrolConfig):
        if not cfg.segments:
            raise ValueError("PatrolConfig.segments must not be empty")
        self.cfg = cfg
        self._seg_idx = 0
        self._seg_elapsed = 0.0

    def reset(self) -> None:
        self._seg_idx = 0
        self._seg_elapsed = 0.0

    def step(self, dt: float) -> Tuple[float, float]:
        if dt < 0:
            dt = 0.0
        self._seg_elapsed += dt
        seg = self.cfg.segments[self._seg_idx]
        while self._seg_elapsed >= seg.duration_s and seg.duration_s > 0:
            self._seg_elapsed -= seg.duration_s
            self._seg_idx = (self._seg_idx + 1) % len(self.cfg.segments)
            seg = self.cfg.segments[self._seg_idx]
        return seg.vx_mps, seg.wz_rps

class PatrolActionScheduler:
    """패트롤 중 액션 스케줄러. Nav2 신호를 받아서 액션 실행."""
    def __init__(self, schedule: PatrolActionSchedule, uart: UartLink, job_event_callback=None, use_nav2_signals: bool = True, feed_bridge=None):
        self.schedule = schedule
        self.uart = uart
        self.job_event_callback = job_event_callback  # 작업 이벤트 콜백 함수
        self.use_nav2_signals = use_nav2_signals  # Nav2 신호 사용 여부 (기본값: True)
        self.feed_bridge = feed_bridge  # FeedControlBridge 참조
        self._litter_clean_executed_this_patrol = False  # 이번 순찰에서 변 치우기 실행 여부
        self._feed_executed_this_patrol = False  # 이번 순찰에서 급식 실행 여부
        self._water_executed_this_patrol = False  # 이번 순찰에서 물 급수 실행 여부
        # Nav2 모드: 아루코 정렬 대기 상태
        self._waiting_for_aruco = False  # 아루코 정렬 대기 중인지
        self._pending_action = None  # 대기 중인 액션 타입
        self._pending_waypoint_id = None  # 대기 중인 waypoint ID
        # 급식: 젯슨이 사료 량 계산 대기 상태
        self._waiting_for_feed_amount = False  # 젯슨이 사료 량 계산 중인지
        self._pending_feed_waypoint_id = None  # 대기 중인 급식 waypoint ID
    
    def update_schedule(self, schedule: PatrolActionSchedule):
        """스케줄 업데이트 (웹에서 설정 변경 시)."""
        self.schedule = schedule
        # 다음 순찰에서 다시 실행 가능하도록 리셋
        self._litter_clean_executed_this_patrol = False
        self._feed_executed_this_patrol = False
        self._water_executed_this_patrol = False
    
    def tick(self, now: float):
        """패트롤 중 호출. Nav2 신호 사용 시에는 신호 대기, 아니면 자동 실행."""
        # Nav2 신호 사용 시에는 tick에서 자동 실행하지 않음 (Nav2 신호로 실행)
        if self.use_nav2_signals:
            return
        
        # Nav2 없이 동작: 매번 순찰할 때마다 자동 실행
        # 변치우기: 매번 순찰할 때마다 (ID_ARM_START, action_id=1: 변 치우기 시작)
        if self.schedule.litter_clean_every_patrol and not self._litter_clean_executed_this_patrol:
            try:
                frame = make_arm_start_frame(1)  # action_id=1: 변 치우기 시작
                self.uart.send(frame)
                self._litter_clean_executed_this_patrol = True
                print(f"[PatrolAction] Litter clean triggered (every patrol)")
                # 작업 이벤트 콜백 호출
                if self.job_event_callback:
                    self.job_event_callback("litter_clean", "in_progress")
            except Exception as e:
                print(f"[PatrolAction] Litter clean failed: {e}")
                # 작업 실패 이벤트
                if self.job_event_callback:
                    self.job_event_callback("litter_clean", "failed", reason=str(e))
        
        # 급식: 매번 순찰할 때마다 (ID_FEED)
        if self.schedule.feed_every_patrol and not self._feed_executed_this_patrol:
            try:
                from src.uart_frames import make_feed_frame
                feed_level = self.schedule.feed_level  # 1~3
                frame = make_feed_frame(feed_level)  # 급식 (STM32 서보모터가 개폐통 열어서 급식)
                self.uart.send(frame)
                self._feed_executed_this_patrol = True
                print(f"[PatrolAction] Feed triggered (every patrol, level={feed_level})")
                # 작업 이벤트 콜백 호출
                if self.job_event_callback:
                    self.job_event_callback("feed", "in_progress")
            except Exception as e:
                print(f"[PatrolAction] Feed failed: {e}")
                # 작업 실패 이벤트
                if self.job_event_callback:
                    self.job_event_callback("feed", "failed", reason=str(e))
        
        # 급수: 매번 순찰할 때마다 (ID_ARM_WATER, action=1: 급수 시작)
        if self.schedule.water_every_patrol and not self._water_executed_this_patrol:
            try:
                frame = make_arm_water_frame(1)  # action=1: 급수 시작 (강화학습 로봇팔이 자율로 수행)
                self.uart.send(frame)
                self._water_executed_this_patrol = True
                print(f"[PatrolAction] Water triggered (every patrol)")
                # 작업 이벤트 콜백 호출
                if self.job_event_callback:
                    self.job_event_callback("water", "in_progress")
            except Exception as e:
                print(f"[PatrolAction] Water failed: {e}")
                # 작업 실패 이벤트
                if self.job_event_callback:
                    self.job_event_callback("water", "failed", reason=str(e))
    
    def reset_patrol(self):
        """순찰이 새로 시작될 때 호출 (플래그 리셋)."""
        self._litter_clean_executed_this_patrol = False
        self._feed_executed_this_patrol = False
        self._water_executed_this_patrol = False
        self._waiting_for_aruco = False
        self._pending_action = None
        self._pending_waypoint_id = None
    
    def execute_action(self, action_type: str, waypoint_id: str, action_complete_callback=None):
        """Nav2 신호를 받아서 액션을 실행. action_complete_callback(action_type, waypoint_id, status) 호출."""
        try:
            if action_type == "litter_clean":
                frame = make_arm_start_frame(1)  # action_id=1: 변 치우기 시작
                self.uart.send(frame)
                print(f"[PatrolAction] Litter clean executed (waypoint: {waypoint_id})")
                if self.job_event_callback:
                    self.job_event_callback("litter_clean", "in_progress")
                # 완료는 젯슨에서 arm/job_complete로 오면 처리됨
                # 여기서는 성공으로 간주하고 Nav2에 신호 발행 (실제 완료는 UART STATUS로 확인)
                if action_complete_callback:
                    action_complete_callback("litter_clean", waypoint_id, "success")
            
            elif action_type == "feed":
                # 급식은 젯슨이 사료 량을 계산해야 함
                # FeedControlBridge가 feed/request 토픽을 발행하여 젯슨에 알림
                # 젯슨이 feed/amount 토픽을 발행할 때까지 대기
                print(f"[PatrolAction] Feed requested (waypoint: {waypoint_id}), waiting for Jetson feed/amount...")
                self._waiting_for_feed_amount = True
                self._pending_feed_waypoint_id = waypoint_id
                if self.job_event_callback:
                    self.job_event_callback("feed", "in_progress")
                # FeedControlBridge에 급식 요청 전달 (feed/request 토픽 발행)
                if self.feed_bridge is not None:
                    self.feed_bridge.request_feed(waypoint_id)
                else:
                    print(f"[PatrolAction] WARNING: FeedControlBridge not available, cannot request feed")
                    if action_complete_callback:
                        action_complete_callback("feed", waypoint_id, "failed")
                # 실제 실행은 FeedControlBridge가 feed/amount 토픽을 받으면 처리
                # action_complete_callback은 FeedControlBridge에서 호출
            
            elif action_type == "water":
                frame = make_arm_water_frame(1)  # action=1: 급수 시작
                self.uart.send(frame)
                print(f"[PatrolAction] Water executed (waypoint: {waypoint_id})")
                if self.job_event_callback:
                    self.job_event_callback("water", "in_progress")
                # 완료는 젯슨에서 arm/job_complete로 오면 처리됨
                if action_complete_callback:
                    action_complete_callback("water", waypoint_id, "success")
            
            else:
                print(f"[PatrolAction] Unknown action type: {action_type}")
                if action_complete_callback:
                    action_complete_callback(action_type, waypoint_id, "failed")
        
        except Exception as e:
            print(f"[PatrolAction] Action execution failed: {e}")
            if self.job_event_callback:
                self.job_event_callback(action_type, "failed", reason=str(e))
            if action_complete_callback:
                action_complete_callback(action_type, waypoint_id, "failed")

# ---------- Homing Controller (수동→자동 전환 시 홈 이동) ----------
def wrap_pi(a):
    """각도를 [-π, π] 범위로 정규화."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a

def yaw_from_quat(qx, qy, qz, qw):
    """쿼터니언에서 yaw 각도 추출."""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)

def sgn(x: float) -> float:
    """부호 함수."""
    if x > 0.0:
        return 1.0
    if x < 0.0:
        return -1.0
    return 0.0

class HomingController:
    """
    홈 위치로 이동하는 컨트롤러.
    수동→자동 전환 시 자동으로 실행되어 홈 위치로 이동 후 순찰 시작.
    
    Y축 우선 정렬 후 X축 이동, 마지막으로 회전.
    원래 homing.py 로직 그대로 반영.
    """
    def __init__(self, node: Node, home_x: float = 1.2, home_y: float = 1.7, home_yaw_deg: float = -180.0,
                 control_hz: float = 20.0, fixed_vx: float = 0.20, fixed_vy: float = 0.20, fixed_wz: float = 0.60,
                 tol_axis: float = 0.03, tol_perp: float = 0.06, tol_yaw: float = 0.05,
                 goto_timeout: float = 60.0, rotate_timeout: float = 20.0,
                 pulse_enable: bool = True, pulse_near_axis: float = 0.12, pulse_near_yaw: float = 0.25,
                 pulse_on_sec: float = 0.12, pulse_off_sec: float = 0.08):
        self.node = node
        self.home_x = float(home_x)
        self.home_y = float(home_y)
        self.home_yaw = wrap_pi(math.radians(float(home_yaw_deg)))
        
        self.dt = 1.0 / max(1.0, float(control_hz))
        self.fixed_vx = float(fixed_vx)
        self.fixed_vy = float(fixed_vy)
        self.fixed_wz = float(fixed_wz)
        
        self.tol_axis = float(tol_axis)
        self.tol_perp = float(tol_perp)
        self.tol_yaw = float(tol_yaw)
        
        self.goto_timeout = float(goto_timeout)
        self.rotate_timeout = float(rotate_timeout)
        
        # Pulse 설정
        self.pulse_enable = bool(pulse_enable)
        self.pulse_near_axis = float(pulse_near_axis)
        self.pulse_near_yaw = float(pulse_near_yaw)
        self.pulse_on_sec = float(pulse_on_sec)
        self.pulse_off_sec = float(pulse_off_sec)
        self.pulse_on = True
        self.pulse_next_t = None
        
        # TF
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, node)
        self.global_frame = "map"
        self.base_frame = "base_link"
        
        # 상태
        self.state = "IDLE"  # IDLE -> GOTO -> ROTATE -> DONE
        self.t0 = self.now_sec()
        self.active = False
        
        # 발행자
        # 홈 이동 명령은 /cmd_vel_nav로 발행하여 CmdVelMux가 통합하도록 함
        self.pub_cmd = node.create_publisher(Twist, "/cmd_vel_nav", 10)
        self.pub_allow_strafe = node.create_publisher(Bool, "/gateway/allow_strafe", 10)
        
        # 타이머
        self.timer = node.create_timer(self.dt, self.on_timer)
        
        node.get_logger().info(
            f"HomingController initialized: home=({self.home_x:.3f},{self.home_y:.3f}), "
            f"yaw_deg={home_yaw_deg:.1f} (abs), Y-First Priority"
        )
    
    def now_sec(self):
        """현재 시간 (초)."""
        return self.node.get_clock().now().nanoseconds * 1e-9
    
    def _reset_pulse(self):
        """Pulse 상태 리셋."""
        self.pulse_on = True
        self.pulse_next_t = None
    
    def _pulse_update(self) -> bool:
        """Pulse 업데이트 (가까워지면 펄스 모드)."""
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
    
    def start(self):
        """홈 이동 시작."""
        self.state = "GOTO"
        self.t0 = self.now_sec()
        self.active = True
        self._reset_pulse()
        self.node.get_logger().info("HOMING START (GOTO -> ROTATE)")
    
    def stop(self):
        """홈 이동 중지."""
        self.active = False
        self.state = "IDLE"
        self.pub_cmd.publish(Twist())
        self.pub_allow_strafe.publish(Bool(data=False))
    
    def is_done(self) -> bool:
        """홈 이동 완료 여부."""
        return self.state == "DONE"
    
    def get_pose_map(self):
        """TF에서 현재 위치 가져오기."""
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
        """맵 좌표계 오차를 로봇 좌표계로 변환."""
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        ex = cy * dx + sy * dy
        ey = -sy * dx + cy * dy
        return ex, ey
    
    def on_timer(self):
        """타이머 콜백: 홈 이동 제어."""
        if not self.active or self.state in ("IDLE", "DONE"):
            return
        
        pose = self.get_pose_map()
        if pose is None:
            self.pub_cmd.publish(Twist())
            return
        
        cx, cy, cyaw = pose
        
        # GOTO 단계: 홈 위치로 이동 (Y축 우선)
        if self.state == "GOTO":
            if (self.now_sec() - self.t0) > self.goto_timeout:
                self.node.get_logger().error("GOTO TIMEOUT -> stop")
                self.state = "DONE"
                self.pub_allow_strafe.publish(Bool(data=False))
                self.pub_cmd.publish(Twist())
                self.active = False
                return
            
            dx = self.home_x - cx
            dy = self.home_y - cy
            ex, ey = self.map_err_to_base(dx, dy, cyaw)
            
            # Y축 우선 정렬
            if abs(ey) > self.tol_perp:
                axis = "y"
            else:
                axis = "x"
            
            if axis == "x":
                e_axis = ex
                e_perp = ey
                cmd_val = self.fixed_vx
                self.pub_allow_strafe.publish(Bool(data=False))
            else:
                e_axis = ey
                e_perp = ex
                cmd_val = self.fixed_vy
                self.pub_allow_strafe.publish(Bool(data=True))
            
            # 도달 판정
            if abs(e_axis) <= self.tol_axis and abs(e_perp) <= self.tol_perp:
                self.pub_cmd.publish(Twist())
                self.pub_allow_strafe.publish(Bool(data=False))
                self.state = "ROTATE"
                self.t0 = self.now_sec()
                self._reset_pulse()
                self.node.get_logger().info("ARRIVED HOME -> ROTATE")
                return
            
            # 가까워지면 pulse 모드
            if abs(e_axis) < self.pulse_near_axis:
                on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True
            
            cmd = Twist()
            if not on:
                self.pub_cmd.publish(cmd)
                return
            
            # 이동 명령 발행
            if axis == "x":
                cmd.linear.x = sgn(e_axis) * abs(cmd_val)
            else:
                cmd.linear.y = sgn(e_axis) * abs(cmd_val)
            cmd.angular.z = 0.0
            self.pub_cmd.publish(cmd)
            return
        
        # ROTATE 단계: 절대 yaw로 회전
        if self.state == "ROTATE":
            if (self.now_sec() - self.t0) > self.rotate_timeout:
                self.node.get_logger().error("ROTATE TIMEOUT -> stop")
                self.state = "DONE"
                self.pub_allow_strafe.publish(Bool(data=False))
                self.pub_cmd.publish(Twist())
                self.active = False
                return
            
            yaw_err = wrap_pi(self.home_yaw - cyaw)
            
            if abs(yaw_err) <= self.tol_yaw:
                self.pub_cmd.publish(Twist())
                self.pub_allow_strafe.publish(Bool(data=False))
                self.state = "DONE"
                self.active = False
                self.node.get_logger().info("HOMING DONE ✅")
                return
            
            # 가까워지면 pulse 모드
            if abs(yaw_err) < self.pulse_near_yaw:
                on = self._pulse_update()
            else:
                self._reset_pulse()
                on = True
            
            cmd = Twist()
            self.pub_allow_strafe.publish(Bool(data=False))
            
            if not on:
                self.pub_cmd.publish(cmd)
                return
            
            cmd.angular.z = sgn(yaw_err) * abs(self.fixed_wz)
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            self.pub_cmd.publish(cmd)
            return

class PatrolLoop(Node):
    """Nav2와 연동. Nav2가 cmd_vel_auto를 발행하므로 이 노드는 액션 실행만 담당."""
    def __init__(self, cfg: PatrolConfig | None = None, uart: UartLink | None = None, job_event_callback=None, use_nav2_signals: bool = True, feed_bridge=None, 
                 home_x: float = 1.2, home_y: float = 1.7, home_yaw_deg: float = -180.0):
        super().__init__("patrol_loop")
        self.cfg = cfg or PatrolConfig()
        self.profile = PatrolProfile(self.cfg)  # 더미 (사용 안 함)
        self.mode = "teleop"
        self.estop = False
        self._patrol_start_ts: float | None = None  # 순찰 시작 시각 (주간 순찰 시간 계산용)
        self.use_nav2_signals = use_nav2_signals  # Nav2 신호 사용 여부 (기본값: True)
        self.feed_bridge = feed_bridge  # FeedControlBridge 참조
        self.sub_mode = self.create_subscription(String, "control_mode", self.on_mode, 10)
        self.sub_estop = self.create_subscription(Bool, "control_estop", self.on_estop, 10)
        # 이동 명령은 Nav2가 /cmd_vel 토픽으로 발행 (PatrolLoop는 발행하지 않음)
        # self.pub_auto = self.create_publisher(Twist, "cmd_vel_auto", 10)  # 제거됨
        self._last_ts = time.time()
        # tick 타이머도 제거 (Nav2가 /cmd_vel 발행하므로 불필요)
        # self.timer = self.create_timer(1.0 / float(self.cfg.rate_hz), self.tick)  # 제거됨
        
        # Homing Controller (수동→자동 전환 시 홈 이동)
        self.homing_controller = HomingController(
            self, 
            home_x=home_x, 
            home_y=home_y, 
            home_yaw_deg=home_yaw_deg
        )
        self._homing_in_progress = False
        self._patrol_started_after_homing = False
        
        # Homing 완료 확인 타이머 (홈 이동 완료 후 순찰 시작)
        self.homing_check_timer = self.create_timer(0.1, self.check_homing_complete)
        
        # 액션 스케줄러 (UART가 있으면 활성화)
        self.action_scheduler: PatrolActionScheduler | None = None
        if uart is not None:
            self.action_scheduler = PatrolActionScheduler(
                self.cfg.action_schedule, 
                uart, 
                job_event_callback=job_event_callback,
                use_nav2_signals=use_nav2_signals,
                feed_bridge=self.feed_bridge
            )
            # FeedControlBridge에 액션 스케줄러 참조 설정
            if self.feed_bridge is not None:
                self.feed_bridge.action_scheduler = self.action_scheduler
                self.feed_bridge.set_action_complete_callback(self._publish_action_complete)
        
        # Nav2 신호 구독 (항상 활성화)
        self.sub_waypoint_reached = self.create_subscription(String, "patrol/waypoint_reached", self.on_waypoint_reached, 10)
        self.sub_aruco_aligned = self.create_subscription(String, "patrol/aruco_aligned", self.on_aruco_aligned, 10)
        self.pub_action_complete = self.create_publisher(String, "patrol/action_complete", 10)
    
    def update_action_schedule(self, schedule: PatrolActionSchedule):
        """웹에서 스케줄 업데이트 시 호출."""
        if self.action_scheduler is not None:
            self.action_scheduler.update_schedule(schedule)
        self.cfg.action_schedule = schedule

    def on_mode(self, msg: String):
        old_mode = self.mode
        self.mode = "auto" if msg.data == "auto" else "teleop"
        if self.mode != "auto":
            self.profile.reset()
            # Homing 중지
            if self._homing_in_progress:
                self.homing_controller.stop()
                self._homing_in_progress = False
            # 순찰 종료 이벤트 (teleop로 전환) — 주간 순찰 시간용 duration 전달
            if old_mode == "auto" and self.action_scheduler and self.action_scheduler.job_event_callback:
                duration_sec = 0.0
                if self._patrol_start_ts is not None:
                    duration_sec = max(0.0, time.time() - self._patrol_start_ts)
                    self._patrol_start_ts = None
                self.action_scheduler.job_event_callback("patrol", "success", duration_sec=duration_sec)
        elif old_mode != "auto" and self.mode == "auto":
            # 수동→자동 전환: 홈 이동 시작
            self.get_logger().info("Mode changed: teleop -> auto, starting homing...")
            self._homing_in_progress = True
            self.homing_controller.start()
            # 순찰 시작은 홈 이동 완료 후 (check_homing_complete에서 확인)
    
    def check_homing_complete(self):
        """Homing 완료 확인 및 순찰 시작."""
        if not self._homing_in_progress:
            return
        
        if self.homing_controller.is_done():
            self._homing_in_progress = False
            self._patrol_started_after_homing = True
            self.get_logger().info("Homing completed, starting patrol...")
            # 순찰 시작 이벤트
            self._patrol_start_ts = time.time()
            if self.action_scheduler and self.action_scheduler.job_event_callback:
                self.action_scheduler.job_event_callback("patrol", "in_progress")
            # 순찰 모드로 전환될 때: 플래그 리셋 (변 치우기/급수는 tick에서 실행)
            if self.action_scheduler is not None:
                self.action_scheduler.reset_patrol()
    
    def on_estop(self, msg: Bool):
        self.estop = bool(msg.data)
    
    def on_waypoint_reached(self, msg: String):
        """Nav2에서 waypoint 도착 신호를 받았을 때."""
        if not self.use_nav2_signals or self.action_scheduler is None:
            return
        
        try:
            data = json.loads(msg.data)
            waypoint_id = data.get("waypoint_id", "")
            waypoint_type = data.get("waypoint_type", "")
            
            self.get_logger().info(f"[Nav2] Waypoint reached: {waypoint_id} ({waypoint_type})")
            
            # 아루코 마커가 필요한 액션인지 확인
            if waypoint_type in ["litter_clean", "water", "feed"]:
                # 아루코 정렬 대기 (급식도 아루코 마커 필요할 수 있음)
                self.action_scheduler._waiting_for_aruco = True
                self.action_scheduler._pending_action = waypoint_type
                self.action_scheduler._pending_waypoint_id = waypoint_id
            else:
                # 아루코 불필요: 바로 실행
                self.action_scheduler.execute_action(
                    waypoint_type, 
                    waypoint_id,
                    action_complete_callback=self._publish_action_complete
                )
        except Exception as e:
            self.get_logger().error(f"[Nav2] Failed to parse waypoint_reached: {e}")
    
    def on_aruco_aligned(self, msg: String):
        """Nav2에서 아루코 마커 정렬 완료 신호를 받았을 때."""
        if not self.use_nav2_signals or self.action_scheduler is None:
            return
        
        try:
            data = json.loads(msg.data)
            waypoint_id = data.get("waypoint_id", "")
            waypoint_type = data.get("waypoint_type", "")
            
            self.get_logger().info(f"[Nav2] Aruco aligned: {waypoint_id} ({waypoint_type})")
            
            # 대기 중인 액션 실행
            if self.action_scheduler._waiting_for_aruco:
                self.action_scheduler.execute_action(
                    waypoint_type, 
                    waypoint_id,
                    action_complete_callback=self._publish_action_complete
                )
                self.action_scheduler._waiting_for_aruco = False
                self.action_scheduler._pending_action = None
                self.action_scheduler._pending_waypoint_id = None
        except Exception as e:
            self.get_logger().error(f"[Nav2] Failed to parse aruco_aligned: {e}")
    
    def _publish_action_complete(self, action_type: str, waypoint_id: str, status: str):
        """액션 완료 신호를 Nav2에 발행."""
        if not self.use_nav2_signals:
            return
        
        try:
            import json
            msg = String()
            msg.data = json.dumps({
                "action_type": action_type,
                "waypoint_id": waypoint_id,
                "status": status,
                "timestamp": time.time()
            })
            self.pub_action_complete.publish(msg)
            self.get_logger().info(f"[Nav2] Action complete: {action_type} ({status})")
        except Exception as e:
            self.get_logger().error(f"[Nav2] Failed to publish action_complete: {e}")

    # tick() 메서드 제거: Nav2가 cmd_vel_auto를 발행하므로 더 이상 필요 없음
    # 액션 실행은 Nav2 신호(on_waypoint_reached, on_aruco_aligned)로만 처리됨


# ---------- 순찰 스케줄러 (주기적으로 순찰 시작) ----------
class PatrolScheduler(Node):
    """
    주기적으로 순찰을 시작하는 스케줄러.
    
    설정된 간격(예: 4시간)마다:
    1. Nav2에 순찰 경로 goal 전송 (또는 control_mode를 auto로 변경)
    2. 순찰 시작 이벤트 발생
    """
    def __init__(self, interval_hours: float = 0.0, control_mode_pub=None, nav2_client=None):
        """
        Args:
            interval_hours: 순찰 간격 (시간). 0이면 비활성화
            control_mode_pub: control_mode 토픽 발행자 (순찰 시작 시 "auto" 발행)
            nav2_client: Nav2 액션 클라이언트 (선택, 있으면 Nav2 goal 전송)
        """
        super().__init__("patrol_scheduler")
        self.interval_hours = float(interval_hours)
        self.control_mode_pub = control_mode_pub
        self.nav2_client = nav2_client
        self.last_patrol_ts = time.time()
        self.is_patrolling = False
        
        # 1분마다 체크 (순찰 간격 확인)
        self.timer = self.create_timer(60.0, self.check_patrol)
        
        if self.interval_hours > 0:
            self.get_logger().info(f"PatrolScheduler initialized: interval={self.interval_hours} hours")
        else:
            self.get_logger().info("PatrolScheduler disabled (interval=0)")
    
    def set_interval(self, interval_hours: float):
        """순찰 간격 업데이트 (웹에서 설정 변경 시)."""
        self.interval_hours = float(interval_hours)
        self.last_patrol_ts = time.time()  # 리셋
        if interval_hours > 0:
            self.get_logger().info(f"Patrol interval updated: {interval_hours} hours")
    
    def check_patrol(self):
        """타이머 콜백: 순찰 간격 확인 및 순찰 시작."""
        if self.interval_hours <= 0:
            return  # 비활성화
        
        if self.is_patrolling:
            return  # 이미 순찰 중
        
        now = time.time()
        elapsed_hours = (now - self.last_patrol_ts) / 3600.0
        
        if elapsed_hours >= self.interval_hours:
            self.start_patrol()
            self.last_patrol_ts = now
    
    def start_patrol(self):
        """순찰 시작."""
        if self.is_patrolling:
            return
        
        self.get_logger().info(f"Starting scheduled patrol (interval={self.interval_hours}h)")
        self.is_patrolling = True
        
        # control_mode를 "auto"로 변경 (순찰 시작)
        if self.control_mode_pub:
            msg = String()
            msg.data = "auto"
            self.control_mode_pub.publish(msg)
            self.get_logger().info("Published control_mode=auto")
        
        # Nav2 액션이 있으면 goal 전송 (선택)
        if self.nav2_client:
            # TODO: 순찰 경로 waypoint 설정 후 goal 전송
            # 예: self.nav2_client.send_goal_async(goal)
            pass
    
    def stop_patrol(self):
        """순찰 종료 (수동 중지 또는 완료 시)."""
        if not self.is_patrolling:
            return
        
        self.get_logger().info("Stopping patrol")
        self.is_patrolling = False
        
        # control_mode를 "teleop"로 변경
        if self.control_mode_pub:
            msg = String()
            msg.data = "teleop"
            self.control_mode_pub.publish(msg)
    
    def on_patrol_completed(self):
        """순찰 완료 시 호출 (PatrolLoop에서 호출 가능)."""
        self.is_patrolling = False
        self.last_patrol_ts = time.time()  # 다음 순찰 타이머 리셋


# ---------- Mux: teleop vs auto → /cmd_vel_joy (ROS2 폴더 twist_mux 입력) ----------
class CmdVelMux(Node):
    """
    명령 통합 (Mux): 웹 대시보드 명령과 패트롤 명령을 통합하여 /cmd_vel_joy로 발행.
    
    ROS2 폴더의 twist_mux가 /cmd_vel_joy를 구독하여 다른 입력과 통합합니다.
    twist_mux가 최종적으로 /cmd_vel을 발행하고, twist_to_stm_uart_bridge.py가 UART로 전송합니다.
    
    우선순위 (twist_mux.yaml 기준):
    - 아루코 마커 (priority 80) > 웹 대시보드 (priority 50) > 패트롤 (priority 10)
    
    이 구조로 ROS2 폴더와 Pi Gateway를 동시에 실행해도 충돌 없이 동작합니다.
    
    참고: /cmd_vel_out은 제거되었습니다. twist_mux 경로만 사용합니다.
    """
    def __init__(self):
        super().__init__("cmdvel_mux")
        self.mode = "teleop"
        self.estop = False
        self.last_teleop = Twist()
        self.last_auto = Twist()
        self.last_auto_ts = 0.0
        self.auto_timeout_sec = 0.5
        self.sub_t = self.create_subscription(Twist, "cmd_vel_teleop", self.on_teleop, 10)
        self.sub_a = self.create_subscription(Twist, "/cmd_vel_nav", self.on_auto, 10)  # 패트롤 노드의 자동 주행 명령 구독
        # ROS2 폴더의 twist_mux 입력 토픽으로 발행 (twist_mux.yaml의 manual_drive 토픽)
        self.pub_out = self.create_publisher(Twist, "/cmd_vel_joy", 10)
        self.sub_mode = self.create_subscription(String, "control_mode", self.on_mode, 10)
        self.sub_estop = self.create_subscription(Bool, "control_estop", self.on_estop, 10)
        self.timer = self.create_timer(1.0/30.0, self.tick)

    def set_control_state(self, *, mode: str, estop: bool):
        self.mode = "auto" if mode == "auto" else "teleop"
        self.estop = bool(estop)

    def on_mode(self, msg: String):
        self.mode = "auto" if msg.data == "auto" else "teleop"

    def on_estop(self, msg: Bool):
        self.estop = bool(msg.data)

    def on_teleop(self, msg: Twist):
        self.last_teleop = msg

    def on_auto(self, msg: Twist):
        self.last_auto = msg
        self.last_auto_ts = time.time()

    def tick(self):
        out = Twist()
        if self.estop:
            self.pub_out.publish(out)
            return
        now = time.time()
        if self.mode == "auto":
            # 패트롤 중: auto 모드일 때는 웹 조이스틱/키보드 입력 무시하고 auto만 사용
            if (now - self.last_auto_ts) <= self.auto_timeout_sec:
                out = self.last_auto
            else:
                # auto 명령이 없거나 오래되었으면 정지 (teleop 무시)
                out = Twist()
        else:
            # teleop 모드: 웹 입력 사용
            out = self.last_teleop
        self.pub_out.publish(out)  # twist_mux 입력 (/cmd_vel_joy)


class ControlTopicBridge(Node):
    """WebState → control_mode, control_estop 발행. mux/patrol이 구독."""
    def __init__(self, get_state_fn, *, rate_hz: float = 20.0):
        super().__init__("control_topic_bridge")
        self._get_state = get_state_fn
        self.pub_mode = self.create_publisher(String, "control_mode", 10)
        self.pub_estop = self.create_publisher(Bool, "control_estop", 10)
        self._last_mode = None
        self._last_estop = None
        period = 1.0 / max(1.0, float(rate_hz))
        self.timer = self.create_timer(period, self.tick)

    def tick(self):
        st = self._get_state()
        mode = "auto" if getattr(st, "mode", "teleop") == "auto" else "teleop"
        estop = bool(getattr(st, "estop", False))
        if mode != self._last_mode:
            m = String()
            m.data = mode
            self.pub_mode.publish(m)
            self._last_mode = mode
        if estop != self._last_estop:
            b = Bool()
            b.data = estop
            self.pub_estop.publish(b)
            self._last_estop = estop


# ---------- UART 제어 (cmd_vel 제외: ROS2 폴더 브릿지가 담당) ----------
class RosCmdVelBridge(Node):
    """
    UART 제어 브릿지 (cmd_vel 제외).
    
    역할:
    - Heartbeat 전송 (STM32 워치독용)
    - Feed 명령 전송
    - Estop 처리
    - 로봇팔 동작 중 바퀴 잠금 (cmd_vel=0 전송)
    
    주의:
    - cmd_vel UART 전송은 ROS2 폴더의 twist_to_stm_uart_bridge.py가 담당합니다.
    - Pi Gateway는 /cmd_vel 토픽을 발행만 하고, UART 전송은 ROS2 폴더 브릿지가 합니다.
    """
    def __init__(self, uart: UartLink, *, tx_rate_hz: float = 20.0, cmd_timeout_ms: int = 500):
        super().__init__("ros_cmdvel_bridge")
        self.uart = uart
        self.estop = False
        self.mode = "teleop"
        self.arm_start_active = False  # arm/start 활성화 상태 (변 치우기 등)
        self.arm_water_active = False  # arm/water 활성화 상태 (급수 단계별)
        self._pending_feed = None
        self.cmd_timeout_ms = int(cmd_timeout_ms)
        self._last_heartbeat_ts = 0.0
        self.timer = self.create_timer(1.0/max(1.0, tx_rate_hz), self.tick)
        # cmd_vel 구독 제거 (ROS2 폴더 브릿지가 /cmd_vel을 구독하여 UART 전송)
        self.sub_estop = self.create_subscription(Bool, "control_estop", self.on_estop, 10)
        self.sub_feed = self.create_subscription(UInt8, "feed_cmd", self.on_feed, 10)

    def set_control_state(self, *, mode: str, estop: bool):
        self.mode = "auto" if mode == "auto" else "teleop"
        self.estop = bool(estop)
    
    def set_arm_start_active(self, active: bool):
        """arm/start 활성화 상태 설정 (변 치우기 등)."""
        self.arm_start_active = bool(active)
    
    def set_arm_water_active(self, active: bool):
        """arm/water 활성화 상태 설정 (급수 단계별)."""
        self.arm_water_active = bool(active)
    
    @property
    def arm_active(self) -> bool:
        """로봇팔 활성화 상태 (arm/start 또는 arm/water 중 하나라도 활성화되면 True)."""
        return self.arm_start_active or self.arm_water_active

    def request_feed(self, level: int):
        self._pending_feed = int(level)

    def on_estop(self, msg: Bool):
        self.estop = bool(msg.data)

    def on_feed(self, msg: UInt8):
        try:
            self._pending_feed = int(msg.data)
        except Exception:
            self._pending_feed = None

    def tick(self):
        """
        UART 제어 (cmd_vel 제외).
        
        cmd_vel UART 전송은 ROS2 폴더의 twist_to_stm_uart_bridge.py가 담당합니다.
        Pi Gateway는 heartbeat, feed, estop, 로봇팔 바퀴 잠금만 처리합니다.
        """
        now = time.time()
        
        # Heartbeat 전송 (STM32 워치독용)
        if now - self._last_heartbeat_ts >= 0.2:
            try:
                self.uart.send(make_heartbeat_frame())
                self._last_heartbeat_ts = now
            except Exception as e:
                self.get_logger().error(f"heartbeat send failed: {e}")

        # Feed 명령 전송
        if self._pending_feed is not None:
            lvl = self._pending_feed
            self._pending_feed = None
            try:
                self.uart.send(make_feed_frame(lvl))
            except Exception as e:
                self.get_logger().error(f"feed send failed: {e}")

        # Estop 처리
        if self.estop:
            try:
                self.uart.send(make_estop_frame(1))
            except Exception as e:
                self.get_logger().error(f"estop send failed: {e}")
            return

        # 로봇팔 동작 중에는 바퀴 모터를 잠가야 함 (cmd_vel=0 전송)
        # 주의: ROS2 폴더 브릿지가 /cmd_vel을 구독하지만, 로봇팔 동작 중에는
        # Pi Gateway가 직접 cmd_vel=0을 UART로 전송하여 즉시 바퀴를 잠급니다.
        if self.arm_active:
            try:
                self.uart.send(make_cmd_vel_frame(0.0, 0.0, 0.0))
            except Exception as e:
                self.get_logger().error(f"cmd_vel send failed (arm active): {e}")
        
        # 일반적인 cmd_vel 전송은 ROS2 폴더 브릿지가 담당하므로 여기서는 처리하지 않음


# ---------- 급식 제어 브릿지 (젯슨 → 파이 → STM) ----------
class FeedControlBridge(Node):
    """
    젯슨에서 발행한 급식 사료 량 토픽을 구독하여 UART로 STM32에 전송.
    
    역할:
    - 브릿지: 젯슨의 사료 량 계산 결과를 받아서 STM32로 전달
    - 급식 요청: PatrolActionScheduler가 급식 요청 시 젯슨에 알림
    
    구독 토픽:
    - feed/amount (std_msgs/UInt8): 젯슨이 계산한 사료 량 (1~3)
    
    발행 토픽:
    - feed/request (std_msgs/String): 급식 요청 (waypoint 도착 시)
    
    통신 흐름:
    1. PatrolActionScheduler가 급식 요청 → feed/request 발행
    2. 젯슨이 FEED_AI 모델로 사료 량 계산 → feed/amount 발행
    3. FeedControlBridge가 feed/amount 구독 → UART로 STM32 전송
    4. STM32가 서보모터 제어 → 완료 신호 (STATUS) 전송
    """
    def __init__(self, uart: UartLink, action_scheduler=None):
        super().__init__("feed_control_bridge")
        self.uart = uart
        self.action_scheduler = action_scheduler  # PatrolActionScheduler 참조
        
        # 젯슨이 발행한 사료 량 구독
        self.sub_amount = self.create_subscription(
            UInt8, "feed/amount", self.on_feed_amount, 10
        )
        
        # 급식 요청 발행 (PatrolActionScheduler가 사용)
        self.pub_request = self.create_publisher(String, "feed/request", 10)
        
        # 액션 완료 콜백 (PatrolActionScheduler에서 설정)
        self.action_complete_callback = None
        
        self.get_logger().info("FeedControlBridge initialized")
    
    def set_action_complete_callback(self, callback):
        """액션 완료 콜백 설정 (PatrolActionScheduler에서 호출)."""
        self.action_complete_callback = callback
    
    def request_feed(self, waypoint_id: str):
        """급식 요청을 젯슨에 발행."""
        try:
            msg = String()
            msg.data = json.dumps({
                "waypoint_id": waypoint_id,
                "timestamp": time.time()
            })
            self.pub_request.publish(msg)
            self.get_logger().info(f"Feed requested for waypoint: {waypoint_id}")
        except Exception as e:
            self.get_logger().error(f"Failed to publish feed request: {e}")
    
    def on_feed_amount(self, msg: UInt8):
        """젯슨이 계산한 사료 량 수신 → UART로 STM32에 전송."""
        try:
            feed_level = int(msg.data)
            if feed_level < 1 or feed_level > 3:
                self.get_logger().warn(f"Invalid feed level: {feed_level}, using default 2")
                feed_level = 2
            
            # UART 프레임 생성 및 전송
            frame = make_feed_frame(feed_level)
            self.uart.send(frame)
            
            self.get_logger().info(f"Feed executed (level: {feed_level})")
            
            # 액션 완료 콜백 호출 (PatrolActionScheduler가 설정)
            if self.action_complete_callback and self.action_scheduler:
                waypoint_id = getattr(self.action_scheduler, "_pending_feed_waypoint_id", "")
                if waypoint_id:
                    self.action_complete_callback("feed", waypoint_id, "success")
                    self.action_scheduler._waiting_for_feed_amount = False
                    self.action_scheduler._pending_feed_waypoint_id = None
        
        except Exception as e:
            self.get_logger().error(f"Failed to process feed amount: {e}")
            if self.action_complete_callback and self.action_scheduler:
                waypoint_id = getattr(self.action_scheduler, "_pending_feed_waypoint_id", "")
                if waypoint_id:
                    self.action_complete_callback("feed", waypoint_id, "failed")
                    self.action_scheduler._waiting_for_feed_amount = False
                    self.action_scheduler._pending_feed_waypoint_id = None


# ---------- 로봇팔 제어 브릿지 (Action 클라이언트 + 토픽 브릿지) ----------
class ArmControlBridge(Node):
    """
    로봇팔 제어 브릿지: Action 클라이언트 + 토픽 브릿지
    
    역할:
    1. Action 클라이언트: 로봇팔 팀의 Action 서버에 작업 요청 (VLA 기반)
    2. 토픽 브릿지: 기존 토픽 기반 통신 유지 (하위 호환성)
    3. 작업 완료 신호 발행: `/arm/done` 토픽 발행 (패트롤 노드용)
    4. 안전 제어: 로봇팔 동작 중 바퀴 모터 잠금
    
    Action 통신:
    - 액션 이름: execute_vla_task
    - 액션 타입: catbot_interfaces/action/VlaTask
    - 입력: 자연어 프롬프트 (예: "Pick up the shovel from the right holder.")
    
    토픽 구독 (기존 호환성):
    - arm/start (std_msgs/UInt8): 로봇팔 동작 시작 (0=정지, 1=변 치우기, 2+=기타)
    - arm/position_correct (geometry_msgs/Vector3): 로봇 위치 보정 (dx, dy, dz)
    - arm/water (std_msgs/UInt8): 급수 단계별 제어
    - arm/job_complete (std_msgs/String): 작업 완료 신호 (젯슨에서)
    
    토픽 발행:
    - /arm/done (std_msgs/Bool): 작업 완료 신호 (패트롤 노드용)
    """
    def __init__(self, uart: UartLink, cmdvel_bridge=None):
        super().__init__("arm_control_bridge")
        self.uart = uart
        self.cmdvel_bridge = cmdvel_bridge  # RosCmdVelBridge 참조 (로봇팔 동작 중 cmd_vel 차단용)
        self.arm_active = False  # arm/start 활성화 상태 (변 치우기 등)
        self.arm_water_active = False  # arm/water 활성화 상태 (급수 단계별)
        
        # Action 클라이언트 (로봇팔 팀의 Action 서버와 통신)
        self._action_client = None
        self._current_goal_handle = None
        if CATBOT_INTERFACES_AVAILABLE:
            self._action_client = ActionClient(self, VlaTask, 'execute_vla_task')
            self.get_logger().info("Action client initialized for execute_vla_task")
        else:
            self.get_logger().warn("catbot_interfaces 패키지가 없습니다. Action 클라이언트를 사용할 수 없습니다.")
        
        # 작업 완료 신호 발행 (패트롤 노드용)
        self.pub_arm_done = self.create_publisher(Bool, '/arm/done', 10)
        
        # ROS 토픽 구독 (기존 호환성)
        self.sub_start = self.create_subscription(
            UInt8, "arm/start", self.on_start, 10
        )
        self.sub_correct = self.create_subscription(
            Vector3, "arm/position_correct", self.on_correct, 10
        )
        self.sub_water = self.create_subscription(
            UInt8, "arm/water", self.on_water, 10
        )
        # 젯슨에서 작업 완료 신호 구독 (변 치우기, 급수 완료)
        self.sub_job_complete = self.create_subscription(
            String, "arm/job_complete", self.on_job_complete, 10
        )
        
        # Action 요청을 위한 토픽 구독 (패트롤 노드에서 사용)
        self.sub_arm_cmd = self.create_subscription(
            String, "arm/cmd", self.on_arm_cmd, 10
        )
        
        # 작업 이벤트 콜백 (main.py에서 설정)
        self.job_event_callback = None
        
        self.get_logger().info("ArmControlBridge initialized")
    
    def set_job_event_callback(self, callback):
        """작업 이벤트 콜백 설정 (main.py에서 호출)."""
        self.job_event_callback = callback
    
    def execute_vla_task(self, task_prompt: str, timeout_sec: float = 60.0):
        """
        로봇팔 Action 서버에 작업 요청 (VLA 기반).
        
        Args:
            task_prompt: 자연어 프롬프트 (예: "Pick up the shovel from the right holder.")
            timeout_sec: 타임아웃 시간 (초)
        
        Returns:
            bool: 작업 성공 여부
        """
        if not CATBOT_INTERFACES_AVAILABLE or self._action_client is None:
            self.get_logger().error("Action 클라이언트를 사용할 수 없습니다.")
            return False
        
        # 서버 대기
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("로봇팔 Action 서버를 찾을 수 없습니다.")
            return False
        
        # 로봇팔 동작 시작 → 바퀴 잠금
        self.arm_active = True
        if self.cmdvel_bridge is not None:
            self.cmdvel_bridge.set_arm_start_active(True)
        
        # 목표 전송
        goal_msg = VlaTask.Goal()
        goal_msg.task_type = task_prompt
        
        self.get_logger().info(f"로봇팔 작업 요청: {task_prompt} (바퀴 잠금)")
        
        # 비동기로 목표 전송
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        
        # 결과를 처리하기 위해 콜백 등록
        send_goal_future.add_done_callback(self._goal_response_callback)
        
        return True
    
    def _goal_response_callback(self, future):
        """목표 응답 콜백."""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("로봇팔 작업이 거부되었습니다.")
            # 작업 실패 신호 발행
            done_msg = Bool()
            done_msg.data = False
            self.pub_arm_done.publish(done_msg)
            return
        
        self.get_logger().info("로봇팔 작업 수락됨 (실행 중...)")
        self._current_goal_handle = goal_handle
        
        # 결과 대기
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self._get_result_callback)
    
    def _get_result_callback(self, future):
        """결과 수신 콜백."""
        try:
            result = future.result().result
            status = future.result().status
            
            # 로봇팔 작업 완료 → 바퀴 해제
            self.arm_active = False
            if self.cmdvel_bridge is not None:
                self.cmdvel_bridge.set_arm_start_active(False)
            
            if result.success:
                self.get_logger().info(f"로봇팔 작업 완료: {result.message} (바퀴 해제)")
                # 작업 완료 신호 발행
                done_msg = Bool()
                done_msg.data = True
                self.pub_arm_done.publish(done_msg)
                
                # 작업 이벤트 콜백 호출
                if self.job_event_callback:
                    self.job_event_callback("arm", "success", result.message)
            else:
                self.get_logger().error(f"로봇팔 작업 실패: {result.message} (바퀴 해제)")
                # 작업 실패 신호 발행
                done_msg = Bool()
                done_msg.data = False
                self.pub_arm_done.publish(done_msg)
                
                # 작업 이벤트 콜백 호출
                if self.job_event_callback:
                    self.job_event_callback("arm", "failed", result.message)
        except Exception as e:
            self.get_logger().error(f"결과 처리 중 오류: {e}")
            # 오류 발생 시에도 바퀴 해제
            self.arm_active = False
            if self.cmdvel_bridge is not None:
                self.cmdvel_bridge.set_arm_start_active(False)
            # 작업 실패 신호 발행
            done_msg = Bool()
            done_msg.data = False
            self.pub_arm_done.publish(done_msg)
        
        self._current_goal_handle = None
    
    def on_arm_cmd(self, msg: String):
        """
        /arm/cmd 토픽 수신 (패트롤 노드에서 로봇팔 작업 요청).
        
        메시지 형식: 자연어 프롬프트 문자열
        예: "Pick up the shovel from the right holder."
        """
        task_prompt = msg.data.strip()
        if not task_prompt:
            self.get_logger().warn("빈 작업 프롬프트를 받았습니다.")
            return
        
        # Action 서버에 작업 요청
        self.execute_vla_task(task_prompt)
    
    def on_job_complete(self, msg: String):
        """
        젯슨에서 작업 완료 신호 수신.
        
        메시지 형식 (JSON 문자열):
        {"job_type": "litter_clean" | "water", "status": "success" | "failed", "reason": "..."}
        """
        try:
            data = json.loads(msg.data)
            job_type = data.get("job_type")
            status = data.get("status", "success")
            reason = data.get("reason")
            
            if job_type in ("litter_clean", "water"):
                # 작업 이벤트 업데이트
                if self.job_event_callback:
                    self.job_event_callback(job_type, status, reason)
                self.get_logger().info(f"Job complete: {job_type} - {status}")
        except Exception as e:
            self.get_logger().error(f"Failed to parse job_complete: {e}")
    
    def on_start(self, msg: UInt8):
        """로봇팔 동작 시작 토픽 수신."""
        action_id = int(msg.data)
        is_starting = (action_id != 0)
        
        try:
            frame = make_arm_start_frame(action_id)
            self.uart.send(frame)
            
            # 로봇팔 상태 업데이트
            self.arm_active = is_starting
            
            # 로봇팔 동작 중에는 cmd_vel을 차단하기 위해 RosCmdVelBridge에 알림
            if self.cmdvel_bridge is not None:
                self.cmdvel_bridge.set_arm_start_active(self.arm_active)
            
            if is_starting:
                self.get_logger().info(f"Arm started (action_id={action_id}) - wheels locked")
            else:
                self.get_logger().info(f"Arm stopped (action_id={action_id}) - wheels unlocked")
                # action_id=0은 "정지" 신호이지만, 완료 신호는 별도 토픽(arm/job_complete) 사용 권장
        except Exception as e:
            self.get_logger().error(f"Failed to send arm/start: {e}")
    
    def on_correct(self, msg: Vector3):
        """로봇 위치 보정 토픽 수신."""
        dx = float(msg.x)
        dy = float(msg.y)
        dz = float(msg.z)
        try:
            frame = make_arm_position_correct_frame(dx, dy, dz)
            self.uart.send(frame)
            self.get_logger().info(f"Sent arm/position_correct: dx={dx:.3f}, dy={dy:.3f}, dz={dz:.3f}")
        except Exception as e:
            self.get_logger().error(f"Failed to send arm/position_correct: {e}")
    
    def on_water(self, msg: UInt8):
        """
        급수 토픽 수신.
        
        급수 동작은 모방학습 로봇팔이 자율로 수행합니다:
        1. 물그릇 위치로 이동 (바퀴 필요, 잠금 해제)
        2. 물그릇 집기 (로봇팔 동작, 바퀴 해제 - 위치 이동 중)
        3. 화장실 위치로 이동 (바퀴 필요, 잠금 해제)
        4. 아루코 마커로 정밀 위치 조정 (바퀴 해제)
        5. 물 버리기 (로봇팔 동작, 바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
        6. 서스펜서 위치로 이동 (바퀴 필요, 잠금 해제)
        7. 아루코 마커로 정밀 위치 조정 (바퀴 해제)
        8. 물 받기 (로봇팔 동작, 바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
        9. 물그릇 위치로 이동 (바퀴 필요, 잠금 해제)
        10. 물그릇 두기 (로봇팔 동작, 바퀴 잠금)
        
        water_action:
        - 0 = 위치 이동/정지 (바퀴 해제)
        - 1 = 물그릇 집기 (바퀴 해제 - 위치 이동 중)
        - 2 = 물 버리기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
        - 3 = 물 받기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
        - 4 = 물그릇 두기 (바퀴 잠금)
        """
        water_action = int(msg.data)
        # 물 버리기(2), 물 받기(3), 물그릇 두기(4)는 바퀴 잠금
        # 물 버리기(2)와 물 받기(3)는 아루코 마커로 정밀 위치 조정 완료 후 시작하므로 바퀴 잠금
        # 물그릇 집기(1)와 위치 이동(0)은 바퀴 해제
        is_wheel_lock = (water_action in [2, 3, 4])
        
        try:
            frame = make_arm_water_frame(water_action)
            self.uart.send(frame)
            
            if is_wheel_lock:
                self.arm_water_active = True
                if self.cmdvel_bridge is not None:
                    self.cmdvel_bridge.set_arm_water_active(True)
                action_names = {2: "pour", 3: "fill", 4: "place"}
                action_name = action_names.get(water_action, f"action_{water_action}")
                self.get_logger().info(f"Water action: {action_name} (action={water_action}) - wheels locked")
            else:
                # water_action = 0, 1: 바퀴 해제 (위치 이동 가능)
                self.arm_water_active = False
                if self.cmdvel_bridge is not None:
                    self.cmdvel_bridge.set_arm_water_active(False)
                action_names = {0: "move/idle", 1: "pick"}
                action_name = action_names.get(water_action, f"action_{water_action}")
                self.get_logger().info(f"Water action: {action_name} (action={water_action}) - wheels unlocked")
            
            self.get_logger().info(f"Sent arm/water: action={water_action}")
        except Exception as e:
            self.get_logger().error(f"Failed to send arm/water: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = PatrolLoop()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
