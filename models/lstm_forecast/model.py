"""
LSTM 시계열 예측 모델 정의 -- 분기별 매출 추이 예측

PyTorch nn.Module 기반 LSTM + FC 아키텍처.
사전학습(서울 전체) -> 파인튜닝(마포구) 전이학습을 지원한다.
"""

from __future__ import annotations

import copy
from pathlib import Path

import torch
import torch.nn as nn

# 가중치 저장 기본 경로
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"


class LSTMForecaster(nn.Module):
    """LSTM 기반 시계열 매출 예측 모델

    Parameters
    ----------
    input_size : int
        입력 피처 수 (매출, 점포 수, 인구 등).
    hidden_size : int
        LSTM hidden state 차원.
    num_layers : int
        LSTM 레이어 수.
    dropout : float
        LSTM 레이어 간 dropout 비율 (num_layers > 1일 때 적용).
    output_size : int
        출력 차원 (기본 1 = 매출 예측값).
    """

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        output_size: int = 1,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size),
        )

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파

        Parameters
        ----------
        x : Tensor
            shape ``(batch, seq_len, input_size)``

        Returns
        -------
        Tensor
            shape ``(batch, output_size)`` -- 마지막 타임스텝의 예측값
        """
        # lstm_out: (batch, seq_len, hidden_size)
        lstm_out, _ = self.lstm(x)
        last_hidden = lstm_out[:, -1, :]  # 마지막 타임스텝
        return self.fc(last_hidden)

    # ------------------------------------------------------------------
    # 가중치 저장 / 로드
    # ------------------------------------------------------------------

    def save_weights(self, path: str | Path | None = None) -> Path:
        """모델 가중치를 파일로 저장한다.

        Parameters
        ----------
        path : str or Path, optional
            저장 경로. None이면 ``weights/pretrained.pt`` 에 저장.

        Returns
        -------
        Path
            실제 저장된 파일 경로.
        """
        if path is None:
            path = WEIGHTS_DIR / "pretrained.pt"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), path)
        return path

    def load_weights(self, path: str | Path, strict: bool = True) -> None:
        """저장된 가중치를 로드한다.

        Parameters
        ----------
        path : str or Path
            가중치 파일 경로.
        strict : bool
            True면 키가 정확히 일치해야 함.
        """
        state = torch.load(path, map_location="cpu", weights_only=True)
        self.load_state_dict(state, strict=strict)

    # ------------------------------------------------------------------
    # Freeze / Unfreeze (전이학습용)
    # ------------------------------------------------------------------

    def freeze_lstm(self) -> None:
        """LSTM 레이어의 파라미터를 동결한다 (FC만 학습)."""
        for param in self.lstm.parameters():
            param.requires_grad = False

    def unfreeze_lstm(self) -> None:
        """LSTM 레이어의 파라미터 동결을 해제한다."""
        for param in self.lstm.parameters():
            param.requires_grad = True

    def get_best_state(self) -> dict:
        """현재 모델 state_dict의 deep copy를 반환한다."""
        return copy.deepcopy(self.state_dict())
