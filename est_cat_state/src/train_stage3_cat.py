# train_stage3_video_pool.py
# Stage3: Video-level training with multi-frame sampling + pooling
# - One sample = one video folder (xxxx.mp4 dir)
# - Sample K frames from folder, encode each, pool (mean), classify
# Targets: metadata.inspect.action, metadata.inspect.emotion

import os
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
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

    backbone: str = "swin_tiny_patch4_window7_224"

    # Stage3: sample K frames per video, pool
    frames_per_video: int = 8
    pool: str = "mean"  # "mean" only for now

    # Fine-tuning policy (keep Stage2 best practice)
    unfreeze_stages: int = 2
    train_norm: bool = True

    # Train
    epochs: int = 12
    batch_size: int = 16  # video batch (each sample has K frames) -> GPU 부담 커서 8~16 추천
    num_workers: int = 4

    lr_head: float = 1e-3
    lr_backbone: float = 2e-5
    wd: float = 1e-4

    use_cosine: bool = True
    warmup_epochs: int = 1
    min_lr: float = 1e-6

    # Optional: start from Stage2 checkpoint
    # 예: "runs_stage2/.../best.pt"
    init_ckpt: Optional[str] = None

    out_root: Path = Path("./runs_stage3")


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# =========================
# Utils: folder/json matching
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


def collect_video_items(img_root: Path, lbl_root: Path) -> List[Tuple[Path, str, str]]:
    """
    Returns video-level items:
      items = [(video_dir, action_str, emotion_str), ...]
    """
    json_idx = index_json_by_name(lbl_root)
    video_dirs = list_video_dirs(img_root)

    items = []
    miss_json = miss_label = miss_frames = 0

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    for vdir in tqdm(video_dirs, desc=f"Scan videos: {img_root.name}"):
        jname = vdir.name + ".json"   # xxxxx.mp4.json
        jpath = json_idx.get(jname)
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

        items.append((vdir, action, emotion))

    if len(items) == 0:
        raise FileNotFoundError(
            f"items=0\nimg_root={img_root}\nlbl_root={lbl_root}\n"
            f"miss_json={miss_json}, miss_label={miss_label}, miss_frames={miss_frames}"
        )

    print(f"[INFO] {img_root.name}: videos={len(items)} miss_json={miss_json} miss_label={miss_label} miss_frames={miss_frames}")
    return items


def build_vocab(tr_items, va_items):
    actions = sorted(list(set([a for _, a, _ in tr_items + va_items])))
    emotions = sorted(list(set([e for _, _, e in tr_items + va_items])))
    return {c: i for i, c in enumerate(actions)}, {c: i for i, c in enumerate(emotions)}


def encode_items(items, action2id, emo2id):
    return [(vdir, action2id[a], emo2id[e]) for vdir, a, e in items]


# =========================
# Dataset (Video)
# =========================
class VideoFolderDataset(Dataset):
    """
    One item = one video folder.
    It samples K frames randomly each time __getitem__ is called.
    """
    def __init__(self, items, tfm, frames_per_video: int = 8):
        self.items = items
        self.tfm = tfm
        self.k = frames_per_video
        self.exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __len__(self):
        return len(self.items)

    def _sample_frames(self, vdir: Path) -> List[Path]:
        frames = [p for p in vdir.rglob("*") if p.suffix.lower() in self.exts]
        if len(frames) == 0:
            return []
        if len(frames) >= self.k:
            return random.sample(frames, self.k)
        # 부족하면 반복 샘플링
        out = frames.copy()
        while len(out) < self.k:
            out.append(random.choice(frames))
        return out

    def __getitem__(self, idx):
        vdir, a_id, e_id = self.items[idx]
        fps = self._sample_frames(vdir)
        if len(fps) == 0:
            # 거의 없겠지만 안전하게
            raise RuntimeError(f"No frames in {vdir}")

        imgs = []
        for fp in fps:
            img = Image.open(fp).convert("RGB")
            img = self.tfm(img)
            imgs.append(img)

        # (K, C, H, W)
        x = torch.stack(imgs, dim=0)
        return x, torch.tensor(a_id, dtype=torch.long), torch.tensor(e_id, dtype=torch.long)


