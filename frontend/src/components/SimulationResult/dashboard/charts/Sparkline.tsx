import type { CSSProperties } from 'react';
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
  up: 'var(--success)',
  down: 'var(--danger)',
  flat: 'var(--muted-foreground)',
};

interface Props {
  /** 너비 미지정 시 부모 컨테이너 100% 사용 (ResponsiveContainer에 위임) */
  width?: number;
  height?: number;
  data: number[];
}

export function Sparkline({ data, width, height = 24 }: Props) {
  if (!data || data.length === 0) {
    return <span className="text-[0.625rem] text-stone-500">—</span>;
  }
  const dir = computeTrendDirection(data);
  const points = data.map((v, i) => ({ i, v }));
  // width 미지정이면 부모 100%로 늘어남 (caller가 height만 주는 카드 레이아웃 대응)
  const containerStyle: CSSProperties =
    width != null ? { width, height } : { width: '100%', height };
  return (
    <div style={containerStyle}>
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
