# Phase 0 통합 보고서 — 라이트 모드 마이그레이션

> 4개 인벤토리 subagent 산출물 통합 + 강민 게이트 결정 사항.
> Phase 1 (토큰 정의) 시작 전 승인 받기 위함.

## 1. 인벤토리 수치 종합

| 항목 | 수 | 산출물 |
|---|---|---|
| Tailwind hex (`bg-[#…]` 등) | **836** (figma-crm-kit 제외) | `hex-catalog-A.md` |
| 라이브러리 props hex (recharts/SVG/inline) | **146** | `library-hex-D.md` |
| 노란색 사용 (yellow/amber/hex) | **130+** | `yellow-inventory-B.md` |
| 다크모드 토글 인프라 | **0** ✓ | `dark-mode-deps-C.md` |
| **총 변경 대상** | **~1,112 인스턴스** | |

> 처음 추정 493건의 약 2.3배. 토큰 시스템 우회가 광범위.

## 2. 좋은 소식 — 다크 정리 작업 0

- `dark:` Tailwind prefix: 0
- `isDark` state / `SkyThemeToggle` 컴포넌트: 모두 부재
- `tailwind.config.darkMode` 옵션: 없음
- App.tsx 주석 2건만 정리하면 끝

→ Phase 2 작업 범위: **hex → 시맨틱 토큰 단순 치환**만. 분기 정리 없음.

## 3. 확정 결정 (강민 기존 결정 — 재확인용)

### 3.1 페이지 토큰 (라이트)
```
--background  #FAF9F5  warm-white
--foreground  #0A0A0A
--card        #FFFFFF
--muted       #F5F4EE  (sidebar/nav)
--border      #EAE9E1
--primary     #002CD1  Deep Blue
```

### 3.2 데이터 차트 4색 (4동 비교)
```
--chart-1     #002CD1  Deep Blue       (선택 본인 동, primary와 동일)
--chart-2     #FF3800  Vivid Red
--chart-3     #00BA7A  Teal Green
--chart-4     #B35CFF  Vibrant Purple
```

> ⚠ Phase 0-D agent는 "현재 indigo/cyan/amber/rose 유지" 권장했으나 **거부**. 강민 결정이 우선.
> 영향: 9개 차트 컴포넌트의 `COLORS = […]` 배열 전부 교체.

### 3.3 노란 3px 띠 처리
- 인벤토리 결과 stripe 분류는 **단 4건** (생각보다 적음):
  1. `InsightsGrid.tsx:33` `LEVEL_CLS.MEDIUM.strip = 'bg-yellow-500'` (체크리스트 좌측 띠 핵심 1줄)
  2. `InsightsGrid.tsx:192` 안전군 행 좌측
  3. `App.tsx:3733` `border-amber-400`
  4. `MarketMap.tsx:138` 승자 마커 2px (이건 `#ffffff` 흰색 테두리이므로 별도 검토 — 노란 아님)
- → 1, 2, 3 → `bg-primary` (Deep Blue) 로 교체

## 4. 강민 결정 필요 ❓ (게이트 항목)

### Q1. 시나리오 차트 3색
`ScenariosComparisonChart.tsx` 가 현재 사용:
- 낙관: `#10b981` Emerald
- 기본: `#818cf8` Indigo
- 비관: `#fb7185` Rose

**제안 A (의미론적 유지)**: emerald/blue/red 각각 라이트 톤 (`#059669`/`#002CD1`/`#DC2626`)
**제안 B (chart 토큰 통일)**: `--chart-3` Teal Green / `--chart-1` Deep Blue / `--chart-2` Vivid Red

→ **A 추천**. 시나리오는 4동 비교가 아니라 *동일 동의 시나리오 분기*라 의미적 색이 더 직관적.

### Q2. 상태 색 토큰 신규 정의
```
--success   #059669  Emerald 600  (라이트 배경 4.5:1 통과)
--warning   #D97706  Amber 600    (#F59E0B는 컨트라스트 부족)
--danger    #DC2626  Red 600      (다크의 #FF808B 대체)
```
→ 동의 여부?

### Q3. SHAP Waterfall 색 (긍정/부정 기여)
현재: `#22c55e` 양 / `#ef4444` 음. 라이트 톤 `#16A34A` / `#DC2626`로 진하게? 또는 그대로?
→ 진하게 하는 게 라이트 배경에서 안 묻힘. **`#16A34A` / `#DC2626` 추천**.

### Q4. 거리 잠식 gradient (5색)
`CannibalizationDistanceChart`: `#ef4444 → #f59e0b → #eab308 → #84cc16 → #22c55e`
→ 5색 gradient는 의미적 (위험→안전), 그대로 유지가 정석. 대신 라이트 배경 컨트라스트 위해 amber/yellow 단계만 살짝 진하게:
```
#DC2626 → #D97706 → #CA8A04 → #65A30D → #16A34A
```

### Q5. AbmPersonaMap POI 마커 4색
현재: Rose/Amber/Blue/Stone (의미: 주의/지불/카드/기본). 4동 차트 색과 별도이므로 **그대로 유지** OK?

### Q6. PDF 템플릿 (`HiddenPDFTemplate.tsx`)
이미 라이트 배경 (`#ffffff`) 으로 되어 있음. 메인 마이그레이션과 별개로 두고 끝까지 그대로 유지? 아니면 토큰화 시 같이 정리?
→ **그대로 두는 거 추천**. PDF는 인쇄/캡쳐용이라 메인 라이트 토큰과 분리되는 게 안전.

## 5. 영역 분할 재조정 (App.tsx 700+ 대응)

원안: 영역① (페이지/라우팅) 에 App.tsx 통째 — 700개 hit 너무 큼.

**개정**:
| 영역 | 디렉토리 | 예상 hex | 추가 메모 |
|---|---|---|---|
| ①-a App.tsx Part 1 | App.tsx 1~2400줄 | ~350 | 변수 정의 + IntroScene + 헤더 |
| ①-b App.tsx Part 2 | App.tsx 2400~4779줄 | ~350 | SimulatorDashboard + 모달 + DashboardOutlet |
| ② 시뮬레이터 | components/SimulationResult/**, components/simulation/** | ~100 | 차트 색은 토큰 |
| ③ 대시보드 | components/dashboard/**, pages/dashboard/**, dashboard/charts/** | ~80 | 차트 4색 적용 |
| ④ Nav/공용/랜딩 | GlobalNav, BrandLogo, Toast, IntroScene 외, JoinUs/* | ~150 | 노란 띠 4건 동시 처리 |
| ⑤ 차트 라이브러리 | recharts/SVG props 146 | ~146 | 별도 영역 (Tailwind 외) |

→ 6개 subagent 병렬. App.tsx만 둘로 나누되 같은 카탈로그 + 같은 매핑 룰 공유.

## 6. 진행 순서 확정

1. **이 보고서 강민 OK** ← 현재 위치
2. Phase 1: `index.css :root` + 신규 토큰 (`--chart-1..4`, `--success`, `--warning`, `--danger`) 직접 작성, 1 커밋, git diff 확인 게이트
3. Phase 2: 6개 영역 병렬 subagent (각자 본인 디렉토리만, 카탈로그 매핑 강제)
4. Phase 3: 잔여 hex 0건 검증 + tsc + eslint, 강민 dev server 시각 확인

---

**Phase 1 진행 전 결정 6개 (Q1~Q6)** 만 답해주시면 즉시 토큰 정의 들어갑니다.
