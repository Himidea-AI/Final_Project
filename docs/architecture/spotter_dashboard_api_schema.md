# SPOTTER Dashboard API Schema (v1.0)

> **목적:** 프론트엔드 SimulatorDashboard와 백엔드 LangGraph synthesis_node 사이의 API 계약 문서.
> **작성:** C1 강민 (프론트엔드)
> **날짜:** 2026-04-10
> **상태:** 검토 요청 (백엔드/AI팀 회신 대기)

## 0. 컨텍스트

이 문서는 **현재 프론트엔드가 표시하는 모든 데이터 필드**를 정리한 것입니다. 백엔드 `synthesis_node`가 이 형태에 맞춰 응답을 생성하면, 프론트엔드는 mock을 실데이터로 1줄씩만 교체하면 됩니다.

**검토 방식:** 각 필드 옆에 다음 중 하나로 표시해주세요.
- ✅ **가능** — 지금 응답에 있음 또는 쉽게 추가 가능
- 🔄 **개발 필요** — 가능하지만 시간 필요 (예상 일수 적어주세요)
- ❌ **불가능** — UI에서 빼야 함 (이유 적어주세요)
- 🎁 **대안** — 대신 X를 줄 수 있음

---

## 1. 요청 (Request) — `POST /api/simulate`

```ts
interface SimulationInput {
  // === 필수 ===
  business_type: string;          // "한식음식점", "커피-음료" 등 (CS 코드 매핑 예정)
  brand_name: string;             // "스타벅스", "이디야" 등
  target_district: string;        // "연남동", "서교동" 등 행정동명

  // === 분석 조건 ===
  existing_stores: ExistingStore[]; // 기존 매장 리스트 (카니발리제이션 분석용)
  initial_investment: number;       // 초기 투자금 (원)
  monthly_rent: number;             // 월 임대료 (원, 0이면 자동 추정)
  simulation_months: number;        // 시뮬레이션 기간 (기본 12)
  scenarios: string[];              // 시나리오 코드 (기본 ["base"])

  // === Advanced (선택) ===
  business_subtype?: string;        // 업종 소분류 (현재 미사용)
  store_area?: number;              // 점포 면적 (평)
  target_price_range?: string;      // 목표 객단가 ("under5k" | "5to10k" | "10to20k" | "over20k")
  operating_hours?: string[];       // 주 타겟 시간대 (["오전", "점심", "저녁", "심야"])
  initial_capital?: number;         // 초기 자본금 (만원)
  use_weighted_population?: boolean; // 유동인구 가중치 사용 여부
  radius_m?: number;                // 분석 반경 (미터)
}

interface ExistingStore {
  district: string;
  address: string;
  monthly_revenue: number;
}
```

---

## 2. 응답 (Response) — `POST /api/simulate`

전체 응답 구조 (synthesis_node 출력):

```ts
interface SimulationOutput {
  // === 메타데이터 ===
  request_id: string;               // UUID
  target_district: string;          // 입력한 동
  generated_at: string;             // ISO 8601 timestamp
  brand_category: "direct_operation" | "franchise"; // 직영/가맹
  is_direct: boolean;               // 직영 여부 (UI 분기용)

  // === 0. AI 한 줄 평 (킬러 인사이트, 메인 상단 배치) ===
  ai_verdict: AIVerdict;

  // === 1. KPI 4개 카드 ===
  kpi_summary: KPISummary;

  // === 2. 시계열 차트 (24H + 12M) ===
  time_series: TimeSeries;

  // === 3. 7대 핵심 지표 (레이더 차트) ===
  core_metrics: CoreMetrics;

  // === 4. 상세 데이터 테이블 ===
  cannibalization_analysis: CannibalizationItem[];
  neighborhood_comparison: NeighborhoodItem[];

  // === 5. AI 인사이트 카드 (severity별) ===
  insights: AIInsight[];

  // === 6. 상세 분석 리포트 (Markdown) ===
  analysis_report: string;          // synthesis_node가 작성한 Markdown 긴 글
}
```

### 2-1. AI Verdict (메인 상단 한 줄 평) ⭐ 킬러 인사이트

```ts
interface AIVerdict {
  headline: string;                 // 한 줄 (예: "스타벅스 서교동: 강력한 입지 독점력과 2030 타겟팅을 통한 고수익 확보 가능 상권")
  severity: "positive" | "neutral" | "warning" | "critical";
  reason: string;                   // 1-2줄 짧은 근거 (예: "직영 브랜드라 가맹점 출점 불가, 단 BBQ 등 유사 업종 진출 시 89점 예상")
}
```

