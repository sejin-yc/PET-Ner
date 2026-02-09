import pandas as pd
import cv2
import numpy as np
from torch.utils.data import Dataset
import albumentations as A
from albumentations.pytorch import ToTensorV2

def build_transforms(train: bool, img_size: int):
    if train:
        return A.Compose([
            A.LongestMaxSize(max_size=img_size),
            A.PadIfNeeded(min_height=img_size, min_width=img_size, border_mode=cv2.BORDER_CONSTANT),
            A.HorizontalFlip(p=0.5),
            A.RandomBrightnessContrast(p=0.3),
            A.ShiftScaleRotate(shift_limit=0.03, scale_limit=0.1, rotate_limit=10, p=0.5),
            A.CoarseDropout(p=0.3),
            A.Normalize(),
            ToTensorV2(),
        ])
    else:
        return A.Compose([
            A.LongestMaxSize(max_size=img_size),
            A.PadIfNeeded(min_height=img_size, min_width=img_size, border_mode=cv2.BORDER_CONSTANT),
            A.Normalize(),
            ToTensorV2(),
        ])

class CatStateDataset(Dataset):
    def __init__(self, csv_path: str, label_maps: dict, img_size: int = 224, train: bool = True,
                 use_bbox_crop: bool = True, bbox_expand: float = 0.15):
        self.df = pd.read_csv(csv_path)
        self.label_maps = label_maps
        self.tfm = build_transforms(train=train, img_size=img_size)
        self.use_bbox_crop = use_bbox_crop
        self.bbox_expand = bbox_expand

        # 미리 정수 라벨로 변환해두기
        for head in label_maps.keys():
            self.df[head] = self.df[head].astype(str).map(self.label_maps[head]).astype(int)



    def __len__(self):
        return len(self.df)

    def _crop_bbox(self, img, row):
        h, w = img.shape[:2]
        x = row["bbox_x"]; y = row["bbox_y"]; bw = row["bbox_w"]; bh = row["bbox_h"]
        if np.isnan(x) or np.isnan(y) or np.isnan(bw) or np.isnan(bh):
            return img

        x, y, bw, bh = float(x), float(y), float(bw), float(bh)
        # expand
        cx = x + bw/2; cy = y + bh/2
        bw2 = bw * (1.0 + self.bbox_expand)
        bh2 = bh * (1.0 + self.bbox_expand)
        x1 = int(max(0, cx - bw2/2))
        y1 = int(max(0, cy - bh2/2))
        x2 = int(min(w, cx + bw2/2))
        y2 = int(min(h, cy + bh2/2))
        if x2 <= x1 or y2 <= y1:
            return img
        return img[y1:y2, x1:x2]

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        path = row["image_path"]

        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.use_bbox_crop:
            img = self._crop_bbox(img, row)

        out = self.tfm(image=img)
        x = out["image"]

        y = {h: int(row[h]) for h in self.label_maps.keys()}
        return x, y

