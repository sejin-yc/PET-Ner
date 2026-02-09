from dataclasses import dataclass, field
import time
import json
import logging
import threading
import asyncio
from typing import Any, Dict, Optional, Set
import os
import subprocess

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None

try:
    import rclpy
    import math
    from rclpy.node import Node
    from std_msgs.msg import String, Bool
    from nav_msgs.msg import Odometry
    from geometry_msgs.msg import PoseWithCovarianceStamped
except Exception:
    rclpy = None
    math = None
    Node = object
    String = None
    Bool = None
    Odometry = None
    PoseWithCovarianceStamped = None

# UART 링크는 main.py에서 전역으로 설정 (또는 함수 인자로 전달)
_uart_link = None

_patrol_node = None  # PatrolLoop 노드 참조 (액션 스케줄 업데이트용)
_patrol_scheduler = None  # PatrolScheduler 노드 참조 (순찰 간격 업데이트용)

# WebRTC 스트리밍 관리
_webrtc_process = None
_webrtc_lock = threading.Lock()

def set_uart_link(uart_link):
    """main.py에서 UART 링크를 설정하기 위한 함수"""
    global _uart_link
    _uart_link = uart_link

def set_patrol_node(patrol_node):
    """main.py에서 PatrolLoop 노드를 설정하기 위한 함수"""
    global _patrol_node
    _patrol_node = patrol_node

def set_patrol_scheduler(patrol_scheduler):
    """main.py에서 PatrolScheduler 노드를 설정하기 위한 함수"""
    global _patrol_scheduler
    _patrol_scheduler = patrol_scheduler

def set_webrtc_process(process):
    """main.py에서 WebRTC 프로세스를 설정하기 위한 함수"""
    global _webrtc_process
    _webrtc_process = process

app = FastAPI(title="PET-NER Pi Gateway (Demo-friendly)")

# 고양이 탐지 영상 정적 제공 (cat_clips/ 폴더)
_clips_dir = os.path.abspath(os.getenv("CLIPS_DIR", "cat_clips"))
os.makedirs(_clips_dir, exist_ok=True)
app.mount("/cat_clips", StaticFiles(directory=_clips_dir), name="cat_clips")


def _gateway_debug() -> bool:
    """요청마다 로그 (GATEWAY_DEBUG=1, 터미널 복잡)."""
    return os.getenv("GATEWAY_DEBUG", "").strip().lower() in ("1", "true", "yes", "y", "on")


def _gateway_debug_summary() -> bool:
    """10초마다 API 호출 횟수 한 줄만 (GATEWAY_DEBUG_SUMMARY=1)."""
    return os.getenv("GATEWAY_DEBUG_SUMMARY", "").strip().lower() in ("1", "true", "yes", "y", "on")


_request_counts: Dict[str, int] = {}
_metrics_requests_total: Dict[str, int] = {}  # Prometheus: 요청 횟수 누적
_metrics_duration: Dict[str, tuple] = {}  # key -> (sum_seconds, count) 요청 지연
_request_counts_lock = threading.Lock()


@app.middleware("http")
async def _debug_log_requests(request, call_next):
    path = request.url.path
    method = request.method
    key = f"{method} {path}"
    start = time.time()
    with _request_counts_lock:
        _metrics_requests_total[key] = _metrics_requests_total.get(key, 0) + 1
    if _gateway_debug_summary():
        with _request_counts_lock:
            _request_counts[key] = _request_counts.get(key, 0) + 1
        response = await call_next(request)
        duration = time.time() - start
        with _request_counts_lock:
            s, c = _metrics_duration.get(key, (0.0, 0))
            _metrics_duration[key] = (s + duration, c + 1)
        return response
    if _gateway_debug():
        body_snippet = ""
        if method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    body_snippet = body.decode("utf-8", errors="replace")[:500]
                    if len(body) > 500:
                        body_snippet += "..."
            except Exception:
                body_snippet = "(read error)"
        log.debug("→ %s %s %s", method, path, f" body={body_snippet}" if body_snippet else "")
    response = await call_next(request)
    duration = time.time() - start
    with _request_counts_lock:
        s, c = _metrics_duration.get(key, (0.0, 0))
        _metrics_duration[key] = (s + duration, c + 1)
    if _gateway_debug():
        log.debug("← %s %s %s", method, path, response.status_code)
    return response


@dataclass
class WebState:
    mode: str = "teleop"     # "teleop" | "auto"
    estop: bool = False
    pressed: set = field(default_factory=set)   # {"up","down","left","right","rot_l","rot_r"}
    joy_x: float = 0.0            # 전진(+)/후진(-)
    joy_y: float = 0.0            # 좌(+)/우(-)
    joy_active: bool = False      # 조이스틱 입력 유효 여부

    last_ts: float = field(default_factory=lambda: time.time())
    feed_level: int | None = None               # 1~3 or None

STATE = WebState()


