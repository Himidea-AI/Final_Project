# Emerging District 탭 정보량 고도화 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emerging District 탭에 시계열(8분기 history) + 16동 분포 비교를 추가해 정적 단일 카드 → 풍성한 정보 페이지로 고도화.

**Architecture:** Backend `EmergingResult` TypedDict 에 `quarter_history` + `peer_distribution` 두 필드 추가 → frontend `EmergingSignal` 동기화 → 신규 컴포넌트 2 (`PeerDistributionBar` + `EmergingPeerComparisonChart`) + 기존 `EmergingSignalCard` 재구조 + `PredictEmergingDistrictTab` 페이지 layout 재구조. Redis 캐시 키 v2 bump.

**Tech Stack:** Python (TypedDict, numpy), TypeScript, React 18, Recharts, Tailwind, Zustand.

**관련 spec:** `docs/superpowers/specs/2026-05-06-emerging-district-deep-dive-design.md`

**작업 컨텍스트:**
- 강민이 backend + frontend 일괄 진행 (백엔드 동료 협의 완료)
- 런타임 검증(uvicorn / 실 LLM 호출)은 강민 직접 — 자동 verification 은 unit test + tsc + prettier 만
- 4동 기준 — `sortByRanking` 으로 winner→4위 정렬 (직전 cycle 적용 완료)

---

## File Structure

| 파일 | 역할 | 행위 |
|------|------|------|
| `models/emerging_district/predict.py` | autoencoder 메인 predict + EmergingResult TypedDict | **modify** — TypedDict 두 필드 + 산출 로직 |
| `models/emerging_district/predict_fallback.py` | 4-tier fallback predict | **modify** — fallback 결과에 두 필드 (or null) 채움 |
| `models/interface.py` | predict + fallback 통합 | **modify (조건부)** — 두 필드 통과 여부 검증 |
| `frontend/src/types/index.ts` | EmergingSignal TypeScript interface | **modify** — 두 필드 추가 (optional) |
| `frontend/src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx` | 카드 안 mini bar — 본 동의 16동 분포 위치 | **create** |
| `frontend/src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx` | 페이지 상단 16동 horizontal bar | **create** |
| `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx` | 4동 카드 본체 | **modify** — sparkline + peer bar 추가, 게이지/RawChip 제거 |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx` | 페이지 컨테이너 | **modify** — layout 재구조, 헤더 chip strip |

**Redis 캐시 키 bump**: `predict.py` 또는 호출처에서 `emerging:v1:{...}` → `emerging:v2:{...}` (현재 캐시 키 패턴 grep 결과 0건 — 모듈 내 `_cache` dict 만 사용 중. Redis 미사용으로 보이며, 단 호출처 (`models/interface.py` 또는 backend node) 에서 캐시한다면 그쪽 키 bump).

---

## Task 1: Backend EmergingResult TypedDict 두 필드 추가

**Files:**
- Modify: `models/emerging_district/predict.py:24-31` (EmergingResult TypedDict)

- [ ] **Step 1: TypedDict 에 두 필드 추가**

```python
class EmergingResult(TypedDict):
    dong_code: str
    industry_code: str
    anomaly_score: float
    signal: str
    consecutive_anomaly_quarters: int
    summary: str
    is_mock: bool
    # 2026-05-06 추가:
    quarter_history: list[dict] | None  # [{quarter: "Q-7", anomaly_score: 0.31}, ...] 길이 8
    peer_distribution: dict | None      # {p25, p50, p75, p90, percentile_self, rank_in_total, total}
```

- [ ] **Step 2: predict_fallback.py 의 동일 결과 빌드 부분에서도 두 필드 None 으로 채움**

`models/emerging_district/predict_fallback.py` 의 `predict_fallback()` 함수 return dict 에 `quarter_history=None, peer_distribution=None` 추가 (산출 안 함, 단 schema 일치).

```python
return {
    "dong_code": dong_code,
    "industry_code": industry_code,
    "anomaly_score": float(score),
    "signal": signal,
    "consecutive_anomaly_quarters": consecutive,
    "summary": summary_text,
    "tier": tier,
    "raw": raw_dict,
    "is_mock": False,
    # 2026-05-06 추가:
    "quarter_history": None,
    "peer_distribution": None,
}
```

- [ ] **Step 3: pytest 통과 확인**

Run: `cd backend && pytest tests/test_emerging_district.py -v`
Expected: 기존 테스트 통과 (필드 추가는 optional 이라 호환).

- [ ] **Step 4: Commit**

```bash
git add models/emerging_district/predict.py models/emerging_district/predict_fallback.py
git commit -m "feat(emerging): EmergingResult 에 quarter_history + peer_distribution 필드 (schema only)

