import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';

export function normalizeRatio(r: number | null | undefined): number | null {
  if (r == null || Number.isNaN(r)) return null;
  return Math.min(1, Math.max(0, r));
}

interface Props {
  ratio: number | null | undefined;
}

export function WeekdayWeekendBar({ ratio }: Props) {
  const n = normalizeRatio(ratio);
  if (n == null) {
    return (
      <div className="flex h-[120px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }
  const data = [
    { label: '주중', value: Math.round(n * 100), color: '#818cf8' },
    { label: '주말', value: Math.round((1 - n) * 100), color: '#a8a29e' },
  ];
  return (
    <div className="h-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 30, left: 30, bottom: 8 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: 11, fill: '#a8a29e' }}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
