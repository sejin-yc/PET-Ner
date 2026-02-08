#!/usr/bin/env python3
"""
ROS2 /front_cam/compressed 구독 → (YOLO로 고양이 감지 + Swin으로 행동 분류) →
(1) cat_state STOMP 전송 (/pub/robot/cat_state)
(2) 고양이 감지 시 15초 영상 저장 → tmp_avi(MJPG) → ffmpeg(H.264 mp4) 변환 →
    영상 저장 완료 STOMP 알림 (/pub/robot/notification)

중요 포인트
- 카메라 직접 열지 않음(VideoCapture/GStreamer 불필요)
- QoS BEST_EFFORT로 구독(퍼블리셔가 BEST_EFFORT인 경우 호환)
- GUI 없는 환경이면 --show 줘도 자동으로 imshow 비활성화
- mp4 재생 호환성:
  - libx264가 없는 환경이 많아서, h264_v4l2m2m → libopenh264 → mpeg4 순으로 시도
  - yuv420p + faststart + 짝수 해상도(scale 필터) 적용

실행 예시:
  source /opt/ros/humble/setup.bash
  export BE_WS_URL=wss://i14c203.p.ssafy.io/ws
  export PI_GATEWAY_PUBLIC_URL=https://i14c203.p.ssafy.io
  export BE_USER_ID=1
  export VIDEO_SAVE_DIR=/home/ssafy/videos
  python3 scripts/cat_detection_webrtc.py \
    --ckpt models/swin_tiny_best.pt \
    --yolo-pose models/yolo_pose.pt \
    --record-sec 15 --prebuffer 3 --fps 15

테스트(강제 녹화):
  python3 scripts/cat_detection_webrtc.py ... --test-trigger

환경 변수:
  BE_WS_URL=wss://.../ws
  PI_GATEWAY_PUBLIC_URL=https://...
  VIDEO_SAVE_DIR=/home/ssafy/videos
  CAMERA_TOPIC=/front_cam/compressed
  BE_USER_ID=1
"""

import os
import sys
import time
import json
import asyncio
import argparse
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import aiohttp

# --- ROS2 ---
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage

# --- 프로젝트 루트 경로 ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# --- 실제 모델 유틸(팀 코드) ---
from src.infer_cat import (
    build_model_from_ckpt,
    get_model_input_size,
    preprocess_bgr,
    pick_best_pose,
    ACTION_KO2EN,
    to_en,
)

try:
    import torch
    from ultralytics import YOLO
except Exception as e:
    print("[FATAL] torch / ultralytics 필요:", e)
    print("  pip install torch ultralytics")
    raise

# -----------------------------------------------------------------------------
# 로깅
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("CatWebRTCROS")