**프론트 매핑:** `AIVerdictBanner` 컴포넌트 (메인 상단)

**Mock 예시:**
```json
{
  "headline": "스타벅스 서교동: 강력한 입지 독점력과 2030 타겟팅을 통한 고수익 확보 가능 상권",
  "severity": "positive",
  "reason": "직영 브랜드라 가맹점 출점은 불가능하지만, 동일 카테고리 브랜드 진출 시 평균 89점 예상"
}
```

---

### 2-2. KPI Summary (4개 카드)

```ts
interface KPISummary {
  monthly_revenue: {
    value: number;                  // 원 단위 (예: 40500000)
    trend_pct: number;              // 전월 대비 % (예: 12.5)
    trend_direction: "up" | "down";
  };
  attractiveness_score: {
    value: number;                  // 0~100 정수 (예: 87)
    delta_pts: number;              // 전월 대비 점수 변화 (예: 5.2)
    grade: "EXCELLENT" | "GOOD" | "NORMAL" | "RISKY";
  };
  daily_floating_pop: {
    value: number;                  // 명 단위 (예: 42105)
    trend_pct: number;              // 전월 대비 %
    trend_direction: "up" | "down";
  };
  cannibalization_risk: {
    level: "LOW" | "MEDIUM" | "HIGH";
    impact_pct: number;             // 매출 영향률 % (예: 12)
    label: string;                  // "안전 권역", "위험 권역" 등
  };
}
```

**프론트 매핑:** `StatCard` × 4

---

### 2-3. Time Series (시계열 차트)

```ts
interface TimeSeries {
  hourly_24h: {                     // 시간대별 24시간 데이터
    floating_population: number[]; // 24개 (시간당, 0~23시)
    revenue: number[];             // 24개 (원)
    competitor_avg_population: number[]; // 24개 (경쟁점 평균, 비교용)
  };
  monthly_12m: {                    // 12개월 매출 추이 (LSTM 예측)
    revenue: number[];             // 12개 (원, 1월~12월)
    cumulative_profit: number[];   // 12개 (누적 순이익, 원)
    confidence_lower: number[];    // 신뢰구간 하한 (선택)
    confidence_upper: number[];    // 신뢰구간 상한 (선택)
  };
}
```

**프론트 매핑:** Chart 영역 (24H/12M 토글)

---

### 2-4. Core Metrics (7대 핵심 지표 — 레이더 차트)

```ts
interface CoreMetrics {
  // 모두 0~100 정규화 (Min-Max Scaling)
  floating_population: MetricItem;
  sales_volume: MetricItem;
  growth_potential: MetricItem;
  survival_rate: MetricItem;
  rent_burden: MetricItem;          // 낮을수록 좋음
  competition_intensity: MetricItem; // 낮을수록 좋음
  accessibility: MetricItem;
}

interface MetricItem {
  score: number;                    // 0~100 정수
  rank_in_district: number;         // 마포구 내 순위 (예: 25개 동 중 3위)
  trend: "rising" | "stable" | "declining";
  reason: string;                   // 1-2줄 짧은 근거 ⭐ AI 설명가능성
}
```

**프론트 매핑:** Radar Chart (7-axis) + Drill-down Drawer (각 axis 클릭 시 reason 표시)

**Mock 예시:**
```json
{
  "floating_population": {
    "score": 82,
    "rank_in_district": 3,
    "trend": "rising",
    "reason": "유동인구 점수가 높은 이유는 20대 여성의 주말 방문 비중이 인근 대비 15% 높기 때문"
  }
}
```

---

### 2-5. Cannibalization Analysis (가맹점 간섭도 테이블)

```ts
interface CannibalizationItem {
  store_name: string;               // "연남파크점"
  distance_m: number;               // 미터 단위 (예: 450)
  revenue_impact_pct: number;       // 매출 영향률 % (음수, 예: -2.1)
  status: "Safe" | "Warning" | "None";

  // === Expandable Row 상세 (선택) ===
  detail?: {
    venn_overlap: { circle1_radius: number; circle2_radius: number; overlap: number }; // 미니맵 데이터
    hourly_impact: {                // 시간대별 영향도
      morning: number;              // 오전 (06-11)
      lunch: number;                // 점심 (11-14)
      evening: number;              // 저녁 (17-21)
      night: number;                // 심야 (21-02)
    };
    counterfactual: {               // "이 매장이 없었다면"
      revenue_increase_pct: number; // 매출 증가율 % (예: 18.4)
    };
  };
}
```

