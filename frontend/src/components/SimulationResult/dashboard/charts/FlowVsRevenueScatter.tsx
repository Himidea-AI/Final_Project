import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import type { DistrictRanking } from '../../../../types';

export function simpleLinearRegression(
  points: { x: number; y: number }[],
): { slope: number; intercept: number } | null {
  if (points.length < 2) return null;
  const n = points.length;
  const sumX = points.reduce((s, p) => s + p.x, 0);
  const sumY = points.reduce((s, p) => s + p.y, 0);
  const sumXY = points.reduce((s, p) => s + p.x * p.y, 0);
  const sumX2 = points.reduce((s, p) => s + p.x * p.x, 0);
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

interface Props {
  rankings: DistrictRanking[];
  winnerDistrict?: string;
}

export function FlowVsRevenueScatter({ rankings, winnerDistrict }: Props) {
  const points = rankings
    .filter((r) => typeof r.pop_score === 'number' && typeof r.sales_score === 'number')
    .map((r) => ({
      x: r.pop_score,
      y: r.sales_score,
      district: r.district,
      isWinner: r.district === winnerDistrict,
    }));

  if (points.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        district_rankings 분석 대기
      </div>
    );
  }

  const reg = simpleLinearRegression(points.map((p) => ({ x: p.x, y: p.y })));
  const regLine =
    reg != null
      ? [
          { x: 0, y: reg.intercept },
          { x: 100, y: reg.intercept + reg.slope * 100 },
        ]
      : null;

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 16, right: 24, left: 16, bottom: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
          <XAxis
            type="number"
            dataKey="x"
            name="유동인구 점수"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            label={{ value: '유동인구', fill: '#57534e', fontSize: 10, dy: 20 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="매출 점수"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            label={{ value: '매출', angle: -90, fill: '#57534e', fontSize: 10, dx: -10 }}
          />
          <Tooltip
            cursor={{ strokeDasharray: '3 3', stroke: '#818cf8' }}
            contentStyle={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #44403c',
              borderRadius: 8,
              fontSize: 11,
            }}
            formatter={(_v, _n, item) => {
              const p = item?.payload as (typeof points)[0];
              return [`${p.district} (유동 ${p.x}·매출 ${p.y})`, ''];
            }}
            labelFormatter={() => ''}
          />
          {regLine && (
            <ReferenceLine
              segment={regLine}
              stroke="#818cf8"
              strokeDasharray="4 4"
              strokeOpacity={0.5}
            />
          )}
          <Scatter data={points} isAnimationActive={false}>
            {points.map((p, i) => (
              <Cell key={i} fill={p.isWinner ? '#818cf8' : '#a8a29e'} r={p.isWinner ? 8 : 4} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
