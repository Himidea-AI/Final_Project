# Dashboard Hub 재디자인 — Design Spec

**Date**: 2026-04-28
**Author**: 강민 + Claude
**Branch**: `feature/dashboard-hub-redesign`
**Status**: Draft → User Review

---

## 1. Context

직전 cycle 의 3그룹 IA (TabbedDashboard 안 sticky header + 3그룹 탭바 + 11서브탭) 채택 후 강민 결정:

> "검은 배경이 페이지 위에 얹어진 느낌이 어색. 대대적 개편. 시뮬 완료 시 회사명 + 그 아래 3 큰 카드 (수평 배치, 풀스크린) → 클릭 시 디테일."

**핵심 변경**:
- 시뮬 완료 → **Hub 화면** 새로 도입 (3 큰 카드)
- 기존 dashboard sticky header / KpiMiniGrid / GradeCard / AGENTS_LIST 배지 / 검은 wrapper **모두 제거**
- 페이지 톤 transparent + 카드 강조 (in-page content 느낌)
- 라우트 기반 (`/dashboard` = hub, `/dashboard/predict|analyze|abm` = 디테일)
- 11종 차트 + 디자인 토큰 + 직전 cycle 의 sub/groups 컴포넌트 **모두 그대로 보존**

**KPI 재배치**:
- ML 출처 (월매출 / 유동인구 / 경쟁강도 / BEP / 폐업위험도) → **PredictGroup** 안 (PredictSummaryTab 확장)
- LLM 출처 (1등 동 "공덕동" / synthesis 권고 / 신호등 등) → **AnalyzeGroup** 안 (AnalyzeAiSummaryTab 확장)

---

## 2. Hub 화면 설계

### 2-1. 레이아웃 (전체 페이지)

