"""
TCN 시계열 예측 모델 정의 — 분기별 매출 추이 예측

GRU/LSTM 대비 변경점:
- 순환 신경망(RNN) → 팽창 인과 컨볼루션(Dilated Causal Convolution)
- cell state / hidden state 개념 없음 — 순수 컨볼루션으로 시퀀스 처리
- Residual connection으로 기울기 소실 방지 (깊은 네트워크에서도 안정)

Receptive Field 공식:
  RF = 1 + (kernel_size - 1) × sum(dilations)

운영 표준 (2026-05-03 v3 채택):
  window=4, dilations=[1,2], output=1 → RF = 1 + 1 × (1+2) = 4 (window 정확 커버)
  자기회귀 4-step rollout으로 4분기 예측 (predict.py).

참고: models/lstm_forecast/model.py, models/gru_forecast/model.py 기반으로 작성.
GRU/LSTM과 동일한 입출력 구조를 유지하여 공정한 비교 실험이 가능하도록 설계.

담당: B2 — 수지니
"""

from __future__ import annotations

import copy
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

# 가중치 저장 기본 경로 — tcn_forecast/weights/ 디렉토리 사용
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"


# ---------------------------------------------------------------------------
# 인과 컨볼루션 레이어
# ---------------------------------------------------------------------------


class CausalConv1d(nn.Module):
    """인과 컨볼루션(Causal Convolution) — 미래 시점을 보지 않는 Conv1d.

    일반 Conv1d는 좌우 대칭 패딩을 사용하지만,
    시계열 예측에서는 미래 데이터 누수를 방지하기 위해
    왼쪽(과거)에만 패딩을 추가하는 인과 패딩을 사용한다.

    패딩 크기 = dilation × (kernel_size - 1)
    → 출력 길이 = 입력 길이 (시퀀스 길이 유지)

    Parameters
    ----------
    in_channels : int
        입력 채널 수.
    out_channels : int
        출력 채널 수.
    kernel_size : int
        컨볼루션 커널 크기.
    dilation : int
        팽창 계수 — 값이 클수록 더 넓은 범위를 참조.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 2,
        dilation: int = 1,
    ) -> None:
        super().__init__()
        # 왼쪽 패딩 크기 계산: dilation × (kernel_size - 1)
        # 이 만큼 왼쪽에 패딩하면 출력 길이 = 입력 길이 유지
        self.padding = dilation * (kernel_size - 1)

        self.conv = nn.Conv1d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            padding=0,  # 수동 패딩 사용 (인과성 보장)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파 — 왼쪽에만 패딩을 추가하여 인과성을 보장한다.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, channels, seq_len)``

        Returns
        -------
        Tensor
            shape ``(batch, out_channels, seq_len)``
        """
        # 왼쪽에만 패딩 추가 (미래 시점 누수 방지)
        # F.pad 인자: (마지막 차원 왼쪽, 마지막 차원 오른쪽)
        x = F.pad(x, (self.padding, 0))
        return self.conv(x)


# ---------------------------------------------------------------------------
# TCN 기본 블록 (Temporal Block)
# ---------------------------------------------------------------------------


class TemporalBlock(nn.Module):
    """TCN의 기본 블록 — 팽창 인과 컨볼루션 2개 + Residual connection.

    구조:
        CausalConv1d → LayerNorm → ReLU → Dropout
        CausalConv1d → LayerNorm → ReLU → Dropout
        + Residual (입력과 출력을 더함)

    Residual connection 이유:
    - 기울기 소실 방지: 깊은 네트워크에서도 그라디언트가 직접 전달됨
    - 안정적 수렴: 초기 학습 시 항등 함수(identity)로 동작해 안정성 확보
    - 채널 수가 다를 경우 1×1 Conv로 차원 맞춤

    Parameters
    ----------
    in_channels : int
        입력 채널 수.
    out_channels : int
        출력 채널 수.
    kernel_size : int
        컨볼루션 커널 크기 (기본 2).
    dilation : int
        팽창 계수.
    dropout : float
        Dropout 비율.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 2,
        dilation: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        # 첫 번째 인과 컨볼루션 레이어
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size, dilation)
        self.norm1 = nn.LayerNorm(out_channels)  # BatchNorm 대신 LayerNorm 사용 (시계열에 더 안정적)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        # 두 번째 인과 컨볼루션 레이어 (같은 dilation 사용)
        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size, dilation)
        self.norm2 = nn.LayerNorm(out_channels)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        # Residual connection: 채널 수가 다를 경우 1×1 Conv로 차원 맞춤
        # 같을 경우 identity (추가 파라미터 없음)
        if in_channels != out_channels:
            self.residual_proj = nn.Conv1d(in_channels, out_channels, kernel_size=1)
        else:
            self.residual_proj = None  # identity residual

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파 — 2개의 인과 컨볼루션 + Residual 합산.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, in_channels, seq_len)``

        Returns
        -------
        Tensor
            shape ``(batch, out_channels, seq_len)``
        """
        # Residual 경로 저장 (채널 불일치 시 projection)
        residual = x if self.residual_proj is None else self.residual_proj(x)

        # 메인 경로: Conv → Norm → ReLU → Dropout (×2)
        # LayerNorm은 (batch, seq_len, channels) 형태를 기대하므로 transpose 필요
        out = self.conv1(x)  # (batch, out_ch, seq_len)
        out = self.norm1(out.transpose(1, 2)).transpose(1, 2)  # LayerNorm 적용
        out = self.relu1(out)
        out = self.dropout1(out)

        out = self.conv2(out)
        out = self.norm2(out.transpose(1, 2)).transpose(1, 2)
        out = self.relu2(out)
        out = self.dropout2(out)

        # Residual 합산 후 ReLU (최종 활성화)
        return F.relu(out + residual)