산출 로직은 다음 task. 일단 TypedDict 정의 + fallback default None 으로 schema 호환만 확보.
"
```

---

## Task 2: Frontend EmergingSignal TypeScript 동기화

**Files:**
- Modify: `frontend/src/types/index.ts:314-322` (EmergingSignal interface)

- [ ] **Step 1: 두 필드 추가**

```ts
export interface EmergingSignal {
  dong_code: string;
  industry_code: string;
  anomaly_score: number;
  signal: 'emerging' | 'declining' | 'normal';
  consecutive_anomaly_quarters: number;
  summary: string;
  tier: 'change_ix' | 'classifier' | 'b1_trend' | 'slope' | 'none';
  raw: Record<string, number | string>;
  is_mock?: boolean;
  // 2026-05-06 추가:
  quarter_history?: { quarter: string; anomaly_score: number }[] | null;
  peer_distribution?: {
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    percentile_self: number; // 0~100
    rank_in_total: number;   // 1-based
    total: number;
  } | null;
}
```

- [ ] **Step 2: tsc 통과 확인**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): EmergingSignal 에 quarter_history + peer_distribution 동기화

backend EmergingResult TypedDict 와 1:1 매핑. 둘 다 optional null — 단계적 rollout 안전.
"
```

---

## Task 3: Backend quarter_history 산출 로직

**Files:**
- Modify: `models/emerging_district/predict.py:147-220` (predict 함수 안)

- [ ] **Step 1: 8분기 anomaly_score 산출 헬퍼**

`predict.py` 안에 신규 함수 추가:

```python
def _compute_history_at_offset(
    df_dong_industry,
    model,
    scaler,
    threshold: float,
    window_size: int,
    q_offset: int,
) -> float | None:
    """q_offset 분기 전 시점에서 anomaly_score 산출.

    df_dong_industry: 동×업종 시계열 데이터 (이미 필터링됨)
    q_offset: 0=현재, 7=7분기 전
    """
    end_idx = len(df_dong_industry) - q_offset - 1
    if end_idx < window_size - 1:
        return None  # 데이터 부족
    window = df_dong_industry.iloc[end_idx - window_size + 1 : end_idx + 1]
    if len(window) < window_size:
        return None
    x = scaler.transform(window.values).astype("float32")
    x_t = torch.tensor(x).unsqueeze(0)
    with torch.no_grad():
        recon = model(x_t).squeeze(0)
    recon_error = float(((recon - x_t.squeeze(0)) ** 2).mean().item())
    return _anomaly_score(recon_error, threshold)
```

- [ ] **Step 2: predict() 함수 안에서 8분기 history 산출 호출**

기존 `predict()` 함수의 result dict 빌드 직전에 추가 (line ~217 근처):

```python
# 2026-05-06: 8 분기 시계열 history 산출
quarter_history: list[dict] = []
for offset in range(7, -1, -1):  # 7→0 (오름차순으로 표시)
    h_score = _compute_history_at_offset(group, model, scaler, threshold, window_size, offset)
    quarter_label = "현재" if offset == 0 else f"Q-{offset}"
    quarter_history.append({
        "quarter": quarter_label,
        "anomaly_score": h_score if h_score is not None else 0.0,
    })

# result 빌드 시 quarter_history 포함
result: EmergingResult = {
    # ... 기존 필드 ...
    "quarter_history": quarter_history,
    "peer_distribution": None,  # task 4 에서 채움
}
```

- [ ] **Step 3: 단위 테스트**

`backend/tests/test_emerging_district.py` 에 추가:

```python
def test_quarter_history_length_eight():
    """quarter_history 가 정확히 8 분기."""
    result = predict(dong_code=TEST_DONG, industry_code=TEST_INDUSTRY)
    assert "quarter_history" in result
    assert isinstance(result["quarter_history"], list)
    assert len(result["quarter_history"]) == 8
    assert result["quarter_history"][-1]["quarter"] == "현재"
    assert result["quarter_history"][0]["quarter"] == "Q-7"
    for entry in result["quarter_history"]:
        assert 0.0 <= entry["anomaly_score"] <= 1.0
```

