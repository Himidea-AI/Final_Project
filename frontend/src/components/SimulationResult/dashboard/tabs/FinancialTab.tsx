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
import { formatKrw, formatPct } from '../utils/formatters';
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

// district_predictions[].bep dict 의 부분 타입 (백엔드는 Record<string, unknown> 반환)
type QuarterlySimRow = {
  revenue?: number;
  quarterly_total_cost?: number;
  quarterly_profit?: number;
};
type BepDict = {
  quarterly_simulation?: QuarterlySimRow[];
  bep_quarters?: number | null;
};

export function FinancialTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;

  // 2026-05-04 분기 단위 통일 + ML 실측 우선.
  // FinancialTab 은 단일 동(legacy) 경로지만 district_predictions 가 있다면 ML 실측 우선 사용.
  const dpredicts = (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo);
  const winnerPred =
    dpredicts.find((p) => p.district === simResult.winner_district) ?? dpredicts[0];
  const winnerDistrict = winnerPred?.district ?? simResult.winner_district ?? '단일';
  const bepObj = (winnerPred?.bep as BepDict | null | undefined) ?? null;
  const firstSimQ = bepObj?.quarterly_simulation?.[0];
  const firstProj = simResult.quarterly_projection?.[0];

  const quarterlyRev =
    firstSimQ?.revenue ??
    (ps?.monthly_revenue != null ? ps.monthly_revenue * 3 : null) ??
    firstProj?.revenue ??
    null;
  const quarterlyCost =
    firstSimQ?.quarterly_total_cost ?? (ps?.monthly_cost != null ? ps.monthly_cost * 3 : null);
  const quarterlyProfit =
    firstSimQ?.quarterly_profit ?? (ps?.net_profit != null ? ps.net_profit * 3 : null);
  const margin =
    firstSimQ?.revenue != null && firstSimQ.revenue > 0 && firstSimQ?.quarterly_profit != null
      ? firstSimQ.quarterly_profit / firstSimQ.revenue
      : (ps?.margin_rate ?? null);

  const dataSource: 'ml' | 'llm' | 'none' =
    firstSimQ != null ? 'ml' : ps?.monthly_revenue != null ? 'llm' : 'none';

  // BEP 분기 — ML 실측 우선
  const winnerRanking = simResult.district_rankings?.find(
    (r) => r.district === simResult.winner_district,
  );
  const bepQuarters =
    bepObj?.bep_quarters ??
    winnerRanking?.bep_quarters ??
    ps?.bep_quarters ??
    (ps?.bep_months != null ? Math.round(ps.bep_months / 3) : null);

  return (
    <div className="space-y-6">
      <ProfitSimulationPanelFull
        quarterlyRev={quarterlyRev}
        quarterlyCost={quarterlyCost}
        quarterlyProfit={quarterlyProfit}
        margin={margin}
        bepQuarters={bepQuarters}
        district={winnerDistrict}
        dataSource={dataSource}
      />

      <SurvivalRateKpi closureRate={simResult.market_report?.closure_rate} />

      <ClosureRatePanel rate={simResult.closure_rate} />

      <ClosureRiskPanel closure={simResult.closure_risk} />
    </div>
  );
}

interface ProfitPanelProps {
  quarterlyRev: number | null | undefined;
  quarterlyCost: number | null | undefined;
  quarterlyProfit: number | null | undefined;
  margin: number | null | undefined;
  bepQuarters: number | null | undefined;
  district: string;
  dataSource: 'ml' | 'llm' | 'none';
}

function ProfitSimulationPanelFull({
  quarterlyRev,
  quarterlyCost,
  quarterlyProfit,
  margin,
  bepQuarters,
  district,
  dataSource,
}: ProfitPanelProps) {
  const rows = [
    { label: '분기 추정 매출', val: quarterlyRev, accent: 'text-foreground' },
    { label: '분기 운영비 (총계)', val: quarterlyCost, accent: 'text-muted-foreground' },
  ];
  const sourceBadge =
    dataSource === 'ml'
      ? { label: 'ML 실측', cls: 'border-success/30 bg-success/10 text-success' }
      : dataSource === 'llm'
        ? { label: 'LLM 추정', cls: 'border-warning/30 bg-warning/10 text-warning' }
        : { label: '데이터 없음', cls: 'border-border bg-secondary text-muted-foreground' };

  return (
    <div className="bg-card border border-border rounded-3xl p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex flex-col gap-1">
          <h4 className="text-sm font-black text-foreground uppercase tracking-tight flex items-center gap-2">
            <Activity size={16} className="text-primary" /> 상세 수익성 시뮬레이션
            <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
              profit_simulation
            </span>
          </h4>
          <p className="text-[0.6875rem] font-bold text-muted-foreground">
            기준 동: <span className="text-foreground">{district}</span> · 분기 단위
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`px-2 py-0.5 rounded-full border text-[0.5625rem] font-black uppercase tracking-widest ${sourceBadge.cls}`}
          >
            {sourceBadge.label}
          </div>
          {margin != null && (
            <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepQuarters != null && (
            <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums">
              BEP {bepQuarters}분기
            </div>
          )}
        </div>
      </div>

      {/* 2026-04-27 BEP 면책 — 백엔드 계산식이 인건비 제외라 명시 필요 */}
      {bepQuarters != null && (
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
          <span className="text-sm font-black text-primary tracking-tighter">
            예상 분기 영업이익
          </span>
          <span className="text-3xl font-black text-primary tabular-nums tracking-tighter">
            {quarterlyProfit != null ? `₩${formatKrw(quarterlyProfit)}` : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
