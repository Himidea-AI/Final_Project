/**
 * PredictFinancialSimTab — 예측·재무 시뮬레이션
 * 2026-04-28 IA 재구조 — FinancialTab 분해.
 * BEP 누적이익 + 과거 12개월 폐업률 + LightGBM/TCN 폐업위험도 + 생존률 KPI.
 */

import { Activity } from 'lucide-react';
import type { ClosureRate, ClosureRisk, SimulationOutput } from '../../../../../types';
import { formatKrw, formatPct, quarterlyToMonthly } from '../../utils/formatters';
import { BepCumulativeProfitChart } from '../../charts/BepCumulativeProfitChart';
import { SurvivalRateKpi } from '../../charts/SurvivalRateKpi';
import { ClosureRatePanel } from '../../charts/ClosureRatePanel';
import { ClosureRiskPanel } from '../../charts/ClosureRiskPanel';

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

  // M6 (2026-04-29): district_predictions 기반 멀티 동 시리즈.
  // is_excluded_combo 동은 제외. 비어있으면 단일 동(quarterly_projection) fallback.
  const dpredicts = (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo);
  const bepSeries =
    dpredicts.length > 0
      ? dpredicts.map((p) => ({
          district: p.district,
          projection: p.quarterly_projection ?? [],
        }))
      : [
          {
            district: simResult.winner_district ?? '단일',
            projection: simResult.quarterly_projection ?? [],
          },
        ];
  const hasAnyProjection = bepSeries.some((s) => s.projection.length > 0);

  return (
    <div className="space-y-6">
      <ProfitSimulationPanelFull
        monthlyRev={monthlyRev}
        monthlyCost={monthlyCost}
        netProfit={netProfit}
        margin={margin}
        bepMonths={bepMonths}
      />

      {hasAnyProjection && (
        <div className="bg-card/40 border border-border/60 rounded-3xl p-6">
          <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2 mb-3">
            투자 회수 곡선
          </h4>
          <BepCumulativeProfitChart series={bepSeries} />
        </div>
      )}

      <SurvivalRateKpi
        survivalRate={simResult.market_report?.survival_rate}
        closureRate={simResult.market_report?.closure_rate}
      />

      {dpredicts.length > 0 ? (
        <>
          <div>
            <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-3">
              동별 폐업위험도 (LightGBM + TCN 예측)
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {dpredicts.map((p) => (
                <ClosureRiskPanel
                  key={p.district}
                  district={p.district}
                  closure={p.closure_risk as ClosureRisk | null}
                />
              ))}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-3">
              동별 12개월 폐업률 추이 (실측)
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {dpredicts.map((p) => (
                <ClosureRatePanel
                  key={p.district}
                  district={p.district}
                  rate={p.closure_rate as ClosureRate | null}
                />
              ))}
            </div>
          </div>
        </>
      ) : (
        <>
          <ClosureRatePanel rate={simResult.closure_rate} />
          <ClosureRiskPanel closure={simResult.closure_risk} />
        </>
      )}
    </div>
  );
}

interface ProfitPanelProps {
  monthlyRev: number | null | undefined;
  monthlyCost: number | null | undefined;
  netProfit: number | null | undefined;
  margin: number | null | undefined;
  bepMonths: number | null | undefined;
}

function ProfitSimulationPanelFull({
  monthlyRev,
  monthlyCost,
  netProfit,
  margin,
  bepMonths,
}: ProfitPanelProps) {
  const rows = [
    { label: '추정 월매출', val: monthlyRev, accent: 'text-foreground' },
    { label: '월 운영비 (총계)', val: monthlyCost, accent: 'text-muted-foreground' },
  ];
  return (
    <div className="bg-card/40 border border-border/60 rounded-3xl p-8">
      <div className="flex items-center justify-between mb-6">
        <h4 className="text-sm font-black text-foreground uppercase tracking-tight flex items-center gap-2">
          <Activity size={16} className="text-primary" /> 상세 수익성 시뮬레이션
        </h4>
        <div className="flex items-center gap-2">
          {margin != null && (
            <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepMonths != null && (
            <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums">
              BEP {bepMonths.toFixed(1)}개월
            </div>
          )}
        </div>
      </div>

      {bepMonths != null && (
        <p className="mb-4 text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 인건비 미포함 기준입니다. 실제 BEP는 운영 인원에 따라 길어질 수 있습니다.
        </p>
      )}

      <div className="space-y-3">
        {rows.map((item) => (
          <div
            key={item.label}
            className="flex justify-between items-end border-b border-border/50 pb-3"
          >
            <span className="text-xs font-bold text-muted-foreground">{item.label}</span>
            <span className={`text-lg font-black tabular-nums ${item.accent}`}>
              {item.val != null ? `₩${formatKrw(item.val)}` : '—'}
            </span>
          </div>
        ))}
        <div className="flex justify-between items-center pt-2">
          <span className="text-sm font-black text-primary tracking-tighter">예상 월 영업이익</span>
          <span className="text-3xl font-black text-primary tabular-nums tracking-tighter">
            {netProfit != null ? `₩${formatKrw(netProfit)}` : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