Run: `cd backend && pytest tests/test_emerging_district.py::test_quarter_history_length_eight -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add models/emerging_district/predict.py backend/tests/test_emerging_district.py
git commit -m "feat(emerging): 8 분기 quarter_history 산출

기존 anomaly_score 로직을 q_offset 별로 반복 적용. 데이터 부족 분기는 0.0 fallback.
라벨: 'Q-7' ~ 'Q-1' + '현재'.
"
```

---

## Task 4: Backend peer_distribution 산출 로직

**Files:**
- Modify: `models/emerging_district/predict.py:147~ predict()`

- [ ] **Step 1: 16동 anomaly score 산출 + numpy quantile**

`predict.py` 안에 신규 함수:

```python
import numpy as np
from src.constants.mapo_dongs import MAPO_DONG_CODES  # 이미 존재 가정

def _compute_peer_distribution(
    industry_code: str,
    own_dong_code: str,
    own_score: float,
    df_all,  # 전체 dong×industry 데이터
    model,
    scaler,
    threshold: float,
    window_size: int,
) -> dict | None:
    """마포 16동 기준 anomaly 분포 산출."""
    peer_scores: list[float] = []
    for code in MAPO_DONG_CODES:
        sub = df_all[(df_all["dong_code"] == code) & (df_all["industry_code"] == industry_code)]
        if len(sub) < window_size:
            continue
        s = _compute_history_at_offset(sub, model, scaler, threshold, window_size, q_offset=0)
        if s is not None:
            peer_scores.append(s)

    if len(peer_scores) < 4:
        return None

    arr = np.array(peer_scores)
    quantiles = np.percentile(arr, [25, 50, 75, 90])

    sorted_desc = sorted(peer_scores, reverse=True)
    rank = next((i + 1 for i, s in enumerate(sorted_desc) if abs(s - own_score) < 1e-6), len(sorted_desc))
    percentile_self = (rank / len(peer_scores)) * 100

    return {
        "p25": float(quantiles[0]),
        "p50": float(quantiles[1]),
        "p75": float(quantiles[2]),
        "p90": float(quantiles[3]),
        "percentile_self": float(percentile_self),
        "rank_in_total": rank,
        "total": len(peer_scores),
    }
```

- [ ] **Step 2: predict() 안에서 호출 + result 채움**

```python
# 2026-05-06: 16동 분포 산출
peer_distribution = _compute_peer_distribution(
    industry_code=industry_code,
    own_dong_code=dong_code,
    own_score=score,
    df_all=df,  # 전체 데이터프레임
    model=model,
    scaler=scaler,
    threshold=threshold,
    window_size=window_size,
)

result["peer_distribution"] = peer_distribution
```

- [ ] **Step 3: 단위 테스트**

```python
def test_peer_distribution_quantiles():
    """peer_distribution 의 사분위가 단조 증가."""
    result = predict(dong_code=TEST_DONG, industry_code=TEST_INDUSTRY)
    pd = result.get("peer_distribution")
    if pd is None:
        pytest.skip("16동 데이터 부족")
    assert pd["p25"] <= pd["p50"] <= pd["p75"] <= pd["p90"]
    assert 1 <= pd["rank_in_total"] <= pd["total"]
    assert 0 <= pd["percentile_self"] <= 100
    assert pd["total"] >= 4
```

Run: `cd backend && pytest tests/test_emerging_district.py::test_peer_distribution_quantiles -v`
Expected: PASS (또는 skip — 16동 데이터 부족 시).

- [ ] **Step 4: Commit**

```bash
git add models/emerging_district/predict.py backend/tests/test_emerging_district.py
git commit -m "feat(emerging): 16 동 peer_distribution 산출 (사분위 + rank)

mapo 16 동 anomaly_score 산출 → numpy.percentile([25, 50, 75, 90]) + rank.
데이터 부족 동(<4) 시 None — frontend 가 graceful fallback.
"
```

---

## Task 5: Backend predict_fallback 두 필드도 함께 채움 (선택)

**Files:**
- Modify: `models/emerging_district/predict_fallback.py`

`predict_fallback.py` 는 4-tier fallback (change_ix → classifier → b1_trend → slope → none) 이라 시계열 자체가 없을 가능성. **현재 cycle 에서는 None 유지** (Task 1 에서 처리 완료).

