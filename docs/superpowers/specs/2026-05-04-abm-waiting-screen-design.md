# ABM 대기화면 정보 보강 — Spot Info + Persona Preview Stream

**Date**: 2026-05-04
**Branch**: `IM3-competitor-place-url`
**Author**: 찬영 (A1)

## 문제

ABM 페르소나 시뮬에서 사용자가 지도에서 공실 spot 클릭하고 ABM 모드 진입하면, 우측 패널에 시나리오 form (날씨/요일/임대료) 만 보임. "시뮬레이션 실행" 누른 후 ~3분 대기 동안에는 `AbmProgressPanel` (7-stage pipeline + progress bar) 만 보임. 둘 다 spot 자체 정보, 시뮬 의미 부여 정보 부족.

## 목표

대기 시간 두 단계에 정보 표시 추가:

- **Phase 1 (시뮬 실행 전)**: 선택 spot 의 컨텍스트 정보 (`SpotInfoCard`)
- **Phase 2 (시뮬 진행 중)**: 카테고리별 페르소나 샘플 대화 rotate (`PersonaPreviewStream`)

backend 변경 0개. 모든 데이터 기존 props / 기존 endpoint 에서 조달.

## 비목표

- 진짜 partial result streaming (backend ABM 노드 단계별 snapshot 캐시 — 본 sprint 범위 외, 옵션 B-1 으로 명시 후 폐기)
- 신규 backend endpoint
- spot 사진 / 카카오 로드뷰 iframe (옵션 f 폐기)

## 설계

### 1. 컴포넌트 구조

```
AbmPersonaMap.tsx 우측 패널 분기 (line ~3393):
  abmResult ? <결과>
  : abmLoading ? <AbmProgressPanel>
                 + <PersonaPreviewStream>      ← 신규
  : abmError ? <에러>
  : <SpotInfoCard>                              ← 신규
    + <시나리오 form>                           ← 기존 (collapse 처리)
```

### 2. 신규 파일

| 파일 | 역할 |
|------|------|
| `frontend/src/components/abm/SpotInfoCard.tsx` | Phase 1 spot 정보 카드 |
| `frontend/src/components/abm/PersonaPreviewStream.tsx` | Phase 2 샘플 대화 rotate |
| `frontend/src/data/personaSampleDialogs.ts` | 카테고리별 샘플 대화 pool |

### 3. SpotInfoCard 상세

**Props**:
```ts
interface Props {
  focusSpot: { lat: number; lon: number; label?: string };
  storeNodes: StoreNode[];           // AbmPersonaMap 내부 fetch 결과 (지하철 포함)
  vacancySpots?: AgentVacancySpot[]; // listing_count 매칭용
  competitors?: Array<{ lat; lng?; lon?; name?; place_name?; distance_m?; category? }>;
  businessType?: string;             // 'cafe' / 'restaurant' / '음식점' …
  dongStats?: {                       // simResult 에서 추출 (AbmPersonaMap props 추가)
    resident_pop?: number;
    floating_pop?: number;
    closure_rate?: number;
  };
}
```

**섹션 (위 → 아래)**:

1. **Header** — focusSpot.label + dong 명, "선택 SPOT" 배지
2. **주소** (a) — Kakao Local SDK `services.Geocoder().coord2Address(lon, lat)` 비동기 fetch. 실패 시 `좌표: lat, lon` fallback.
3. **가장 가까운 지하철** (b) — storeNodes 중 `tier === 'S'` 항목들에서 focusSpot 기준 haversine 최단 + 거리 m 표시. storeNodes 비면 "—".
4. **listing_count** (c) — vacancySpots 에서 focusSpot 좌표 ±0.0001 매칭. 매물 N개. 없으면 표시 안함.
5. **동 통계** (d) — dongStats 의 resident_pop / floating_pop / closure_rate 3개 metric 한 줄씩. null 값은 row skip.
6. **주변 경쟁업체** (e) — competitors 중 focusSpot 기준 haversine ≤ 500m 인 것만. distance 오름차순 top 5. 카드 list (이름, 카테고리, 거리). 0개면 "주변 500m 내 경쟁업체 없음".
7. **Brand Fit 한 줄** (g) — competitors 카테고리 분포 + businessType heuristic:
   - businessType 과 같은 카테고리 비율 ≥ 30% → "포화 우려 — 차별화 필수"
   - 10~30% → "균형 — 표준 진입 가능"
   - < 10% → "신규 진입 기회 — 대체 수요 검증 필요"
   - 없음(null businessType) → 표시 안함

**스타일**: 기존 `box-glass` 패턴, `SectionLabel` 재사용, 텍스트 사이즈는 시나리오 form 과 동일 (`text-[11px]` ~ `text-xs`).

**collapse 동작**: 시나리오 form 은 SpotInfoCard 아래에 `<details open>` 으로 래핑. 사용자가 spot info 더 보고 싶으면 form 접을 수 있음. default expand.

### 4. PersonaPreviewStream 상세

**Props**:
```ts
interface Props {
  businessType?: string;        // 카테고리 매칭 (cafe/restaurant/etc)
  spotLabel?: string;           // 표시용
}
```

