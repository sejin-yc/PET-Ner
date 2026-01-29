import argparse
from pathlib import Path
import time
import threading

import cv2
import numpy as np
import torch
import timm
from PIL import Image
from torchvision import transforms
from ultralytics import YOLO
import yaml
from flask import Flask, Response

# ROS2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as RosImage
from cv_bridge import CvBridge


# =========================
# Regression model
# =========================
class RegrModel(torch.nn.Module):
    def __init__(self, backbone: str):
        super().__init__()
        self.net = timm.create_model(backbone, pretrained=False, num_classes=1)

    def forward(self, x):
        return self.net(x)


def safe_load_ckpt(path: Path, device: str):
    try:
        return torch.load(path, map_location=device, weights_only=True)
    except TypeError:
        return torch.load(path, map_location=device)


def load_regression(ckpt_path: Path, device: str):
    ckpt = safe_load_ckpt(ckpt_path, device)
    backbone = ckpt["backbone"]
    img_size = int(ckpt["img_size"])

    model = RegrModel(backbone).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
    ])
    return model, tf, backbone, img_size


@torch.no_grad()
def predict_grams(model, tf, roi_bgr, device: str, amp: bool) -> float:
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    x = tf(Image.fromarray(rgb)).unsqueeze(0).to(device)

    if amp and device.startswith("cuda"):
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            g = float(model(x).item())
    else:
        g = float(model(x).item())
    return g


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def load_full_grams(config_path: Path) -> float:
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    full_grams = float(cfg.get("full_grams", 0.0))
    if full_grams <= 0:
        raise ValueError("full_grams must be > 0 in config.yaml")
    return full_grams


# =========================
# YOLO seg helpers
# =========================
def mask_to_bbox_xyxy(mask01: np.ndarray):
    ys, xs = np.where(mask01 > 0)
    if len(xs) == 0 or len(ys) == 0:
        return None
    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())
    return (x1, y1, x2, y2)


def expand_bbox(x1, y1, x2, y2, W, H, margin=0.12):
    bw = x2 - x1 + 1
    bh = y2 - y1 + 1
    mx = int(bw * margin)
    my = int(bh * margin)
    x1 = max(0, x1 - mx)
    y1 = max(0, y1 - my)
    x2 = min(W - 1, x2 + mx)
    y2 = min(H - 1, y2 + my)
    return x1, y1, x2, y2


def choose_best_instance_by_mask_area(result, conf_thres=0.25, min_mask_area_ratio=0.02):
    boxes = result.boxes
    masks = result.masks

    if boxes is None or len(boxes) == 0:
        return None, "no_box"

    if masks is None or masks.data is None or len(masks.data) == 0:
        conf = boxes.conf.detach().cpu().numpy()
        idx = int(np.argmax(conf))
        if float(conf[idx]) < conf_thres:
            return None, "low_conf_no_mask"
        return idx, "best_conf_no_mask"

    conf = boxes.conf.detach().cpu().numpy()
    H, W = result.orig_shape[:2]
    frame_area = float(H * W)

    best_idx, best_score = None, -1.0
    for i in range(len(boxes)):
        c = float(conf[i])
        if c < conf_thres:
            continue
        m = masks.data[i].detach().cpu().numpy()
        mask01 = (m > 0.5).astype(np.uint8)
        area_ratio = float(mask01.sum()) / frame_area
        if area_ratio < min_mask_area_ratio:
            continue
        score = area_ratio + 0.001 * c
        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx is None:
        return None, "filtered_all"
    return int(best_idx), "best_mask_area"


def get_roi_from_seg_result(result, frame_bgr, idx, margin=0.12):
    H, W = frame_bgr.shape[:2]

    if result.masks is not None and result.masks.data is not None and idx is not None:
        m = result.masks.data[idx].detach().cpu().numpy()
        mask01 = (m > 0.5).astype(np.uint8)
        bbox = mask_to_bbox_xyxy(mask01)
        if bbox is None:
            return None, None
        x1, y1, x2, y2 = bbox
        x1, y1, x2, y2 = expand_bbox(x1, y1, x2, y2, W, H, margin=margin)
        roi = frame_bgr[y1:y2 + 1, x1:x2 + 1].copy()
        return roi, (x1, y1, x2, y2)

    b = result.boxes.xyxy[idx].detach().cpu().numpy().astype(int)
    x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
    x1, y1, x2, y2 = expand_bbox(x1, y1, x2, y2, W, H, margin=margin)
    roi = frame_bgr[y1:y2 + 1, x1:x2 + 1].copy()
    return roi, (x1, y1, x2, y2)


# =========================
# ROS subscriber -> latest frame (BGR)
# =========================
class ImageSub(Node):
    def __init__(self, topic: str):
        super().__init__("feed_ai_image_sub")
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.latest_bgr = None
        self.last_ts = 0.0

        self.create_subscription(RosImage, topic, self.cb, 10)
        self.get_logger().info(f"Subscribed to {topic}")

    def cb(self, msg: RosImage):
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"cv_bridge convert failed: {e}")
            return
        with self.lock:
            self.latest_bgr = bgr
            self.last_ts = time.time()

    def get_latest(self):
        with self.lock:
            if self.latest_bgr is None:
                return None, 0.0
            return self.latest_bgr.copy(), self.last_ts


