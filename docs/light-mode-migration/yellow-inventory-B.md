# Phase 0-B: 노란색 사용처 인벤토리

## 요약

**총 노란색 인스턴스: 130+**

- **stripe** (3px 띠): 4
- **badge** (뱃지/상태): 51
- **status-warning** (경고 상태): 22
- **chart** (차트 색): 8
- **text** (글자색): 18
- **decoration-large** (큰 장식 면적): 8
- **other**: 19

### 핵심 발견
- **stripe 3px 띠는 4개만 존재** (InsightsGrid.tsx에 집중) — Deep Blue 교체 용이
- **badge 51개가 대부분** (amber-500/10, amber-400 등) — status-warning 계열과 mix
- **#f59e0b, #fbbf24 hex색은 10개** (차트, 지도 시각화)
- **yellow-500 계열은 5개만** (InsightsGrid, HistoryCard, LegalDrawer)

---

## stripe (3px 띠 — Deep Blue 교체 대상) [4건]

### Legal 테이블 구분선
| 파일 | 라인 | 코드 | 용도 |
|------|------|------|------|
| InsightsGrid.tsx | 136 | w-[3px] rounded-r \ | MEDIUM 위험도 행 좌측 3px |
| InsightsGrid.tsx | 192 | w-[3px] rounded-r \ | 안전군 행 좌측 3px |
| App.tsx | 3733 | order-l-2 border-amber-400 | 체크리스트 좌측 2px |
| MarketMap.tsx | 138 | order:2px solid #ffffff | 승자 마커 2px |

**교체 지점**: InsightsGrid.tsx:33 LEVEL_CLS[MEDIUM].strip = 'bg-yellow-500' → 'bg-[#002CD1]'

---

## badge (뱃지/상태 라벨) [51건]

### 분포 요약
- App.tsx (13): 공실 미반영, 주의, 설정 패널
- PersonaCard.tsx (6): 카드 테두리, 아바타, 텍스트
- AbmPersonaMap.tsx (11): 로딩, 에러, 지도 오버레이
- 대시보드 (15): 상태 카드, 신호, 범례
- 경고 박스 (10): TokenBurnrate, HQCommandCenter

### 패턴
- g-amber-500/10 border border-amber-500/30 text-amber-400 (표준)
- g-amber-500/20 text-amber-300 (강조)

**라이트모드 검증 필요**: #FAF9F5 배경에서 가독성

---

## status-warning (경고 상태) [22건]

### yellow-500 교체 대상
| 파일 | 라인 | 패턴 |
|------|------|------|
| InsightsGrid.tsx | 33 | LEVEL_CLS[MEDIUM].strip = 'bg-yellow-500' |
| LegalDrawer.tsx | 22 | bg-yellow-500/10 text-yellow-400 |
| HistoryCard.tsx | 15 | yellow signal badge |
| DistrictRankings.tsx | 10 | caution: text-yellow-400 |
| ShapChart.tsx | 59 | bg-yellow-500/20 text-yellow-400 |

### amber 유지 검토
- App.tsx (주의 레벨)
- HQCommandCenter (경고 박스)
- TokenBurnrate (배너)

---

## chart (차트 색) [8건]

### Hex 매핑
| Hex | 파일 | 용도 | 토큰 |
|-----|------|------|------|
| #fbbf24 | QuarterlyProjectionChart | 라인 색 | --chart-3 |
| #f59e0b | MarketMap, HubCard | 마커 색 | --chart-accent |
| #eab308 | CannibalizationDistanceChart | 배열 색 | --chart-warn |

---

## text (글자색 — 라이트모드 위험) [18건]

### 배경 없는 텍스트 (위험도 높음)
- SignupForm.tsx:470,472 text-amber-400
- IndicatorGrid.tsx:38 text-yellow-400
- DistrictRankings.tsx:10 text-yellow-400

### 배경 있는 텍스트 (안전)
- 배경/테두리 포함 대부분 amber

---

## decoration-large (큰 면적 — 옐로우 톤 유지 검토) [8건]

### 그라디언트 & 배경
- AbmPersonaMap.tsx:2676 from-amber-500/[0.04]
- TokenBurnrate.tsx:58 bg-amber-500/5
- HQCommandCenter.tsx (3개 박스) bg-amber-500/5

**의사결정 대기**: cream-yellow 유지 vs 중립색 교체

---

## other (동적/조건부) [19건]

- 호버: hover:bg-amber-500/[0.06]
- 그로우: shadow-[0_0_15px_rgba(245,158,11,0.4)]
- 색상맵: DashboardPanelView colorMap rotation

---

## Phase 2 실행 순서

### 1단계: stripe (파일 2개, 4줄)
InsightsGrid.tsx L33: bg-yellow-500 → bg-[#002CD1]
App.tsx L3733: border-amber-400 → border-indigo-500

### 2단계: yellow 배지 (파일 4개, 5줄)
HistoryCard, LegalDrawer, InsightsGrid, ShapChart yellow → deep blue

### 3단계: 차트 토큰 (6개 파일, 8줄)
--chart-3, --chart-accent CSS 변수 추가

### 4단계: 라이트모드 텍스트 (검토 필요)
배경 없는 amber/yellow text → 색상 or dark-only 변경

---

## 파일 목록 (가나다순)

총 42개 파일, 130+ hit
1. src/App.tsx (13)
2. src/components/AbmPersonaMap.tsx (11)
3. src/components/PersonaCard.tsx (6)
4. src/components/SimulationResult/sections/InsightsGrid.tsx (4)
5. src/components/SimulationResult/sections/MarketMap.tsx (10)
6. src/components/TokenBurnrate/TokenBurnrateSection.tsx (5)
7. src/pages/HQCommandCenter.tsx (10)
8. 기타 35개 파일

---

작성: 2026-04-30 | 전수 조사: src/ 160개 파일 | 제외: reference/figma-crm-kit/