/**
 * SummaryTab — 요약 탭 (탭 재구조화 후 경량)
 *
 * 구성:
 * 1) 상단: EntrySignalLight Hero
 * 2) DecisionCard 3 (창업 판단 / 매출 / BEP)
 *
 * 이관됨:
 *   - 수익성 상세 → FinancialTab
 *   - 인구 구성 / 인구 심층 리포트 → DemographicTab
 *   - 탭이 분리된 후 요약은 "의사결정 요약"에만 집중.
 */

import {
  BarChart3,
  BrainCircuit,
  Users,
  PieChart,
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  Layers,
} from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import { DecisionCard } from '../shared/DecisionCard';
import type { DetailModalContent } from '../shared/DetailModal';
import { formatKrw, formatPct, quarterlyToMonthly } from '../utils/formatters';
import { computeDecision, DECISION_COPY } from '../../../../constants/decisionThresholds';
import { EntrySignalLight } from '../charts/EntrySignalLight';

interface Props {
  simResult: SimulationOutput;
  /** DecisionCard의 "근거" footer 클릭 시 상세 모달 오픈 (없으면 footer 비활성) */
  openModal?: (content: DetailModalContent) => void;
}

// 에이전트 아이콘 공용 (DecisionCard footer용) — borderCls는 시인성용 고유 색 테두리
const AGENT_ICON = {
  market: { icon: BarChart3, color: 'text-blue-400', borderCls: 'border-blue-500/50' },
  population: { icon: Users, color: 'text-emerald-400', borderCls: 'border-emerald-500/50' },
  demographic: { icon: PieChart, color: 'text-indigo-400', borderCls: 'border-indigo-500/50' },
  competitor: { icon: ShieldAlert, color: 'text-amber-400', borderCls: 'border-amber-500/50' },
  legal: { icon: AlertTriangle, color: 'text-rose-400', borderCls: 'border-rose-500/50' },
  trend: { icon: TrendingUp, color: 'text-cyan-400', borderCls: 'border-cyan-500/50' },
  ranking: { icon: Layers, color: 'text-violet-400', borderCls: 'border-violet-500/50' },
  synthesis: { icon: BrainCircuit, color: 'text-white', borderCls: 'border-stone-300/60' },
};