```
┌─────────────────────────────────────────────────────────────────┐
│  [회사명 (주)홍길동 분식]                       시뮬 일시 · 문서ID │  ← 작은 헤더 (a-3)
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┬─────────────┬─────────────┐                   │
│  │             │             │             │                   │
│  │  [hero img] │  [hero img] │  [hero img] │                   │
│  │  aspect     │  aspect     │  aspect     │                   │
│  │  -video     │  -video     │  -video     │                   │
│  │             │             │             │                   │
│  ├─────────────┼─────────────┼─────────────┤                   │
│  │ 예측 결과    │ AI 분석      │ ABM 시뮬레이터 │                   │
│  │ ML 기반...   │ LLM 기반... │ 100명 행동... │                   │
│  │ 진입 →       │ 진입 →      │ 진입 →       │                   │
│  └─────────────┴─────────────┴─────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

- **풀스크린 가로 3등분**: `grid grid-cols-3 gap-6` (모바일 `grid-cols-1` stack)
- **배경**: 페이지 톤 그대로 (`bg-[#1e1b18]` 자체는 GlobalLimelightNav 가 사용 — dashboard wrapper 만 transparent)
- **컨테이너**: `max-w-[1728px] mx-auto px-8 py-12` (직전 ultra-wide 토큰 유지)

### 2-2. 작은 헤더 (a-3)

| 요소 | 위치 | 스타일 |
|---|---|---|
| 회사명 | 좌측 큰 글자 | `text-2xl font-black text-stone-100` |
| 시뮬 일시 + 문서ID | 우측 작은 메타 | `text-[10px] font-mono text-stone-500` |

### 2-3. Hub Card (3개 동일 패턴)

기존 ProjectCard + ServiceCard + PricingCard 레이저 효과 통합:

```
┌─────────────────────────┐
│                         │
│   [Hero 이미지 — Unsplash] │  aspect-video, group-hover scale 1.10 700ms
│                         │
├─────────────────────────┤
│ 예측 결과                │  text-2xl font-black text-stone-100
│                         │
│ ML 기반 매출 · 재무 · 폐업 │  text-sm text-stone-400 leading-relaxed
│ 위험도 예측              │
│                         │
│ 진입 →                   │  text-xs font-bold text-indigo-400
└─────────────────────────┘  +group-hover/button:translate-x-1
+ 외곽 레이저 (PricingCard 패턴)
+ group-hover -translate-y-2
```

**디자인 토큰** (직전 cycle 일관):
- 배경: `bg-stone-900/60` (현 카드 `/40` 보다 살짝 진하게 — 떠보이는 효과)
- 테두리: `border border-stone-800/60 rounded-3xl`
- 그림자: `shadow-sm hover:shadow-2xl shadow-indigo-500/10`
- 레이저 효과 (hover): `conic-gradient + animate-spin-slow + opacity-0 group-hover:opacity-100`
  ```html
  <div className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500"
       style={{ background: 'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)' }} />
  ```

**3 카드 색 시멘틱** (직전 cycle 토큰):
- 예측 결과 → indigo (`indigo-500/30` 액센트)
- AI 분석 → cyan (`cyan-500/30` 액센트)
- ABM → amber (`amber-500/30` 액센트)

### 2-4. Hero 이미지 source

| 카드 | Unsplash 후보 (라이선스 OK) |
|---|---|
| 예측 결과 | 차트/대시보드 사진 (예: `photo-1551288049-bebda4e38f71` 데이터 시각화) |
| AI 분석 | 마포 거리 / 상권 풍경 (홍대/연남 류) |
| ABM 시뮬레이터 | 거리 군중 / 사람들 활동 |

URL 우선 사용 (정적 import 안 함 — 번들 영향 0). lazy load (`loading="lazy"` 속성). 추후 마포구 자체 사진 교체 가능.

### 2-5. 카드 인터랙션 (ui-ux-pro-max 가이드 반영)

| 항목 | 값 | 가이드 출처 |
|---|---|---|
| 카드 클릭 영역 | 카드 전체 (`<button>` 또는 `<a>` 풀 wrapper) | touch-target-size (≥44pt) |
| Hover 효과 timing | scale `700ms ease-in-out`, lift `300ms ease-out` | duration-timing |
| 레이저 회전 | `animate-spin-slow` (PricingCard 패턴, 4-8s 주기) | continuity, motion-meaning |
| Focus ring | `focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2` | focus-states |
| Reduced motion | `motion-reduce:transition-none motion-reduce:hover:scale-100` | reduced-motion |
| Cursor | `cursor-pointer` | cursor-pointer |

### 2-6. Responsive

| breakpoint | 레이아웃 |
|---|---|
| `sm` (≥640px) | `grid-cols-1` (모바일 — 카드 stack) |
| `md` (≥768px) | `grid-cols-1` (태블릿 세로 — stack) |
| `lg` (≥1024px) | `grid-cols-3` (가로 3등분) |

모바일 stack 시 hero 이미지 height 줄임 (`aspect-[16/9]` → `aspect-[2/1]` 등).

---

## 3. 라우팅 구조 (b-2)

```
/dashboard                    → DashboardHub (3 카드)
/dashboard/predict            → PredictGroup (5 서브탭)
/dashboard/predict?sub=summary  → PredictSummaryTab + KPI 미니 헤더
/dashboard/analyze            → AnalyzeGroup (5 서브탭)
/dashboard/analyze?sub=ai_summary → AnalyzeAiSummaryTab + 추천동 헤더
/dashboard/abm                → AbmGroup
```

- 브라우저 back = hub 복귀 자연
- 새로고침 시 위치 복원
- 딥링크 공유 가능
- 그룹 페이지 좌상단 "← Hub" back 버튼 추가

`App.tsx` 라우트 추가 또는 `/dashboard/*` nested route 패턴. 직전 sticky header 의 회사명/문서ID 는 hub 헤더로 이동, 디테일 페이지는 미니 sub-header 또는 GlobalLimelightNav 만.

---

## 4. KPI 재배치

### 4-1. PredictGroup (ML KPI)

`PredictSummaryTab` 확장 — 기존 3 KPI (월매출/BEP/폐업위험도) + 추가:
- 유동인구 점수 (`market_report.floating_population` — 0-100 정규화)
- 경쟁강도 등급 (`market_report.competition_intensity` — 0-100 정규화)

총 5 KPI. 2x3 grid 또는 가로 5열 (responsive).

### 4-2. AnalyzeGroup (LLM KPI)

`AnalyzeAiSummaryTab` 확장 — 기존 (decision card + 신호등 + synthesis 자연어) + 추가:
- 1등 추천 동 (예: "공덕동") — `simResult.winner_district` 큰 글자 표시 + 추천 이유 한 줄
- 후보 Top 3 동 (`top_3_candidates`) — 칩 리스트

---

## 5. 직전 cycle 영향 (재배치만)

| 영향 | 처리 |
|---|---|
| `TabbedDashboard.tsx` | 폐기 → `DashboardHub.tsx` (hub 만) + 라우트 별 그룹 페이지로 분리 |
| `groups/PredictGroup.tsx` 등 | 그대로 유지 — 라우트 페이지 wrapper 가 호출 |
| `sub/predict/*`, `sub/analyze/*` | 그대로 유지 — 일부 (PredictSummaryTab, AnalyzeAiSummaryTab) KPI 재배치로 확장 |
| `KpiMiniGrid.tsx` | hub 에서 미사용. 그러나 PredictSummaryTab 안에서 재활용 가능 |
| `GradeCard.tsx` | hub 에서 미사용. 디테일 페이지 어디 사용할지 결정 (선택 — out of scope) |
| `AGENTS_LIST` 배지 | hub 에서 미사용. AnalyzeAgentInsightTab 으로 이동 (이미 AgentConfidenceRadar 있음 — 중복 가능, 검토 필요) |
| 디자인 토큰 (cyan 배지, ultra-wide, 노란선) | 그대로 보존 |
| 11종 차트 컴포넌트 | 그대로 보존 |

---

## 6. 변경 파일 (예상 8-12개)

### 신규 (4)
- `frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx` — hub 화면 (작은 헤더 + 3 카드)
- `frontend/src/components/SimulationResult/dashboard/HubCard.tsx` — 3 카드 공통 컴포넌트 (hero 이미지 + 제목 + 설명 + 레이저 효과)
- `frontend/src/pages/DashboardPredictPage.tsx` — `/dashboard/predict` 라우트 페이지 (← Hub back + PredictGroup)
- `frontend/src/pages/DashboardAnalyzePage.tsx` — 동일 패턴
- `frontend/src/pages/DashboardAbmPage.tsx` — 동일 패턴

### 수정 (3-5)
- `frontend/src/App.tsx` — 라우트 정의 (`/dashboard`, `/dashboard/predict`, etc.) + 기존 SimulatorDashboard wrapper 제거
- `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` — **삭제** (DashboardHub 가 대체)
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx` — KPI 5개로 확장
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx` — 1등 동 + Top 3 추가
- (선택) `tailwind.config.cjs` — `animate-spin-slow` 정의 확인 (PricingCard 가 사용 중이라 이미 있을 가능성)

### 삭제 (검토 후)
- `KpiMiniGrid.tsx` — sub-tab 안에서 재사용 안 하면 삭제
- `GradeCard.tsx` — hub 에서 미사용 + 다른 곳 미사용이면 삭제

---

## 7. ui-ux-pro-max 가이드 체크리스트 (spec 단계 적용)

### CRITICAL (Pre-Delivery)
- [x] **Touch target ≥44pt** — 카드 전체가 클릭 영역 (자연 충족)
- [x] **Color contrast 4.5:1** — `text-stone-100 on bg-stone-900/60` (자연 충족)
- [x] **Focus visible** — `focus:ring-2 focus:ring-indigo-400`
- [x] **Reduced motion** — `motion-reduce:` modifier 적용
- [x] **Aria-label** — 카드 `<a>` 또는 `<button>` 에 `aria-label="예측 결과 화면 진입"` 등

### HIGH
- [x] **Mobile-first** — `grid-cols-1 lg:grid-cols-3`
- [x] **Image optimization** — Unsplash CDN + `loading="lazy"` + `width/height` 명시 (CLS 방지)
- [x] **Animation duration 150-300ms** — hover 효과 ease-out 300ms / 이미지 scale 700ms (decorative — meaning 있음 = 진입 의도 신호)
- [x] **Transform/opacity only** — scale, translate, opacity 만 (width/height 미사용)
- [x] **Style consistency** — 직전 cycle 의 stone/cyan/indigo/amber 토큰 그대로

### MEDIUM
- [x] **Spacing rhythm** — 8pt 시스템 (gap-6 = 24px, py-12 = 48px)
- [x] **Hierarchy** — 회사명 (큰) > 카드 제목 (중) > 설명 (작) > arrow (가장 작)
- [x] **Tabular numbers** — KPI 영역에서 사용 (이미 직전 cycle 토큰)

### LOW
- [x] **Loading state** — hub 진입 시 시뮬 결과 로딩 중이면 skeleton (현재 시뮬 진행 화면 SpotterAgentWorkflow 가 처리, hub 는 시뮬 완료 후 진입이라 즉시 렌더)

---

## 8. Out of Scope

- Backend 변경 0 (frontend 한정 — 직전 cycle 결정 일관)
- 시뮬 진행 화면 (SpotterAgentWorkflow) 변경 0 — hub 는 시뮬 완료 후 진입점만
- ABM 디테일 변경 0 — AbmGroup 그대로
- B1 의 Phase 1 backend 분리 (별 cycle)
- B2 미연동 ML endpoint 노출 (placeholder 유지)

---

## 9. 검증 (강민 brain verify 시나리오)

1. 시뮬 완료 → **DashboardHub 진입** (URL `/dashboard`) — 회사명 큰 글자 + 3 카드 가로
2. 카드 hover → **레이저 회전 + 이미지 scale + 카드 lift** (300-700ms)
3. 카드 클릭 → **디테일 페이지 진입** (예: `/dashboard/predict`)
4. 디테일 페이지 좌상단 **← Hub** 클릭 → **hub 복귀**
5. 브라우저 back 버튼 → 동일하게 hub 복귀
6. 새로고침 (`/dashboard/analyze?sub=market`) → 그 위치 그대로 복원
7. PredictSummaryTab 에서 KPI 5종 정상 (월매출/유동인구/경쟁강도/BEP/폐업위험도)
8. AnalyzeAiSummaryTab 에서 1등 동 ("공덕동") 큰 글자 + Top 3 칩
9. 기존 11종 차트 모두 그대로 동작
10. master `by 매니저명` 배지 (직전 cycle simulation_history) 그대로
11. manager 권한 (직전 cycle) 그대로 — manager 가 dashboard 진입 시 정상
12. 검은 wrapper 사라짐 — 페이지 톤이 자연스럽게 보임 (in-page content 느낌)
13. mobile (`375px`) 카드 stack 정상 + hero 이미지 적정 height
14. reduced-motion OS 설정 시 애니메이션 비활성

---

## 10. References

- 직전 cycle: `docs/superpowers/specs/2026-04-28-3group-tab-restructure-design.md`
- ui-ux-pro-max 가이드 (이 spec 의 §7 에 체크리스트 반영)
- ServiceCard 패턴 (사용자 제공) — hover scale + arrow 영감
- ProjectCard 패턴 (사용자 제공) — hero image + 제목/설명/CTA 구조
- PricingCard (`frontend/src/pages/JoinUs/components/PricingCard.tsx:28-31`) — 레이저 효과 (`conic-gradient + animate-spin-slow`)
- 메모리: `feedback_runtime_verification.md`, `feedback_commit_policy.md`
