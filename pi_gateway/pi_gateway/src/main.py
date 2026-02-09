import os
import logging
import threading
import time
import yaml
import struct
import random
from dataclasses import dataclass
from typing import Optional

import uvicorn

from src.log_config import configure_logging, configure_uvicorn_logging, get_uvicorn_log_level

log = logging.getLogger(__name__ if __name__ != "__main__" else "src.main")

from src.web_ws_server import app, STATE, TELEM, set_uart_link, set_patrol_node, set_patrol_scheduler, JOB_EVENTS
from src.uart_link import UartLink, UartConfig
from src.uart_frames import make_cmd_vel_frame, make_estop_frame, make_feed_frame, make_heartbeat_frame, decode_telemetry

# WebRTC 시그널링 클라이언트 (프론트엔드 버튼 클릭 감지용)
try:
    from src.webrtc_signaling_client import run_signaling_client
    WEBRTC_SIGNALING_AVAILABLE = True
except ImportError:
    WEBRTC_SIGNALING_AVAILABLE = False

# ROS2 모듈은 조건부로 import (데모 모드에서는 불필요)
try:
    from src.ros_cmdvel import PatrolLoop, PatrolConfig, PatrolProfile, PatrolActionSchedule, PatrolScheduler, FeedControlBridge
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    # ROS 미설치 환경에서도 데모 루프가 돌 수 있도록 최소 더미 구현 제공
    class PatrolLoop:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            pass

    class PatrolActionSchedule:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            pass

    class PatrolConfig:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            pass

    class PatrolProfile:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            # open-loop 데모에서만 사용. ROS 없으면 정지 패턴으로 둔다.
            pass

        def reset(self) -> None:
            return None

        def step(self, dt: float):
            # (vx, wz) 반환. ROS 없이 auto 모드에서 충돌 방지용.
            return 0.0, 0.0



def load_params():
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "params.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class TeleopConfig:
    linear_speed: float = 0.6
    angular_speed: float = 1.5

def state_to_cmd(state, cfg: TeleopConfig):
    if getattr(state, "estop", False):
        return 0.0, 0.0, 0.0
    if getattr(state, "joy_active", False):
        vx = float(getattr(state, "joy_x", 0.0)) * cfg.linear_speed
        vy = float(getattr(state, "joy_y", 0.0)) * cfg.linear_speed
        wz = 0.0
    else:
        pressed = getattr(state, "pressed", set()) or set()
        vx = vy = wz = 0.0
        if "up" in pressed:    vx += cfg.linear_speed
        if "down" in pressed:  vx -= cfg.linear_speed
        if "left" in pressed:  wz += cfg.angular_speed   # 좌회전
        if "right" in pressed: wz -= cfg.angular_speed    # 우회전
        # rot_l, rot_r은 left, right와 동일하지만 현재 사용 안 함 (WebSocket에서 직접 사용 가능하도록 남겨둠)
        if "rot_l" in pressed: wz += cfg.angular_speed   # 좌회전 (left와 동일)
        if "rot_r" in pressed: wz -= cfg.angular_speed   # 우회전 (right와 동일)
    
    return vx, vy, wz

def pressed_to_cmd(pressed: set, cfg: TeleopConfig):
    vx = vy = wz = 0.0
    pressed = pressed or set()
    if "up" in pressed:    vx += cfg.linear_speed
    if "down" in pressed:  vx -= cfg.linear_speed
    if "left" in pressed:  wz += cfg.angular_speed   # 좌회전
    if "right" in pressed: wz -= cfg.angular_speed    # 우회전
    # rot_l, rot_r은 left, right와 동일하지만 현재 사용 안 함 (WebSocket에서 직접 사용 가능하도록 남겨둠)
    if "rot_l" in pressed: wz += cfg.angular_speed   # 좌회전 (left와 동일)
    if "rot_r" in pressed: wz -= cfg.angular_speed   # 우회전 (right와 동일)
    return vx, vy, wz


# ------------------------
# 데모 루프 (ROS 없이)
# ------------------------

