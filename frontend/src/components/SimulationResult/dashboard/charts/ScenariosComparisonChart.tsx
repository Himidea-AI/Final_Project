/**
 * ScenariosComparisonChart — 낙관/기본/비관 시나리오 비교 (멀티 동 dropdown)
 *
 * 데이터 소스: allScenarios (동별 ScenarioSet 배열)
 *  - dropdown 으로 동 선택 → 선택 동의 optimistic/base/pessimistic 3라인 표시
 *  - 단일 동일 때는 dropdown 숨기고 라벨로 대체
 * 시각: LineChart 3 lines (emerald/indigo/rose) + Legend
 * Best practice: 4분기 Q1~Q4 X축, connectNulls 로 부분 데이터 보존
 */

import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';

interface ScenarioPoint {
  quarter: number;
  revenue: number;
}

type ScenarioSet = {
  optimistic: ScenarioPoint[];
  base: ScenarioPoint[];
  pessimistic: ScenarioPoint[];
};

interface Props {
  allScenarios: { district: string; scenarios: ScenarioSet | null }[];
  height?: number;
}

const formatKRW = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString()}만`;
  return `${Math.round(value).toLocaleString()}원`;
};

export function ScenariosComparisonChart({ allScenarios, height = 240 }: Props) {
  const validScenarios = allScenarios.filter(
    (s): s is { district: string; scenarios: ScenarioSet } =>
      s.scenarios !== null &&
      s.scenarios !== undefined &&
      Array.isArray(s.scenarios.base) &&
      s.scenarios.base.length > 0,
  );

  const [selectedDistrict, setSelectedDistrict] = useState<string>(
    validScenarios[0]?.district ?? '',
  );

  if (validScenarios.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card/40 p-6 text-center text-xs text-muted-foreground">
        시나리오 비교 데이터 없음
      </div>
    );
  }

  const selected =
    validScenarios.find((s) => s.district === selectedDistrict) ?? validScenarios[0]!;
  const scenarios = selected.scenarios;

  const len = Math.max(
    scenarios.optimistic.length,
    scenarios.base.length,
    scenarios.pessimistic.length,
  );
  const chartData = Array.from({ length: len }, (_, i) => {
    const q = i + 1;
    return {
      quarter: q,
      optimistic: scenarios.optimistic[i]?.revenue ?? null,
      base: scenarios.base[i]?.revenue ?? null,
      pessimistic: scenarios.pessimistic[i]?.revenue ?? null,
    };
  }).slice(0, 4);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest">
          낙관/기본/비관 시나리오
        </h4>
        {validScenarios.length > 1 ? (
          <select
            value={selectedDistrict}
            onChange={(e) => setSelectedDistrict(e.target.value)}
            className="bg-card border border-border rounded-lg text-xs text-foreground px-3 py-1.5 focus:outline-none focus:border-primary"
          >
            {validScenarios.map((s) => (
              <option key={s.district} value={s.district}>
                {s.district}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-[0.625rem] text-muted-foreground">
            {validScenarios[0]!.district}
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 12, right: 20, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="quarter"
            tickFormatter={(q) => `Q${q}`}
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            tickFormatter={formatKRW}
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            width={70}
          />
          <Tooltip
            cursor={{ stroke: 'var(--border)', strokeDasharray: '3 3' }}
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--card-foreground)',
            }}
            labelFormatter={(q: number) => `Q${q}`}
            formatter={(v: number, name: string) => {
              const labels: Record<string, string> = {
                optimistic: '낙관',
                base: '기본',
                pessimistic: '비관',
              };
              return [formatKRW(v), labels[name] ?? name];
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 10, color: 'var(--muted-foreground)' }}
            iconType="circle"
            formatter={(v) =>
              v === 'optimistic' ? '낙관' : v === 'base' ? '기본' : v === 'pessimistic' ? '비관' : v
            }
          />
          <Line
            type="monotone"
            dataKey="optimistic"
            stroke="var(--success)"
            strokeWidth={2}
            name="optimistic"
            connectNulls
            dot={{ r: 2.5, fill: 'var(--success)' }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="base"
            stroke="var(--primary)"
            strokeWidth={2}
            name="base"
            connectNulls
            dot={{ r: 3, fill: 'var(--primary)' }}
            activeDot={{ r: 5, fill: 'var(--primary)', stroke: 'var(--card)', strokeWidth: 2 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="pessimistic"
            stroke="var(--danger)"
            strokeWidth={2}
            name="pessimistic"
            connectNulls
            dot={{ r: 2.5, fill: 'var(--danger)' }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
