import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';

// 백엔드 weekday_weekend_ratio 는 "평일매출/주말매출" 배수 (>=1 이면 평일 우위, schemas/demographic.py:37).
// UI 막대는 평일·주말 점유율(합=100%) 표시이므로 배수를 점유율로 변환:
//   weekday_share = r / (r + 1)
// 음수·NaN·null·Inf 는 유효치 아님 → null 반환 (placeholder 노출).
export function normalizeRatio(r: number | null | undefined): number | null {
  if (r == null || Number.isNaN(r) || !Number.isFinite(r) || r < 0) return null;
  return r / (r + 1);
}

interface Props {
  ratio: number | null | undefined;
}

export function WeekdayWeekendBar({ ratio }: Props) {
  const n = normalizeRatio(ratio);
  if (n == null) {
    return (
      <div className="flex h-[120px] items-center justify-center rounded-2xl border border-dashed border-border text-muted-foreground text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }
  const data = [
    { label: '주중', value: Math.round(n * 100), color: 'var(--primary)' },
    { label: '주말', value: Math.round((1 - n) * 100), color: 'var(--muted-foreground)' },
  ];
  return (
    <div className="h-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 30, left: 30, bottom: 8 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
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
