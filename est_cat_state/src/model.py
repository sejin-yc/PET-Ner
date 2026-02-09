import torch
import torch.nn as nn
import timm

class MultiHeadClassifier(nn.Module):
    """
    num_classes: dict, 예) {"action": 12, "emotion": 6}
    원하는 head만 자동 생성한다.
    """
    def __init__(self, backbone_name: str, num_classes: dict, pretrained: bool = True, dropout: float = 0.2):
        super().__init__()
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, num_classes=0)
        feat_dim = self.backbone.num_features

        self.heads = nn.ModuleDict()
        for name, nc in num_classes.items():
            self.heads[name] = nn.Sequential(
                nn.Dropout(dropout),
                nn.Linear(feat_dim, int(nc)),
            )

    def forward(self, x):
        f = self.backbone(x)
        return {name: head(f) for name, head in self.heads.items()}
