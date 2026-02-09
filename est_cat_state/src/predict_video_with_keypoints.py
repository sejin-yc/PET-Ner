import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2
from tqdm import tqdm

from model import MultiHeadClassifier

HEADS = ["action", "emotion"]

# ====== label english mapping (optional) ======
EMOTION_EN = {
    "편안/안정": "Calm",
    "행복/즐거움": "Happy",
    "화남/불쾌": "Angry",
    "공격성": "Aggressive",
    "불안/슬픔": "Anxious/Sad",
    "공포": "Fear",
}

# action은 많을 가능성이 높아서 기본은 그대로 두고, 원하면 추가 가능
ACTION_EN = {
    # "허리를 아치로 세움": "Arching back",
}

def build_tfm(img_size: int):
    return A.Compose([
        A.LongestMaxSize(max_size=img_size),
        A.PadIfNeeded(min_height=img_size, min_width=img_size, border_mode=cv2.BORDER_CONSTANT),
        A.Normalize(),
        ToTensorV2(),
    ])

def load_ckpt(ckpt_path: str, device: str):
    ckpt = torch.load(ckpt_path, map_location="cpu")
    label_maps = ckpt["label_maps"]
    num_classes = ckpt["num_classes"]
    backbone = ckpt["backbone"]

    inv_maps = {h: {v: k for k, v in label_maps[h].items()} for h in HEADS}

    model = MultiHeadClassifier(backbone, num_classes, pretrained=False).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, inv_maps

def load_label_json(label_json_path: str):
    data = json.loads(Path(label_json_path).read_text(encoding="utf-8"))

    # frame_number -> annotation dict
    ann_map = {}
    for ann in data.get("annotations", []):
        fn = int(ann.get("frame_number", -1))
        if fn >= 0:
            ann_map[fn] = ann
    return ann_map

def draw_keypoints(frame_bgr, ann, radius=4, draw_bbox=False):
    """Draw points from ann['keypoints'] on image"""
    if ann is None:
        return frame_bgr

    img = frame_bgr

    # bbox
    if draw_bbox and "bounding_box" in ann and ann["bounding_box"] is not None:
        bb = ann["bounding_box"]
        x, y, w, h = int(bb["x"]), int(bb["y"]), int(bb["width"]), int(bb["height"])
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

    # keypoints
    kps = ann.get("keypoints", {})
    for k, v in kps.items():
        if v is None:
            continue
        x, y = int(v["x"]), int(v["y"])
        cv2.circle(img, (x, y), radius, (0, 0, 255), -1)  # red dot

        # point index text
        cv2.putText(img, str(k), (x+4, y-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return img

@torch.no_grad()
def infer_frame(model, inv_maps, tfm, frame_rgb, device):
    x = tfm(image=frame_rgb)["image"].unsqueeze(0).to(device)
    logits = model(x)

    out = {}
    for h in HEADS:
        prob = torch.softmax(logits[h], dim=1)[0].detach().cpu().numpy()
        pred_id = int(prob.argmax())
        label = inv_maps[h][pred_id]
        conf = float(prob[pred_id])
        out[h] = (label, conf)
    return out

def to_english(head, label):
    if head == "emotion":
        return EMOTION_EN.get(label, label)
    if head == "action":
        return ACTION_EN.get(label, label)
    return label

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--label_json", required=True)
    ap.add_argument("--out_video", default="outputs/overlay_keypoints.mp4")
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--sample_fps", type=float, default=2.0)
    ap.add_argument("--draw_bbox", action="store_true")
    ap.add_argument("--english", action="store_true", help="show labels in english if mapping exists")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_maps = load_ckpt(args.ckpt, device)
    tfm = build_tfm(args.img_size)

    ann_map = load_label_json(args.label_json)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(round(src_fps / args.sample_fps)))

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = Path(args.out_video)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), fourcc, src_fps, (w, h))

    last_pred = {"action": ("", 0.0), "emotion": ("", 0.0)}

    pbar = tqdm(total=total, desc="Predict+Overlay")
    frame_idx = -1

    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frame_idx += 1
        pbar.update(1)

        # 1) keypoints overlay using label json
        ann = ann_map.get(frame_idx, None)
        frame_bgr = draw_keypoints(frame_bgr, ann, radius=4, draw_bbox=args.draw_bbox)

        # 2) inference only on sampled frames (speed)
        if frame_idx % step == 0:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pred = infer_frame(model, inv_maps, tfm, frame_rgb, device)
            last_pred["action"] = pred["action"]
            last_pred["emotion"] = pred["emotion"]

        # 3) text overlay
        a_label, a_conf = last_pred["action"]
        e_label, e_conf = last_pred["emotion"]

        if args.english:
            a_label = to_english("action", a_label)
            e_label = to_english("emotion", e_label)

        text1 = f"ACTION: {a_label} ({a_conf:.2f})"
        text2 = f"EMOTION: {e_label} ({e_conf:.2f})"
        cv2.putText(frame_bgr, text1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2, cv2.LINE_AA)
        cv2.putText(frame_bgr, text2, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2, cv2.LINE_AA)

        writer.write(frame_bgr)

    pbar.close()
    cap.release()
    writer.release()
    print("Saved:", out_path)

if __name__ == "__main__":
    main()
