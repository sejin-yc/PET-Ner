# make_yolo_pose_dataset_from_videojson.py
# Convert: video-folder (.mp4 dir) + video-level json (.mp4.json with per-frame annos)
# To: Ultralytics YOLO Pose dataset format
# Output:
#   cat_pose_yolo/
#     data.yaml
#     images/train/*.jpg
#     images/val/*.jpg
#     labels/train/*.txt
#     labels/val/*.txt
#
# Label txt format (per image, 1 object):
#   cls xc yc w h  x1 y1 v1  x2 y2 v2 ... xK yK vK
# All coords are normalized [0,1]. v: 0(not labeled) or 2(labeled/visible).

import json
import shutil
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import cv2

# =========================
# USER CONFIG (EDIT THESE)
# =========================
TRAIN_IMG_ROOT = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/원천")
TRAIN_LBL_ROOT = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/라벨")
VAL_IMG_ROOT   = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/원천")
VAL_LBL_ROOT   = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/라벨")

OUT_ROOT = Path("./cat_pose_yolo")     # output dataset root
CLASS_ID = 0
CLASS_NAME = "cat"

NUM_KPTS = 15                          # your json uses "1".."15"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# If your data contains many frames but only some are annotated, we only export annotated frames.
# You can also downsample annotations if too many.
EXPORT_EVERY_N_ANNOS = 5               # 1 = export all annotated frames, 2 = export every 2nd anno, ...


# =========================
# Indexing helpers
# =========================
def index_json_by_name(lbl_root: Path) -> Dict[str, Path]:
    """key: 'xxxxx.mp4.json' -> json Path"""
    idx: Dict[str, Path] = {}
    for j in lbl_root.rglob("*.json"):
        idx[j.name] = j
    return idx


def list_video_dirs(img_root: Path) -> List[Path]:
    """Find directories whose name endswith '.mp4'"""
    vids: List[Path] = []
    for p in img_root.rglob("*"):
        if p.is_dir() and p.name.lower().endswith(".mp4"):
            vids.append(p)
    return vids


# =========================
# Frame matching (UPDATED for your filename pattern)
#   frame_{frame_number}_timestamp_{ms}.jpg
# =========================
def find_frame_image(video_dir: Path, frame_number: int) -> Optional[Path]:
    """
    Expected filename pattern:
      frame_{frame_number}_timestamp_{ms}.jpg
    Examples:
      frame_0_timestamp_0.jpg
      frame_12_timestamp_800.jpg
      frame_15_timestamp_1000.jpg

    We match by frame_number first (exact), then fallback to nearest.
    """
    frame_number = int(frame_number)

    # 1) exact match by glob (fast)
    for ext in IMG_EXTS:
        cand = list(video_dir.rglob(f"frame_{frame_number}_timestamp_*{ext}"))
        if cand:
            cand.sort()
            return cand[0]

    # 2) regex fallback: parse all frames and find closest
    pattern = re.compile(r"^frame_(\d+)_timestamp_(\d+)\.[^.]+$", re.IGNORECASE)
    candidates = []
    for p in video_dir.rglob("*"):
        if p.suffix.lower() not in IMG_EXTS:
            continue
        m = pattern.match(p.name)
        if not m:
            continue
        fn = int(m.group(1))
        ts = int(m.group(2))
        candidates.append((fn, ts, p))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (abs(x[0] - frame_number), x[0], x[1]))
    return candidates[0][2]


# =========================
# Geometry conversions
# =========================
def bbox_to_yolo(bb: dict, W: int, H: int) -> Tuple[float, float, float, float]:
    """
    bb: {"x":..., "y":..., "width":..., "height":...} in pixels (top-left)
    -> (xc,yc,w,h) normalized
    """
    x = float(bb["x"])
    y = float(bb["y"])
    w = float(bb["width"])
    h = float(bb["height"])
    xc = (x + w / 2.0) / W
    yc = (y + h / 2.0) / H
    ww = w / W
    hh = h / H
    # clamp to [0,1] just in case
    xc = min(max(xc, 0.0), 1.0)
    yc = min(max(yc, 0.0), 1.0)
    ww = min(max(ww, 0.0), 1.0)
    hh = min(max(hh, 0.0), 1.0)
    return xc, yc, ww, hh


def kpts_to_yolo(kpts: dict, W: int, H: int, num_kpts: int) -> List[float]:
    """
    YOLO pose expects:
      [x1,y1,v1, x2,y2,v2, ...] (all normalized)
    - if json point is null -> (0,0,0)
    - else -> (x/W, y/H, 2)
    """
    out: List[float] = []
    for i in range(1, num_kpts + 1):
        item = kpts.get(str(i), None)
        if item is None:
            out += [0.0, 0.0, 0.0]
        else:
            x = float(item["x"])
            y = float(item["y"])
            xn = min(max(x / W, 0.0), 1.0)
            yn = min(max(y / H, 0.0), 1.0)
            out += [xn, yn, 2.0]
    return out


# =========================
# IO helpers
# =========================
def safe_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    shutil.copy2(src, dst)


