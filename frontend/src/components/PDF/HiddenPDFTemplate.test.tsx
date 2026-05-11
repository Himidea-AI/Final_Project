/**
 * HiddenPDFTemplate mount tests — 각 mode 별 dummy data 로 render 성공 검증.
 *
 * jsPDF/html2canvas 는 실제로 호출하지 않고, React render 가 throw 없이
 * 끝나는지 + 핵심 텍스트가 렌더되는지만 확인.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { createRef } from 'react';
import { HiddenPDFTemplate } from './HiddenPDFTemplate';
import type { AbmPdfData, AiPdfData, ForeseePdfData } from '../../utils/pdfPropsBuilder';

describe('HiddenPDFTemplate', () => {
  it('renders foresee mode with full data', () => {
    const foresee: ForeseePdfData = {
      predicted_monthly_revenue: 12_000_000,
      quarterly_projection: [
        { quarter: 1, revenue: 36_000_000 },
        { quarter: 2, revenue: 38_000_000 },
        { quarter: 3, revenue: 40_000_000 },
        { quarter: 4, revenue: 42_000_000 },
      ],
      scenarios: { optimistic: 45_000_000, base: 36_000_000, pessimistic: 28_000_000 },
      scenarios_quarterly: {
        optimistic: [45_000_000, 47_000_000, 49_000_000, 51_000_000],
        base: [36_000_000, 38_000_000, 40_000_000, 42_000_000],
        pessimistic: [28_000_000, 29_000_000, 30_000_000, 31_000_000],
      },
      quarterly_kpi: [
        { quarter: 1, revenue: 36_000_000, visits: null, avg_ticket: null, yoy_pct: null },
        { quarter: 2, revenue: 38_000_000, visits: null, avg_ticket: null, yoy_pct: 5.6 },
        { quarter: 3, revenue: 40_000_000, visits: null, avg_ticket: null, yoy_pct: 5.3 },
        { quarter: 4, revenue: 42_000_000, visits: null, avg_ticket: null, yoy_pct: 5.0 },
      ],
      closure_risk_score: 0.18,
      closure_risk_level: 'caution',
      closure_top_signal: '경쟁밀도',
      closure_rate_recent: 0.045,
      closure_monthly: [
        0.04, 0.045, 0.05, 0.045, 0.04, 0.038, 0.035, 0.04, 0.045, 0.05, 0.05, 0.045,
      ],
      closure_top_features: [
        { feature: '경쟁밀도', contribution: 0.32 },
        { feature: '유동인구 변동', contribution: -0.21 },
        { feature: '임대료 상승', contribution: 0.18 },
      ],
      closure_benchmark: {
        self_pct: 0.045,
        dong_avg_pct: 0.05,
        gu_avg_pct: 0.055,
      },
      customer_segment: {
        segment_ratio: 0.32,
        segment_sales: 5_400_000,
        identified_sales: 12_000_000,
        total_sales_per_store: 36_000_000,
        profile_summary: '20-30대 여성 점심 시간대 핵심 고객',
        dimension_ratios: {
          age_10_ratio: 0.05,
          age_20_ratio: 0.35,
          age_30_ratio: 0.4,
          age_40_ratio: 0.15,
          age_50_ratio: 0.04,
          age_60_above_ratio: 0.01,
        },
      },
      living_pop_quarter: {
        peak_time_zone: 12,
        peak_pop: 8500,
        all_hours: Array.from({ length: 24 }, (_, i) => ({
          time_zone: i,
          predicted_pop: 1000 + Math.abs(12 - i) * -200 + 5000,
        })),
      },
      demographic_extra: {
        core_age: '30대',
        core_gender: '여성',
        weekday_weekend_ratio: 1.2,
        peak_consumption_hours: ['12:00', '19:00'],
        elderly_ratio: 0.12,
        brand_match_score: 78,
        target_alignment_score: 82,
      },
      bep_months: 14,
      margin_rate: 0.18,
      profit_simulation: [
        { quarter: 1, revenue: 36_000_000, cost: 30_000_000, operating_profit: 6_000_000 },
        { quarter: 2, revenue: 38_000_000, cost: 31_000_000, operating_profit: 7_000_000 },
      ],
      cumulative_profit_monthly: [
        2_000_000, 4_000_000, 6_000_000, 8_000_000, 10_000_000, 12_000_000, 14_000_000, 16_000_000,
        18_000_000, 20_000_000, 22_000_000, 24_000_000,
      ],
      cost_breakdown: {
        rent: 4_500_000,
        labor: 7_500_000,
        cogs: 10_500_000,
        marketing: 1_500_000,
      },
      bep_scenarios: { optimistic: 10, base: 14, pessimistic: 20 },
      three_year_roi: { year1: 72_000_000, year2: 144_000_000, year3: 216_000_000 },
      shap_top: [
        {
          rank: 1,
          feature: 'flow_pop',
          feature_ko: '유동인구',
          shap_value: 1_200_000,
          abs_shap: 1_200_000,
          direction: 'positive',
        },
        {
          rank: 2,
          feature: 'rent',
          feature_ko: '임대료',
          shap_value: -800_000,
          abs_shap: 800_000,
          direction: 'negative',
        },
      ],
      shap_secondary: [],
      shap_summary: ['유동인구가 매출에 가장 크게 기여합니다.'],
      model_meta: {
        train_period: '2019Q1 - 2024Q4',
        sample_size: 24,
        rmse: null,
        region: '서울 마포구',
      },
    };

    const ref = createRef<HTMLDivElement>();
    const { getByText, getAllByText, container } = render(
      <HiddenPDFTemplate
        ref={ref}
        mode="foresee"
        districtFull="마포구 서교동"
        reportDate="2026.05.09"
        savedHistoryId={142}
        foresee={foresee}
      />,
    );
    // '마포구 서교동' 은 표지 h1 + 각 페이지 헤더에서 여러 번 등장 — getAllByText 사용.
    expect(getAllByText(/마포구 서교동/).length).toBeGreaterThan(0);
    expect(getByText('01. 매출 예측')).toBeInTheDocument();
    expect(getByText('05. SHAP 기여도 분석')).toBeInTheDocument();
    expect(container.querySelectorAll('.w-\\[794px\\]').length).toBeGreaterThan(1);
  });

  it('renders foresee mode gracefully with minimal data (page skipping)', () => {
    const foresee: ForeseePdfData = {
      predicted_monthly_revenue: null,
      quarterly_projection: [],
      scenarios: null,
      scenarios_quarterly: null,
      quarterly_kpi: [],
      closure_risk_score: null,
      closure_risk_level: null,
      closure_top_signal: null,
      closure_rate_recent: null,
      closure_monthly: [],
      closure_top_features: [],
      closure_benchmark: null,
      customer_segment: null,
      living_pop_quarter: null,
      demographic_extra: null,
      bep_months: null,
      margin_rate: null,
      profit_simulation: [],
      cumulative_profit_monthly: [],
      cost_breakdown: null,
      bep_scenarios: null,
      three_year_roi: null,
      shap_top: [],
      shap_secondary: [],
      shap_summary: [],
      model_meta: null,
    };
    const { getAllByText } = render(
      <HiddenPDFTemplate
        ref={createRef<HTMLDivElement>()}
        mode="foresee"
        districtFull="마포구 합정동"
        reportDate="2026.05.09"
        savedHistoryId={null}
        foresee={foresee}
      />,
    );
    // 표지만 남음
    expect(getAllByText(/마포구 합정동/).length).toBeGreaterThan(0);
  });

  it('renders ai mode with full data', () => {
    const ai: AiPdfData = {
      winner_district: '서교동',
      ai_verdict_summary: '서교동은 진입 양호',
      market_entry_signal: 'green',
      overall_legal_risk: 'caution',
      top_3_candidates: [
        { district: '서교동', score: '85', summary: '진입 양호' },
        { district: '합정동', score: '78', summary: '폐업률 낮음' },
        { district: '망원동', score: '72', summary: '주거 인구 증가' },
      ],
      analysis_meta: {
        agent_count: 7,
        data_sources: ['서울 열린데이터광장', 'FTC 가맹사업정보'],
        generated_at: '2026.05.09',
      },
      district_rankings: [
        {
          rank: 1,
          district: '서교동',
          score: '85',
          closure_rate: '4.5%',
          bep: '12분기',
          sales_growth: '8.2%',
          zoning_risk: 'safe',
          differentiation: null,
          commentary: null,
        },
        {
          rank: 2,
          district: '합정동',
          score: '78',
          closure_rate: '5.0%',
          bep: '14분기',
          sales_growth: '5.1%',
          zoning_risk: 'caution',
          differentiation: null,
          commentary: null,
        },
      ],
      legal_risks: [
        {
          type: '가맹사업법',
          risk_level: 'HIGH',
          detail: '제12조의4 영업구역 침해 가능성 검토 필요',
          recommendation: '본사와 영업지역 재협상',
          article_ref: '제12조의4',
        },
        {
          type: '식품위생법',
          risk_level: 'LOW',
          detail: '특이사항 없음',
          recommendation: null,
          article_ref: null,
        },
      ],
      spot_evaluations: [
        {
          rank_label: '1등',
          dong_name: '서교동',
          level: 'caution',
          summary: '500m 내 동일 브랜드 1개',
          closest_m: 420,
        },
        {
          rank_label: '2등',
          dong_name: '합정동',
          level: 'safe',
          summary: '동일 브랜드 없음',
          closest_m: null,
        },
      ],
      trend_forecast: {
        direction: 'growth',
        narrative: '카페 산업 성장세 지속',
        score: 75,
        yoy_change_pct: 8.2,
        industry: '커피',
        samples: [60, 62, 65, 68, 70, 72, 73, 74, 75, 76, 77, 78],
        horizon_months: 12,
      },
      competitor_intel: {
        market_entry_signal: 'green',
        competition_count: 12,
        saturation_level: 'medium',
        cannibalization_pct: -0.05,
        differentiation_position: '프리미엄',
        recommended_actions: ['유동인구 시간대 광고', '매장 차별화'],
        top_competitors: [
          {
            place_name: '스타벅스 서교점',
            brand_name: '스타벅스',
            distance_text: '120m',
            category: '커피전문점',
          },
        ],
      },
      demographic_report: {
        core_age: '30대',
        core_gender: '여성',
        brand_match_score: 78,
        top_age_groups: [
          { age_group: '20대', share: 0.35 },
          { age_group: '30대', share: 0.4 },
          { age_group: '40대', share: 0.15 },
        ],
        narrative: '30대 여성이 핵심 고객층',
        resident_visitor_ratio: 0.6,
        weekday_weekend_ratio: 1.2,
        elderly_ratio: 0.12,
        area_income_level: 'mid',
        population_trend: 'growing',
        peak_consumption_hours: ['12:00', '19:00'],
      },
      agent_attributions: [
        {
          display_name: 'Market Analyst',
          kind: 'LLM',
          verdict: '진입 양호',
          reasoning: '경쟁 밀도 적정',
          confidence: 'high',
          key_finding: '500m 반경 경쟁 12개',
        },
      ],
    };

    const { getByText, container } = render(
      <HiddenPDFTemplate
        ref={createRef<HTMLDivElement>()}
        mode="ai"
        districtFull="마포구 서교동"
        reportDate="2026.05.09"
        savedHistoryId={143}
        ai={ai}
      />,
    );
    expect(container.textContent).toContain('AI 분석 결과');
    expect(getByText('01. AI 종합 판단')).toBeInTheDocument();
    expect(getByText('02. Top 4 동 랭킹')).toBeInTheDocument();
    expect(getByText('03. 법률 14 specialist')).toBeInTheDocument();
  });

  it('renders abm mode with full data', () => {
    const abm: AbmPdfData = {
      kpis: [
        { title: 'AGENTS', value: '1000명', accent: '#002cd1' },
        { title: '시뮬 일수', value: '30일' },
        { title: '일평균 방문', value: '850명', accent: '#002cd1' },
        { title: '일평균 매출', value: '₩4,500,000', accent: '#059669' },
        { title: '피크 시간', value: '3개' },
        { title: '예상 비용', value: '$0.70' },
      ],
      peak_hours: [12, 13, 19],
      hourly_visits: Array.from({ length: 24 }, (_, i) => 20 + Math.abs(12 - i) * -2 + 30),
      sim_meta: {
        n_agents: 1000,
        days: 30,
        tier_s: 100,
        tier_a: 300,
        tier_b: 600,
        daily_visits: 850,
        daily_visits_std: 50,
        monthly_revenue_estimate: 135_000_000,
        estimated_cost_usd: 0.7,
        role_distribution: [
          { role: 'resident', count: 600 },
          { role: 'commuter', count: 250 },
          { role: 'visitor', count: 150 },
        ],
      },
      cannibalization: {
        estimated_impact_pct: -0.08,
        affected_stores: [
          {
            name: '메가커피 합정점',
            dong: '합정동',
            distance_text: '450m',
            distance_m: 450,
            impact_pct: -0.05,
          },
        ],
        primary_zone_count: 1,
        secondary_zone_count: 0,
      },
      dong_totals: [
        {
          dong: '서교동',
          daily_visits: 850,
          daily_revenue: 4_500_000,
          store_count: 12,
          avg_revenue: 5_300,
        },
        {
          dong: '합정동',
          daily_visits: 720,
          daily_revenue: 3_800_000,
          store_count: 10,
          avg_revenue: 5_280,
        },
      ],
      dong_winner: '서교동',
      dong_hour_matrix: null,
      dong_commentary: [{ dong: '서교동', comment: '점심 시간대 방문 집중' }],
      scenario: {
        weather_override: '맑음',
        weekend_force: false,
        rent_shock_pct: 0.1,
        store_area_m2: 50,
        baseline_visits: 850,
        baseline_revenue: 4_500_000,
        visits_delta_pct: -0.05,
        revenue_delta_pct: -0.12,
        narrator_summary: '임대료 10% 상승 시 영업이익 12% 감소.',
        sensitivity: [
          { variable: '임대료', impact_pct: -0.12 },
          { variable: '주말 강제', impact_pct: 0.08 },
        ],
      },
    };

    const { getByText, container } = render(
      <HiddenPDFTemplate
        ref={createRef<HTMLDivElement>()}
        mode="abm"
        districtFull="메가커피 ABM 시뮬"
        reportDate="2026.05.09"
        savedHistoryId={144}
        abm={abm}
      />,
    );
    expect(container.textContent).toContain('ABM 시뮬 결과');
    expect(getByText('01. 시뮬 KPI')).toBeInTheDocument();
    expect(getByText('02. 시장 자기잠식')).toBeInTheDocument();
    expect(getByText('03. 동별 비교')).toBeInTheDocument();
    expect(getByText('04. 시나리오 충격')).toBeInTheDocument();
  });

  it('renders legacy mode (backward-compat)', () => {
    const { getByText } = render(
      <HiddenPDFTemplate
        ref={createRef<HTMLDivElement>()}
        mode="legacy"
        districtFull="마포구 서교동"
        reportDate="2026.05.09"
        savedHistoryId={1}
        stats={[{ title: '월 매출', value: '₩12,000,000', trend: '+10%' }]}
        cannibalizationRows={[]}
        neighborhoodRows={[]}
        insights={[]}
        customerSegment={null}
      />,
    );
    expect(getByText('01. 상권 종합 요약')).toBeInTheDocument();
  });
});
