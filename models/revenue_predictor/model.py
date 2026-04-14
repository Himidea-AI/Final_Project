"""
폐업률 예측 모델 정의 — LSTM 기반

입력:  과거 N분기의 점포 시계열 피처 (store_count, closure_rate 등)
출력:  다음 분기 폐업 확률 (0~1)
"""

from __future__ import annotations

import torch
import torch.nn as nn


class ClosurePredictor(nn.Module):
    """
    LSTM 기반 폐업률 예측 모델.

    Architecture:
        Input (batch, seq_len, n_features)
        → LSTM (2-layer, bidirectional)
        → Attention pooling
        → FC head
        → Sigmoid → closure probability
    """

    def __init__(
        self,
        input_size: int = 8,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=True,
        )

        # Attention layer — 시퀀스 내 중요 시점에 가중치 부여
        self.attention = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 1),
        )

        # FC head
        self.fc = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        순전파.

        Args:
            x: (batch, seq_len, n_features)

        Returns:
            (batch,) — 폐업 확률 (0~1)
        """
        # LSTM 출력: (batch, seq_len, hidden*2)
        lstm_out, _ = self.lstm(x)

        # Attention weights: (batch, seq_len, 1)
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)

        # Context vector: (batch, hidden*2)
        context = (lstm_out * attn_weights).sum(dim=1)

        # 폐업 확률
        return self.fc(context).squeeze(-1)


def build_model(input_size: int = 8, hidden_size: int = 64) -> ClosurePredictor:
    """모델 인스턴스를 생성하고 가중치를 초기화한다."""
    model = ClosurePredictor(input_size=input_size, hidden_size=hidden_size)

    # Xavier 초기화
    for name, param in model.named_parameters():
        if "weight" in name and param.dim() >= 2:
            nn.init.xavier_uniform_(param)
        elif "bias" in name:
            nn.init.zeros_(param)

    return model
