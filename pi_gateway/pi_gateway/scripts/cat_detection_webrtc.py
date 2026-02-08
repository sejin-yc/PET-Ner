#!/usr/bin/env python3
"""
고양이 탐지 + WebRTC 스트리밍 통합 서비스

- 카메라 토픽(/front_cam/compressed) 또는 로컬 웹캠(--camera 0) → YOLO/Swin 액션 분석
- ring buffer → 15초 영상 저장 → Spring API 전송
- cat_state → WebSocket/MQTT
- WebRTC 실시간 스트리밍 (동일 프레임 공유)

한 프로세스로 고양이 탐지 + WebRTC 스트리밍을 함께 수행합니다.
터미널 하나만 필요합니다.

실행 (프로젝트 루트에서):
  python scripts/cat_detection_webrtc.py --ckpt models/swin_tiny_best/best --yolo_pose models/yolo_pose.pt
  python scripts/cat_detection_webrtc.py --ckpt models/swin_tiny_best/best --yolo_pose models/yolo_pose.pt --camera 0 --show

환경 변수:
  BE_WS_URL=wss://...    WebSocket (cat_state + WebRTC 시그널링)
  ROBOT_ID=1             WebRTC Offer 시 robotId
  (기타 cat_detection과 동일)
"""

import os
import sys
import time
import json
import logging
import argparse
import threading
import asyncio
from pathlib import Path
from collections import deque
from typing import Optional, Tuple

import cv2
import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    import torch
    import timm
    from ultralytics import YOLO
except ImportError as e:
    print(f"[ERROR] pip install torch timm ultralytics: {e}")
    sys.exit(1)

try:
    import aiohttp
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from av import VideoFrame
except ImportError as e:
    print(f"[ERROR] pip install aiohttp aiortc av: {e}")
    sys.exit(1)

log = logging.getLogger(__name__)

from src.infer_cat import (
    build_model_from_ckpt,
    get_model_input_size,
    preprocess_bgr,
    pick_best_pose,
    ACTION_KO2EN,
    to_en,
)

# ----- 공유 프레임 (WebRTC 트랙에서 사용) -----
_webrtc_latest = None
_webrtc_lock = threading.Lock()

# ----- ROS2 카메라 구독 -----
_ros_latest_bgr = None
_ros_latest_lock = threading.Lock()
_ros_camera_node = None
_ros_executor = None

# ----- 로컬 웹캠 -----
_cap: Optional[cv2.VideoCapture] = None

# ----- MJPEG 스트림 -----
_mjpeg_latest = None
_mjpeg_lock = threading.Lock()
_mjpeg_server_thread = None


# ==================== MJPEG 서버 ====================
def _start_mjpeg_server(port: int = 8080):
    if os.getenv("SERVE_MJPEG", "1").strip().lower() not in ("1", "true", "yes"):
        return
    try:
        from flask import Flask, Response
    except ImportError:
        log.debug("flask 없음: MJPEG 서버 스킵")
        return
    global _mjpeg_server_thread
    port = int(os.getenv("STREAM_PORT", str(port)))
    app = Flask(__name__)
    BOUNDARY = "frame"

    def gen():
        while True:
            with _mjpeg_lock:
                jpeg = _mjpeg_latest
            if jpeg:
                yield (
                    f"--{BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode() + jpeg + b"\r\n"
            time.sleep(0.07)

    @app.route("/stream.mjpeg")
    def stream_mjpeg():
        return Response(
            gen(),
            mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            headers={"Cache-Control": "no-store, no-cache"},
        )

    def run():
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)

    _mjpeg_server_thread = threading.Thread(target=run, daemon=True)
    _mjpeg_server_thread.start()
    log.info("MJPEG 서버 시작: http://0.0.0.0:%s/stream.mjpeg", port)


