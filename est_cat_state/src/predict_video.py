import argparse
from pathlib import Path
import json
import cv2
import numpy as np
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2
import pandas as pd
from tqdm import tqdm

from model import MultiHeadClassifier

HEADS = ["action", "emotion"]

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

@torch.no_grad()
def infer_one(model, inv_maps, tfm, frame_rgb, device):
    x = tfm(image=frame_rgb)["image"].unsqueeze(0).to(device)
    logits = model(x)
    out = {}
    for h in HEADS:
        prob = torch.softmax(logits[h], dim=1)[0].detach().cpu().numpy()
        pred_id = int(prob.argmax())
        out[h] = (inv_maps[h][pred_id], float(prob[pred_id]), prob)  # label, conf, full prob
    return out

def aggregate_majority(pred_labels):
    # pred_labels: list[str]
    if not pred_labels:
        return "", 0
    vals, counts = np.unique(pred_labels, return_counts=True)
    i = int(counts.argmax())
    return str(vals[i]), int(counts[i])

def aggregate_probavg(prob_list):
    # prob_list: list[np.ndarray], each shape (C,)
    if not prob_list:
        return "", 0.0
    p = np.mean(np.stack(prob_list, axis=0), axis=0)
    pred_id = int(p.argmax())
    return pred_id, float(p[pred_id])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out_dir", default="outputs/video_infer")
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--sample_fps", type=float, default=2.0, help="process N frames per second")
    ap.add_argument("--save_overlay", action="store_true", help="save annotated video (slower)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_maps = load_ckpt(args.ckpt, device)
    tfm = build_tfm(args.img_size)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / args.sample_fps)))  # sample every 'step' frames

    # overlay writer (optional)
    writer = None
    if args.save_overlay:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_video = str(out_dir / "overlay.mp4")
        writer = cv2.VideoWriter(out_video, fourcc, src_fps, (w, h))

    rows = []
    all_preds = {h: [] for h in HEADS}
    all_probs = {h: [] for h in HEADS}  # store full prob vectors for avg

    frame_idx = -1
    pbar = tqdm(total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0), desc="Video")
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frame_idx += 1
        pbar.update(1)

        # always write overlay frame if enabled, but predictions only on sampled frames
        do_infer = (frame_idx % step == 0)

        text = ""
        if do_infer:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            out = infer_one(model, inv_maps, tfm, frame_rgb, device)

            row = {"frame_idx": frame_idx, "time_sec": frame_idx / src_fps}
            for h in HEADS:
                label, conf, probvec = out[h]
                row[h] = label
                row[f"{h}_conf"] = conf
                all_preds[h].append(label)
                all_probs[h].append(probvec)
            rows.append(row)

            text = f"action={row['action']} ({row['action_conf']:.2f})  emotion={row['emotion']} ({row['emotion_conf']:.2f})"

        if writer is not None:
            draw = frame_bgr.copy()
            if text:
                cv2.putText(draw, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
            writer.write(draw)

    pbar.close()
    cap.release()
    if writer is not None:
        writer.release()

    # save per-frame csv
    df = pd.DataFrame(rows)
    csv_path = out_dir / "frame_preds.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # aggregate (majority + prob-avg)
    summary = {}
    for h in HEADS:
        maj_label, maj_count = aggregate_majority(all_preds[h])
        pred_id, pred_prob = aggregate_probavg(all_probs[h]) if all_probs[h] else ("", 0.0)
        # pred_id -> label for prob avg
        if all_probs[h]:
            avg_label = inv_maps[h][int(pred_id)]
        else:
            avg_label = ""
        summary[h] = {
            "majority_label": maj_label,
            "majority_count": maj_count,
            "probavg_label": avg_label,
            "probavg_conf": pred_prob,
            "n_samples": len(all_preds[h]),
        }

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", csv_path)
    print("Saved:", out_dir / "summary.json")
    if args.save_overlay:
        print("Saved:", out_dir / "overlay.mp4")

if __name__ == "__main__":
    main()