def start_demo_teleop_loop(uart: UartLink, tele_cfg: TeleopConfig, tx_rate_hz: float = 20.0):
    """WebState(pressed/mode/estop/feed) 읽어서 UART 프레임 주기 전송(가상 모드면 hex만 출력). HEARTBEAT 약 5Hz 별도."""
    period = 1.0 / max(1.0, float(tx_rate_hz))
    heartbeat_interval = 0.2  # 5 Hz, STM 워치독용

    patrol = PatrolProfile(PatrolConfig())

    def loop():
        last_sent_feed = None
        last_heartbeat_ts = 0.0
        last_patrol_ts = time.time()
        last_log_ts = 0.0
        while True:
            try:
                now = time.time()
                # HEARTBEAT: STM 워치독용, 약 5Hz
                if now - last_heartbeat_ts >= heartbeat_interval:
                    uart.send(make_heartbeat_frame())
                    last_heartbeat_ts = now

                # estop 우선
                if STATE.estop:
                    uart.send(make_estop_frame(1))
                    # estop이면 속도 0 유지
                    uart.send(make_cmd_vel_frame(0.0, 0.0, 0.0))
                else:
                    if STATE.mode == "teleop":
                        vx, vy, wz = state_to_cmd(STATE, tele_cfg)
                        uart.send(make_cmd_vel_frame(vx, vy, wz))
                        # 디버깅: 1초마다 상태 로그 (키 입력이 있을 때만)
                        if (vx != 0.0 or vy != 0.0 or wz != 0.0) and (now - last_log_ts >= 1.0):
                            log.info("[DEMO TELEOP] mode=%s estop=%s pressed=%s joy_active=%s cmd=(%.2f, %.2f, %.2f)",
                                    STATE.mode, STATE.estop, sorted(list(STATE.pressed)), STATE.joy_active, vx, vy, wz)
                            last_log_ts = now
                        # STATE가 비어있는데도 5초마다 한 번씩 로그 (디버깅용)
                        elif len(STATE.pressed) == 0 and not STATE.joy_active and (now - last_log_ts >= 5.0):
                            log.debug("[DEMO TELEOP] 대기 중: mode=%s pressed=%s joy_active=%s cmd=(0.0, 0.0, 0.0)",
                                     STATE.mode, sorted(list(STATE.pressed)), STATE.joy_active)
                            last_log_ts = now
                    else:
                        # patrol(auto): 정석적으로는 Nav2/SLAM에서 cmd_vel_auto가 나오지만,
                        # 지금은 open-loop 패턴으로라도 "auto에서 계속 움직이는" 동작을 보이게 한다.
                        dt = now - last_patrol_ts
                        last_patrol_ts = now
                        vx, wz = patrol.step(dt)
                        uart.send(make_cmd_vel_frame(vx, 0.0, wz))

                # 급식: 한 번만 보내고 소비 (급식 레벨 1~3)
                if STATE.feed_level is not None and STATE.feed_level != last_sent_feed:
                    uart.send(make_feed_frame(int(STATE.feed_level)))
                    last_sent_feed = STATE.feed_level
                    STATE.feed_level = None

            except Exception as e:
                log.error("[DEMO LOOP ERROR] %s", e, exc_info=True)

            time.sleep(period)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t

def start_fake_telemetry(uart: UartLink, *, hz: float = 2.0):
    """STM/ROS 없이도 '뭔가 올라오는 것처럼' 로그를 찍고, on_frame 콜백을 태운다."""
    if not hasattr(uart, "_on_frame") or uart._on_frame is None:
        return None

    period = 1.0 / max(0.2, float(hz))

    def loop():
        soc = 78
        mv = 11800
        charging = 0
        enc_fl = enc_fr = enc_rl = enc_rr = 0
        while True:
            try:
                # 배터리: voltage(uint16 mV), soc(uint8), charging(uint8), error(uint8)
                soc = max(0, min(100, soc + random.choice([-1, 0, 0, 1])))
                mv = max(10500, min(12600, mv + random.choice([-30, -10, 0, 10, 30])))
                payload_batt = struct.pack("<HBBB", mv, soc, charging, 0)
                uart._on_frame(0x81, payload_batt)

                # 바퀴 엔코더: enc_fl,enc_fr,enc_rl,enc_rr (데모용 4륜 누적 틱)
                enc_fl += random.choice([-1, 0, 0, 1, 2])
                enc_fr += random.choice([-1, 0, 0, 1, 2])
                enc_rl += random.choice([-1, 0, 0, 1, 2])
                enc_rr += random.choice([-1, 0, 0, 1, 2])
                payload_enc = struct.pack("<iiii", enc_fl, enc_fr, enc_rl, enc_rr)
                uart._on_frame(0x82, payload_enc)

                # IMU: float32 x6 (yaw,pitch,roll,accx,accy,accz)
                yaw = random.uniform(-3.14, 3.14)
                pitch = random.uniform(-0.2, 0.2)
                roll = random.uniform(-0.2, 0.2)
                accx = random.uniform(-0.1, 0.1)
                accy = random.uniform(-0.1, 0.1)
                accz = 9.8 + random.uniform(-0.2, 0.2)
                payload_imu = struct.pack("<ffffff", yaw, pitch, roll, accx, accy, accz)
                uart._on_frame(0x83, payload_imu)

            except Exception as e:
                log.error("[FAKE TELEMETRY ERROR] %s", e, exc_info=True)

            time.sleep(period)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t

