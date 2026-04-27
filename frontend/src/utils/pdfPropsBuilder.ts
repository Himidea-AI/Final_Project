/**
 * pdfPropsBuilder — 저장된 SimulationOutput에서 HiddenPDFTemplateProps 조립.
 *
 * App.tsx의 라이브 simResult(camelCase 변환본)와 달리 saved는 snake_case
 * JSONB 그대로. 동일한 PDF 품질을 재현하기 위해 여기서 변환.
 */

import type { SimulationOutput } from '../types';
import type { CannRow, NeighborhoodRow } from '../App';

interface BuilderInput {
  simResult: SimulationOutput;
  businessType?: string | null;
  savedHistoryId: number;
}

interface PdfProps {
  districtFull: string;
  stats: { title: string; value: string; trend: string }[];
  cannibalizationRows: CannRow[];
  neighborhoodRows: NeighborhoodRow[];
  insights: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[];
  reportDate: string;
  savedHistoryId: number;
  customerSegment: SimulationOutput['customer_segment'] | null;
}

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

function buildCannibalizationRows(r: any, businessType?: string | null): CannRow[] {
  const samples = Array.isArray(r?.competitor_intel?.competition_500m?.samples)
    ? r.competitor_intel.competition_500m.samples
    : [];
  if (samples.length === 0) return [];
  const industry = industryKeyFrom(businessType);
  const baseRate = INDUSTRY_BASE[industry] ?? 0.2;

  return samples.slice(0, 12).map((s: any) => {
    const dist = typeof s?.distance_m === 'number' ? s.distance_m : 0;
    const impactPct = -baseRate * Math.pow(0.813, dist / 1000) * 100;
    const status = dist < 300 ? 'Danger' : dist < 800 ? 'Caution' : 'Safe';
    return {
      name: String(s?.place_name ?? '경쟁업체'),
      distance: dist >= 1000 ? `${(dist / 1000).toFixed(1)}km` : `${Math.round(dist)}m`,
      impact: `${impactPct.toFixed(1)}%`,
      status,
    };
  });
}

function buildNeighborhoodRows(r: any): NeighborhoodRow[] {
  const rankings = Array.isArray(r?.district_rankings) ? r.district_rankings : [];
  return rankings.slice(0, 16).map((row: any) => ({
    name: String(row?.district ?? '-'),
    score: typeof row?.score === 'number' ? String(Math.round(row.score)) : '—',
    closureRate:
      typeof row?.closure_rate === 'number' ? `${Math.round(row.closure_rate * 100)}%` : '—',
    bep: typeof row?.bep_quarters === 'number' ? `${row.bep_quarters}분기` : '—',
  }));
}

function buildInsights(
  r: any,
): { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[] {
  const out: { severity: 'critical' | 'advisory' | 'opportunity'; title: string; desc: string }[] =
    [];

  const legalRisks: any[] = Array.isArray(r?.legal_risks) ? r.legal_risks : [];
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

  const shap: any[] = Array.isArray(r?.shap_result?.feature_importance)
    ? r.shap_result.feature_importance
    : [];
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

  const ci: any = r?.competitor_intel ?? null;
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

export function buildPdfPropsFromSimulation(input: BuilderInput): PdfProps {
  const { simResult, businessType, savedHistoryId } = input;
  const r = simResult as any;

  const winner = r?.winner_district || r?.target_district || '—';
  const districtFull = `마포구 ${winner}`;

  const qp = Array.isArray(r?.quarterly_projection) ? r.quarterly_projection : [];
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

  const ci = r?.competitor_intel ?? null;
  const cannImpact = ci?.cannibalization?.estimated_revenue_impact_pct;
  const cannSig = ci?.market_entry_signal;

  const synthAttr = Array.isArray(r?.agent_attributions)
    ? r.agent_attributions.find((a: any) => a?.id === 'synthesis')
    : null;
  const overallScore =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;

  const floatingPop = r?.market_report?.floating_population;

  const stats = [
    {
      title: '예상 월 매출 (추정)',
      value: formatWon(monthly),
      trend: growthTrend,
    },
    {
      title: '상권 종합 매력도',
      value: overallScore != null ? `${overallScore} / 100` : '—',
      trend: '',
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

  const today = new Date();
  const reportDate = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(
    today.getDate(),
  ).padStart(2, '0')}`;

  return {
    districtFull,
    stats,
    cannibalizationRows: buildCannibalizationRows(r, businessType),
    neighborhoodRows: buildNeighborhoodRows(r),
    insights: buildInsights(r),
    reportDate,
    savedHistoryId,
    customerSegment: r?.customer_segment ?? null,
  };
}
