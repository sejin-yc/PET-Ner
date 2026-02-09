# train_stage2_cat.py
# Stage2: Partial fine-tuning (unfreeze last stage(s) of backbone)
# Targets: metadata.inspect.action, metadata.inspect.emotion
# Data: video-folder (.mp4 dir) + video-level json (.mp4.json), labels replicated to frames

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

    train_img_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/원천")
    train_lbl_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Training/CAT/라벨")
    val_img_root:   Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/원천")
    val_lbl_root:   Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/라벨")

    # Winner backbone from Stage1
    backbone: str = "swin_tiny_patch4_window7_224"

    # Stage2: partial unfreeze
    # For Swin: unfreeze last stage(s) among encoder.layers
    unfreeze_stages: int = 1  # 1 or 2 추천
    train_norm: bool = True   # 마지막 norm도 학습

    # Train hyperparams
    epochs: int = 8
    batch_size: int = 64
    num_workers: int = 4

    # Discriminative LR
    lr_head: float = 1e-3
    lr_backbone: float = 2e-5
    wd: float = 1e-4

    # Scheduler (optional, cosine)
    use_cosine: bool = True
    warmup_epochs: int = 1
    min_lr: float = 1e-6

    # Output root
    out_root: Path = Path("./runs_stage2")


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# =========================
# Data matching
# =========================
def index_json_by_name(lbl_root: Path) -> Dict[str, Path]:
    idx = {}
    for j in lbl_root.rglob("*.json"):
        idx[j.name] = j
    return idx


def list_video_dirs(img_root: Path) -> List[Path]:
    vids = []
    for p in img_root.rglob("*"):
        if p.is_dir() and p.name.lower().endswith(".mp4"):
            vids.append(p)
    return vids


def extract_action_emotion(meta: dict) -> Tuple[str, str]:
    md = meta.get("metadata", {})
    insp = md.get("inspect", {})
    action = insp.get("action", None)
    emotion = insp.get("emotion", None)
    if action is None or emotion is None:
        raise KeyError("Cannot find metadata.inspect.action or metadata.inspect.emotion")
    return str(action), str(emotion)


def collect_frame_records(img_root: Path, lbl_root: Path) -> List[Tuple[Path, str, str]]:
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
            f"records=0\nimg_root={img_root}\nlbl_root={lbl_root}\n"
            f"miss_json={miss_json}, miss_label={miss_label}, miss_frames={miss_frames}"
        )

    print(f"[INFO] {img_root.name}: records={len(records)} miss_json={miss_json} miss_label={miss_label} miss_frames={miss_frames}")
    return records


def build_vocab(tr_records, va_records):
    actions = sorted(list(set([a for _, a, _ in tr_records + va_records])))
    emotions = sorted(list(set([e for _, _, e in tr_records + va_records])))
    return {c: i for i, c in enumerate(actions)}, {c: i for i, c in enumerate(emotions)}


def encode_records(records, action2id, emo2id):
    return [(fp, action2id[a], emo2id[e]) for fp, a, e in records]


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
    # allow passing exact timm names (you already use exact swin name)
    mname = cfg.backbone

    print(f"[BACKBONE] cfg.backbone = {cfg.backbone}")
    print(f"[BACKBONE] timm model_name = {mname}")

    enc = timm.create_model(mname, pretrained=True, num_classes=0, global_pool="avg")
    feat_dim = enc.num_features

    # infer required input size
    model_img = None
    if hasattr(enc, "img_size"):
        isz = enc.img_size
        model_img = int(isz[0]) if isinstance(isz, (tuple, list)) else int(isz)
    if model_img is None and hasattr(enc, "default_cfg"):
        dc = enc.default_cfg or {}
        isz = dc.get("input_size", None)  # (3,H,W)
        if isz and len(isz) == 3:
            model_img = int(isz[1])
    if model_img is None:
        model_img = 224

    print(f"[BACKBONE] encoder type = {type(enc).__name__}, feat_dim = {feat_dim}, input={model_img}")
    return enc, feat_dim, mname, model_img


def freeze_all(m: nn.Module):
    for p in m.parameters():
        p.requires_grad = False


def unfreeze_swin_last_stages(enc: nn.Module, n_stages: int = 1, train_norm: bool = True):
    """
    For timm SwinTransformer/SwinTransformerV2:
      enc.layers is a ModuleList of stages
    We'll unfreeze last n stages + (optional) final norm layer.
    """
    freeze_all(enc)

    if not hasattr(enc, "layers"):
        raise ValueError("Encoder has no .layers. This helper is intended for Swin-like models in timm.")

    layers = enc.layers
    n = max(1, int(n_stages))
    n = min(n, len(layers))

    for i in range(len(layers) - n, len(layers)):
        for p in layers[i].parameters():
            p.requires_grad = True

    if train_norm and hasattr(enc, "norm"):
        for p in enc.norm.parameters():
            p.requires_grad = True


