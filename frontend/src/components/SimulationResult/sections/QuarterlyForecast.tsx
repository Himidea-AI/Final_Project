import type { SimulationOutput } from '../../../types';
import { QuarterlyProjectionChart } from '../QuarterlyProjectionChart';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

export function QuarterlyForecast({ simResult }: Props) {
  const attrs = simResult.agent_attributions ?? [];
  const trend = attrs.find((a) => a.id === 'trend_forecaster');
  const demo = attrs.find((a) => a.id === 'demographic_depth');

  return (
    <section>
      <SectionLabel label="QUARTERLY FORECAST" subtitle="분기별 매출 · 누적 수익 · BEP 도달 시점" />
      <div className="mb-3 rounded-lg border border-stone-700 bg-stone-800 p-4">
        <QuarterlyProjectionChart data={simResult.quarterly_projection ?? []} />
      </div>
      {(trend || demo) && (
        <div className="grid gap-2 md:grid-cols-2">
          {trend && <AgentCard attribution={trend} size="compact" />}
          {demo && <AgentCard attribution={demo} size="compact" />}
        </div>
      )}
    </section>
  );
}
