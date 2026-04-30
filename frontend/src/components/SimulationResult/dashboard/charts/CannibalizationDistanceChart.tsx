/**
 * CannibalizationDistanceChart — 자사 매장 거리 분포 막대
 *
 * 데이터: competitor_intel.cannibalization.distance_bins
 *   {"0-300m": 1, "300-500m": 1, "500-1000m": 0, "1000-2000m": 2}
 * 디자인: 가로 막대, 가까울수록 빨강 (잠식 위험 ↑)
 * Best practice: ordinal X axis + monochromatic warning gradient
 */

import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';

interface Props {
  bins: Record<string, number> | null | undefined;
  closestM?: number | null;
  impactPct?: number | null;
  height?: number;
}

// 거리가 가까울수록 빨강 (잠식 위험 색상 시멘틱)
// 룰 §9: danger → warning → decor-yellow → decor-cyan → success
const BIN_COLORS = [
  'var(--danger)',
  'var(--warning)',
  'var(--decor-yellow)',
  'var(--decor-cyan)',
  'var(--success)',
];

export function CannibalizationDistanceChart({ bins, closestM, impactPct, height = 180 }: Props) {
  if (!bins || Object.keys(bins).length === 0) {
    return null;
  }

  const entries = Object.entries(bins).map(([label, count], i) => ({
    bin: label,
    count: count ?? 0,
    color: BIN_COLORS[Math.min(i, BIN_COLORS.length - 1)],
  }));

  const total = entries.reduce((s, e) => s + e.count, 0);
  if (total === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        2km 반경 내 자사 매장 없음
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-stone-800/60 bg-stone-950/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
          자사 매장 거리 분포
          <span className="ml-2 text-[0.5625rem] font-bold text-stone-600 normal-case tracking-normal">
            cannibalization · 2km 반경
          </span>
        </div>
        <div className="flex items-center gap-3 text-[0.625rem] font-bold tabular-nums">
          {closestM != null && (
            <span className="text-stone-400">
              최근접 <span className="text-stone-100">{closestM}m</span>
            </span>
          )}
          {impactPct != null && (
            <span className="text-rose-400">잠식 {(impactPct * 100).toFixed(1)}%</span>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={entries} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="bin"
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: 'rgba(168,162,158,0.05)' }}
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--card-foreground)',
            }}
            formatter={(v: number) => [`${v}개`, '자사 매장']}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {entries.map((e, i) => (
              <Cell key={i} fill={e.color} fillOpacity={0.75} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
