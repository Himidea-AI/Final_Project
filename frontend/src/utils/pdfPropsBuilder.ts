/**
 * pdfPropsBuilder — 저장된 SimulationOutput / ABM result 에서 mode-aware
 * PDF props 조립.
 *
 * - buildForeseePdfProps : ML 예측 (simulation_foresee 테이블)
 * - buildAiPdfProps      : LangGraph 분석 (simulation_ai 테이블)
 * - buildAbmPdfProps     : ABM 시뮬 결과
 * - buildPdfPropsFromSimulation : @deprecated 통합 빌더 (legacy 호환)
 *
 * App.tsx 의 라이브 simResult(camelCase)와 달리 saved 는 snake_case JSONB
 * 그대로. 동일 PDF 품질을 재현하기 위해 여기서 변환.
 */

import type { SimulationOutput, CustomerSegment, ShapFeatureItem } from '../types';
import type { CannRow, NeighborhoodRow } from '../components/PDF/HiddenPDFTemplate';

/* ═══════════════════════════════════════════════════════
   FORESEE PDF data shape
   ═══════════════════════════════════════════════════════ */
export interface ForeseePdfData {
  predicted_monthly_revenue: number | null;
  quarterly_projection: { quarter: number; revenue: number }[];
  scenarios: { optimistic: number | null; base: number | null; pessimistic: number | null } | null;
  /** 시나리오 4분기 시리즈 — 낙관/기본/비관 분기별 매출 표용 */
  scenarios_quarterly: {
    optimistic: number[];
    base: number[];
    pessimistic: number[];
  } | null;
  /** 분기별 KPI 표 — visits, avg_ticket 등 (revenue 외) */
  quarterly_kpi: {
    quarter: number;
    revenue: number;
    visits: number | null;
    avg_ticket: number | null;
    yoy_pct: number | null;
  }[];
  closure_risk_score: number | null;
  closure_risk_level: 'safe' | 'caution' | 'danger' | 'unknown' | null;
  closure_top_signal: string | null;
  closure_rate_recent: number | null;
  closure_monthly: number[];
  /** closure_risk.top_signals_lgbm Top 5 (방향성 포함) */
  closure_top_features: { feature: string; contribution: number }[];
  /** 동/자치구/매장 폐업률 비교 — peer_distribution 기반 */
  closure_benchmark: {
    self_pct: number | null;
    dong_avg_pct: number | null;
    gu_avg_pct: number | null;
  } | null;
  customer_segment: CustomerSegment | null;
  living_pop_quarter: {
    peak_time_zone: number;
    peak_pop: number;
    all_hours: { time_zone: number; predicted_pop: number }[];
  } | null;
  /** 인구 통계 보강 — 4분면 (연령×성별), 요일별, 권고 */
  demographic_extra: {
    core_age: string | null;
    core_gender: string | null;
    weekday_weekend_ratio: number | null;
    peak_consumption_hours: string[];
    elderly_ratio: number | null;
    brand_match_score: number | null;
    target_alignment_score: number | null;
  } | null;
  bep_months: number | null;
  margin_rate: number | null;
  profit_simulation: { quarter: number; revenue: number; cost: number; operating_profit: number }[];
  /** 12개월 누적 손익 (BEP point 표시) */
  cumulative_profit_monthly: number[];
  /** 비용 구조 — 임대/인건/원재료/마케팅 (월 단위 추정) */
  cost_breakdown: {
    rent: number | null;
    labor: number | null;
    cogs: number | null;
    marketing: number | null;
  } | null;
  /** 시나리오별 BEP (개월) */
  bep_scenarios: {
    optimistic: number | null;
    base: number | null;
    pessimistic: number | null;
  } | null;
  /** 3년 누적 ROI 카드용 — yr1/yr2/yr3 누적 영업이익 */
  three_year_roi: {
    year1: number | null;
    year2: number | null;
    year3: number | null;
  } | null;
  shap_top: ShapFeatureItem[];
  shap_summary: string[];
  /** SHAP 6~10순위 — 보조 표시 */
  shap_secondary: ShapFeatureItem[];
  /** 모델 학습 메타 — 출처/기간/RMSE 표시용 */
  model_meta: {
    train_period: string | null;
    sample_size: number | null;
    rmse: number | null;
    region: string | null;
  } | null;
}

/* ═══════════════════════════════════════════════════════
   AI PDF data shape
   ═══════════════════════════════════════════════════════ */
export interface AiPdfData {
  winner_district: string | null;
  ai_verdict_summary: string | null;
  market_entry_signal: 'green' | 'yellow' | 'red' | null;
  overall_legal_risk: 'safe' | 'caution' | 'danger' | null;
  /** Top 3 후보 동 — score + 핵심 이유 */
  top_3_candidates: {
    district: string;
    score: string;
    summary: string;
  }[];
  /** 분석 메타 — agent 수 / 데이터 출처 */
  analysis_meta: {
    agent_count: number;
    data_sources: string[];
    generated_at: string;
  };
  district_rankings: {
    rank: number;
    district: string;
    score: string;
    closure_rate: string;
    bep: string;
    /** 화면 동일 — 매출 성장률 (%) */
    sales_growth: string;
    /** 용도지역 risk: safe/caution/danger */
    zoning_risk: 'safe' | 'caution' | 'danger' | null;
    /** legacy — backend 미제공 (null 만 들어감) */
    differentiation: string | null;
    commentary: string | null;
  }[];
  legal_risks: {
    type: string;
    risk_level: string;
    detail: string;
    recommendation: string | null;
    /** articles 첫 1개 인용 */
    article_ref: string | null;
  }[];
  spot_evaluations: {
    rank_label: string;
    dong_name: string;
    level: 'safe' | 'caution' | 'danger';
    summary: string | null;
    closest_m: number | null;
  }[];
  trend_forecast: {
    direction: string | null;
    narrative: string | null;
    /** 보강 — 핵심 지표 4종 */
    score: number | null;
    yoy_change_pct: number | null;
    industry: string | null;
    samples: number[]; // 월별 0~100 (추세 라인용)
    horizon_months: number | null;
  } | null;
  competitor_intel: {
    market_entry_signal: 'green' | 'yellow' | 'red' | null;
    competition_count: number | null;
    saturation_level: string | null;
    /** 보강 — 카니발리제이션 / 차별화 / 추천액션 */
    cannibalization_pct: number | null;
    differentiation_position: string | null;
    recommended_actions: string[];
    top_competitors: {
      place_name: string;
      brand_name: string | null;
      distance_text: string;
      category: string | null;
    }[];
  } | null;
  demographic_report: {
    core_age: string | null;
    core_gender: string | null;
    brand_match_score: number | null;
    top_age_groups: { age_group: string; share: number }[];
    narrative: string | null;
    /** 보강 — 거주/방문, 평일/주말, 고령자 비율, 소득 */
    resident_visitor_ratio: number | null;
    weekday_weekend_ratio: number | null;
    elderly_ratio: number | null;
    area_income_level: string | null;
    population_trend: string | null;
    peak_consumption_hours: string[];
  } | null;
  agent_attributions: {
    display_name: string;
    kind: string;
    verdict: string;
    reasoning: string;
    /** 보강 — confidence (옵션) / key_finding 추출 */
    confidence: string | null;
    key_finding: string | null;
  }[];
}