다만 `change_ix` tier 의 경우 서울 공식 stage 가 분기별 stage 를 제공하므로 quarter_history 를 stage→score 매핑으로 채울 수 있음. 본 cycle 에서는 보류 (다음 cycle).

- [ ] **Step 1: 진행 안 함 (None 유지)**

Skip. Task 1 에서 이미 None 으로 schema 호환만 확보.

---

## Task 6: Frontend PeerDistributionBar 신규 컴포넌트

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * PeerDistributionBar — 카드 안 mini bar.
 * 16 동 anomaly_score 분포에서 본 동의 위치를 horizontal bar + dot 으로 시각화.
 *
 * 입력: peer_distribution (사분위 + rank) + ownScore (본 동) + seriesColor.
 * 출력: 좌(min=0) ─ 우(max=1) horizontal track + p25/p50/p75 사분위 tick + 본 동 dot + "16동 중 N위 (상위 X%)" 라벨.
 */

import type { EmergingSignal } from '../../../../types';

interface Props {
  peerDistribution: NonNullable<EmergingSignal['peer_distribution']>;
  ownScore: number;
  seriesColor: string;
}

export function PeerDistributionBar({ peerDistribution, ownScore, seriesColor }: Props) {
  const pct = (v: number) => Math.min(100, Math.max(0, v * 100));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
        <span>16동 분포</span>
        <span>
          {peerDistribution.rank_in_total} / {peerDistribution.total}위 · 상위{' '}
          {peerDistribution.percentile_self.toFixed(0)}%
        </span>
      </div>
      <div className="relative h-2 w-full rounded-full bg-secondary overflow-visible">
        {/* 사분위 tick (p25 / p50 / p75) */}
        {[peerDistribution.p25, peerDistribution.p50, peerDistribution.p75].map((q, i) => (
          <span
            key={i}
            aria-hidden
            className="absolute top-0 h-2 w-px bg-border"
            style={{ left: `${pct(q)}%` }}
          />
        ))}
        {/* p90 강조 tick */}
        <span
          aria-hidden
          className="absolute -top-0.5 h-3 w-0.5 bg-muted-foreground/60"
          style={{ left: `${pct(peerDistribution.p90)}%` }}
        />
        {/* 본 동 dot */}
        <span
          aria-hidden
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-card"
          style={{
            left: `${pct(ownScore)}%`,
            backgroundColor: seriesColor,
          }}
        />
      </div>
      <div className="flex justify-between text-[0.5rem] tabular-nums text-muted-foreground/70">
        <span>0</span>
        <span>0.5</span>
        <span>1.0</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

Run:
```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx
```
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx
git commit -m "feat(emerging): PeerDistributionBar 신규 — 16동 분포 안 본 동 위치 mini bar

좌(0) ~ 우(1) track + p25/p50/p75 tick + p90 강조 + 본 동 dot (seriesColor) + 'N위 / 상위 X%' 라벨.
"
```

---

## Task 7: Frontend EmergingPeerComparisonChart 신규 컴포넌트

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * EmergingPeerComparisonChart — 페이지 상단 16동 horizontal bar.
 *
 * 입력: 4동 emerging_signal[] + 첫 동의 peer_distribution (모두 동일 분포 가정).
 * 시각화: 16동 anomaly_score 오름차순 정렬 horizontal bar.
 *   - 4동(시뮬 입력) = SERIES_COLORS[idx] 강조
 *   - 12동(시뮬 외) = bg-muted 회색
 *   - 사분위 reference line (p25 / p50 / p75 / p90 vertical)
 *   - hover → 동 이름 + score tooltip
 *
 * 4동 외 12 동 score 는 backend 로부터 못 받음 (peer_distribution 은 quantile 만 제공).
 * 따라서 본 차트는 "4동 위치 + 사분위 가이드" 형태로 표시.
 */

import type { DistrictPredictionResult } from '../../../../types';
import { SERIES_COLORS } from '../../QuarterlyProjectionChart';

interface Props {
  dpredicts: DistrictPredictionResult[]; // 4 동 (sortByRanking 정렬)
}

export function EmergingPeerComparisonChart({ dpredicts }: Props) {
  // 첫 동의 peer_distribution 사용 (모두 같은 분포)
  const first = dpredicts.find((p) => p.emerging_signal?.peer_distribution);
  const peer = first?.emerging_signal?.peer_distribution;

  if (!peer) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        16동 분포 데이터 미수신
      </div>
    );
  }

  const pct = (v: number) => Math.min(100, Math.max(0, v * 100));

  // 4동 score 정렬 (오름차순 — 안정 → 변화 큼)
  const fourDongs = dpredicts
    .map((p, idx) => ({
      district: p.district,
      score: p.emerging_signal?.anomaly_score ?? 0,
      color: SERIES_COLORS[idx % SERIES_COLORS.length]!,
    }))
    .sort((a, b) => a.score - b.score);

  return (
    <div className="space-y-3">
      {/* 사분위 라벨 */}
      <div className="relative h-4">
        {[
          { v: peer.p25, label: 'P25' },
          { v: peer.p50, label: 'P50' },
          { v: peer.p75, label: 'P75' },
          { v: peer.p90, label: 'P90' },
        ].map(({ v, label }) => (
          <span
            key={label}
            className="absolute -top-0.5 -translate-x-1/2 text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground"
            style={{ left: `${pct(v)}%` }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* 본 차트 — track + 사분위 line + 4동 dot */}
      <div className="relative h-12 w-full rounded-2xl bg-secondary">
        {/* 사분위 vertical line */}
        {[peer.p25, peer.p50, peer.p75, peer.p90].map((v, i) => (
          <span
            key={i}
            aria-hidden
            className="absolute top-0 h-12 w-px bg-border"
            style={{ left: `${pct(v)}%` }}
          />
        ))}
        {/* 4 동 dot — 정렬 순으로 y 분산 (겹침 방지) */}
        {fourDongs.map((d, i) => (
          <div
            key={d.district}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{
              left: `${pct(d.score)}%`,
              top: `${20 + i * 20}%`,
            }}
            title={`${d.district} · ${(d.score * 100).toFixed(0)}점`}
          >
            <span
              className="block h-3.5 w-3.5 rounded-full border-2 border-card"
              style={{ backgroundColor: d.color }}
            />
            <span className="absolute left-1/2 top-full mt-0.5 -translate-x-1/2 whitespace-nowrap text-[0.5625rem] font-bold text-foreground">
              {d.district}
            </span>
          </div>
        ))}
      </div>

      <div className="flex justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
        <span>안정 ────────</span>
        <span>──────── 평소와 다름</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

Run:
```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx
```
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx
git commit -m "feat(emerging): EmergingPeerComparisonChart 신규 — 16동 분포 안 4동 위치

페이지 상단 풀와이드. 사분위 P25/P50/P75/P90 reference line + 4동 dot (SERIES_COLORS).
peer_distribution null 시 placeholder.
"
```

---

## Task 8: Frontend EmergingSignalCard 재구조

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx`

- [ ] **Step 1: import 정리 + sparkline 추가**

기존 import 에 `Sparkline` + `PeerDistributionBar` 추가:

```tsx
import { Sparkline } from './Sparkline';
import { PeerDistributionBar } from './PeerDistributionBar';
```

- [ ] **Step 2: 게이지 + RawChip 영역 제거**

기존 게이지 block (`<div className="space-y-6">` 안의 "평소와 다른 정도 게이지" 영역) 통째 삭제. RawChip 호출 라인도 제거.

- [ ] **Step 3: sparkline + peer bar 영역 추가**

신호등 + 변화도 점수 grid 아래에 다음 추가:

```tsx
{/* 8 분기 변화도 sparkline */}
{signal.quarter_history && signal.quarter_history.length > 0 && (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
      <span>최근 8분기 변화도</span>
      {(() => {
        const first = signal.quarter_history[0]?.anomaly_score ?? 0;
        const last = signal.quarter_history[signal.quarter_history.length - 1]?.anomaly_score ?? 0;
        const delta = last - first;
        const arrow = delta > 0.05 ? '↗' : delta < -0.05 ? '↘' : '→';
        const sign = delta >= 0 ? '+' : '';
        return (
          <span className="tabular-nums" style={{ color: seriesColor ?? 'var(--foreground)' }}>
            {arrow} {sign}{(delta * 100).toFixed(0)}%
          </span>
        );
      })()}
    </div>
    <Sparkline
      data={signal.quarter_history.map((q) => q.anomaly_score)}
      height={32}
    />
  </div>
)}

{/* 16동 분포 위치 */}
{signal.peer_distribution && (
  <PeerDistributionBar
    peerDistribution={signal.peer_distribution}
    ownScore={signal.anomaly_score}
    seriesColor={seriesColor ?? 'var(--primary)'}
  />
)}

{/* 자연어 요약 — 카드 하단 한 줄 */}
{signal.summary && (
  <p className="text-[0.6875rem] text-foreground leading-relaxed border-t border-border/50 pt-3">
    {signal.summary}
  </p>
)}
```

- [ ] **Step 4: 기존 RawChip 함수 + 호출 제거**

`RawChip` 컴포넌트 함수 + 카드 안 `<RawChip signal={signal} />` 호출 제거.

- [ ] **Step 5: tsc + prettier**

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx
```
Expected: 0 error.

- [ ] **Step 6: 기존 EmergingSignalCard.test.tsx 의 "신뢰도", "지하철" 같은 RawChip 의존 테스트 갱신/제거**

`grep -n "신뢰도\|지하철 ↑\|청년 +" frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx` 결과 있으면 해당 테스트 제거 또는 sparkline/peer-bar 테스트로 대체.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
git commit -m "refactor(emerging-card): 게이지·RawChip 제거 + sparkline · peer bar · summary 추가

- 평소와 다른 정도 게이지 제거 — 변화도 점수 박스 + sparkline 으로 대체 (중복 시각화 회피)
- tier 별 RawChip 제거 — 카드 단순화 (raw evidence 는 추후 hover popup 검토)
- 8 분기 sparkline + 트렌드 화살표 (↗ / ↘ / →) + Δ%
- PeerDistributionBar 통합 (16동 분포 안 본 동 위치)
- summary 자연어 카드 하단 한 줄
"
```

---

## Task 9: Frontend PredictEmergingDistrictTab 페이지 layout 재구조

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx`

- [ ] **Step 1: import 추가**

```tsx
import { EmergingPeerComparisonChart } from '../../charts/EmergingPeerComparisonChart';
```

- [ ] **Step 2: 헤더 chip strip 추가 (tier 분포 + 4동 종합)**

기존 `<h3>` 아래에 chip strip 추가:

```tsx
{/* tier 분포 + 4동 종합 chip strip */}
<div className="flex flex-wrap items-center gap-3 text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
  {(() => {
    const tierCount: Record<string, number> = {};
    const signalCount = { normal: 0, emerging: 0, declining: 0 };
    dpredicts.forEach((p) => {
      const s = p.emerging_signal;
      if (!s) return;
      tierCount[s.tier] = (tierCount[s.tier] ?? 0) + 1;
      signalCount[s.signal] = (signalCount[s.signal] ?? 0) + 1;
    });
    const TIER_LABEL: Record<string, string> = {
      change_ix: '공식',
      classifier: 'AI',
      b1_trend: '보조',
      slope: '보조',
      none: '검증중',
    };
    return (
      <>
        {Object.entries(tierCount).map(([k, v]) => (
          <span key={k}>
            {TIER_LABEL[k] ?? k} {v}
          </span>
        ))}
        <span className="text-border">·</span>
        <span className="text-success">🟢 안정 {signalCount.normal}</span>
        <span className="text-primary">🔵 신흥 {signalCount.emerging}</span>
        <span className="text-danger">🔴 쇠퇴 {signalCount.declining}</span>
      </>
    );
  })()}
</div>
```

- [ ] **Step 3: [1] 16동 비교 차트 섹션 추가**

기존 4동 카드 grid 위에 추가:

```tsx
{/* [1] 16동 변화도 비교 차트 */}
<div className="bg-card border border-border rounded-3xl p-6">
  <div className="mb-4 flex items-center gap-3">
    <h4 className="text-sm font-black uppercase tracking-widest text-muted-foreground">
      16 동 변화도 비교
    </h4>
    <span className="text-[0.5625rem] font-mono uppercase tracking-widest text-muted-foreground">
      anomaly_score 오름차순
    </span>
  </div>
  <EmergingPeerComparisonChart dpredicts={dpredicts} />
</div>
```

- [ ] **Step 4: tsc + prettier**

```
cd frontend && npx tsc --noEmit
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
```
Expected: 0 error.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
git commit -m "feat(emerging-tab): layout 재구조 — 16동 비교 차트 + tier 분포 chip strip

- 헤더에 tier 분포 chip (공식 N · AI N · 보조 N) + 4동 종합 (안정 N · 신흥 N · 쇠퇴 N)
- [1] 16동 변화도 비교 차트 (페이지 상단, EmergingPeerComparisonChart)
- [2] 4동 카드 grid (기존 — 카드 안엔 직전 task 에서 sparkline + peer bar 추가)
"
```

---

## Task 10: 시각 회귀 + 통합 검증

**Files:**
- 검증 only — 코드 변경 없음

- [ ] **Step 1: tsc 전체 통과**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 error.

- [ ] **Step 2: backend pytest 통과**

Run: `cd backend && pytest tests/test_emerging_district.py -v`
Expected: 모든 테스트 PASS (또는 16동 데이터 부족 시 skip).

- [ ] **Step 3: prettier 일괄**

Run:
```bash
cd frontend && npx prettier --write \
  src/types/index.ts \
  src/components/SimulationResult/dashboard/charts/PeerDistributionBar.tsx \
  src/components/SimulationResult/dashboard/charts/EmergingPeerComparisonChart.tsx \
  src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx \
  src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
```

- [ ] **Step 4: 강민 직접 시각 회귀**

uvicorn + npm run dev 띄운 후:
- `/dashboard/predict?sub=emerging_district` 접근
- [1] 16동 비교 차트가 페이지 상단 노출 확인
- 4 동 dot 이 SERIES_COLORS 색으로 강조
- 사분위 P25/P50/P75/P90 reference line 보임
- 4 동 카드 안 8분기 sparkline + 트렌드 화살표
- 4 동 카드 안 16동 분포 mini bar + 본 동 dot + "N위 (상위 X%)"
- 게이지 / RawChip 사라짐
- summary 카드 하단에 한 줄
- 헤더 tier 분포 + 신호 분포 chip 노출

- [ ] **Step 5: 회귀 없음 확인**

다른 탭들 (매출 예측 / 재무 / customer_flow / scenario / market) 색 일관성 그대로인지.

- [ ] **Step 6: (회귀 발견 시 fix commit, 없으면 skip)**

---

## Self-Review Note

이 plan 의 spec 커버리지:

| Spec 요구 | 구현 task |
|---------|---------|
| `quarter_history` 산출 | Task 3 |
| `peer_distribution` 산출 | Task 4 |
| Backend schema 두 필드 추가 | Task 1 |
| Backend predict_fallback null 호환 | Task 1 (Step 2) |
| Frontend types 동기화 | Task 2 |
| Frontend PeerDistributionBar 신규 | Task 6 |
| Frontend EmergingPeerComparisonChart 신규 | Task 7 |
| Frontend EmergingSignalCard 재구조 (sparkline + peer + summary, 게이지/RawChip 제거) | Task 8 |
| Frontend PredictEmergingDistrictTab layout 재구조 + 헤더 chip | Task 9 |
| Redis 캐시 키 bump | **N/A** — 코드 grep 결과 emerging 캐시 키 패턴 0건. 모듈 내 `_cache` dict 만 사용 중 (Redis 미사용). 호출처에서 캐시한다면 그쪽 별도 fix (해당 시 Task 추가) |
| 시각 회귀 검증 | Task 10 (강민 직접) |
| `top_drivers` (다음 cycle) | 미포함 — 의도적 보류 |

placeholder 0건. 타입 일치 (TypedDict ↔ TypeScript interface 1:1).

---

## 작업 흐름

```
Backend  → Task 1 (schema)
         → Task 3 (quarter_history)
         → Task 4 (peer_distribution)
         → Task 5 (fallback 보류)

Frontend → Task 2 (types 동기화)
         → Task 6 (PeerDistributionBar)
         → Task 7 (EmergingPeerComparisonChart)
         → Task 8 (EmergingSignalCard 재구조)
         → Task 9 (PredictEmergingDistrictTab layout)
         → Task 10 (시각 회귀 + 통합 검증)
```

Backend → Frontend 순. 단 Task 2 (types) 는 backend 완료 후 시작.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-emerging-district-deep-dive.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task + 두 단계 review (코드 작성 + 검증 분리). 9 task 라 한 task 끝날 때마다 강민 잠깐 확인 → 다음 task. 가장 안전.

**2. Inline Execution** — 현재 세션에서 일괄 실행. backend 4 task + frontend 5 task 묶어서 진행. 빠르지만 중간 검증 약함.

**Auto mode 가 활성** 이라 사용자 별도 지시 없으면 inline (2번) 으로 진행하겠습니다. 다른 방식 원하시면 알려주세요.
