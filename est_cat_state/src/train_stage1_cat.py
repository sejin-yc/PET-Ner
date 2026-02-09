# train_stage1_cat.py
# Stage1 (Linear Probing): video-folder (.mp4 dir) + video-level json (.mp4.json)
# Targets: metadata.inspect.action, metadata.inspect.emotion
# Backbone: convnextv2 / swin (timm).
# NOTE: DINOv2 may NOT be available in timm depending on your version.

import os
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

import numpy as np
from PIL import Image
from tqdm import tqdm

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim

import timm
from sklearn.metrics import accuracy_score, f1_score
from torchvision import transforms


# =========================
# Config
# =========================
@dataclass
class CFG:
    seed: int = 42
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # Your dataset roots
    train_img_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/원천")
    train_lbl_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/라벨")
    val_img_root:   Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/원천")
    val_lbl_root:   Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/라벨")

    # Stage1: linear probing
    freeze_encoder: bool = True

    # Backbone candidates (timm)
    # Use ONE at a time by editing here, OR set in __main__ (but do not override accidentally)
    backbone: str = "swinv2_tiny_window16_256" # "eva02_tiny_patch14_224" # "swin_tiny" # "convnextv2_tiny"    #"swinv2_tiny_window16_256"

    # Train hyperparams
    img_size: int = 224
    batch_size: int = 64
    epochs: int = 5
    lr_head: float = 1e-3
    wd: float = 1e-4
    num_workers: int = 4

    # Output root
    out_root: Path = Path("./runs_stage1")


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# =========================
# Matching: video folder <-> json
#  - video folder name:  xxxxx.mp4   (directory)
#  - json file name:     xxxxx.mp4.json
# =========================
def index_json_by_name(lbl_root: Path) -> Dict[str, Path]:
    idx = {}
    for j in lbl_root.rglob("*.json"):
        idx[j.name] = j  # key: "xxxxx.mp4.json"
    return idx


def list_video_dirs(img_root: Path) -> List[Path]:
    vids = []
    for p in img_root.rglob("*"):
        if p.is_dir() and p.name.lower().endswith(".mp4"):
            vids.append(p)
    return vids


def extract_action_emotion(meta: dict) -> Tuple[str, str]:
    """
    Based on your raw json:
      meta["metadata"]["inspect"]["action"]
      meta["metadata"]["inspect"]["emotion"]
    """
    md = meta.get("metadata", {})
    insp = md.get("inspect", {})
    action = insp.get("action", None)
    emotion = insp.get("emotion", None)
    if action is None or emotion is None:
        raise KeyError("Cannot find metadata.inspect.action or metadata.inspect.emotion")
    return str(action), str(emotion)


def collect_frame_records(img_root: Path, lbl_root: Path) -> List[Tuple[Path, str, str]]:
    """
    Returns:
      records = [(frame_path, action_str, emotion_str), ...]
    Labels are video-level; we replicate them for all frames in the video folder.
    """
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    json_idx = index_json_by_name(lbl_root)
    video_dirs = list_video_dirs(img_root)

    records = []
    miss_json = miss_label = miss_frames = 0

    for vdir in tqdm(video_dirs, desc=f"Scan videos: {img_root.name}"):
        jname = vdir.name + ".json"  # "xxxxx.mp4.json"
        jpath = json_idx.get(jname, None)
        if jpath is None:
            miss_json += 1
            continue

        try:
            with open(jpath, "r", encoding="utf-8") as f:
                meta = json.load(f)
            action, emotion = extract_action_emotion(meta)
        except Exception:
            miss_label += 1
            continue

        frames = [p for p in vdir.rglob("*") if p.suffix.lower() in exts]
        if len(frames) == 0:
            miss_frames += 1
            continue

        for fp in frames:
            records.append((fp, action, emotion))

    if len(records) == 0:
        raise FileNotFoundError(
            f"records=0\n"
            f"- img_root={img_root}\n- lbl_root={lbl_root}\n"
            f"miss_json={miss_json}, miss_label={miss_label}, miss_frames={miss_frames}\n"
            f"Possible causes:\n"
            f"  (1) json naming != foldername+'.json'\n"
            f"  (2) metadata.inspect.action/emotion path differs\n"
        )

    print(f"[INFO] {img_root.name}: records={len(records)} miss_json={miss_json} miss_label={miss_label} miss_frames={miss_frames}")
    return records


