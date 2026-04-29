/**
 * PredictFinancialSimTab — 예측·재무 시뮬레이션
 * 2026-04-28 IA 재구조 — FinancialTab 분해.
 * BEP 누적이익 + 과거 12개월 폐업률 + LightGBM/TCN 폐업위험도 + 생존률 KPI.
 */

import { Activity, Gauge } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { formatKrw, formatPct, quarterlyToMonthly } from '../../utils/formatters';
import { BepCumulativeProfitChart } from '../../charts/BepCumulativeProfitChart';
import { SurvivalRateKpi } from '../../charts/SurvivalRateKpi';
import { ClosureRatePanel, ClosureRiskPanel } from '../../tabs/FinancialTab';

interface Props {
  simResult: SimulationOutput;
}

export function PredictFinancialSimTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const firstQ = simResult.quarterly_projection?.[0];
  const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
  const monthlyCost = ps?.monthly_cost ?? null;
  const netProfit = ps?.net_profit ?? null;
  const margin = ps?.margin_rate ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const synthAttr = simResult.agent_attributions?.find((a) => a.id === 'synthesis');
  const confidencePct =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;

  return (
    <div className="space-y-6">
      <ProfitSimulationPanelFull
        monthlyRev={monthlyRev}
        monthlyCost={monthlyCost}
        netProfit={netProfit}
        margin={margin}
        bepMonths={bepMonths}
        confidencePct={confidencePct}
      />

      {(simResult.quarterly_projection ?? []).length > 0 && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
          <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 mb-3">
            투자 회수 곡선
          </h4>
          <BepCumulativeProfitChart data={simResult.quarterly_projection ?? []} />
        </div>
      )}

      <SurvivalRateKpi
        survivalRate={simResult.market_report?.survival_rate}
        closureRate={simResult.market_report?.closure_rate}
      />

      <ClosureRatePanel rate={simResult.closure_rate} />
      <ClosureRiskPanel closure={simResult.closure_risk} />
    </div>
  );
}

interface ProfitPanelProps {
  monthlyRev: number | null | undefined;
  monthlyCost: number | null | undefined;
  netProfit: number | null | undefined;
  margin: number | null | undefined;
  bepMonths: number | null | undefined;
  confidencePct: number | null;
}

function ProfitSimulationPanelFull({
  monthlyRev,
  monthlyCost,
  netProfit,
  margin,
  bepMonths,
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
        </h4>
        <div className="flex items-center gap-2">
          {margin != null && (
            <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[0.6875rem] font-black text-indigo-400 tabular-nums">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepMonths != null && (
            <div className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full text-[0.6875rem] font-black text-cyan-400 tabular-nums">
              BEP {bepMonths.toFixed(1)}개월
            </div>
          )}
        </div>
      </div>

      {bepMonths != null && (
        <p className="mb-4 text-[0.625rem] text-stone-500 leading-relaxed">
          ※ 인건비 미포함 기준입니다. 실제 BEP는 운영 인원에 따라 길어질 수 있습니다.
        </p>
      )}

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
            <span className="text-[0.625rem] font-black text-stone-500 uppercase tracking-widest">
              분석 신뢰도
            </span>
          </div>
          {confidencePct != null ? (
            <>
              <div className="text-3xl font-black text-indigo-400 tabular-nums mb-2">
                {confidencePct}%
              </div>
              <div className="w-full bg-stone-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, confidencePct))}%` }}
                />
              </div>
            </>
          ) : (
            <div className="text-2xl font-black text-stone-500 tabular-nums">—</div>
          )}
        </div>
      </div>
    </div>
  );
}
