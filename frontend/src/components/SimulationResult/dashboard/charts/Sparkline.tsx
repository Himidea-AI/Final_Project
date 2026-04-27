import { LineChart, Line, ResponsiveContainer } from 'recharts';

export type TrendDirection = 'up' | 'down' | 'flat';

export function computeTrendDirection(data: number[]): TrendDirection {
  if (data.length < 2) return 'flat';
  const first = data[0];
  const last = data[data.length - 1];
  if (first === 0) return last > 0 ? 'up' : 'flat';
  const pct = (last - first) / first;
  if (pct > 0.2) return 'up';
  if (pct < -0.2) return 'down';
  return 'flat';
}

const TREND_COLOR: Record<TrendDirection, string> = {
  up: '#22c55e',
  down: '#ef4444',
  flat: '#a8a29e',
};

interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 80, height = 24 }: Props) {
  if (!data || data.length === 0) {
    return <span className="text-[10px] text-stone-500">—</span>;
  }
  const dir = computeTrendDirection(data);
  const points = data.map((v, i) => ({ i, v }));
  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={TREND_COLOR[dir]}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