/* ═══════════════════════════════════════════════════════
   ABM PDF data shape
   ═══════════════════════════════════════════════════════ */
export interface AbmPdfData {
  kpis: { title: string; value: string; accent?: string }[];
  peak_hours: number[] | null;
  /** 24시간 visits 분포 (있으면) */
  hourly_visits: number[] | null;
  /** 시뮬 메타 — Tier 분포, daily_visits_std, monthly_revenue_estimate */
  sim_meta: {
    n_agents: number | null;
    days: number | null;
    tier_s: number | null;
    tier_a: number | null;
    tier_b: number | null;
    daily_visits: number | null;
    daily_visits_std: number | null;
    monthly_revenue_estimate: number | null;
    estimated_cost_usd: number | null;
    role_distribution: { role: string; count: number }[];
  };
  cannibalization: {
    estimated_impact_pct: number;
    affected_stores: {
      name: string;
      dong: string;
      distance_text: string;
      distance_m: number | null;
      impact_pct: number;
    }[];
    /** 1차/2차 영향권 카운트 */
    primary_zone_count: number;
    secondary_zone_count: number;
  } | null;
  dong_totals: {
    dong: string;
    daily_visits: number;
    daily_revenue: number;
    /** 동별 매장 수 / 평균 매출 (있으면) */
    store_count: number | null;
    avg_revenue: number | null;
  }[];
  /** 동 winner — 메달 표시 */
  dong_winner: string | null;
  /** 동별 시간대 매트릭스 — heatmap-like grid (4동 × 24h 또는 4동 × 6 구간) */
  dong_hour_matrix: { dong: string; hours: number[] }[] | null;
  /** narrator commentary (동별 코멘트) */
  dong_commentary: { dong: string; comment: string }[];
  scenario: {
    weather_override: string | null;
    weekend_force: boolean | null;
    rent_shock_pct: number | null;
    /** 보강 — store_area, baseline 대비 변화율 */
    store_area_m2: number | null;
    baseline_visits: number | null;
    baseline_revenue: number | null;
    visits_delta_pct: number | null;
    revenue_delta_pct: number | null;
    narrator_summary: string | null;
    /** 민감도 분석 — 각 변수별 영향도 */
    sensitivity: { variable: string; impact_pct: number }[];
  } | null;
}

/* ═══════════════════════════════════════════════════════
   공용 입력
   ═══════════════════════════════════════════════════════ */
export interface BuilderInput {
  simResult: SimulationOutput;
  businessType?: string | null;
  brandName?: string | null;
  savedHistoryId: number;
}

export interface AbmBuilderInput {
  abmResult: Record<string, unknown> | null;
  brandName?: string | null;
  businessType?: string | null;
  savedHistoryId: number | null;
}

interface PdfPropsBase {
  districtFull: string;
  reportDate: string;
  savedHistoryId: number | null;
}

export interface ForeseePdfProps extends PdfPropsBase {
  mode: 'foresee';
  foresee: ForeseePdfData;
}

export interface AiPdfProps extends PdfPropsBase {
  mode: 'ai';
  ai: AiPdfData;
}

export interface AbmPdfProps extends PdfPropsBase {
  mode: 'abm';
  abm: AbmPdfData;
}

/* ═══════════════════════════════════════════════════════
   helpers
   ═══════════════════════════════════════════════════════ */
const INDUSTRY_BASE: Record<string, number> = {
  cafe: 0.25,
  coffee: 0.25,
  chicken: 0.1,
  burger: 0.2,
  korean: 0.15,
};

function industryKeyFrom(bt?: string | null): string {
  if (!bt) return '';
  const k = bt.toLowerCase();
  if (k.includes('커피') || k.includes('카페') || k === 'coffee' || k === 'cafe') return 'coffee';
  if (k.includes('치킨') || k === 'chicken') return 'chicken';
  if (k.includes('햄버거') || k.includes('패스트푸드') || k === 'burger') return 'burger';
  if (k.includes('한식') || k === 'korean') return 'korean';
  return '';
}

function formatWon(v: number | null | undefined): string {
  if (v == null) return '—';
  return `₩ ${v.toLocaleString('ko-KR')}`;
}

function formatDistance(d: number | null | undefined): string {
  if (typeof d !== 'number' || !Number.isFinite(d)) return '—';
  return d >= 1000 ? `${(d / 1000).toFixed(1)}km` : `${Math.round(d)}m`;
}

function todayStamp(): string {
  const today = new Date();
  return `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(
    today.getDate(),
  ).padStart(2, '0')}`;
}

function districtFullFrom(r: SimulationOutput): string {
  const winner =
    (r as unknown as { winner_district?: string }).winner_district || r.target_district || '—';
  return `마포구 ${winner}`;
}

/* ═══════════════════════════════════════════════════════
   FORESEE BUILDER
   ═══════════════════════════════════════════════════════ */
