# analyze_attention_topk.py
# - Load Stage3 attention model checkpoint
# - Sample one video (or N videos) from validation set
# - Save Top-K frames by attention weight with alpha overlay text
# - Print GT / Pred for action & emotion

import os
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import torch
import torch.nn as nn
from torchvision import transforms
import timm


# -------------------------
# Config
# -------------------------
@dataclass
class CFG:
    ckpt_path: str = "runs_stage3_attn/20260119_135944_bb-swin_tiny_patch4_window7_224_stage3attn_K8_unfreeze2_lrB2e-05_lrH0.001_bs16_ep12_seed42/best.pt"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # dataset roots (same as training)
    val_img_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/원천")
    val_lbl_root: Path = Path("/home/ssafy/반려동물 구분을 위한 동물 영상/Validation/CAT/라벨")

    # analysis options
    num_samples: int = 10          # how many videos to analyze
    topk_save: int = 3             # save top-k frames by attention
    seed: int = 42

    out_dir: Path = Path("./attn_analysis_out")


# -------------------------
# Dataset indexing helpers
# -------------------------
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

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
    json_idx = index_json_by_name(lbl_root)
    video_dirs = list_video_dirs(img_root)
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    items = []
    for vdir in video_dirs:
        jname = vdir.name + ".json"
        jpath = json_idx.get(jname)
        if jpath is None:
            continue
        try:
            with open(jpath, "r", encoding="utf-8") as f:
                meta = json.load(f)
            action, emotion = extract_action_emotion(meta)
        except Exception:
            continue

        frames = [p for p in vdir.rglob("*") if p.suffix.lower() in exts]
        if len(frames) == 0:
            continue

        items.append((vdir, action, emotion))

    return items


