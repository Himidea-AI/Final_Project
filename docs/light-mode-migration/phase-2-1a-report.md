# Phase 2 영역 1a 보고 — App.tsx (lines 1~2400)

## 통계
- 치환 hex 인스턴스: **202** (Tailwind 임의값 `[#xxxxxx]` 형태 기준 — `git diff` 의 `-` 라인에서 추출)
- 영향 파일: **1** (`frontend/src/App.tsx`)
- `dark:` prefix 폐기: **0** (1~2400 범위 내 `dark:` 미발견)
- unmapped (보고): **1** (아래 표 참조 — `#ffffff` 는 Rule 14 의 "단순 흰색 유지 OK" 기준으로 의도적 보존)

## 파일별 변경 요약
- `src/App.tsx` (lines 1~2400): 202 건

## 주요 치환 패턴
| from (hex) | to (시맨틱 토큰) | 룰 |
|---|---|---|
| `bg-[#1e1b18]`, `bg-[#1a1816]` | `bg-card` | §1 |
| `bg-[#2c2825]` | `bg-card` | §1 |
| `bg-[#3a3633]` (배경 변형) | `bg-muted` | §1 (catalog A 보조) |
| `border-[#3a3633]` | `border-border` | §3 |
| `text-[#e2e8f0]` | `text-foreground` | §2 |
| `text-[#9ca3af]`, `text-[#6b7280]`, `text-[#d1d5db]`, `text-[#666666]` | `text-muted-foreground` | §2 |
| `text-[#818cf8]`, `bg-[#818cf8]`, `border-[#818cf8]` | `text/bg/border-primary` | §4 |
| `border-indigo-500/20`, `shadow-indigo-500/5` (hex 동반 컨텍스트) | `border-primary/20`, `shadow-primary/5` | §4 (indigo→primary 통합) |

## 변환 변수 (§1500 부근)
```ts
// before
const textPrimary = 'text-[#e2e8f0]';
const textSecondary = 'text-[#9ca3af]';
const accent = 'text-[#818cf8]';
const accentBg = 'bg-[#818cf8]';
const panel = 'bg-[#2c2825] border-[#3a3633] shadow-2xl';

// after
const textPrimary = 'text-foreground';
const textSecondary = 'text-muted-foreground';
const accent = 'text-primary';
const accentBg = 'bg-primary';
const panel = 'bg-card border-border shadow-2xl';
```

## Unmapped (강민 결정 필요)
| file:line | hex | 추정 맥락 |
|---|---|---|
| `src/App.tsx:1146` | `#ffffff` | `html2canvas({ ..., backgroundColor: '#ffffff' })` — PDF 캔버스 배경. UI 토큰이 아니라 라이브러리 인자. Rule 14 "단순 흰색 borderColor 등은 유지 OK" 에 준하여 보존. 시맨틱 토큰화하려면 CSS var 해석이 필요해 html2canvas 호환성 검증 필요 → 명시 결정 대기. |

## 범위 외 (다른 subagent 영역 — 변경 없음)
- 라인 2401~ (현 4905줄까지): SVG `stroke=`/`fill=` hex (radar/SHAP/스파크라인), Recharts XAxis/YAxis tick fill, 하단 차트 색상 등 모두 미접촉.

## tsc / prettier 결과
- `npx prettier --write src/App.tsx` → **PASS** (`src/App.tsx 264ms`, 11줄 wrap 발생, 4894→4905)
- `npx tsc --noEmit` → **PASS** (exit 0, 에러 없음)

## 비고
- conversion-rules.md 표 기반 **임의 추측 0건**.
- 변환 후 `git diff`: -133 / +144 라인 (prettier 재포매팅 영향 포함).
- `bg-[#1e1b18]/40` `bg-[#1e1b18]/50` 등 opacity 변형은 `bg-card/40` `bg-card/50` 로 보존.
- Tailwind 명명 색 (`emerald-400`, `indigo-400`, `text-cyan-*` 등) 은 hex 가 아니므로 본 task 범위 밖. 동일 클래스 내 hex 만 치환하고 명명 색은 그대로 유지.