# ------------------------
# ROS 모드 (선택)
# ------------------------

def try_start_ros_mode(uart: UartLink, tele_cfg: TeleopConfig, *, tx_rate_hz: float, cmd_timeout_ms: int, ros_telemetry_cb_holder: list, encoder_params: dict = None, patrol_actions_params: dict = None, params: dict = None):
    """rclpy 있을 때만 ROS 노드 기동. UART 텔레메트리(IMU/배터리/엔코더)는 telemetry/* 발행, 엔코더→/odom 계산."""
    patrol_node = None  # 분기에서 생성 안 될 수 있으므로 초기화
    if not ROS_AVAILABLE:
        log.info("[ROS] unavailable -> ROS modules not available")
        return None
    
    try:
        import rclpy
        from rclpy.node import Node
        from geometry_msgs.msg import Twist
        from src.ros_cmdvel import CmdVelMux, ControlTopicBridge, RosCmdVelBridge, ArmControlBridge, PatrolActionSchedule
        from src.ros_telemetry_bridge import TelemetryRosPublisher, EncoderOdomNode
    except Exception as e:
        log.warning("[ROS] unavailable -> fallback to DEMO mode. Reason: %s", e)
        return None

    enc_p = encoder_params or {}

    class TeleopPublisher(Node):
        def __init__(self, cfg: TeleopConfig):
            super().__init__("teleop_publisher")
            self.cfg = cfg
            self.pub = self.create_publisher(Twist, "cmd_vel_teleop", 10)
            self.timer = self.create_timer(1.0/30.0, self.tick)  # 30Hz 주기
            self._last_log_ts = 0.0

        def tick(self):
            msg = Twist()
            if STATE.mode == "teleop" and (not STATE.estop):
                vx, vy, wz = state_to_cmd(STATE, self.cfg)
                msg.linear.x = vx
                msg.linear.y = vy
                msg.angular.z = wz
                # 디버깅: 1초마다 상태 로그 (키 입력이 있을 때만)
                now = time.time()
                if (vx != 0.0 or vy != 0.0 or wz != 0.0) and (now - self._last_log_ts >= 1.0):
                    self.get_logger().info(f"Teleop: mode={STATE.mode}, estop={STATE.estop}, pressed={sorted(list(STATE.pressed))}, joy_active={STATE.joy_active}, cmd=({vx:.2f}, {vy:.2f}, {wz:.2f})")
                    self._last_log_ts = now
            else:
                # teleop 모드가 아니거나 estop일 때도 0으로 발행 (명시적)
                msg.linear.x = 0.0
                msg.linear.y = 0.0
                msg.angular.z = 0.0
            self.pub.publish(msg)

    class GatewaySyncNode(Node):
        """Web STATE → mux/cmdvel_bridge 동기화 + feed 소비. 단일 executor용."""
        def __init__(self, mux, cmdvel_bridge, rate_hz: float = 20.0):
            super().__init__("gateway_sync")
            self._mux = mux
            self._cmdvel = cmdvel_bridge
            self.timer = self.create_timer(1.0 / max(1.0, rate_hz), self.tick)

        def tick(self):
            self._mux.set_control_state(mode=STATE.mode, estop=STATE.estop)
            self._cmdvel.set_control_state(mode=STATE.mode, estop=STATE.estop)
            if STATE.feed_level is not None:
                self._cmdvel.request_feed(STATE.feed_level)
                STATE.feed_level = None

    rclpy.init(args=None)

    teleop_node = TeleopPublisher(tele_cfg)
    control_bridge = ControlTopicBridge(get_state_fn=lambda: STATE, rate_hz=20.0)
    
    # 순찰 스케줄 설정 (주기적으로 순찰 시작)
    patrol_p = (params or {}).get("patrol", {}) or {}
    patrol_interval_hours = float(patrol_p.get("interval_hours", 0.0))
    
    # control_mode 발행자 (순찰 시작 시 "auto" 발행용)
    from std_msgs.msg import String
    control_mode_pub = control_bridge.pub_mode  # ControlTopicBridge의 발행자 재사용
    
    # 순찰 스케줄러 생성
    patrol_scheduler = PatrolScheduler(
        interval_hours=patrol_interval_hours,
        control_mode_pub=control_mode_pub,
        nav2_client=None  # TODO: Nav2 액션 클라이언트 추가 시 사용
    )
    
    # 패트롤 액션 스케줄 설정 (함수 인자로 전달받음)
    patrol_actions_p = patrol_actions_params or {}
    action_schedule = PatrolActionSchedule(
        litter_clean_every_patrol=bool(patrol_actions_p.get("litter_clean_every_patrol", True)),
        feed_every_patrol=bool(patrol_actions_p.get("feed_every_patrol", True)),
        feed_level=int(patrol_actions_p.get("feed_level", 2)),
        water_every_patrol=bool(patrol_actions_p.get("water_every_patrol", False)),
    )
    patrol_cfg = PatrolConfig(action_schedule=action_schedule)
    
    # 홈 이동 설정 (params에서 읽기)
    homing_p = (params or {}).get("homing", {}) or {}
    
    # 작업 이벤트 콜백 함수 (PatrolActionScheduler, PatrolLoop에서 호출)
    # patrol 완료 시 duration_sec 전달 → 주간 순찰 시간 저장용
    def job_event_callback(job_type: str, status: str, reason: str = None, **kwargs):
        JOB_EVENTS.add_job(job_type, status, reason, **kwargs)
    
    mux = CmdVelMux()
    cmdvel_bridge = RosCmdVelBridge(
        uart,
        tx_rate_hz=float(tx_rate_hz),
        cmd_timeout_ms=int(cmd_timeout_ms),
    )
    
    # 급식 제어 브릿지 (젯슨 → 파이 → STM)
    feed_bridge = FeedControlBridge(uart)
    
    # PatrolLoop에 FeedControlBridge 참조 및 Homing 설정 전달
    patrol_node = PatrolLoop(
        cfg=patrol_cfg, 
        uart=uart, 
        job_event_callback=job_event_callback,
        use_nav2_signals=True,  # 항상 Nav2 신호 사용
        feed_bridge=feed_bridge,
        home_x=float(homing_p.get("home_x", 1.2)),
        home_y=float(homing_p.get("home_y", 1.7)),
        home_yaw_deg=float(homing_p.get("home_yaw_deg", -180.0))
    )
    if patrol_node is not None:
        set_patrol_node(patrol_node)  # 웹 API에서 스케줄 업데이트 가능하도록 설정
    set_patrol_scheduler(patrol_scheduler)  # 웹 API에서 순찰 간격 업데이트 가능하도록 설정

    # 로봇팔 제어 브릿지 (젯슨 → 파이 → STM)
    # 로봇팔 동작 중에는 바퀴 모터를 잠가야 하므로 cmdvel_bridge 참조 전달
    arm_bridge = ArmControlBridge(uart, cmdvel_bridge=cmdvel_bridge)
    # 작업 완료 이벤트 콜백 설정 (젯슨에서 arm/job_complete 토픽으로 완료 신호 받을 때)
    arm_bridge.set_job_event_callback(job_event_callback)
    
    # 츄르는 웹 API로만 호출 (POST /feed/fill) - ChuruControlBridge 사용 안 함
    
    telemetry_node = TelemetryRosPublisher()  # on_frame에서 decode된 dict → telemetry/* 발행
    ros_telemetry_cb_holder[0] = telemetry_node.publish

    odom_node = EncoderOdomNode(
        meters_per_tick=float(enc_p.get("meters_per_tick", 1e-5)),
        odom_lx=float(enc_p.get("odom_lx", 0.1)),
        odom_ly=float(enc_p.get("odom_ly", 0.1)),
        odom_frame_id=str(enc_p.get("odom_frame_id", "odom")),
        child_frame_id=str(enc_p.get("child_frame_id", "base_link")),
        use_imu_yaw=bool(enc_p.get("use_imu_yaw", True)),  # IMU yaw 우선 사용
        use_imu_gyro=bool(enc_p.get("use_imu_gyro", True)),  # IMU gyro_z 사용
        encoder_filter_alpha=float(enc_p.get("encoder_filter_alpha", 0.7)),  # EMA 필터링 (0.6~0.75)
        fl_estimation_method=str(enc_p.get("fl_estimation_method", "rr")),  # "rr" 또는 "fr_rr_avg"
        encoder_mode=str(enc_p.get("encoder_mode", "3wheel")),  # "auto", "4wheel", "3wheel"
    )

    sync_node = GatewaySyncNode(mux, cmdvel_bridge, rate_hz=20.0)

    # 노드 리스트 확정 (spin 시작 전에 완성)
    nodes = [teleop_node, control_bridge, patrol_node, mux, cmdvel_bridge, arm_bridge, telemetry_node, odom_node, sync_node, patrol_scheduler]

    def ros_spin():
        """Executor는 ros_spin 안에서 생성 (종료/재시작 시 꼬임 방지)."""
        from rclpy.executors import SingleThreadedExecutor
        executor = SingleThreadedExecutor()
        for n in nodes:
            executor.add_node(n)

        try:
            executor.spin()
        except Exception as e:
            print(f"[ROS] spin exception: {e}")
        finally:
            # remove_node 생략 (오히려 꼬일 수 있음), executor.shutdown()만
            try:
                executor.shutdown()
            except Exception:
                pass

    t = threading.Thread(target=ros_spin, daemon=True)
    t.start()
    print("[ROS] started.")

    def shutdown():
        # 1) ROS 종료 신호 (spin() 빠져나오게)
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

        # 2) 노드 destroy는 여기서 한 번만
        for n in nodes:
            try:
                n.destroy_node()
            except Exception:
                pass

        # 3) ros 스핀 쓰레드 합류 (깔끔하게)
        try:
            t.join(timeout=1.0)
        except Exception:
            pass

    return {"thread": t, "shutdown": shutdown}