# =========================
# Model
# =========================
class VideoPoolMultiHead(nn.Module):
    def __init__(self, encoder, feat_dim, n_action, n_emo, pool: str = "mean"):
        super().__init__()
        self.encoder = encoder
        self.pool = pool
        self.h_action = nn.Linear(feat_dim, n_action)
        self.h_emotion = nn.Linear(feat_dim, n_emo)

    def forward(self, x):
        """
        x: (B, K, C, H, W)
        """
        B, K, C, H, W = x.shape
        x = x.view(B * K, C, H, W)
        feat = self.encoder(x)              # (B*K, D)
        feat = feat.view(B, K, -1)          # (B, K, D)

        if self.pool == "mean":
            vid_feat = feat.mean(dim=1)     # (B, D)
        else:
            raise ValueError(f"Unknown pool={self.pool}")

        return self.h_action(vid_feat), self.h_emotion(vid_feat)


def create_backbone(backbone_name: str):
    print(f"[BACKBONE] timm model_name = {backbone_name}")
    enc = timm.create_model(backbone_name, pretrained=True, num_classes=0, global_pool="avg")
    feat_dim = enc.num_features

    # infer input size
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

    print(f"[BACKBONE] encoder type={type(enc).__name__}, feat_dim={feat_dim}, input={model_img}")
    return enc, feat_dim, model_img


def freeze_all(m: nn.Module):
    for p in m.parameters():
        p.requires_grad = False


def unfreeze_swin_last_stages(enc: nn.Module, n_stages: int = 2, train_norm: bool = True):
    freeze_all(enc)
    if not hasattr(enc, "layers"):
        raise ValueError("Encoder has no .layers. This unfreeze helper is for Swin-like timm models.")
    layers = enc.layers
    n = max(1, int(n_stages))
    n = min(n, len(layers))

    for i in range(len(layers) - n, len(layers)):
        for p in layers[i].parameters():
            p.requires_grad = True

    if train_norm and hasattr(enc, "norm"):
        for p in enc.norm.parameters():
            p.requires_grad = True


def make_param_groups(model: nn.Module, lr_head: float, lr_backbone: float, wd: float):
    backbone_params = [p for p in model.encoder.parameters() if p.requires_grad]
    head_params = [p for p in list(model.h_action.parameters()) + list(model.h_emotion.parameters()) if p.requires_grad]
    groups = []
    if backbone_params:
        groups.append({"params": backbone_params, "lr": lr_backbone, "weight_decay": wd})
    groups.append({"params": head_params, "lr": lr_head, "weight_decay": wd})
    return groups


def build_scheduler(cfg: CFG, optimizer):
    if not cfg.use_cosine:
        return None

    def lr_lambda(epoch):
        if epoch < cfg.warmup_epochs:
            return float(epoch + 1) / float(max(1, cfg.warmup_epochs))
        t = (epoch - cfg.warmup_epochs) / float(max(1, cfg.epochs - cfg.warmup_epochs))
        cosine = 0.5 * (1.0 + np.cos(np.pi * t))
        min_ratio = cfg.min_lr / max(cfg.lr_head, 1e-12)
        return min_ratio + (1.0 - min_ratio) * cosine

    return optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    act_pred, act_gt = [], []
    emo_pred, emo_gt = [], []

    for x, a, e in loader:
        x = x.to(device)  # (B,K,C,H,W)
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


def try_load_stage2_weights(model: nn.Module, ckpt_path: str):
    ckpt = torch.load(ckpt_path, map_location="cpu")
    sd = ckpt.get("model", ckpt)  # allow raw sd
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print(f"[INIT] loaded from {ckpt_path}")
    print(f"[INIT] missing keys: {len(missing)}, unexpected keys: {len(unexpected)}")
    # missing는 보통 head shape 달라서 생길 수 있음(하지만 지금은 동일 구조라 거의 없을 것)


