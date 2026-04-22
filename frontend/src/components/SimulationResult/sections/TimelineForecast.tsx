import type { SimulationOutput } from '../../../types';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

const DIRECTION_LABEL: Record<string, string> = {
  growth: '성장',
  stable: '유지',
  decline: '하락',
};

const CLOSURE_LEVEL_CLS: Record<string, string> = {
  safe: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  caution: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  danger: 'border-rose-500/30 bg-rose-500/10 text-rose-400',
};

export function TimelineForecast({ simResult }: Props) {
  const tf = simResult.trend_forecast?.forecast;
  const industryDir = simResult.trend_forecast?.industry_trend?.direction;
  const changeIx = simResult.trend_forecast?.change_ix?.change_ix_label;
  const closure = simResult.closure_risk;
  const trendAgent = simResult.agent_attributions?.find((a) => a.id === 'trend_forecaster');

  const forecastScore = tf?.score != null ? Math.round(tf.score) : null;
  const direction = tf?.direction ?? '—';
  const directionKo = DIRECTION_LABEL[direction] ?? direction;

  return (
    <section>
      <SectionLabel label="TIMELINE FORECAST" subtitle="트렌드 예측 · 폐업 위험 신호" />

      <div className="mb-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-widest text-zinc-400">종합 전망 점수</div>
              <div className="mt-1 text-4xl font-bold text-cyan-400">
                {forecastScore != null ? forecastScore : '—'}
                <span className="ml-1 text-lg text-zinc-500">/100</span>
              </div>
            </div>
            <TrendingUp className="h-6 w-6 text-cyan-400" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-zinc-900/60 px-2 py-1 text-zinc-300">
              방향 <span className="font-semibold text-zinc-100">{directionKo}</span>
            </span>
            {industryDir && (
              <span className="rounded bg-zinc-900/60 px-2 py-1 text-zinc-300">
                업종 <span className="font-semibold text-zinc-100">{industryDir}</span>
              </span>
            )}
            {changeIx && (
              <span className="rounded bg-zinc-900/60 px-2 py-1 text-zinc-300">
                변화 <span className="font-semibold text-zinc-100">{changeIx}</span>
              </span>
            )}
          </div>
          {tf?.narrative && (
            <p className="mt-4 text-sm leading-relaxed text-zinc-300">{tf.narrative}</p>
          )}
        </div>

        <div
          className={`rounded-lg border p-5 ${
            closure
              ? (CLOSURE_LEVEL_CLS[closure.risk_level] ?? 'border-zinc-700 bg-zinc-800')
              : 'border-zinc-700 bg-zinc-800'
          }`}
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-widest text-zinc-400">폐업 위험도</div>
              <div className="mt-1 text-4xl font-bold">
                {closure ? Math.round(closure.risk_score * 100) : '—'}
                <span className="ml-1 text-lg text-zinc-500">{closure ? '%' : '/100'}</span>
              </div>
            </div>
            <AlertTriangle className="h-6 w-6" />
          </div>
          {closure?.top_signals && closure.top_signals.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-xs uppercase tracking-widest text-zinc-400">
                주요 폐업 신호
              </div>
              <ul className="space-y-1 text-xs text-zinc-200">
                {closure.top_signals.slice(0, 3).map((s, i) => (
                  <li key={i} className="flex items-center justify-between">
                    <span>{s.feature}</span>
                    <span className="font-mono">{(s.contribution * 100).toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {trendAgent && <AgentCard attribution={trendAgent} size="compact" />}
    </section>
  );
}