# =========================
# Flask MJPEG streaming
# =========================
app = Flask(__name__)
LATEST_JPEG = None
JPEG_LOCK = threading.Lock()

def encode_jpeg(bgr):
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return buf.tobytes() if ok else None

@app.get("/")
def index():
    return "OK. Open /video"

@app.get("/video")
def video():
    def gen():
        while True:
            with JPEG_LOCK:
                frame = LATEST_JPEG
            if frame is None:
                time.sleep(0.01)
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.001)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# =========================
# Inference loop (reads ROS latest frame)
# =========================
def infer_loop(args, sub: ImageSub):
    global LATEST_JPEG

    full_grams = load_full_grams(Path(args.config))
    yolo = YOLO(str(args.yolo_seg))
    reg_model, reg_tf, backbone, reg_imgsz = load_regression(Path(args.reg_ckpt), args.device)

    print("device     :", args.device, "| amp:", args.amp)
    print("yolo_seg   :", args.yolo_seg)
    print("reg_ckpt   :", args.reg_ckpt, "| backbone:", backbone, "| reg_imgsz:", reg_imgsz)
    print("full_grams :", full_grams)

    fps_ema = None

    infer_period = 1.0 / max(args.infer_fps, 0.1)
    next_infer_t = 0.0

    last_overlay = None  # 마지막 추론 결과 vis(그대로 쓰거나 overlay용)

    while True:
        frame, ts = sub.get_latest()

        now = time.time()

        # 추론 주기 안 됐으면: 마지막 결과를 재송출(또는 원본 송출)
        if now < next_infer_t:
            # 1) 마지막 vis가 있으면 그걸 내보내고
            if last_overlay is not None:
                vis = last_overlay
            else:
                vis = frame  # 초기엔 원본

            jpg = encode_jpeg(vis)
            if jpg is not None:
                with JPEG_LOCK:
                    LATEST_JPEG = jpg
            time.sleep(0.001)
            continue

        # 추론 타이밍 갱신
        next_infer_t = now + infer_period

        if frame is None:
            time.sleep(0.01)
            continue

        # 프레임이 너무 오래된 경우(토픽 끊김) 표시
        stale = (time.time() - ts) > 1.0

        t0 = time.time()
        r = yolo.predict(source=frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
        idx, reason = choose_best_instance_by_mask_area(
            r, conf_thres=args.conf, min_mask_area_ratio=args.min_mask_area_ratio
        )

        vis = frame.copy()

        if stale:
            cv2.putText(vis, "STALE FRAME (topic delay)", (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        if idx is None:
            cv2.putText(vis, f"BOWL NOT FOUND ({reason})", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        else:
            roi, bbox = get_roi_from_seg_result(r, frame, idx, margin=args.margin)
            if roi is None or bbox is None or roi.size == 0:
                cv2.putText(vis, "BOWL ROI FAIL", (20, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            else:
                grams = predict_grams(reg_model, reg_tf, roi, device=args.device, amp=args.amp)
                pct = clamp((grams / full_grams) * 100.0, 0.0, 100.0)

                x1, y1, x2, y2 = bbox
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(vis, f"{grams:.1f} g ({pct:.0f}%)", (x1, max(30, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        dt = time.time() - t0
        inst_fps = 1.0 / max(dt, 1e-6)
        fps_ema = inst_fps if fps_ema is None else (0.9 * fps_ema + 0.1 * inst_fps)
        cv2.putText(vis, f"{dt*1000:.1f} ms | FPS {fps_ema:.1f}",
                    (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        last_overlay = vis.copy()

        jpg = encode_jpeg(vis)
        if jpg is not None:
            with JPEG_LOCK:
                LATEST_JPEG = jpg


def ros_spin_thread(topic: str):
    rclpy.init()
    node = ImageSub(topic)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="/camera/image_raw", help="ROS2 Image topic (sensor_msgs/Image)")
    ap.add_argument("--yolo_seg", default="models/bowl_seg_best.pt")
    ap.add_argument("--reg_ckpt", default="models/ckpt_feedg_roi_fromtxt__effv2s__224__e80__bs32__lr3e-4__seed42.pt")
    ap.add_argument("--config", default="models/config.yaml")

    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--amp", action="store_true")

    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.60)
    ap.add_argument("--min_mask_area_ratio", type=float, default=0.02)
    ap.add_argument("--margin", type=float, default=0.12)

    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5000)
    
    ap.add_argument("--infer_fps", type=float, default=5.0, help="run inference at this rate (Hz)")

    args = ap.parse_args()

    # ROS node in same process (need access to subscriber instance)
    rclpy.init()
    sub = ImageSub(args.topic)

    th_spin = threading.Thread(target=rclpy.spin, args=(sub,), daemon=True)
    th_spin.start()

    th_infer = threading.Thread(target=infer_loop, args=(args, sub), daemon=True)
    th_infer.start()

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