def _update_mjpeg_frame(frame_bgr):
    global _mjpeg_latest
    if os.getenv("SERVE_MJPEG", "1").strip().lower() not in ("1", "true", "yes"):
        return
    try:
        _, jpeg = cv2.imencode(".jpg", frame_bgr)
        with _mjpeg_lock:
            _mjpeg_latest = jpeg.tobytes()
    except Exception as e:
        log.debug("MJPEG 프레임 저장 실패: %s", e)


# ==================== ROS2 카메라 구독 ====================
def _init_ros_camera_subscriber(topic: str):
    global _ros_latest_bgr, _ros_latest_lock, _ros_camera_node, _ros_executor
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        from sensor_msgs.msg import CompressedImage
    except ImportError:
        log.warning("ROS2 없음: 카메라 구독 스킵")
        return False
    try:
        if not rclpy.ok():
            rclpy.init()
        node = Node("cat_detection_webrtc_camera")
        with _ros_latest_lock:
            _ros_latest_bgr = None

        def on_compressed(msg):
            try:
                arr = np.frombuffer(msg.data, np.uint8)
                bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if bgr is not None:
                    with _ros_latest_lock:
                        global _ros_latest_bgr
                        _ros_latest_bgr = bgr
            except Exception as e:
                log.debug("ROS 카메라 디코드 실패: %s", e)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        node.create_subscription(CompressedImage, topic, on_compressed, qos)
        executor = rclpy.executors.SingleThreadedExecutor()
        executor.add_node(node)

        def spin_loop():
            try:
                while rclpy.ok():
                    executor.spin_once(timeout_sec=0.1)
            except Exception:
                pass

        th = threading.Thread(target=spin_loop, daemon=True)
        th.start()
        _ros_camera_node = node
        _ros_executor = executor
        log.info("ROS2 카메라 구독 시작: %s", topic)
        return True
    except Exception as e:
        log.warning("ROS 카메라 구독 초기화 실패: %s", e)
        return False


def _get_ros_frame(timeout_sec: float = 0.5):
    with _ros_latest_lock:
        if _ros_latest_bgr is not None:
            return _ros_latest_bgr.copy()
    return None


def _init_camera_device(camera_index: int) -> bool:
    global _cap
    try:
        _cap = cv2.VideoCapture(camera_index)
        if not _cap.isOpened():
            log.error("웹캠 열기 실패: device=%s", camera_index)
            return False
        log.info("로컬 웹캠 열림: device=%s (ROS 미사용)", camera_index)
        return True
    except Exception as e:
        log.error("웹캠 초기화 실패: %s", e)
        return False


def _get_camera_frame():
    global _cap
    if _cap is None or not _cap.isOpened():
        return None
    ret, frame = _cap.read()
    return frame if ret else None


# ==================== WebRTC ====================
class SharedFrameTrack(VideoStreamTrack):
    """공유 프레임(_webrtc_latest)을 읽어 WebRTC 비디오 트랙으로 전송"""

    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        with _webrtc_lock:
            frame = _webrtc_latest.copy() if _webrtc_latest is not None else None
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for camera", (50, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame


