/**
 * PredictFinancialSimTab — 예측·재무 시뮬레이션
 * 2026-04-28 IA 재구조 — FinancialTab 분해.
 * BEP 누적이익 + 과거 12개월 폐업률 + LightGBM/TCN 폐업위험도 + 생존률 KPI.
 */

import { Activity, History, ShieldAlert, TrendingUp } from 'lucide-react';
import type { ClosureRate, ClosureRisk, SimulationOutput } from '../../../../../types';
import { formatKrw, formatPct } from '../../utils/formatters';
import { sortByRanking } from '../../utils/rankSort';
import { BepCumulativeProfitChart } from '../../charts/BepCumulativeProfitChart';
import { ClosureRatePanel } from '../../charts/ClosureRatePanel';
import { ClosureRiskHeatmap } from '../../charts/ClosureRiskHeatmap';
import { ClosureRiskPanel } from '../../charts/ClosureRiskPanel';
import { SERIES_COLORS } from '../../../QuarterlyProjectionChart';

interface Props {
  simResult: SimulationOutput;
}

// district_predictions[].bep dict 의 부분 타입 (백엔드는 Record<string, unknown> 으로 반환)
type QuarterlySimRow = {
  revenue?: number;
  quarterly_total_cost?: number;
  quarterly_profit?: number;
};
type BepDict = {
  quarterly_simulation?: QuarterlySimRow[];
  bep_quarters?: number | null;
};

export function PredictFinancialSimTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;

  // M6 (2026-04-29): district_predictions 기반 멀티 동 시리즈.
  // is_excluded_combo 동은 제외. 비어있으면 단일 동(quarterly_projection) fallback.
  // ranking 정렬 (winner→4위) 로 SERIES_COLORS[idx] = Deep Blue Sequential 4-tier 매핑 정합.
  const dpredicts = sortByRanking(
    (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo),
    simResult,
  );

  // 2026-05-04 분기 단위 통일 + ML 실측 우선.
  // 데이터 소스 우선순위:
  //   (1) district_predictions[winner].bep.quarterly_simulation[0]  ← ML 실측 (분기 단위)
  //   (2) LLM final_report.profit_simulation.monthly_*  × 3         ← LLM 월값 환산 (hallucination 가능)
  //   (3) simResult.quarterly_projection[0].revenue                  ← TCN 분기 매출만
  const winnerPred =
    dpredicts.find((p) => p.district === simResult.winner_district) ?? dpredicts[0];
  const winnerDistrict = winnerPred?.district ?? simResult.winner_district ?? '단일';
  const bepObj = (winnerPred?.bep as BepDict | null | undefined) ?? null;
  const firstSimQ = bepObj?.quarterly_simulation?.[0];
  const firstProj = simResult.quarterly_projection?.[0];

  // 분기 매출 / 운영비 / 영업이익 — ML 실측 → LLM ×3 → TCN projection 순서
  const quarterlyRev =
    firstSimQ?.revenue ??
    (ps?.monthly_revenue != null ? ps.monthly_revenue * 3 : null) ??
    firstProj?.revenue ??
    null;
  const quarterlyCost =
    firstSimQ?.quarterly_total_cost ?? (ps?.monthly_cost != null ? ps.monthly_cost * 3 : null);
  const quarterlyProfit =
    firstSimQ?.quarterly_profit ?? (ps?.net_profit != null ? ps.net_profit * 3 : null);
  // 마진 — ML 실측에서 직접 산출하면 가장 정확. fallback LLM margin_rate.
  const margin =
    firstSimQ?.revenue != null && firstSimQ.revenue > 0 && firstSimQ?.quarterly_profit != null
      ? firstSimQ.quarterly_profit / firstSimQ.revenue
      : (ps?.margin_rate ?? null);

  // 데이터 소스 라벨 — UI에 출처 명시 (사용자가 mock/LLM/ML 구분 가능)
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
      {/* 좌:우 = 6:4 (투자 회수 곡선 시각 anchor 우위, 상세 수익성 KPI 박스 보조).
          hasAnyProjection==false 시 우측 패널만 풀 폭. lg 미만 (mobile/tablet) 세로 stack. */}
      {hasAnyProjection ? (
        <div className="grid grid-cols-1 items-stretch gap-6 lg:grid-cols-[6fr_4fr]">
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-8 flex items-start justify-between gap-6">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <TrendingUp className="text-primary" /> 투자 회수 곡선
              </h3>
            </div>
            <BepCumulativeProfitChart series={bepSeries} />
          </div>
          <ProfitSimulationPanelFull
            quarterlyRev={quarterlyRev}
            quarterlyCost={quarterlyCost}
            quarterlyProfit={quarterlyProfit}
            margin={margin}
            bepQuarters={bepQuarters}
            district={winnerDistrict}
            dataSource={dataSource}
          />
        </div>
      ) : (
        <ProfitSimulationPanelFull
          quarterlyRev={quarterlyRev}
          quarterlyCost={quarterlyCost}
          quarterlyProfit={quarterlyProfit}
          margin={margin}
          bepQuarters={bepQuarters}
          district={winnerDistrict}
          dataSource={dataSource}
        />
      )}

      {dpredicts.length > 0 ? (
        <>
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-8 flex items-start justify-between gap-6">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <ShieldAlert className="text-primary" /> 동별 폐업위험도
              </h3>
            </div>
            {/* Heatmap — 4동 × 피처 (LightGBM / TCN 분리). 셀 색강도 = SHAP contribution.
                양수=빨강(위험↑), 음수=초록(위험↓). 동마다 다른 피처가 위험 결정에 기여한 것을 한눈에. */}
            <ClosureRiskHeatmap
              rows={dpredicts.map((p) => ({
                district: p.district,
                closure: p.closure_risk as ClosureRisk | null,
              }))}
            />
          </div>
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-8 flex items-start justify-between gap-6">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <History className="text-primary" /> 동별 최근 4분기 폐업률 추이
              </h3>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {dpredicts.map((p, idx) => (
                <ClosureRatePanel
                  key={p.district}
                  district={p.district}
                  rate={p.closure_rate as ClosureRate | null}
                  color={SERIES_COLORS[idx % SERIES_COLORS.length]}
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
  // 데이터 출처 배지 — 사용자에게 ML 실측인지 LLM 추정인지 명시
  const sourceBadge =
    dataSource === 'ml'
      ? { label: 'ML 실측', cls: 'border-success/30 bg-success/10 text-success' }
      : dataSource === 'llm'
        ? { label: 'LLM 추정', cls: 'border-warning/30 bg-warning/10 text-warning' }
        : { label: '데이터 없음', cls: 'border-border bg-secondary text-muted-foreground' };
  return (
    <div className="rounded-3xl border border-border bg-card p-8">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
            <Activity className="text-primary" /> 상세 수익성 시뮬레이션
          </h3>
          <p className="text-[0.6875rem] font-bold text-muted-foreground">
            기준 동: <span className="text-foreground">{district}</span> · 분기 단위
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`rounded-full border px-2 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest ${sourceBadge.cls}`}
          >
            {sourceBadge.label}
          </div>
          {margin != null && (
            <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepQuarters != null && (
            <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
              BEP {bepQuarters}분기
            </div>
          )}
        </div>
      </div>

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
