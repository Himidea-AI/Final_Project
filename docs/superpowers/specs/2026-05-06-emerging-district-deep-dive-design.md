# Emerging District 탭 정보량 고도화 — Design Spec

작성일: 2026-05-06
담당: C1 (강민) — backend + frontend 일괄 진행 (백엔드 협의 완료)
관련 컴포넌트:
- `models/emerging_district/predict.py` / `predict_fallback.py`
- `backend/src/schemas/state.py` (또는 `simulation_output.py`) `EmergingSignal`
- `backend/src/database/redis_client.py` (캐시 키 bump)
- `frontend/src/types/index.ts` `EmergingSignal`
- `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx`
- 신규: `frontend/src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx`
- 신규: `frontend/src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx`

## 배경

`/dashboard/predict?sub=emerging_district` 단일 탭의 컨텐츠가 4동 grid 카드 1개뿐. 각 카드는 신호등 + 변화도 점수 + 게이지 + 자연어 요약 정도라 페이지 전체가 부실하게 느껴진다.

1. **시계열 정보 없음** — `anomaly_score` 가 단일 시점 스칼라. "최근 흐름이 어땠는지" 알 수 없음.
2. **상대적 비교 정보 없음** — 16동 중 본 동이 어디 위치하는지 (분포 quantile) 표시 없음.
3. **단일 카드 grid 만 노출** — 페이지 layout 자체가 단조. 다른 탭(매출 예측 / 재무 / 시나리오) 대비 정보 밀도 격차.

직전 cycle (2026-05-04) 에서 `RawChip` + `tier 배지` + `변화 1위` 배지 등이 들어갔지만 페이지 전체 구조는 그대로.

## 목표

- 백엔드 `EmergingSignal` 에 **시계열(`quarter_history`)** + **분포(`peer_distribution`)** 2 필드 추가
- 페이지 layout 재구조: `[1] 16동 변화도 비교 차트` (신규) + `[2] 4동 카드 grid` (sparkline + peer 위치 신규)
- 카드 안 게이지 + RawChip 제거 (정보 통합으로 대체)
- 캐시 키 bump (Redis emerging cache → v2)

비목표:
- autoencoder 재학습 (X — 기존 forward 8 분기 반복만)
- `predict_fallback.py` 4-tier 로직 자체 변경 (X)
- driver/feature attribution 추가 (다음 cycle, 이번엔 보류 — 도메인 정의 별도 회의 필요)

## 변경 파일 (8개)

| 레이어 | 파일 | 변경 내용 |
|--------|------|---------|
| Model | `models/emerging_district/predict.py` | `quarter_history` (8분기) + `peer_distribution` (16동 quantile) 산출 로직 추가 |
| Model fallback | `models/emerging_district/predict_fallback.py` | 4-tier fallback 시에도 두 필드 채움 (or null) |
| Backend schema | `backend/src/schemas/state.py` (또는 `simulation_output.py`) | `EmergingSignal` 에 `quarter_history`, `peer_distribution` 추가 |
| Backend cache | `backend/src/database/redis_client.py` 또는 emerging 호출처 | 캐시 키 v1 → v2 bump |
| Frontend types | `frontend/src/types/index.ts` | `EmergingSignal` 동기화 |
| Frontend tab | `PredictEmergingDistrictTab.tsx` | layout 재구조 — `[1]` 16동 비교 + `[2]` 4동 카드 grid |
| Frontend card | `EmergingSignalCard.tsx` | sparkline + peer 위치 + summary 추가, 게이지/RawChip 제거 |
| Frontend chart 신규 | `EmergingPeerComparisonChart.tsx` | 16동 horizontal bar (anomaly_score 정렬, 4동 강조) |
| Frontend mini 신규 | `PeerDistributionBar.tsx` | 카드 안 mini bar — 본 동의 16동 분포 위치 |

## Backend 구현 — 2 필드 산출

### `quarter_history: { quarter: string, anomaly_score: number }[]`

길이 8 (최근 8분기). 기존 `anomaly_score` 산출 로직(autoencoder reconstruction error → 정규화)을 8 분기 시점별로 반복 적용.

