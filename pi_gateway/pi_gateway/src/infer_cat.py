"""고양이 포즈/액션/감정 추론 모듈. cat_detection_service.py 및 비디오 추론에서 공유."""
import os
import cv2
import json
import tempfile
import time
import zipfile
import argparse
from collections import deque
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import numpy as np
import torch
import torch.nn as nn
import timm
from ultralytics import YOLO


# -------------------------
# Korean -> English mapping (from your label list)
# -------------------------
ACTION_KO2EN = {
    "걷거나 뛰는 동작": "WALK_OR_RUN",
    "그루밍하는 동작": "GROOMING_ACTION",
    "그루밍함": "GROOMING",
    "꼬리를 흔드는 동작": "TAIL_WAG_ACTION",
    "꼬리를 흔든다": "TAIL_WAG",
    "납작 엎드리는 동작": "CROUCH_FLAT_ACTION",
    "납작 엎드림": "CROUCH_FLAT",
    "머리를 들이대는 동작": "HEAD_BUTT_ACTION",
    "머리를 들이댐": "HEAD_BUTT",
    "발을 숨기고 웅크리고 앉는 동작": "LOAF_SIT_ACTION",
    "발을 숨기고 웅크리고 앉음": "LOAF_SIT",
    "배를 보이는 동작": "SHOW_BELLY_ACTION",
    "배를 보임": "SHOW_BELLY",
    "앞발로 꾹꾹 누르는 동작": "KNEADING_ACTION",
    "앞발로 꾹꾹 누름": "KNEADING",
    "앞발을 뻗어 휘적거리는 동작": "PAW_SWAT_ACTION",
    "옆으로 누워 있음": "LYING_SIDE",
    "옆으로 눕는 동작": "LIE_DOWN_SIDE_ACTION",
    "좌우로 뒹구는 동작": "ROLLING_ACTION",
    "좌우로 뒹굴음": "ROLLING",
    "팔을 뻗어 휘적거림": "PAW_SWAT",
    "허리를 아치로 세우는 동작": "ARCH_BACK_ACTION",
    "허리를 아치로 세움": "ARCH_BACK",
}
EMO_KO2EN = {
    "공격성": "AGGRESSIVE",
    "공포": "FEAR",
    "불안/슬픔": "ANXIOUS_SAD",
    "편안/안정": "CALM",
    "행복/즐거움": "HAPPY",
    "화남/불쾌": "ANGRY",
}
def to_en(label: str, table: dict, prefix: str = "UNK"):
    label = str(label).strip()
    return table.get(label, f"{prefix}:{label}")


