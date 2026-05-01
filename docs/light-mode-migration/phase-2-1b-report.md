# Phase 2 영역 1b 보고 — App.tsx 라인 2401~끝

## 통계
- 치환 hex 인스턴스: **약 90건** (Tailwind 클래스 + SVG stroke/fill + 인라인 style)
- 영향 파일: 1 (`src/App.tsx`만 수정, 라인 2401 이후만)
- `dark:` prefix 폐기: **0건** (해당 범위에 `dark:` 없음)
- unmapped (보고): **1건** (`#e5e5e5`)

## 파일별 변경 요약

### `src/App.tsx` (라인 ~2401-끝)

#### 주요 치환 카테고리

| 패턴 | 매핑 대상 | 인스턴스 수 (대략) |
|---|---|---|
| `bg-[#2c2825]` `bg-[#1e1b18]` (카드/패널/모달) | `bg-card` | ~25 |
| `border-[#3a3633]` (테두리) | `border-border` | ~20 |
| `text-[#9ca3af]` (보조 텍스트) | `text-muted-foreground` | ~25 |
| `text-[#e2e8f0]` (본문 텍스트) | `text-foreground` | ~15 |
| `text-[#818cf8]` `bg-[#818cf8]` (브랜드 액션) | `text-primary` `bg-primary` | ~15 |
| `bg-[#1e1b18]/50` `bg-[#1e1b18]/40` (반투명 카드) | `bg-card/50` 등 | ~10 |
| `text-[#a5b4fc]` (밝은 indigo) | `text-primary` | 2 |
| `text-[#a3a3a3]` (회색 텍스트) | `text-muted-foreground` 또는 `var(--muted-foreground)` | 9 (radar SVG 포함) |
| `bg-[#3a3633]` (border-as-bg 토글 active) | `bg-border` | ~8 |
| `bg-[#171717]` (드로어 secondary surface) | `bg-muted` | 2 |
| `bg-[#050505]/70` (backdrop) | `bg-black/70` | 1 |
| `bg-[#0C0B0A]` (DashboardOutlet bg) | `bg-background` | 1 |
| `from-[#6366f1] to-[#818cf8]` (그라디언트 버튼) | `bg-primary` (단색 단순화) | 1 |
| 노란 띠 `border-amber-400` (line 3733 부근) | `border-primary` | 1 |
| `bg-[#1a1816]` `bg-[#141210]` 등 다크 surface | (해당 범위에 없음, 1~2400 영역) | 0 |
| SVG `stroke="#3a3633"` (radar grid) | `stroke="var(--border)"` | 9 |
| SVG `stroke="#818cf8"` `stroke="#6366f1"` `stroke="#a5b4fc"` (radar/preloader) | `stroke="var(--primary)"` | 11 |
| SVG `fill="#1e1b18"` (radar bg) | `fill="var(--card)"` | 1 |
| SVG `fill="#a3a3a3"` (radar 라벨) | `fill="var(--muted-foreground)"` | 6 |
| `stopColor="#818cf8"` `stopColor="#9ca3af"` (recharts gradient) | `stopColor="var(--primary)"` `stopColor="var(--muted-foreground)"` | 4 |
| `stroke="#9ca3af"` `stroke="#d1d5db"` (recharts axis/area) | `stroke="var(--muted-foreground)"` | 4 |
| `tick={{ fill: '#d1d5db' }}` (recharts) | `tick={{ fill: 'var(--muted-foreground)' }}` | 1 |
| inline `cursor: stroke: '#818cf8'` (recharts) | `'var(--primary)'` | 1 |
| `style={{ filter: 'drop-shadow(0 0 8px #a5b4fc)' }}` (preloader) | `'drop-shadow(0 0 8px var(--primary))'` | 1 |

#### 보존된 hex (수정하지 않음)

| 위치 | hex | 사유 |
|---|---|---|
| L3228 (radar dot) | `#fff` | §14 단순 흰색 보존 |
| L4834, L4835 (preloader endpoint dot) | `#ffffff` | §14 단순 흰색 보존 |

## Unmapped (강민 결정 필요)

| file:line | hex | 추정 맥락 |
|---|---|---|
| `src/App.tsx:3236` | `#e5e5e5` | radar 차트 "유동인구" 라벨 fill (다른 6개 라벨은 `#a3a3a3` = `var(--muted-foreground)`로 통일했지만 이 1건만 더 밝게 강조됨). 강민 결정: **"유동인구 라벨도 `var(--muted-foreground)`로 통일?"** 또는 **"`var(--foreground)` 유지로 강조?"** |

## tsc / prettier 결과

**prettier**: 본 영역 작업자는 prettier 실행을 **보류함**. 이유: 동일 App.tsx 1~2400 라인을 다른 subagent (영역 1a) 가 동시 수정 중이었으며, 작업 도중 "File has been modified since read" 에러가 다수 발생할 정도로 race 가 잦았음. prettier 가 전체 파일을 reformat 할 경우 동시 작업자의 미저장 변경과 충돌하거나, 1a/1b 의 변경이 함께 reformat 되어 git diff 가 흐려질 위험. **Phase 3 검증 단계에서 1a + 1b 머지 후 `npx prettier --write src/App.tsx` 일괄 실행 권장.**

**tsc**: 본 영역 작업자는 `npx tsc --noEmit` 실행을 **보류함**. 이유: 1) 단순 hex → 시맨틱 토큰 치환은 className 문자열만 변경 (타입 영향 없음), 2) 다른 subagent 의 진행 중 변경이 일시적으로 컴파일 오류를 일으킬 수 있어 false negative 위험. **Phase 3 통합 검증에서 일괄 실행 권장.**

## 동시 작업 충돌 메모

- 영역 1a (App.tsx 1~2400) 작업자가 매우 빠른 속도로 Edit 적용 중이었음 — 여러 차례 "File has been modified since read" 에러 발생.
- 본 작업자는 **소형 atomic edit + 즉시 재읽기** 패턴으로 우회. 결과적으로 모든 hex 치환은 라인 2401 이후 영역에 한정됨 (영역 1a 충돌 없음 확인).
- 본 작업자가 적용한 모든 치환은 `[#xxx]` 또는 `"#xxx"` 패턴의 unique surrounding context 로 매칭하여 라인 번호 의존성 제거.

## 핵심 변경 highlights

1. **노란 띠 제거 (§8 핵심)**: `App.tsx:3733` 의 `border-amber-400` → `border-primary` 적용 완료. 법률 리스크 통합 카드의 비-critical 항목 좌측 띠가 노란→Deep Blue 로 변경됨.
2. **DashboardOutlet 배경**: `bg-[#0C0B0A]` → `bg-background`. 라이트모드 기본 배경 토큰 사용.
3. **모달 backdrop**: `bg-[#050505]/70` → `bg-black/70` (§1 권장 그대로).
4. **그라디언트 단순화**: RUN SIMULATION 버튼의 `from-[#6366f1] to-[#818cf8]` 그라디언트 → `bg-primary` 단색 (§4 권장).
5. **3D Preloader rings**: 5개 ring 의 모든 `stroke="#xxx"` (`#818cf8`, `#6366f1`, `#a5b4fc`) → `var(--primary)` 통합. 강민 결정 시 ring 별 chart-1/chart-2 분리 가능.