class TelemetryHub:
    """ROS(또는 기타)에서 들어온 텔레메트리를 Web으로 내보내기 위한 in-memory 허브."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latest: Dict[str, Any] = {
            "battery": None,
            "imu": None,
            "encoders": None,
            "odom": None,
            "amcl_pose": None,
            "ts": None,
        }
        self._clients: Set[WebSocket] = set()

    def update(self, *, battery=None, imu=None, encoders=None, odom=None, amcl_pose=None):
        with self._lock:
            if battery is not None:
                self._latest["battery"] = battery
            if imu is not None:
                self._latest["imu"] = imu
            if encoders is not None:
                self._latest["encoders"] = encoders
            if odom is not None:
                self._latest["odom"] = odom
            if amcl_pose is not None:
                self._latest["amcl_pose"] = amcl_pose
            self._latest["ts"] = time.time()
            payload = dict(self._latest)

        # 전파(가능한 만큼). FastAPI WS는 await 필요하므로
        # /ws/telemetry 루프에서 pull로 최신값만 꺼내 쓰게 저장만 함.
        return payload

    def latest(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest)


TELEM = TelemetryHub()


class JobEventCollector:
    """작업 완료 이벤트 수집 및 BE 전송."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: list = []  # 최근 작업 이벤트 목록 (최대 100개)
        self._job_id_counter = 0
        self._be_url = os.getenv("BE_SERVER_URL", None)  # BE 서버 URL (선택)
    
    def _send_to_be(self, job: dict):
        """BE 서버로 작업 이벤트 전송 (HTTP POST). Log 엔티티 형식 일치."""
        if not self._be_url or not requests:
            return
        
        # 순찰 완료 시 duration (주간 순찰 시간용)
        # Log.durationNum: 분 단위 (LogCharts가 "분"으로 표시)
        duration_sec = job.get("duration_sec")
        if duration_sec is not None:
            duration_num = max(0, int(round(duration_sec / 60.0)))
            duration_str = f"{duration_num}분"
        else:
            duration_num = 0
            duration_str = "0분"
        
        # Log 엔티티 필드와 정확히 일치
        status_map = {"success": "completed", "failed": "failed", "in_progress": "in-progress"}
        status_str = status_map.get(job["status"], "in-progress")
        mode_str = "auto" if job["type"] == "patrol" else "manual"
        details = f"{job['type']} 작업 - {job['status']}" + (f" (이유: {job.get('reason')})" if job.get("reason") else "")
        
        try:
            log_data = {
                "userId": int(os.getenv("BE_USER_ID", "1")),
                "mode": mode_str,
                "status": status_str,
                "duration": duration_str,
                "durationNum": duration_num,
                "distance": 0.0,
                "detectionCount": 0,
                "details": details,
            }
            
            response = requests.post(
                f"{self._be_url}/api/logs",
                json=log_data,
                timeout=2.0
            )
            if response.status_code in (200, 201):
                log.info("JobEvent BE 전송 성공: %s - %s", job["type"], job["status"])
        except Exception as e:
            log.warning("JobEvent BE 전송 실패: %s", e)
    
    def add_job(self, job_type: str, status: str, reason: str = None, **kwargs):
        """
        작업 이벤트 추가.
        
        Args:
            job_type: "patrol", "feed", "water", "litter_clean"
            status: "success", "failed", "in_progress"
            reason: 실패 이유 (선택)
            **kwargs: duration_sec 등 (patrol 완료 시 순찰 시간, 초 단위)
        """
        with self._lock:
            self._job_id_counter += 1
            job = {
                "jobId": self._job_id_counter,
                "type": job_type,
                "status": status,
                "startedAt": time.time(),
                "endedAt": time.time() if status in ("success", "failed") else None,
                "reason": reason,
                **{k: v for k, v in kwargs.items() if k in ("duration_sec",)}
            }
            self._jobs.append(job)
            # 최대 100개만 유지
            if len(self._jobs) > 100:
                self._jobs = self._jobs[-100:]
            
            # BE로 실시간 전송 (WebSocket처럼 즉시 전송)
            self._send_to_be(job)
            
            return job
    
    def update_job(self, job_id: int, status: str, reason: str = None):
        """작업 상태 업데이트."""
        with self._lock:
            for job in self._jobs:
                if job["jobId"] == job_id:
                    job["status"] = status
                    job["endedAt"] = time.time()
                    if reason:
                        job["reason"] = reason
                    # BE로 업데이트 전송
                    self._send_to_be(job)
                    return job
        return None
    
    def update_job_by_type(self, job_type: str, status: str, reason: str = None):
        """작업 타입으로 최근 in_progress 작업 찾아서 상태 업데이트 (STATUS 메시지용)."""
        with self._lock:
            # 최근 작업부터 역순으로 찾기 (가장 최근 in_progress 작업)
            for job in reversed(self._jobs):
                if job["type"] == job_type and job["status"] == "in_progress":
                    job["status"] = status
                    job["endedAt"] = time.time()
                    if reason:
                        job["reason"] = reason
                    # BE로 업데이트 전송
                    self._send_to_be(job)
                    return job
        return None
    
    def get_jobs(self, limit: int = 50) -> list:
        """최근 작업 목록 조회."""
        with self._lock:
            return list(reversed(self._jobs[-limit:]))