# -------------------------
# Model defs (Stage3 Attn)
# -------------------------
class AttentionPooling(nn.Module):
    def __init__(self, feat_dim: int, hidden: int = 256, dropout: float = 0.1):
        super().__init__()
        self.scorer = nn.Sequential(
            nn.Linear(feat_dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )

    def forward(self, feat: torch.Tensor):
        scores = self.scorer(feat)            # (B,K,1)
        alpha = torch.softmax(scores, dim=1)  # (B,K,1)
        v = (alpha * feat).sum(dim=1)         # (B,D)
        return v, alpha.squeeze(-1)           # (B,K)


class AttnMultiHead(nn.Module):
    def __init__(self, encoder, feat_dim, n_action, n_emo, attn_hidden=256, attn_dropout=0.1):
        super().__init__()
        self.encoder = encoder
        self.pooler = AttentionPooling(feat_dim, hidden=attn_hidden, dropout=attn_dropout)
        self.h_action = nn.Linear(feat_dim, n_action)
        self.h_emotion = nn.Linear(feat_dim, n_emo)

    def forward(self, x):
        B, K, C, H, W = x.shape
        x = x.view(B * K, C, H, W)
        feat = self.encoder(x)
        feat = feat.view(B, K, -1)
        v, alpha = self.pooler(feat)
        return self.h_action(v), self.h_emotion(v), alpha


def build_model_from_ckpt(ckpt_path: str, device: str):
    # 단일 파일(.pt)이면 그대로 로드. 디렉터리(best/ 안에 data.pkl, data/0,1,...)면 zip으로 묶어서 로드
    load_path = str(Path(ckpt_path).resolve())
    if os.path.isdir(load_path):
        # PyTorch zip 형식: 아카이브 안에 한 단계 하위 디렉터리 필요 (예: best/data.pkl)
        fd, tmp_path = tempfile.mkstemp(suffix=".pt")
        os.close(fd)
        try:
            prefix = os.path.basename(load_path.rstrip(os.sep))  # e.g. "best"
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
                for root, _dirs, files in os.walk(load_path):
                    for f in files:
                        fn = os.path.join(root, f)
                        rel = os.path.relpath(fn, load_path)
                        arcname = os.path.join(prefix, rel)
                        zf.write(fn, arcname)
            ckpt = torch.load(tmp_path, map_location="cpu", weights_only=False)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    else:
        ckpt = torch.load(load_path, map_location="cpu", weights_only=False)

    action2id = ckpt["action2id"]
    emo2id = ckpt["emo2id"]
    id2action = {v: k for k, v in action2id.items()}
    id2emo = {v: k for k, v in emo2id.items()}

    cfg = ckpt.get("cfg", {})
    backbone = cfg.get("backbone", "swin_tiny_patch4_window7_224")
    attn_hidden = cfg.get("attn_hidden", 256)
    attn_dropout = cfg.get("attn_dropout", 0.1)

    encoder = timm.create_model(backbone, pretrained=False, num_classes=0, global_pool="avg")
    feat_dim = encoder.num_features

    model = AttnMultiHead(
        encoder=encoder,
        feat_dim=feat_dim,
        n_action=len(action2id),
        n_emo=len(emo2id),
        attn_hidden=attn_hidden,
        attn_dropout=attn_dropout,
    )

    sd = ckpt["model"]
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print(f"[LOAD] ckpt={ckpt_path}")
    print(f"[LOAD] backbone={backbone} feat_dim={feat_dim}")
    print(f"[LOAD] missing={len(missing)} unexpected={len(unexpected)}")

    model.to(device).eval()
    return model, id2action, id2emo, backbone


def get_model_input_size(backbone_name: str):
    m = timm.create_model(backbone_name, pretrained=False)
    if hasattr(m, "img_size"):
        isz = m.img_size
        if isinstance(isz, (tuple, list)):
            return int(isz[0])
        return int(isz)
    dc = getattr(m, "default_cfg", {}) or {}
    isz = dc.get("input_size", (3, 224, 224))
    return int(isz[1])


def preprocess_bgr(frame_bgr: np.ndarray, img_size: int) -> torch.Tensor:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
    x = rgb.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    x = (x - mean) / std
    x = np.transpose(x, (2, 0, 1))
    return torch.from_numpy(x)


# -------------------------
# Drawing helpers
# -------------------------
def put_text_box(img, text, org, font_scale=0.7, thickness=2):
    x, y = org
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    pad = 8
    x1, y1 = x, y - th - pad
    x2, y2 = x + tw + pad * 2, y + baseline + pad
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(img.shape[1] - 1, x2); y2 = min(img.shape[0] - 1, y2)
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
    cv2.putText(img, text, (x + pad, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

def draw_glow_circle(img, cx, cy, r, color_bgr, alpha=0.18):
    overlay = img.copy()
    cv2.circle(overlay, (cx, cy), r * 2, color_bgr, thickness=-1, lineType=cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.circle(img, (cx, cy), r, color_bgr, thickness=-1, lineType=cv2.LINE_AA)

def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, int(round(float(x))))))

def put_label_bottom_left(frame_bgr: np.ndarray, action_en: str, emotion_en: str):
    h, w = frame_bgr.shape[:2]
    put_text_box(frame_bgr, f"Emotion: {emotion_en}", (12, h - 20), font_scale=0.75, thickness=2)
    put_text_box(frame_bgr, f"Action : {action_en}", (12, h - 55), font_scale=0.75, thickness=2)
    return frame_bgr


# -------------------------
# Simple smoothing for keypoints (EMA + deadzone + hold)
# -------------------------
class KeypointSmoother:
    def __init__(self, alpha=0.35, min_move=1.5, hold=6):
        self.alpha = float(alpha)
        self.min_move = float(min_move)
        self.hold = int(hold)
        self.kp = None          # (K,2)
        self.kp_conf = None     # (K,)
        self.miss = 0

    def reset(self):
        self.kp = None
        self.kp_conf = None
        self.miss = 0

    def update(self, kp_xy: Optional[np.ndarray], kp_conf: Optional[np.ndarray]) -> Optional[Tuple[np.ndarray, Optional[np.ndarray]]]:
        """
        kp_xy: (K,2) or None
        kp_conf: (K,) or None
        returns smoothed (kp_xy, kp_conf) or None if dropped
        """
        if kp_xy is None:
            self.miss += 1
            if self.miss > self.hold:
                self.reset()
                return None
            return (self.kp, self.kp_conf) if self.kp is not None else None

        self.miss = 0
        kp_xy = kp_xy.astype(np.float32)

        if self.kp is None:
            self.kp = kp_xy.copy()
            self.kp_conf = kp_conf.copy() if kp_conf is not None else None
            return self.kp, self.kp_conf

        # deadzone: tiny jitter ignored
        delta = kp_xy - self.kp
        move = np.sqrt((delta ** 2).sum(axis=1))  # (K,)
        mask = move >= self.min_move
        blended = self.kp.copy()
        blended[mask] = blended[mask] * (1.0 - self.alpha) + kp_xy[mask] * self.alpha

        self.kp = blended
        self.kp_conf = kp_conf.copy() if kp_conf is not None else self.kp_conf
        return self.kp, self.kp_conf


# -------------------------
# YOLO pick best + draw
# -------------------------
def pick_best_pose(res, only_best_one: bool):
    """
    Return: box(4,), conf, kp_xy(K,2), kp_conf(K,) or None
    """
    if res is None or res.boxes is None or len(res.boxes) == 0 or res.keypoints is None:
        return None

    boxes = res.boxes.xyxy.cpu().numpy()
    det_confs = res.boxes.conf.cpu().numpy().astype(float)
    kps_xy = res.keypoints.xy.cpu().numpy()

    kps_cf = None
    if hasattr(res.keypoints, "conf") and res.keypoints.conf is not None:
        kps_cf = res.keypoints.conf.cpu().numpy().astype(float)

    idxs = list(range(len(boxes)))
    if not idxs:
        return None

    if only_best_one:
        areas = [(i, (boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1])) for i in idxs]
        bi = max(areas, key=lambda x: x[1])[0]
    else:
        bi = int(np.argmax(det_confs))

    box = boxes[bi]
    conf = float(det_confs[bi])
    kp_xy = kps_xy[bi]
    kp_cf = (kps_cf[bi] if kps_cf is not None else None)
    return box, conf, kp_xy, kp_cf