def build_vocab(tr_records, va_records):
    actions = sorted(list(set([a for _, a, _ in tr_records + va_records])))
    emotions = sorted(list(set([e for _, _, e in tr_records + va_records])))
    return {c: i for i, c in enumerate(actions)}, {c: i for i, c in enumerate(emotions)}


def encode_records(records, action2id, emo2id):
    items = []
    for fp, a, e in records:
        items.append((fp, action2id[a], emo2id[e]))
    return items


# =========================
# Dataset
# =========================
class FrameDataset(Dataset):
    def __init__(self, items, tfm):
        self.items = items
        self.tfm = tfm

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        fp, a_id, e_id = self.items[idx]
        img = Image.open(fp).convert("RGB")
        img = self.tfm(img)
        return img, torch.tensor(a_id, dtype=torch.long), torch.tensor(e_id, dtype=torch.long)


# =========================
# Model
# =========================
class MultiHead(nn.Module):
    def __init__(self, encoder, feat_dim, n_action, n_emo):
        super().__init__()
        self.encoder = encoder
        self.h_action = nn.Linear(feat_dim, n_action)
        self.h_emotion = nn.Linear(feat_dim, n_emo)

    def forward(self, x):
        feat = self.encoder(x)
        return self.h_action(feat), self.h_emotion(feat)


def create_backbone(cfg: CFG):
    """
    Returns:
      encoder (feature extractor), feat_dim, real_model_name
    """
    name_map = {
        "convnextv2_tiny": "convnextv2_tiny.fcmae",
        "convnextv2_base": "convnextv2_base.fcmae",
        "swin_tiny": "swin_tiny_patch4_window7_224",
        "swin_base": "swin_base_patch4_window7_224",
    }

    mname = name_map.get(cfg.backbone, cfg.backbone)

    # --- DEBUG PRINTS: confirm backbone actually changes ---
    print(f"[BACKBONE] cfg.backbone = {cfg.backbone}")
    print(f"[BACKBONE] timm model_name = {mname}")

    enc = timm.create_model(mname, pretrained=True, num_classes=0, global_pool="avg")
    feat_dim = enc.num_features

    print(f"[BACKBONE] encoder type = {type(enc).__name__}, feat_dim = {feat_dim}")
    return enc, feat_dim, mname


def freeze_module(m: nn.Module):
    for p in m.parameters():
        p.requires_grad = False


# =========================
# Train/Eval
# =========================
@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    act_pred, act_gt = [], []
    emo_pred, emo_gt = [], []

    for x, a, e in loader:
        x = x.to(device)
        out_a, out_e = model(x)
        pa = out_a.argmax(1).cpu().numpy()
        pe = out_e.argmax(1).cpu().numpy()

        act_pred.extend(pa.tolist())
        act_gt.extend(a.numpy().tolist())
        emo_pred.extend(pe.tolist())
        emo_gt.extend(e.numpy().tolist())

    return {
        "act_acc": accuracy_score(act_gt, act_pred),
        "emo_acc": accuracy_score(emo_gt, emo_pred),
        "act_f1": f1_score(act_gt, act_pred, average="macro"),
        "emo_f1": f1_score(emo_gt, emo_pred, average="macro"),
    }


