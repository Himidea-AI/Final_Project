/**
 * FinancialTab — 재무·수익성 전용 탭
 *
 * SummaryTab에서 ProfitSimulationPanelFull 이관 + ForecastTab에서 ClosureRiskPanel 이관.
 * 결재자(본부장급) 관점: 매출/운영비/영업이익/마진 + 폐업 위험도.
 * 매출 예측 그래프는 ForecastTab에 그대로 남김 (예측 vs 현재 재무 관점 구분).
 *
 * 2026-04-29 M8: ClosureRatePanel / ClosureRiskPanel 을 charts/ 로 분리.
 * 본 탭은 단일 동(legacy) 영역 — district prop 미지정.
 */

import { Activity } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import { formatKrw, formatPct, quarterlyToMonthly } from '../utils/formatters';
import { SurvivalRateKpi } from '../charts/SurvivalRateKpi';
import { ClosureRatePanel } from '../charts/ClosureRatePanel';
import { ClosureRiskPanel } from '../charts/ClosureRiskPanel';

// M8 호환: 기존에 `from '../../tabs/FinancialTab'` 으로 import 하던 외부 모듈을 위해 재수출.
// 새 코드는 charts/ 에서 직접 import 하는 것을 권장.
export { ClosureRatePanel } from '../charts/ClosureRatePanel';
export { ClosureRiskPanel } from '../charts/ClosureRiskPanel';

interface Props {
  simResult: SimulationOutput;
}

export function FinancialTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const firstQ = simResult.quarterly_projection?.[0];
  const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
  const monthlyCost = ps?.monthly_cost ?? null;
  const netProfit = ps?.net_profit ?? null;
  const margin = ps?.margin_rate ?? null;
  const bepMonths = ps?.bep_months ?? null;

  return (
    <div className="space-y-6">
      <ProfitSimulationPanelFull
        monthlyRev={monthlyRev}
        monthlyCost={monthlyCost}
        netProfit={netProfit}
        margin={margin}
        bepMonths={bepMonths}
      />

      <SurvivalRateKpi closureRate={simResult.market_report?.closure_rate} />

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
          <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
            profit_simulation
          </span>
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

      {/* 2026-04-27 BEP 면책 — 백엔드 계산식이 인건비 제외라 명시 필요 */}
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
