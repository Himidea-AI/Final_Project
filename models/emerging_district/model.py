"""
신흥 상권 조기 감지 모델: LSTM Autoencoder

정상 상권 시계열을 재구성하도록 학습.
추론 시 reconstruction error(MSE) = 이상도 점수.
error > threshold → 이상 패턴 (신흥 또는 쇠퇴 상권 신호).

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
WEIGHTS_DIR.mkdir(exist_ok=True)


class LSTMAutoencoder(nn.Module):
    """LSTM 기반 시계열 Autoencoder.

    Parameters
    ----------
    input_size : int
        입력 피처 수 (기본 6 — EMERGING_FEATURES).
    hidden_size : int
        LSTM hidden dimension (기본 64).
    num_layers : int
        LSTM 레이어 수 (기본 2).
    dropout : float
        Dropout 비율 (num_layers > 1 시 적용, 기본 0.2).
    """

    def __init__(
        self,
        input_size: int = 6,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # Encoder: 시퀀스 → 잠재 벡터 (마지막 hidden state)
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Decoder: 잠재 벡터 반복 → 시퀀스 재구성
        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # 출력층: hidden_size → 원본 피처 크기
        self.output_layer = nn.Linear(hidden_size, input_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, seq_len, input_size)``

        Returns
        -------
        Tensor
            재구성된 시퀀스 ``(batch, seq_len, input_size)``
        """
        _, seq_len, _ = x.shape

        # Encoder
        _, (h_n, _) = self.encoder(x)

        # Decoder 입력: 마지막 레이어 hidden state를 seq_len만큼 반복
        latent = h_n[-1]  # (batch, hidden_size)
        dec_input = latent.unsqueeze(1).repeat(1, seq_len, 1)  # (batch, seq_len, hidden_size)

        # Decoder
        dec_out, _ = self.decoder(dec_input)

        # 출력
        reconstructed = self.output_layer(dec_out)  # (batch, seq_len, input_size)
        return reconstructed

    def save_weights(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), path)
        logger.info("LSTMAutoencoder 가중치 저장: %s", path)

    def load_weights(self, path: str | Path) -> None:
        path = Path(path)
        state = torch.load(path, map_location="cpu", weights_only=True)
        self.load_state_dict(state)
        logger.info("LSTMAutoencoder 가중치 로드: %s", path)