def train(cfg: CFG):
    set_seed(cfg.seed)
    cfg.out_root.mkdir(parents=True, exist_ok=True)

    print("[SCRIPT PATH]", os.path.abspath(__file__))  # make sure you're running the right file

    # ---- Run naming & directory ----
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = (
        f"{ts}_bb-{cfg.backbone}_img{cfg.img_size}_bs{cfg.batch_size}_ep{cfg.epochs}"
        f"_freeze{int(cfg.freeze_encoder)}_seed{cfg.seed}"
    )
    run_dir = cfg.out_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "log.txt"
    best_path = run_dir / "best.pt"
    meta_path = run_dir / "meta.json"

    print(f"[RUN] {run_name}")
    print(f"[RUN] dir: {run_dir}")

    # transforms
    train_tfm = transforms.Compose([
        transforms.Resize((cfg.img_size, cfg.img_size)),
        transforms.RandomHorizontalFlip(0.5),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    val_tfm = transforms.Compose([
        transforms.Resize((cfg.img_size, cfg.img_size)),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])

    # 1) collect records
    tr_records = collect_frame_records(cfg.train_img_root, cfg.train_lbl_root)
    va_records = collect_frame_records(cfg.val_img_root, cfg.val_lbl_root)

    # 2) vocab
    action2id, emo2id = build_vocab(tr_records, va_records)
    print(f"[INFO] classes: action={len(action2id)} emotion={len(emo2id)}")

    # save meta
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "cfg": {k: str(v) if isinstance(v, Path) else v for k, v in cfg.__dict__.items()},
                "action2id": action2id,
                "emo2id": emo2id,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 3) encode
    tr_items = encode_records(tr_records, action2id, emo2id)
    va_items = encode_records(va_records, action2id, emo2id)

    tr_ds = FrameDataset(tr_items, train_tfm)
    va_ds = FrameDataset(va_items, val_tfm)

    tr_loader = DataLoader(
        tr_ds, batch_size=cfg.batch_size, shuffle=True,
        num_workers=cfg.num_workers, pin_memory=True
    )
    va_loader = DataLoader(
        va_ds, batch_size=cfg.batch_size, shuffle=False,
        num_workers=cfg.num_workers, pin_memory=True
    )

    # 4) model
    encoder, feat_dim, real_name = create_backbone(cfg)
    if cfg.freeze_encoder:
        freeze_module(encoder)

    model = MultiHead(encoder, feat_dim, len(action2id), len(emo2id)).to(cfg.device)

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.AdamW(params, lr=cfg.lr_head, weight_decay=cfg.wd)
    ce = nn.CrossEntropyLoss()

    best = -1.0

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        pbar = tqdm(tr_loader, desc=f"[{cfg.backbone}] epoch {epoch}/{cfg.epochs}")

        for x, a, e in pbar:
            x = x.to(cfg.device)
            a = a.to(cfg.device)
            e = e.to(cfg.device)

            out_a, out_e = model(x)
            loss = ce(out_a, a) + ce(out_e, e)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            pbar.set_postfix(loss=float(loss.item()))

        metrics = evaluate(model, va_loader, cfg.device)
        score = (metrics["act_f1"] + metrics["emo_f1"]) / 2.0

        line = (
            f"epoch={epoch} backbone={real_name} "
            f"act_f1={metrics['act_f1']:.4f} emo_f1={metrics['emo_f1']:.4f} "
            f"act_acc={metrics['act_acc']:.4f} emo_acc={metrics['emo_acc']:.4f} score={score:.4f}"
        )
        print(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        if score > best:
            best = score
            torch.save(
                {
                    "model": model.state_dict(),
                    "action2id": action2id,
                    "emo2id": emo2id,
                    "cfg": cfg.__dict__,
                    "backbone_real_name": real_name,
                },
                best_path,
            )

    print(f"[DONE] best_score={best:.4f} saved: {best_path}")


if __name__ == "__main__":
    # IMPORTANT:
    # Do NOT override backbone here unless you really want to.
    # If you want to test different backbones, change CFG.backbone above,
    # or set it here explicitly ONCE and confirm the [BACKBONE] print changes.
    cfg = CFG(
        # backbone="convnextv2_tiny",  # <- 주석 풀면 여기 값이 CFG 기본값을 덮어씀
        epochs=5,
        batch_size=64,
        img_size=224,
        freeze_encoder=True,
    )
    train(cfg)
