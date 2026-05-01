"""
타겟 고객 매출 기여 예측 MLP 모델

입력:  동코드 임베딩 + 업종코드 임베딩 + 분기 인코딩(sin/cos) + 연도 정규화(year_norm)
출력:  연령(6) + 성별(2) + 시간대(6) + 요일타입(2) 세그먼트 비율 = 16차원

담당: B2 — 수지니
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
WEIGHTS_DIR.mkdir(exist_ok=True)

# 출력 세그먼트 컬럼 순서 (data_prep.SEGMENT_COLS와 동기화)
SEGMENT_COLS = [
    "age_10_ratio",
    "age_20_ratio",
    "age_30_ratio",
    "age_40_ratio",
    "age_50_ratio",
    "age_60_above_ratio",
    "male_ratio",
    "female_ratio",
    "time_00_06_ratio",
    "time_06_11_ratio",
    "time_11_14_ratio",
    "time_14_17_ratio",
    "time_17_21_ratio",
    "time_21_24_ratio",
    "weekday_ratio",
    "weekend_ratio",
]

N_DONGS = 16
N_INDUSTRIES = 10
N_OUTPUTS = len(SEGMENT_COLS)  # 16


class MLPPredictor(nn.Module):
    """
    타겟 고객 세그먼트 비율 예측 MLP.

    Architecture:
        dong_embed(16→4) + industry_embed(10→4) + quarter_sin/cos/year_norm(3)
        → FC(11→128) → BN → ReLU → Dropout
        → FC(128→64) → ReLU → Dropout
        → FC(64→16) → Softmax×4그룹 (비율 0~1, 그룹 합=1.0)
    """

    def __init__(
        self,
        n_dongs: int = N_DONGS,
        n_industries: int = N_INDUSTRIES,
        dong_embed_dim: int = 4,
        industry_embed_dim: int = 4,
        hidden1: int = 128,
        hidden2: int = 64,
        dropout: float = 0.3,
        n_outputs: int = N_OUTPUTS,
    ):
        super().__init__()

        self.dong_embed = nn.Embedding(n_dongs, dong_embed_dim)
        self.industry_embed = nn.Embedding(n_industries, industry_embed_dim)

        input_dim = dong_embed_dim + industry_embed_dim + 3  # +3: sin/cos/year_norm

        self.fc = nn.Sequential(
            nn.Linear(input_dim, hidden1),
            nn.BatchNorm1d(hidden1),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden2, n_outputs),
            # Sigmoid 없음 — forward()에서 그룹별 Softmax 적용
        )

    def forward(self, dong_idx: torch.Tensor, industry_idx: torch.Tensor, quarter_enc: torch.Tensor) -> torch.Tensor:
        """
        Args:
            dong_idx:      (batch,) — 동 인덱스 (0~15)
            industry_idx:  (batch,) — 업종 인덱스 (0~9)
            quarter_enc:   (batch, 3) — [sin(2π·q/4), cos(2π·q/4), year_norm]

        Returns:
            (batch, 16) — 그룹별 Softmax 적용된 세그먼트 비율
                [0:6]  연령 6개  — identified_sales 기준, 합=1.0
                [6:8]  성별 2개  — identified_sales 기준, 합=1.0
                [8:14] 시간대 6개 — monthly_sales 기준, 합=1.0
                [14:16] 요일 2개  — monthly_sales 기준, 합=1.0
        """
        d = self.dong_embed(dong_idx)  # (batch, 4)
        i = self.industry_embed(industry_idx)  # (batch, 4)
        x = torch.cat([d, i, quarter_enc], dim=-1)  # (batch, 11)
        logits = self.fc(x)  # (batch, 16) raw logit

        age = torch.softmax(logits[:, 0:6], dim=-1)  # 연령 6개 합=1
        gender = torch.softmax(logits[:, 6:8], dim=-1)  # 성별 2개 합=1
        time = torch.softmax(logits[:, 8:14], dim=-1)  # 시간대 6개 합=1
        day = torch.softmax(logits[:, 14:16], dim=-1)  # 요일 2개 합=1

        return torch.cat([age, gender, time, day], dim=-1)  # (batch, 16)

    def save_weights(self, path: str | Path) -> None:
        torch.save(self.state_dict(), path)

    def load_weights(self, path: str | Path) -> None:
        self.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
        self.eval()


def build_model(dropout: float = 0.3) -> MLPPredictor:
    """모델 인스턴스 생성 + Xavier 초기화."""
    model = MLPPredictor(dropout=dropout)
    for name, param in model.named_parameters():
        if "weight" in name and param.dim() >= 2:
            nn.init.xavier_uniform_(param)
        elif "bias" in name:
            nn.init.zeros_(param)
    return model
