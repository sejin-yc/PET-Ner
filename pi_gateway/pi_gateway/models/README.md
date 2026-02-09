# 모델 폴더

고양이 탐지/상태 분석에 필요한 모델 파일을 여기에 배치하세요.

## 폴더 구조

```
models/
  swin_tiny_best/     ← 액션/감정 분류 (Swin)
    best.pt           또는 best/ 폴더 (data.pkl 등)
  yolo_pose.pt        ← 고양이 포즈 탐지 (YOLO)
```

## 복사 방법

```bash
# pi_gateway 프로젝트 루트에서
cp -r /path/to/swin_tiny_best models/
cp /path/to/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt models/yolo_pose.pt
```

또는 심볼릭 링크:

```bash
ln -s /home/ssafy/Downloads/swin_tiny_best models/swin_tiny_best
ln -s /home/ssafy/Downloads/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome.pt models/yolo_pose.pt
```

## 기본 경로

- Swin 체크포인트: `./models/swin_tiny_best/best` (단일 파일 `best.pt` 또는 폴더 `best/` 둘 다 가능)
- YOLO pose: `./models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best` 또는 단일 파일

## 실행 예시 (프로젝트 루트에서)

```bash
python3 scripts/cat_detection_service.py \
  --ckpt models/swin_tiny_best/best \
  --yolo_pose models/yolo_pose-gy8961dp9tbgbxw9xekwdg9ome/best
```