# -------------------------
# Model: same as Stage3-attn
# -------------------------
class AttentionPooling(nn.Module):
    def __init__(self, feat_dim: int, hidden: int = 256, dropout: float = 0.1):
        super().__init__()
        self.scorer = nn.Sequential(
            nn.Linear(feat_dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )

    def forward(self, feat: torch.Tensor):
        # feat: (B,K,D)
        scores = self.scorer(feat)            # (B,K,1)
        alpha = torch.softmax(scores, dim=1)  # (B,K,1)
        v = (alpha * feat).sum(dim=1)         # (B,D)
        return v, alpha.squeeze(-1)           # alpha: (B,K)

class VideoAttnMultiHead(nn.Module):
    def __init__(self, encoder, feat_dim, n_action, n_emo, attn_hidden=256, attn_dropout=0.1):
        super().__init__()
        self.encoder = encoder
        self.pooler = AttentionPooling(feat_dim, hidden=attn_hidden, dropout=attn_dropout)
        self.h_action = nn.Linear(feat_dim, n_action)
        self.h_emotion = nn.Linear(feat_dim, n_emo)

    def forward(self, x):
        # x: (B,K,C,H,W)
        B, K, C, H, W = x.shape
        x = x.view(B*K, C, H, W)
        feat = self.encoder(x)          # (B*K,D)
        feat = feat.view(B, K, -1)      # (B,K,D)
        vid_feat, alpha = self.pooler(feat)  # (B,D), (B,K)
        return self.h_action(vid_feat), self.h_emotion(vid_feat), alpha


def create_backbone(backbone_name: str):
    enc = timm.create_model(backbone_name, pretrained=True, num_classes=0, global_pool="avg")
    feat_dim = enc.num_features

    model_img = None
    if hasattr(enc, "img_size"):
        isz = enc.img_size
        model_img = int(isz[0]) if isinstance(isz, (tuple, list)) else int(isz)
    if model_img is None and hasattr(enc, "default_cfg"):
        dc = enc.default_cfg or {}
        isz = dc.get("input_size", None)
        if isz and len(isz) == 3:
            model_img = int(isz[1])
    if model_img is None:
        model_img = 224

    return enc, feat_dim, model_img


# -------------------------
# Visualization helper
# -------------------------
def draw_alpha_text(img: Image.Image, text: str) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    # 기본 폰트(환경에 따라 다름). 숫자만 찍으니 한글 폰트 필요 없음.
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([0, 0, 260, 40], fill=(0, 0, 0))
    draw.text((8, 8), text, fill=(255, 255, 255), font=font)
    return out


def main():
    cfg = CFG()
    set_seed(cfg.seed)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    ckpt = torch.load(cfg.ckpt_path, map_location="cpu")
    action2id = ckpt["action2id"]
    emo2id = ckpt["emo2id"]
    id2action = {v: k for k, v in action2id.items()}
    id2emo = {v: k for k, v in emo2id.items()}

    # backbone name/size: Stage3 attn에서 cfg로 저장했을 가능성 있음
    bb = ckpt.get("cfg", {}).get("backbone", "swin_tiny_patch4_window7_224")
    attn_hidden = ckpt.get("cfg", {}).get("attn_hidden", 256)
    attn_dropout = ckpt.get("cfg", {}).get("attn_dropout", 0.1)

    encoder, feat_dim, model_img = create_backbone(bb)
    model = VideoAttnMultiHead(
        encoder=encoder, feat_dim=feat_dim,
        n_action=len(action2id), n_emo=len(emo2id),
        attn_hidden=attn_hidden, attn_dropout=attn_dropout
    )
    model.load_state_dict(ckpt["model"], strict=True)
    model.to(cfg.device)
    model.eval()

    tfm = transforms.Compose([
        transforms.Resize((model_img, model_img)),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])

    items = collect_video_items(cfg.val_img_root, cfg.val_lbl_root)
    random.shuffle(items)
    items = items[:cfg.num_samples]

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    for i, (vdir, gt_a_str, gt_e_str) in enumerate(items):
        frames = [p for p in vdir.rglob("*") if p.suffix.lower() in exts]
        # 분석은 “어떤 프레임이 중요한지” 보기 좋게: 균일 샘플링 권장
        frames = sorted(frames)
        K = ckpt.get("cfg", {}).get("frames_per_video", 8)
        if len(frames) >= K:
            idxs = np.linspace(0, len(frames)-1, K).astype(int).tolist()
            chosen = [frames[j] for j in idxs]
        else:
            chosen = frames + [random.choice(frames) for _ in range(K - len(frames))]

        # 텐서 만들기 (1,K,C,H,W)
        imgs = []
        for fp in chosen:
            img = Image.open(fp).convert("RGB")
            imgs.append(tfm(img))
        x = torch.stack(imgs, dim=0).unsqueeze(0).to(cfg.device)

        with torch.no_grad():
            out_a, out_e, alpha = model(x)     # alpha: (1,K)
            pa = int(out_a.argmax(1).item())
            pe = int(out_e.argmax(1).item())
            alpha = alpha.squeeze(0).detach().cpu().numpy().tolist()

        pred_a_str = id2action[pa]
        pred_e_str = id2emo[pe]

        # 저장 폴더
        vid_out = cfg.out_dir / f"{i:03d}_{vdir.name}"
        vid_out.mkdir(parents=True, exist_ok=True)

        # TopK 저장
        order = np.argsort(alpha)[::-1]  # desc
        topk = order[:cfg.topk_save]

        # summary log
        with open(vid_out / "summary.txt", "w", encoding="utf-8") as f:
            f.write(f"video_dir: {vdir}\n")
            f.write(f"GT action: {gt_a_str}\nGT emotion: {gt_e_str}\n")
            f.write(f"PRED action: {pred_a_str}\nPRED emotion: {pred_e_str}\n")
            f.write(f"alpha (K={len(alpha)}): {alpha}\n")
            f.write(f"topk idx: {topk.tolist()}\n")

        # 이미지 저장 + alpha overlay
        for rank, t in enumerate(topk, start=1):
            fp = chosen[int(t)]
            img = Image.open(fp).convert("RGB").resize((model_img, model_img))
            txt = f"rank#{rank}  idx={int(t)}  alpha={alpha[int(t)]:.4f}"
            img2 = draw_alpha_text(img, txt)
            img2.save(vid_out / f"top{rank}_idx{int(t)}_alpha{alpha[int(t)]:.4f}.jpg")

        print(f"[OK] saved -> {vid_out} | GT=({gt_a_str}/{gt_e_str}) PRED=({pred_a_str}/{pred_e_str})")


if __name__ == "__main__":
    main()