```python
# predict.py 내 EmergingResult 빌드 시
quarter_history = []
for q_offset in range(7, -1, -1):  # 7분기 전 → 0분기 (현재)
    quarter_score = _compute_anomaly_at(dong_code, industry_code, q_offset)
    quarter_history.append({
        "quarter": f"Q-{q_offset}" if q_offset > 0 else "현재",
        "anomaly_score": quarter_score,
    })
```

산출 비용: 기존 anomaly 호출 로직 8회 반복. 동×업종 1조합당 ~수십 ms.

### `peer_distribution: { p25: float, p50: float, p75: float, p90: float, percentile_self: float, rank_in_total: int, total: int }`

마포 16동 anomaly_score 분포에서 본 동 위치.

```python
import numpy as np
peer_scores = [_compute_anomaly_at(d, industry_code, 0) for d in MAPO_16_DONG_CODES]
own_score = anomaly_score  # 이미 산출한 본 동 score
quantiles = np.percentile(peer_scores, [25, 50, 75, 90])
sorted_desc = sorted(peer_scores, reverse=True)
rank = sorted_desc.index(own_score) + 1  # 1-based
percentile_self = (rank / len(peer_scores)) * 100

peer_distribution = {
    "p25": float(quantiles[0]),
    "p50": float(quantiles[1]),
    "p75": float(quantiles[2]),
    "p90": float(quantiles[3]),
    "percentile_self": percentile_self,  # 0~100, 낮을수록 anomaly 큼
    "rank_in_total": rank,
    "total": len(peer_scores),
}
```

산출 비용: 16동 anomaly 호출 1회씩 = ~16 × 수십 ms = ~1초. 캐시 미적중 시에만 (적중 시 0).

### Redis 캐시 키 bump

기존 emerging 캐시 키 패턴 (예: `emerging:v1:{dong_code}:{industry_code}`) → `emerging:v2:{dong_code}:{industry_code}`. 새 schema 호환성 유지.

### Backend schema 추가

```python
# backend/src/schemas/state.py (또는 simulation_output.py)
class EmergingSignal(BaseModel):
    dong_code: str
    industry_code: str
    anomaly_score: float
    signal: Literal["emerging", "declining", "normal"]
    consecutive_anomaly_quarters: int
    summary: str
    tier: Literal["change_ix", "classifier", "b1_trend", "slope", "none"]
    raw: dict[str, Any]
    is_mock: bool = False
    # 신규 (2026-05-06):
    quarter_history: list[dict] | None = None
    peer_distribution: dict | None = None
```

## Frontend 구현 — 페이지 layout 재구조

### `[1] 16동 변화도 비교 차트` — 페이지 상단 (신규)

`EmergingPeerComparisonChart.tsx`:
- 입력: `simResult.district_predictions[].emerging_signal` 4동 + `peer_distribution` (각 동 동일 분포)
- 시각화: horizontal bar, 16동 anomaly_score 오름차순 정렬
- 4동(시뮬 입력) 색 = `SERIES_COLORS[idx]` (winner→4위 매핑)
- 12동(시뮬 외) 색 = `bg-muted` (회색)
- 사분위 reference line (p25 / p50 / p75 / p90 vertical line)
- hover → 동 이름 + score tooltip
- height: ~280px, full width

### `[2] 4동 카드 grid` — `EmergingSignalCard.tsx` 재구조

| 영역 | Before | After |
|------|--------|-------|
| 헤더 (동 이름 + tier 배지 + 변화 1위) | 유지 | 유지 |
| 신호등 + 변화도 점수 (grid-cols-2) | 유지 | 유지 |
| **8분기 sparkline** | 없음 | **신규** — `Sparkline.tsx` 재사용, 트렌드 화살표 (↗ / ↘ / →) + Δ% |
| **16동 분포 위치** | 없음 | **신규** — `PeerDistributionBar.tsx` (mini horizontal bar + dot) + "16동 중 N위" |
| 자연어 요약 | tier별 RawChip | **summary 한 줄로 통일** (tier 의 raw evidence 는 hover popup 으로 보존) |
| 게이지 (`평소와 다른 정도`) | 유지 | **제거** (변화도 점수 박스 + sparkline 으로 대체, 중복 시각화 회피) |

### `PeerDistributionBar.tsx` (신규)