**프론트 매핑:** 가맹점 간섭도 테이블 + Expandable Row (Venn 미니맵 + 시간대별 + Counterfactual)

---

### 2-6. Neighborhood Comparison (행정동 비교 테이블)

```ts
interface NeighborhoodItem {
  district_name: string;            // "연남동", "서교동" 등
  ai_score: number;                 // 0~100
  survival_rate_pct: number;        // 생존율 % (예: 82)
  estimated_bep_months: number;     // 예상 BEP (개월, 예: 3.5)
}
```

**프론트 매핑:** 행정동 비교 테이블

---

### 2-7. AI Insights (인사이트 카드 — severity별)

```ts
interface AIInsight {
  agent_node: "market_analyst" | "population_analyst" | "legal_analyst" | "financial_insight";
  severity: "critical" | "advisory" | "opportunity";
  title: string;                    // 카드 제목
  desc: string;                     // 1-2줄 설명
  reasoning?: string;               // Drill-down Drawer 펼침 시 표시할 긴 설명 (선택)
  recommended_action?: string;      // 추천 액션 (선택)
}
```

**프론트 매핑:** `InsightCard` × 3 (severity별 색상: rose/indigo/emerald)

**Mock 예시:**
```json
{
  "agent_node": "legal_analyst",
  "severity": "critical",
  "title": "법률 리스크 경고 (Legal Node)",
  "desc": "상가임대차보호법 위반 사례 존재 권역. 최근 3년 평균 임대료 인상률이 5%를 초과.",
  "reasoning": "Legal Node가 14개 영역 3,775개 판례·법령 청크에서 유사 사례 검색...",
  "recommended_action": "계약 갱신 청구권 행사 시 전문 법무팀 상담 권장"
}
```

---

### 2-8. Analysis Report (Markdown 긴 글)

```ts
analysis_report: string;            // synthesis_node가 작성한 Markdown
```

**프론트 매핑:** Markdown 뷰어 (`react-markdown` 사용, Drill-down Drawer 또는 별도 모달)

**예상 길이:** 500~2000자 (헤딩 + 표 + 리스트 포함)

---

## 3. UI 컴포넌트 ↔ API 필드 매핑

| UI 컴포넌트 | 사용하는 필드 | 우선순위 |
|---|---|---|
| `AIVerdictBanner` (신규) | `ai_verdict.headline`, `severity`, `reason` | ⭐⭐⭐ |
| `StatCard × 4` | `kpi_summary.*` | ⭐⭐⭐ |
| `Chart (24H 토글)` | `time_series.hourly_24h.*` | ⭐⭐ |
| `Chart (12M 토글)` | `time_series.monthly_12m.*` | ⭐⭐⭐ |
| `Radar Chart` | `core_metrics.*.score` | ⭐⭐⭐ |
| `Cannibalization Table` | `cannibalization_analysis[]` | ⭐⭐⭐ |
| `Cannibalization Expand Row` | `cannibalization_analysis[].detail` | ⭐⭐ |
| `Neighborhood Table` | `neighborhood_comparison[]` | ⭐⭐ |
| `InsightCard × 3` | `insights[]` (severity별) | ⭐⭐⭐ |
| `Drill-down Drawer (KPI 클릭)` | `core_metrics.*.reason`, `insights[].reasoning` | ⭐⭐ |
| `DirectOperationBanner` | `is_direct`, `brand_category` | ⭐⭐⭐ |
| `Markdown ReportViewer` (신규) | `analysis_report` | ⭐⭐ |
| `PDF Export` | 위 모든 필드 + `request_id`, `generated_at` | ⭐ |
| `Excel Export` | 위 모든 필드 (시트별 분리) | ⭐ |

---

## 4. 직영점 분기 (`is_direct === true`)

직영 브랜드(스타벅스 등)일 때 일부 필드는 다른 의미를 가집니다:

```ts
// 직영점일 때
{
  "is_direct": true,
  "brand_category": "direct_operation",
  "ai_verdict": {
    "headline": "...직영 브랜드 특화 분석...",
    "severity": "neutral",
    "reason": "이 브랜드는 직영점 위주로 운영되어 가맹점 출점이 불가능합니다."
  },
  // cannibalization은 자기 자신과의 거리 분석으로 해석
  // 일부 가맹 관련 필드는 null 가능
}
```

**프론트 처리:** `DirectOperationBanner` 컴포넌트로 "본사 직접 관리 브랜드 특화 분석 모드" 안내

---

## 5. 응답 시간 SLA

