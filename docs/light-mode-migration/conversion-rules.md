# 변환 룰 — hex → 시맨틱 토큰 매핑 (Phase 2 단일 진실)

> Phase 2 모든 subagent 가 이 표를 따라야 합니다. 임의 판단 금지.
> 표에 없는 hex 발견 시 → **변환 중단, 보고**.
> 룰 출처: Phase 0-A/B/D 카탈로그 + 강민 결정 12색 시스템.

## 0. 핵심 원칙

1. **System A (배경/구조)** 와 **System B (12색)** 외 색은 절대 추가하지 않는다.
2. Tailwind 클래스 임의값 `bg-[#xxx]` 는 모두 **시맨틱 클래스** (`bg-background`/`bg-card`/`bg-primary` 등) 로 치환.
3. CSS in JS / inline style / recharts props 의 hex 는 **CSS 변수** (`var(--primary)` 등) 로 치환.
4. `dark:` prefix 는 만나면 **그 자리에서 폐기**, 라이트값만 남김 (Phase 0-C 확인).
5. 본인 영역(디렉토리/라인범위) 밖 파일은 *수정 금지*.

## 1. 배경/표면 (System A)

| from | to (Tailwind) | to (CSS var) | 맥락 |
|---|---|---|---|
| `bg-[#0c0b0a]` `bg-[#0d1117]` `bg-[#1C1D21]` `bg-[#141210]` | `bg-background` | `var(--background)` | 페이지 배경 |
| `bg-[#1a1a1a]` `bg-[#1a1816]` `bg-[#1e1b18]` `bg-[#2c2825]` | `bg-card` | `var(--card)` | 카드/패널/모달 표면 |
| `bg-[#171717]` `bg-[#404040]` `bg-[#57534e]` | `bg-muted` | `var(--muted)` | 사이드바/nav/secondary surface |
| `bg-[#050505]/70` `bg-[#000000]/N` | `bg-black/70` | `rgba(0,0,0,0.7)` | 모달 backdrop (그대로) |

## 2. 텍스트

| from | to (Tailwind) | to (CSS var) |
|---|---|---|
| `text-[#e2e8f0]` `text-[#d6d3d1]` `text-[#ffffff]` | `text-foreground` | `var(--foreground)` |
| `text-[#9ca3af]` `text-[#6b7280]` `text-[#a8a29e]` `text-[#a3a3a3]` `text-[#d1d5db]` `text-[#666666]` | `text-muted-foreground` | `var(--muted-foreground)` |

## 3. 테두리/구분선

| from | to (Tailwind) | to (CSS var) |
|---|---|---|
| `border-[#3a3633]` `border-[#292524]` `border-[#44403c]` `border-[#4a4643]` `border-[#57534e]` `border-[#cbd5e1]` `border-[#e5e7eb]` | `border-border` | `var(--border)` |

## 4. Brand / Primary (Indigo → Deep Blue 통합)

| from | to (Tailwind) | to (CSS var) | 맥락 |
|---|---|---|---|
| `bg-[#818cf8]` `text-[#818cf8]` `border-[#818cf8]` | `bg-primary` `text-primary` `border-primary` | `var(--primary)` | indigo → Deep Blue 통합 |
| `bg-[#6366f1]` `text-[#6366f1]` (그라디언트 stop 포함) | `bg-primary` | `var(--primary)` | indigo-500 통합 |
| `bg-[#4f46e5]` `text-[#4f46e5]` | `bg-primary` | `var(--primary)` | indigo-600 통합 |
| `bg-[#a5b4fc]` `text-[#a5b4fc]` | `bg-primary/60` 또는 `var(--primary)` + opacity | indigo-300 (밝은 변형) |
| `from-[#6366f1] to-[#818cf8]` | `from-primary to-primary` 또는 단색 `bg-primary` | gradient는 단색으로 단순화 권장 |

## 5. 시나리오 차트 3색 (의미적 매핑 — 단 12색 안에서)

| from | to (CSS var) | 의미 |
|---|---|---|
| `#10b981` `#22c55e` (Emerald, 낙관/성공) | `var(--success)` = Teal Green | success |
| `#818cf8` (Indigo, 기본) | `var(--primary)` = Deep Blue | primary |
| `#fb7185` `#ef4444` `#f43f5e` (Rose/Red, 비관/위험) | `var(--danger)` = Vivid Red | danger |
| `#FF808B` (다크 분홍) | `var(--danger)` | danger 통합 |

## 6. 4동 비교 차트 4색

| 기존 (Phase 0-D 발견) | 새 매핑 |
|---|---|
| `COLORS = ['#818cf8', '#22d3ee', '#fbbf24', '#fb7185']` | `COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)']` |
| 1동 `#818cf8` | `var(--chart-1)` Deep Blue |
| 2동 `#22d3ee` | `var(--chart-2)` Vivid Red |
| 3동 `#fbbf24` | `var(--chart-3)` Teal Green |
| 4동 `#fb7185` | `var(--chart-4)` Vibrant Purple |

## 7. 상태 색 (Warning / Success / Danger)

| from | to (Tailwind) | to (CSS var) |
|---|---|---|
| `bg-yellow-500` `bg-amber-500` `bg-amber-400` `text-amber-*` `text-yellow-*` `#f59e0b` `#f97316` `#fbbf24` `#fde047` `#facc15` | `bg-warning` `text-warning` | `var(--warning)` |
| `bg-green-500` `bg-emerald-*` `text-green-*` `text-emerald-*` `#10b981` `#22c55e` `#16a34a` | `bg-success` `text-success` | `var(--success)` |
| `bg-red-500` `text-red-*` `#ef4444` `#dc2626` `#fb7185` `#f43f5e` `#FF808B` | `bg-danger` `text-danger` (또는 `bg-destructive`) | `var(--danger)` |