# -----------------------------------------------------------------------------
# 저장 경로
# -----------------------------------------------------------------------------
VIDEO_SAVE_DIR = os.getenv("VIDEO_SAVE_DIR", "/home/ssafy/videos")
os.makedirs(VIDEO_SAVE_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# GUI 가능 여부 (imshow 크래시 방지)
# -----------------------------------------------------------------------------
def _gui_available() -> bool:
    if os.getenv("DISPLAY"):
        return True
    return False

# -----------------------------------------------------------------------------
# ffmpeg 변환 (avi -> mp4)  ✅ 여기 수정됨 (libx264 없는 환경 대응)
# -----------------------------------------------------------------------------
async def convert_avi_to_mp4_async(tmp_avi: str, out_mp4: str) -> bool:
    """
    MJPG AVI를 MP4로 변환.
    사용 가능한 인코더를 순서대로 시도:
      1) h264_v4l2m2m
      2) libopenh264
      3) mpeg4 (fallback)

    + H.264는 짝수 해상도 요구가 많아 scale 필터 적용
    + 실패 시 stderr 일부 출력
    """
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    candidates = [
        ("h264_v4l2m2m", [
            "ffmpeg", "-y", "-hide_banner",
            "-i", tmp_avi,
            "-vf", vf,
            "-c:v", "h264_v4l2m2m",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            out_mp4,
        ]),
        ("libopenh264", [
            "ffmpeg", "-y", "-hide_banner",
            "-i", tmp_avi,
            "-vf", vf,
            "-c:v", "libopenh264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            out_mp4,
        ]),
        ("mpeg4", [
            "ffmpeg", "-y", "-hide_banner",
            "-i", tmp_avi,
            "-vf", vf,
            "-c:v", "mpeg4",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            out_mp4,
        ]),
    ]

    try:
        for enc_name, cmd in candidates:
            # 이전 시도 결과 삭제
            try:
                if os.path.exists(out_mp4):
                    os.remove(out_mp4)
            except Exception:
                pass

            log.info("🔄 ffmpeg 변환 시도 encoder=%s: %s -> %s", enc_name, tmp_avi, out_mp4)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _out, err = await proc.communicate()
            rc = proc.returncode

            if rc == 0 and os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 0:
                # 성공 시 원본 삭제
                try:
                    os.remove(tmp_avi)
                except Exception:
                    pass
                log.info("✅ 변환 완료: %s (encoder=%s)", out_mp4, enc_name)
                return True

            log.error("❌ ffmpeg 실패 encoder=%s rc=%s", enc_name, rc)
            if err:
                log.error(err.decode("utf-8", errors="replace")[-2000:])

        return False

    except FileNotFoundError:
        log.error("❌ ffmpeg 없음: sudo apt install -y ffmpeg")
        return False
    except Exception as e:
        log.error("❌ ffmpeg 예외: %s", e, exc_info=True)
        return False

# -----------------------------------------------------------------------------
# STOMP helper
# -----------------------------------------------------------------------------
def _stomp_connect_frame() -> str:
    return "CONNECT\naccept-version:1.1,1.0\nheart-beat:10000,10000\n\n\x00"

def _stomp_send_frame(dest: str, body_json: dict) -> str:
    body = json.dumps(body_json, ensure_ascii=False)
    return (
        "SEND\n"
        f"destination:{dest}\n"
        "content-type:application/json\n\n"
        f"{body}\x00"
    )

async def stomp_send_once(ws_url: str, dest: str, payload: dict) -> bool:
    """
    단발성 STOMP SEND (연결→CONNECT→SEND→close)
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url, ssl=False) as ws:
                await ws.send_str(_stomp_connect_frame())
                await ws.send_str(_stomp_send_frame(dest, payload))
        return True
    except Exception as e:
        log.debug("STOMP send fail (%s): %s", dest, e)
        return False

# -----------------------------------------------------------------------------
# ROS2 Subscriber: 최신 프레임 저장
# -----------------------------------------------------------------------------
class FrontCamSubscriber(Node):
    def __init__(self, topic: str):
        super().__init__("front_cam_subscriber")

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_stamp: float = 0.0
        self.frame_count = 0

        self.sub = self.create_subscription(
            CompressedImage,
            topic,
            self._cb,
            qos
        )
        self.get_logger().info(f"✅ subscribe(BEST_EFFORT): {topic}")

    def _cb(self, msg: CompressedImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return
            self.latest_frame = frame
            self.latest_stamp = time.time()
            self.frame_count += 1
            if self.frame_count % 30 == 0:
                self.get_logger().info(f"frame rx: {frame.shape}")
        except Exception as e:
            self.get_logger().debug(f"decode fail: {e}")

# -----------------------------------------------------------------------------
# 메인 서비스
# -----------------------------------------------------------------------------
class CatDetectionWebRTCROSService:
    def __init__(self, args):
        self.args = args
        self.running = True

        # ROS 노드
        self.node = FrontCamSubscriber(args.topic)

        # 녹화/버퍼
        self.fps = float(args.fps)
        self.prebuffer_sec = float(args.prebuffer)
        self.record_sec = float(args.record_sec)

        self.prebuf_len = max(1, int(self.fps * self.prebuffer_sec))
        self.frame_buffer = deque(maxlen=self.prebuf_len)

        self.recording = False
        self.out: Optional[cv2.VideoWriter] = None
        self.record_start_ts = 0.0
        self.current_tmp_avi = ""
        self.current_mp4 = ""
        self.detected_behavior_ko = "..."

        # 모델
        self.device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
        log.info("device=%s", self.device)

        self.model, self.id2action, _id2emo, backbone = build_model_from_ckpt(args.ckpt, self.device)
        self.img_size = get_model_input_size(backbone)

        yolo_pose_path = args.yolo_pose
        if os.path.isdir(yolo_pose_path) and os.path.isfile(os.path.join(yolo_pose_path, "data.pkl")):
            yolo_pose_path = os.path.join(yolo_pose_path, "data.pkl")
        self.yolo = YOLO(yolo_pose_path)

        # 분류 버퍼/주기
        self.cls_buf = deque(maxlen=args.K)
        self.frame_idx = 0
        self.cls_every_n = max(1, int(round(self.fps / max(args.cls_hz, 0.1))))
        self.last_action_ko = "..."

        # STOMP
        self.ws_url = args.be_ws_url or os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws")
        self.user_id = int(args.user_id)
        self.public_base = (args.public_base or os.getenv("PI_GATEWAY_PUBLIC_URL", "https://i14c203.p.ssafy.io")).rstrip("/")

        # show
        self.show = bool(args.show) and _gui_available()
        if args.show and not self.show:
            log.warning("⚠️ --show 요청했지만 GUI 불가(DISPLAY/GTK 없음). show 비활성화합니다.")

    def detect_cat_and_action(self, frame: np.ndarray) -> tuple[bool, str]:
        """
        YOLO로 고양이 감지 + Swin으로 행동 분류(ko) 반환
        """
        self.frame_idx += 1

        # 1) YOLO cat detect
        try:
            yres = self.yolo.predict(frame, verbose=False)
            picked = pick_best_pose(yres[0], only_best_one=True) if len(yres) > 0 else None
            cat_detected = picked is not None
        except Exception as e:
            log.debug("YOLO fail: %s", e)
            cat_detected = False

        if not cat_detected:
            self.cls_buf.clear()
            return False, self.last_action_ko

        # 2) Swin input buffer
        try:
            x = preprocess_bgr(frame, self.img_size)
            self.cls_buf.append(x)
        except Exception as e:
            log.debug("preprocess fail: %s", e)
            return True, self.last_action_ko

        # 3) classify periodically
        if len(self.cls_buf) == self.args.K and (self.frame_idx % self.cls_every_n == 0):
            try:
                with torch.no_grad():
                    stack = torch.stack(list(self.cls_buf), dim=0).unsqueeze(0).to(self.device)
                    out_a, _out_e, _ = self.model(stack)
                    pa = int(out_a.argmax(1).item())
                    self.last_action_ko = self.id2action.get(pa, str(pa))
            except Exception as e:
                log.debug("swin infer fail: %s", e)

        return True, self.last_action_ko

    def start_recording(self, frame_shape, action_ko: str):
        """
        tmp_avi로 녹화 시작 (MJPG)
        - prebuffer(최근 몇 초) 먼저 넣고 시작
        """
        h, w = frame_shape[:2]
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.current_tmp_avi = os.path.join(VIDEO_SAVE_DIR, f"temp_{ts}.avi")
        self.current_mp4 = os.path.join(VIDEO_SAVE_DIR, f"cat_{ts}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self.out = cv2.VideoWriter(self.current_tmp_avi, fourcc, self.fps, (w, h))
        if not self.out.isOpened():
            log.error("❌ VideoWriter open fail: %s", self.current_tmp_avi)
            self.out = None
            self.recording = False
            return

        # prebuffer frames
        for bf in self.frame_buffer:
            self.out.write(bf)

        self.recording = True
        self.record_start_ts = time.time()
        self.detected_behavior_ko = action_ko
        log.info("⏺️ 녹화 시작: %s (behavior=%s)", self.current_tmp_avi, action_ko)

    async def stop_recording(self):
        """
        녹화 종료 → ffmpeg 변환 → notification 전송
        """
        self.recording = False
        if self.out:
            try:
                self.out.release()
            except Exception:
                pass
            self.out = None

        duration = int(time.time() - self.record_start_ts)
        log.info("⏹️ 녹화 종료(길이 %ss). mp4 변환...", duration)

        ok = await convert_avi_to_mp4_async(self.current_tmp_avi, self.current_mp4)
        if not ok:
            return

        filename = os.path.basename(self.current_mp4)
        url = f"{self.public_base}/videos/{filename}"

        payload = {
            "type": "VIDEO_SAVED",
            "fileName": filename,
            "url": url,
            "behavior": self.detected_behavior_ko,
            "duration": f"00:{duration:02d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "userId": self.user_id,
        }

        sent = await stomp_send_once(self.ws_url, "/pub/robot/notification", payload)
        if sent:
            log.info("🔔 알림 전송 완료: %s", filename)
        else:
            log.warning("⚠️ 알림 전송 실패(WS): %s", filename)

    async def send_cat_state(self, action_ko: str):
        """
        cat_state 전송 (STOMP)
        """
        now = time.time()
        action_en = to_en(action_ko, ACTION_KO2EN, "ACT")
        payload = {
            "userId": self.user_id,
            "timestamp": now,
            "detected": True,
            "action": action_en,
            "action_ko": action_ko,
            "emotion": "N/A",
            "emotion_ko": "-",
        }
        ok = await stomp_send_once(self.ws_url, "/pub/robot/cat_state", payload)
        if ok:
            log.info("[전송 성공] cat_state → STOMP (action=%s)", action_en)
        else:
            log.warning("[전송 실패] cat_state → STOMP (action=%s)", action_en)

    async def run(self):
        log.info("🚀 ROS2 구독 기반 감지 서비스 시작")
        last_stamp = 0.0
        last_test_sec = -1

        while self.running:
            rclpy.spin_once(self.node, timeout_sec=0.0)

            frame = self.node.latest_frame
            stamp = self.node.latest_stamp

            if frame is None or stamp == last_stamp:
                await asyncio.sleep(0.01)
                continue

            last_stamp = stamp

            # resize 옵션
            if self.args.resize_w > 0 and self.args.resize_h > 0:
                try:
                    frame = cv2.resize(frame, (self.args.resize_w, self.args.resize_h))
                except Exception:
                    pass

            # prebuffer 업데이트
            self.frame_buffer.append(frame)

            # 감지 + 분류
            is_cat, action_ko = self.detect_cat_and_action(frame)

            # test trigger: 10초마다 강제 is_cat=True
            if self.args.test_trigger:
                now_sec = int(time.time())
                if now_sec % 10 == 0 and now_sec != last_test_sec:
                    last_test_sec = now_sec
                    is_cat, action_ko = True, "test"

            # cat_state throttle
            if is_cat:
                if (time.time() - getattr(self, "_last_state_ts", 0.0)) >= self.args.state_interval:
                    self._last_state_ts = time.time()
                    await self.send_cat_state(action_ko)

            # 녹화 로직
            now = time.time()
            if is_cat and not self.recording:
                self.start_recording(frame.shape, action_ko)

            if self.recording and self.out is not None:
                self.out.write(frame)
                if (now - self.record_start_ts) >= self.record_sec:
                    await self.stop_recording()

            # debug show (GUI 있을 때만)
            if self.show:
                disp = frame.copy()
                if self.recording:
                    cv2.circle(disp, (30, 30), 10, (0, 0, 255), -1)
                    cv2.putText(disp, "REC", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(disp, f"act_ko: {action_ko}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.imshow("FrontCam (ROS)", disp)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    self.running = False

            await asyncio.sleep(0.001)

        self.cleanup()

    def cleanup(self):
        try:
            if self.out:
                self.out.release()
        except Exception:
            pass
        try:
            if self.show:
                cv2.destroyAllWindows()
        except Exception:
            pass
        try:
            self.node.destroy_node()
        except Exception:
            pass
        log.info("👋 종료")

# -----------------------------------------------------------------------------
# argparse
# -----------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser()

    p.add_argument("--topic", default=os.getenv("CAMERA_TOPIC", "/front_cam/compressed"))
    p.add_argument("--show", action="store_true", help="(GUI 필요) show window")
    p.add_argument("--test-trigger", action="store_true", help="force trigger every 10s")

    # record
    p.add_argument("--fps", type=float, default=15.0, help="record fps")
    p.add_argument("--prebuffer", type=float, default=3.0, help="prebuffer seconds")
    p.add_argument("--record-sec", dest="record_sec", type=float, default=15.0, help="record duration seconds")

    # resize
    p.add_argument("--resize-w", dest="resize_w", type=int, default=320)
    p.add_argument("--resize-h", dest="resize_h", type=int, default=240)

    # model
    p.add_argument("--ckpt", required=True, help="Swin ckpt path")
    p.add_argument("--yolo-pose", dest="yolo_pose", required=True, help="YOLO pose model path")
    p.add_argument("--K", type=int, default=8)
    p.add_argument("--cls-hz", dest="cls_hz", type=float, default=5.0)
    p.add_argument("--cpu", action="store_true")

    # backend
    p.add_argument("--be-ws-url", dest="be_ws_url", default=os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws"))
    p.add_argument("--user-id", dest="user_id", default=os.getenv("BE_USER_ID", "1"))
    p.add_argument("--public-base", dest="public_base", default=os.getenv("PI_GATEWAY_PUBLIC_URL", "https://i14c203.p.ssafy.io"))

    # cat_state throttle
    p.add_argument("--state-interval", dest="state_interval", type=float, default=1.0,
                   help="seconds between cat_state sends (default 1s)")
    return p

def main():
    args = build_parser().parse_args()

    rclpy.init()
    service = CatDetectionWebRTCROSService(args)

    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            rclpy.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
