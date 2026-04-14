"""
GRU 시계열 예측 모델 정의 — 분기별 매출 추이 예측

LSTM 대비 변경점:
- nn.LSTM → nn.GRU
- GRU는 cell state(c)가 없으므로 forward에서 h만 반환 (튜플 해제 불필요)
- 그 외 Attention, FC 구조, 전이학습 메서드는 LSTM과 동일하게 유지

참고: models/lstm_forecast/model.py 를 기반으로 작성.
모델 구조를 통일하여 비교 실험이 가능하도록 설계.
"""

from __future__ import annotations

import copy
from pathlib import Path

import torch
import torch.nn as nn

# 가중치 저장 기본 경로 — gru_forecast/weights/ 디렉토리 사용
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"


class GRUForecaster(nn.Module):
    """GRU 기반 시계열 매출 예측 모델

    LSTM 대비 파라미터 수가 적고 학습이 빠른 GRU를 사용.
    동일한 Attention + FC 구조로 LSTM과 직접 성능 비교 가능.

    Parameters
    ----------
    input_size : int
        입력 피처 수 (매출, 점포 수, 인구 등 31개).
    hidden_size : int
        GRU hidden state 차원. 실험 최적값 128 사용.
    num_layers : int
        GRU 레이어 수.
    dropout : float
        GRU 레이어 간 dropout 비율 (num_layers > 1일 때 적용).
    output_size : int
        출력 차원 (기본 1 = 매출 예측값).
    """

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,  # 실험 최적값: 128 (LSTM과 동일 조건)
        num_layers: int = 2,
        dropout: float = 0.2,
        output_size: int = 1,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # GRU 레이어 — LSTM과 달리 cell state 없이 hidden state만 유지
        # batch_first=True: 입력 shape (batch, seq, features) 형태 사용
        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Attention 메커니즘 — 시퀀스 내 중요 시점에 가중치 부여
        # LSTM과 동일한 구조 유지 (공정한 비교를 위해)
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.Tanh(),
            nn.Linear(hidden_size // 2, 1),
        )

        # FC head — Attention 가중 합산 후 매출 예측값 출력
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

        GRU는 LSTM과 달리 hidden state h만 반환 (cell state c 없음).
        출력 텐서 gru_out의 shape은 LSTM과 동일하므로
        Attention 연산 이후 로직은 LSTM과 완전히 동일하다.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, seq_len, input_size)``

        Returns
        -------
        Tensor
            shape ``(batch, output_size)`` — 예측 매출값
        """
        # gru_out: (batch, seq_len, hidden_size)
        # h: (num_layers, batch, hidden_size) — GRU는 h만 반환 (LSTM과 다름)
        gru_out, _ = self.gru(x)

        # Attention: 각 타임스텝의 중요도를 계산
        attn_scores = self.attention(gru_out)   # (batch, seq_len, 1)
        attn_weights = torch.softmax(attn_scores, dim=1)  # 정규화
        context = (attn_weights * gru_out).sum(dim=1)     # 가중 합산 (batch, hidden_size)

        return self.fc(context)

    # ------------------------------------------------------------------
    # 가중치 저장 / 로드
    # ------------------------------------------------------------------

    def save_weights(self, path: str | Path | None = None) -> Path:
        """모델 가중치를 파일로 저장한다.

        Parameters
        ----------
        path : str or Path, optional
            저장 경로. None이면 ``weights/pretrained_gru.pt`` 에 저장.

        Returns
        -------
        Path
            실제 저장된 파일 경로.
        """
        if path is None:
            path = WEIGHTS_DIR / "pretrained_gru.pt"
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

    def load_weights_partial(self, path: str | Path) -> None:
        """input_size가 다른 사전학습 가중치를 부분 복사로 로드한다.

        서울 전체(24피처) → 마포구(31피처) 전이학습 시
        GRU weight_ih 레이어를 부분 복사하고
        나머지(Attention, FC)는 그대로 로드한다.
        추가된 피처에 대한 가중치는 랜덤 초기화 상태로 유지.
        """
        pretrained = torch.load(path, map_location="cpu", weights_only=True)
        current = self.state_dict()

        for key in pretrained:
            if key in current:
                if pretrained[key].shape == current[key].shape:
                    # 형상이 동일하면 그대로 복사
                    current[key] = pretrained[key]
                elif "weight_ih" in key:
                    # GRU input 가중치: 기존 피처 수만큼만 복사
                    min_feat = min(pretrained[key].shape[1], current[key].shape[1])
                    current[key][:, :min_feat] = pretrained[key][:, :min_feat]

        self.load_state_dict(current)

    # ------------------------------------------------------------------
    # Freeze / Unfreeze (전이학습용)
    # ------------------------------------------------------------------

    def freeze_gru(self) -> None:
        """GRU 레이어의 파라미터를 동결한다 (FC만 학습).

        파인튜닝 1단계: LSTM과 동일하게 GRU 레이어를 고정하고
        FC + Attention만 먼저 학습하여 안정적인 수렴 유도.
        """
        for param in self.gru.parameters():
            param.requires_grad = False

    def unfreeze_gru(self) -> None:
        """GRU 레이어의 파라미터 동결을 해제한다.

        파인튜닝 2단계: 전체 파라미터를 낮은 학습률로 fine-tuning.
        """
        for param in self.gru.parameters():
            param.requires_grad = True

    def get_best_state(self) -> dict:
        """현재 모델 state_dict의 deep copy를 반환한다.

        조기종료(early stopping) 시 최적 가중치를 보존하기 위해 사용.
        """
        return copy.deepcopy(self.state_dict())
