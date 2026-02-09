import argparse
from pathlib import Path
import time

import cv2
import numpy as np
import torch
import timm
from PIL import Image
from torchvision import transforms
from ultralytics import YOLO
import yaml


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
    # torch 2.4+ warning 줄이기 (가능하면 weights_only=True)
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


# =========================
# Config
# =========================
def load_full_grams(config_path: Path) -> float:
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    full_grams = float(cfg.get("full_grams", 0.0))
    if full_grams <= 0:
        raise ValueError("full_grams must be > 0 in config.yaml")
    return full_grams


# =========================
# YOLO seg -> pick best bowl
# =========================
def overlay_mask(vis_bgr, mask01, alpha=0.35):
    if mask01 is None:
        return vis_bgr
    H, W = vis_bgr.shape[:2]
    if mask01.shape[0] != H or mask01.shape[1] != W:
        mask01 = cv2.resize(mask01, (W, H), interpolation=cv2.INTER_NEAREST)

    overlay = vis_bgr.copy()
    overlay[mask01 > 0] = (0, 255, 255)  # yellow
    return cv2.addWeighted(overlay, alpha, vis_bgr, 1 - alpha, 0)


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
    """
    여러 검출이 나와도, '진짜 그릇'은 보통 가장 큰 마스크 면적.
    - conf_thres 미만은 제외
    - mask 면적이 프레임 대비 너무 작은 것 제외 (왼쪽 위 작은 박스 제거 핵심)
    """
    boxes = result.boxes
    masks = result.masks

    if boxes is None or len(boxes) == 0:
        return None, "no_box"

    if masks is None or masks.data is None or len(masks.data) == 0:
        # seg가 없다면 confidence 최대
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
        area = float(mask01.sum())
        area_ratio = area / frame_area

        if area_ratio < min_mask_area_ratio:
            continue

        # 점수: 면적 우선(가장 큰 bowl 가정), tie-break로 conf 약간 가산
        score = area_ratio + 0.001 * c
        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx is None:
        return None, "filtered_all"
    return int(best_idx), "best_mask_area"


def get_roi_from_seg_result(result, frame_bgr, idx, margin=0.12):
    H, W = frame_bgr.shape[:2]
    mask01 = None

    if result.masks is not None and result.masks.data is not None and idx is not None:
        m = result.masks.data[idx].detach().cpu().numpy()
        mask01 = (m > 0.5).astype(np.uint8)
        bbox = mask_to_bbox_xyxy(mask01)
        if bbox is None:
            return None, None, None
        x1, y1, x2, y2 = bbox
        x1, y1, x2, y2 = expand_bbox(x1, y1, x2, y2, W, H, margin=margin)
        roi = frame_bgr[y1:y2 + 1, x1:x2 + 1].copy()

        # resize mask to frame
        if mask01.shape[0] != H or mask01.shape[1] != W:
            mask01 = cv2.resize(mask01, (W, H), interpolation=cv2.INTER_NEAREST)

        return roi, (x1, y1, x2, y2), mask01

    # fallback box
    b = result.boxes.xyxy[idx].detach().cpu().numpy().astype(int)
    x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
    x1, y1, x2, y2 = expand_bbox(x1, y1, x2, y2, W, H, margin=margin)
    roi = frame_bgr[y1:y2 + 1, x1:x2 + 1].copy()
    return roi, (x1, y1, x2, y2), None


# =========================
# Main
# =========================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", default="0", help="camera index (0) or video path")
    ap.add_argument(
    "--yolo_seg",
    default="models/bowl_seg_best.pt",
    help="path to YOLOv8 segmentation model (bowl)"
    )
    
    ap.add_argument(
    "--reg_ckpt",
    default="models/ckpt_feedg_roi_fromtxt__effv2s__224__e80__bs32__lr3e-4__seed42.pt",
    help="path to regression checkpoint"
    )

    ap.add_argument(
    "--config",
    default="models/config.yaml",
    help="path to config.yaml (must contain full_grams)"
    )
    
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--amp", action="store_true")

    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--min_mask_area_ratio", type=float, default=0.02,  # << 핵심(작은 잡검출 제거)
                    help="min mask area ratio to keep (e.g., 0.02 = 2% of frame)")
    ap.add_argument("--margin", type=float, default=0.12)

    ap.add_argument("--show_mask", action="store_true")
    ap.add_argument("--save_video", default="", help="optional output video path (mp4)")
    args = ap.parse_args()

    full_grams = load_full_grams(Path(args.config))

    # load models
    yolo = YOLO(str(args.yolo_seg))
    reg_model, reg_tf, backbone, reg_imgsz = load_regression(Path(args.reg_ckpt), args.device)

    print("device     :", args.device, "| amp:", args.amp)
    print("yolo_seg   :", args.yolo_seg)
    print("reg_ckpt   :", args.reg_ckpt, "| backbone:", backbone, "| reg_imgsz:", reg_imgsz)
    print("full_grams :", full_grams)

    # open camera/video
    cam_src = args.cam
    if cam_src.isdigit():
        cap = cv2.VideoCapture(int(cam_src))
    else:
        cap = cv2.VideoCapture(cam_src)

    if not cap.isOpened():
        raise RuntimeError(f"cannot open camera/video: {args.cam}")

    # optional video writer
    writer = None
    if args.save_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps is None or fps <= 1:
            fps = 30
        writer = cv2.VideoWriter(args.save_video, fourcc, fps, (w, h))
        print("save_video :", args.save_video, f"({w}x{h}@{fps})")

    # fps smoothing
    fps_ema = None
    t_prev = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        t0 = time.time()

        # YOLO seg inference
        r = yolo.predict(source=frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]

        # choose best bowl instance (remove small false bbox)
        idx, reason = choose_best_instance_by_mask_area(
            r, conf_thres=args.conf, min_mask_area_ratio=args.min_mask_area_ratio
        )

        vis = frame.copy()

        if idx is None:
            cv2.putText(vis, f"BOWL NOT FOUND ({reason})", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        else:
            roi, bbox, mask01 = get_roi_from_seg_result(r, frame, idx, margin=args.margin)
            if roi is None or bbox is None or roi.size == 0:
                cv2.putText(vis, "BOWL ROI FAIL", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            else:
                grams = predict_grams(reg_model, reg_tf, roi, device=args.device, amp=args.amp)
                pct = clamp((grams / full_grams) * 100.0, 0.0, 100.0)

                x1, y1, x2, y2 = bbox

                if args.show_mask and mask01 is not None:
                    vis = overlay_mask(vis, mask01, alpha=0.35)

                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                txt = f"{grams:.1f} g ({pct:.0f}%)"
                cv2.putText(vis, txt, (x1, max(30, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # fps + latency
        dt = time.time() - t0
        inst_fps = 1.0 / max(dt, 1e-6)
        fps_ema = inst_fps if fps_ema is None else (0.9 * fps_ema + 0.1 * inst_fps)

        cv2.putText(vis, f"{dt*1000:.1f} ms | FPS {fps_ema:.1f}",
                    (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        cv2.imshow("FeedAI | YOLO-seg + Feed regression", vis)
        if writer is not None:
            writer.write(vis)

        key = cv2.waitKey(1) & 0xFF
        if key in [27, ord("q")]:
            break

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