def draw_pose_bbox(frame_bgr: np.ndarray, box, conf, kp_xy, kp_conf, args):
    H, W = frame_bgr.shape[:2]
    green = (0, 255, 0)

    # bbox
    x1, y1, x2, y2 = box
    x1 = clamp_int(x1, 0, W-1); y1 = clamp_int(y1, 0, H-1)
    x2 = clamp_int(x2, 0, W-1); y2 = clamp_int(y2, 0, H-1)
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), green, args.box_thickness, cv2.LINE_AA)
    put_text_box(frame_bgr, f"cat conf: {conf:.2f}", (x1, max(20, y1 - 8)), 0.7, 2)

    # keypoints
    base_r = args.kp_radius if args.kp_radius > 0 else max(2, int(min(W, H) * 0.004))
    pulse = 0.6 + 0.4 * (0.5 * (1 + np.sin(args._frame_idx * 0.35)))
    r = int(base_r * (1.0 + 0.8 * pulse))

    for j in range(kp_xy.shape[0]):
        x, y = kp_xy[j]
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        if kp_conf is not None:
            if j < len(kp_conf) and float(kp_conf[j]) < args.kpt_conf:
                continue
        cx = clamp_int(x, 0, W-1)
        cy = clamp_int(y, 0, H-1)
        draw_glow_circle(frame_bgr, cx, cy, r, green, alpha=0.18)

    return frame_bgr


