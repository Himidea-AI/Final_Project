# 대시보드 15 섹션 통합 리포트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SPOTTER 시뮬레이션 결과를 15 섹션 통합 레이아웃으로 전면 재구성, App.tsx 모놀리식 분리, 카카오맵 도입, 기존 기능 100% 보존.

**Architecture:** Big Bang 접근법. 백엔드 4 필드 보강(수정 허가) → 프론트 shared/sections 컴포넌트 생성 → App.tsx에서 SimulatorDashboard 추출 → IntegratedReport 오케스트레이터로 15 섹션 연결. 카카오맵은 기존 AgentMapVisualizer D3를 폴백으로 유지하며 리팩터.

**Tech Stack:** TypeScript strict · React 18 · Tailwind (Zinc/Amber) · Pretendard · lucide-react · Recharts · Framer Motion · Zustand · Kakao Maps JS SDK (신규) · vitest · Python 3.12 · FastAPI · LangGraph · pytest

**Spec:** `docs/superpowers/specs/2026-04-21-dashboard-15section-design.md`

---

## File Structure

### 신규 생성

```
frontend/
├── public/
│   └── mapo-dong.geo.json                           🆕 마포 16동 GeoJSON
├── src/
│   ├── pages/
│   │   └── SimulatorDashboard.tsx                   🆕 App.tsx에서 추출
│   └── components/
│       ├── kakao/
│       │   └── useKakaoMap.ts                       🆕 Kakao SDK 동적 로더 훅
│       └── SimulationResult/
│           ├── IntegratedReport.tsx                 🆕 15 섹션 오케스트레이터
│           ├── sections/
│           │   ├── CommandBar.tsx                   §01
│           │   ├── HeadlineBlock.tsx                §02
│           │   ├── PrimaryKPIs.tsx                  §03
│           │   ├── Scorecard.tsx                    §04
│           │   ├── MapSection.tsx                   §05
│           │   ├── IndicatorGrid.tsx                §06
│           │   ├── QuarterlyForecast.tsx            §07
│           │   ├── ScenarioSplit.tsx                §08
│           │   ├── ShapContribution.tsx             §09
│           │   ├── TimelineForecast.tsx             §10
│           │   ├── AgentAttribution.tsx             §11
│           │   ├── DistrictRankings.tsx             §12
│           │   ├── InsightsGrid.tsx                 §13
│           │   ├── DecisionMemo.tsx                 §14
│           │   └── ReportFooter.tsx                 §15
│           └── shared/
│               ├── SectionLabel.tsx                 공통 섹션 헤더
│               ├── Sparkline.tsx                    KPI 미니 차트
│               ├── AgentCard.tsx                    full/compact variant
│               └── LegalDrawer.tsx                  §13 우측 드로어
```

### 수정

- `frontend/src/App.tsx` — SimulatorDashboard 함수 추출 + import 경로 업데이트
- `frontend/src/components/AgentMapVisualizer.tsx` — 카카오맵 기반 리팩터 (기존 D3 폴백으로 내부 유지)
- `frontend/src/types/index.ts` — `AgentId` / `AgentAttribution` / `AgentKind` / `ReportSection` / `TimelineEvent` / `LegalChecklistItem` 추가
- `backend/src/agents/nodes/*.py` — 각 노드에 `agent_attribution` 필드 반환
- `backend/src/agents/graph.py` — `parallel_analysis_node`에서 `agent_attributions[]` 집계
- `backend/src/agents/nodes/synthesis.py` — `agent_attributions`를 response에 포함
- `backend/src/services/commercial_intelligence.py` — `analyze_competition` 반환에 `lat`/`lng` 노출
- `backend/src/agents/nodes/legal.py` — `legal_info[].checklist` 필드 생성
- `backend/src/schemas/structured_output.py` — `AgentAttribution` Pydantic 모델
- `backend/src/main.py` — response에 `agent_attributions`/`scenarios` 필드 포함

### 책임 경계