async def run_webrtc_loop():
    """WebRTC Offer/Answer 시그널링 루프 (백엔드 /ws STOMP)"""
    server_url = os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws")
    robot_id = os.getenv("ROBOT_ID", "1")

    while True:
        pc = None
        try:
            log.info("🔄 [WebRTC] 서버 연결 시도 중... %s", server_url)
            pc = RTCPeerConnection()
            pc.addTrack(SharedFrameTrack())

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(server_url, heartbeat=30.0) as ws:
                    log.info("✅ [WebRTC] 서버 연결 성공!")

                    connect_frame = "CONNECT\naccept-version:1.1,1.0\n\n\x00"
                    await ws.send_str(connect_frame)

                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    payload = json.dumps({
                        "sdp": pc.localDescription.sdp,
                        "type": pc.localDescription.type,
                        "robotId": robot_id
                    })
                    send_frame = f"SEND\ndestination:/pub/peer/offer\ncontent-type:application/json\n\n{payload}\x00"
                    sub_frame = "SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/answer\n\n\x00"
                    await ws.send_str(sub_frame)

                    answer_received = False
                    OFFER_INTERVAL = 5.0

                    async def send_offer_periodically():
                        while not answer_received:
                            await ws.send_str(send_frame)
                            log.info("📤 [WebRTC] Offer 재전송")
                            await asyncio.sleep(OFFER_INTERVAL)

                    await ws.send_str(send_frame)
                    log.info("📤 [WebRTC] Offer 전송 완료 (5초마다 재전송)")
                    offer_task = asyncio.create_task(send_offer_periodically())

                    try:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                if "MESSAGE" in msg.data and "destination:/sub/peer/answer" in msg.data:
                                    if answer_received:
                                        continue
                                    try:
                                        body = msg.data.split("\n\n")[-1].replace("\x00", "").strip()
                                        if not body:
                                            continue
                                        answer = json.loads(body)
                                        sdp = answer.get("sdp")
                                        type_ = answer.get("type")
                                        if not sdp or not type_:
                                            continue
                                        if pc.signalingState == "stable":
                                            continue
                                        desc = RTCSessionDescription(sdp=sdp, type=type_)
                                        await pc.setRemoteDescription(desc)
                                        answer_received = True
                                        offer_task.cancel()
                                        log.info("🎥 [WebRTC] P2P 연결 성공!")
                                    except Exception as e:
                                        log.debug("WebRTC Answer 처리 스킵: %s", e)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                    finally:
                        offer_task.cancel()
                        try:
                            await offer_task
                        except asyncio.CancelledError:
                            pass
        except Exception as e:
            log.error("❌ [WebRTC] 오류: %s", e, exc_info=True)
        finally:
            if pc:
                await pc.close()
            log.info("⏳ [WebRTC] 3초 후 재접속...")
            await asyncio.sleep(3)


