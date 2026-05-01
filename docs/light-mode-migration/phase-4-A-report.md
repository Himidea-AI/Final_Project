# Phase 4 영역 A 보고 — App.tsx 명명 컬러 클래스 치환

## 통계

- 영향 파일: 1 (`frontend/src/App.tsx`)
- 치환 인스턴스: 약 102건 (편집 횟수 기준)
  - 색 토큰 라인 매칭 95건 + `text-white` / `hover:text-white` 19건 처리
- dark: prefix 폐기: 0 (App.tsx 내 `dark:` 미발견)
- unmapped (보고): 0 — 모든 발견 패턴이 룰표로 결정 가능

## 매핑 분포 (대표 케이스)

| 원본 패턴 | 대상 토큰 |
|---|---|
| `text-indigo-400` (15건) | `text-primary` |
| `text-rose-300/400/500/200` (총 14건) | `text-danger` |
| `text-emerald-200/300/400/500` (총 14건) | `text-success` |
| `text-amber-200/300/400/500` (총 14건) | `text-warning` |
| `text-stone-100/300/500/600` (5건) | `text-foreground` 또는 `text-muted-foreground` (룰 따름) |
| `text-slate-300/400/500` (7건) | `text-muted-foreground` |
| `bg-rose-*` `bg-emerald-*` `bg-amber-*` (모든 alpha 변형) | `bg-danger`/`bg-success`/`bg-warning` (alpha 보존) |
| `border-rose-500/30`, `border-amber-500/40` 등 | `border-danger/30`, `border-warning/40` |
| `bg-indigo-500/10..30`, `border-indigo-500*` | `bg-primary/*`, `border-primary*` |
| `hover:bg-indigo-500/10`, `hover:border-indigo-500` | `hover:bg-primary/10`, `hover:border-primary` |
| `text-cyan-400` / `hover:text-cyan-300` (line 2363, 단일 UI 액센트) | `text-primary` / `hover:text-primary/80` |
| `bg-cyan-400` / `text-cyan-300/400` (TCN SHAP 시각화) | `bg-chart-2` / `text-chart-2` (LightGBM=primary 와 색 분리 위해 chart-2 적용 — §12·6 차트 자리) |
| 4-panel `panelColors` (`text-amber/emerald/sky/rose-500`) | `text-chart-1..chart-4` (§6 따름) |
| `bg-amber-500 text-black border-amber-500` (Split toggle active) | `bg-warning text-warning-foreground border-warning` |
| `text-white`(11건) / `hover:text-white`(8건) | `text-foreground` / `hover:text-foreground` (단, 4118 `bg-primary text-white` → `text-primary-foreground`) |
| Fallback `bg-slate-500/20 text-slate-300 border-slate-500/40` | `bg-muted text-muted-foreground border-border` |

## Unmapped (강민 결정 필요)

없음. cyan/violet/purple/fuchsia 발견 케이스도 모두 §"Cyan / Teal" 케이스 룰("강조 액센트→primary" or "차트 자리→chart-N")로 결정 가능했음.

특기 사항:
- TCN 폐업 시그널 시각화에서 LightGBM=primary 와 시각 분리를 유지하기 위해 cyan을 `chart-2`로 매핑. 의미상 "TCN(시계열) 모델 기여" 표시이므로 차트 색 영역에 해당.
- `details summary`(line 2363) 의 cyan 은 단일 expand 링크 액센트 → `text-primary`로 통합.

## tsc / prettier 결과

- `npx prettier --write src/App.tsx`: PASS (345ms)
- `npx tsc --noEmit`: PASS (오류 없음)
