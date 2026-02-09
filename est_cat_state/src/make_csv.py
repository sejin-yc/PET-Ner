import json
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import argparse

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def safe_get(d, path, default=None):
    cur = d
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

def build_video_dir_index(image_root: Path):
    """
    원천 폴더 아래에서 '...mp4' 로 끝나는 디렉토리들을 찾아
    dir_name(예: 20201028_cat-arch-000156.mp4) -> 실제 경로 로 매핑
    """
    video_dirs = {}
    for p in image_root.rglob("*"):
        if p.is_dir() and p.name.lower().endswith(".mp4"):
            video_dirs[p.name] = p
    return video_dirs

def find_frame_image(video_dir: Path, frame_number: int, timestamp: int | None):
    """
    frame_{frame_number}_timestamp_{timestamp}.jpg 를 우선 찾고,
    없으면 frame_{frame_number}_timestamp_* 로 fallback
    """
    if timestamp is not None:
        # 보통 jpg
        cand = video_dir / f"frame_{frame_number}_timestamp_{timestamp}.jpg"
        if cand.exists():
            return str(cand)

        # 확장자 다른 경우 대비
        for ext in IMG_EXTS:
            cand2 = video_dir / f"frame_{frame_number}_timestamp_{timestamp}{ext}"
            if cand2.exists():
                return str(cand2)

    # timestamp가 다르거나 파일명 규칙이 살짝 다른 경우 fallback
    # (frame_number만 맞는 걸 찾음)
    candidates = list(video_dir.glob(f"frame_{frame_number}_timestamp_*"))
    candidates = [c for c in candidates if c.suffix.lower() in IMG_EXTS]
    if candidates:
        return str(sorted(candidates)[0])

    # 더 fallback: frame_{frame_number}_* 형태도 찾기
    candidates = list(video_dir.glob(f"frame_{frame_number}_*"))
    candidates = [c for c in candidates if c.suffix.lower() in IMG_EXTS]
    if candidates:
        return str(sorted(candidates)[0])

    return None

def json_to_rows(label_json_path: Path, video_dir_index: dict):
    with open(label_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ===== 라벨(네가 원하는 출력 4개) =====
    action = safe_get(data, "metadata.inspect.action")
    painDisease = safe_get(data, "metadata.inspect.painDisease")
    abnormalAction = safe_get(data, "metadata.inspect.abnormalAction")
    emotion = safe_get(data, "metadata.inspect.emotion")

    # ===== json이 가리키는 비디오(폴더명 만들기) =====
    # file_video: "20201028/cat-arch-000156.mp4"
    file_video = data.get("file_video", "")
    p = Path(file_video)
    if len(p.parts) >= 2:
        # "20201028" + "_" + "cat-arch-000156.mp4" => "20201028_cat-arch-000156.mp4"
        video_dir_name = f"{p.parts[-2]}_{p.name}"
    else:
        # 혹시 "cat-arch-000156.mp4" 만 들어오는 경우
        video_dir_name = p.name

    video_dir = video_dir_index.get(video_dir_name)
    if video_dir is None:
        # 매칭 실패: row 0개로 반환
        return []

    rows = []
    for ann in data.get("annotations", []):
        frame_number = ann.get("frame_number", None)
        if frame_number is None:
            continue
        timestamp = ann.get("timestamp", None)

        img_path = find_frame_image(video_dir, int(frame_number), int(timestamp) if timestamp is not None else None)
        if img_path is None:
            continue

        bbox = ann.get("bounding_box", {})
        rows.append({
            "image_path": img_path,
            "video_dir": str(video_dir),
            "video_dir_name": video_dir_name,
            "frame_number": int(frame_number),
            "timestamp": int(timestamp) if timestamp is not None else None,
            "action": action,
            "painDisease": painDisease,
            "abnormalAction": abnormalAction,
            "emotion": emotion,
            "bbox_x": bbox.get("x", None),
            "bbox_y": bbox.get("y", None),
            "bbox_w": bbox.get("width", None),
            "bbox_h": bbox.get("height", None),
            "label_json": str(label_json_path),
        })
    return rows

def build_split_csv(image_root: str, label_root: str, out_csv: str):
    image_root = Path(image_root)
    label_root = Path(label_root)

    video_dir_index = build_video_dir_index(image_root)
    label_jsons = sorted(label_root.rglob("*.json"))

    all_rows = []
    zero_match = 0
    for jp in tqdm(label_jsons, desc=f"Parsing {label_root}"):
        try:
            rows = json_to_rows(jp, video_dir_index)
            if len(rows) == 0:
                zero_match += 1
            all_rows.extend(rows)
        except Exception:
            zero_match += 1

    df = pd.DataFrame(all_rows)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print("\n=== Summary ===")
    print("Video frame folders indexed:", len(video_dir_index))
    print("Label json files:", len(label_jsons))
    print("Rows made (annotated frames matched):", len(df))
    print("Json with 0 matched frames or error:", zero_match)
    if len(df) > 0:
        print("\nTop label counts:")
        for col in ["action", "painDisease", "abnormalAction", "emotion"]:
            print(f"\n[{col}]")
            print(df[col].value_counts().head(10))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train_img", required=True)
    ap.add_argument("--train_lbl", required=True)
    ap.add_argument("--val_img", required=True)
    ap.add_argument("--val_lbl", required=True)
    ap.add_argument("--out_dir", default="data")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    build_split_csv(args.train_img, args.train_lbl, str(out_dir / "train.csv"))
    build_split_csv(args.val_img, args.val_lbl, str(out_dir / "val.csv"))

if __name__ == "__main__":
    main()
