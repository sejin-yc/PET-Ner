import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm
from sklearn.metrics import f1_score, confusion_matrix, classification_report
from pathlib import Path

from dataset import CatStateDataset
from model import MultiHeadClassifier

# ✅ 우리가 평가/예측할 head 목록 (2개로 고정)
HEADS = ["action", "emotion"]

@torch.no_grad()
def main(
    ckpt_path="outputs/run2_long_both/best.pt",
    val_csv="data/val.csv",
    batch_size=128,
    img_size=224,
    num_workers=4,
    use_bbox_crop=True
):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    ckpt = torch.load(ckpt_path, map_location="cpu")
    label_maps = ckpt["label_maps"]       # {"action": {...}, "emotion": {...}}
    num_classes = ckpt["num_classes"]     # {"action": N, "emotion": M}
    backbone = ckpt["backbone"]           # 예: "tf_efficientnet_b2"

    # ✅ 정수 -> 문자열 라벨 변환용
    inv_maps = {h: {v: k for k, v in label_maps[h].items()} for h in HEADS}

    # Dataset / Loader
    ds = CatStateDataset(val_csv, label_maps, img_size=img_size, train=False, use_bbox_crop=use_bbox_crop)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)

    # Model
    model = MultiHeadClassifier(backbone, num_classes, pretrained=False).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    y_true = {h: [] for h in HEADS}
    y_pred = {h: [] for h in HEADS}

    for x, y in tqdm(dl, desc="Eval"):
        x = x.to(device)
        logits = model(x)  # dict: {"action": [B,C], "emotion": [B,C]}

        for h in HEADS:
            t = y[h].numpy().tolist()
            p = logits[h].argmax(1).detach().cpu().numpy().tolist()
            y_true[h].extend(t)
            y_pred[h].extend(p)

    out_dir = Path(ckpt_path).parent

    for h in HEADS:
        yt = np.array(y_true[h])
        yp = np.array(y_pred[h])

        acc = float((yt == yp).mean())
        f1_macro = float(f1_score(yt, yp, average="macro"))
        f1_weighted = float(f1_score(yt, yp, average="weighted"))

        print(f"\n[{h}] acc={acc:.4f}  f1_macro={f1_macro:.4f}  f1_weighted={f1_weighted:.4f}")

        # confusion matrix 저장
        cm = confusion_matrix(yt, yp, labels=list(range(num_classes[h])))
        np.save(out_dir / f"cm_{h}.npy", cm)

        # classification report 저장
        target_names = [inv_maps[h][i] for i in range(num_classes[h])]
        report = classification_report(yt, yp, target_names=target_names, zero_division=0)
        (out_dir / f"report_{h}.txt").write_text(report, encoding="utf-8")

    print("\nSaved reports to:", out_dir)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="outputs/run2_long_both/best.pt")
    ap.add_argument("--val_csv", default="data/val.csv")
    ap.add_argument("--batch_size", type=int, default=128)
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--num_workers", type=int, default=4)
    ap.add_argument("--use_bbox_crop", action="store_true")
    args = ap.parse_args()

    main(
        ckpt_path=args.ckpt,
        val_csv=args.val_csv,
        batch_size=args.batch_size,
        img_size=args.img_size,
        num_workers=args.num_workers,
        use_bbox_crop=args.use_bbox_crop,
    )