@torch.no_grad()
def run(args):
    """비디오 파일 입력 → 추론 → 결과 영상 저장. python -m src.infer_cat --video xxx --ckpt ... 로 실행."""
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"

    model, id2action, id2emo, backbone = build_model_from_ckpt(args.ckpt, device)
    img_size = get_model_input_size(backbone)
    print(f"[PREP] backbone={backbone} img_size={img_size}")

    yolo = YOLO(args.yolo_pose)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {args.video}")

    in_fps = cap.get(cv2.CAP_PROP_FPS)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"[INFO] input fps (cv2) = {in_fps}")
    print(f"[INFO] input size = {W}x{H}")

    fps = float(args.out_fps)
    out_path = args.out
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (W, H))
    if not writer.isOpened():
        raise RuntimeError("VideoWriter failed to open. Try changing codec or output path.")

    K = args.K
    buf = deque(maxlen=K)
    kp_smoother = KeypointSmoother(alpha=args.kp_smooth_alpha, min_move=args.kp_min_move, hold=args.kp_hold)

    last_action = "..."
    last_emotion = "..."
    ref_fps = fps if fps > 0 else 30.0
    cls_every_n_frames = max(1, int(round(ref_fps / max(args.cls_hz, 1e-6))))
    print(f"[SCHED] cls_hz={args.cls_hz} => classify every {cls_every_n_frames} frames (ref_fps={ref_fps})")

    frame_idx = 0
    t0 = time.time()

    while True:
        ok, raw_frame = cap.read()
        if not ok:
            break

        args._frame_idx = frame_idx

        yres = yolo.predict(raw_frame, verbose=False)
        vis_frame = raw_frame.copy()

        picked = None
        if len(yres) > 0:
            picked = pick_best_pose(yres[0], only_best_one=args.only_best_one)

        if picked is not None:
            box, det_conf, kp_xy, kp_cf = picked
            sm = kp_smoother.update(kp_xy, kp_cf)
            if sm is not None:
                kp_xy_s, kp_cf_s = sm
                vis_frame = draw_pose_bbox(vis_frame, box, det_conf, kp_xy_s, kp_cf_s, args)
        else:
            kp_smoother.update(None, None)

        x = preprocess_bgr(raw_frame, img_size)
        buf.append(x)

        if len(buf) == K and (frame_idx % cls_every_n_frames == 0):
            stack = torch.stack(list(buf), dim=0).unsqueeze(0).to(device)
            out_a, out_e, _ = model(stack)
            pa = int(out_a.argmax(1).item())
            pe = int(out_e.argmax(1).item())
            last_action = id2action.get(pa, str(pa))
            last_emotion = id2emo.get(pe, str(pe))

        action_en = to_en(last_action, ACTION_KO2EN, prefix="ACT")
        emotion_en = to_en(last_emotion, EMO_KO2EN, prefix="EMO")
        vis_frame = put_label_bottom_left(vis_frame, action_en, emotion_en)

        writer.write(vis_frame)

        if args.show:
            cv2.imshow("cat inference", vis_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        frame_idx += 1

    cap.release()
    writer.release()
    if args.show:
        cv2.destroyAllWindows()

    dt = time.time() - t0
    print(f"[DONE] saved: {out_path}")
    print(f"[DONE] frames={frame_idx}, time={dt:.1f}s, write_fps={fps}, effective_proc_fps={frame_idx/max(dt,1e-6):.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="cat.webm")
    ap.add_argument("--ckpt", type=str, required=True)
    ap.add_argument("--out", type=str, default="cat_pred.mp4")
    ap.add_argument("--K", type=int, default=8)
    ap.add_argument("--cls_hz", type=float, default=5.0, help="classify action/emotion N times per second (default=5)")
    ap.add_argument("--yolo_pose", type=str, default="yolov8s-pose.pt")
    ap.add_argument("--kpt_conf", type=float, default=0.25)
    ap.add_argument("--out_fps", type=float, default=30.0)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--only_best_one", action="store_true")
    ap.add_argument("--box_thickness", type=int, default=2)
    ap.add_argument("--kp_radius", type=int, default=0)
    ap.add_argument("--kp_smooth_alpha", type=float, default=0.35)
    ap.add_argument("--kp_min_move", type=float, default=1.5)
    ap.add_argument("--kp_hold", type=int, default=6)

    args = ap.parse_args()
    args._frame_idx = 0
    run(args)