export function SummaryTab({ simResult, openModal }: Props) {
  const fr = simResult.final_report ?? null;
  const ps = fr?.profit_simulation ?? null;
  const ci = simResult.competitor_intel as Record<string, any> | null | undefined;
  const demo = simResult.demographic_report ?? null;
  const qp = simResult.quarterly_projection ?? [];
  const firstQ = qp[0];

  // ── 공통 값 ──
  const netProfit = ps?.net_profit ?? null;
  const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
  const monthlyCost = ps?.monthly_cost ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const margin = ps?.margin_rate ?? null;

  // ── DecisionCard 1: 창업 가능성 ──
  const legalRaw = simResult.overall_legal_risk ?? 'safe';
  const entryRaw = (ci?.market_entry_signal as string | undefined) ?? 'green';
  const verdict = computeDecision(legalRaw, entryRaw);
  const verdictCopy = DECISION_COPY[verdict];
  const matchScore = demo?.brand_target_match_score;
  const compCount = ci?.competition_500m?.count as number | undefined;
  const vacancyApplied = Boolean(simResult.vacancy_applied);

  // ── DecisionCard 2: 매출 전망 ──
  const annualRevenue = qp.reduce((sum, q) => sum + (q.revenue ?? 0), 0);
  const annualLower = qp.reduce((sum, q) => sum + (q.confidence_lower ?? 0), 0);
  const annualUpper = qp.reduce((sum, q) => sum + (q.confidence_upper ?? 0), 0);
  const hasQp = qp.length > 0;

  // ── DecisionCard 3: BEP ──
  const bepStatus: 'emerald' | 'amber' | 'rose' =
    bepMonths == null ? 'amber' : bepMonths <= 12 ? 'emerald' : bepMonths <= 18 ? 'amber' : 'rose';

  // ── Hero Entry Signal ──
  const entrySignal = (ci?.market_entry_signal as 'green' | 'yellow' | 'red' | undefined) ?? null;

  // ── DecisionCard footer 클릭 → "근거" 설명 모달 ──
  const openDecisionExplainer = openModal
    ? () =>
        openModal({
          title: '이 자리, 창업해도 될까? — 판단 근거',
          content: [
            `종합 판정: ${verdict} (${verdictCopy.label})`,
            `법률 리스크 레벨: ${legalRaw} · 진입 신호: ${entryRaw}`,
            vacancyApplied ? '공실 페널티 반영됨 — 매출 기대치가 하향 조정되었습니다.' : '',
            '',
            '【 판단 로직 】',
            '법률 리스크(safe/caution/danger) × 경쟁 진입 신호(green/yellow/red)의 2D 매트릭스로 GO / HOLD / NOGO 3단계 판정을 도출합니다.',
            '  · 둘 다 양호 → GO',
            '  · 한 쪽이 주의 이상 → HOLD (조건부)',
            '  · 둘 다 위험 → NOGO',
            '',
            '【 기여 에이전트 】',
            '  · synthesis — 8개 에이전트 결과 통합 + LLM 최종 판정',
            '  · legal — 가맹사업법/임대차보호법 RAG 기반 리스크 추출',
            '  · competitor_intel — 500m 반경 포화도 + 카니발리제이션 지수',
          ]
            .filter(Boolean)
            .join('\n'),
        })
    : undefined;

  const openRevenueExplainer = openModal
    ? () =>
        openModal({
          title: '얼마나 벌 수 있을까? — TCN 모델 근거',
          content: [
            hasQp
              ? `연 매출 (P50 기본) ₩${formatKrw(annualRevenue)}\nP10 (비관) ₩${formatKrw(annualLower)} · P90 (낙관) ₩${formatKrw(annualUpper)}`
              : '분기 예측 데이터 준비 중입니다.',
            '',
            '【 예측 방법 】',
            'TCN (Temporal Convolutional Network) v2 모델이 해당 동·업종의 분기별 매출을 4분기 예측합니다. 학습 피처: 유동인구, 임대시세, 경쟁 매장 수, 계절성, 골목상권 밀도.',
            '',
            '【 신뢰 구간 의미 】',
            '  · P10 (비관): 최악 10% 시나리오 — 확률적 하한',
            '  · P50 (기본): 중앙값 — 예상 가능한 가장 가능성 높은 결과',
            '  · P90 (낙관): 최상 10% 시나리오 — 확률적 상한',
            '',
            '【 보정 에이전트 】',
            '  · market_analyst — 상권 8대 지표 정규화',
            '  · trend_forecaster — 네이버 검색량 + 한국은행 기준금리 매크로 보정',
            '  · demographic_depth — 타겟 고객 프로필 매칭도 반영',
            '',
            '※ 현재 P10~P90 연 합산은 단순 sum으로, 분기 간 상관 반영 시 구간이 좁아질 수 있음 (후속 개선 예정).',
          ].join('\n'),
        })
    : undefined;

  const openBepExplainer = openModal
    ? () =>
        openModal({
          title: '언제 본전을 뽑을까? — BEP 계산 근거',
          content: [
            bepMonths != null
              ? `예상 BEP 도달: ${bepMonths.toFixed(1)} 개월`
              : 'BEP 계산 데이터 준비 중입니다.',
            monthlyRev != null ? `월 매출 (추정) ₩${formatKrw(monthlyRev)}` : '',
            monthlyCost != null ? `월 운영비 ₩${formatKrw(monthlyCost)}` : '',
            netProfit != null ? `월 영업이익 ₩${formatKrw(netProfit)}` : '',
            margin != null ? `마진율 ${formatPct(margin)}` : '',
            '',
            '【 BEP 계산식 】',
            'BEP (개월) = 초기 투자금 ÷ 월 영업이익',
            '월 영업이익 = 월 매출 − 월 운영비 (임대료 · 인건비 · 원가 등)',
            '',
            '【 판정 기준 】',
            '  · 12개월 이내 — 우수 (emerald)',
            '  · 12~18개월 — 주의 (amber) · 업종 평균 범위',
            '  · 18개월 초과 — 위험 (rose) · 계약 기간 내 회수 어려움',
            '',
            '【 기여 에이전트 】',
            '  · synthesis — 분기 매출 예측을 월 단위로 환산 + 계절성 가중',
            '  · legal — 프랜차이즈 가맹금/보증금 등 계약상 초기 비용 검증',
          ]
            .filter(Boolean)
            .join('\n'),
        })
    : undefined;

  return (
    <div className="space-y-8">
      {/* ═══ Hero: Market Entry Signal ═══ */}
      <div className="flex justify-end">
        <EntrySignalLight signal={entrySignal} />
      </div>

      {/* ═══ DecisionCard 3 (질문형) ═══ */}
      <div className="grid grid-cols-3 gap-8">
        <DecisionCard
          title="이 자리, 창업해도 될까?"
          heroBadge={`${verdict} · ${verdictCopy.label}`}
          heroColor={verdictCopy.color}
          description={
            fr?.final_recommendation?.slice(0, 200) ??
            simResult.ai_recommendation?.slice(0, 200) ??
            '법률 리스크와 경쟁 진입 신호를 종합한 의사결정 지표입니다.'
          }
          items={[
            {
              text:
                matchScore != null ? `브랜드 적합도 ${Math.round(matchScore)}` : '브랜드 적합도 —',
              highlight: matchScore != null && matchScore >= 70,
            },
            {
              text: compCount != null ? `500m 내 경쟁점 ${compCount}개` : '경쟁점 데이터 없음',
              highlight: compCount != null && compCount >= 10,
            },
            vacancyApplied
              ? { text: '공실 페널티 반영됨', highlight: true }
              : { text: `법률 리스크 ${legalRaw} · 진입 신호 ${entryRaw}`, highlight: false },
          ]}
          footer={{
            agents: [AGENT_ICON.synthesis, AGENT_ICON.legal, AGENT_ICON.competitor].map((a, i) => ({
              id: `syn-${i}`,
              ...a,
            })),
            methodology: 'synthesis + legal + competitor',
          }}
          onFootnoteClick={openDecisionExplainer}
        />

        <DecisionCard
          title="얼마나 벌 수 있을까?"
          heroBadge={hasQp ? `₩${formatKrw(annualRevenue)} · 연 P50` : '—'}
          heroColor="indigo"
          description="TCN 모델 분기 예측 합산 (12개월). P10~P90 신뢰 구간은 계절성을 보존한 분기 단위 정규화 결과입니다."
          items={
            hasQp
              ? [
                  { text: `P10 (비관) ₩${formatKrw(annualLower)}`, highlight: false },
                  { text: `P50 (기본) ₩${formatKrw(annualRevenue)}`, highlight: true },
                  { text: `P90 (낙관) ₩${formatKrw(annualUpper)}`, highlight: false },
                ]
              : [{ text: '분기 예측 데이터 없음', highlight: false }]
          }
          footer={{
            agents: [AGENT_ICON.market, AGENT_ICON.trend, AGENT_ICON.demographic].map((a, i) => ({
              id: `rev-${i}`,
              ...a,
            })),
            methodology: 'TCN + trend + demographic',
          }}
          onFootnoteClick={openRevenueExplainer}
        />

        <DecisionCard
          title="언제 본전을 뽑을까?"
          heroBadge={bepMonths != null ? `${bepMonths.toFixed(1)} 개월` : '—'}
          heroColor={bepStatus}
          description="초기 자본금 기준 회수 기간. 분기 매출 예측치를 월 단위로 환산해 계절성 가중치를 반영했습니다."
          items={[
            {
              text: monthlyRev != null ? `월 매출 ₩${formatKrw(monthlyRev)}` : '월 매출 —',
              highlight: false,
            },
            {
              text: monthlyCost != null ? `월 운영비 ₩${formatKrw(monthlyCost)}` : '월 운영비 —',
              highlight: false,
            },
            {
              text: netProfit != null ? `월 영업이익 ₩${formatKrw(netProfit)}` : '월 영업이익 —',
              highlight: netProfit != null && netProfit > 0,
            },
          ]}
          footer={{
            agents: [AGENT_ICON.synthesis, AGENT_ICON.legal].map((a, i) => ({
              id: `bep-${i}`,
              ...a,
            })),
            methodology: 'TCN + BEP 계산',
          }}
          onFootnoteClick={openBepExplainer}
        />
      </div>
    </div>
  );
}
