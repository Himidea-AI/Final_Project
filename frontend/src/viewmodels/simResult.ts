/**
 * SimResult ViewModel — 레거시 대시보드(snake_case → camelCase) 어댑터.
 *
 * Zustand store.result(SimulationOutput, snake_case)는 IntegratedReport / TabbedDashboard 같은
 * 신규 화면이 직접 소비. 그런데 App.tsx의 레거시 SimulatorDashboard 본체는 여전히
 * camelCase 뷰모델(SimResult)을 기대하므로 여기서 변환만 담당.
 *
 * 신규 컴포넌트는 SimulationOutput을 직접 받도록 작성 — 이 어댑터에 새 필드 추가하지 말 것.
 *
 * [규칙 R1] 순수 함수. 마운트 시 rehydrate / runSim 성공 양쪽에서 재사용.
 * mock fallback에는 호출 금지(스키마 불일치).
 *
 * 2026-04-27: market_report·comparison 폴백을 None으로 전환하면서 chartData·marketReport·
 *   comparison 필드 nullable로 동기화 (api-contract-frontend-input.md §3.7).
 */

import type {
  ClosureRisk,
  DemographicReport,
  QuarterlyProjection,
  ShapResult,
  SimulationOutput,
  TrendForecast,
} from '../types';

export interface SimResult {
  score: number;
  revenue: number | null;
  netProfit?: number | null;
  riskLevel: string;
  recommendation: string;
  chartData: { label: string; value: number | null }[];
  // 분기별 매출 예측 데이터 (TCN 모델 출력) — B2 수지니 연동
  quarterlyProjection: QuarterlyProjection[];
  // TCN SHAP 피처 기여도 분석 결과 (없으면 null) — B2 수지니 연동
  shapResult: ShapResult | null;
  // [C1 응답 필드 반영] v12.6 — 백엔드가 주는데 UI가 안 쓰던 5 영역
  marketReport?: {
    floating_population: number | null;
    rent_index: number | null;
    competition_intensity: number | null;
    estimated_revenue: number | null;
    survival_rate: number | null;
    closure_rate: number | null;
    growth_potential: number | null;
    accessibility: number | null;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  districtRankings?: { district: string; score: number; [k: string]: any }[];
  // [C1] DistrictComparison — DashboardPanelView 실데이터 렌더용 (backend SimulationOutput.comparison)
  // 2026-04-27: backend가 폴백 시 5필드 모두 None을 보냄 — 거짓 양성 회피.
  comparison?: {
    district: string;
    score: number | null;
    revenue: number | null;
    bep: number | null;
    survival: number | null;
    cannibalization: number | null;
  }[];
  winnerDistrict?: string;
  topCandidates?: string[];
  legalRisks?: {
    type: string;
    risk_level: string;
    detail: string;
    recommendation?: string;
    articles?: { article_ref: string; content: string }[];
  }[];
  overallLegalRisk?: string;
  vacancyApplied?: boolean;
  vacancySpots?: {
    id: number;
    lat: number;
    lon: number;
    dong_name: string;
    listing_count: number;
  }[];
  analysis_metrics?: {
    main_target_age?: string;
    peak_time?: string;
    [k: string]: unknown;
  };
  // [B2 시나리오] 낙관/기본/비관 분기 매출 시나리오 — C1 UI 연동용
  scenarios?: {
    optimistic: { quarter: number; revenue: number }[];
    base: { quarter: number; revenue: number }[];
    pessimistic: { quarter: number; revenue: number }[];
  } | null;
  // [B2 수지니] 폐업 위험도
  closureRisk?: ClosureRisk | null;
  // [PR #72] 경쟁 매장 인텔리전스 (500m 반경)
  competitorIntel?: {
    competition_500m?: {
      total_competitors: number;
      franchise_count?: number;
      independent_count?: number;
      saturation_level: string;
      saturation_score?: number;
      brand_distribution?: Record<string, number>;
      samples: Array<{
        place_name: string;
        distance_m: number;
        category?: string;
      }>;
    };
    cannibalization?: { estimated_revenue_impact_pct: number };
    market_entry_signal?: 'green' | 'yellow' | 'red';
    differentiation_position?: string;
    key_opportunities?: string[];
    key_risks?: string[];
    recommended_actions?: string[];
    narrative?: string;
  } | null;
  // [PR #71] 트렌드 전망 (trend_forecaster 에이전트)
  trendForecast?: TrendForecast | null;
  // [PR #75] 인구통계 심층 분석 (demographic_depth 에이전트)
  demographicReport?: DemographicReport | null;
  // 추천 동 전체 경쟁업체 좌표 (winner + top3 합산)
  allCompetitorLocations?: Array<{
    id: string;
    place_name: string;
    brand_name?: string;
    lat: number;
    lng: number;
    distance_m?: number;
    is_franchise?: boolean;
    category?: string;
    source_dong?: string;
  }>;
}

/**
 * SimulationOutput (snake_case) → SimResult (camelCase) 변환.
 * market_report 부재 시 chartData는 빈 배열 → 렌더 시 empty state.
 */
export function toSimResultViewModel(simRes: SimulationOutput): SimResult {
  const mr = simRes.market_report;
  const topComp = simRes.comparison?.[0];
  const topRisk = simRes.legal_risks?.[0];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = simRes as SimulationOutput & Record<string, any>;

  return {
    score: topComp?.score ?? 87,
    revenue: topComp?.revenue ?? null,
    netProfit: (topComp as unknown as Record<string, unknown> | undefined)?.net_profit as
      | number
      | null
      | undefined,
    riskLevel: topRisk?.risk_level ?? 'LOW',
    recommendation: simRes.ai_recommendation || '',
    chartData: mr
      ? [
          { label: '유동인구', value: mr.floating_population },
          { label: '임대료', value: mr.rent_index },
          { label: '경쟁강도', value: mr.competition_intensity },
          { label: '매출추정', value: mr.estimated_revenue },
          {
            label: '폐업률',
            // closure_rate 우선. 없으면 survival_rate에서 역산하되 둘 다 null이면 null (가짜 100/100 금지).
            value:
              mr.closure_rate != null
                ? Math.round(mr.closure_rate * 100)
                : mr.survival_rate != null
                  ? 100 - mr.survival_rate
                  : null,
          },
          { label: '성장성', value: mr.growth_potential },
          { label: '접근성', value: mr.accessibility },
        ]
      : [],
    quarterlyProjection: simRes.quarterly_projection ?? [],
    shapResult: simRes.shap_result ?? null,
    marketReport: mr,
    districtRankings: raw.district_rankings,
    comparison: simRes.comparison,
    winnerDistrict: raw.winner_district,
    topCandidates: raw.top_3_candidates,
    legalRisks: simRes.legal_risks,
    overallLegalRisk: raw.overall_legal_risk,
    vacancyApplied: raw.vacancy_applied,
    vacancySpots: raw.vacancy_spots ?? [],
    analysis_metrics: raw.analysis_metrics as unknown as SimResult['analysis_metrics'],
    scenarios: simRes.scenarios ?? null,
    closureRisk: simRes.closure_risk ?? null,
    competitorIntel: raw.competitor_intel ?? null,
    trendForecast: raw.trend_forecast ?? null,
    demographicReport: raw.demographic_report ?? null,
    allCompetitorLocations: raw.all_competitor_locations ?? [],
  };
}
