/**
 * FinancialTab — 재무·수익성 전용 탭
 *
 * SummaryTab에서 ProfitSimulationPanelFull 이관 + ForecastTab에서 ClosureRiskPanel 이관.
 * 결재자(본부장급) 관점: 매출/운영비/영업이익/마진 + 폐업 위험도.
 * 매출 예측 그래프는 ForecastTab에 그대로 남김 (예측 vs 현재 재무 관점 구분).
 */

import { Activity, Gauge } from 'lucide-react';
import type { SimulationOutput, ClosureRisk } from '../../../../types';
import { formatKrw, formatPct, quarterlyToMonthly } from '../utils/formatters';
import { BulletChart } from '../charts/BulletChart';

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
  const synthAttr = simResult.agent_attributions?.find((a) => a.id === 'synthesis');
  // 실데이터 원칙: synthesis 에이전트 신뢰도가 없으면 null (이전 90% 기본값 제거)
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
  /** synthesis.confidence × 100. null이면 "미산정" empty state */
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
          <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal">
            profit_simulation
          </span>
        </h4>
        <div className="flex items-center gap-2">
          {margin != null && (
            <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tabular-nums">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepMonths != null && (
            <div className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full text-[11px] font-black text-cyan-400 tabular-nums">
              BEP {bepMonths.toFixed(1)}개월
            </div>
          )}
        </div>
      </div>

      {/* 2026-04-27 BEP 면책 — 백엔드 계산식이 인건비 제외라 명시 필요 */}
      {bepMonths != null && (
        <p className="mb-4 text-[10px] text-stone-500 leading-relaxed">
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
            <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
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
              <p className="mt-3 text-[10px] text-stone-500 leading-relaxed">
                synthesis 에이전트 판단 신뢰도 기반. TCN MAPE 제공 시 교체됩니다.
              </p>
            </>
          ) : (
            <>
              <div className="text-2xl font-black text-stone-500 tabular-nums mb-2">—</div>
              <div className="w-full bg-stone-800 h-1.5 rounded-full" />
              <p className="mt-3 text-[10px] text-stone-500 leading-relaxed">
                synthesis 에이전트 신뢰도 미산정. 분석 완료 후 표시됩니다.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function ClosureRiskPanel({ closure }: { closure: ClosureRisk | null | undefined }) {
  if (!closure) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        closure_risk 분석 대기
      </div>
    );
  }
  // 백엔드는 risk_score를 0~1 소수점으로 저장 (synthesis.py:209가 *100해서 표시).
  // BulletChart는 0~100 스케일 기대 → 여기서 정규화.
  const scoreRaw = closure.risk_score;
  const score100 =
    scoreRaw == null ? null : scoreRaw <= 1 ? Math.round(scoreRaw * 100) : Math.round(scoreRaw);
  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2">
          폐업 위험도
        </h4>
        {closure.is_mock && (
          <span className="text-[9px] font-black text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full uppercase">
            MOCK
          </span>
        )}
      </div>
      <BulletChart
        actual={score100}
        target={30}
        max={100}
        label="위험 점수"
        thresholds={[30, 60]}
      />

      {/* 2026-04-27: closure_risk가 LightGBM(과거 패턴) + TCN(시계열) 두 모델 결과를 별도 노출 */}
      {closure.summary_lgbm && closure.summary_lgbm.length > 0 && (
        <div className="mt-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-indigo-400 mb-1">
            <span className="w-1 h-1 rounded-full bg-indigo-400" />
            LightGBM · 과거 패턴
          </div>
          <p className="text-[11px] text-stone-300 leading-relaxed">{closure.summary_lgbm[0]}</p>
        </div>
      )}
      {closure.summary_tcn && closure.summary_tcn.length > 0 && (
        <div className="mt-2 rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-cyan-400 mb-1">
            <span className="w-1 h-1 rounded-full bg-cyan-400" />
            TCN · 시계열 흐름
          </div>
          <p className="text-[11px] text-stone-300 leading-relaxed">{closure.summary_tcn[0]}</p>
        </div>
      )}
      {(!closure.summary_lgbm || closure.summary_lgbm.length === 0) &&
        (!closure.summary_tcn || closure.summary_tcn.length === 0) && (
          <p className="mt-3 text-[11px] text-stone-500 leading-relaxed">
            폐업 위험도 모델 요약 미생성
          </p>
        )}
    </div>
  );
}
