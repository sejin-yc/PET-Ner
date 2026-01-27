import os
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from dataset import CatStateDataset
from model import MultiHeadClassifier

HEADS = ["action", "painDisease", "abnormalAction", "emotion"]

def set_seed(seed=42):
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def build_label_maps(train_csv: str, out_dir: str):
    df = pd.read_csv(train_csv)
    label_maps = {}
    inv_maps = {}

    for h in HEADS:
        classes = sorted(df[h].astype(str).unique().tolist())
        label_maps[h] = {c:i for i,c in enumerate(classes)}
        inv_maps[h] = {i:c for c,i in label_maps[h].items()}

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(out_dir)/"label_maps.json", "w", encoding="utf-8") as f:
        json.dump({"label_maps": label_maps, "inv_maps": inv_maps}, f, ensure_ascii=False, indent=2)

    num_classes = {h: len(label_maps[h]) for h in HEADS}
    return label_maps, inv_maps, num_classes

def compute_class_weights(train_csv: str, label_maps: dict):
    df = pd.read_csv(train_csv)
    weights = {}

    for h in HEADS:
        y = df[h].astype(str).map(label_maps[h]).astype(int).to_numpy()
        counts = np.bincount(y, minlength=len(label_maps[h])).astype(np.float32)
        # inverse freq (stable)
        w = counts.sum() / np.clip(counts, 1.0, None)
        w = w / w.mean()
        weights[h] = torch.tensor(w, dtype=torch.float32)
    return weights

@torch.no_grad()
def evaluate(model, loader, device, criterions):
    model.eval()
    total_loss = 0.0
    total = 0
    correct = {h: 0 for h in HEADS}

    for x, y in loader:
        x = x.to(device)
        logits = model(x)

        loss = 0.0
        bs = x.size(0)
        for h in HEADS:
            target = y[h].to(device).long()
            loss = loss + criterions[h](logits[h], target)

            pred = logits[h].argmax(dim=1)
            correct[h] += (pred == target).sum().item()

        total_loss += loss.item() * bs
        total += bs

    metrics = {f"acc_{h}": correct[h] / max(total, 1) for h in HEADS}
    return total_loss / max(total, 1), metrics

def main(
    train_csv="data/train.csv",
    val_csv="data/val.csv",
    out_dir="outputs/run1",
    backbone="tf_efficientnet_b0",
    img_size=224,
    batch_size=64,
    lr=3e-4,
    epochs=10,
    num_workers=4,
    use_bbox_crop=True,
    sampler_mode="emotion",   # ✅ 추가 (emotion/action/both)
    seed=42,
):
    set_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    label_maps, inv_maps, num_classes = build_label_maps(train_csv, out_dir)
    class_w = compute_class_weights(train_csv, label_maps)

    # Dataset / Loader
    train_ds = CatStateDataset(train_csv, label_maps, img_size=img_size, train=True, use_bbox_crop=use_bbox_crop)
    val_ds   = CatStateDataset(val_csv,   label_maps, img_size=img_size, train=False, use_bbox_crop=use_bbox_crop)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True)
    val_loader   = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)

    # Model
    model = MultiHeadClassifier(backbone, num_classes, pretrained=True, dropout=0.2).to(device)

    # Loss (class weights 적용: 특히 emotion 불균형에 도움)
    criterions = {}
    for h in HEADS:
        w = class_w[h].to(device)
        criterions[h] = nn.CrossEntropyLoss(weight=w)

    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler('cuda', enabled=(device=="cuda"))


    best = -1.0
    for ep in range(1, epochs+1):
        model.train()
        pbar = tqdm(train_loader, desc=f"Epoch {ep}/{epochs}")
        running = 0.0
        n = 0

        for x, y in pbar:
            x = x.to(device)
            targets = {h: y[h].to(device).long() for h in HEADS}

            opt.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=(device=="cuda")):
                logits = model(x)
                loss = 0.0
                for h in HEADS:
                    loss = loss + criterions[h](logits[h], targets[h])

            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()

            bs = x.size(0)
            running += loss.item() * bs
            n += bs
            pbar.set_postfix(loss=running/max(n,1))

        val_loss, metrics = evaluate(model, val_loader, device, criterions)

        # 평균 정확도(간단 기준)
        mean_acc = float(np.mean([metrics[f"acc_{h}"] for h in HEADS]))
        log = {"epoch": ep, "train_loss": running/max(n,1), "val_loss": val_loss, "mean_acc": mean_acc, **metrics}
        print(log)

        with open(Path(out_dir)/"log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")

        # 매 epoch 마지막 상태 저장 (안전장치)
        last_ckpt = {
            "model": model.state_dict(),
            "backbone": backbone,
            "num_classes": num_classes,
            "label_maps": label_maps,
            "epoch": ep,
        }
        torch.save(last_ckpt, Path(out_dir)/"last.pt")

        # best 갱신 시 best 저장
        if mean_acc > best:
            best = mean_acc
            torch.save(last_ckpt, Path(out_dir)/"best.pt")
            print(f"✅ saved best: mean_acc={best:.4f}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train_csv", default="data/train.csv")
    ap.add_argument("--val_csv", default="data/val.csv")
    ap.add_argument("--out_dir", default="outputs/run1")
    ap.add_argument("--backbone", default="tf_efficientnet_b0")
    ap.add_argument("--img_size", type=int, default=224)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--num_workers", type=int, default=4)
    ap.add_argument("--use_bbox_crop", action="store_true")
    ap.add_argument("--sampler_mode", default="emotion")  # emotion/action/both
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    main(**vars(args))