def train(cfg: CFG):
    set_seed(cfg.seed)
    cfg.out_root.mkdir(parents=True, exist_ok=True)

    print("[SCRIPT PATH]", os.path.abspath(__file__))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = (
        f"{ts}_bb-{cfg.backbone}_stage3_pool-{cfg.pool}_K{cfg.frames_per_video}"
        f"_unfreeze{cfg.unfreeze_stages}_lrB{cfg.lr_backbone}_lrH{cfg.lr_head}"
        f"_bs{cfg.batch_size}_ep{cfg.epochs}_seed{cfg.seed}"
    )
    run_dir = cfg.out_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "log.txt"
    best_path = run_dir / "best.pt"
    meta_path = run_dir / "meta.json"

    print(f"[RUN] {run_name}")
    print(f"[RUN] dir: {run_dir}")

    # 1) video-level items
    tr_vids = collect_video_items(cfg.train_img_root, cfg.train_lbl_root)
    va_vids = collect_video_items(cfg.val_img_root, cfg.val_lbl_root)

    action2id, emo2id = build_vocab(tr_vids, va_vids)
    print(f"[INFO] classes: action={len(action2id)} emotion={len(emo2id)}")

    tr_items = encode_items(tr_vids, action2id, emo2id)
    va_items = encode_items(va_vids, action2id, emo2id)

    # 2) backbone first (to get input size)
    encoder, feat_dim, model_img = create_backbone(cfg.backbone)

    # 3) transforms
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

    tr_ds = VideoFolderDataset(tr_items, train_tfm, frames_per_video=cfg.frames_per_video)
    va_ds = VideoFolderDataset(va_items, val_tfm, frames_per_video=cfg.frames_per_video)

    tr_loader = DataLoader(tr_ds, batch_size=cfg.batch_size, shuffle=True,
                           num_workers=cfg.num_workers, pin_memory=True)
    va_loader = DataLoader(va_ds, batch_size=cfg.batch_size, shuffle=False,
                           num_workers=cfg.num_workers, pin_memory=True)

    # 4) unfreeze policy (same as your best Stage2)
    unfreeze_swin_last_stages(encoder, n_stages=cfg.unfreeze_stages, train_norm=cfg.train_norm)

    model = VideoPoolMultiHead(
        encoder=encoder, feat_dim=feat_dim, n_action=len(action2id), n_emo=len(emo2id), pool=cfg.pool
    ).to(cfg.device)

    # (Optional) init from Stage2 best.pt
    if cfg.init_ckpt:
        try_load_stage2_weights(model, cfg.init_ckpt)

    param_groups = make_param_groups(model, cfg.lr_head, cfg.lr_backbone, cfg.wd)
    optimizer = optim.AdamW(param_groups)
    scheduler = build_scheduler(cfg, optimizer)
    ce = nn.CrossEntropyLoss()

    # save meta
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_name": run_name,
                "cfg": {k: str(v) if isinstance(v, Path) else v for k, v in cfg.__dict__.items()},
                "action2id": action2id,
                "emo2id": emo2id,
                "model_img": model_img,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    best = -1.0

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        pbar = tqdm(tr_loader, desc=f"[Stage3 {cfg.backbone}] epoch {epoch}/{cfg.epochs}")

        for x, a, e in pbar:
            x = x.to(cfg.device)  # (B,K,C,H,W)
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
            f"epoch={epoch} backbone={cfg.backbone} pool={cfg.pool} K={cfg.frames_per_video} "
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
                    "model_img": model_img,
                },
                best_path,
            )

    print(f"[DONE] best_score={best:.4f} saved: {best_path}")


if __name__ == "__main__":
    cfg = CFG(
        backbone="swin_tiny_patch4_window7_224",
        frames_per_video=12,
        pool="mean",
        unfreeze_stages=2,
        lr_backbone=2e-5,
        lr_head=1e-3,
        epochs=12,
        batch_size=12,
        # 여기에 Stage2 best.pt 경로 넣으면 그 가중치에서 시작
        # init_ckpt="runs_stage2/....../best.pt",
        init_ckpt="runs_stage2/20260119_004226_bb-swin_tiny_patch4_window7_224_stage2_unfreeze2_lrB2e-05_lrH0.001_bs64_ep8_seed42/best.pt"
,
    )
    train(cfg)