# ------------------------
# 진입점
# ------------------------

def main():
    configure_logging()
    configure_uvicorn_logging()
    params = load_params()

    uart_p = params.get("uart", {}) or {}
    tele_p = params.get("teleop", {}) or {}
    safe_p = params.get("safety", {}) or {}

    # ROS 토픽이 기본. 연동(실기기/SLAM/Nav2) 시에는 ROS 필수. DEMO는 로컬 웹 연결 테스트용으로만.
    demo_mode = env_bool("DEMO_MODE", False)   # 기본 False = ROS 모드. True면 데모(웹만, ROS 미사용)
    ros_enabled = env_bool("ROS_ENABLED", True) if ROS_AVAILABLE else False  # 기본 True = ROS 토픽 사용
    if demo_mode:
        ros_enabled = False  # 데모 모드: 웹 ↔ gateway 연결 테스트용 (로컬 전용)
    uart_enabled = env_bool("UART_ENABLED", bool(uart_p.get("enabled", False))) and (not demo_mode)

    uart = UartLink(UartConfig(
        port=os.getenv("UART_PORT", uart_p.get("port", "/dev/ttyUSB0")),
        baudrate=int(os.getenv("UART_BAUD", uart_p.get("baudrate", 115200))),
        enabled=uart_enabled,   # demo_mode면 False로 강제됨
    ))

    # ROS 모드일 때 on_frame에서 telemetry/* 토픽으로도 publish (센서/엔코더용)
    ros_telemetry_cb_holder = [None]  # try_start_ros_mode가 [0]에 발행 함수 넣음

    def on_frame(msg_id, payload):
        obj = decode_telemetry(msg_id, payload)
        if obj.get("type") == "battery":
            TELEM.update(battery=obj)
        elif obj.get("type") == "imu":
            TELEM.update(imu=obj)
        elif obj.get("type") == "encoder":
            TELEM.update(encoders=obj)
        elif obj.get("type") == "status":
            # STATUS 메시지 처리: 작업 완료/실패 이벤트 업데이트
            status_type = obj.get("status_type")
            if status_type == 0x01:  # STATUS_TYPE_JOB_COMPLETE
                job_type = obj.get("job_type")
                if job_type:
                    JOB_EVENTS.update_job_by_type(job_type, "success")
            elif status_type == 0x02:  # STATUS_TYPE_JOB_FAILED
                job_type = obj.get("job_type")
                if job_type:
                    JOB_EVENTS.update_job_by_type(job_type, "failed", reason=f"STM32 error code: {obj.get('status_code')}")
            elif status_type == 0x03:  # STATUS_TYPE_ERROR
                error_type = obj.get("error_type", "unknown")
                log.warning("STM32 에러 발생: %s (code=%s)", error_type, obj.get("status_code"))
        cb = ros_telemetry_cb_holder[0]
        if cb:
            cb(obj)

    uart.set_on_frame(on_frame)

    try:
        uart.open()
    except Exception as e:
        log.warning("UART open failed -> forcing dry-run. Reason: %s", e)
        uart.cfg.enabled = False
        try:
            uart.open()
        except Exception:
            pass

    tele_cfg = TeleopConfig(
        linear_speed=float(tele_p.get("linear_speed", 0.2)),
        angular_speed=float(tele_p.get("angular_speed", 0.8)),
    )

    tx_rate_hz = float(uart_p.get("tx_rate_hz", 20))
    cmd_timeout_ms = int(safe_p.get("cmd_timeout_ms", 500))

    enc_p = params.get("encoder", {}) or {}
    patrol_actions_p = params.get("patrol_actions", {}) or {}
    ros_handle = None
    if ros_enabled and ROS_AVAILABLE:
        ros_handle = try_start_ros_mode(
            uart, tele_cfg,
            tx_rate_hz=tx_rate_hz, cmd_timeout_ms=cmd_timeout_ms,
            ros_telemetry_cb_holder=ros_telemetry_cb_holder,
            encoder_params=enc_p,
            patrol_actions_params=patrol_actions_p,
            params=params,
        )
    
    # WebRTC 시그널링 클라이언트 시작 (프론트엔드 버튼 클릭 감지)
    # 프론트엔드가 Offer를 구독하기 시작하면 자동으로 스트리밍 시작
    webrtc_signaling_enabled = env_bool("WEBRTC_SIGNALING_ENABLED", True)
    if webrtc_signaling_enabled and WEBRTC_SIGNALING_AVAILABLE and ros_enabled and ROS_AVAILABLE:
        try:
            run_signaling_client()
            log.info("WebRTC 시그널링 클라이언트 시작됨 (프론트엔드 버튼 클릭 감지 대기 중)")
        except Exception as e:
            log.warning("WebRTC 시그널링 클라이언트 시작 실패: %s", e)

    if (not ros_handle):
        log.info("MODE=DEMO (no ROS). Web 입력 -> UART(dry-run) 프레임 출력. (로컬 웹 테스트용)")
        log.info("실기기/연동 시에는 ROS2(Humble) 설치 후 ROS_ENABLED=1 로 실행 필요.")
        start_demo_teleop_loop(uart, tele_cfg, tx_rate_hz=tx_rate_hz)
        # 데모에서만 가짜 텔레메트리 (선택)
        start_fake_telemetry(uart, hz=2.0)
    else:
        log.info("MODE=ROS 활성화됨.")

    # 웹 서버에 UART 링크 설정 (API에서 사용)
    set_uart_link(uart)

    # 웹 서버 (uvicorn 로그 포맷·레벨은 configure_uvicorn_logging()에서 통일)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn_level = get_uvicorn_log_level()
    mode_str = "DEMO" if demo_mode else "ROS"
    log.info("starting uvicorn on %s:%s (MODE=%s, ROS_ENABLED=%s, UART_ENABLED=%s, LOG_LEVEL=%s)",
             host, port, mode_str, ros_enabled, uart_enabled, uvicorn_level)
    uvicorn.run(app, host=host, port=port, log_level=uvicorn_level)

    # uvicorn 종료 시 여기로 내려옴
    try:
        if ros_handle and ros_handle.get("shutdown"):
            ros_handle["shutdown"]()
    except Exception:
        pass

    try:
        uart.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()
