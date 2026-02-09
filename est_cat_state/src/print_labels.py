import torch

ckpt_path = "runs_stage3_attn/20260119_135944_bb-swin_tiny_patch4_window7_224_stage3attn_K8_unfreeze2_lrB2e-05_lrH0.001_bs16_ep12_seed42/best.pt"  # <- 여기를 실제 경로로 바꿔

ckpt = torch.load(ckpt_path, map_location="cpu")

print("\n[ACTION LABELS]")
for i, name in enumerate(ckpt["action2id"].keys()):
    print(f"{i:02d}  {name}")

print("\n[EMOTION LABELS]")
for i, name in enumerate(ckpt["emo2id"].keys()):
    print(f"{i:02d}  {name}")