```tsx
interface Props {
  peerDistribution: PeerDistribution;
  ownScore: number;
  seriesColor: string;
}
// 시각화: bg-secondary horizontal bar (h-2)
//   - 좌(min) ─ 우(max) 0~1
//   - 사분위 작은 tick (p25 / p50 / p75)
//   - 본 동 dot (seriesColor)
//   - 우측 작은 텍스트: "16동 중 N위 (상위 X%)"
```

### 페이지 헤더 — tier 분포 + 4동 종합

```tsx
<header className="flex justify-between">
  <h3 className="text-xl font-black italic">
    <Sparkles /> 동별 상권 조기감지 신호
  </h3>
  <div className="flex gap-3">
    {/* tier 분포 chip strip */}
    <chip>공식 데이터 N</chip>
    <chip>AI 판정 N</chip>
    <chip>보조 신호 N</chip>
    {/* 4동 종합 chip */}
    <chip>🟢 안정 N · 🔵 신흥 N · 🔴 쇠퇴 N</chip>
  </div>
</header>
```

### 디자인 토큰 정합

- **퐁당퐁당 룰**: 페이지 outer = bg-background / `[1]` 16동 차트 outer = bg-card rounded-3xl / `[2]` 4동 카드 outer = bg-card / 카드 안 sparkline·peer = bg-secondary (cool gray)
- **SERIES_COLORS**: 4동 winner→4위 색 매핑 (`sortByRanking` — 직전 cycle 적용 완료)
- **카드 form**: `MarketTab` 5 카드와 같은 pattern (`bg-card border rounded-3xl p-5`)

## Edge cases

| 케이스 | 동작 |
|--------|------|
| `quarter_history` null (백엔드 미수신) | sparkline 영역 hide |
| `peer_distribution` null | 카드 안 분포 위치 영역 hide + `[1]` 차트 placeholder ("16동 분포 데이터 미수신") |
| 4동 중 일부 emerging_signal null | 해당 카드 placeholder ("상권 조기감지 신호 미수신") — 기존 동작 유지 |
| `quarter_history` 길이 < 8 | 받은 만큼만 sparkline 그림 (1~7분기) |
| `peer_distribution.total` < 16 | 분포 차트 + peer bar 모두 받은 동 수 기준 표시 |

## 캐시 무효화 전략

- 기존 cache 키 v1 그대로 유지 (옛 응답 받는 frontend 가 새 필드 미존재 시 graceful fallback)
- 새 cache 키 v2 부터 신규 필드 포함
- frontend 는 두 필드 모두 optional (null 허용) 처리 — 단계적 rollout 안전

## Verification

| 검증 | 방법 |
|------|------|
| Backend schema | `pytest backend/tests/test_emerging_district.py` (기존 + 새 필드 추가 테스트) |
| Frontend types | `cd frontend && npx tsc --noEmit` |
| 시각 회귀 | 강민 직접 — `/dashboard/predict?sub=emerging_district` 페이지 hard refresh 후 layout 확인 |
| 4동 색 일관성 | 매출 곡선 / 폐업률 추이 / BEP / 본 페이지 4동 카드 색 동일 |
| Edge cases | mock simResult (일부 동 null) 로 placeholder 동작 확인 |

## 다음 cycle 보류 항목

- `top_drivers` 추가 (driver feature attribution) — 도메인 룰 정의 별도 회의 필요
- consecutive_anomaly_quarters 의미 정합 (현재 sliding window 기반 → per-quarter 기반 재정의) — 2026-05-04 spec 에 별도 작업으로 정의됨
- autoencoder 가중치 재학습 — 현재 forward only

## 작업 순서

1. Backend `predict.py` 두 필드 산출 로직 추가
2. Backend `predict_fallback.py` 두 필드 (or null) 채움
3. Backend schema (`state.py` / `simulation_output.py`) 두 필드 추가
4. Redis 캐시 키 bump
5. `pytest` 통과 확인
6. Frontend `types/index.ts` 동기화
7. Frontend `PeerDistributionBar.tsx` + `EmergingPeerComparisonChart.tsx` 신규 컴포넌트 작성
8. Frontend `EmergingSignalCard.tsx` 재구조 (sparkline + peer bar 추가, 게이지/RawChip 제거)
9. Frontend `PredictEmergingDistrictTab.tsx` layout 재구조 + 헤더 chip strip
10. `tsc --noEmit` + prettier 통과
11. 시각 회귀 확인
12. commit 분리 (backend / frontend types / frontend new components / frontend tab restructure)