export function buildForeseePdfProps(input: BuilderInput): ForeseePdfProps {
  const { simResult, savedHistoryId } = input;
  const r = simResult as unknown as Record<string, unknown>;
  const districtFull = districtFullFrom(simResult);

  // winner 동 prediction 우선 — /predict 분리 호출 시 district_predictions[winner_idx]
  // 의 quarterly_projection / scenarios 가 동 단위 정확 데이터.
  // simResult.quarterly_projection 은 winner 또는 평균 fallback 으로 일치하지 않을 수 있음.
  // (2026-05-10) PDF 가 "저장한 내용과 다름" 회귀 차단 — 대시보드 sortByRanking 동등 패턴.
  const winnerName = (r.winner_district as string | undefined) ?? null;
  const dpreds = Array.isArray(r.district_predictions)
    ? (r.district_predictions as Array<{
        district?: string;
        is_excluded_combo?: boolean;
        quarterly_projection?: Array<{ quarter?: number; revenue?: number }>;
        scenarios?: {
          optimistic?: { revenue?: number }[];
          base?: { revenue?: number }[];
          pessimistic?: { revenue?: number }[];
        } | null;
      }>)
    : [];
  const winnerPred =
    (winnerName ? dpreds.find((p) => p.district === winnerName && !p.is_excluded_combo) : null) ??
    dpreds.find((p) => !p.is_excluded_combo) ??
    null;

  const qpRawWinner = winnerPred?.quarterly_projection;
  const qpRawTop = Array.isArray(r.quarterly_projection)
    ? (r.quarterly_projection as Array<{ quarter?: number; revenue?: number }>)
    : [];
  const qpRaw = Array.isArray(qpRawWinner) && qpRawWinner.length > 0 ? qpRawWinner : qpRawTop;
  const quarterly_projection = qpRaw
    .filter((q) => typeof q.revenue === 'number')
    .map((q, i) => ({ quarter: q.quarter ?? i + 1, revenue: q.revenue as number }));

  const scenariosRaw =
    (winnerPred?.scenarios as
      | {
          optimistic?: { revenue?: number }[];
          base?: { revenue?: number }[];
          pessimistic?: { revenue?: number }[];
        }
      | null
      | undefined) ??
    (r.scenarios as
      | {
          optimistic?: { revenue?: number }[];
          base?: { revenue?: number }[];
          pessimistic?: { revenue?: number }[];
        }
      | null
      | undefined);
  const scenarios =
    scenariosRaw && (scenariosRaw.optimistic || scenariosRaw.base || scenariosRaw.pessimistic)
      ? {
          optimistic: scenariosRaw.optimistic?.[0]?.revenue ?? null,
          base: scenariosRaw.base?.[0]?.revenue ?? null,
          pessimistic: scenariosRaw.pessimistic?.[0]?.revenue ?? null,
        }
      : null;

  // 시나리오 4분기 시리즈
  const extractQ = (arr: { revenue?: number }[] | undefined): number[] =>
    Array.isArray(arr) ? arr.slice(0, 4).map((q) => q.revenue ?? 0) : [];
  const scenarios_quarterly = scenariosRaw
    ? {
        optimistic: extractQ(scenariosRaw.optimistic),
        base: extractQ(scenariosRaw.base),
        pessimistic: extractQ(scenariosRaw.pessimistic),
      }
    : null;

  // 분기별 KPI 표 — visits / avg_ticket 추정 (quarterly_projection 기반)
  // backend 가 직접 visits/avg_ticket 을 안 주면 baseline 비율로 추정
  const quarterly_kpi = quarterly_projection.slice(0, 4).map((q, i) => {
    const prev = i > 0 ? quarterly_projection[i - 1]?.revenue : null;
    const yoy_pct = prev && prev > 0 ? ((q.revenue - prev) / prev) * 100 : null;
    return {
      quarter: q.quarter,
      revenue: q.revenue,
      visits: null as number | null, // backend 데이터 없으면 — 표시
      avg_ticket: null as number | null,
      yoy_pct,
    };
  });

  // closure_risk / closure_rate / customer_segment / living_pop_forecast / emerging_signal
  // 모두 winner 동의 district_predictions[winner] 에서 우선 추출 (동 단위 정확).
  // top-level simResult.* 는 평균/winner 의 fallback. 화면 (대시보드) 가 winner pred 를 사용하기에
  // PDF 도 동일 패턴으로 통일 (2026-05-10). 빌더 매핑 누락으로 빈 셀 회귀 차단.
  const winnerExtras = winnerPred as unknown as
    | {
        closure_risk?: unknown;
        closure_rate?: unknown;
        customer_segment?: unknown;
        living_pop_forecast?: unknown;
        emerging_signal?: unknown;
      }
    | null
    | undefined;
  const closureRisk = (winnerExtras?.closure_risk ?? r.closure_risk) as
    | {
        risk_score?: number;
        risk_level?: 'safe' | 'caution' | 'danger';
        top_signals_lgbm?: { feature?: string; feature_key?: string; contribution?: number }[];
      }
    | null
    | undefined;
  const closureRate = (winnerExtras?.closure_rate ?? r.closure_rate) as
    | { closure_rate?: number; monthly_closure_rates?: number[] }
    | null
    | undefined;

  const closure_top_features = (closureRisk?.top_signals_lgbm ?? [])
    .slice(0, 5)
    .filter((s) => typeof s.contribution === 'number')
    .map((s) => ({
      feature: s.feature ?? s.feature_key ?? '신호',
      contribution: s.contribution as number,
    }));

  // closure_benchmark — backend 직접 제공 시에만 표시 (peer_distribution.p50 derive 제거).
  // 사용자 요청 (2026-05-10) 화면에 있는 정보로만 PDF 생성 — 추정 데이터 차단.
  const closure_benchmark =
    closureRate?.closure_rate != null
      ? {
          self_pct: closureRate.closure_rate,
          dong_avg_pct: null,
          gu_avg_pct: null,
        }
      : null;

  const customerSegment =
    (winnerExtras?.customer_segment as CustomerSegment | null | undefined) ??
    (r.customer_segment as CustomerSegment | null | undefined) ??
    null;

  const livingPop = (winnerExtras?.living_pop_forecast ?? r.living_pop_forecast) as
    | {
        quarters?: {
          peak_time_zone?: number;
          peak_pop?: number;
          all_hours?: { time_zone?: number; predicted_pop?: number }[];
        }[];
      }
    | null
    | undefined;
  const q1 = livingPop?.quarters?.[0];
  const living_pop_quarter =
    q1 && typeof q1.peak_time_zone === 'number' && typeof q1.peak_pop === 'number'
      ? {
          peak_time_zone: q1.peak_time_zone,
          peak_pop: q1.peak_pop,
          all_hours: (q1.all_hours ?? [])
            .filter(
              (h): h is { time_zone: number; predicted_pop: number } =>
                typeof h.time_zone === 'number' && typeof h.predicted_pop === 'number',
            )
            .map((h) => ({ time_zone: h.time_zone, predicted_pop: h.predicted_pop })),
        }
      : null;

  // demographic_report 일부 추출 — Foresee 페이지 4 보강
  const demoRaw = r.demographic_report as
    | {
        core_demographic?: { age?: string; gender?: string };
        weekday_weekend_ratio?: number;
        peak_consumption_hours?: string[];
        elderly_ratio?: number | null;
        brand_target_match_score?: number | null;
        target_alignment_score?: number | null;
      }
    | null
    | undefined;
  const demographic_extra = demoRaw
    ? {
        core_age: demoRaw.core_demographic?.age ?? null,
        core_gender: demoRaw.core_demographic?.gender ?? null,
        weekday_weekend_ratio: demoRaw.weekday_weekend_ratio ?? null,
        peak_consumption_hours: demoRaw.peak_consumption_hours ?? [],
        elderly_ratio: demoRaw.elderly_ratio ?? null,
        brand_match_score: demoRaw.brand_target_match_score ?? null,
        target_alignment_score: demoRaw.target_alignment_score ?? null,
      }
    : null;

  const finalReport = r.final_report as
    | {
        profit_simulation?: {
          monthly_revenue?: number;
          monthly_cost?: number;
          margin_rate?: number;
          bep_months?: number;
        };
      }
    | null
    | undefined;
  const ps = finalReport?.profit_simulation;

  // 추정 데이터 전부 제거 (사용자 요청 2026-05-10) — backend 가 직접 분기별 cost 를
  // 주지 않는 이상 monthly_cost*3 derive / 12개월 누적 / 비용 구조 도넛 / BEP 시나리오
  // / 3년 ROI 모두 hardcoded 비율 추정. 화면에 없는 정보 → PDF 도 표시 X.
  const profit_simulation: ForeseePdfData['profit_simulation'] = [];
  const cumulative_profit_monthly: number[] = [];
  const cost_breakdown = null;
  const bep_scenarios = null;
  const three_year_roi = null;

  // SHAP — winner 동의 district_predictions[winner].shap_result 우선 (매출 예측 동일 패턴).
  // top-level simResult.shap_result 는 평균/winner fallback 일 수 있어 동 단위 정확치 X.
  // (2026-05-10) 사용자 보고 — PDF SHAP 값 이상함 → winner 동 직접 사용.
  const winnerShapRaw = (winnerPred as { shap_result?: unknown } | null | undefined)?.shap_result;
  const topLevelShap = r.shap_result;
  const shapResult = (winnerShapRaw ?? topLevelShap) as
    | {
        feature_importance?: ShapFeatureItem[];
        summary?: string[];
        base_value?: number;
        predicted_value?: number;
      }
    | null
    | undefined;
  const shapAll = shapResult?.feature_importance ?? [];
  const shap_top = shapAll.slice(0, 5);
  const shap_secondary = shapAll.slice(5, 10);
  const shap_summary = shapResult?.summary ?? [];

  // 모델 메타 — backend 직접 제공 데이터 없으므로 hardcoded 텍스트 제거.
  // 화면에 표시 안 되는 메타라 PDF 도 비워둠 (사용자 요청 2026-05-10).
  const model_meta = null;

  return {
    mode: 'foresee',
    districtFull,
    reportDate: todayStamp(),
    savedHistoryId,
    foresee: {
      predicted_monthly_revenue: (r.predicted_monthly_revenue as number | null | undefined) ?? null,
      quarterly_projection,
      scenarios,
      scenarios_quarterly,
      quarterly_kpi,
      closure_risk_score: closureRisk?.risk_score ?? null,
      closure_risk_level: closureRisk?.risk_level ?? null,
      closure_top_signal: closureRisk?.top_signals_lgbm?.[0]?.feature ?? null,
      closure_rate_recent: closureRate?.closure_rate ?? null,
      closure_monthly: closureRate?.monthly_closure_rates ?? [],
      closure_top_features,
      closure_benchmark,
      customer_segment: customerSegment,
      living_pop_quarter,
      demographic_extra,
      bep_months: (r.bep_months as number | null | undefined) ?? ps?.bep_months ?? null,
      margin_rate: ps?.margin_rate ?? null,
      profit_simulation,
      cumulative_profit_monthly,
      cost_breakdown,
      bep_scenarios,
      three_year_roi,
      shap_top,
      shap_secondary,
      shap_summary,
      model_meta,
    },
  };
}

