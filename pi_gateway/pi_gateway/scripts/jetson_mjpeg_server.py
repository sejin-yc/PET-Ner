#!/usr/bin/env python3
"""
젯슨에서 실행: 카메라 → MJPEG HTTP 스트림 (웹으로 직접 전송).
Pi 거치지 않고 웹에서 http://JETSON_IP:포트/stream.mjpeg 로 접속.

실행 (젯슨):
  pip install flask opencv-python  # 필요시
  python3 scripts/jetson_mjpeg_server.py

환경 변수:
  CAMERA_ID=0           카메라 디바이스 (기본 0)
  CAMERA_WIDTH=640      해상도 가로
  CAMERA_HEIGHT=480     해상도 세로
  CAMERA_FPS=15         목표 fps
  STREAM_PORT=8080      MJPEG 서버 포트 (기본 8080)

웹: <img src="http://192.168.100.253:8080/stream.mjpeg">
"""

import os
import sys
import time
import threading

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import cv2
except ImportError:
    print("[ERROR] opencv-python 필요: pip install opencv-python")
    sys.exit(1)

try:
    from flask import Flask, Response
except ImportError:
    print("[ERROR] flask 필요: pip install flask")
    sys.exit(1)

BOUNDARY = "frame"
_latest_jpeg = None
_latest_jpeg_lock = threading.Lock()


def generate_mjpeg():
    """MJPEG 스트림 생성기."""
    global _latest_jpeg
    while True:
        with _latest_jpeg_lock:
            jpeg = _latest_jpeg
        if jpeg:
            yield (
                f"--{BOUNDARY}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg)}\r\n\r\n"
            ).encode() + jpeg + b"\r\n"
        time.sleep(0.07)  # ~15fps


def main():
    camera_id = int(os.getenv("CAMERA_ID", "0"))
    width = int(os.getenv("CAMERA_WIDTH", "640"))
    height = int(os.getenv("CAMERA_HEIGHT", "480"))
    target_fps = float(os.getenv("CAMERA_FPS", "15"))
    port = int(os.getenv("STREAM_PORT", "8080"))
    period = 1.0 / max(1.0, target_fps)

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[ERROR] 카메라 열기 실패: device={camera_id}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, target_fps)

    def capture_loop():
        global _latest_jpeg
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            _, jpeg = cv2.imencode(".jpg", frame)
            with _latest_jpeg_lock:
                _latest_jpeg = jpeg.tobytes()
            time.sleep(period)

    th = threading.Thread(target=capture_loop, daemon=True)
    th.start()

    app = Flask(__name__)

    @app.route("/stream.mjpeg")
    def stream_mjpeg():
        return Response(
            generate_mjpeg(),
            mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            headers={"Cache-Control": "no-store, no-cache"},
        )

    @app.route("/")
    def index():
        return """<!DOCTYPE html>
<html><head><title>Jetson MJPEG</title></head>
<body><h1>Jetson Live Stream</h1>
<img src="/stream.mjpeg" alt="Live" style="max-width:100%;" />
</body></html>"""

    print(f"[jetson_mjpeg_server] http://0.0.0.0:{port}/stream.mjpeg")
    print(f"[jetson_mjpeg_server] 웹: img src=\"http://192.168.100.253:{port}/stream.mjpeg\"")

    try:
        app.run(host="0.0.0.0", port=port, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


if __name__ == "__main__":
    main()
