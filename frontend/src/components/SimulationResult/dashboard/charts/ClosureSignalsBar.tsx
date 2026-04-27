/**
 * ClosureSignalsBar — 폐업위험도 LightGBM/TCN 피처 기여도 가로 막대
 *
 * 2026-04-27: 기존 텍스트 1줄 요약(summary_lgbm)만 표시되던 것을 시각화 보강.
 * 양수 = 폐업 위험 증가 (빨강), 음수 = 위험 감소 (초록).
 */

import type { ClosureRiskSignal } from '../../../../types';

interface Props {
  signals: ClosureRiskSignal[] | undefined;
  title: string;
  /** 라벨 색상 토큰 (LightGBM=indigo, TCN=cyan 등) */
  accent?: 'indigo' | 'cyan';
}

export function ClosureSignalsBar({ signals, title, accent = 'indigo' }: Props) {
  if (!signals || signals.length === 0) {
    return null;
  }

  const top = signals.slice(0, 5);
  const maxAbs = Math.max(...top.map((s) => Math.abs(s.contribution)), 0.0001);
  const accentClass = accent === 'cyan' ? 'text-cyan-400' : 'text-indigo-400';

  return (
    <div className="mt-3 rounded-lg border border-stone-800/60 bg-stone-950/40 p-4">
      <div className={`text-[10px] font-black uppercase tracking-widest mb-3 ${accentClass}`}>
        {title}
      </div>
      <div className="space-y-2">
        {top.map((s, i) => {
          const positive = s.contribution >= 0;
          const widthPct = (Math.abs(s.contribution) / maxAbs) * 100;
          const barColor = positive ? 'bg-rose-500/70' : 'bg-emerald-500/70';
          const labelColor = positive ? 'text-rose-400' : 'text-emerald-400';
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[11px] text-stone-400 font-bold w-24 truncate">
                {s.feature}
              </span>
              <div className="flex-1 relative h-3 rounded-sm overflow-hidden">
                <div className="absolute inset-y-0 left-1/2 w-px bg-stone-700" />
                {positive ? (
                  <div
                    className={`absolute inset-y-0 left-1/2 ${barColor} rounded-r-sm`}
                    style={{ width: `${widthPct / 2}%` }}
                  />
                ) : (
                  <div
                    className={`absolute inset-y-0 right-1/2 ${barColor} rounded-l-sm`}
                    style={{ width: `${widthPct / 2}%` }}
                  />
                )}
              </div>
              <span className={`text-[11px] font-black tabular-nums w-14 text-right ${labelColor}`}>
                {positive ? '+' : ''}
                {s.contribution.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10px] text-stone-500 leading-relaxed">
        양수(빨강) = 폐업 위험을 높이는 요인, 음수(초록) = 낮추는 요인
      </p>
    </div>
  );
}