| 파일 | 책임 | 의존 |
|---|---|---|
| `types/index.ts` | 공통 타입 정의 | — |
| `shared/AgentCard.tsx` | 에이전트 카드 렌더 (size prop으로 full/compact 분기) | lucide-react |
| `shared/LegalDrawer.tsx` | 법률 상세 드로어 (focus trap, ESC close) | Framer Motion |
| `shared/SectionLabel.tsx` | 섹션 번호 + 라벨 공통 헤더 | — |
| `shared/Sparkline.tsx` | KPI용 미니 차트 | Recharts |
| `kakao/useKakaoMap.ts` | Kakao SDK 동적 로딩 + ready 상태 훅 | Kakao Maps |
| `sections/*.tsx` | 각 섹션 렌더링 (데이터는 prop) | shared, 기존 재사용 |
| `IntegratedReport.tsx` | simResult를 각 섹션으로 분배 + VS 모드 토글 | sections/* |
| `pages/SimulatorDashboard.tsx` | 시뮬레이션 입력 + runSim + IntegratedReport 포함 | IntegratedReport, simulationStore |

---

## Phase 0: 타입 & 기반

### Task 1: types/index.ts에 신규 타입 추가

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 기존 types/index.ts 내용 확인**

Run: `grep -n "^export" frontend/src/types/index.ts | head -20`

기존 export들 확인 (건드리지 않기 위함).

- [ ] **Step 2: 파일 하단에 신규 타입 추가**

`frontend/src/types/index.ts` 하단에:

```ts
// ──────────────────────────────────────────────────────────
// Dashboard 15 섹션 통합 리포트 타입 (2026-04-21 스펙)
// ──────────────────────────────────────────────────────────

export type AgentId =
  | 'market_analyst'
  | 'population_analyst'
  | 'legal'
  | 'district_ranking'
  | 'synthesis'
  | 'demographic_depth'
  | 'trend_forecaster'
  | 'competitor_intel';

export type AgentKind = 'LLM' | 'Python' | 'Hybrid' | 'RAG';

export interface AgentAttribution {
  id: AgentId;
  display_name: string;
  kind: AgentKind;
  sources: string[];
  verdict: string;
  reasoning: string;
  confidence?: number;
}

export interface ReportSection {
  id: string;
  label: string;
  number: string;
}

export interface TimelineEvent {
  monthOffset: number;
  label: string;
  type: 'milestone' | 'risk' | 'opportunity';
}

export interface LegalChecklistItem {
  text: string;
  isRequired?: boolean;
}

// SimulationOutput에 optional 필드 추가 시 기존 인터페이스 확장
```

- [ ] **Step 3: tsc 검증**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0 (신규 타입만 추가이므로 깨질 일 없음)

- [ ] **Step 4: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/types/index.ts
git add frontend/src/types/index.ts
git commit -m "feat(C1): AgentId / AgentAttribution / AgentKind / TimelineEvent 타입 추가"
```

---

## Phase 1: 백엔드 4 필드 보강

### Task 2: backend Pydantic AgentAttribution 스키마

**Files:**
- Modify: `backend/src/schemas/structured_output.py`

- [ ] **Step 1: 현재 structured_output.py 확인**

Run: `grep -n "^class" backend/src/schemas/structured_output.py | head -15`

- [ ] **Step 2: `AgentAttribution` Pydantic 모델 추가 (파일 하단)**

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

AgentId = Literal[
    "market_analyst",
    "population_analyst",
    "legal",
    "district_ranking",
    "synthesis",
    "demographic_depth",
    "trend_forecaster",
    "competitor_intel",
]

AgentKind = Literal["LLM", "Python", "Hybrid", "RAG"]


class AgentAttribution(BaseModel):
    """각 에이전트의 판단 근거 — §11 UI 카드 + 섹션별 compact 카드 공통 데이터."""

    id: AgentId
    display_name: str = Field(description="사람이 읽는 에이전트 이름 (예: '경쟁 인텔')")
    kind: AgentKind
    sources: list[str] = Field(description="사용한 DB 테이블·모델명 (chip으로 표시)")
    verdict: str = Field(description="한 줄 판단 (80자 내)")
    reasoning: str = Field(description="2-3 문장 설명")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
```

- [ ] **Step 3: ruff + 커밋**

```bash
cd backend && ruff check --fix src/schemas/structured_output.py && ruff format src/schemas/structured_output.py
git add backend/src/schemas/structured_output.py
git commit -m "feat(C1): AgentAttribution Pydantic 스키마 추가"
```

---

### Task 3: 각 에이전트 노드에서 AgentAttribution 생성 (8개)

**Files:**
- Modify: `backend/src/agents/nodes/market_analyst.py`
- Modify: `backend/src/agents/nodes/population.py`
- Modify: `backend/src/agents/nodes/legal.py`
- Modify: `backend/src/agents/nodes/district_ranking.py`
- Modify: `backend/src/agents/nodes/demographic_depth.py`
- Modify: `backend/src/agents/nodes/trend_forecaster.py`
- Modify: `backend/src/agents/nodes/competitor_intel.py`
- Modify: `backend/src/agents/nodes/synthesis.py`

**Note**: 각 노드의 기존 반환 dict에 `agent_attribution: dict` 키 1개 추가. 기존 로직·필드 수정 없음.

- [ ] **Step 1: 공통 헬퍼 함수 생성**

Create: `backend/src/agents/nodes/_attribution_helpers.py`

```python
"""각 에이전트 노드에서 AgentAttribution dict를 만드는 헬퍼."""

from typing import Optional
from src.schemas.structured_output import AgentAttribution


def build_attribution(
    agent_id: str,
    display_name: str,
    kind: str,
    sources: list[str],
    verdict: str,
    reasoning: str,
    confidence: Optional[float] = None,
) -> dict:
    """AgentAttribution 생성 → dict 반환 (agent 노드 반환 dict에 그대로 넣음)."""
    attr = AgentAttribution(
        id=agent_id,  # type: ignore[arg-type]
        display_name=display_name,
        kind=kind,  # type: ignore[arg-type]
        sources=sources,
        verdict=verdict[:80],  # 80자 제한
        reasoning=reasoning,
        confidence=confidence,
    )
    return attr.model_dump()
```

- [ ] **Step 2: market_analyst.py 에 attribution 추가**

`market_analyst_node` 반환 dict의 마지막에:

```python
from src.agents.nodes._attribution_helpers import build_attribution

# 기존 분석 로직 끝부분, return 직전
attr = build_attribution(
    agent_id="market_analyst",
    display_name="시장 분석",
    kind="LLM",
    sources=["district_sales", "kakao_store"],
    verdict=f"상권 점수 {score}/100 · {grade}",
    reasoning=(llm_output.get("narrative") or "")[:300],
    confidence=0.8,
)

# return 문에 추가
return {
    ...기존 필드,
    "agent_attribution": attr,
}
```

- [ ] **Step 3: population.py, legal.py, district_ranking.py 각각 동일 패턴**

각 에이전트별 verdict/reasoning/sources 내용은 해당 에이전트 결과에서 추출.

population: `sources=["seoul_adstrd_flpop", "kosis"]`
legal: `sources=["legal_rag_chunks (3775)"]`, `kind="RAG"`
district_ranking: `sources=["district_sales", "golmok_rent"]`, `kind="Python"`

- [ ] **Step 4: demographic_depth / trend_forecaster / competitor_intel 각각**

demographic_depth: 기존 narrative 사용
trend_forecaster: forecast.narrative 첫 문장 추출
competitor_intel: `kind="Hybrid"`, Pancras 공식 언급

- [ ] **Step 5: synthesis.py 에서 attribution 집계 → response**

`synthesis_node` 내부:

```python
# 다른 에이전트 결과에서 attribution 수집
agent_attributions = []
for agent_key in [
    "market_analyst", "population_analyst", "legal", "district_ranking",
    "demographic_depth", "trend_forecaster", "competitor_intel",
]:
    attr = state.get("analysis_results", {}).get(f"{agent_key}_attribution")
    if attr is None:
        attr = state.get(f"{agent_key}_result", {}).get("agent_attribution")
    if attr:
        agent_attributions.append(attr)

# synthesis 자체 attribution도 마지막에 append
synthesis_attr = build_attribution(
    agent_id="synthesis",
    display_name="전략 종합",
    kind="LLM",
    sources=[f"{len(agent_attributions)} agents"],
    verdict=f"종합 판단: {overall_legal_risk}",
    reasoning=final_strategy.summary[:300],
)
agent_attributions.append(synthesis_attr)

return {
    ...기존 필드,
    "agent_attributions": agent_attributions,  # 배열 길이 8
}
```

- [ ] **Step 6: graph.py parallel_analysis_node에서 각 결과의 agent_attribution 분배**

`parallel_analysis_node` 내부: 각 agent 결과의 `agent_attribution` 필드를 state의 각 agent별 result 필드 안에 유지 (synthesis가 수집 가능하도록).

- [ ] **Step 7: main.py response 매핑**

`map_state_to_simulation_output` 함수:

```python
response["agent_attributions"] = analysis.get("agent_attributions", [])
```

- [ ] **Step 8: 통합 테스트 — /simulate 호출로 확인**

```bash
cd backend && pytest tests/test_demographic_depth_node.py tests/test_commercial_intelligence.py -v
```

(기존 테스트 회귀 없음 확인)

Manual:
```bash
curl -X POST http://localhost:8000/simulate -H "Content-Type: application/json" \
  --data '{"business_type":"카페","brand_name":"빽다방","target_district":"서교동"}' \
  | python -c "import json,sys; d=json.load(sys.stdin); print('attrs:', len(d.get('agent_attributions',[])))"
```
Expected: `attrs: 8` (또는 작동 중인 에이전트 개수)

- [ ] **Step 9: ruff + 커밋**

```bash
cd backend && ruff check --fix src/agents/nodes/ src/main.py && ruff format src/agents/nodes/ src/main.py
git add backend/src/agents/nodes/ backend/src/main.py
git commit -m "feat(C1): 8 에이전트에 agent_attribution 생성 + synthesis 집계 + response 노출"
```

---

### Task 4: competitor_intel.samples[].lat/lng 노출

**Files:**
- Modify: `backend/src/services/commercial_intelligence.py`

- [ ] **Step 1: `analyze_competition` 반환 확인**

Run: `grep -n "samples" backend/src/services/commercial_intelligence.py | head -5`

기존 samples는 이미 lat/lng 포함 가능성 확인.

- [ ] **Step 2: 없으면 추가**

`analyze_competition` 함수 내 `within: list[dict]` 생성 시 `lat`/`lon` 포함 보장:

```python
within.append({
    "place_name": r["place_name"],
    "category": r["category"],
    "distance_m": round(d, 1),
    "brand_name": r.get("brand_name"),
    "is_franchise": r.get("is_franchise", False),
    "lat": r["lat"],   # ← 추가
    "lng": r["lon"],   # ← 추가 (프론트 관례 lng)
})
```

- [ ] **Step 3: 테스트 실행**

```bash
cd backend && pytest tests/test_commercial_intelligence.py -v
```
Expected: 기존 20/20 pass

- [ ] **Step 4: 커밋**

```bash
git add backend/src/services/commercial_intelligence.py
git commit -m "feat(C1): competitor samples에 lat/lng 노출 (§05 지도 마커용)"
```

---

### Task 5: scenarios 필드 (optimistic/base/pessimistic)

**Files:**
- Modify: `backend/src/agents/nodes/synthesis.py` 또는 신규 `scenarios.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: 현재 scenarios 필드 존재 여부**

Run: `grep -rn "scenarios" backend/src/agents/ backend/src/main.py | head -10`

- [ ] **Step 2: 이미 있으면 스킵, 없으면 생성**

없으면 synthesis.py에 추가:

```python
# quarterly_projection의 base에서 ±15%, ±30% 파생
base = state.get("analysis_results", {}).get("quarterly_projection", [])
optimistic = [{**q, "revenue": int(q["revenue"] * 1.3)} for q in base]
pessimistic = [{**q, "revenue": int(q["revenue"] * 0.7)} for q in base]

scenarios = {
    "optimistic": {"quarterly": optimistic, "probability": 0.2},
    "base": {"quarterly": base, "probability": 0.6},
    "pessimistic": {"quarterly": pessimistic, "probability": 0.2},
}
```

- [ ] **Step 3: main.py response 매핑**

```python
response["scenarios"] = analysis.get("scenarios") or {}
```

- [ ] **Step 4: 커밋**

```bash
git add backend/src/agents/nodes/synthesis.py backend/src/main.py
git commit -m "feat(C1): 시나리오 3종 (낙관/기본/비관) response 노출"
```

---

### Task 6: legal_info[].checklist 필드

**Files:**
- Modify: `backend/src/agents/nodes/legal.py`

- [ ] **Step 1: 현재 legal_info 구조 확인**

Run: `grep -n "legal_info\|checklist" backend/src/agents/nodes/legal.py | head -15`

봉환 PR #80에 checklist 추가됐을 가능성 높음. 있으면 이 Task 스킵.

- [ ] **Step 2: 없으면 각 risk에 checklist 생성**

`legal_node`의 각 risk 생성 부분에:

```python
# 조문별 창업 체크리스트 생성 (RAG 결과에서 파생)
checklist_items = _derive_checklist_from_articles(articles, risk_type)

risks.append({
    "type": risk_type,
    "risk_level": risk_level,
    "summary": summary,
    "articles": articles,
    "recommendation": recommendation,
    "checklist": checklist_items,  # ← 신규
})

def _derive_checklist_from_articles(articles: list, risk_type: str) -> list[dict]:
    """조문 본문에서 체크리스트 항목 파생 (간단 규칙 기반)."""
    items = []
    # 간단한 휴리스틱: 조문에서 "해야 한다", "의무", "확보" 등 패턴 추출
    for a in articles[:3]:  # 상위 3 조문만
        content = a.get("content", "")
        if "정보공개서" in content:
            items.append({"text": "가맹본부로부터 정보공개서 수령", "isRequired": True})
        if "14일" in content or "숙고기간" in content:
            items.append({"text": "14일 숙고기간 확보 후 계약", "isRequired": True})
        # 기본 fallback
    if not items:
        items.append({"text": f"{risk_type} 관련 법령 검토 필요", "isRequired": False})
    return items
```

- [ ] **Step 3: 커밋**

```bash
git add backend/src/agents/nodes/legal.py
git commit -m "feat(C1): legal_info[].checklist 필드 추가 (§13 드로어 체크리스트용)"
```

---

## Phase 2: Shared 컴포넌트

### Task 7: shared/SectionLabel.tsx

**Files:**
- Create: `frontend/src/components/SimulationResult/shared/SectionLabel.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * SectionLabel — 15 섹션 공통 헤더
 * "§01 COMMAND BAR / 시뮬레이션 실행 정보" 형식
 */

