# Phase 2 영역 ⑤ 보고 — 차트 라이브러리 props (잔여 hex)

> 영역 ⑤ 책임 = 영역 ②/③/④ 가 처리하지 않은 *Tailwind 클래스 외* hex (recharts/SVG/inline style/색 상수).
> 영역 ②/③/④ 의 디렉토리 내 파일 + App.tsx + HiddenPDFTemplate.tsx + figma-crm-kit/** + *.test.tsx 는 영역 ⑤ 외.

## 통계

- 검토한 파일 (전수): 53개 (frontend/src 내 hex 사용처 모두)
- 영역 ⑤ 책임 파일 (다른 영역 디렉토리 외): 4개
- 실제 변환 파일: 1개
- 치환 hex 인스턴스: **2건** (SVG fill)
- 영향 파일: 1개
- dark: prefix 폐기: 0건 (해당 없음)
- unmapped (보고): 6건 (alpha-bearing 8자리 hex, 변환 보류)
- 다른 영역 위임: 144건 (146건 중 2건만 영역 ⑤ 처리)

## 검토한 파일 목록

### 영역 ⑤ 가 처리한 파일 (1)

| 파일 | hex 인스턴스 | 처리 |
|---|---|---|
| `src/pages/LoginPage.tsx` | SVG `fill="#818cf8"` × 2 (line 116, 120) | → `var(--primary)` |

### 영역 ⑤ 책임이지만 변환 보류 — Unmapped 또는 충돌 위험 (3)

| 파일 | hex 인스턴스 | 사유 |
|---|---|---|
| `src/components/AgentMapVisualizer.tsx` | 8건 (인라인 var + SVG fill/stroke + 8자리 alpha hex) | alpha-bearing hex (`#f43f5e33`, `#f9731633`) 는 conversion-rules.md 표에 매핑 없음. 단색은 동시 작업 중인 다른 영역과 충돌 위험. |
| `src/components/AbmPersonaMap.tsx` | 50+ 건 (canvas ctx hex, 색 상수, SVG stroke/fill) | 다수가 4동 차트 팔레트 (`#34D399`, `#60A5FA`, `#F472B6`, `#FBBF24`, `#22D3EE`, `#A78BFA`)인데 §11 ABM POI 마커 4색 매핑은 다른 색 코드(`#FB7185`/`#FBBF24`/`#60A5FA`/`#9CA3AF`). canvas ctx 는 string concat 으로 var() 적용 시 invalid CSS 위험. 동시에 다른 영역 작업 중. |
| `src/components/VacancySpotMarker.tsx` | 3건 (Kakao Maps marker style hex `#E45756`) | `#E45756` 는 conversion-rules.md 표에 *없음*. AbmPersonaMap 의 visit 마커 색과 동일 (line 27). Kakao Maps SDK 가 inline style string 으로 hex를 요구해 var() 적용 가능 여부 검토 필요. |

### 영역 ⑤ 외 — 다른 영역(②/③/④/①)이 처리 중 (위임)

App.tsx, src/components/SimulationResult/**, src/components/simulation/**, src/components/dashboard/**, src/pages/dashboard/**, src/components/GlobalNav.tsx, src/components/PDF/HiddenPDFTemplate.tsx, src/reference/figma-crm-kit/**, *.test.tsx — task 설명대로 손대지 않음.

기타 보조 파일들 (영역 ⑤ 검토 대상이지만 hex 0건):
- `src/utils/`, `src/hooks/`, `src/api/`, `src/auth/`, `src/contexts/`, `src/data/`, `src/stores/`, `src/viewmodels/`, `src/constants/`, `src/test/` — hex 사용 0건
- `src/types/index.ts` — `#107`, `#106` 은 GitHub issue 번호 (색 hex 아님)
- `src/components/NetworkBackground.tsx`, `src/components/PersonaCard.tsx`, `src/components/kakao/**` — hex 0건

기타 보조 파일들 (Tailwind class hex 만 — 영역 ⑤ 외, 영역 ① 등 Tailwind subagent 담당):
- `src/components/BrandLogo.tsx`, `src/components/CommandPalette.tsx`, `src/components/DetailDrawer.tsx`, `src/components/Toast.tsx`, `src/components/VacancyStatsPanel.tsx`, `src/components/SimulationHistory/HistoryFilter.tsx`, `src/components/TokenBurnrate/TokenBurnrateSection.tsx`, `src/components/ui/HybridSliderInput.tsx` 등 — `bg-[#xxx]`/`text-[#xxx]`/`border-[#xxx]` 만 사용 (Tailwind arbitrary value)

## 파일별 변경 요약

- `src/pages/LoginPage.tsx`: 2건 (SPOTTER 로고 SVG `fill="#818cf8"` × 2 → `fill="var(--primary)"`)

## Unmapped (강민 결정 필요)

| file:line | hex | 추정 맥락 |
|---|---|---|
| `src/components/AgentMapVisualizer.tsx:282` | `${pinColor}33` (=`#818cf833`) | MapPin fill, alpha 0x33. var() concat 불가. |
| `src/components/AgentMapVisualizer.tsx:322` | `${pinColor}33` (=`#f43f5e33` 또는 `#f9731633`) | SVG polygon fill. |
| `src/components/AgentMapVisualizer.tsx:329` | `${pinColor}22` (=alpha 0x22 변형) | 텍스트 background. |
| `src/components/AgentMapVisualizer.tsx:365` | `#f43f5e33` | SVG legend polygon fill (Rose alpha 20%). |
| `src/components/AgentMapVisualizer.tsx:376` | `#f9731633` | SVG legend polygon fill (Orange alpha 20%). |
| `src/components/VacancySpotMarker.tsx:43,72,75` | `#E45756` (3회) | Kakao Maps SDK marker style. conversion-rules.md 미수록 색 (단 AbmPersonaMap.tsx visit 마커와 동일 → §7 danger 그룹 후보 = `var(--danger)`). |

추가 결정 필요:
- alpha-bearing 8자리 hex 처리 룰 (`#xxxxxxAA`) — `color-mix(in srgb, var(--token) N%, transparent)` 로 변환할지, 아니면 별도 `--token-alpha-20` 같은 token 추가할지.
- AbmPersonaMap.tsx 의 6동 색 팔레트 (`#34D399`/`#60A5FA`/`#F472B6`/`#FBBF24`/`#22D3EE`/`#A78BFA`) — §6 4동 chart 색 (chart-1~4) 외 추가 chart-5/chart-6 token 필요 여부.
- Kakao Maps SDK style props 가 CSS var()를 받을 수 있는지 (런타임 SDK 가 hex string parse 할 가능성 → var() 거부 위험).

## tsc / prettier 결과

- `npx prettier --write src/pages/LoginPage.tsx` → PASS (1 file formatted)
- `npx tsc --noEmit` → PASS (no output, no errors)

## 결론

- 영역 ⑤ 의 실제 변환 작업은 **2건** (LoginPage.tsx SVG fill).
- 나머지 144건은 영역 ②/③/④/① 의 디렉토리 내에 있어 다른 영역이 처리. (`library-hex-D.md` 의 파일별 체크리스트 기준 QuarterlyProjectionChart=12, BepCumulativeProfitChart=10, ScenariosComparisonChart=8, ClosureRateHistoryChart=7, AgentConfidenceRadar=5, CannibalizationDistanceChart=7, WaterfallChart=4, App.tsx SVG=24, DashboardPanelView=4 등 → 모두 다른 영역 책임)
- AgentMapVisualizer / AbmPersonaMap / VacancySpotMarker 는 영역 ⑤ 책임이지만 conversion-rules.md 표 미수록 색 + alpha-bearing hex 가 다수라 **unmapped 보고** 후 변환 중단. 동시에 다른 영역이 같은 파일에서 Tailwind hex 를 변환 중이라 충돌 위험도 있음.

생성일: 2026-04-30 | SPOTTER Phase 2 영역 ⑤ 종료
