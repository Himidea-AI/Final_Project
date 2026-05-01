# Phase 4 영역 B2 보고

영역: `frontend/src/components/SimulationResult/dashboard/**` (영역 B 가 누락한 zone)
작업일: 2026-04-30
담당: B2 subagent

## 통계

- 치환 명명-색 인스턴스: **768**
- 영향 파일: **51** (charts 26 + tabs 6 + sub 9 + shared 8 + groups 2 + 직속 2 = HubCard.tsx + DashboardHub.tsx + agents.ts)
- `dark:` prefix 폐기: **0** (영역 내 dark prefix 없음 — 사전 grep 확인)
- unmapped: **0**

## HubCard.tsx 변경 사항 핵심 highlight

13.png 회귀 핵심 자리. 카드 자체 다크 배경 → 라이트 카드 면.

| 변경 |
|------|
| `bg-stone-900/60` → `bg-card/60` (commonCls 양 모드) |
| `border-stone-800/60` → `border-border/60` |
| `bg-stone-900/95` → `bg-card/95` (inner 컨테이너) |
| `text-stone-100` → `text-foreground` (제목) |
| `text-stone-400` → `text-muted-foreground` (설명) |
| `hover:shadow-indigo-500/10` → `hover:shadow-primary/10` |
| `border-rose-500/30` → `border-danger/30` (disabled alert) |
| `bg-rose-500/10` → `bg-danger/10` |
| `text-rose-300` `text-rose-200/80` `text-rose-300/60` → `text-danger` `text-danger/80` `text-danger/60` |
| `focus-visible:ring-warning` → 그대로 (이미 시맨틱) |
| **cyan accent 특수 처리**: `text-cyan-400`/`focus-visible:ring-cyan-400` → `text-chart-2`/`focus-visible:ring-chart-2` (스펙: cyan 자리 의미상 chart-2 매핑, indigo accent 와 시각 분리 유지). laser conic-gradient 는 이미 `var(--chart-2)` 사용 중이라 일치. |

`accent: 'indigo'` → primary 톤, `accent: 'cyan'` → chart-2 톤, `accent: 'amber'` → warning 톤. 3 accent 의미 분리 유지.

## DashboardHub.tsx

11 substitutions. 컨테이너 배경 + 헤더 텍스트 + 보조 문구 라이트화.

## charts/AgentConfidenceRadar.tsx

5 substitutions. 외부 wrapper 다크 박스 (16.png 회귀 자리)는 이미 `var(--primary)` 등 CSS 변수 기반 → 명명 색 5건만 잔여하던 라벨/카운터 텍스트 시맨틱화 (`text-stone-*` → `text-muted-foreground` / `text-primary`).

## 11종 차트 + groups + shared + sub + tabs

전수 처리. 가장 큰 변경:
- `charts/EmergingSignalCard.tsx`: 49 subs
- `tabs/MarketTab.tsx`: 56 subs
- `shared/DecisionCard.tsx`: 42 subs
- `agents.ts`: 39 subs (8 에이전트 borderCls/iconBgCls 모두 시맨틱화 — text-blue-400/text-emerald-400/text-indigo-400/text-amber-400/text-rose-400/text-cyan-400/text-violet-400/text-white → text-primary/text-success/text-primary/text-warning/text-danger/text-primary/text-primary/text-foreground 등. 8 distinct accents → primary/success/warning/danger 4 톤으로 통합되는 점은 라벨 식별성 측면에서 본부 영업팀 뷰의 미니멀 라이트 미감 우선이 결정)

## 매핑 룰 (Phase 4 ★ 적용)

| from | to |
|---|---|
| `stone/zinc/slate/gray/neutral` 모든 prop/shade/opacity | `bg-card`/`bg-muted`/`text-foreground`/`text-muted-foreground`/`border-border`/`ring-border` |
| `indigo/sky/blue` | `*-primary` |
| `rose/red/pink` | `*-danger` |
| `emerald/green` | `*-success` |
| `amber/yellow/orange` | `*-warning` |
| `cyan/teal` | `*-primary` (단 HubCard cyan accent 만 chart-2 수동 처리) |
| `violet/purple/fuchsia` | `*-primary` (관찰: 영역 내 violet 사용은 agents.ts 1자리뿐. fuchsia/purple 사용 0건) |

## prefix 변형

`hover:` `focus:` `focus-visible:` `group-hover:` `peer-checked:` 등 모두 보존하여 시맨틱 토큰에 정확히 적용. `text-rose-300/60` 같은 opacity suffix 도 유지.

## Unmapped (강민 결정 필요)

없음.

## tsc / prettier 결과

- `npx prettier --write src/components/SimulationResult/dashboard/`: **PASS**
- `npx tsc --noEmit`: **PASS** (no errors)

## 검증 grep

```
grep -rE 'bg-stone-9|bg-zinc-9|bg-gray-9' src/components/SimulationResult/dashboard --include='*.tsx' --include='*.ts' (excl. *.test.tsx)
→ 0 hits
```

```
grep -rE '\b(stone|zinc|slate|gray|neutral|indigo|sky|blue|rose|red|pink|emerald|green|amber|yellow|orange|cyan|violet|purple|fuchsia|teal)-[0-9]+' src/components/SimulationResult/dashboard
→ 0 hits
```

명명 색 인스턴스 전수 제거. 768 인스턴스 잔여 → 0.
