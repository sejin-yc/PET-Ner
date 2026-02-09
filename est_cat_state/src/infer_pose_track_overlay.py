import argparse
import math
from dataclasses import dataclass
from typing import Optional, Dict, Any

import cv2
import numpy as np
from ultralytics import YOLO


# -----------------------
# Utils
# -----------------------
def iou_xyxy(a, b) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - inter + 1e-9
    return float(inter / union)

def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, int(round(float(x))))))

def draw_glow_circle(img, cx, cy, r, color_bgr, alpha=0.18):
    overlay = img.copy()
    cv2.circle(overlay, (cx, cy), r * 2, color_bgr, thickness=-1, lineType=cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.circle(img, (cx, cy), r, color_bgr, thickness=-1, lineType=cv2.LINE_AA)

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

def ema_update(prev: np.ndarray, cur: np.ndarray, alpha: float) -> np.ndarray:
    return prev * (1.0 - alpha) + cur * alpha


# -----------------------
# Pose quality filter (False Positive killer)
# -----------------------
def pose_quality_filter(
    box_xyxy: np.ndarray,
    kp_xy: np.ndarray,
    kp_conf: Optional[np.ndarray],
    min_kp_conf: float = 0.20,
    min_valid_kps: int = 9,
    min_inside_ratio: float = 0.80,
) -> (bool, Dict[str, Any]):
    """
    Return True if pose looks plausible.
    - valid keypoints count >= min_valid_kps (conf >= min_kp_conf)
    - among valid keypoints, inside bbox ratio >= min_inside_ratio

    If kp_conf is None (some models), we skip strict filtering and accept.
    """
    x1, y1, x2, y2 = [float(v) for v in box_xyxy.tolist()]
    K = int(kp_xy.shape[0])

    if kp_conf is None:
        return True, {"valid_kps": K, "inside_ratio": 1.0, "note": "no_kp_conf"}

    conf = kp_conf.astype(float)
    valid_mask = conf >= float(min_kp_conf)
    valid_cnt = int(valid_mask.sum())
    if valid_cnt < int(min_valid_kps):
        return False, {"valid_kps": valid_cnt, "inside_ratio": 0.0, "note": "few_kps"}

    pts = kp_xy[valid_mask]
    inside = (
        (pts[:, 0] >= x1) & (pts[:, 0] <= x2) &
        (pts[:, 1] >= y1) & (pts[:, 1] <= y2)
    )
    inside_ratio = float(inside.mean()) if len(pts) > 0 else 0.0
    ok = inside_ratio >= float(min_inside_ratio)
    return ok, {"valid_kps": valid_cnt, "inside_ratio": inside_ratio, "note": "ok" if ok else "outside_bbox"}


# -----------------------
# Tracking state
# -----------------------
@dataclass
class TrackState:
    has: bool = False
    last_box: Optional[np.ndarray] = None     # (4,)
    last_kp: Optional[np.ndarray] = None      # (K,2)
    last_kpconf: Optional[np.ndarray] = None  # (K,)
    last_detconf: float = 0.0
    last_cls: int = -1
    miss_count: int = 0


# -----------------------
# Args
# -----------------------
def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="input video path (.webm/.mp4)")
    ap.add_argument("--weights", required=True, help="YOLO pose weights (.pt)")
    ap.add_argument("--out", default="out_pose_track.mp4", help="output video path (.mp4)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--fps", type=float, default=30.0, help="output fps (fixed).")
    ap.add_argument("--only_best_one", action="store_true", help="keep only largest box")
    ap.add_argument("--class_id", type=int, default=-1, help="filter class id (-1 disables)")
    ap.add_argument("--smooth_alpha", type=float, default=0.35, help="EMA alpha for keypoints")
    ap.add_argument("--hold_frames", type=int, default=6, help="keep last pose for N missed frames")
    ap.add_argument("--kp_conf_th", type=float, default=0.15, help="min keypoint conf to draw (if available)")
    ap.add_argument("--show", action="store_true", help="show realtime window")
    ap.add_argument("--show_fps", action="store_true", help="overlay realtime FPS on video")
    ap.add_argument("--box_thickness", type=int, default=2)
    ap.add_argument("--kp_radius", type=int, default=0, help="0=auto, else fixed radius")
    # pose quality filter params
    ap.add_argument("--pq_min_kp_conf", type=float, default=0.20)
    ap.add_argument("--pq_min_valid_kps", type=int, default=7)
    ap.add_argument("--pq_min_inside_ratio", type=float, default=0.70)
    ap.add_argument("--pq_debug", action="store_true", help="draw reject reason text when filtered")
    ap.add_argument("--pred_json", type=str, default="", help="frame-wise action/emotion json")

    return ap.parse_args()