/* ═══════════════════════════════════════════════════════
   AI BUILDER
   ═══════════════════════════════════════════════════════ */
export function buildAiPdfProps(input: BuilderInput): AiPdfProps {
  const { simResult, savedHistoryId } = input;
  const r = simResult as unknown as Record<string, unknown>;
  const districtFull = districtFullFrom(simResult);

  const finalReport = r.final_report as
    | { summary?: string; final_recommendation?: string }
    | null
    | undefined;
  const ai_verdict_summary = finalReport?.summary ?? finalReport?.final_recommendation ?? null;

  // 화면 DistrictRankings 와 동일 컬럼 — 점수 / 매출성장 / 용도지역. backend 미제공 필드
  // (commentary, differentiation_score) 제거 (2026-05-10 사용자 요청 화면 일관).
  const districtRankingsRaw = Array.isArray(r.district_rankings)
    ? (r.district_rankings as Array<{
        rank?: number;
        district?: string;
        score?: number;
        sales_growth?: number;
        zoning_risk?: 'safe' | 'caution' | 'danger' | string;
        closure_rate?: number;
        bep_quarters?: number;
      }>)
    : [];

  const district_rankings = districtRankingsRaw.slice(0, 16).map((row, i) => ({
    rank: row.rank ?? i + 1,
    district: row.district ?? '—',
    score: typeof row.score === 'number' ? row.score.toFixed(1) : '—',
    closure_rate:
      typeof row.closure_rate === 'number' ? `${(row.closure_rate * 100).toFixed(1)}%` : '—',
    bep: typeof row.bep_quarters === 'number' ? `${row.bep_quarters}분기` : '—',
    // 화면 표시 필드 — 빌더 추가:
    sales_growth: typeof row.sales_growth === 'number' ? `${row.sales_growth.toFixed(1)}%` : '—',
    zoning_risk:
      row.zoning_risk === 'safe' || row.zoning_risk === 'caution' || row.zoning_risk === 'danger'
        ? (row.zoning_risk as 'safe' | 'caution' | 'danger')
        : null,
    differentiation: null,
    commentary: null,
  }));

  // Top 3 candidates
  const top3Names = Array.isArray(r.top_3_candidates)
    ? (r.top_3_candidates as string[]).slice(0, 3)
    : [];
  const top_3_candidates = top3Names.map((name) => {
    const found = districtRankingsRaw.find((d) => d.district === name);
    return {
      district: name,
      score: typeof found?.score === 'number' ? String(Math.round(found.score)) : '—',
      summary:
        typeof found?.closure_rate === 'number'
          ? `폐업률 ${(found.closure_rate * 100).toFixed(1)}% / BEP ${found.bep_quarters ?? '—'}분기`
          : '데이터 부족',
    };
  });

  const legalRisksRaw = Array.isArray(r.legal_risks)
    ? (r.legal_risks as Array<{
        type?: string;
        risk_level?: string;
        detail?: string;
        recommendation?: string;
        articles?: Array<{ article_ref?: string; content?: string }>;
        spot_evaluations?: Array<{
          rank_label?: string;
          dong_name?: string;
          level?: 'safe' | 'caution' | 'danger';
          summary?: string;
          closest_m?: number | null;
        }>;
      }>)
    : [];

  // HIGH 우선 정렬
  const sorted = [...legalRisksRaw].sort((a, b) => {
    const score = (lvl: string | undefined) => {
      const u = String(lvl ?? '').toUpperCase();
      if (u === 'HIGH' || lvl === 'danger') return 3;
      if (u === 'MEDIUM' || lvl === 'caution') return 2;
      return 1;
    };
    return score(b.risk_level) - score(a.risk_level);
  });

  const legal_risks = sorted.slice(0, 14).map((x) => ({
    type: x.type ?? '항목',
    risk_level: String(x.risk_level ?? 'low'),
    detail: x.detail ?? x.recommendation ?? '—',
    recommendation: x.recommendation ?? null,
    article_ref: x.articles?.[0]?.article_ref ?? null,
  }));

  const spot_evaluations: AiPdfData['spot_evaluations'] = [];
  for (const lr of legalRisksRaw) {
    if (Array.isArray(lr.spot_evaluations)) {
      for (const e of lr.spot_evaluations) {
        if (e.rank_label && e.dong_name && e.level) {
          spot_evaluations.push({
            rank_label: e.rank_label,
            dong_name: e.dong_name,
            level: e.level,
            summary: e.summary ?? null,
            closest_m: typeof e.closest_m === 'number' ? e.closest_m : null,
          });
        }
      }
    }
  }

  const trendForecastRaw = r.trend_forecast as
    | {
        forecast?: {
          direction?: string;
          narrative?: string;
          score?: number;
          horizon_months?: number;
        };
        industry_trend?: {
          industry?: string;
          yoy_change_pct?: number | null;
          samples?: number[];
        };
      }
    | null
    | undefined;
  const trend_forecast = trendForecastRaw?.forecast
    ? {
        direction: trendForecastRaw.forecast.direction ?? null,
        narrative: trendForecastRaw.forecast.narrative ?? null,
        score: trendForecastRaw.forecast.score ?? null,
        yoy_change_pct: trendForecastRaw.industry_trend?.yoy_change_pct ?? null,
        industry: trendForecastRaw.industry_trend?.industry ?? null,
        samples: Array.isArray(trendForecastRaw.industry_trend?.samples)
          ? (trendForecastRaw.industry_trend?.samples as number[]).slice(0, 12)
          : [],
        horizon_months: trendForecastRaw.forecast.horizon_months ?? null,
      }
    : null;

  const ciRaw = r.competitor_intel as
    | {
        market_entry_signal?: 'green' | 'yellow' | 'red' | string;
        differentiation_position?: string | null;
        recommended_actions?: string[];
        competition_500m?: {
          count?: number;
          total_competitors?: number;
          saturation_level?: string;
          samples?: Array<{
            place_name?: string;
            brand_name?: string;
            distance_m?: number;
            category?: string;
          }>;
        };
        cannibalization?: {
          estimated_revenue_impact_pct?: number | null;
        };
      }
    | null
    | undefined;
  const competitor_intel: AiPdfData['competitor_intel'] = ciRaw
    ? {
        market_entry_signal:
          ciRaw.market_entry_signal === 'green' ||
          ciRaw.market_entry_signal === 'yellow' ||
          ciRaw.market_entry_signal === 'red'
            ? (ciRaw.market_entry_signal as 'green' | 'yellow' | 'red')
            : null,
        competition_count:
          ciRaw.competition_500m?.count ?? ciRaw.competition_500m?.total_competitors ?? null,
        saturation_level: ciRaw.competition_500m?.saturation_level ?? null,
        // backend competitor_intel.cannibalization.estimated_revenue_impact_pct 는 fraction (예: -0.082).
        // ABM 의 cannibalization.estimated_impact_pct 는 percent (예: 19.0). 빌더에서 전부 percent 정규화.
        // (2026-05-10) 사용자 보고 — 자기잠식 % 표시 이상 → 단위 통일.
        cannibalization_pct:
          typeof ciRaw.cannibalization?.estimated_revenue_impact_pct === 'number'
            ? ciRaw.cannibalization.estimated_revenue_impact_pct * 100
            : null,
        differentiation_position: ciRaw.differentiation_position ?? null,
        recommended_actions: Array.isArray(ciRaw.recommended_actions)
          ? ciRaw.recommended_actions.slice(0, 3)
          : [],
        top_competitors: (ciRaw.competition_500m?.samples ?? []).slice(0, 5).map((s) => ({
          place_name: s.place_name ?? '경쟁업체',
          brand_name: s.brand_name ?? null,
          distance_text: formatDistance(s.distance_m ?? null),
          category: s.category ?? null,
        })),
      }
    : null;

  const demoRaw = r.demographic_report as
    | {
        core_demographic?: { age?: string; gender?: string };
        brand_target_match_score?: number | null;
        top_3_age_groups?: { age_group?: string; share?: number }[];
        narrative?: string;
        resident_visitor_ratio?: number | null;
        weekday_weekend_ratio?: number | null;
        elderly_ratio?: number | null;
        area_income_level?: string;
        population_trend?: string;
        peak_consumption_hours?: string[];
      }
    | null
    | undefined;
  const demographic_report = demoRaw
    ? {
        core_age: demoRaw.core_demographic?.age ?? null,
        core_gender: demoRaw.core_demographic?.gender ?? null,
        brand_match_score: demoRaw.brand_target_match_score ?? null,
        top_age_groups: (demoRaw.top_3_age_groups ?? [])
          .filter(
            (a): a is { age_group: string; share: number } =>
              typeof a.age_group === 'string' && typeof a.share === 'number',
          )
          .map((a) => ({ age_group: a.age_group, share: a.share })),
        narrative: demoRaw.narrative ?? null,
        resident_visitor_ratio: demoRaw.resident_visitor_ratio ?? null,
        weekday_weekend_ratio: demoRaw.weekday_weekend_ratio ?? null,
        elderly_ratio: demoRaw.elderly_ratio ?? null,
        area_income_level: demoRaw.area_income_level ?? null,
        population_trend: demoRaw.population_trend ?? null,
        peak_consumption_hours: demoRaw.peak_consumption_hours ?? [],
      }
    : null;

  const agentAttrRaw = Array.isArray(r.agent_attributions)
    ? (r.agent_attributions as Array<{
        display_name?: string;
        kind?: string;
        verdict?: string;
        reasoning?: string;
        confidence?: string;
        key_finding?: string;
      }>)
    : [];
  const agent_attributions = agentAttrRaw.slice(0, 7).map((a) => ({
    display_name: a.display_name ?? '에이전트',
    kind: a.kind ?? 'LLM',
    verdict: a.verdict ?? '—',
    reasoning: a.reasoning ?? '—',
    confidence: a.confidence ?? null,
    key_finding:
      a.key_finding ??
      (a.reasoning && a.reasoning.length > 0 ? a.reasoning.split('.')[0] + '.' : null),
  }));

  const overallLegalRisk = r.overall_legal_risk;
  const overall_legal_risk =
    overallLegalRisk === 'safe' || overallLegalRisk === 'caution' || overallLegalRisk === 'danger'
      ? overallLegalRisk
      : null;

  const winnerSignal = ciRaw?.market_entry_signal;
  const market_entry_signal =
    winnerSignal === 'green' || winnerSignal === 'yellow' || winnerSignal === 'red'
      ? winnerSignal
      : null;

  const analysis_meta = {
    agent_count: agentAttrRaw.length || 7,
    data_sources: ['서울 열린데이터광장', '소상공인진흥공단', 'FTC 가맹사업정보', 'Kakao Local'],
    generated_at: todayStamp(),
  };

  return {
    mode: 'ai',
    districtFull,
    reportDate: todayStamp(),
    savedHistoryId,
    ai: {
      winner_district: (r.winner_district as string | null | undefined) ?? null,
      ai_verdict_summary,
      market_entry_signal,
      overall_legal_risk,
      top_3_candidates,
      analysis_meta,
      district_rankings,
      legal_risks,
      spot_evaluations,
      trend_forecast,
      competitor_intel,
      demographic_report,
      agent_attributions,
    },
  };
}