JOB_EVENTS = JobEventCollector()


def _quat_to_yaw(q) -> float:
    """Quaternion(x,y,z,w) → yaw (rad)."""
    if math is None:
        return 0.0
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class _TelemetrySub(Node):
    """FastAPI 프로세스 안에서 ROS topic을 subscribe 해서 TELEM에 반영."""

    def __init__(self):
        super().__init__("telemetry_sub")

        self.create_subscription(String, "telemetry/battery", self._on_batt, 10)
        self.create_subscription(String, "telemetry/imu", self._on_imu, 10)
        self.create_subscription(String, "telemetry/encoders", self._on_enc, 10)
        if Odometry is not None:
            self.create_subscription(Odometry, "odom", self._on_odom, 10)
        if PoseWithCovarianceStamped is not None:
            self.create_subscription(PoseWithCovarianceStamped, "amcl_pose", self._on_amcl_pose, 10)

    def _safe_json(self, s: str):
        try:
            return json.loads(s)
        except Exception:
            return {"raw": s}

    def _on_batt(self, msg: String):
        TELEM.update(battery=self._safe_json(msg.data))

    def _on_imu(self, msg: String):
        TELEM.update(imu=self._safe_json(msg.data))

    def _on_enc(self, msg: String):
        TELEM.update(encoders=self._safe_json(msg.data))

    def _on_odom(self, msg):
        """/odom (nav_msgs/Odometry) → TELEM.odom {x, y, yaw}."""
        if Odometry is None:
            return
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        TELEM.update(odom={"x": float(p.x), "y": float(p.y), "yaw": _quat_to_yaw(q)})

    def _on_amcl_pose(self, msg):
        """/amcl_pose (geometry_msgs/PoseWithCovarianceStamped) → TELEM.amcl_pose {x, y, yaw}."""
        if PoseWithCovarianceStamped is None:
            return
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        TELEM.update(amcl_pose={"x": float(p.x), "y": float(p.y), "yaw": _quat_to_yaw(q)})


def _start_ros_telemetry_subscriber_once():
    if not rclpy:
        return

    # rclpy는 전역 init이 1회만 되어야 함
    try:
        rclpy.init(args=None)
    except Exception:
        pass

    node = _TelemetrySub()

    def _spin():
        try:
            rclpy.spin(node)
        except Exception:
            pass
        try:
            node.destroy_node()
        except Exception:
            pass

    th = threading.Thread(target=_spin, daemon=True)
    th.start()


_ROS_SUB_STARTED = False


def _gateway_stats_loop():
    """10초마다 API 호출 횟수 한 줄만 (GATEWAY_DEBUG_SUMMARY)."""
    while True:
        time.sleep(10.0)
        with _request_counts_lock:
            if not _request_counts:
                continue
            parts = [f"{k} {v}" for k, v in sorted(_request_counts.items(), key=lambda x: -x[1])]
            _request_counts.clear()
        log.info("10s: %s", ", ".join(parts))


@app.on_event("startup")
def _startup_hook():
    global _ROS_SUB_STARTED
    if not _ROS_SUB_STARTED:
        _ROS_SUB_STARTED = True
        _start_ros_telemetry_subscriber_once()
    if _gateway_debug():
        log.info("GATEWAY_DEBUG=1: API 요청/응답마다 로그 (터미널 복잡)")
    if _gateway_debug_summary():
        th = threading.Thread(target=_gateway_stats_loop, daemon=True)
        th.start()
        log.info("GATEWAY_DEBUG_SUMMARY=1: 10초마다 API 호출 횟수 한 줄만 출력")


@app.get("/debug/routes")
def debug_routes():
    """등록된 라우트 목록 (디버그용)."""
    routes = []
    for r in app.routes:
        path = getattr(r, "path", str(r))
        methods = list(getattr(r, "methods", set()) or [])
        name = getattr(r, "name", "")
        routes.append({"path": path, "methods": methods, "name": name})
    return {"routes": routes}


@app.get("/debug/state")
def debug_state():
    """Pi Gateway 내부 상태 조회 (로그 없음). curl http://localhost:8000/debug/state"""
    return {
        "mode": STATE.mode,
        "estop": STATE.estop,
        "pressed": sorted(list(STATE.pressed)),
        "joy_x": STATE.joy_x,
        "joy_y": STATE.joy_y,
        "joy_active": STATE.joy_active,
        "feed_level": STATE.feed_level,
        "last_ts": STATE.last_ts,
    }


