"""
폐업위험도 모델 정의

TCNClassifier: TCNForecaster 출력층을 sigmoid로 교체한 이진 분류 모델
  - pretrained_tcn.pt 가중치에서 TCN 컨볼루션 블록 재사용 (전이학습)
  - FC head만 새로 초기화 (매출 예측 → 폐업 위험 분류)

담당: B2 — 수지니
참조: models/tcn_forecast/model.py (TCNForecaster 구조 동일)
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch
import torch.nn as nn

from models.tcn_forecast.model import TCNForecaster

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
WEIGHTS_DIR.mkdir(exist_ok=True)


class TCNClassifier(nn.Module):
    """TCN 기반 폐업위험도 이진 분류 모델.

    TCNForecaster의 컨볼루션 블록(feature extractor)을 그대로 가져오고
    FC head만 sigmoid 분류기로 교체한다.

    Parameters
    ----------
    input_size : int
        입력 피처 수 (기본 33 — data_prep.ALL_FEATURES).
    n_channels : int
        TCN 내부 채널 수 (pretrain과 동일하게 128 유지).
    kernel_size : int
        컨볼루션 커널 크기 (기본 2).
    dilations : list[int]
        팽창 계수 목록 (기본 [1, 2]).
    dropout : float
        Dropout 비율.
    """

    def __init__(
        self,
        input_size: int = 33,
        n_channels: int = 128,
        kernel_size: int = 2,
        dilations: list[int] | None = None,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if dilations is None:
            dilations = [1, 2]

        # TCNForecaster를 backbone으로 활용 (output_size=1 임시 — head 교체 예정)
        self._backbone = TCNForecaster(
            input_size=input_size,
            n_channels=n_channels,
            kernel_size=kernel_size,
            dilations=dilations,
            dropout=dropout,
            output_size=1,
        )

        # FC head 교체: 회귀(Linear) → 이진 분류(logit 출력)
        # Sigmoid는 추론 시에만 적용 — BCEWithLogitsLoss와 수치 안정성 확보
        self._backbone.fc_head = nn.Sequential(
            nn.Linear(n_channels, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),  # logit 출력 (sigmoid 없음)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, seq_len, input_size)``

        Returns
        -------
        Tensor
            shape ``(batch, 1)`` — logit 값 (sigmoid 미적용; predict.py에서 torch.sigmoid() 적용)
        """
        return self._backbone(x)

    def load_pretrained_tcn(self, pretrained_path: str | Path) -> None:
        """매출 예측 TCN 가중치에서 컨볼루션 블록만 전이학습.

        FC head(분류기)는 새로 초기화된 상태를 유지한다.
        """
        pretrained_path = Path(pretrained_path)
        if not pretrained_path.exists():
            logger.warning("pretrained 가중치 없음, 전이학습 스킵: %s", pretrained_path)
            return

        state = torch.load(pretrained_path, map_location="cpu", weights_only=True)

        # fc_head 관련 키 제외 — 컨볼루션 블록만 로드
        tcn_keys = {k: v for k, v in state.items() if not k.startswith("fc_head")}
        missing, unexpected = self._backbone.load_state_dict(tcn_keys, strict=False)

        logger.info(
            "전이학습 완료: %d 레이어 로드, missing=%d, unexpected=%d",
            len(tcn_keys),
            len(missing),
            len(unexpected),
        )

    def save_weights(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._backbone.state_dict(), path)
        logger.info("TCNClassifier 가중치 저장: %s", path)

    def load_weights(self, path: str | Path) -> None:
        path = Path(path)
        state = torch.load(path, map_location="cpu", weights_only=True)
        self._backbone.load_state_dict(state, strict=False)
        logger.info("TCNClassifier 가중치 로드: %s", path)