/* ═══════════════════════════════════════════════════════
   ABM BUILDER
   ═══════════════════════════════════════════════════════ */
export function buildAbmPdfProps(input: AbmBuilderInput): AbmPdfProps {
  const { abmResult, brandName, savedHistoryId } = input;
  const r = (abmResult ?? {}) as Record<string, unknown>;

  // backend /simulate-abm 응답은 top-level flat 구조 (summary wrapper 없음).
  // 키: n_personas / daily_visits_mean / daily_revenue_mean / total_daily_* / peak_hours /
  //   monthly_revenue_estimate / estimated_cost_usd / tier_s_calls / tier_a_calls /
  //   cannibalization / dong_totals / customer_profile_dist / new_store_role_dist
  // 사용자 보고 (2026-05-10): 에이전트수/일방문자수 빈셀 → 잘못된 키 lookup 회귀 fix.
  const summary = (r.summary as Record<string, unknown> | undefined) ?? r;
  const n_agents =
    (r.n_personas as number | undefined) ??
    (summary.n_personas as number | undefined) ??
    (summary.n_agents as number | undefined) ??
    (r.n_agents as number | undefined);
  // 시뮬 일수는 frontend 에서 1로 고정 (AbmTab.tsx:236). backend 응답에 days 직접 미포함 →
  // fallback 1 (사용자 요청 2026-05-10 1일 픽스).
  const days =
    (r.days as number | undefined) ??
    (summary.days as number | undefined) ??
    ((r.scenario_applied as Record<string, unknown> | undefined)?.days as number | undefined) ??
    1;
  const dailyVisits =
    (r.daily_visits_mean as number | undefined) ??
    (r.total_daily_visits as number | undefined) ??
    (summary.daily_visits as number | undefined) ??
    (summary.avg_daily_visits as number | undefined);
  const dailyVisitsStd =
    (r.daily_visits_std as number | undefined) ?? (summary.daily_visits_std as number | undefined);
  const dailyRevenue =
    (r.daily_revenue_mean as number | undefined) ??
    (r.total_daily_revenue as number | undefined) ??
    (summary.daily_revenue as number | undefined) ??
    (summary.avg_daily_revenue as number | undefined);
  const monthlyRevenueEstimate =
    (r.monthly_revenue_estimate as number | undefined) ??
    (summary.monthly_revenue_estimate as number | undefined) ??
    (dailyRevenue != null ? dailyRevenue * 25 : undefined);
  const peakHoursRaw = (r.peak_hours as unknown) ?? summary.peak_hours;
  const peak_hours = Array.isArray(peakHoursRaw)
    ? peakHoursRaw.filter((h): h is number => typeof h === 'number')
    : null;
  const cost =
    (r.estimated_cost_usd as number | undefined) ??
    (summary.estimated_cost_usd as number | undefined);

  // 시간대별 visits — backend 'hourly_visits' 또는 비슷한 키 시도
  const hourlyRaw =
    (summary.hourly_visits as number[] | undefined) ??
    (r.hourly_visits as number[] | undefined) ??
    null;
  const hourly_visits = Array.isArray(hourlyRaw)
    ? hourlyRaw.slice(0, 24).map((v) => (typeof v === 'number' ? v : 0))
    : null;

  // Tier 분포 — backend /simulate-abm 응답에 포함 X (tier_s_calls 는 LLM 호출 횟수, agent 수 아님).
  // 추정 (50/200/n-250 default) 은 사용자 요청 (화면에 있는 정보로만) 정책 위배 → null.
  const tier_s = null;
  const tier_a = null;
  const tier_b = null;

  // role_distribution — backend `customer_profile_dist` (마포 전체) 또는 `new_store_role_dist` (신규 매장 방문자).
  // 신규 매장 분포가 더 의미 있음 (어떤 role 이 새 매장 가는지) → 우선 사용. fallback 마포 전체.
  const roleRaw =
    (r.new_store_role_dist as Record<string, number> | undefined) ??
    (r.customer_profile_dist as Record<string, number> | undefined) ??
    (summary.role_distribution as Record<string, number> | undefined) ??
    null;
  const role_distribution: AbmPdfData['sim_meta']['role_distribution'] = roleRaw
    ? Object.entries(roleRaw)
        .filter(([, v]) => typeof v === 'number')
        .map(([role, count]) => ({ role, count: count as number }))
        .sort((a, b) => b.count - a.count)
    : [];

  const sim_meta: AbmPdfData['sim_meta'] = {
    n_agents: n_agents ?? null,
    days: days ?? null,
    tier_s,
    tier_a,
    tier_b,
    daily_visits: dailyVisits != null ? Math.round(dailyVisits) : null,
    daily_visits_std: dailyVisitsStd != null ? Math.round(dailyVisitsStd) : null,
    monthly_revenue_estimate: monthlyRevenueEstimate ?? null,
    estimated_cost_usd: cost ?? null,
    role_distribution,
  };

  const kpis: AbmPdfData['kpis'] = [
    { title: 'AGENTS', value: n_agents != null ? `${n_agents}명` : '—', accent: '#002cd1' },
    { title: '시뮬 일수', value: days != null ? `${days}일` : '—' },
    {
      title: '일평균 방문',
      value: dailyVisits != null ? `${Math.round(dailyVisits).toLocaleString('ko-KR')}명` : '—',
      accent: '#002cd1',
    },
    {
      title: '일평균 매출',
      value: dailyRevenue != null ? `₩${Math.round(dailyRevenue).toLocaleString('ko-KR')}` : '—',
      accent: '#059669',
    },
    {
      title: '피크 시간',
      value: peak_hours && peak_hours.length > 0 ? `${peak_hours.length}개` : '—',
    },
    {
      title: '예상 비용',
      value: cost != null ? `$${cost.toFixed(2)}` : '—',
    },
  ];

  const cannRaw = r.cannibalization as
    | {
        estimated_impact_pct?: number;
        affected_stores?: Array<{
          name?: string;
          dong?: string;
          dong_name?: string;
          distance_m?: number;
          impact_pct?: number;
        }>;
      }
    | null
    | undefined;
  const cannibalization =
    cannRaw && typeof cannRaw.estimated_impact_pct === 'number'
      ? (() => {
          // affected_stores 가 array 아닐 수 있음 (저장된 result schema 변형 — dict/object/null).
          // (2026-05-10) 사용자 보고 — `.filter is not a function` runtime crash 회귀 차단.
          const rawStores = Array.isArray(cannRaw.affected_stores) ? cannRaw.affected_stores : [];
          const stores = rawStores
            .filter(
              (
                s,
              ): s is {
                name: string;
                dong?: string;
                dong_name?: string;
                distance_m?: number;
                impact_pct: number;
              } =>
                s != null &&
                typeof s === 'object' &&
                typeof (s as { name?: unknown }).name === 'string' &&
                typeof (s as { impact_pct?: unknown }).impact_pct === 'number',
            )
            .map((s) => ({
              name: s.name,
              dong: s.dong ?? s.dong_name ?? '—',
              distance_text: formatDistance(s.distance_m ?? null),
              distance_m: typeof s.distance_m === 'number' ? s.distance_m : null,
              impact_pct: s.impact_pct,
            }));
          // 1차 영향권 (500m 이내) / 2차 (500-1000m)
          const primary = stores.filter((s) => s.distance_m != null && s.distance_m < 500).length;
          const secondary = stores.filter(
            (s) => s.distance_m != null && s.distance_m >= 500 && s.distance_m < 1000,
          ).length;
          return {
            estimated_impact_pct: cannRaw.estimated_impact_pct as number,
            affected_stores: stores,
            primary_zone_count: primary,
            secondary_zone_count: secondary,
          };
        })()
      : null;

  // backend dong_totals = dict {dong_name: {visits, revenue}} (main.py:2864).
  // 빌더가 daily_visits/daily_revenue 키로 lookup 했지만 backend 는 visits/revenue → 항상 빈 배열.
  // (2026-05-10) 키 매핑 fix — visits/revenue 우선, daily_* fallback.
  type DongCell = {
    visits?: number;
    revenue?: number;
    daily_visits?: number;
    daily_revenue?: number;
    store_count?: number;
    avg_revenue?: number;
  };
  const dongTotalsRaw = r.dong_totals as
    | Record<string, DongCell>
    | Array<DongCell & { dong?: string; dong_name?: string }>
    | null
    | undefined;
  const pickVisits = (v: DongCell): number | null =>
    typeof v.visits === 'number'
      ? v.visits
      : typeof v.daily_visits === 'number'
        ? v.daily_visits
        : null;
  const pickRevenue = (v: DongCell): number | null =>
    typeof v.revenue === 'number'
      ? v.revenue
      : typeof v.daily_revenue === 'number'
        ? v.daily_revenue
        : null;
  let dong_totals: AbmPdfData['dong_totals'] = [];
  if (Array.isArray(dongTotalsRaw)) {
    dong_totals = dongTotalsRaw
      .map((d) => {
        const visits = pickVisits(d);
        const revenue = pickRevenue(d);
        if (visits == null || revenue == null) return null;
        return {
          dong: d.dong ?? d.dong_name ?? '—',
          daily_visits: visits,
          daily_revenue: revenue,
          store_count: typeof d.store_count === 'number' ? d.store_count : null,
          avg_revenue: typeof d.avg_revenue === 'number' ? d.avg_revenue : null,
        };
      })
      .filter((d): d is NonNullable<typeof d> => d != null);
  } else if (dongTotalsRaw && typeof dongTotalsRaw === 'object') {
    dong_totals = Object.entries(dongTotalsRaw)
      .map(([k, v]) => {
        const visits = pickVisits(v);
        const revenue = pickRevenue(v);
        if (visits == null || revenue == null) return null;
        return {
          dong: k,
          daily_visits: visits,
          daily_revenue: revenue,
          store_count: typeof v.store_count === 'number' ? v.store_count : null,
          avg_revenue: typeof v.avg_revenue === 'number' ? v.avg_revenue : null,
        };
      })
      .filter((d): d is NonNullable<typeof d> => d != null);
  }
  // winner = 매출 1위
  const dong_winner =
    dong_totals.length > 0
      ? [...dong_totals].sort((a, b) => b.daily_revenue - a.daily_revenue)[0].dong
      : null;

  // 동별 시간대 매트릭스 — backend dong_hour_matrix 또는 비슷한 키
  const dongHourRaw =
    (r.dong_hour_matrix as Array<{ dong?: string; hours?: number[] }> | undefined) ??
    (summary.dong_hour_matrix as Array<{ dong?: string; hours?: number[] }> | undefined) ??
    null;
  const dong_hour_matrix = Array.isArray(dongHourRaw)
    ? dongHourRaw
        .filter((d): d is { dong: string; hours: number[] } => Array.isArray(d.hours))
        .map((d) => ({
          dong: d.dong ?? '—',
          hours: d.hours.slice(0, 24).map((v) => (typeof v === 'number' ? v : 0)),
        }))
    : null;

  // dong_commentary — narrator 가 동별로 코멘트 주는지 시도
  const dongCommentRaw =
    (r.dong_commentary as Array<{ dong?: string; comment?: string }> | undefined) ??
    (summary.dong_commentary as Array<{ dong?: string; comment?: string }> | undefined) ??
    null;
  const dong_commentary = Array.isArray(dongCommentRaw)
    ? dongCommentRaw
        .filter(
          (d): d is { dong: string; comment: string } =>
            typeof d.dong === 'string' && typeof d.comment === 'string',
        )
        .map((d) => ({ dong: d.dong, comment: d.comment }))
    : [];

  const scenarioRaw = r.scenario as
    | {
        weather_override?: string;
        weekend_force?: boolean;
        rent_shock_pct?: number;
        store_area_m2?: number;
        baseline_visits?: number;
        baseline_revenue?: number;
        visits_delta_pct?: number;
        revenue_delta_pct?: number;
        narrator_summary?: string;
        sensitivity?: Array<{ variable?: string; impact_pct?: number }>;
      }
    | null
    | undefined;
  const scenario = scenarioRaw
    ? {
        weather_override: scenarioRaw.weather_override ?? null,
        weekend_force:
          typeof scenarioRaw.weekend_force === 'boolean' ? scenarioRaw.weekend_force : null,
        rent_shock_pct:
          typeof scenarioRaw.rent_shock_pct === 'number' ? scenarioRaw.rent_shock_pct : null,
        store_area_m2:
          typeof scenarioRaw.store_area_m2 === 'number' ? scenarioRaw.store_area_m2 : null,
        baseline_visits:
          typeof scenarioRaw.baseline_visits === 'number' ? scenarioRaw.baseline_visits : null,
        baseline_revenue:
          typeof scenarioRaw.baseline_revenue === 'number' ? scenarioRaw.baseline_revenue : null,
        visits_delta_pct:
          typeof scenarioRaw.visits_delta_pct === 'number' ? scenarioRaw.visits_delta_pct : null,
        revenue_delta_pct:
          typeof scenarioRaw.revenue_delta_pct === 'number' ? scenarioRaw.revenue_delta_pct : null,
        narrator_summary: scenarioRaw.narrator_summary ?? null,
        sensitivity: Array.isArray(scenarioRaw.sensitivity)
          ? scenarioRaw.sensitivity
              .filter(
                (s): s is { variable: string; impact_pct: number } =>
                  typeof s.variable === 'string' && typeof s.impact_pct === 'number',
              )
              .map((s) => ({ variable: s.variable, impact_pct: s.impact_pct }))
          : [],
      }
    : null;

  // ABM 은 brand 기준 — districtFull 은 brandName 으로 대체 가능
  const districtFull = brandName ? `${brandName} ABM 시뮬` : 'ABM 시뮬';

  return {
    mode: 'abm',
    districtFull,
    reportDate: todayStamp(),
    savedHistoryId,
    abm: {
      kpis,
      peak_hours,
      hourly_visits,
      sim_meta,
      cannibalization,
      dong_totals,
      dong_winner,
      dong_hour_matrix,
      dong_commentary,
      scenario,
    },
  };
}