**내부 로직**:
- `personaSampleDialogs.ts` 에서 businessType 매칭 카테고리 pool 로드 (없으면 default pool)
- pool 구조: `{ category: string, dialogs: Array<{ persona: string; tier: 'S'|'A'|'B'; text: string }> }[]`
- 6초 interval 로 dialog 1개 add (cumulative, 최근 4개 유지)
- pool 길이 < 추가 횟수 면 shuffle 재순환
- progress 진행 단계 (`useAbmStore` 의 stage) 표시 prefix — "[탐색 중]" "[추론 중]" 등
- abmLoading=true 일 때만 마운트

**UI**:
```
┌─ AI 페르소나 추론 라이브 ─────────────┐
│ [방금] [탐색 중] 30대 직장인 박씨 (S) │
│   "여기 점심 먹을 만하네. 가격도..."  │
│ [12s 전] [추론 중] 20대 학생 김씨 (A)│
│   "친구랑 카페로 들리기 좋음."         │
│ ...                                    │
│ ⓘ 샘플 페르소나 — 실제 시뮬 결과는    │
│   완료 후 표시됩니다.                  │
└────────────────────────────────────────┘
```

**fade animation**: 새 메시지는 opacity 0 → 1 + translateY(-4px) → 0 transition. 위로 밀려나는 메시지는 opacity 단계 감소.

**경고 명시**: 카드 하단 "샘플 페르소나" 표기 (사용자 오인 방지).

### 5. personaSampleDialogs 데이터 구조

```ts
export interface PersonaDialog {
  persona: string;       // "30대 직장인 박씨"
  tier: 'S' | 'A' | 'B';
  text: string;          // 1~2 문장 한국어
}

export interface CategoryPool {
  category: string;      // 'cafe' | 'restaurant' | 'pub' | 'convenience' | 'default'
  dialogs: PersonaDialog[];
}

export const SAMPLE_DIALOGS: CategoryPool[] = [
  { category: 'cafe', dialogs: [
    { persona: '20대 학생 김씨', tier: 'A', text: '카페인 충전 필요. 콘센트 있고 wifi 빠르면 OK.' },
    { persona: '30대 직장인 박씨', tier: 'S', text: '점심 후 동료랑 잠깐 — 회의실 분위기 카페면 더 좋음.' },
    // … 8개씩
  ]},
  { category: 'restaurant', dialogs: [...] },
  { category: 'pub', dialogs: [...] },
  { category: 'convenience', dialogs: [...] },
  { category: 'default', dialogs: [...] },
];
```

각 카테고리 8개 이상 (6초 × 8 = 48초 unique → 3분 동안 4 cycle, 충분히 다양해 보임).

### 6. AbmPersonaMap 변경

- props 에 `dongStats?: { resident_pop?: number; floating_pop?: number; closure_rate?: number }` 추가
- 우측 패널 분기 두 곳 수정:
  - `abmLoading ? <AbmProgressPanel />` → `abmLoading ? <><AbmProgressPanel /><PersonaPreviewStream businessType={businessType} spotLabel={focusSpot?.label} /></>`
  - `else <시나리오 form>` → `else <><SpotInfoCard focusSpot={focusSpot} storeNodes={storeNodes} vacancySpots={vacancySpots} competitors={competitors} businessType={businessType} dongStats={dongStats} /><details open><summary>시나리오 설정</summary><시나리오 form/></details></>`
- props 에 `businessType?: string` 추가 (없으면 useEffect skip)

### 7. AbmTab 변경

- `<AbmPersonaMap>` 에 prop 두 개 추가:
  - `businessType={businessType}`
  - `dongStats={{ resident_pop: r?.demographic_report?.area_resident_count, floating_pop: r?.market_report?.floating_population, closure_rate: r?.closure_rate?.recent_value }}` (필드명 실제 schema 에 맞춰 추출)

### 8. 에러 / 폴백

| 상황 | 동작 |
|------|------|
| Kakao Geocoder 실패 | 좌표 fallback 표시 |
| storeNodes 비어있음 | 지하철 row 숨김 |
| competitors 비어있음 | "주변 500m 내 경쟁업체 없음" |
| businessType null | brand fit row + persona category default pool |
| dongStats 모두 null | 동 통계 섹션 자체 숨김 |

### 9. 테스트

- `SpotInfoCard.test.tsx` — props 변형으로 각 row 표시/숨김 검증 (Vitest + RTL)
- `PersonaPreviewStream.test.tsx` — interval mock 으로 6초 후 새 dialog add 검증
- `personaSampleDialogs.test.ts` — 각 카테고리 ≥ 8개, persona/text non-empty

### 10. 작업량

| 단계 | 시간 |
|------|------|
| SpotInfoCard 구현 + 테스트 | 3h |
| PersonaPreviewStream + dialog pool | 2h |
| AbmPersonaMap / AbmTab 배선 | 1h |
| QA + prettier | 0.5h |
| **합계** | **~6.5h (1 일)** |

## 결정 기록

- **B-2 연출 streaming 채택** (B-1 진짜 streaming 폐기) — backend ABM 비동기 task 의 partial snapshot 저장 인프라 미존재, 본 sprint 범위 초과.
- **로드뷰 (f) 폐기** — Kakao Roadview iframe 은 페이지 무거워지고 spot 좌표가 도로 위 아닐 시 빈 화면. ROI 낮음.
- **시나리오 form collapse 채택** — spot info 가 메인 내용이 되어야 하지만 form 은 시뮬 실행에 필수 → `<details open>` 로 양립.
