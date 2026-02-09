from pathlib import Path
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt


def load_inv_maps(label_maps_path: Path):
    """
    label_maps.json 구조 예:
    {
      "label_maps": {"action": {"...":0, ...}, "emotion": {...}},
      "inv_maps":   {"action": { "0":"...", ...}, "emotion": {...}}
    }
    """
    data = json.loads(label_maps_path.read_text(encoding="utf-8"))

    # 우리가 저장했던 형식은 inv_maps도 같이 들어있음
    if "inv_maps" in data:
        inv_maps = {}
        for head, m in data["inv_maps"].items():
            # json key가 문자열일 수 있으니 int로 변환
            inv_maps[head] = {int(k): v for k, v in m.items()}
        return inv_maps

    # 혹시 label_maps만 있을 경우 역매핑 생성
    label_maps = data["label_maps"]
    inv_maps = {}
    for head, m in label_maps.items():
        inv_maps[head] = {v: k for k, v in m.items()}
    return inv_maps


def plot_cm(cm: np.ndarray, labels: list[str], title: str, out_path: Path, normalize: bool):
    """
    normalize=True면 행(=true class) 기준으로 정규화해서 '비율'로 표시
    """
    # normalize 안할 때는 count니까 int 그대로 유지
    cm_to_plot = cm.copy()

    if normalize:
        cm_to_plot = cm_to_plot.astype(np.float32)
        row_sum = cm_to_plot.sum(axis=1, keepdims=True)
        cm_to_plot = np.divide(cm_to_plot, np.clip(row_sum, 1e-9, None))


    plt.figure(figsize=(10, 8))
    plt.imshow(cm_to_plot, interpolation="nearest", aspect="auto")
    plt.title(title)
    plt.colorbar()

    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=60, ha="right")
    plt.yticks(tick_marks, labels)

    # 숫자(값) 표시 (클래스가 너무 많으면 보기 복잡할 수 있어 자동으로 제한)
    n = len(labels)
    show_numbers = n <= 25
    if show_numbers:
        fmt = ".2f" if normalize else "d"
        thresh = cm_to_plot.max() * 0.6 if cm_to_plot.size else 0.0
        for i in range(n):
            for j in range(n):
                val = cm_to_plot[i, j]
                text = format(val, fmt)
                plt.text(j, i, text, ha="center", va="center",
                         color="white" if val > thresh else "black", fontsize=8)

    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def main(run_dir: str, normalize: bool):
    run_dir = Path(run_dir)

    cm_action_path = run_dir / "cm_action.npy"
    cm_emotion_path = run_dir / "cm_emotion.npy"
    label_maps_path = run_dir / "label_maps.json"

    if not label_maps_path.exists():
        raise FileNotFoundError(f"label_maps.json not found: {label_maps_path}")

    inv_maps = load_inv_maps(label_maps_path)

    # action
    if cm_action_path.exists():
        cm_action = np.load(cm_action_path)
        action_labels = [inv_maps["action"][i] for i in range(cm_action.shape[0])]
        suffix = "norm" if normalize else "raw"
        out_action = run_dir / f"cm_action_{suffix}.png"
        plot_cm(cm_action, action_labels, f"Confusion Matrix - action ({suffix})", out_action, normalize)
        print("Saved:", out_action)
    else:
        print("Skip: cm_action.npy not found")

    # emotion
    if cm_emotion_path.exists():
        cm_emotion = np.load(cm_emotion_path)
        emotion_labels = [inv_maps["emotion"][i] for i in range(cm_emotion.shape[0])]
        suffix = "norm" if normalize else "raw"
        out_emotion = run_dir / f"cm_emotion_{suffix}.png"
        plot_cm(cm_emotion, emotion_labels, f"Confusion Matrix - emotion ({suffix})", out_emotion, normalize)
        print("Saved:", out_emotion)
    else:
        print("Skip: cm_emotion.npy not found")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True, help="outputs/<run_name> folder")
    ap.add_argument("--normalize", action="store_true", help="normalize rows (true class) to show ratios")
    args = ap.parse_args()
    main(args.run_dir, args.normalize)
