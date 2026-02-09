#!/usr/bin/env python3
"""
젯슨 전용 WebRTC 카메라 스트리밍: 카메라 직접 캡처 → 백엔드 서버
ROS 없이 cv2.VideoCapture로 카메라를 캡처하여 WebRTC로 백엔드에 스트리밍합니다.

젯슨에서 cat_detection_service.py와 함께 실행:
  - cat_detection_service.py: 고양이 탐지 + cat_state 전송 (SERVE_MJPEG=0)
  - jetson_webrtc.py: WebRTC 스트리밍

환경 변수:
  BE_WS_URL       시그널링 서버 (기본: wss://i14c203.p.ssafy.io/ws)
  ROBOT_ID        로봇 ID (기본: 1)
  CAMERA_DEVICE   카메라 장치 번호 (기본: 0)
  GSTREAMER_PIPELINE  GStreamer 파이프라인 (CSI 카메라용, 있으면 VideoCapture에 사용)
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time

import cv2
import numpy as np
import aiohttp

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

# 설정 (환경 변수로 오버라이드)
SERVER_URL = os.getenv("BE_WS_URL", "wss://i14c203.p.ssafy.io/ws")
ROBOT_ID = os.getenv("ROBOT_ID", "1")
CAMERA_DEVICE = int(os.getenv("CAMERA_DEVICE", "0"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# 카메라 캡처
_cap = None
_latest_frame = None
_frame_lock = threading.Lock()
_capture_thread = None
_capture_running = False


def _init_camera():
    """카메라 초기화. GStreamer 파이프라인 또는 V4L2 지원."""
    global _cap
    gst = os.getenv("GSTREAMER_PIPELINE", "").strip()
    if gst:
        log.info("GStreamer 파이프라인 사용: %s", gst[:80] + "..." if len(gst) > 80 else gst)
        _cap = cv2.VideoCapture(gst, cv2.CAP_GSTREAMER)
    else:
        _cap = cv2.VideoCapture(CAMERA_DEVICE)
    if not _cap or not _cap.isOpened():
        log.error("카메라 열기 실패: device=%s", CAMERA_DEVICE)
        return False
    log.info("카메라 열림: device=%s", CAMERA_DEVICE)
    return True


def _capture_loop():
    """별도 스레드에서 카메라 캡처."""
    global _latest_frame, _capture_running
    while _capture_running and _cap and _cap.isOpened():
        ok, frame = _cap.read()
        if ok and frame is not None:
            with _frame_lock:
                _latest_frame = frame.copy()
        else:
            time.sleep(0.01)
    log.debug("캡처 루프 종료")


def _get_latest_frame():
    """최신 프레임 반환 (스레드 안전)."""
    with _frame_lock:
        return _latest_frame.copy() if _latest_frame is not None else None


class CameraStreamTrack(VideoStreamTrack):
    """카메라 프레임을 WebRTC VideoStreamTrack으로 제공."""

    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = _get_latest_frame()

        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame, "Waiting for Camera", (50, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
            )
            cv2.putText(
                frame, f"Device: {CAMERA_DEVICE}", (50, 300),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1
            )

        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame


async def run_webrtc():
    """WebRTC 연결 및 스트리밍 루프."""
    while True:
        pc = None
        try:
            ws_url = SERVER_URL
            log.info("🔄 [Jetson] 서버 연결 시도 중... %s", ws_url)

            pc = RTCPeerConnection()
            pc.addTrack(CameraStreamTrack())

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, heartbeat=30.0) as ws:
                    log.info("✅ [Jetson] 서버 연결 성공!")

                    connect_frame = "CONNECT\naccept-version:1.1,1.0\n\n\x00"
                    await ws.send_str(connect_frame)

                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)

                    payload = json.dumps({
                        "sdp": pc.localDescription.sdp,
                        "type": pc.localDescription.type,
                        "robotId": ROBOT_ID,
                    })
                    send_frame = f"SEND\ndestination:/pub/peer/offer\ncontent-type:application/json\n\n{payload}\x00"
                    await ws.send_str(send_frame)
                    log.info("📤 [Jetson] Offer 전송 완료")

                    sub_frame = "SUBSCRIBE\nid:sub-0\ndestination:/sub/peer/answer\n\n\x00"
                    await ws.send_str(sub_frame)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            if "MESSAGE" in msg.data and "destination:/sub/peer/answer" in msg.data:
                                try:
                                    body = msg.data.split("\n\n")[-1].replace("\x00", "")
                                    answer = json.loads(body)
                                    desc = RTCSessionDescription(
                                        sdp=answer["sdp"], type=answer["type"]
                                    )
                                    await pc.setRemoteDescription(desc)
                                    log.info("🎥 [Jetson] P2P 연결 성공!")
                                except Exception as e:
                                    log.error("❌ WebRTC 핸드쉐이크 에러: %s", e)

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            log.error("❌ 실행 중 오류: %s", e, exc_info=True)
        finally:
            if pc:
                await pc.close()
            log.info("⏳ 3초 후 재접속합니다...")
            await asyncio.sleep(3)


def main():
    global _cap, _capture_thread, _capture_running

    log.info("젯슨 WebRTC 카메라 스트리밍 시작")
    log.info("  SERVER_URL: %s", SERVER_URL)
    log.info("  ROBOT_ID: %s", ROBOT_ID)
    log.info("  CAMERA_DEVICE: %s", CAMERA_DEVICE)

    if not _init_camera():
        sys.exit(1)

    _capture_running = True
    _capture_thread = threading.Thread(target=_capture_loop, daemon=True)
    _capture_thread.start()

    try:
        asyncio.run(run_webrtc())
    except KeyboardInterrupt:
        log.info("종료 중...")
    finally:
        _capture_running = False
        if _capture_thread:
            _capture_thread.join(timeout=2.0)
        if _cap:
            _cap.release()
            log.info("카메라 해제")


if __name__ == "__main__":
    main()
