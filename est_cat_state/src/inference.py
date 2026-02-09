import json
from pathlib import Path
import argparse
import pandas as pd
import cv2
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2
from tqdm import tqdm

from model import MultiHeadClassifier

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ✅ 예측할 head 목록 (2개로 고정)
HEADS = ["action", "emotion"]

def build_tfm(img_size: int):
    return A.Compose([
        A.LongestMaxSize(max_size=img_size),
        A.PadIfNeeded(min_height=img_size, min_width=img_size, border_mode=cv2.BORDER_CONSTANT),
        A.Normalize(),
        ToTensorV2(),
    ])

def load_image(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(str(path))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img

@torch.no_grad()
def main(
    ckpt_path: str,
    input_path: str,
    out_csv: str = "outputs/preds_action_emotion.csv",
    img_size: int = 224,
    use_bbox_crop: bool = False,  # inference에서 bbox crop 옵션은 일단 꺼둠
):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    ckpt = torch.load(ckpt_path, map_location="cpu")
    label_maps = ckpt["label_maps"]
    num_classes = ckpt["num_classes"]
    backbone = ckpt["backbone"]

    # ✅ head별 id -> 라벨 문자열
    inv_maps = {h: {v: k for k, v in label_maps[h].items()} for h in HEADS}

    model = MultiHeadClassifier(backbone, num_classes, pretrained=False).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    tfm = build_tfm(img_size)

    in_path = Path(input_path)
    if in_path.is_dir():
        images = []
        for ext in IMG_EXTS:
            images.extend(sorted(in_path.rglob(f"*{ext}")))
    else:
        images = [in_path]

    rows = []
    for p in tqdm(images, desc="Infer"):
        img = load_image(p)
        x = tfm(image=img)["image"].unsqueeze(0).to(device)

        logits = model(x)  # dict

        row = {"image_path": str(p)}
        for h in HEADS:
            prob = torch.softmax(logits[h], dim=1)[0].detach().cpu()
            pred_id = int(prob.argmax().item())
            row[h] = inv_maps[h][pred_id]
            row[f"{h}_prob"] = float(prob[pred_id].item())
        rows.append(row)

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("Saved:", out_csv)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--input", required=True, help="image file or folder")
    ap.add_argument("--out_csv", default="outputs/preds_action_emotion.csv")
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--use_bbox_crop", action="store_true")
    args = ap.parse_args()

    main(
        ckpt_path=args.ckpt,
        input_path=args.input,
        out_csv=args.out_csv,
        img_size=args.img_size,
        use_bbox_crop=args.use_bbox_crop,
    )