# ---------------------------------------------------------------------------
# TCN 전체 모델
# ---------------------------------------------------------------------------


class TCNForecaster(nn.Module):
    """TCN 기반 시계열 매출 예측 모델.

    Temporal Convolutional Network를 사용하여 분기별 매출을 예측한다.
    LSTM/GRU 대비 병렬 연산이 가능하여 학습 속도가 빠르며,
    팽창 컨볼루션으로 window_size만큼의 수용 영역을 정확히 커버한다.

    아키텍처 (TemporalBlock 개수 = len(dilations)):
        1. Input Projection: Linear(input_size → n_channels)
        2. TemporalBlock 스택 (dilation 별로 1개씩, dilations 리스트 순서대로 stack)
        3. FC Head: Linear(n_ch → n_ch//2) → ReLU → Dropout → Linear(→ output_size)

    Receptive Field 공식: RF = 1 + (kernel_size - 1) × sum(dilations)

    프로젝트 표준 설정:
    - v3 (운영 기본, 2026-05-03 채택):
        window=4, dilations=[1,2], output=1 → RF = 1+1×(1+2) = 4 (window 정확 커버)
    - v2 (DMS legacy):
        window=12, dilations=[1,2,4,8], output=4 → RF = 1+1×15 = 16 (window 초과)
    - 클래스 기본값(`dilations=None` 시 [1,2,4])은 RF=8용 — 실제 학습/추론은 항상
      explicit dilations 전달하므로 default는 fallback 의미만 가짐.

    Parameters
    ----------
    input_size : int
        입력 피처 수 (v3 기본 37개).
    n_channels : int
        TCN 내부 채널 수. GRU의 hidden_size에 대응. 기본 128.
    kernel_size : int
        컨볼루션 커널 크기 (기본 2).
    dilations : list[int] | None
        각 TemporalBlock의 팽창 계수 목록. None=fallback [1,2,4].
        운영 학습/추론은 train.py / predict.py 에서 explicit 전달.
    dropout : float
        Dropout 비율.
    output_size : int
        출력 차원 (v3=1 자기회귀 / v2=4 DMS).
    """

    def __init__(
        self,
        input_size: int = 10,
        n_channels: int = 128,  # GRU의 hidden_size에 대응 — 실험 최적값 128
        kernel_size: int = 2,  # window_size=8 기준 최적 커널 크기
        dilations: list[int] | None = None,  # 기본 [1, 2, 4] — window_size=8 최적
        dropout: float = 0.2,
        output_size: int = 4,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.n_channels = n_channels

        # dilation 기본값: [1, 2, 4] — window_size=8과 RF가 정확히 일치
        # RF = 1 + (kernel_size-1) × sum([1,2,4]) = 1 + 1×7 = 8
        if dilations is None:
            dilations = [1, 2, 4]
        self.dilations = dilations

        # 1. Input Projection: 피처 차원 → TCN 채널 차원
        # Conv1d 입력 형태에 맞게 피처를 n_channels로 변환
        # Linear 사용 이유: 각 타임스텝에 독립적으로 적용 (피처 믹싱)
        self.input_proj = nn.Linear(input_size, n_channels)

        # 2. Temporal Blocks: 팽창 인과 컨볼루션 블록 스택
        # 첫 블록은 in_channels=n_channels (input_proj 출력 후이므로)
        blocks = []
        for dilation in dilations:
            blocks.append(
                TemporalBlock(
                    in_channels=n_channels,
                    out_channels=n_channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
        self.tcn_blocks = nn.Sequential(*blocks)

        # 3. FC Head — 마지막 타임스텝의 특징을 매출 예측값으로 변환
        # GRU/LSTM과 동일한 FC 구조 유지 (공정한 비교를 위해)
        self.fc = nn.Sequential(
            nn.Linear(n_channels, n_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(n_channels // 2, output_size),
        )

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파.

        TCN은 RNN과 달리 시퀀스 전체를 한 번에 처리한다 (병렬 가능).
        마지막 타임스텝의 출력을 FC Head에 입력하여 다음 분기 매출 예측.

        Parameters
        ----------
        x : Tensor
            shape ``(batch, seq_len, input_size)``

        Returns
        -------
        Tensor
            shape ``(batch, output_size)`` — 예측 매출값
        """
        # Input Projection: (batch, seq_len, input_size) → (batch, seq_len, n_channels)
        out = self.input_proj(x)

        # Conv1d 입력 형태로 변환: (batch, seq_len, n_channels) → (batch, n_channels, seq_len)
        out = out.transpose(1, 2)

        # TCN Blocks 통과: 팽창 인과 컨볼루션 적용
        out = self.tcn_blocks(out)

        # 마지막 타임스텝만 사용: (batch, n_channels, seq_len) → (batch, n_channels)
        # 이유: 자기회귀 예측에서 가장 최근 타임스텝이 미래 예측의 근거
        out = out[:, :, -1]

        # FC Head로 매출 예측값 출력
        return self.fc(out)

    # ------------------------------------------------------------------
    # 가중치 저장 / 로드
    # ------------------------------------------------------------------

    def save_weights(self, path: str | Path | None = None) -> Path:
        """모델 가중치를 파일로 저장한다.

        Parameters
        ----------
        path : str or Path, optional
            저장 경로. None이면 ``weights/pretrained_tcn.pt`` 에 저장.

        Returns
        -------
        Path
            실제 저장된 파일 경로.
        """
        if path is None:
            path = WEIGHTS_DIR / "pretrained_tcn.pt"
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

        서울 전체(피처 수 다를 수 있음) → 마포구(31피처) 전이학습 시
        input_proj 레이어를 부분 복사하고 나머지(TCN blocks, FC)는 그대로 로드한다.
        추가된 피처에 대한 가중치는 랜덤 초기화 상태로 유지.
        """
        pretrained = torch.load(path, map_location="cpu", weights_only=True)
        current = self.state_dict()

        for key in pretrained:
            if key in current:
                if pretrained[key].shape == current[key].shape:
                    # 형상이 동일하면 그대로 복사
                    current[key] = pretrained[key]
                elif "input_proj.weight" in key:
                    # input_proj의 weight: 기존 피처 수만큼만 복사
                    # shape: (n_channels, input_size) — input_size 차원이 다를 수 있음
                    min_feat = min(pretrained[key].shape[1], current[key].shape[1])
                    current[key][:, :min_feat] = pretrained[key][:, :min_feat]

        self.load_state_dict(current)

    # ------------------------------------------------------------------
    # Freeze / Unfreeze (전이학습용)
    # ------------------------------------------------------------------

    def freeze_tcn(self) -> None:
        """TCN 블록과 Input Projection의 파라미터를 동결한다 (FC만 학습).

        파인튜닝 1단계: TCN 레이어를 고정하고 FC만 먼저 학습하여
        안정적인 수렴 유도 — GRU의 freeze_gru()와 동일한 전략.
        """
        # Input Projection 동결
        for param in self.input_proj.parameters():
            param.requires_grad = False
        # TCN Blocks 동결
        for param in self.tcn_blocks.parameters():
            param.requires_grad = False

    def unfreeze_tcn(self) -> None:
        """TCN 블록과 Input Projection의 파라미터 동결을 해제한다.

        파인튜닝 2단계: 전체 파라미터를 낮은 학습률로 fine-tuning.
        """
        for param in self.input_proj.parameters():
            param.requires_grad = True
        for param in self.tcn_blocks.parameters():
            param.requires_grad = True

    def get_best_state(self) -> dict:
        """현재 모델 state_dict의 deep copy를 반환한다.

        조기종료(early stopping) 시 최적 가중치를 보존하기 위해 사용.
        GRU/LSTM과 동일한 방식.
        """
        return copy.deepcopy(self.state_dict())