@app.get("/metrics")
def metrics():
    """Prometheus 형식 메트릭 (요청 횟수·지연 시간)."""
    lines = [
        "# HELP gateway_requests_total Total HTTP requests by method and path",
        "# TYPE gateway_requests_total counter",
    ]
    with _request_counts_lock:
        for key in sorted(_metrics_requests_total.keys()):
            count = _metrics_requests_total[key]
            method, path = key.split(" ", 1) if " " in key else ("", key)
            path_esc = path.replace('"', '\\"')
            lines.append(f'gateway_requests_total{{method="{method}",path="{path_esc}"}} {count}')
        lines.extend([
            "",
            "# HELP gateway_request_duration_seconds_sum Total request duration in seconds",
            "# TYPE gateway_request_duration_seconds_sum counter",
        ])
        for key in sorted(_metrics_duration.keys()):
            s, _ = _metrics_duration[key]
            method, path = key.split(" ", 1) if " " in key else ("", key)
            path_esc = path.replace('"', '\\"')
            lines.append(f'gateway_request_duration_seconds_sum{{method="{method}",path="{path_esc}"}} {s:.6f}')
        lines.extend([
            "",
            "# HELP gateway_request_duration_seconds_count Total request count (for duration)",
            "# TYPE gateway_request_duration_seconds_count counter",
        ])
        for key in sorted(_metrics_duration.keys()):
            _, c = _metrics_duration[key]
            method, path = key.split(" ", 1) if " " in key else ("", key)
            path_esc = path.replace('"', '\\"')
            lines.append(f'gateway_request_duration_seconds_count{{method="{method}",path="{path_esc}"}} {c}')
    lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@app.get("/robot/health")
def robot_health():
    """
    로봇 상태 조회
    """
    latest = TELEM.latest()
    battery_data = latest.get("battery", {}) or {}
    
    return {
        "resultCode": "SUCCESS",
        "message": "Robot health retrieved successfully",
        "data": {
            "mode": STATE.mode,
            "estop": STATE.estop,
            "battery": battery_data.get("soc_percent", 0) if isinstance(battery_data, dict) else 0,
            "charging": battery_data.get("charging", False) if isinstance(battery_data, dict) else False,
            "network": "online" if _uart_link is not None else "offline",
            "timestamp": time.time()
        }
    }


@app.get("/telemetry/latest")
def telemetry_latest():
    return JSONResponse(TELEM.latest())


@app.get("/robot/state")
def robot_state():
    """    
    Returns:
        mode: "auto|teleop"
        status: "moving|stopped|avoiding" (현재는 stopped만 지원)
        battery: 배터리 잔량 (%)
        network: "online|offline"
        pose: 현재 위치 {x, y, yaw}
        target: 목표 위치 {x, y} (현재는 None)
        nextWaypointIndex: 다음 웨이포인트 인덱스 (현재는 None)
    """
    latest = TELEM.latest()
    battery_data = latest.get("battery", {}) or {}
    imu_data = latest.get("imu", {}) or {}
    odom_data = latest.get("odom", {}) or {}
    amcl_data = latest.get("amcl_pose", {}) or {}
    
    # 상태 판단 (간단한 로직)
    status = "stopped"
    if STATE.mode == "auto" and not STATE.estop:
        status = "moving"
    elif STATE.estop:
        status = "stopped"
    elif len(STATE.pressed) > 0 or STATE.joy_active:
        status = "moving"
    
    pose_src = amcl_data if isinstance(amcl_data, dict) and amcl_data.get("x") is not None else odom_data
    x = float(pose_src.get("x", 0.0)) if isinstance(pose_src, dict) else 0.0
    y = float(pose_src.get("y", 0.0)) if isinstance(pose_src, dict) else 0.0
    yaw = float(pose_src.get("yaw", 0.0)) if isinstance(pose_src, dict) else (
        float(imu_data.get("yaw", 0.0)) if isinstance(imu_data, dict) else 0.0
    )
    
    return {
        "resultCode": "SUCCESS",
        "message": "Robot state retrieved successfully",
        "data": {
            "mode": STATE.mode,
            "status": status,
            "battery": battery_data.get("soc_percent", 0) if isinstance(battery_data, dict) else 0,
            "network": "online" if _uart_link is not None else "offline",
            "pose": {"x": x, "y": y, "yaw": yaw},
            "target": None,  # TODO: Nav2 연동 시 목표 위치
            "nextWaypointIndex": None  # TODO: Nav2 연동 시 웨이포인트 인덱스
        }
    }


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    """
    웹 UI가 실시간 텔레메트리를 보고 싶을 때.

    - 서버는 TELEM 최신값을 주기적으로 push
    - ROS subscriber가 없으면(None) 값은 계속 None일 수 있음
    """
    await ws.accept()
    try:
        while True:
            # 클라이언트가 ping을 보내도 되고, 아무것도 안 보내도 됨
            try:
                # 0.2s 동안 입력 없으면 timeout
                data = await ws.receive_text()
                _ = data  # 사용 안 함
            except Exception:
                pass

            await ws.send_json({"type": "telemetry", **TELEM.latest()})
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass
        return