def make_param_groups(model: MultiHead, lr_head: float, lr_backbone: float, wd: float):
    # backbone params: encoder parameters that are trainable
    backbone_params = [p for p in model.encoder.parameters() if p.requires_grad]
    head_params = [p for p in list(model.h_action.parameters()) + list(model.h_emotion.parameters()) if p.requires_grad]

    groups = []
    if backbone_params:
        groups.append({"params": backbone_params, "lr": lr_backbone, "weight_decay": wd})
    groups.append({"params": head_params, "lr": lr_head, "weight_decay": wd})
    return groups


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

        act_pred.extend(pa.tolist()); act_gt.extend(a.numpy().tolist())
        emo_pred.extend(pe.tolist()); emo_gt.extend(e.numpy().tolist())

    return {
        "act_acc": accuracy_score(act_gt, act_pred),
        "emo_acc": accuracy_score(emo_gt, emo_pred),
        "act_f1": f1_score(act_gt, act_pred, average="macro"),
        "emo_f1": f1_score(emo_gt, emo_pred, average="macro"),
    }


def build_scheduler(cfg: CFG, optimizer):
    if not cfg.use_cosine:
        return None

    # simple cosine with warmup (epoch-level)
    def lr_lambda(epoch):
        if epoch < cfg.warmup_epochs:
            return float(epoch + 1) / float(max(1, cfg.warmup_epochs))
        # cosine decay from 1.0 to min_lr ratio
        t = (epoch - cfg.warmup_epochs) / float(max(1, cfg.epochs - cfg.warmup_epochs))
        cosine = 0.5 * (1.0 + np.cos(np.pi * t))
        # map to [min_lr_ratio, 1]
        # NOTE: this scales base LR for each param group
        min_ratio = cfg.min_lr / max(cfg.lr_head, 1e-12)  # roughly for head base, acceptable
        return min_ratio + (1.0 - min_ratio) * cosine

    return optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)


def train(cfg: CFG):
    set_seed(cfg.seed)
    cfg.out_root.mkdir(parents=True, exist_ok=True)

    print("[SCRIPT PATH]", os.path.abspath(__file__))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = (
        f"{ts}_bb-{cfg.backbone}_stage2_unfreeze{cfg.unfreeze_stages}"
        f"_lrB{cfg.lr_backbone}_lrH{cfg.lr_head}_bs{cfg.batch_size}_ep{cfg.epochs}_seed{cfg.seed}"
    )
    run_dir = cfg.out_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "log.txt"
    best_path = run_dir / "best.pt"
    meta_path = run_dir / "meta.json"

    print(f"[RUN] {run_name}")
    print(f"[RUN] dir: {run_dir}")

    # data scan
    tr_records = collect_frame_records(cfg.train_img_root, cfg.train_lbl_root)
    va_records = collect_frame_records(cfg.val_img_root, cfg.val_lbl_root)
    action2id, emo2id = build_vocab(tr_records, va_records)
    print(f"[INFO] classes: action={len(action2id)} emotion={len(emo2id)}")

    # backbone first (to get input size)
    encoder, feat_dim, real_name, model_img = create_backbone(cfg)

    # transforms (match model input size)
    train_tfm = transforms.Compose([
        transforms.Resize((model_img, model_img)),
        transforms.RandomHorizontalFlip(0.5),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    val_tfm = transforms.Compose([
        transforms.Resize((model_img, model_img)),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])

    tr_items = encode_records(tr_records, action2id, emo2id)
    va_items = encode_records(va_records, action2id, emo2id)

    tr_ds = FrameDataset(tr_items, train_tfm)
    va_ds = FrameDataset(va_items, val_tfm)

    tr_loader = DataLoader(tr_ds, batch_size=cfg.batch_size, shuffle=True,
                           num_workers=cfg.num_workers, pin_memory=True)
    va_loader = DataLoader(va_ds, batch_size=cfg.batch_size, shuffle=False,
                           num_workers=cfg.num_workers, pin_memory=True)

    # Stage2 unfreeze policy (for Swin)
    unfreeze_swin_last_stages(encoder, n_stages=cfg.unfreeze_stages, train_norm=cfg.train_norm)

    model = MultiHead(encoder, feat_dim, len(action2id), len(emo2id)).to(cfg.device)

    # optimizer with discriminative LR
    param_groups = make_param_groups(model, cfg.lr_head, cfg.lr_backbone, cfg.wd)
    optimizer = optim.AdamW(param_groups)
    scheduler = build_scheduler(cfg, optimizer)

    ce = nn.CrossEntropyLoss()
    best = -1.0

    # save meta
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_name": run_name,
                "cfg": {k: str(v) if isinstance(v, Path) else v for k, v in cfg.__dict__.items()},
                "action2id": action2id,
                "emo2id": emo2id,
                "backbone_real_name": real_name,
                "model_img": model_img,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        pbar = tqdm(tr_loader, desc=f"[Stage2 {cfg.backbone}] epoch {epoch}/{cfg.epochs}")

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

        if scheduler is not None:
            scheduler.step()

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
                    "model_img": model_img,
                    "unfreeze_stages": cfg.unfreeze_stages,
                },
                best_path,
            )

    print(f"[DONE] best_score={best:.4f} saved: {best_path}")


if __name__ == "__main__":
    cfg = CFG(
        backbone="swin_tiny_patch4_window7_224",
        unfreeze_stages=2,      # 먼저 1로
        lr_backbone=2e-5,       # backbone은 작게
        lr_head=1e-3,           # head는 크게
        epochs=15,
        batch_size=64,
        use_cosine=True,
        warmup_epochs=1,
    )
    train(cfg)
