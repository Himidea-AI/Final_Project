/**
 * ClosureSignalsBar — 폐업위험도 LightGBM/TCN 피처 기여도 가로 막대
 *
 * 2026-04-27: 기존 텍스트 1줄 요약(summary_lgbm)만 표시되던 것을 시각화 보강.
 * 양수 = 폐업 위험 증가 (빨강), 음수 = 위험 감소 (초록).
 */

import type { ClosureRiskSignal } from '../../../../types';
import { shapStrengthFullLabel } from '../utils/formatters';

interface Props {
  signals: ClosureRiskSignal[] | undefined;
  title: string;
  /** 라벨 색상 — LightGBM(과거 패턴, chart-1 deep blue) / TCN(시계열 흐름, chart-3 teal). 12색 토큰 SoT. */
  accent?: 'lgbm' | 'tcn';
}

export function ClosureSignalsBar({ signals, title, accent = 'lgbm' }: Props) {
  if (!signals || signals.length === 0) {
    return null;
  }

  const top = signals.slice(0, 5);
  const maxAbs = Math.max(...top.map((s) => Math.abs(s.contribution)), 0.0001);
  // 두 모델 시각 분리 — LightGBM = primary(deep blue, brand), TCN = chart-3(teal green)
  const accentClass = accent === 'tcn' ? 'text-chart-3' : 'text-primary';

  return (
    <div className="mt-3 rounded-lg border border-border bg-secondary p-4">
      <div className={`text-[0.625rem] font-black uppercase tracking-widest mb-3 ${accentClass}`}>
        {title}
      </div>
      <div className="space-y-2">
        {top.map((s, i) => {
          const positive = s.contribution >= 0;
          const widthPct = (Math.abs(s.contribution) / maxAbs) * 100;
          const barColor = positive ? 'bg-danger/70' : 'bg-success/70';
          const labelColor = positive ? 'text-danger' : 'text-success';
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[0.6875rem] text-muted-foreground font-bold w-24 truncate">
                {s.feature}
              </span>
              <div className="flex-1 relative h-3 rounded-sm overflow-hidden">
                <div className="absolute inset-y-0 left-1/2 w-px bg-muted" />
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
              {/* 우측 라벨: SHAP 원시값 → "위험 증가 ↑↑" 등급 표기.
                  화살표 1/2/3개 = 약/중/강 (utils/formatters.ts shapStrengthFullLabel 단일소스).
                  hover 시 원시값 노출. */}
              <span
                className={`text-[0.6875rem] font-black w-20 text-right ${labelColor}`}
                title={`원시 SHAP 값: ${positive ? '+' : ''}${s.contribution.toFixed(4)}`}
              >
                {shapStrengthFullLabel(s.contribution)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[0.625rem] text-muted-foreground leading-relaxed">
        양수(빨강) = 폐업 위험을 높이는 요인, 음수(초록) = 낮추는 요인
      </p>
    </div>
  );
}