| 환경 | 목표 | 현재 (봉환 fix 적용 후) |
|---|---|---|
| 단순 시뮬레이션 | < 30초 | 8~12초 (legal_node 병렬화) |
| 상세 분석 (모든 노드) | < 90초 | 미측정 |

**프론트 측:** `progress bar`가 가상으로 90%까지 천천히 차오르도록 구현 예정 (실제 polling은 추후)

---

## 6. 에러 응답

```ts
// 200 OK 정상 응답: SimulationOutput 그대로
// 4xx/5xx 에러:
{
  "status": "error",
  "error_code": "DATA_NOT_FOUND" | "AGENT_TIMEOUT" | "LLM_API_FAIL" | "INTERNAL",
  "message": "사용자 친화적 에러 메시지",
  "details"?: { ... }              // 디버깅용 (개발 환경만)
}
```

**프론트 처리:** catch block에서 fallback Mock으로 결과 화면 표시 + 에러 토스트

---

## 7. 데이터 출처 표시 (Attribution)

UI 풋터에 표시할 데이터 출처. 백엔드 응답에 `data_sources` 배열 포함 권장:

```ts
data_sources?: Array<{
  name: string;       // "서울시 상권분석서비스 (2018~2024)"
  url?: string;
  last_updated?: string;
}>;
```

**프론트 매핑:** PDF 푸터 + 결과 화면 하단 작게 표시

---

## 8. 검토 요청 — 백엔드/AI팀 액션 항목

각 섹션별로 한 가지씩만 표시 부탁드립니다:

### Section 2-1: AI Verdict
- [ ] ✅ 가능
- [ ] 🔄 개발 필요 (예상 ___일)
- [ ] ❌ 불가능
- [ ] 🎁 대안: ___

### Section 2-2: KPI Summary
- [ ] ✅ 가능 / [ ] 🔄 개발 / [ ] ❌ 불가능 / [ ] 🎁 대안

### Section 2-3: Time Series
- [ ] hourly_24h: ✅ / 🔄 / ❌ / 🎁
- [ ] monthly_12m: ✅ / 🔄 / ❌ / 🎁

### Section 2-4: Core Metrics
- [ ] 7개 지표 0~100 정규화: ✅ / 🔄 / ❌ / 🎁
- [ ] 각 지표별 reason 1-2줄: ✅ / 🔄 / ❌ / 🎁
- [ ] rank_in_district: ✅ / 🔄 / ❌ / 🎁

### Section 2-5: Cannibalization
- [ ] 기본 4 필드: ✅ / 🔄 / ❌ / 🎁
- [ ] detail.venn_overlap: ✅ / 🔄 / ❌ / 🎁
- [ ] detail.hourly_impact: ✅ / 🔄 / ❌ / 🎁
- [ ] detail.counterfactual: ✅ / 🔄 / ❌ / 🎁

### Section 2-6: Neighborhood Comparison
- [ ] ✅ / 🔄 / ❌ / 🎁

### Section 2-7: AI Insights
- [ ] severity 분류: ✅ / 🔄 / ❌ / 🎁
- [ ] reasoning 긴 글: ✅ / 🔄 / ❌ / 🎁
- [ ] recommended_action: ✅ / 🔄 / ❌ / 🎁

### Section 2-8: Analysis Report (Markdown)
- [ ] ✅ / 🔄 / ❌ / 🎁

### Section 4: 직영점 분기 (is_direct)
- [ ] ✅ / 🔄 / ❌ / 🎁

### Section 5: SLA 약속
- [ ] 30초 이내 보장 가능?: ___
- [ ] 90초 이내 보장 가능?: ___

### Section 7: 데이터 출처 attribution
- [ ] ✅ / 🔄 / ❌ / 🎁

---

## 9. 변경 이력

| 버전 | 날짜 | 작성/수정 | 내용 |
|---|---|---|---|
| v1.0 | 2026-04-10 | C1 강민 | 최초 작성 — 현재 SimulatorDashboard 기준 |

---

## 10. 의문점 / TODO

- [ ] 봉환 답변 ("synthesis_node에서 100% 맞춰서 가공 가능") 재확인 — 이 문서가 진짜 명세서
- [ ] 찬영 (DB 커버리지) 답변 대기 중
- [ ] 예진 추가 의견 (혼자 합의는 위험)
- [ ] 12개월 monthly_projection 실제 LSTM 예측 가능한지 (찬영 v8 모델 결합)
- [ ] 직영점 케이스 실제 응답 샘플 1개 확보 필요 (스타벅스 등)
- [ ] 응답 캐싱 정책 (Redis) — 같은 조건 반복 호출 시
