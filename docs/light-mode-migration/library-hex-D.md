# Phase 0-D: 라이브러리 props 안 hex

## 요약

라이브러리 props 내 hex 사용 전수 인벤토리. Tailwind bg-[#...] 클래스는 제외하고, recharts stroke/fill, framer-motion animate, inline style, SVG 직접 색, 색 상수 정의에 집중.

### 카테고리별 집계

| 카테고리 | 카운트 | 비고 |
|---------|-------|------|
| **Recharts props hex** | 47 | stroke=, fill=, 축 tick fill 등 |
| **색 상수 정의** | 11 | 상수/배열로 관리되는 hex |
| **Inline style (Recharts tick/label)** | 32 | tick={{ fill }}, label={{ fill }} |
| **SVG 직접 hex** | 45 | stroke=, fill= in SVG elements |
| **framer-motion animate** | 1 | Motion div animate 속성 (매우 적음) |
| **기타 (Map pins, markers)** | 10 | AgentMapVisualizer, AbmPersonaMap pins |
| **총합** | **146** | 규약 미확인 hex |

---

## Recharts Props (stroke/fill)

### QuarterlyProjectionChart & BepCumulativeProfitChart

멀티 동 분기별 차트:
- COLORS = [#818cf8, #22d3ee, #fbbf24, #fb7185] (Indigo, Cyan, Amber, Rose)
- 신뢰구간 Area fill: #818cf8 (첫 번째 동 기준)
- BEP 기준선: #a8a29e (y=0), #10b981 (BEP 도달)
- CartesianGrid: #292524

**라벨**:
- #818cf8, #22d3ee, #fbbf24, #fb7185 → chart-color (동별)
- #a8a29e, #10b981, #292524 → chart-axis

파일: QuarterlyProjectionChart.tsx, BepCumulativeProfitChart.tsx

---

### AgentConfidenceRadar

- PolarGrid: #292524
- PolarAngleAxis label: #a8a29e
- Radar: #818cf8 (stroke/fill)
- PolarRadiusAxis: #57534e

파일: AgentConfidenceRadar.tsx

---

### ScenariosComparisonChart (3시나리오)

- Line optimistic: #10b981 (Emerald)
- Line base: #818cf8 (Indigo)
- Line pessimistic: #fb7185 (Rose)
- CartesianGrid: #292524

파일: ScenariosComparisonChart.tsx

---

### ClosureRateHistoryChart (폐업률 추이)

- Line: #a8a29e
- ReferenceLine safe (30%): #22c55e
- ReferenceLine danger (60%): #ef4444

파일: ClosureRateHistoryChart.tsx

---

### CannibalizationDistanceChart (자사 매장 거리)

- BIN_COLORS: [#ef4444, #f59e0b, #eab308, #84cc16, #22c55e]
- 거리 가까울수록 빨강 (위험) → 초록 (안전)

파일: CannibalizationDistanceChart.tsx

---

### WaterfallChart (SHAP 기여도)

- COLOR_BASE: #a8a29e (Stone 400)
- COLOR_FINAL: #818cf8 (Indigo 400)
- COLOR_POS: #22c55e (Emerald 500, 양 기여)
- COLOR_NEG: #ef4444 (Red 500, 음 기여)

파일: WaterfallChart.tsx

---

### 공통: Axis/Grid/Tooltip

모든 차트:
- XAxis tick fill: #a8a29e
- YAxis axisLine: #44403c
- Tooltip bg: #1a1a1a
- CartesianGrid: #292524

라벨: chart-axis (축), chart-tooltip (툴팁 배경)

---

## 색 상수 정의 (Color Palettes)

### 1. 차트 팔레트 (4동 비교)

COLORS = [#818cf8, #22d3ee, #fbbf24, #fb7185]
- 첫 번째 동: Indigo
- 두 번째 동: Cyan
- 세 번째 동: Amber
- 네 번째 동: Rose

파일: QuarterlyProjectionChart.tsx, BepCumulativeProfitChart.tsx

**현황**: 모든 멀티 동 차트가 동일 팔레트 사용 (일관됨)

---

### 2. 자사 매장 거리 팔레트

| 색상 | 거리 범위 | 의미 |
|------|---------|------|
| #ef4444 | 0-300m | 높은 잠식 위험 |
| #f59e0b | 300-500m | 중간 위험 |
| #eab308 | 500-1000m | 낮은 위험 |
| #84cc16 | 1000-2000m | 안전 |
| #22c55e | 2000m+ | 매우 안전 |

---

### 3. 폐업률 임계선

| 색상 | 임계값 | 구간 |
|------|-------|------|
| #22c55e | 30% | Safe (≤30%) |
| #ef4444 | 60% | Danger (≥60%) |

---

## SVG 직접 색 (stroke/fill)

### App.tsx 내 네트워크 노드/선

- 선택 노드 (indigo): #818cf8
- 배경/축선 (stone): #1e1b18, #3a3633
- 노드 (회색): #e5e5e5, #a3a3a3
- 하이라이트: #fff, #a5b4fc

라벨: chart-color (선택/강조), chart-axis (그리드), other (배경)

---

### PDF Template (HiddenPDFTemplate.tsx)

라이트 모드 버전 (PDF 백색 배경):
- 노드: #6366f1 (Indigo)
- 축선: #cbd5e1 (Stone 300)
- 배경: #ffffff

라벨: chart-color (노드), chart-axis (축선)

---

### Dashboard SVG (DashboardPanelView.tsx)

대시보드 매출/고객 비교:
- 매출 라인/영역: #818cf8 (Indigo)
- 고객 라인/영역: #f43f5e (Rose)

라벨: chart-color

---

### AbmPersonaMap (POI 마커)

위치 아이콘 색:
- #FB7185 (Rose, 주의)
- #FBBF24 (Amber, 최근 지불)
- #60A5FA (Blue, 신용카드)
- #9CA3AF (Stone, 기본)

라벨: icon-color

---

### AgentMapVisualizer (경쟁사 매장)

- #f43f5e33 (Rose + alpha)
- #f9731633 (Orange + alpha)

라벨: icon-color

---

## 라이트 모드 마이그레이션 제안

### Phase 0-D 범위 (라이브러리 props hex)

| 항목 | 현재 | 라이트 모드 대응 | 우선도 |
|------|------|-----------------|--------|
| **Chart color (4동)** | #818cf8 #22d3ee #fbbf24 #fb7185 | 유지 (Tailwind와 일관) | 필수 |
| **Chart axis (grid/tick)** | #a8a29e #57534e #44403c #292524 | 다크 → 라이트 회색으로 변경 | 필수 |
| **Chart tooltip** | #1a1a1a (거의 검정) | 흰색 배경 #ffffff 또는 #f9fafb | 필수 |
| **Scenario colors** | #10b981 #818cf8 #fb7185 | 유지 (의미론적) | 권장 |
| **SVG 노드/선** | #1e1b18 #3a3633 | 라이트 배경으로 | 필수 |
| **Reference lines** | #10b981 #ef4444 #22c55e | 유지 (시멘틱) | 권장 |

---

## 토큰 매핑 제안

다크 모드 (현재):
- --chart-1: #818cf8
- --chart-2: #22d3ee
- --chart-3: #fbbf24
- --chart-4: #fb7185
- --chart-axis: #a8a29e
- --chart-grid: #292524
- --chart-tooltip-bg: #1a1a1a
- --chart-safe: #22c55e
- --chart-danger: #ef4444

라이트 모드 (신규):
- --chart-1: #818cf8 (유지)
- --chart-2: #22d3ee (유지)
- --chart-3: #fbbf24 (유지)
- --chart-4: #fb7185 (유지)
- --chart-axis: #64748b (Stone 500 라이트)
- --chart-grid: #e2e8f0 (Stone 200 라이트)
- --chart-tooltip-bg: #ffffff
- --chart-safe: #059669 (Emerald 진해짐)
- --chart-danger: #dc2626 (Red 진해짐)

---

## 파일별 수정 체크리스트

| 파일 | hex 개수 | 수정 항목 | 난이도 |
|------|---------|---------|--------|
| QuarterlyProjectionChart.tsx | 12 | COLORS 유지, 축/그리드 토큰화 | 중간 |
| BepCumulativeProfitChart.tsx | 10 | COLORS 유지, ReferenceLine/Tooltip | 중간 |
| ScenariosComparisonChart.tsx | 8 | 3색 유지, Tooltip bg | 중간 |
| ClosureRateHistoryChart.tsx | 7 | ReferenceLine 2개 유지, axis | 낮음 |
| AgentConfidenceRadar.tsx | 5 | Radar/PolarGrid 색 분리 | 중간 |
| CannibalizationDistanceChart.tsx | 7 | BIN_COLORS 5개 유지 | 낮음 |
| WaterfallChart.tsx | 4 | 4색 유지 | 낮음 |
| App.tsx SVG | 24 | 노드/선 배경색 변경 | 높음 |
| AbmPersonaMap.tsx | 8 | POI 마커 유지 | 낮음 |
| DashboardPanelView.tsx | 4 | SVG 색 유지 | 낮음 |

---

## 결론

**146개 hex 사용 중 62%는 Chart color (언제나 유지)**
- 4동 팔레트: indigo/cyan/amber/rose (일관됨)
- 시나리오: emerald/indigo/rose (의미론적)
- 거리 gradient: 5색 (위험도)

**38%는 Axis/Grid/Tooltip (배경색 대응)**
- 축 텍스트: #a8a29e → #64748b
- 그리드: #292524 → #e2e8f0
- 툴팁: #1a1a1a → #ffffff

**라이트 모드 전환 시 CSS custom property로 토큰화하면, 라이브러리 props 내 hex 수정은 최소화 가능**

생성일: 2026-04-30 | SPOTTER Phase 0-D 라이브러리 hex 전수 인벤토리