/* ═══════════════════════════════════════════════════════
   LEGACY BUILDER (호환 유지)
   ═══════════════════════════════════════════════════════ */
interface LegacyPdfProps {
  districtFull: string;
  stats: { title: string; value: string; trend: string }[];
  cannibalizationRows: CannRow[];
  neighborhoodRows: NeighborhoodRow[];
  insights: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  reportDate: string;
  savedHistoryId: number;
  customerSegment: SimulationOutput['customer_segment'] | null;
}

function buildCannibalizationRows(
  r: Record<string, unknown>,
  businessType?: string | null,
): CannRow[] {
  const ci = r.competitor_intel as
    | { competition_500m?: { samples?: Array<{ place_name?: string; distance_m?: number }> } }
    | null
    | undefined;
  const samples = Array.isArray(ci?.competition_500m?.samples)
    ? ci!.competition_500m!.samples!
    : [];
  if (samples.length === 0) return [];
  const industry = industryKeyFrom(businessType);
  const baseRate = INDUSTRY_BASE[industry] ?? 0.2;

  return samples.slice(0, 12).map((s) => {
    const dist = typeof s?.distance_m === 'number' ? s.distance_m : 0;
    const impactPct = -baseRate * Math.pow(0.813, dist / 1000) * 100;
    const status = dist < 300 ? 'Danger' : dist < 800 ? 'Caution' : 'Safe';
    return {
      name: String(s?.place_name ?? '경쟁업체'),
      distance: formatDistance(dist),
      impact: `${impactPct.toFixed(1)}%`,
      status,
    };
  });
}