@app.post("/robot/estop")
def robot_estop(body: dict):
    """
    비상정지 실행 
    
    Body:
        {"enabled": true, "reason": "String(optional)"}
    """
    STATE.estop = bool(body.get("enabled", True))
    STATE.last_ts = time.time()
    reason = body.get("reason", "")
    return {
        "resultCode": "SUCCESS",
        "message": "E-STOP applied"
    }

@app.post("/robot/control")
def robot_control(body: dict):
    """
    제어 명령 (HTTP) - MQTT 브릿지 등에서 WebSocket 대신 사용.
    Body: {"type": "press", "key": "up", "down": true, "timestamp": 0}
      또는 {"type": "joy", "joy_x": 0.5, "joy_y": 0, "joy_active": true, "timestamp": 0}
    """
    t = body.get("type")
    if t == "press":
        key = str(body.get("key", ""))
        down = bool(body.get("down", False))
        if down:
            STATE.pressed.add(key)
        else:
            STATE.pressed.discard(key)
        STATE.last_ts = float(body.get("timestamp", time.time()))
        log.info("[CONTROL] press: key=%s down=%s pressed=%s", key, down, sorted(list(STATE.pressed)))
    elif t == "joy":
        STATE.joy_x = float(body.get("joy_x", 0.0))
        STATE.joy_y = float(body.get("joy_y", 0.0))
        STATE.joy_active = bool(body.get("joy_active", False))
        STATE.last_ts = float(body.get("timestamp", time.time()))
        log.info("[CONTROL] joy: x=%.2f y=%.2f active=%s", STATE.joy_x, STATE.joy_y, STATE.joy_active)
    else:
        log.warning("[CONTROL] unknown type: %s body=%s", t, body)
    return {"ok": True}


@app.post("/robot/mode")
def robot_mode(body: dict):
    """
    모드 전환 (API 명세서 경로).
    
    Body:
        {"mode": "auto | teleop"}
    """
    mode = str(body.get("mode", "teleop"))
    STATE.mode = "auto" if mode == "auto" else "teleop"
    STATE.last_ts = time.time()
    return {
        "resultCode": "SUCCESS",
        "message": "Mode updated",
        "data": {"mode": STATE.mode}
    }

@app.post("/action/feed")
def feed(body: dict):
    """
    급식 실행 API.
    
    현재 상태:
    - 급식은 패트롤 중 자동으로 실행됩니다 (`PatrolActionScheduler`가 `auto_feed_interval_s` 간격으로 실행).
    - 웹 UI에는 급식 버튼이 없습니다 (웹에는 츄르 버튼만 있음).
    - 현재는 이 API를 사용하지 않습니다.
    
    향후 확장 가능성:
    - 웹에서 사용자가 시간을 설정하면 로봇이 급식장소로 이동하여 급식을 실행하는 기능에 사용될 수 있습니다.
    
    Body:
        {"level": 1~3} - 급식 레벨 (서보모터로 개폐통 열어서 급식)
                         1=소량, 2=중량, 3=대량
    """
    if _uart_link is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "UART not available"})
    
    try:
        level = int(body.get("level", 1))
        level = max(1, min(3, level))
    except Exception:
        level = 1
    
    from src.uart_frames import make_feed_frame
    try:
        _uart_link.send(make_feed_frame(level))
        # 작업 이벤트 추가 (급식 시작)
        job = JOB_EVENTS.add_job("feed", "in_progress")
        # TODO: STM32에서 완료 신호를 받으면 "success"로 업데이트
        # 일단 5초 후 자동 완료로 가정 (나중에 STM32 신호로 교체)
        def mark_complete():
            time.sleep(5.0)  # 급식 완료 대기 (실제로는 STM32 신호 대기)
            JOB_EVENTS.update_job(job["jobId"], "success")
        threading.Thread(target=mark_complete, daemon=True).start()
        return {"ok": True, "level": level}
    except Exception as e:
        # 작업 실패 이벤트
        JOB_EVENTS.add_job("feed", "failed", reason=str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# ---------- 로봇팔 제어 API ----------

@app.post("/arm/start")
def arm_start(body: dict):
    """로봇팔 동작 시작."""
    if _uart_link is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "UART not available"})
    
    try:
        action_id = int(body.get("action_id", 0))
        action_id = max(0, min(255, action_id))
    except Exception:
        action_id = 0
    
    from src.uart_frames import make_arm_start_frame
    try:
        _uart_link.send(make_arm_start_frame(action_id))
        # 변치우기 작업 이벤트 (action_id=1일 때)
        if action_id == 1:
            job = JOB_EVENTS.add_job("litter_clean", "in_progress")
            # 완료 신호는 젯슨이 arm/job_complete 토픽으로 발행
            # (젯슨이 로봇팔 제어하므로 젯슨이 완료 판단)
            # TODO: 젯슨에서 완료 신호가 없으면 타이머로 fallback (임시)
            def mark_complete_fallback():
                time.sleep(30.0)  # 젯슨 신호 없을 때 fallback
                JOB_EVENTS.update_job(job["jobId"], "success")
            threading.Thread(target=mark_complete_fallback, daemon=True).start()
        return {"ok": True, "action_id": action_id}
    except Exception as e:
        # 작업 실패 이벤트
        if action_id == 1:
            JOB_EVENTS.add_job("litter_clean", "failed", reason=str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.post("/arm/position_correct")
def arm_position_correct(body: dict):
    """로봇 위치 보정."""
    if _uart_link is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "UART not available"})
    
    try:
        dx = float(body.get("dx", 0.0))
        dy = float(body.get("dy", 0.0))
        dz = float(body.get("dz", 0.0))
    except Exception:
        dx = dy = dz = 0.0
    
    from src.uart_frames import make_arm_position_correct_frame
    try:
        _uart_link.send(make_arm_position_correct_frame(dx, dy, dz))
        return {"ok": True, "dx": dx, "dy": dy, "dz": dz}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.post("/patrol/schedule")
