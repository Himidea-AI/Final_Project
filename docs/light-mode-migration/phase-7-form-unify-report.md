# Phase 7 — 시뮬레이션 옵션 화면 통일 (Form Unify)

작성일: 2026-04-30
작업자: 강민 (Frontend Lead)
브랜치: `feature/analyze-llm-migration`

## 배경

옵션 화면 3 issue:
1. 느낌표(Info) 아이콘 크기/색/툴팁 모양이 자리마다 달랐음
2. 유동인구 가중치 토글이 OFF 상태에서 잘 안 보였음 (트랙/thumb contrast 부족)
3. 옵션 형태가 제각각 — 박스/내장/wrap-less 혼재

4개 신규 컴포넌트(`FormField`, `ChipGroup`, `Toggle`, `InfoTooltip`)로 일괄 교체.

## 변경 파일

- `frontend/src/App.tsx` (라인 ~1530~2010)
- `frontend/src/components/ui/FormField.tsx` (icon prop 타입 → `LucideIcon`)

## FormField 적용 자리 (10개)

1. 분석 대상 — `icon={MapPin}`
2. 업종 — `icon={Store}`
3. 유동인구 가중치 — `info="ON: KT 통신 유동인구 데이터를 매출 예측에 반영. 카페/음식점은 ON 권장"`
4. 목표 객단가 — `hint="단일 선택"`
5. 주 타겟 시간대 — `hint="복수 선택"`
6. 연령대 — `hint="복수 선택"`
7. 성별 — `hint="단일 선택"`
8. 방문 시간대 — `hint="복수 선택"`
9. 요일 — `hint="단일 선택"`
10. 예상 월매출 — `hint="선택 사항"`

## ChipGroup 적용 자리 (6개)

| 자리 | 모드 | cols | 옵션 수 |
|------|------|------|--------|
| 목표 객단가 | single (string) | 2 | 4 (PRICE_RANGES) |
| 주 타겟 시간대 | multi (string) | 4 | 4 (OPERATING_HOURS_OPTIONS) |
| 연령대 | multi (string) | 3 | 6 |
| 성별 | single (string \| null) | 3 | 3 |
| 방문 시간대 | multi (string) | 3 | 6 |
| 요일 | single (string \| null) | 3 | 3 |

타입 충돌 없음 — PRICE_RANGES.value 가 처음부터 string ('under5k' 등). `as const` 로 단일/null 옵션 처리.

## Toggle 적용 자리 (1개)

유동인구 가중치 — 기존 hand-rolled 트랙/thumb 제거, OFF 상태에서도 트랙(`bg-muted border-border`) + thumb(`bg-card shadow-sm`) 명확.

## InfoTooltip 자동 적용 (1개)

유동인구 가중치 `info` prop → 14px Lucide Info 아이콘 + dark callout (`bg-foreground text-card`). 기존 `<span title="...">` 브라우저 기본 툴팁 제거.

## 보존된 자리 (변경 없음)

- HybridSliderInput 4개: 상권 반경 / 임대료 예산 / 매장 면적 / 초기 자본금 (자체 라벨+슬라이더+infoText 내장, 일관성 이미 OK)
- 동 선택 드롭다운 button + 메뉴 패턴 (FormField 안에서 padding/height 정렬만, h-10 통일)
- 업종 선택 드롭다운 button + 메뉴 (h-10 통일)
- SectionLabel (Core / Operating / Target 섹션 헤더)
- "분석 대상" / "업종" 박스의 외곽 강조 스타일 (`bg-card border border-primary/20 rounded-2xl shadow-xl shadow-primary/5`)
- 시뮬레이션 logic (state, handlers) — 모두 그대로

## 부가 정리

- `accentBg = 'bg-primary'` 변수 — 기존 hand-rolled 토글에서만 사용되었고 Toggle 컴포넌트로 대체되며 dead → 제거.
- 입력 필드 height 정합: native button/input 들 `py-2.5` → `h-10` 통일 (ChipGroup 의 h-9 + 시각 격차 줄임).

## 검증

- `npx prettier --write src/App.tsx src/components/ui/FormField.tsx` — PASS (unchanged 후 idempotent)
- `npx tsc --noEmit` — PASS (no errors)

## Import 추가 (App.tsx 상단)

```tsx
import { FormField } from './components/ui/FormField';
import { ChipGroup } from './components/ui/ChipGroup';
import { Toggle } from './components/ui/Toggle';
```

`InfoTooltip` 은 FormField 내부에서 자동 사용되므로 직접 import 불필요.

## FormField 컴포넌트 미세 수정

`icon?: ComponentType<{size?: number; className?: string}>` → `icon?: LucideIcon` 로 교체.
이유: Lucide 아이콘은 `ForwardRefExoticComponent<LucideProps>` 라서 좁은 ComponentType 시그니처에 할당 시 propTypes mismatch 로 TS 에러. SectionLabel.tsx 와 동일 패턴 통일.