function buildNeighborhoodRows(r: Record<string, unknown>): NeighborhoodRow[] {
  const rankings = Array.isArray(r.district_rankings)
    ? (r.district_rankings as Array<{
        district?: string;
        score?: number;
        closure_rate?: number;
        bep_quarters?: number;
      }>)
    : [];
  return rankings.slice(0, 16).map((row) => ({
    name: String(row?.district ?? '-'),
    score: typeof row?.score === 'number' ? String(Math.round(row.score)) : '—',
    closureRate:
      typeof row?.closure_rate === 'number' ? `${Math.round(row.closure_rate * 100)}%` : '—',
    bep: typeof row?.bep_quarters === 'number' ? `${row.bep_quarters}분기` : '—',
  }));
}

function buildInsights(
  r: Record<string, unknown>,
): { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[] {
  const out: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[] =
    [];

  const legalRisks = Array.isArray(r.legal_risks)
    ? (r.legal_risks as Array<{
        risk_level?: string;
        type?: string;
        detail?: string;
        recommendation?: string;
      }>)
    : [];
  const highRisks = legalRisks.filter(
    (x) => String(x?.risk_level ?? '').toUpperCase() === 'HIGH' || x?.risk_level === 'danger',
  );
  if (highRisks.length > 0) {
    out.push({
      severity: 'critical',
      title: `법률 리스크 HIGH ${highRisks.length}건 확인 필요`,
      desc:
        highRisks
          .slice(0, 2)
          .map((x) => `${x?.type ?? '항목'}: ${x?.detail ?? x?.recommendation ?? ''}`)
          .join(' · ') || '가맹사업법·임대차보호법 관련 조항을 재검토하세요.',
    });
  }

  const shapResult = r.shap_result as { feature_importance?: ShapFeatureItem[] } | null | undefined;
  const shap = Array.isArray(shapResult?.feature_importance) ? shapResult!.feature_importance! : [];
  const topPositive = shap.find((f) => (f?.shap_value ?? 0) > 0);
  if (topPositive) {
    out.push({
      severity: 'opportunity',
      title: `매출 기여 Top 요인: ${topPositive.feature_ko ?? topPositive.feature}`,
      desc: `SHAP +${Math.round(topPositive.shap_value).toLocaleString('ko-KR')}원. 해당 요인의 영향력이 평균보다 높아 핵심 강점으로 작용합니다.`,
    });
  }
  const topNegative = shap.find((f) => (f?.shap_value ?? 0) < 0);
  if (topNegative) {
    out.push({
      severity: 'advisory',
      title: `매출 저해 요인: ${topNegative.feature_ko ?? topNegative.feature}`,
      desc: `SHAP ${Math.round(topNegative.shap_value).toLocaleString('ko-KR')}원. 보완 전략 또는 입지 조정 검토 권장.`,
    });
  }

  const ci = r.competitor_intel as { market_entry_signal?: string } | null | undefined;
  const signal = ci?.market_entry_signal;
  if (signal === 'red') {
    out.push({
      severity: 'critical',
      title: '진입 신호 RED — 경쟁 포화 상태',
      desc: '500m 반경 경쟁 밀도가 임계치 초과. 입지 재선정 또는 차별화 전략이 필요합니다.',
    });
  } else if (signal === 'green') {
    out.push({
      severity: 'opportunity',
      title: '진입 신호 GREEN — 경쟁 공백',
      desc: '반경 내 포화 징후 없음. 선점 효과를 기대할 수 있습니다.',
    });
  }

  return out;
}

/**
 * @deprecated 2026-05-09 — 신규 코드는 buildForeseePdfProps / buildAiPdfProps
 *   를 사용. 이 함수는 legacy `/dashboard/history/:id` 라우트 호환을 위해 유지.
 */
export function buildPdfPropsFromSimulation(input: BuilderInput): LegacyPdfProps {
  const { simResult, businessType, savedHistoryId } = input;
  const r = simResult as unknown as Record<string, unknown>;

  const districtFull = districtFullFrom(simResult);

  const qp = Array.isArray(r.quarterly_projection)
    ? (r.quarterly_projection as Array<{ revenue?: number }>)
    : [];
  const q1Rev = qp[0]?.revenue;
  const monthly = typeof q1Rev === 'number' ? Math.round(q1Rev / 3) : null;
  const growthTrend = (() => {
    if (qp.length < 2) return '';
    const a = qp[0]?.revenue ?? 0;
    const b = qp[1]?.revenue ?? 0;
    if (!a) return '';
    const g = ((b - a) / a) * 100;
    return `${g >= 0 ? '+' : ''}${g.toFixed(1)}% (Q2/Q1)`;
  })();

  const ci = r.competitor_intel as
    | {
        cannibalization?: { estimated_revenue_impact_pct?: number };
        market_entry_signal?: string;
      }
    | null
    | undefined;
  const cannImpact = ci?.cannibalization?.estimated_revenue_impact_pct;
  const cannSig = ci?.market_entry_signal;

  const market = r.market_report as { floating_population?: number } | null | undefined;
  const floatingPop = market?.floating_population;

  const stats = [
    {
      title: '예상 월 매출 (추정)',
      value: formatWon(monthly),
      trend: growthTrend,
    },
    {
      title: '유동인구 점수',
      value: typeof floatingPop === 'number' ? `${Math.round(floatingPop)} / 100` : '—',
      trend: '',
    },
    {
      title: '카니발리제이션 영향',
      value: typeof cannImpact === 'number' ? `${(cannImpact * 100).toFixed(1)}%` : '—',
      trend: typeof cannSig === 'string' ? cannSig : '',
    },
  ];

  return {
    districtFull,
    stats,
    cannibalizationRows: buildCannibalizationRows(r, businessType),
    neighborhoodRows: buildNeighborhoodRows(r),
    insights: buildInsights(r),
    reportDate: todayStamp(),
    savedHistoryId,
    customerSegment: (r.customer_segment as CustomerSegment | null | undefined) ?? null,
  };
}