def patrol_schedule(body: dict):
    """
    순찰 스케줄 설정.
    
    Body:
        interval_hours: 순찰 간격 (시간). 0이면 비활성화. 예: 4.0 = 4시간마다 순찰
    """
    if _patrol_scheduler is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "PatrolScheduler not available"})
    
    try:
        interval_hours = float(body.get("interval_hours", 0.0))
        interval_hours = max(0.0, interval_hours)  # 음수 방지
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid interval_hours"})
    
    try:
        _patrol_scheduler.set_interval(interval_hours)
        return {"ok": True, "interval_hours": interval_hours}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.get("/patrol/schedule")
def get_patrol_schedule():
    """순찰 스케줄 조회."""
    if _patrol_scheduler is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "PatrolScheduler not available"})
    
    return {
        "ok": True,
        "interval_hours": _patrol_scheduler.interval_hours,
        "is_patrolling": _patrol_scheduler.is_patrolling,
        "last_patrol_ts": _patrol_scheduler.last_patrol_ts
    }

@app.post("/arm/water")
def arm_water(body: dict):
    """
    로봇팔 급수.
    
    water_action:
    - 0 = 위치 이동/정지 (바퀴 해제)
    - 1 = 물그릇 집기 (바퀴 해제)
    - 2 = 물 버리기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
    - 3 = 물 받기 (바퀴 잠금 - 아루코 마커로 정밀 위치 조정 완료 후)
    - 4 = 물그릇 두기 (바퀴 잠금)
    """
    if _uart_link is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "UART not available"})
    
    try:
        water_action = int(body.get("action", 0))
        water_action = max(0, min(4, water_action))  # 0~4 범위
    except Exception:
        water_action = 0
    
    from src.uart_frames import make_arm_water_frame
    try:
        _uart_link.send(make_arm_water_frame(water_action))
        # 급수 작업 이벤트
        if water_action == 1:
            # 급수 시작
            job = JOB_EVENTS.add_job("water", "in_progress")
            # 완료 신호는 젯슨이 arm/job_complete 토픽으로 발행
            # (젯슨이 로봇팔 제어하므로 젯슨이 완료 판단)
            # TODO: 젯슨에서 완료 신호가 없으면 타이머로 fallback (임시)
            def mark_complete_fallback():
                time.sleep(60.0)  # 급수 전체 완료 대기 (젯슨 신호 없을 때 fallback)
                JOB_EVENTS.update_job(job["jobId"], "success")
            threading.Thread(target=mark_complete_fallback, daemon=True).start()
        elif water_action == 4:
            # 물그릇 두기 단계 (급수 마지막 단계이지만, 완료는 젯슨이 판단)
            # 완료 신호는 젯슨이 arm/job_complete로 발행
            pass
        return {"ok": True, "action": water_action}
    except Exception as e:
        # 작업 실패 이벤트
        JOB_EVENTS.add_job("water", "failed", reason=str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# ---------- 츄르 주기 API ----------

@app.post("/feed/fill")
def feed_fill(body: dict):
    """
    츄르(간식) 주기 API - 웹 UI 버튼 클릭 시 사용.
    
    웹 UI에서 사용자가 츄르 버튼을 클릭하면 즉시 실행됩니다.
    급식(FEED)과는 별개입니다. 급식은 패트롤 중 자동 실행됩니다.
    
    Body:
        {"enable": 0 또는 1} - 0=정지, 1=츄르 주기 (주사기 밀기)
    """
    if _uart_link is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "UART not available"})
    
    try:
        enable = int(body.get("enable", 1))
        enable = max(0, min(1, enable))
    except Exception:
        enable = 1
    
    from src.uart_frames import make_churu_frame
    try:
        _uart_link.send(make_churu_frame(enable))
        return {"ok": True, "enable": enable}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# ---------- 카메라 스트리밍 API ----------