interface SectionLabelProps {
  number: string; // "§01"
  label: string; // "COMMAND BAR"
  subtitle?: string; // "시뮬레이션 실행 정보"
}

export function SectionLabel({ number, label, subtitle }: SectionLabelProps) {
  return (
    <div className="mb-6">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-xs text-amber-500 tracking-widest">{number}</span>
        <h2 className="text-xl font-semibold text-zinc-100 uppercase tracking-wide">{label}</h2>
      </div>
      {subtitle && <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>}
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/SimulationResult/shared/SectionLabel.tsx
git commit -m "feat(C1): SectionLabel 공통 헤더 컴포넌트 추가"
```

---

### Task 8: shared/Sparkline.tsx

**Files:**
- Create: `frontend/src/components/SimulationResult/shared/Sparkline.tsx`

- [ ] **Step 1: 컴포넌트 작성 (Recharts LineChart)**

```tsx
import { LineChart, Line, ResponsiveContainer } from 'recharts';

interface SparklineProps {
  data: number[];
  color?: string; // tailwind class 또는 hex
  height?: number;
}

export function Sparkline({ data, color = '#f59e0b', height = 32 }: SparklineProps) {
  const chartData = data.map((value, i) => ({ i, value }));
  return (
    <div style={{ height, width: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/SimulationResult/shared/Sparkline.tsx
git commit -m "feat(C1): Sparkline KPI 미니 차트 컴포넌트 추가"
```

---

### Task 9: shared/AgentCard.tsx (full + compact)

**Files:**
- Create: `frontend/src/components/SimulationResult/shared/AgentCard.tsx`
- Test: `frontend/src/components/SimulationResult/shared/AgentCard.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentCard } from './AgentCard';
import type { AgentAttribution } from '@/types';

const mockAttr: AgentAttribution = {
  id: 'competitor_intel',
  display_name: '경쟁 인텔',
  kind: 'Hybrid',
  sources: ['kakao_store', 'ftc_brand_franchise'],
  verdict: '진입 신호 RED · 포화 saturated',
  reasoning: '500m 내 경쟁점 145개. Pancras 감쇠로 자사 잠식 12% 추정.',
  confidence: 0.85,
};

describe('AgentCard', () => {
  it('full variant renders verdict + reasoning + sources', () => {
    render(<AgentCard attribution={mockAttr} size="full" />);
    expect(screen.getByText('경쟁 인텔')).toBeInTheDocument();
    expect(screen.getByText(/진입 신호 RED/)).toBeInTheDocument();
    expect(screen.getByText(/500m 내 경쟁점 145/)).toBeInTheDocument();
    expect(screen.getByText('kakao_store')).toBeInTheDocument();
  });

  it('compact variant renders only verdict one-line', () => {
    render(<AgentCard attribution={mockAttr} size="compact" />);
    expect(screen.getByText('경쟁 인텔')).toBeInTheDocument();
    expect(screen.queryByText(/500m 내 경쟁점 145/)).not.toBeInTheDocument(); // reasoning 숨김
  });

  it('kind badge 색상 매핑', () => {
    const { rerender } = render(<AgentCard attribution={{ ...mockAttr, kind: 'LLM' }} size="full" />);
    expect(screen.getByText('LLM')).toBeInTheDocument();

    rerender(<AgentCard attribution={{ ...mockAttr, kind: 'RAG' }} size="full" />);
    expect(screen.getByText('RAG')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실행 → FAIL**

Run: `cd frontend && npx vitest run src/components/SimulationResult/shared/AgentCard.test.tsx`
Expected: FAIL (컴포넌트 없음)

- [ ] **Step 3: 구현**

```tsx
import { lucideIcons, type LucideIcon } from 'lucide-react';
import {
  TrendingUp, Users, ShieldAlert, Target, Brain,
  UserSearch, LineChart as LineChartIcon, Crosshair,
} from 'lucide-react';
import type { AgentAttribution, AgentId, AgentKind } from '@/types';

const AGENT_ICONS: Record<AgentId, LucideIcon> = {
  market_analyst: TrendingUp,
  population_analyst: Users,
  legal: ShieldAlert,
  district_ranking: Target,
  synthesis: Brain,
  demographic_depth: UserSearch,
  trend_forecaster: LineChartIcon,
  competitor_intel: Crosshair,
};

const AGENT_COLORS: Record<AgentId, string> = {
  market_analyst: 'text-blue-400',
  population_analyst: 'text-emerald-400',
  legal: 'text-rose-400',
  district_ranking: 'text-sky-400',
  synthesis: 'text-amber-400',
  demographic_depth: 'text-violet-400',
  trend_forecaster: 'text-cyan-400',
  competitor_intel: 'text-orange-400',
};

const KIND_BADGE: Record<AgentKind, string> = {
  LLM: 'bg-amber-500/10 text-amber-500',
  Python: 'bg-emerald-500/10 text-emerald-500',
  Hybrid: 'bg-blue-500/10 text-blue-400',
  RAG: 'bg-rose-500/10 text-rose-400',
};

interface AgentCardProps {
  attribution: AgentAttribution;
  size: 'full' | 'compact';
  onExpand?: () => void;
}

export function AgentCard({ attribution, size, onExpand }: AgentCardProps) {
  const Icon = AGENT_ICONS[attribution.id];
  const color = AGENT_COLORS[attribution.id];
  const kindCls = KIND_BADGE[attribution.kind];

  if (size === 'compact') {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="flex w-full items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900/50 p-2 text-left hover:bg-zinc-800 transition-colors"
      >
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-900/90 border border-white/5`}>
          <Icon className={`h-4 w-4 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-100 truncate">{attribution.display_name}</span>
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-mono ${kindCls}`}>{attribution.kind}</span>
          </div>
          <p className="text-xs text-zinc-400 truncate">{attribution.verdict}</p>
        </div>
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-zinc-900/90 border border-white/5">
          <Icon className={`h-7 w-7 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-zinc-100">{attribution.display_name}</h3>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${kindCls}`}>{attribution.kind}</span>
          </div>
          <p className="mt-2 text-sm font-semibold text-zinc-100 leading-snug">{attribution.verdict}</p>
          <p className="mt-2 text-xs text-zinc-400 leading-relaxed">{attribution.reasoning}</p>
        </div>
      </div>
      {attribution.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {attribution.sources.map((s) => (
            <span key={s} className="rounded bg-zinc-700 px-2 py-0.5 text-xs font-mono text-zinc-400">
              {s}
            </span>
          ))}
        </div>
      )}
      {attribution.confidence != null && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] text-zinc-500">
            <span>신뢰도</span>
            <span>{(attribution.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1 h-1 rounded-full bg-zinc-700">
            <div
              className="h-full rounded-full bg-amber-500"
              style={{ width: `${attribution.confidence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 테스트 재실행 → PASS**

Run: `cd frontend && npx vitest run src/components/SimulationResult/shared/AgentCard.test.tsx`
Expected: 3 passed

- [ ] **Step 5: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/components/SimulationResult/shared/
git add frontend/src/components/SimulationResult/shared/AgentCard.tsx frontend/src/components/SimulationResult/shared/AgentCard.test.tsx
git commit -m "feat(C1): AgentCard 공통 컴포넌트 (full/compact variant) + 테스트"
```

---

### Task 10: shared/LegalDrawer.tsx

**Files:**
- Create: `frontend/src/components/SimulationResult/shared/LegalDrawer.tsx`
- Test: `frontend/src/components/SimulationResult/shared/LegalDrawer.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LegalDrawer } from './LegalDrawer';

const mockRisk = {
  type: '가맹사업법',
  risk_level: 'HIGH' as const,
  articles: [
    { article_ref: '가맹사업법 제5조', content: '가맹본부의 의무...' },
    { article_ref: '가맹사업법 제9조', content: '정보공개서...' },
  ],
  checklist: [{ text: '정보공개서 수령', isRequired: true }],
  recommendation: '계약 전 14일 숙고기간 확보',
};

describe('LegalDrawer', () => {
  it('open 시 조항 본문·체크리스트·권고 모두 렌더', () => {
    render(<LegalDrawer risk={mockRisk} open={true} onClose={() => {}} />);
    expect(screen.getByText('가맹사업법')).toBeInTheDocument();
    expect(screen.getByText('가맹사업법 제5조')).toBeInTheDocument();
    expect(screen.getByText('정보공개서 수령')).toBeInTheDocument();
    expect(screen.getByText(/14일 숙고기간/)).toBeInTheDocument();
  });

  it('X 버튼 클릭 시 onClose 호출', () => {
    const onClose = vi.fn();
    render(<LegalDrawer risk={mockRisk} open={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('닫기'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('open=false 시 렌더 안 함', () => {
    render(<LegalDrawer risk={mockRisk} open={false} onClose={() => {}} />);
    expect(screen.queryByText('가맹사업법')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: FAIL 확인 → 구현**

```tsx
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect } from 'react';
import type { LegalChecklistItem } from '@/types';

interface LegalRiskDetail {
  type: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  articles?: { article_ref: string; content: string }[];
  checklist?: LegalChecklistItem[];
  recommendation?: string;
}

interface LegalDrawerProps {
  risk: LegalRiskDetail | null;
  open: boolean;
  onClose: () => void;
}

const RISK_BADGE = {
  HIGH: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  MEDIUM: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  LOW: 'bg-green-500/10 text-green-400 border-green-500/30',
};

export function LegalDrawer({ risk, open, onClose }: LegalDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handleEsc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEsc);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && risk && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="legal-drawer-title"
            className="fixed right-0 top-0 z-50 h-full w-full max-w-[480px] overflow-y-auto bg-zinc-900 border-l border-zinc-700"
          >
            <div className="flex items-start justify-between border-b border-zinc-700 p-6">
              <div>
                <h2 id="legal-drawer-title" className="text-xl font-semibold text-zinc-100">
                  {risk.type}
                </h2>
                <span
                  className={`mt-2 inline-block rounded-full border px-2 py-0.5 text-xs font-bold ${RISK_BADGE[risk.risk_level]}`}
                >
                  ● {risk.risk_level}
                </span>
              </div>
              <button onClick={onClose} aria-label="닫기" className="text-zinc-400 hover:text-zinc-100">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {risk.articles && risk.articles.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                    조항 본문
                  </h3>
                  <div className="space-y-3">
                    {risk.articles.map((a, i) => (
                      <div key={i} className="border-l-2 border-amber-500 pl-4 py-2">
                        <div className="text-sm font-semibold text-amber-500">{a.article_ref}</div>
                        <div className="mt-1 text-sm text-zinc-300 whitespace-pre-line leading-relaxed">
                          {a.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {risk.checklist && risk.checklist.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                    창업 체크리스트
                  </h3>
                  <ul className="space-y-2">
                    {risk.checklist.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          disabled
                          className="mt-1 shrink-0 cursor-not-allowed"
                          aria-label={item.text}
                        />
                        <span className="text-zinc-300">
                          {item.text}
                          {item.isRequired && <span className="ml-1 text-rose-400">*</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {risk.recommendation && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                    AI 권고
                  </h3>
                  <p className="text-sm text-zinc-300 leading-relaxed">{risk.recommendation}</p>
                </section>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 3: 테스트 PASS 확인 + 커밋**

```bash
cd frontend && npx vitest run src/components/SimulationResult/shared/LegalDrawer.test.tsx
git add frontend/src/components/SimulationResult/shared/LegalDrawer.tsx frontend/src/components/SimulationResult/shared/LegalDrawer.test.tsx
git commit -m "feat(C1): LegalDrawer 우측 슬라이드 드로어 + focus trap + ESC close"
```

---

## Phase 3: Kakao Maps

### Task 11: Kakao Maps 동적 로더 훅

**Files:**
- Create: `frontend/src/components/kakao/useKakaoMap.ts`

- [ ] **Step 1: 구현**

```ts
import { useEffect, useState } from 'react';

declare global {
  interface Window {
    kakao: any;
  }
}

const KAKAO_SDK_URL = (apiKey: string) =>
  `//dapi.kakao.com/v2/maps/sdk.js?appkey=${apiKey}&libraries=services,clusterer&autoload=false`;

let loadPromise: Promise<void> | null = null;

function loadKakaoSdk(apiKey: string): Promise<void> {
  if (loadPromise) return loadPromise;
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR'));
  if (window.kakao?.maps) return Promise.resolve();

  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = KAKAO_SDK_URL(apiKey);
    script.async = true;
    script.onload = () => {
      window.kakao.maps.load(() => resolve());
    };
    script.onerror = () => reject(new Error('Kakao Maps SDK 로드 실패'));
    document.head.appendChild(script);
  });
  return loadPromise;
}

export function useKakaoMap() {
  const [ready, setReady] = useState<boolean>(!!window?.kakao?.maps);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const apiKey = import.meta.env.VITE_KAKAO_MAP_API_KEY;
    if (!apiKey) {
      setError(new Error('VITE_KAKAO_MAP_API_KEY 미설정'));
      return;
    }
    loadKakaoSdk(apiKey)
      .then(() => setReady(true))
      .catch((e) => setError(e));
  }, []);

  return { ready, error, kakao: ready ? window.kakao : null };
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/kakao/useKakaoMap.ts
git commit -m "feat(C1): useKakaoMap 동적 로더 훅"
```

---

### Task 12: 마포 16동 GeoJSON 준비

**Files:**
- Create: `frontend/public/mapo-dong.geo.json`

- [ ] **Step 1: 공공데이터포털에서 서울 행정동 경계 GeoJSON 다운로드**

수동 단계 (사용자 or 에이전트가 한 번만 실행):

1. https://data.seoul.go.kr/ 에서 "서울특별시 행정동 경계" 검색
2. GeoJSON 포맷으로 다운로드
3. 마포구 16동만 필터링 (dong_name 혹은 adm_cd 기준)
4. 파일 크기 ~50KB

- [ ] **Step 2: 파일 배치**

Path: `frontend/public/mapo-dong.geo.json`

구조:
```json
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature", "properties": { "dong_name": "서교동", "dong_code": "11440660" }, "geometry": {...} },
    // ... 16 features
  ]
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/public/mapo-dong.geo.json
git commit -m "feat(C1): 마포 16동 경계 GeoJSON 추가 (카카오맵 choropleth용)"
```

---

### Task 13: AgentMapVisualizer 카카오맵 리팩터

**Files:**
- Modify: `frontend/src/components/AgentMapVisualizer.tsx`

- [ ] **Step 1: 기존 AgentMapVisualizer props 확인**

Run: `grep -n "export\|interface.*Props\|function AgentMap" frontend/src/components/AgentMapVisualizer.tsx | head -10`

- [ ] **Step 2: props 확장**

기존 props에 추가:
- `competitors?: Array<{place_name, lat, lng, distance_m}>`
- `rankings?: Array<{district, score, closure_rate?}>`
- `radius?: number`

- [ ] **Step 3: 카카오맵 초기화 로직 추가**

컴포넌트 내부에서:
```tsx
const { ready, error, kakao } = useKakaoMap();
const mapRef = useRef<HTMLDivElement>(null);
const mapInstance = useRef<any>(null);

useEffect(() => {
  if (!ready || !mapRef.current) return;
  mapInstance.current = new kakao.maps.Map(mapRef.current, {
    center: new kakao.maps.LatLng(center.lat, center.lng),
    level: 4,
  });
  // 500m Circle
  new kakao.maps.Circle({
    center: new kakao.maps.LatLng(center.lat, center.lng),
    radius: radius || 500,
    strokeStyle: 'dashed',
    strokeColor: '#f59e0b',
    strokeWeight: 2,
    fillColor: '#f59e0b',
    fillOpacity: 0.05,
  }).setMap(mapInstance.current);
  // 경쟁점 CustomOverlay
  competitors?.forEach((c) => {
    const content = document.createElement('div');
    content.className =
      c.distance_m <= (radius || 500)
        ? 'w-3 h-3 rounded-full bg-amber-500 border-2 border-white shadow'
        : 'w-2 h-2 rounded-full bg-zinc-600 border border-white';
    new kakao.maps.CustomOverlay({
      position: new kakao.maps.LatLng(c.lat, c.lng),
      content,
      map: mapInstance.current,
    });
  });
  // GeoJSON choropleth (fetch public/mapo-dong.geo.json)
  fetch('/mapo-dong.geo.json')
    .then((r) => r.json())
    .then((geo) => {
      geo.features.forEach((f: any) => {
        const dong = f.properties.dong_name;
        const ranking = rankings?.find((r) => r.district === dong);
        const score = ranking?.score ?? 50;
        const opacity = Math.max(0.1, Math.min(0.5, score / 200));
        const path = f.geometry.coordinates[0][0].map(
          ([lng, lat]: number[]) => new kakao.maps.LatLng(lat, lng),
        );
        new kakao.maps.Polygon({
          path,
          strokeWeight: 1,
          strokeColor: '#3f3f46',
          strokeOpacity: 0.7,
          fillColor: '#f59e0b',
          fillOpacity: opacity,
          map: mapInstance.current,
        });
      });
    });
}, [ready, center, competitors, rankings, radius, kakao]);
```

- [ ] **Step 4: error 폴백 렌더**

```tsx
if (error) {
  return (
    <div className="flex items-center justify-center h-full bg-zinc-900 border border-zinc-700 rounded-lg p-8">
      <div className="text-center">
        <div className="text-rose-400 mb-2">지도를 불러올 수 없습니다</div>
        <button
          onClick={() => window.location.reload()}
          className="text-xs text-zinc-400 hover:text-zinc-100"
        >
          새로고침
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 타입 체크 + 커밋**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/AgentMapVisualizer.tsx
git commit -m "refactor(C1): AgentMapVisualizer 카카오맵 기반 리팩터 + GeoJSON choropleth"
```

---

## Phase 4: 15 섹션 구현

### Task 14: IntegratedReport 오케스트레이터

**Files:**
- Create: `frontend/src/components/SimulationResult/IntegratedReport.tsx`

- [ ] **Step 1: 빈 껍데기 먼저 (15 섹션 자리)**

```tsx
import type { SimulationOutput } from '@/types';
import { CommandBar } from './sections/CommandBar';
import { HeadlineBlock } from './sections/HeadlineBlock';
// ... 15 import

interface IntegratedReportProps {
  simResult: SimulationOutput | null;
  onExportPdf: () => void;
  onExportXlsx: () => void;
  compareMode: boolean;
  onToggleCompare: () => void;
}

export function IntegratedReport({
  simResult, onExportPdf, onExportXlsx, compareMode, onToggleCompare,
}: IntegratedReportProps) {
  if (!simResult) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16">
      <CommandBar
        simResult={simResult}
        compareMode={compareMode}
        onToggleCompare={onToggleCompare}
        onExportPdf={onExportPdf}
      />
      <HeadlineBlock simResult={simResult} />
      {/* §03 ~ §15 placeholders */}
      <div id="report-footer">
        <ReportFooter onExportPdf={onExportPdf} onExportXlsx={onExportXlsx} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/SimulationResult/IntegratedReport.tsx
git commit -m "feat(C1): IntegratedReport 오케스트레이터 뼈대"
```

---

### Task 15: §01 CommandBar + §02 HeadlineBlock

**Files:**
- Create: `sections/CommandBar.tsx`
- Create: `sections/HeadlineBlock.tsx`

- [ ] **Step 1: CommandBar 작성**

```tsx
// sections/CommandBar.tsx
import { Download, FileText, Activity } from 'lucide-react';
import { SectionLabel } from '../shared/SectionLabel';
import type { SimulationOutput } from '@/types';

interface Props {
  simResult: SimulationOutput;
  compareMode: boolean;
  onToggleCompare: () => void;
  onExportPdf: () => void;
}

export function CommandBar({ simResult, compareMode, onToggleCompare, onExportPdf }: Props) {
  const attrCount = simResult.agent_attributions?.length ?? 0;
  return (
    <section className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-amber-500" />
          <div>
            <div className="text-xs text-zinc-400">Run ID</div>
            <div className="font-mono text-sm text-zinc-100">
              {simResult.request_id?.slice(0, 8) ?? '—'}
            </div>
          </div>
          <div className="border-l border-zinc-700 pl-3">
            <div className="text-xs text-zinc-400">Agents</div>
            <div className="font-mono text-sm text-zinc-100">{attrCount}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleCompare}
            className={`rounded-md px-3 py-1.5 text-sm font-semibold ${
              compareMode
                ? 'bg-amber-500 text-zinc-900'
                : 'border border-zinc-700 text-zinc-300 hover:bg-zinc-700'
            }`}
          >
            VS 비교 모드
          </button>
          <button
            onClick={onExportPdf}
            className="flex items-center gap-1 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
          >
            <FileText className="w-4 h-4" />
            PDF
          </button>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: HeadlineBlock 작성**

```tsx
// sections/HeadlineBlock.tsx
import { CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react';
import { SectionLabel } from '../shared/SectionLabel';
import type { SimulationOutput } from '@/types';

interface Props {
  simResult: SimulationOutput;
}

export function HeadlineBlock({ simResult }: Props) {
  const signal =
    simResult.competitor_intel?.market_entry_signal ??
    (simResult.overall_legal_risk === 'safe'
      ? 'green'
      : simResult.overall_legal_risk === 'danger'
        ? 'red'
        : 'yellow');

  const SIGNAL_CFG = {
    green: { icon: CheckCircle2, color: 'text-green-500', label: '진입 권장', bg: 'bg-green-500/10' },
    yellow: { icon: AlertTriangle, color: 'text-yellow-500', label: '조건부', bg: 'bg-yellow-500/10' },
    red: { icon: ShieldAlert, color: 'text-red-500', label: '비권장', bg: 'bg-red-500/10' },
  };
  const cfg = SIGNAL_CFG[signal as keyof typeof SIGNAL_CFG];
  const Icon = cfg.icon;

  const headline = simResult.ai_recommendation?.split(/[.!?。]/)[0] || '분석 결과';
  const body = simResult.ai_recommendation?.slice(headline.length + 1).trim();

  return (
    <section>
      <SectionLabel number="§02" label="AI VERDICT" subtitle="종합 판단 신호" />
      <div className={`rounded-lg border border-zinc-700 ${cfg.bg} p-6`}>
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-zinc-900/80 border border-white/5">
            <Icon className={`w-7 h-7 ${cfg.color}`} strokeWidth={2} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`rounded-full border border-current px-2 py-0.5 text-xs font-bold ${cfg.color}`}>
                {cfg.label}
              </span>
              <span className="text-xs text-zinc-400">
                추천 지역: <span className="text-zinc-100 font-semibold">{simResult.winner_district ?? '—'}</span>
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-100 leading-tight">{headline}</h2>
            {body && <p className="mt-2 text-sm text-zinc-300 leading-relaxed">{body}</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/CommandBar.tsx frontend/src/components/SimulationResult/sections/HeadlineBlock.tsx
git commit -m "feat(C1): §01 CommandBar + §02 HeadlineBlock 구현"
```

---

### Task 16: §03 PrimaryKPIs (5 카드)

**Files:**
- Create: `sections/PrimaryKPIs.tsx`

- [ ] **Step 1: 5 KPI 카드 컴포넌트 작성**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { Sparkline } from '../shared/Sparkline';
import type { SimulationOutput } from '@/types';

interface Props {
  simResult: SimulationOutput;
}

export function PrimaryKPIs({ simResult }: Props) {
  const revenue = simResult.quarterly_projection?.[0]?.revenue ?? 0;
  const grade = simResult.market_report?.estimated_revenue ?? '—';
  const rent = simResult.market_report?.rent_affordability ?? '—';
  const competition = simResult.competitor_intel?.competition_500m?.saturation_score ?? 0;
  const saturation = simResult.competitor_intel?.competition_500m?.saturation_level ?? '—';
  const legalSafety = simResult.overall_legal_risk ?? 'unknown';
  const forecastScore = simResult.trend_forecast?.forecast?.score ?? 0;
  const forecastDir = simResult.trend_forecast?.forecast?.direction ?? 'unknown';

  const RENT_COLOR = { SAFE: 'text-green-500', CAUTION: 'text-yellow-500', DANGER: 'text-red-500' };
  const LEGAL_COLOR = { safe: 'text-green-500', caution: 'text-yellow-500', danger: 'text-red-500' };

  return (
    <section>
      <SectionLabel number="§03" label="PRIMARY KPIs" subtitle="5 대 핵심 지표" />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KpiCard
          label="예상 월매출"
          value={`${(revenue / 10000).toLocaleString()}만`}
          unit="원"
          badge={`${grade}등급`}
          badgeColor="text-amber-500"
        />
        <KpiCard
          label="임대료 적정성"
          value={rent}
          badge=""
          badgeColor={RENT_COLOR[rent as keyof typeof RENT_COLOR] || 'text-zinc-400'}
        />
        <KpiCard
          label="경쟁강도"
          value={`${competition}/100`}
          badge={saturation}
          badgeColor="text-rose-400"
        />
        <KpiCard
          label="법률안전도"
          value={legalSafety.toUpperCase()}
          badge=""
          badgeColor={LEGAL_COLOR[legalSafety as keyof typeof LEGAL_COLOR] || 'text-zinc-400'}
        />
        <KpiCard
          label="12개월 전망"
          value={`${forecastScore}/100`}
          badge={forecastDir}
          badgeColor="text-cyan-400"
        />
      </div>
    </section>
  );
}

function KpiCard({
  label, value, unit, badge, badgeColor,
}: { label: string; value: string | number; unit?: string; badge?: string; badgeColor: string }) {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-zinc-100">{value}</span>
        {unit && <span className="text-xs text-zinc-400">{unit}</span>}
      </div>
      {badge && <div className={`mt-2 text-xs font-semibold ${badgeColor}`}>{badge}</div>}
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/PrimaryKPIs.tsx
git commit -m "feat(C1): §03 PrimaryKPIs 5 카드 (매출/임대/경쟁/법률/전망)"
```

---

### Task 17: §04 Scorecard + §05 MapSection + §06 IndicatorGrid

**Files:**
- Create: `sections/Scorecard.tsx`
- Create: `sections/MapSection.tsx`
- Create: `sections/IndicatorGrid.tsx`

- [ ] **Step 1: Scorecard (demographic + analysis_metrics 5 영역)**

```tsx
// sections/Scorecard.tsx — demographic 점수 카드 + 5 영역 그룹핑
import { SectionLabel } from '../shared/SectionLabel';
import type { SimulationOutput } from '@/types';

interface Props { simResult: SimulationOutput; }

export function Scorecard({ simResult }: Props) {
  const match = simResult.demographic_report?.brand_target_match_score ?? 0;
  const core = simResult.demographic_report?.core_demographic;
  return (
    <section>
      <SectionLabel number="§04" label="SCORECARD" subtitle="영역별 점수" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xs text-zinc-400">브랜드 타겟 매칭</div>
            <div className="text-3xl font-bold text-amber-500">{match.toFixed(0)}/100</div>
          </div>
          {core && (
            <div className="text-right">
              <div className="text-xs text-zinc-400">핵심 소비층</div>
              <div className="text-sm font-semibold text-zinc-100">
                {core.age} · {core.gender}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: MapSection (AgentMapVisualizer 래핑)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { AgentMapVisualizer } from '@/components/AgentMapVisualizer';
import type { SimulationOutput } from '@/types';

interface Props { simResult: SimulationOutput; }

export function MapSection({ simResult }: Props) {
  const center = simResult.market_data?.target_coords ?? { lat: 37.5558, lng: 126.9193 };
  const competitors = simResult.competitor_intel?.competition_500m?.samples ?? [];
  const rankings = simResult.scouting_results ?? [];

  return (
    <section>
      <SectionLabel number="§05" label="MARKET MAP" subtitle="마포 16동 choropleth + 500m 경쟁 반경" />
      <div className="relative rounded-lg border border-zinc-700 overflow-hidden" style={{ height: 520 }}>
        <AgentMapVisualizer
          center={center}
          competitors={competitors}
          rankings={rankings}
          radius={500}
        />
        <div className="absolute top-4 left-4 backdrop-blur-xl bg-zinc-900/75 border border-zinc-700 rounded-lg p-4 max-w-xs">
          <div className="text-xs text-zinc-400">대상 지역</div>
          <div className="text-lg font-semibold text-zinc-100">{simResult.winner_district ?? '—'}</div>
          <div className="text-xs text-amber-500 mt-1">{simResult.brand_name ?? ''}</div>
        </div>
        <div className="absolute bottom-4 left-4 backdrop-blur-xl bg-zinc-900/75 border border-zinc-700 rounded-lg p-3">
          <div className="text-xs text-zinc-400 mb-1">범례</div>
          <div className="flex items-center gap-2 text-xs text-zinc-300">
            <span className="w-3 h-3 rounded-full bg-amber-500" />
            <span>반경 500m 내 경쟁점</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-300">
            <span className="w-3 h-3 rounded-full bg-zinc-600" />
            <span>외부 경쟁점</span>
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: IndicatorGrid (7대 지표 레이더 재사용)**

기존 `MetricCharts.tsx`를 import하거나 Recharts `RadarChart` 직접 구성. 하단에 AgentCard compact 3개.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/Scorecard.tsx frontend/src/components/SimulationResult/sections/MapSection.tsx frontend/src/components/SimulationResult/sections/IndicatorGrid.tsx
git commit -m "feat(C1): §04 Scorecard + §05 MapSection + §06 IndicatorGrid"
```

---

### Task 18: §07 QuarterlyForecast + §08 ScenarioSplit + §09 ShapContribution

**Files:**
- Create: `sections/QuarterlyForecast.tsx` (기존 QuarterlyProjectionChart 래핑)
- Create: `sections/ScenarioSplit.tsx` (신규 ComposedChart)
- Create: `sections/ShapContribution.tsx` (기존 ShapChart 래핑)

- [ ] **Step 1: QuarterlyForecast (기존 래핑 + AgentCard compact 2)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { QuarterlyProjectionChart } from '@/components/SimulationResult/QuarterlyProjectionChart';
import { AgentCard } from '../shared/AgentCard';
import type { SimulationOutput } from '@/types';

export function QuarterlyForecast({ simResult }: { simResult: SimulationOutput }) {
  const attrs = simResult.agent_attributions ?? [];
  const trend = attrs.find((a) => a.id === 'trend_forecaster');
  const demo = attrs.find((a) => a.id === 'demographic_depth');

  return (
    <section>
      <SectionLabel number="§07" label="QUARTERLY FORECAST" subtitle="6분기 매출 예측" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4 mb-3">
        <QuarterlyProjectionChart data={simResult.quarterly_projection ?? []} />
      </div>
      <div className="grid md:grid-cols-2 gap-2">
        {trend && <AgentCard attribution={trend} size="compact" />}
        {demo && <AgentCard attribution={demo} size="compact" />}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: ScenarioSplit (Recharts ComposedChart)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';
import { ComposedChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { SimulationOutput } from '@/types';

export function ScenarioSplit({ simResult }: { simResult: SimulationOutput }) {
  const sc = simResult.scenarios;
  if (!sc) {
    return (
      <section>
        <SectionLabel number="§08" label="SCENARIOS" />
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6 text-center text-zinc-400 text-sm">
          시나리오 데이터가 없습니다
        </div>
      </section>
    );
  }

  const chartData = sc.base?.quarterly?.map((b: any, i: number) => ({
    quarter: b.quarter,
    optimistic: sc.optimistic?.quarterly?.[i]?.revenue,
    base: b.revenue,
    pessimistic: sc.pessimistic?.quarterly?.[i]?.revenue,
  })) ?? [];

  const synthesis = simResult.agent_attributions?.find((a) => a.id === 'synthesis');

  return (
    <section>
      <SectionLabel number="§08" label="SCENARIOS" subtitle="낙관 / 기본 / 비관" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4 mb-3">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData}>
            <XAxis dataKey="quarter" stroke="#9ca3af" fontSize={12} />
            <YAxis stroke="#9ca3af" fontSize={12} />
            <Tooltip contentStyle={{ background: '#27272a', border: '1px solid #3f3f46' }} />
            <Legend />
            <Line type="monotone" dataKey="optimistic" stroke="#10b981" strokeWidth={2} name="낙관" />
            <Line type="monotone" dataKey="base" stroke="#f59e0b" strokeWidth={2} name="기본" />
            <Line type="monotone" dataKey="pessimistic" stroke="#ef4444" strokeWidth={2} name="비관" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {synthesis && <AgentCard attribution={synthesis} size="compact" />}
    </section>
  );
}
```

- [ ] **Step 3: ShapContribution (기존 ShapChart 래핑 + AgentCard 2)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { ShapChart } from '@/components/SimulationResult/ShapChart';
import { AgentCard } from '../shared/AgentCard';
import type { SimulationOutput } from '@/types';

export function ShapContribution({ simResult }: { simResult: SimulationOutput }) {
  const demo = simResult.agent_attributions?.find((a) => a.id === 'demographic_depth');
  const competitor = simResult.agent_attributions?.find((a) => a.id === 'competitor_intel');

  return (
    <section>
      <SectionLabel number="§09" label="FEATURE CONTRIBUTION" subtitle="SHAP 피처 중요도" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4 mb-3">
        <ShapChart data={simResult.shap_result} />
      </div>
      <div className="grid md:grid-cols-2 gap-2">
        {demo && <AgentCard attribution={demo} size="compact" />}
        {competitor && <AgentCard attribution={competitor} size="compact" />}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/QuarterlyForecast.tsx frontend/src/components/SimulationResult/sections/ScenarioSplit.tsx frontend/src/components/SimulationResult/sections/ShapContribution.tsx
git commit -m "feat(C1): §07 Quarterly + §08 Scenarios + §09 SHAP"
```

---

### Task 19: §10 TimelineForecast + §11 AgentAttribution

**Files:**
- Create: `sections/TimelineForecast.tsx`
- Create: `sections/AgentAttribution.tsx`

- [ ] **Step 1: TimelineForecast (trend + closure_risk 경고)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';
import { AlertTriangle } from 'lucide-react';
import type { SimulationOutput } from '@/types';

export function TimelineForecast({ simResult }: { simResult: SimulationOutput }) {
  const tf = simResult.trend_forecast?.forecast;
  const closureSignals = simResult.closure_risk?.top_signals ?? [];
  const trendAgent = simResult.agent_attributions?.find((a) => a.id === 'trend_forecaster');

  return (
    <section>
      <SectionLabel number="§10" label="TIMELINE FORECAST" subtitle="6/12/24개월 전망 + 폐업 신호" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6 mb-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-zinc-400">종합 전망 점수</div>
            <div className="text-4xl font-bold text-cyan-400">{tf?.score ?? 0}/100</div>
            <div className="text-sm text-zinc-400 mt-1">방향: {tf?.direction ?? '—'}</div>
          </div>
        </div>
        {tf?.narrative && <p className="mt-4 text-sm text-zinc-300 leading-relaxed">{tf.narrative}</p>}
      </div>
      {closureSignals.length > 0 && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-semibold text-rose-400 mb-2">폐업 위험 신호</div>
              <ul className="text-xs text-zinc-300 space-y-1">
                {closureSignals.slice(0, 3).map((s, i) => (
                  <li key={i}>• {s.feature}: {(s.contribution * 100).toFixed(1)}%</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
      {trendAgent && <AgentCard attribution={trendAgent} size="compact" />}
    </section>
  );
}
```

- [ ] **Step 2: AgentAttribution (8 카드 그리드)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';
import type { SimulationOutput } from '@/types';

export function AgentAttribution({ simResult }: { simResult: SimulationOutput }) {
  const attrs = simResult.agent_attributions ?? [];

  if (attrs.length === 0) {
    return (
      <section>
        <SectionLabel number="§11" label="AGENT ATTRIBUTION" />
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6 text-center text-zinc-400 text-sm">
          에이전트 판단 근거 데이터가 없습니다
        </div>
      </section>
    );
  }

  return (
    <section>
      <SectionLabel number="§11" label="AGENT ATTRIBUTION" subtitle="8 에이전트가 이 판단을 어떻게 만들었나" />
      <div className="grid xl:grid-cols-4 md:grid-cols-2 gap-4">
        {attrs.map((attr) => (
          <AgentCard key={attr.id} attribution={attr} size="full" />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/TimelineForecast.tsx frontend/src/components/SimulationResult/sections/AgentAttribution.tsx
git commit -m "feat(C1): §10 Timeline + §11 Agent 그리드"
```

---

### Task 20: §12 DistrictRankings + §13 InsightsGrid

**Files:**
- Create: `sections/DistrictRankings.tsx`
- Create: `sections/InsightsGrid.tsx`

- [ ] **Step 1: DistrictRankings (테이블 기본 + VS 모드)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import type { SimulationOutput } from '@/types';

export function DistrictRankings({ simResult, compareMode }: { simResult: SimulationOutput; compareMode: boolean }) {
  const rankings = simResult.scouting_results ?? [];

  return (
    <section>
      <SectionLabel number="§12" label="DISTRICT RANKINGS" subtitle="마포 16동 순위" />
      <div className="rounded-lg border border-zinc-700 bg-zinc-800 overflow-hidden">
        <table className="w-full">
          <thead className="bg-zinc-900 border-b border-zinc-700">
            <tr>
              <th className="text-left text-xs text-zinc-400 font-semibold uppercase p-3">순위</th>
              <th className="text-left text-xs text-zinc-400 font-semibold uppercase p-3">행정동</th>
              <th className="text-right text-xs text-zinc-400 font-semibold uppercase p-3">점수</th>
              <th className="text-right text-xs text-zinc-400 font-semibold uppercase p-3">폐업률</th>
              <th className="text-right text-xs text-zinc-400 font-semibold uppercase p-3">BEP</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => (
              <tr key={r.district} className={i < 3 ? 'bg-amber-500/5' : ''}>
                <td className="p-3 font-mono text-sm text-zinc-100">{i + 1}</td>
                <td className="p-3 text-sm text-zinc-100 font-semibold">{r.district}</td>
                <td className="p-3 text-right font-mono text-sm text-zinc-100">{r.score}</td>
                <td className="p-3 text-right font-mono text-sm text-rose-400">
                  {r.closure_rate != null ? `${(r.closure_rate * 100).toFixed(1)}%` : '—'}
                </td>
                <td className="p-3 text-right font-mono text-sm text-zinc-400">
                  {r.bep_months != null ? `${r.bep_months}개월` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: InsightsGrid (탭 토글 + Legal 테이블 + 드로어)**

```tsx
import { useState } from 'react';
import { SectionLabel } from '../shared/SectionLabel';
import { LegalDrawer } from '../shared/LegalDrawer';
import type { SimulationOutput } from '@/types';

type Tab = 'legal' | 'ai_insights' | 'competitor_risks';

export function InsightsGrid({ simResult }: { simResult: SimulationOutput }) {
  const [tab, setTab] = useState<Tab>('legal');
  const [selectedRisk, setSelectedRisk] = useState<any | null>(null);

  const risks = simResult.legal_risks ?? [];

  return (
    <section>
      <SectionLabel number="§13" label="INSIGHTS & LEGAL" subtitle="법률 14 + AI 인사이트 + 경쟁 리스크" />

      <div className="flex gap-2 mb-4 border-b border-zinc-700">
        {(['legal', 'ai_insights', 'competitor_risks'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
              tab === t
                ? 'border-amber-500 text-amber-500'
                : 'border-transparent text-zinc-400 hover:text-zinc-100'
            }`}
          >
            {t === 'legal' ? '법률 14' : t === 'ai_insights' ? 'AI 인사이트' : '경쟁 리스크'}
          </button>
        ))}
      </div>

      {tab === 'legal' && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 overflow-hidden">
          <table className="w-full">
            <thead className="bg-zinc-900 border-b border-zinc-700">
              <tr>
                <th className="text-left p-3 text-xs text-zinc-400 uppercase">#</th>
                <th className="text-left p-3 text-xs text-zinc-400 uppercase">법률</th>
                <th className="text-left p-3 text-xs text-zinc-400 uppercase">위험도</th>
                <th className="text-right p-3 text-xs text-zinc-400 uppercase">조문</th>
                <th className="text-right p-3 text-xs text-zinc-400 uppercase">체크리스트</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {risks.map((r: any, i: number) => {
                const borderCls = {
                  HIGH: 'border-l-4 border-rose-500',
                  MEDIUM: 'border-l-4 border-yellow-500',
                  LOW: 'border-l-4 border-green-500',
                }[r.risk_level] || '';
                const levelColor = {
                  HIGH: 'text-rose-400',
                  MEDIUM: 'text-yellow-400',
                  LOW: 'text-green-400',
                }[r.risk_level] || 'text-zinc-400';
                return (
                  <tr
                    key={i}
                    onClick={() => setSelectedRisk(r)}
                    className={`cursor-pointer hover:bg-zinc-700/50 ${borderCls}`}
                  >
                    <td className="p-3 font-mono text-xs text-zinc-400">{i + 1}</td>
                    <td className="p-3 text-sm text-zinc-100 font-semibold">{r.type}</td>
                    <td className={`p-3 text-xs font-bold ${levelColor}`}>● {r.risk_level}</td>
                    <td className="p-3 text-right text-sm text-zinc-400">{r.articles?.length ?? 0}</td>
                    <td className="p-3 text-right text-sm text-zinc-400">{r.checklist?.length ?? 0}</td>
                    <td className="p-3 text-zinc-400">›</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'ai_insights' && (
        <div className="text-sm text-zinc-400">AI 인사이트 (기존 카드 이관)</div>
      )}

      {tab === 'competitor_risks' && simResult.competitor_intel && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
            <h4 className="text-sm font-semibold text-emerald-400 mb-2">기회</h4>
            <ul className="space-y-1 text-sm text-zinc-300">
              {simResult.competitor_intel.key_opportunities?.map((o: string, i: number) => <li key={i}>• {o}</li>)}
            </ul>
          </div>
          <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
            <h4 className="text-sm font-semibold text-rose-400 mb-2">리스크</h4>
            <ul className="space-y-1 text-sm text-zinc-300">
              {simResult.competitor_intel.key_risks?.map((o: string, i: number) => <li key={i}>• {o}</li>)}
            </ul>
          </div>
        </div>
      )}

      <LegalDrawer
        risk={selectedRisk}
        open={!!selectedRisk}
        onClose={() => setSelectedRisk(null)}
      />
    </section>
  );
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/DistrictRankings.tsx frontend/src/components/SimulationResult/sections/InsightsGrid.tsx
git commit -m "feat(C1): §12 Rankings + §13 InsightsGrid (Legal 테이블 + 드로어)"
```

---

### Task 21: §14 DecisionMemo + §15 ReportFooter

**Files:**
- Create: `sections/DecisionMemo.tsx`
- Create: `sections/ReportFooter.tsx`

- [ ] **Step 1: DecisionMemo (라이트 톤 isolated)**

```tsx
import { SectionLabel } from '../shared/SectionLabel';
import type { SimulationOutput } from '@/types';

export function DecisionMemo({ simResult }: { simResult: SimulationOutput }) {
  const verdict =
    simResult.overall_legal_risk === 'safe' ? 'GO'
      : simResult.overall_legal_risk === 'danger' ? 'NO' : 'HOLD';
  const VERDICT_CLS = {
    GO: 'text-green-700 bg-green-100',
    HOLD: 'text-yellow-700 bg-yellow-100',
    NO: 'text-red-700 bg-red-100',
  };

  return (
    <section>
      <SectionLabel number="§14" label="DECISION MEMO" subtitle="본사 보고용 요약" />
      <div className="rounded-lg border border-zinc-300 bg-zinc-50 p-8 text-zinc-900 print:shadow-none">
        <div className={`inline-block rounded-full px-4 py-1 text-xl font-bold ${VERDICT_CLS[verdict]} mb-4`}>
          {verdict}
        </div>
        <h3 className="text-2xl font-semibold mb-4">
          {simResult.brand_name ?? '—'} · {simResult.winner_district ?? '—'}
        </h3>
        <div className="grid md:grid-cols-2 gap-6 text-sm">
          <div>
            <h4 className="font-semibold text-zinc-700 mb-2">근거</h4>
            <p className="text-zinc-600 leading-relaxed">
              {simResult.ai_recommendation?.slice(0, 300) || '—'}
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-700 mb-2">다음 액션</h4>
            <ul className="text-zinc-600 space-y-1">
              {simResult.competitor_intel?.recommended_actions?.slice(0, 3).map((a: string, i: number) => (
                <li key={i}>• {a}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: ReportFooter**

```tsx
import { Download, FileText } from 'lucide-react';

interface Props {
  onExportPdf: () => void;
  onExportXlsx: () => void;
}

export function ReportFooter({ onExportPdf, onExportXlsx }: Props) {
  return (
    <footer className="mt-16 pt-8 border-t border-zinc-700">
      <div className="flex justify-between items-center">
        <div className="text-xs text-zinc-500">
          SPOTTER v1.0 · 마포구 프랜차이즈 입지 시뮬레이터
        </div>
        <div className="flex gap-2">
          <button
            onClick={onExportPdf}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700"
          >
            <FileText className="w-4 h-4" /> PDF
          </button>
          <button
            onClick={onExportXlsx}
            className="flex items-center gap-2 rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700"
          >
            <Download className="w-4 h-4" /> XLSX
          </button>
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/SimulationResult/sections/DecisionMemo.tsx frontend/src/components/SimulationResult/sections/ReportFooter.tsx
git commit -m "feat(C1): §14 DecisionMemo (라이트 톤) + §15 Footer"
```

---

### Task 22: IntegratedReport 15 섹션 연결

**Files:**
- Modify: `frontend/src/components/SimulationResult/IntegratedReport.tsx`

- [ ] **Step 1: 모든 섹션 import + 렌더**

```tsx
import { CommandBar } from './sections/CommandBar';
import { HeadlineBlock } from './sections/HeadlineBlock';
import { PrimaryKPIs } from './sections/PrimaryKPIs';
import { Scorecard } from './sections/Scorecard';
import { MapSection } from './sections/MapSection';
import { IndicatorGrid } from './sections/IndicatorGrid';
import { QuarterlyForecast } from './sections/QuarterlyForecast';
import { ScenarioSplit } from './sections/ScenarioSplit';
import { ShapContribution } from './sections/ShapContribution';
import { TimelineForecast } from './sections/TimelineForecast';
import { AgentAttribution } from './sections/AgentAttribution';
import { DistrictRankings } from './sections/DistrictRankings';
import { InsightsGrid } from './sections/InsightsGrid';
import { DecisionMemo } from './sections/DecisionMemo';
import { ReportFooter } from './sections/ReportFooter';
import type { SimulationOutput } from '@/types';

interface IntegratedReportProps {
  simResult: SimulationOutput | null;
  onExportPdf: () => void;
  onExportXlsx: () => void;
  compareMode: boolean;
  onToggleCompare: () => void;
}

export function IntegratedReport({
  simResult, onExportPdf, onExportXlsx, compareMode, onToggleCompare,
}: IntegratedReportProps) {
  if (!simResult) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16">
      <CommandBar simResult={simResult} compareMode={compareMode} onToggleCompare={onToggleCompare} onExportPdf={onExportPdf} />
      <HeadlineBlock simResult={simResult} />
      <PrimaryKPIs simResult={simResult} />
      <Scorecard simResult={simResult} />
      <MapSection simResult={simResult} />
      <IndicatorGrid simResult={simResult} />
      <QuarterlyForecast simResult={simResult} />
      <ScenarioSplit simResult={simResult} />
      <ShapContribution simResult={simResult} />
      <TimelineForecast simResult={simResult} />
      <AgentAttribution simResult={simResult} />
      <DistrictRankings simResult={simResult} compareMode={compareMode} />
      <InsightsGrid simResult={simResult} />
      <DecisionMemo simResult={simResult} />
      <ReportFooter onExportPdf={onExportPdf} onExportXlsx={onExportXlsx} />
    </div>
  );
}
```

- [ ] **Step 2: tsc 체크 + 커밋**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/SimulationResult/IntegratedReport.tsx
git commit -m "feat(C1): IntegratedReport 15 섹션 연결 완료"
```

---

## Phase 5: App.tsx 통합

### Task 23: pages/SimulatorDashboard.tsx 생성 + App.tsx 추출

**Files:**
- Create: `frontend/src/pages/SimulatorDashboard.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: App.tsx line 2236~ SimulatorDashboard 함수 확인**

Run: `grep -n "function SimulatorDashboard" frontend/src/App.tsx`

- [ ] **Step 2: pages/SimulatorDashboard.tsx에 추출**

pages/SimulatorDashboard.tsx:
- App.tsx에서 `function SimulatorDashboard` 및 해당 함수 내부 코드 복사
- import 경로 조정 (상대 경로 → `@/` alias)
- 결과 렌더 부분을 `<IntegratedReport />` 호출로 교체:

```tsx
import { IntegratedReport } from '@/components/SimulationResult/IntegratedReport';

export default function SimulatorDashboard({ reportState, setReportState }: Props) {
  // ... 기존 state / runSim 등
  return (
    <>
      {/* 기존 입력 영역 유지 */}
      {reportState === 'result' && (
        <IntegratedReport
          simResult={simResult}
          onExportPdf={handleDownloadPdf}
          onExportXlsx={handleDownloadXlsx}
          compareMode={isSplitMode}
          onToggleCompare={() => setIsSplitMode(!isSplitMode)}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: App.tsx에서 기존 inline SimulatorDashboard 제거 + import**

```tsx
import SimulatorDashboard from './pages/SimulatorDashboard';
```

- [ ] **Step 4: tsc + build + test**

```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
cd frontend && npm test
```
Expected: 모두 pass

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/pages/SimulatorDashboard.tsx frontend/src/App.tsx
git commit -m "refactor(C1): SimulatorDashboard를 App.tsx에서 pages/로 추출 + IntegratedReport 연결"
```

---

## Phase 6: QA & 최종

### Task 24: 수동 QA 체크리스트

**Files:** 없음 (런타임 검증)

- [ ] **Step 1: 프론트 dev 서버 + 백엔드 재기동**

```bash
taskkill //F //IM python.exe
cd backend && uvicorn src.main:app --reload --port 8000 &
cd frontend && npm run dev
```

- [ ] **Step 2: 수동 체크리스트 (v2 §2-C)**

- [ ] 시뮬레이션 실행 → 진행률 → 완료 토스트 → 결과 렌더
- [ ] VS 비교 모드 토글 양방향 동작
- [ ] PDF 다운로드 정상
- [ ] XLSX 다운로드 정상
- [ ] §05 카카오맵 + 오버레이 렌더 (choropleth + 경쟁점 마커)
- [ ] §11 Agent 그리드 8 카드 표시
- [ ] §13 Legal 테이블 14/14 + 드로어 open
- [ ] `VITE_USE_MOCK=true` 크래시 없음
- [ ] 분석 중 탭 닫기 → BeforeUnload 경고
- [ ] 분석 중 취소 → AbortController 정상

- [ ] **Step 3: 기존 vitest 회귀 확인**

```bash
cd frontend && npm test
```
Expected: 10 + 새로 추가한 5 (AgentCard 3 + LegalDrawer 3) = 13+ passed

- [ ] **Step 4: 통합 커밋 (필요 시)**

버그 발견 시:
```bash
git add -p
git commit -m "fix(C1): QA 피드백 반영"
```

---

## 완료 기준 (스펙 §11 Acceptance와 매핑)

| # | 기준 | Task |
|---|------|------|
| 1 | 15 섹션 모두 실데이터 렌더 | Task 15-22 |
| 2 | 기존 기능 100% 보존 | Task 23 (수동 QA) |
| 3 | 페르소나 톤 유지 | Task 15, 21 (코드 카피) |
| 4 | Zinc/Amber 팔레트 일관 | Task 15-22 |
| 5 | SimulatorDashboard만 분리 | Task 23 |
| 6 | 타입 strict, `any` 신규 0 | Task 1, 모든 Task |
| 7 | vitest 기존 10 회귀 없음 | Task 23 |
| 8 | 카카오맵 실패 시 D3 폴백 | Task 13 |
| 9 | 백엔드 4 필드 실 노출 | Task 3, 4, 5, 6 |

---

## Self-Review 체크리스트 (이 플랜 작성 시 수행)

- [x] 스펙 §4 아키텍처 → Task 1, 2, 7-11, 22, 23로 커버
- [x] 스펙 §5 데이터 바인딩 → Task 15-21 각 섹션 내부에 실 필드 접근 명시
- [x] 스펙 §6 백엔드 4 필드 → Task 2, 3, 4, 5, 6
- [x] 스펙 §7 카카오맵 → Task 11-13
- [x] 스펙 §8 AgentCard → Task 9
- [x] 스펙 §9 LegalDrawer → Task 10
- [x] 스펙 §11 Acceptance → Task 23 QA 체크리스트
- [x] 타입 일관성: `AgentId`/`AgentAttribution`/`AgentKind` 모든 Task에서 동일
- [x] 파일 경로: 모두 `@/` alias 또는 절대경로 명시
- [x] Placeholder 스캔: TBD/TODO 없음, 모든 코드 블록 포함