def _start_webrtc_thread():
    """WebRTC 루프를 별도 스레드에서 실행"""
    def run():
        try:
            asyncio.run(run_webrtc_loop())
        except Exception as e:
            log.error("[WebRTC] 스레드 종료: %s", e)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    log.info("WebRTC 스트리밍 스레드 시작 (BE_WS_URL=%s)", os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws"))


# ==================== cat_state / 비디오 업로드 (cat_detection과 동일) ====================
def save_video_from_frames(frames: list, out_path: str, fps: float = 15) -> bool:
    if not frames:
        return False
    h, w = frames[0].shape[:2]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    if not writer.isOpened():
        return False
    for f in frames:
        writer.write(f)
    writer.release()
    return True


def create_thumbnail(frame, out_path: str, size=(320, 180)) -> bool:
    try:
        thumb = cv2.resize(frame, size)
        cv2.imwrite(out_path, thumb)
        return True
    except Exception:
        return False


class CatStateWsSender:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.connected = False
        self._ws = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        try:
            import websocket
        except ImportError:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        for _ in range(50):
            time.sleep(0.1)
            if self.connected:
                log.info("cat_state WebSocket 연결: %s", self.url)
                return True
        return False

    def _run(self):
        try:
            import websocket
        except ImportError:
            return
        def on_open(ws):
            ws.send("CONNECT\naccept-version:1.2\nheart-beat:10000,10000\n\n\x00", opcode=websocket.ABNF.OPCODE_TEXT)
        def on_message(ws, msg):
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8", errors="replace")
            if msg.startswith("CONNECTED"):
                self.connected = True
        def on_error(ws, err):
            log.debug("cat_state WS 에러: %s", err)
        def on_close(ws, *args):
            self.connected = False
        while True:
            try:
                self._ws = websocket.WebSocketApp(
                    self.url, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close
                )
                self._ws.run_forever()
            except Exception as e:
                log.debug("cat_state WS 예외: %s", e)
            log.info("cat_state WebSocket 재연결 시도 (5초 후)...")
            time.sleep(5)

    def send(self, payload: dict) -> bool:
        if not self.connected or not self._ws or not self._ws.sock or not self._ws.sock.connected:
            return False
        try:
            import websocket
            body = json.dumps(payload, ensure_ascii=False)
            frame = f"SEND\ndestination:/pub/robot/cat_state\ncontent-type:application/json\n\n{body}\x00"
            with self._lock:
                self._ws.send(frame, opcode=websocket.ABNF.OPCODE_TEXT)
            return True
        except Exception:
            return False


def post_video_to_backend(video_path, thumbnail_path, cat_name, behavior, duration, base_url, user_id):
    try:
        import requests
    except ImportError:
        return False
    base_url = base_url.rstrip("/")
    video_url = None
    thumb_url = None
    upload_url = os.getenv("BE_VIDEO_UPLOAD_URL", f"{base_url}/api/videos/upload")
    try:
        files = {"video": (os.path.basename(video_path), open(video_path, "rb"), "video/mp4")}
        handles = [files["video"][1]]
        if thumbnail_path and os.path.exists(thumbnail_path):
            files["thumbnail"] = (os.path.basename(thumbnail_path), open(thumbnail_path, "rb"), "image/jpeg")
            handles.append(files["thumbnail"][1])
        try:
            data = {"userId": user_id, "catName": cat_name, "behavior": behavior, "duration": duration}
            r = requests.post(upload_url, files=files, data=data, timeout=30)
        finally:
            for h in handles:
                h.close()
        if r.status_code in (200, 201):
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            video_url = body.get("url") or body.get("videoUrl")
        else:
            log.warning("[전송 실패] 영상 업로드: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("[전송 실패] 영상 업로드 예외: %s", e)
    if not video_url:
        clips_base = os.getenv("PI_GATEWAY_PUBLIC_URL", "http://localhost:8000").strip().rstrip("/")
        video_fn = os.path.basename(video_path)
        thumb_fn = os.path.basename(thumbnail_path) if thumbnail_path else ""
        video_url = f"{clips_base}/cat_clips/{video_fn}"
        thumb_url = f"{clips_base}/cat_clips/{thumb_fn}" if thumb_fn else ""
    payload = {"userId": user_id, "catName": cat_name, "behavior": behavior, "duration": duration, "url": video_url, "thumbnailUrl": thumb_url or ""}
    try:
        r = requests.post(f"{base_url}/api/videos", json=payload, timeout=10)
        if r.status_code in (200, 201):
            log.info("[전송 성공] 영상 정보 저장: %s", video_url)
            return True
        log.warning("[전송 실패] POST /api/videos: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("[전송 실패] POST /api/videos 예외: %s", e)
    return False


def post_cat_state_as_log(base_url: str, user_id: int, action_ko: str, action_en: str) -> bool:
    """cat_state를 백엔드 로그 API(POST /log)로 남깁니다. (나만 수정: pi_gateway만으로 로그 페이지 반영)"""
    if not base_url or not base_url.strip():
        return False
    url = f"{base_url.rstrip('/')}/api/log"
    payload = {
        "userId": user_id,
        "details": f"고양이 행동: {action_ko} ({action_en})",
    }
    try:
        r = requests.post(url, json=payload, timeout=2.0)
        if r.status_code in (200, 201):
            log.info("[전송 성공] cat_state → 로그 API (action=%s)", action_en)
            return True
        log.debug("[로그 API] %s %s", r.status_code, r.text[:100])
    except Exception as e:
        log.debug("[로그 API 예외] %s", e)
    return False


# ==================== Main ====================
def main():
    parser = argparse.ArgumentParser(description="고양이 탐지 + WebRTC 통합 서비스")
    parser.add_argument("--ckpt", type=str, required=True, help="Swin 체크포인트 경로")
    parser.add_argument("--yolo_pose", type=str, required=True, help="YOLO pose 모델 경로")
    parser.add_argument("--camera", type=int, default=-1,
                        help="로컬 웹캠 장치 번호 (0,1,...). 지정 시 ROS 미사용")
    parser.add_argument("--camera_topic", type=str, default=os.getenv("CAMERA_TOPIC", "/front_cam/compressed"))
    parser.add_argument("--K", type=int, default=8)
    parser.add_argument("--cls_hz", type=float, default=5.0)
    parser.add_argument("--record_sec", type=float, default=15.0)
    parser.add_argument("--capture_fps", type=float, default=15.0)
    parser.add_argument("--clips_dir", type=str, default=os.getenv("CLIPS_DIR", "./cat_clips"))
    parser.add_argument("--be_url", type=str, default=os.getenv("BE_SERVER_URL", ""))
    parser.add_argument("--be_ws_url", type=str, default=os.getenv("BE_WS_URL", ""))
    parser.add_argument("--user_id", type=int, default=int(os.getenv("BE_USER_ID", "1")))
    parser.add_argument("--mqtt_host", type=str, default=os.getenv("MQTT_HOST", ""))
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--show", action="store_true", help="미리보기 창 표시")
    args = parser.parse_args()

    def _valid_ckpt(p: str) -> bool:
        if os.path.isfile(p):
            return True
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "data.pkl")):
            return True
        return False
    if not _valid_ckpt(args.ckpt):
        print(f"[ERROR] Swin 체크포인트 없음: {args.ckpt}")
        sys.exit(1)
    if not _valid_ckpt(args.yolo_pose):
        print(f"[ERROR] YOLO pose 모델 없음: {args.yolo_pose}")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    log.info("device=%s", device)

    model, id2action, id2emo, backbone = build_model_from_ckpt(args.ckpt, device)
    img_size = get_model_input_size(backbone)
    yolo_pose_path = args.yolo_pose
    if os.path.isdir(args.yolo_pose) and os.path.isfile(os.path.join(args.yolo_pose, "data.pkl")):
        yolo_pose_path = os.path.join(args.yolo_pose, "data.pkl")
    yolo = YOLO(yolo_pose_path)

    use_ros = args.camera < 0
    if use_ros:
        if not _init_ros_camera_subscriber(args.camera_topic):
            log.error("ROS 카메라 구독 실패. 토픽 %s 발행 여부 확인", args.camera_topic)
            sys.exit(1)
    else:
        if not _init_camera_device(args.camera):
            sys.exit(1)

    w, h = 0, 0
    buf_size = int(args.record_sec * args.capture_fps)
    frame_buffer: deque = deque(maxlen=buf_size)
    cls_buf: deque = deque(maxlen=args.K)
    cls_every_n = max(1, int(round(args.capture_fps / max(args.cls_hz, 0.1))))

    last_action = "..."
    last_emotion = "-"
    cat_detected = False
    recording = False
    record_start_ts = 0.0
    last_save_ts = 0.0
    last_cat_state_nolog_ts = 0.0
    last_log_ts = 0.0
    log_throttle_sec = 30.0
    cooldown_sec = 30.0
    frame_idx = 0

    ws_sender = None
    if args.be_ws_url:
        ws_sender = CatStateWsSender(args.be_ws_url)
        ws_sender.start()

    _start_mjpeg_server(8080)
    _start_webrtc_thread()

    mqtt_client = None
    if args.mqtt_host:
        try:
            import paho.mqtt.client as mqtt
            mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            mqtt_client.connect(args.mqtt_host, mqtt_port, 60)
            mqtt_client.loop_start()
            log.info("MQTT 연결: %s:%s", args.mqtt_host, mqtt_port)
        except Exception as e:
            log.warning("MQTT 연결 실패: %s", e)

    user_id = args.user_id
    mqtt_topic = f"robot/{user_id}/cat_state"

    global _webrtc_latest
    try:
        while True:
            raw = _get_camera_frame() if not use_ros else _get_ros_frame()
            if raw is None:
                time.sleep(0.05)
                continue
            if w == 0 or h == 0:
                h, w = raw.shape[:2]
                log.info("카메라 첫 프레임: %sx%s", w, h)

            frame_idx += 1
            yres = yolo.predict(raw, verbose=False)
            picked = pick_best_pose(yres[0], only_best_one=True) if len(yres) > 0 else None
            cat_detected = picked is not None
            frame_buffer.append(raw.copy())

            with _webrtc_lock:
                _webrtc_latest = raw.copy()
            _update_mjpeg_frame(raw)

            if cat_detected:
                x = preprocess_bgr(raw, img_size)
                cls_buf.append(x)
                if len(cls_buf) == args.K and (frame_idx % cls_every_n == 0):
                    with torch.no_grad():
                        stack = torch.stack(list(cls_buf), dim=0).unsqueeze(0).to(device)
                        out_a, _out_e, _ = model(stack)
                        pa = int(out_a.argmax(1).item())
                        last_action = id2action.get(pa, str(pa))
            else:
                cls_buf.clear()

            action_en = to_en(last_action, ACTION_KO2EN, "ACT")
            now = time.time()
            if cat_detected and len(frame_buffer) >= buf_size:
                if not recording:
                    recording = True
                    record_start_ts = now
                if (now - record_start_ts) >= args.record_sec and (now - last_save_ts) >= cooldown_sec:
                    ts_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
                    out_path = Path(args.clips_dir) / f"cat_{ts_str}.mp4"
                    thumb_path = Path(args.clips_dir) / f"cat_{ts_str}_thumb.jpg"
                    frames = list(frame_buffer)
                    if save_video_from_frames(frames, str(out_path), args.capture_fps):
                        create_thumbnail(frames[-1], str(thumb_path))
                        log.info("영상 저장: %s (action=%s)", out_path, action_en)
                        last_save_ts = now
                        if args.be_url:
                            post_video_to_backend(
                                str(out_path), str(thumb_path),
                                cat_name=os.getenv("BE_CAT_NAME", "고양이"),
                                behavior=last_action,
                                duration="00:15",
                                base_url=args.be_url,
                                user_id=user_id,
                            )
                    recording = False
            else:
                recording = False

            cat_payload = {
                "userId": user_id,
                "timestamp": now,
                "detected": True,
                "action": action_en,
                "action_ko": last_action,
                "emotion": "N/A",
                "emotion_ko": "-",
            }
            if cat_detected:
                sent = False
                if ws_sender and ws_sender.send(cat_payload):
                    sent = True
                    log.info("[전송 성공] cat_state → WebSocket (action=%s)", action_en)
                if not sent and mqtt_client:
                    try:
                        mqtt_client.publish(mqtt_topic, json.dumps(cat_payload, ensure_ascii=False), qos=0)
                        sent = True
                        log.info("[전송 성공] cat_state → MQTT (action=%s)", action_en)
                    except Exception as e:
                        log.warning("[전송 실패] cat_state MQTT: %s", e)
                if not sent and args.be_url:
                    try:
                        import requests
                        r = requests.post(f"{args.be_url.rstrip('/')}/api/robot/cat_state", json=cat_payload, timeout=2.0)
                        if r.status_code in (200, 201):
                            sent = True
                            log.info("[전송 성공] cat_state → HTTP (action=%s)", action_en)
                        else:
                            log.warning("[전송 실패] cat_state HTTP: %s %s", r.status_code, r.text[:100])
                    except Exception as e:
                        log.warning("[전송 실패] cat_state HTTP: %s", e)
                if not sent and (now - last_cat_state_nolog_ts) >= 2.0:
                    last_cat_state_nolog_ts = now
                    log.info("[cat_state] 전송 수단 없음 action=%s", action_en)
                # 나만 수정: cat_state 전송 성공 시 백엔드 로그 API로도 남김 (쓰로틀 30초)
                if sent and args.be_url and (now - last_log_ts) >= log_throttle_sec:
                    if post_cat_state_as_log(args.be_url, user_id, last_action, action_en):
                        last_log_ts = now

            if args.show:
                vis = raw.copy()
                cv2.putText(vis, f"Action: {action_en}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(vis, "CAT!" if cat_detected else "---", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow("cat_detection_webrtc", vis)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        log.info("종료")
    finally:
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            except Exception:
                pass
        if _cap is not None:
            _cap.release()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
