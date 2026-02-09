import pandas as pd
import numpy as np
from pathlib import Path
import argparse

def rebalance(df, col, target=8000, max_multiplier=20, downsample_major=True, seed=42):
    """
    - 소수 클래스: min(target, n * max_multiplier) 까지 오버샘플
    - 다수 클래스: (옵션) target 까지 다운샘플
    """
    rng = np.random.default_rng(seed)
    vc = df[col].value_counts()

    parts = []
    for cls, n in vc.items():
        sub = df[df[col] == cls]

        # 소수/중간 클래스: 최대 cap까지 올림
        cap_up = min(target, int(n * max_multiplier))

        if n < target:
            # upsample (하지만 cap_up까지만)
            new_n = cap_up
            idx = rng.choice(sub.index.to_numpy(), size=new_n, replace=True)
            parts.append(df.loc[idx])
        else:
            # majority class
            if downsample_major:
                # downsample to target
                idx = rng.choice(sub.index.to_numpy(), size=target, replace=False)
                parts.append(df.loc[idx])
            else:
                parts.append(sub)

    out = pd.concat(parts, ignore_index=True)
    return out

def main(in_csv, out_csv, col, target=8000, max_multiplier=20, downsample_major=True, seed=42):
    df = pd.read_csv(in_csv)
    df2 = rebalance(df, col=col, target=target, max_multiplier=max_multiplier,
                    downsample_major=downsample_major, seed=seed)

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df2.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print("Saved:", out_csv)
    print("\nBefore:\n", df[col].value_counts())
    print("\nAfter:\n", df2[col].value_counts())

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", default="data/train.csv")
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--col", required=True, help="emotion or action")
    ap.add_argument("--target", type=int, default=8000)
    ap.add_argument("--max_multiplier", type=int, default=20)
    ap.add_argument("--downsample_major", action="store_true", help="downsample majority classes to target")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(**vars(args))
