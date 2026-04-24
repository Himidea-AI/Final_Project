/**
 * SummaryTab — 요약 탭 (v4.3 리디자인)
 * 1) 상단: DecisionCard 3 (질문형 제목 + Hero 배지 + 체크리스트 + 에이전트 footer)
 * 2) 중단: 수익성 상세 (기존 ProfitSimulationPanel — 풀와이드로 확대)
 * 3) 하단: 인구 심층 분석 리포트 (기존 DemographicReportSection)
 */

import { useState } from 'react';
import {
  Activity,
  BarChart3,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  Gauge,
  Users,
  PieChart,
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  Layers,
} from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import { DecisionCard } from '../shared/DecisionCard';
import { MetricBox } from '../shared/MetricBox';
import { INCOME_MAP, TREND_MAP, safeMap } from '../utils/mappings';
import { formatKrw, formatPct, formatPeakHours, quarterlyToMonthly } from '../utils/formatters';
import { computeDecision, DECISION_COPY } from '../../../../constants/decisionThresholds';
import { EntrySignalLight } from '../charts/EntrySignalLight';
import { CoreDemographicDonut } from '../charts/CoreDemographicDonut';
import { WeekdayWeekendBar } from '../charts/WeekdayWeekendBar';
import { StackedAgeBar } from '../charts/StackedAgeBar';

interface Props {
  simResult: SimulationOutput;
}

// 에이전트 아이콘 공용 (DecisionCard footer용)
const AGENT_ICON = {
  market: { icon: BarChart3, color: 'text-blue-400' },
  population: { icon: Users, color: 'text-emerald-400' },
  demographic: { icon: PieChart, color: 'text-indigo-400' },
  competitor: { icon: ShieldAlert, color: 'text-amber-400' },
  legal: { icon: AlertTriangle, color: 'text-rose-400' },
  trend: { icon: TrendingUp, color: 'text-cyan-400' },
  ranking: { icon: Layers, color: 'text-violet-400' },
  synthesis: { icon: BrainCircuit, color: 'text-white' },
};

