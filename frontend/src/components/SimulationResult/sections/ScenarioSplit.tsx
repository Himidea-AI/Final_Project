import type { SimulationOutput } from '../../../types';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

export function ScenarioSplit({ simResult }: Props) {
  const sc = simResult.scenarios;
  const synthesis = simResult.agent_attributions?.find((a) => a.id === 'synthesis');

  if (!sc) {
    return (
      <section>
        <SectionLabel label="SCENARIOS" subtitle="낙관 / 기본 / 비관 분기 매출 시나리오" />
        <div className="rounded-lg border border-stone-700 bg-stone-800 p-6 text-center text-sm text-stone-400">
          시나리오 분석 데이터가 없습니다
        </div>
      </section>
    );
  }

  const base = sc.base ?? [];
  const chartData = base.map((b, i) => ({
    quarter: `Q${b.quarter}`,
    optimistic: sc.optimistic?.[i]?.revenue ?? null,
    base: b.revenue,
    pessimistic: sc.pessimistic?.[i]?.revenue ?? null,
  }));

  return (
    <section>
      <SectionLabel label="SCENARIOS" subtitle="낙관 / 기본 / 비관 분기 매출 시나리오" />
      <div className="mb-3 rounded-lg border border-stone-700 bg-stone-800 p-4">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
            <XAxis dataKey="quarter" stroke="#a1a1aa" fontSize={12} />
            <YAxis
              stroke="#a1a1aa"
              fontSize={12}
              tickFormatter={(v: number) => `${(v / 10000).toLocaleString()}만`}
            />
            <Tooltip
              contentStyle={{
                background: '#27272a',
                border: '1px solid #3f3f46',
                borderRadius: 6,
                color: '#e4e4e7',
              }}
              formatter={(v: number) => `${(v / 10000).toLocaleString()}만원`}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: '#a1a1aa' }} />
            <Line
              type="monotone"
              dataKey="optimistic"
              stroke="#10b981"
              strokeWidth={2}
              name="낙관"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="base"
              stroke="#f59e0b"
              strokeWidth={2}
              name="기본"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="pessimistic"
              stroke="#ef4444"
              strokeWidth={2}
              name="비관"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {synthesis && <AgentCard attribution={synthesis} size="compact" />}
    </section>
  );
}