@app.post("/camera/stream/start")
def camera_stream_start(body: dict = None):
    """
    WebRTC 카메라 스트리밍 시작.
    
    대시보드에서 실시간 스트리밍 버튼을 눌렀을 때 호출됩니다.
    """
    global _webrtc_process
    
    with _webrtc_lock:
        if _webrtc_process is not None and _webrtc_process.is_alive():
            return {"ok": True, "status": "already_running", "message": "스트리밍이 이미 실행 중입니다"}
        
        try:
            import subprocess
            import sys
            script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "robot_webrtc.py")
            
            # 환경 변수 설정
            env = os.environ.copy()
            env["BE_WS_URL"] = os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws")
            env["CAMERA_TOPIC"] = os.getenv("CAMERA_TOPIC", "/front_cam/compressed")
            env["ROBOT_ID"] = os.getenv("ROBOT_ID", "1")
            
            # ROS2 환경 설정
            if "ROS_DISTRO" not in env:
                env["ROS_DISTRO"] = "humble"
            
            # 프로세스 시작
            process = subprocess.Popen(
                [sys.executable, script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            _webrtc_process = process
            log.info("WebRTC 스트리밍 시작됨 (PID: %s)", process.pid)
            return {
                "ok": True,
                "status": "started",
                "message": "스트리밍이 시작되었습니다",
                "pid": process.pid
            }
        except Exception as e:
            log.error("WebRTC 스트리밍 시작 실패: %s", e, exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": str(e), "message": "스트리밍 시작 실패"}
            )

@app.post("/camera/stream/stop")
def camera_stream_stop(body: dict = None):
    """
    WebRTC 카메라 스트리밍 중지.
    
    대시보드에서 스트리밍 중지 버튼을 눌렀을 때 호출됩니다.
    """
    global _webrtc_process
    
    with _webrtc_lock:
        if _webrtc_process is None:
            return {"ok": True, "status": "not_running", "message": "스트리밍이 실행 중이 아닙니다"}
        
        try:
            if _webrtc_process.poll() is None:  # 프로세스가 실행 중이면
                _webrtc_process.terminate()
                try:
                    _webrtc_process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    _webrtc_process.kill()
                    _webrtc_process.wait()
                log.info("WebRTC 스트리밍 중지됨")
            
            _webrtc_process = None
            return {
                "ok": True,
                "status": "stopped",
                "message": "스트리밍이 중지되었습니다"
            }
        except Exception as e:
            log.error("WebRTC 스트리밍 중지 실패: %s", e, exc_info=True)
            _webrtc_process = None
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": str(e), "message": "스트리밍 중지 실패"}
            )

@app.get("/camera/stream/status")
def camera_stream_status():
    """
    WebRTC 카메라 스트리밍 상태 조회.
    """
    global _webrtc_process
    
    with _webrtc_lock:
        if _webrtc_process is None:
            return {"ok": True, "status": "stopped", "running": False}
        
        is_running = _webrtc_process.poll() is None
        return {
            "ok": True,
            "status": "running" if is_running else "stopped",
            "running": is_running,
            "pid": _webrtc_process.pid if _webrtc_process else None
        }

@app.post("/patrol/actions/schedule")
async def set_patrol_action_schedule(body: dict):
    """
    패트롤 중 액션 스케줄 설정.
    
    Body:
        litter_clean_daily_hour (int, optional): 변치우기: 저녁 순찰 시간 (시, 0~23). -1이면 비활성화. 예: 18 = 저녁 6시 이후 순찰 시 실행
        litter_clean_daily_minute (int, optional): 변치우기: 저녁 순찰 시간 (분, 0~59)
        auto_feed_interval_s (float, optional): 자동 급식 간격 (초). 0이면 비활성화
        auto_feed_level (int, optional): 자동 급식 레벨 (1~3, 기본 2)
        water_every_patrol (bool, optional): 급수: 매번 순찰할 때마다 실행
    
    예시:
        {
            "litter_clean_daily_hour": 18,      # 저녁 6시 이후 순찰 시 변치우기
            "litter_clean_daily_minute": 0,
            "auto_feed_interval_s": 7200.0,      # 2시간마다 자동 급식
            "auto_feed_level": 2,
            "water_every_patrol": true            # 매번 순찰할 때마다 급수
        }
    """
    if _patrol_node is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Patrol node not available"})
    
    try:
        from src.ros_cmdvel import PatrolActionSchedule
        
        schedule = PatrolActionSchedule(
            litter_clean_daily_hour=int(body.get("litter_clean_daily_hour", -1)),
            litter_clean_daily_minute=int(body.get("litter_clean_daily_minute", 0)),
            auto_feed_interval_s=float(body.get("auto_feed_interval_s", 0.0)),
            auto_feed_level=int(body.get("auto_feed_level", 2)),
            water_every_patrol=bool(body.get("water_every_patrol", False)),
        )
        
        # 범위 체크
        schedule.litter_clean_daily_hour = max(-1, min(23, schedule.litter_clean_daily_hour))
        schedule.litter_clean_daily_minute = max(0, min(59, schedule.litter_clean_daily_minute))
        schedule.auto_feed_level = max(1, min(3, schedule.auto_feed_level))
        
        # PatrolLoop에 스케줄 업데이트
        _patrol_node.update_action_schedule(schedule)
        
        return {
            "ok": True,
            "schedule": {
                "litter_clean_daily_hour": schedule.litter_clean_daily_hour,
                "litter_clean_daily_minute": schedule.litter_clean_daily_minute,
                "auto_feed_interval_s": schedule.auto_feed_interval_s,
                "auto_feed_level": schedule.auto_feed_level,
                "water_every_patrol": schedule.water_every_patrol,
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.get("/patrol/actions/schedule")
async def get_patrol_action_schedule():
    """
    현재 패트롤 액션 스케줄 조회.
    """
    if _patrol_node is None or _patrol_node.cfg.action_schedule is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Patrol schedule not available"})
    
    schedule = _patrol_node.cfg.action_schedule
    return {
        "ok": True,
        "schedule": {
            "litter_clean_daily_hour": schedule.litter_clean_daily_hour,
            "litter_clean_daily_minute": schedule.litter_clean_daily_minute,
            "auto_feed_interval_s": schedule.auto_feed_interval_s,
            "auto_feed_level": schedule.auto_feed_level,
            "water_every_patrol": schedule.water_every_patrol,
        }
    }

@app.get("/robot/jobs")
def robot_jobs(limit: int = 50):
    """
    작업 결과 이벤트 조회 (API 명세서 경로).
    
    Query:
        limit (optional): 조회할 작업 수 (기본 50)
    """
    jobs = JOB_EVENTS.get_jobs(limit=limit)
    
    # 명세서 형식으로 변환
    formatted_jobs = []
    for job in jobs:
        formatted_job = {
            "jobId": job["jobId"],
            "type": job["type"],
            "status": job["status"],
            "endedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.localtime(job["endedAt"])) if job["endedAt"] else None
        }
        if job.get("reason"):
            formatted_job["reason"] = job["reason"]
        formatted_jobs.append(formatted_job)
    
    return {
        "resultCode": "SUCCESS",
        "message": "Robot jobs retrieved successfully",
        "data": {
            "jobs": formatted_jobs
        }
    }

@app.websocket("/ws/teleop")
async def ws_teleop(ws: WebSocket):
    await ws.accept()
    # 연결 시 초기 상태 전송
    await ws.send_json({
        "type": "state",
        "mode": STATE.mode,
        "estop": STATE.estop,
        "pressed": sorted(list(STATE.pressed)),
        "feed_level": STATE.feed_level,
        "timestamp": time.time(),
    })
    log.info("WS/TELEOP client connected, mode=%s, estop=%s", STATE.mode, STATE.estop)
    try:
        while True:
            data = await ws.receive_json()

            t = data.get("type")
            if t == "press":
                key = str(data.get("key", ""))
                down = bool(data.get("down", False))
                if down:
                    STATE.pressed.add(key)
                else:
                    STATE.pressed.discard(key)
                STATE.last_ts = float(data.get("timestamp", time.time()))
                log.debug("WS/TELEOP key=%s down=%s pressed=%s", key, down, sorted(list(STATE.pressed)))
            elif t == "joy":
                # joy_x: 전진/후진, joy_y: 좌/우(슬라이드)
                # joy_active: 조이스틱 입력 유효 플래그
                STATE.joy_x = float(data.get("joy_x", 0.0))
                STATE.joy_y = float(data.get("joy_y", 0.0))
                STATE.joy_active = bool(data.get("joy_active", False))
                STATE.last_ts = float(data.get("timestamp", time.time()))
                if STATE.joy_active:
                    log.debug("WS/TELEOP joy: x=%.2f y=%.2f active=%s", STATE.joy_x, STATE.joy_y, STATE.joy_active)

            elif t == "mode":
                mode = str(data.get("mode", "teleop"))
                old_mode = STATE.mode
                STATE.mode = "auto" if mode == "auto" else "teleop"
                STATE.last_ts = float(data.get("timestamp", time.time()))
                if old_mode != STATE.mode:
                    log.info("WS/TELEOP mode changed: %s -> %s", old_mode, STATE.mode)

            elif t == "estop":
                old_estop = STATE.estop
                STATE.estop = bool(data.get("value", True))
                STATE.last_ts = float(data.get("timestamp", time.time()))
                if old_estop != STATE.estop:
                    log.info("WS/TELEOP estop changed: %s -> %s", old_estop, STATE.estop)

            elif t == "feed":
                level = int(data.get("level", 1))
                level = max(1, min(3, level))
                STATE.feed_level = level
                STATE.last_ts = float(data.get("timestamp", time.time()))

            await ws.send_json({
                "type": "state",
                "mode": STATE.mode,
                "estop": STATE.estop,
                "pressed": sorted(list(STATE.pressed)),
                "feed_level": STATE.feed_level,
                "timestamp": time.time(),
            })
    except WebSocketDisconnect:
        return
    except Exception as e:
        log.exception("WS/TELEOP error: %s", e)
        await ws.close()
        return