ACTION_EN = [
  "Walk/Run motion",            # 00
  "Grooming motion",            # 01
  "Grooming",                   # 02
  "Tail wagging motion",        # 03
  "Tail wagging",               # 04
  "Crouch/flatten motion",      # 05
  "Crouching/flattened",        # 06
  "Nuzzle/head-butting motion", # 07
  "Nuzzle/head-butting",        # 08
  "Tuck paws & sit motion",     # 09
  "Tuck paws & sitting",        # 10
  "Expose belly motion",        # 11
  "Expose belly",               # 12
  "Kneading motion",            # 13
  "Kneading",                   # 14
  "Paw swiping motion",         # 15
  "Lying on side",              # 16
  "Lie down on side motion",    # 17
  "Rolling motion",             # 18
  "Rolling",                    # 19
  "Paw swiping",                # 20
  "Arch back motion",           # 21
  "Arch back",                  # 22
]

EMOTION_EN = [
  "Aggression",        # 00 공격성
  "Fear",              # 01 공포
  "Anxiety/Sadness",   # 02 불안/슬픔
  "Calm/Stable",       # 03 편안/안정
  "Happy/Joy",         # 04 행복/즐거움
  "Angry/Displeased",  # 05 화남/불쾌
]


# -----------------------
# Main
# -----------------------
def main():
    args = parse_args()
    model = YOLO(args.weights)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    pred_by_frame = {}
    if args.pred_json:
        import json
        with open(args.pred_json, "r", encoding="utf-8") as f:
            arr = json.load(f)
        # frame -> (action_id, emotion_id)
        for r in arr:
            pred_by_frame[int(r["frame"])] = (int(r["action_id"]), int(r["emotion_id"]))
        print(f"[INFO] loaded pred_json frames={len(pred_by_frame)}")

    out_fps = float(args.fps) if args.fps and args.fps > 0 else 30.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(args.out, fourcc, out_fps, (W, H))
    if not vw.isOpened():
        raise RuntimeError(f"Cannot open VideoWriter: {args.out}")

    st = TrackState()
    frame_idx = 0

    green = (0, 255, 0)  # BGR
    base_r = args.kp_radius if args.kp_radius > 0 else max(2, int(min(W, H) * 0.004))

    # FPS measure for show_fps
    t_prev = cv2.getTickCount()
    fps_smooth = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # ---------- YOLO predict ----------
        res = model.predict(
            source=frame,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            verbose=False
        )[0]

        chosen = None  # (box, det_conf, cls, kp_xy, kp_conf)
        reject_info = None

        if res.boxes is not None and len(res.boxes) > 0 and res.keypoints is not None:
            boxes = res.boxes.xyxy.cpu().numpy()                   # (N,4)
            det_confs = res.boxes.conf.cpu().numpy().astype(float) # (N,)
            clss = res.boxes.cls.cpu().numpy().astype(int)         # (N,)
            kps_xy = res.keypoints.xy.cpu().numpy()                # (N,K,2)
            kps_cf = None
            if hasattr(res.keypoints, "conf") and res.keypoints.conf is not None:
                kps_cf = res.keypoints.conf.cpu().numpy().astype(float)  # (N,K)

            candidates = []
            for i in range(len(boxes)):
                if args.class_id >= 0 and clss[i] != args.class_id:
                    continue
                candidates.append(i)

            if candidates:
                if args.only_best_one:
                    areas = [(i, (boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1])) for i in candidates]
                    best_i = max(areas, key=lambda x: x[1])[0]
                else:
                    best_i = max(candidates, key=lambda i: det_confs[i])

                kp_xy_i = kps_xy[best_i]
                kp_cf_i = (kps_cf[best_i] if kps_cf is not None else None)

                # ---------- Pose quality filter ----------
                ok_pose, info = pose_quality_filter(
                    boxes[best_i],
                    kp_xy_i,
                    kp_cf_i,
                    min_kp_conf=args.pq_min_kp_conf,
                    min_valid_kps=args.pq_min_valid_kps,
                    min_inside_ratio=args.pq_min_inside_ratio,
                )

                if ok_pose:
                    chosen = (boxes[best_i], float(det_confs[best_i]), int(clss[best_i]), kp_xy_i, kp_cf_i)
                else:
                    chosen = None
                    reject_info = info

        # ---------- simple tracking + smoothing ----------
        if chosen is not None:
            box, det_conf, cls_id, kp_xy, kp_conf = chosen

            if st.has and st.last_box is not None:
                if iou_xyxy(st.last_box, box) < 0.10:
                    # new target
                    st.last_box = box
                    st.last_kp = kp_xy
                    st.last_kpconf = kp_conf
                    st.last_detconf = det_conf
                    st.last_cls = cls_id
                    st.miss_count = 0
                else:
                    # same target -> smooth
                    st.last_box = box
                    st.last_detconf = det_conf
                    st.last_cls = cls_id
                    st.last_kp = kp_xy if st.last_kp is None else ema_update(st.last_kp, kp_xy, args.smooth_alpha)
                    st.last_kpconf = kp_conf
                    st.miss_count = 0
            else:
                st.has = True
                st.last_box = box
                st.last_kp = kp_xy
                st.last_kpconf = kp_conf
                st.last_detconf = det_conf
                st.last_cls = cls_id
                st.miss_count = 0

        else:
            # if nothing chosen (including filtered out), hold previous for a few frames
            if st.has:
                st.miss_count += 1
                if st.miss_count > args.hold_frames:
                    st = TrackState()

        # ---------- draw ----------
        if st.has and st.last_box is not None:
            x1, y1, x2, y2 = st.last_box
            x1 = clamp_int(x1, 0, W - 1)
            y1 = clamp_int(y1, 0, H - 1)
            x2 = clamp_int(x2, 0, W - 1)
            y2 = clamp_int(y2, 0, H - 1)

            cv2.rectangle(frame, (x1, y1), (x2, y2), green, args.box_thickness, cv2.LINE_AA)
            put_text_box(frame, f"cat conf: {st.last_detconf:.2f}", (x1, max(20, y1 - 8)), font_scale=0.7, thickness=2)

        if st.has and st.last_kp is not None:
            # sparkle pulse
            pulse = 0.6 + 0.4 * (0.5 * (1 + math.sin(frame_idx * 0.35)))
            r = int(base_r * (1.0 + 0.8 * pulse))

            kp = st.last_kp
            for j in range(kp.shape[0]):
                x, y = kp[j]
                if not np.isfinite(x) or not np.isfinite(y):
                    continue
                if st.last_kpconf is not None:
                    if j < len(st.last_kpconf) and float(st.last_kpconf[j]) < args.kp_conf_th:
                        continue
                cx = clamp_int(x, 0, W - 1)
                cy = clamp_int(y, 0, H - 1)
                draw_glow_circle(frame, cx, cy, r, green, alpha=0.18)

        # show debug if filtered out this frame
        if args.pq_debug and reject_info is not None and not st.has:
            put_text_box(
                frame,
                f"REJECT pose (kps={reject_info.get('valid_kps','?')} inside={reject_info.get('inside_ratio',0):.2f} {reject_info.get('note','')})",
                (12, 60),
                font_scale=0.65,
                thickness=2,
            )

        # realtime FPS overlay
        if args.show_fps:
            t_now = cv2.getTickCount()
            dt = (t_now - t_prev) / cv2.getTickFrequency()
            t_prev = t_now
            cur_fps = 1.0 / max(dt, 1e-6)
            fps_smooth = 0.9 * fps_smooth + 0.1 * cur_fps if fps_smooth > 0 else cur_fps
            put_text_box(frame, f"FPS: {fps_smooth:.1f}", (12, 28), font_scale=0.7, thickness=2)

        # --- action/emotion overlay (bottom-left) ---
        if args.pred_json and frame_idx in pred_by_frame:
            a_id, e_id = pred_by_frame[frame_idx]
            a_txt = ACTION_EN[a_id] if 0 <= a_id < len(ACTION_EN) else f"Action:{a_id}"
            e_txt = EMOTION_EN[e_id] if 0 <= e_id < len(EMOTION_EN) else f"Emotion:{e_id}"

            # 아래에서 위로 2줄 (좌하단)
            put_text_box(frame, f"Emotion: {e_txt}", (12, H - 20), font_scale=0.75, thickness=2)
            put_text_box(frame, f"Action : {a_txt}", (12, H - 55), font_scale=0.75, thickness=2)


        vw.write(frame)

        if args.show:
            cv2.imshow("cat pose track (filtered)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        frame_idx += 1

    cap.release()
    vw.release()
    if args.show:
        cv2.destroyAllWindows()

    print(f"[DONE] saved: {args.out}")


if __name__ == "__main__":
    main()