> `bg-warning` 의 fg 는 `text-warning-foreground` (`#FFFFFF`).

## 8. 노란 3px 띠 → Deep Blue 띠

InsightsGrid.tsx 가 핵심 (1줄 수정으로 전부 해결):

```diff
- const LEVEL_CLS = { MEDIUM: { strip: 'bg-yellow-500', ... } }
+ const LEVEL_CLS = { MEDIUM: { strip: 'bg-primary', ... } }
```

기타 노란 띠:
- `App.tsx:3733` `border-amber-400` → `border-primary`
- 텍스트로서의 `text-yellow-*` 는 라이트 배경 컨트라스트 미달 → `text-warning` 으로

## 9. 거리 잠식 5색 gradient (Cannibalization)

| from | to (CSS var) | 비고 |
|---|---|---|
| `#ef4444` (가장 위험) | `var(--danger)` | |
| `#f59e0b` (위험) | `var(--warning)` | |
| `#eab308` (중간) | `var(--decor-yellow)` | 큰 면적 채우기라 OK |
| `#84cc16` (안전) | `var(--decor-cyan)` | 12색 룰: cyan을 안전 표시로 |
| `#22c55e` (매우 안전) | `var(--success)` | |

## 10. SHAP Waterfall (양/음 기여)

| from | to (CSS var) |
|---|---|
| `COLOR_POS = '#22c55e'` | `var(--success)` |
| `COLOR_NEG = '#ef4444'` | `var(--danger)` |
| `COLOR_BASE = '#a8a29e'` | `var(--muted-foreground)` |
| `COLOR_FINAL = '#818cf8'` | `var(--primary)` |

## 11. ABM POI 마커 4색 (4동 차트와 별개, 12색 안)

| 기존 | 새 매핑 |
|---|---|
| `#FB7185` Rose (주의) | `var(--danger)` |
| `#FBBF24` Amber (지불) | `var(--warning)` |
| `#60A5FA` Blue (카드) | `var(--primary)` |
| `#9CA3AF` Stone (기본) | `var(--muted-foreground)` |

## 12. 차트 axis/grid/tooltip

| from | to (CSS var) |
|---|---|
| XAxis tick fill `#a8a29e` | `var(--muted-foreground)` |
| YAxis axisLine `#44403c` `#57534e` | `var(--border)` |
| CartesianGrid stroke `#292524` | `var(--border)` |
| Tooltip bg `#1a1a1a` | `var(--card)` (`#FFFFFF`) |
| Tooltip text | `var(--card-foreground)` |

## 13. 큰 면적 장식 (Decoration only — 데이터 자리 사용 금지)

| from | to (CSS var) |
|---|---|
| `#F8F7E8` (cream 배경 강조) | `var(--accent)` 또는 `var(--decor-cream)` |
| `#FFDE00` (노란 배경 큰 영역) | `var(--decor-yellow)` |
| `#00E0D1` (cyan 큰 배경) | `var(--decor-cyan)` |
| `#FFB6D0` (pink 큰 배경) | `var(--decor-light-pink)` |
| `#FF0070` (hot pink 큰 액센트) | `var(--decor-hot-pink)` |
| `#FF78B9` (starburst pink) | `var(--decor-starburst-pink)` |

## 14. 처리 금지 / 보존

| 패턴 | 처리 |
|---|---|
| `#ffffff` 단독 (텍스트/단색 표면) | 그대로 둘지 (`text-foreground`/`bg-card`) 검토 — 단순 흰색 borderColor 등은 유지 OK |
| `frontend/src/reference/figma-crm-kit/**` | **수정 금지** (Figma reference, SPOTTER 토큰과 무관) |
| `HiddenPDFTemplate.tsx` | **수정 금지** (PDF 인쇄용, Q6 결정대로 제외) |
| 테스트 파일 (`*.test.tsx`) | hex가 있어도 일단 *건드리지 않음* (스냅샷 영향) |

## 15. 절차

각 영역 subagent 작업 흐름:

1. 본인 영역 디렉토리/라인범위의 `bg-[#`, `text-[#`, `border-[#`, `from-[#`, `to-[#`, `via-[#`, `ring-[#`, `outline-[#`, `divide-[#`, `placeholder:text-[#`, `style={{ ... '#`, `stroke="#"`, `fill="#"` 검색
2. 표 1~14 매핑대로 치환
3. 표에 없는 hex 발견 → **그 hex 위치 기록 후 변환 중단**, 보고서에 `unmapped` 섹션
4. `dark:` prefix 발견 → 그 자리에서 폐기, 라이트값만 남김
5. 영역 작업 완료 후 `npx prettier --write <영역 파일>` + `npx tsc --noEmit` (전역) 실행
6. 변경 카운트 보고: 치환 N건, dark 폐기 K건, unmapped P건

## 16. 보고 형식

각 subagent 가 종료 시 다음 markdown 작성:
`docs/light-mode-migration/phase-2-{영역키}-report.md`

```
# Phase 2 영역 X 보고

## 통계
- 치환 hex 인스턴스: N
- 영향 파일: K
- dark: prefix 폐기: P
- unmapped (보고): Q

## 파일별 변경 요약
- src/...: N건

## Unmapped (강민 결정 필요)
| file:line | hex | 추정 맥락 |

## tsc / prettier 결과
PASS / FAIL
```
