/**
 * SurvivalRateKpi — 생존률 보조 KPI 카드
 *
 * 데이터: market_report.survival_rate (0~100 정규화 또는 0~1)
 * 디자인: 폐업률(rose) ↔ 생존률(emerald) 시각적 균형
 */

import { ShieldCheck } from 'lucide-react';

interface Props {
  survivalRate: number | null | undefined;
  closureRate?: number | null | undefined;
}

function normalizePct(value: number | null | undefined): number | null {
  if (value == null) return null;
  // 0~1 범위면 100 곱, 그 외엔 그대로 (0~100 정규화)
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

export function SurvivalRateKpi({ survivalRate, closureRate }: Props) {
  const sPct = normalizePct(survivalRate);
  const cPct = normalizePct(closureRate);

  if (sPct == null && cPct == null) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-stone-800/60 bg-stone-950/40 p-5">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck size={14} className="text-emerald-400" />
        <span className="text-[10px] font-black uppercase tracking-widest text-stone-500">
          3년 생존 vs 폐업
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[9px] font-black uppercase tracking-widest text-emerald-400 mb-1">
            생존률
          </div>
          <div className="text-3xl font-black tabular-nums text-emerald-400 tracking-tighter">
            {sPct != null ? `${sPct}` : '—'}
            <span className="text-sm font-bold text-stone-500 ml-0.5">%</span>
          </div>
        </div>
        <div>
          <div className="text-[9px] font-black uppercase tracking-widest text-rose-400 mb-1">
            폐업률
          </div>
          <div className="text-3xl font-black tabular-nums text-rose-400 tracking-tighter">
            {cPct != null ? `${cPct}` : '—'}
            <span className="text-sm font-bold text-stone-500 ml-0.5">%</span>
          </div>
        </div>
      </div>
      {sPct != null &&
        cPct != null &&
        (() => {
          // High #3 — 합 100% 보장 안 됨 (단순 누적은 105% 되어 시각 깨짐).
          // total>0이면 share로 정규화 후 width로만 사용. 표시 텍스트는 원본 그대로.
          const total = sPct + cPct;
          if (total <= 0) return null;
          const sShare = (sPct / total) * 100;
          const cShare = (cPct / total) * 100;
          return (
            <div className="mt-3 h-1.5 w-full rounded-full bg-stone-800 overflow-hidden flex">
              <div className="h-full bg-emerald-500/70" style={{ width: `${sShare}%` }} />
              <div className="h-full bg-rose-500/70" style={{ width: `${cShare}%` }} />
            </div>
          );
        })()}
      <p className="mt-3 text-[10px] text-stone-500 leading-relaxed">
        market_report 정규화 지표. 100을 합한 비율 시각화.
      </p>
    </div>
  );
}