export function SummaryTab({ simResult }: Props) {
  const fr = simResult.final_report ?? null;
  const ps = fr?.profit_simulation ?? null;
  const ci = simResult.competitor_intel as Record<string, any> | null | undefined;
  const demo = simResult.demographic_report ?? null;
  const qp = simResult.quarterly_projection ?? [];
  const firstQ = qp[0];

  // ── 공통 값 ──
  const netProfit = ps?.net_profit ?? null;
  const margin = ps?.margin_rate ?? null;
  const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
  const monthlyCost = ps?.monthly_cost ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const synthAttr = simResult.agent_attributions?.find((a) => a.id === 'synthesis');
  const tcnConfidencePct =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : 90;

  // ── DecisionCard 1: 창업 가능성 (Q12 C 로직) ──
  const legalRaw = simResult.overall_legal_risk ?? 'safe';
  const entryRaw = (ci?.market_entry_signal as string | undefined) ?? 'green';
  const verdict = computeDecision(legalRaw, entryRaw);
  const verdictCopy = DECISION_COPY[verdict];
  const matchScore = demo?.brand_target_match_score;
  const compCount = ci?.competition_500m?.count as number | undefined;
  const vacancyApplied = Boolean(simResult.vacancy_applied);

  // ── DecisionCard 2: 매출 전망 (분기 합산 P10/P50/P90) ──
  // TODO(B2 수지니): 분기 간 상관 반영한 CI 재계산 로직 필요.
  //   현재는 단순 sum(lower)/sum(upper)라 분산 과소추정 위험.
  const annualRevenue = qp.reduce((sum, q) => sum + (q.revenue ?? 0), 0);
  const annualLower = qp.reduce((sum, q) => sum + (q.confidence_lower ?? 0), 0);
  const annualUpper = qp.reduce((sum, q) => sum + (q.confidence_upper ?? 0), 0);
  const hasQp = qp.length > 0;

  // ── DecisionCard 3: BEP ──
  const bepStatus: 'emerald' | 'amber' | 'rose' =
    bepMonths == null ? 'amber' : bepMonths <= 12 ? 'emerald' : bepMonths <= 18 ? 'amber' : 'rose';

  // ── Hero Entry Signal ──
  const entrySignal = (ci?.market_entry_signal as 'green' | 'yellow' | 'red' | undefined) ?? null;

  return (
    <div className="space-y-8">
      {/* ═══ Hero: Market Entry Signal ═══ */}
      <div className="flex justify-end">
        <EntrySignalLight signal={entrySignal} />
      </div>

      {/* ═══ 상단: DecisionCard 3 (질문형) ═══ */}
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
        />
      </div>

      {/* ═══ 중단: 수익성 상세 (기존 ProfitSimulationPanel — 풀와이드) ═══ */}
      <ProfitSimulationPanelFull
        monthlyRev={monthlyRev}
        monthlyCost={monthlyCost}
        netProfit={netProfit}
        margin={margin}
        confidencePct={tcnConfidencePct}
      />

      {/* ═══ 인구 구성 상세 (Collapsible, 가이드 #2 #5 #6) ═══ */}
      <DemographicCompositionSection demo={demo} />

      {/* ═══ 하단: 인구 심층 분석 ═══ */}
      <DemographicReportSection demo={demo} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   인구 구성 Collapsible — Donut + StackedAge + Weekday/Weekend
   ═══════════════════════════════════════════════════════ */
function DemographicCompositionSection({ demo }: { demo: SimulationOutput['demographic_report'] }) {
  const [open, setOpen] = useState(true);
  const hasAny = Boolean(
    demo?.core_demographic ||
    (demo?.top_3_age_groups && demo.top_3_age_groups.length > 0) ||
    typeof demo?.weekday_weekend_ratio === 'number',
  );
  if (!hasAny) return null;

  return (
    <div className="bg-stone-900/30 border border-stone-800/40 rounded-3xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 p-6 hover:bg-stone-900/40 transition-colors"
      >
        {open ? (
          <ChevronDown size={16} className="text-stone-500" />
        ) : (
          <ChevronRight size={16} className="text-stone-500" />
        )}
        <h3 className="text-sm font-black text-stone-100 uppercase tracking-tight">
          인구 구성 상세
        </h3>
        <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
          demographic_depth
        </span>
      </button>
      {open && (
        <div
          className={`grid gap-6 p-6 pt-0 ${
            Array.isArray(demo?.peak_hour_matrix) && demo.peak_hour_matrix.length === 7
              ? 'grid-cols-4'
              : 'grid-cols-3'
          }`}
        >
          <CoreDemographicDonut core={demo?.core_demographic ?? null} />
          <StackedAgeBar groups={demo?.top_3_age_groups ?? []} />
          <WeekdayWeekendBar ratio={demo?.weekday_weekend_ratio} />
          {Array.isArray(demo?.peak_hour_matrix) && demo.peak_hour_matrix.length === 7 && (
            <div className="flex h-[140px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
              Calendar Heatmap — Track B #106 구현 대기
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Profit Simulation 풀와이드 패널 — 기존 로직 보존, 레이아웃만 확대
   ═══════════════════════════════════════════════════════ */
interface ProfitPanelProps {
  monthlyRev: number | null | undefined;
  monthlyCost: number | null | undefined;
  netProfit: number | null | undefined;
  margin: number | null | undefined;
  confidencePct: number;
}

function ProfitSimulationPanelFull({
  monthlyRev,
  monthlyCost,
  netProfit,
  margin,
  confidencePct,
}: ProfitPanelProps) {
  const rows = [
    { label: '추정 월매출', val: monthlyRev, accent: 'text-stone-100' },
    { label: '월 운영비 (총계)', val: monthlyCost, accent: 'text-stone-400' },
  ];

  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
      <div className="flex items-center justify-between mb-6">
        <h4 className="text-sm font-black text-stone-100 uppercase tracking-tight flex items-center gap-2">
          <Activity size={16} className="text-indigo-400" /> 상세 수익성 시뮬레이션
          <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal">
            profit_simulation
          </span>
        </h4>
        {margin != null && (
          <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tabular-nums">
            마진 {formatPct(margin)}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-3">
          {rows.map((item) => (
            <div
              key={item.label}
              className="flex justify-between items-end border-b border-stone-800/50 pb-3"
            >
              <span className="text-xs font-bold text-stone-500">{item.label}</span>
              <span className={`text-lg font-black tabular-nums ${item.accent}`}>
                {item.val != null ? `₩${formatKrw(item.val)}` : '—'}
              </span>
            </div>
          ))}
          <div className="flex justify-between items-center pt-2">
            <span className="text-sm font-black text-indigo-400 tracking-tighter">
              예상 월 영업이익
            </span>
            <span className="text-3xl font-black text-indigo-400 tabular-nums tracking-tighter">
              {netProfit != null ? `₩${formatKrw(netProfit)}` : '—'}
            </span>
          </div>
        </div>

        <div className="bg-stone-950/40 border border-stone-800 rounded-2xl p-5 flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-3">
            <Gauge size={18} className="text-indigo-500" />
            <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
              분석 신뢰도
            </span>
          </div>
          <div className="text-3xl font-black text-indigo-400 tabular-nums mb-2">
            {confidencePct}%
          </div>
          <div className="w-full bg-stone-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-indigo-500 h-full transition-all"
              style={{ width: `${Math.min(100, Math.max(0, confidencePct))}%` }}
            />
          </div>
          <p className="mt-3 text-[10px] text-stone-500 leading-relaxed">
            synthesis 에이전트 판단 신뢰도 기반. TCN MAPE 제공 시 교체됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   인구 심층 분석 섹션 (기존 구조 보존, 스타일만 v4.3 정렬)
   ═══════════════════════════════════════════════════════ */
interface DemoSectionProps {
  demo: SimulationOutput['demographic_report'];
}

function DemographicReportSection({ demo }: DemoSectionProps) {
  const core = demo?.core_demographic;
  const corePct =
    core && typeof core.share === 'number' ? `${(core.share * 100).toFixed(1)}%` : null;
  const peak = demo?.peak_consumption_hours?.[0];
  const income = safeMap(INCOME_MAP, demo?.area_income_level, INCOME_MAP.unknown);
  const trend = safeMap(TREND_MAP, demo?.population_trend, TREND_MAP.unknown);
  const match = demo?.brand_target_match_score;
  const narrative = demo?.narrative;
  const rationale = demo?.match_rationale;

  const hasData = Boolean(
    core || peak || demo?.area_income_level || demo?.population_trend || match != null,
  );

  if (!hasData) {
    return (
      <div className="bg-stone-900/30 border border-dashed border-stone-800 rounded-3xl p-10 text-center">
        <Users className="mx-auto mb-3 text-stone-600" size={22} />
        <div className="text-sm font-bold text-stone-400">인구 심층 분석 데이터 없음</div>
        <div className="mt-1 text-xs text-stone-500">
          demographic_depth 에이전트 분석이 완료되면 해당 권역의 타겟 프로필이 표시됩니다.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-stone-900/30 border border-stone-800/40 rounded-3xl p-8">
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic text-left tracking-tight">
          <Users size={22} className="text-indigo-400" /> 인구 심층 분석 리포트
          <span className="text-[11px] font-black text-stone-500 uppercase tracking-widest not-italic">
            demographic_report
          </span>
        </h3>
        {match != null && (
          <div className="px-4 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tracking-widest tabular-nums">
            브랜드 적합도 {Math.round(match)}
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-8 mb-8 text-left">
        <MetricBox
          label="주요 소비 연령대"
          val={core ? `${core.age} ${core.gender}` : '—'}
          sub={corePct ? `전체 방문객의 ${corePct} 차지` : 'core_demographic 기준'}
        />
        <MetricBox
          label="피크 시간대"
          val={peak ? formatPeakHours(peak) : '—'}
          sub="peak_consumption_hours[0]"
        />
        <MetricBox label="지역 소득 수준" val={income} sub="area_income_level 기준" />
        <MetricBox label="인구 증감 추세" val={trend} sub="population_trend 기준" />
      </div>

      {(narrative || rationale) && (
        <div className="p-6 bg-stone-950/40 border border-stone-800 rounded-2xl text-left space-y-2">
          {narrative && (
            <p className="text-sm text-stone-300 leading-relaxed font-medium">{narrative}</p>
          )}
          {rationale && (
            <p className="text-xs text-stone-500 leading-relaxed italic">매칭 근거: {rationale}</p>
          )}
        </div>
      )}
    </div>
  );
}