def write_label_txt(txt_path: Path, cls_id: int, bb_yolo, kpts_yolo):
    xc, yc, w, h = bb_yolo
    vals = [cls_id, xc, yc, w, h] + kpts_yolo
    # write with fixed precision
    parts = []
    for v in vals:
        if isinstance(v, float):
            parts.append(f"{v:.6f}")
        else:
            parts.append(str(v))
    line = " ".join(parts)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(line + "\n", encoding="utf-8")


# =========================
# Debug visualization (optional)
# =========================
def draw_debug(img_bgr, bb, kpts: dict, save_path: Path):
    x = int(bb["x"])
    y = int(bb["y"])
    w = int(bb["width"])
    h = int(bb["height"])
    cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)

    for i in range(1, NUM_KPTS + 1):
        item = kpts.get(str(i), None)
        if item is None:
            continue
        px = int(item["x"])
        py = int(item["y"])
        cv2.circle(img_bgr, (px, py), 3, (0, 255, 255), -1)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(save_path), img_bgr)


# =========================
# Main conversion per split
# =========================
def process_split(
    img_root: Path,
    lbl_root: Path,
    out_images: Path,
    out_labels: Path,
    debug_vis_dir: Optional[Path] = None,
):
    json_idx = index_json_by_name(lbl_root)
    video_dirs = list_video_dirs(img_root)

    total_written = 0
    miss_json = 0
    miss_frame = 0
    miss_anno = 0

    for vdir in video_dirs:
        jname = vdir.name + ".json"  # "xxxxx.mp4.json"
        jpath = json_idx.get(jname, None)
        if jpath is None:
            miss_json += 1
            continue

        try:
            meta = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception:
            miss_json += 1
            continue

        annos = meta.get("annotations", [])
        if not annos:
            miss_anno += 1
            continue

        vid_stem = vdir.name.replace(".", "_")  # "xxx.mp4" -> "xxx_mp4"

        for ai, a in enumerate(annos):
            if EXPORT_EVERY_N_ANNOS > 1 and (ai % EXPORT_EVERY_N_ANNOS != 0):
                continue

            frame_number = int(a.get("frame_number", -1))
            bb = a.get("bounding_box", None)
            kpts = a.get("keypoints", None)
            if frame_number < 0 or bb is None or kpts is None:
                miss_anno += 1
                continue

            img_path = find_frame_image(vdir, frame_number)
            if img_path is None or not img_path.exists():
                miss_frame += 1
                continue

            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                miss_frame += 1
                continue
            H, W = img_bgr.shape[:2]

            bb_yolo = bbox_to_yolo(bb, W, H)
            kpts_yolo = kpts_to_yolo(kpts, W, H, NUM_KPTS)

            out_name = f"{vid_stem}_f{frame_number:06d}{img_path.suffix.lower()}"
            out_img = out_images / out_name
            out_txt = out_labels / (Path(out_name).stem + ".txt")

            safe_copy(img_path, out_img)
            write_label_txt(out_txt, CLASS_ID, bb_yolo, kpts_yolo)
            total_written += 1

            # optional debug rendering for the first few or for all if you want
            if debug_vis_dir is not None and total_written <= 200:
                dbg_path = debug_vis_dir / out_name
                draw_debug(img_bgr.copy(), bb, kpts, dbg_path)

    print(
        f"[SPLIT] {img_root.name} wrote={total_written} "
        f"miss_json={miss_json} miss_frame={miss_frame} miss_anno={miss_anno}"
    )


def write_data_yaml(out_root: Path):
    yaml_text = f"""# Ultralytics YOLO Pose dataset config
path: {out_root.resolve()}
train: images/train
val: images/val

names:
  0: {CLASS_NAME}

# keypoints: [num_kpts, dims] dims=3 means (x,y,vis)
kpt_shape: [{NUM_KPTS}, 3]
"""
    (out_root / "data.yaml").write_text(yaml_text, encoding="utf-8")
    print(f"[YAML] saved: {out_root / 'data.yaml'}")


def main():
    # output structure
    (OUT_ROOT / "images/train").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "images/val").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "labels/train").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "labels/val").mkdir(parents=True, exist_ok=True)

    # Optional: save some visual checks (bbox + kpts) for sanity.
    # Set to None to disable.
    debug_train = OUT_ROOT / "_debug_vis/train"
    debug_val = OUT_ROOT / "_debug_vis/val"

    process_split(TRAIN_IMG_ROOT, TRAIN_LBL_ROOT, OUT_ROOT / "images/train", OUT_ROOT / "labels/train", debug_vis_dir=debug_train)
    process_split(VAL_IMG_ROOT, VAL_LBL_ROOT, OUT_ROOT / "images/val", OUT_ROOT / "labels/val", debug_vis_dir=debug_val)

    write_data_yaml(OUT_ROOT)
    print("[DONE] dataset ready:", OUT_ROOT.resolve())
    print("[NEXT] Train YOLO pose:")
    print(f"  yolo pose train data={OUT_ROOT/'data.yaml'} model=yolov8n-pose.pt imgsz=640 epochs=100 batch=8")


if __name__ == "__main__":
    main()
