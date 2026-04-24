/**
 * WaterfallChart — SHAP 기여도 시각화 (Recharts PoC)
 *
 * Recharts BarChart에 invisible spacer + colored bar를 stack해서 구현.
 * 외부 라이브러리 의존성 0 (Recharts만 사용).
 *
 * 데이터 흐름:
 *   base → contrib₁ → contrib₂ → ... → final
 *   각 step은 [spacer (transparent), value (colored)] 두 segment로 stack.
 */

import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from 'recharts';

export interface WaterfallStep {
  label: string;
  /** base/final이면 absolute value, contribution이면 delta (음수 가능) */
  value: number;
  kind: 'base' | 'contribution' | 'final';
}

interface Props {
  steps: WaterfallStep[];
  /** Y축 단위 포매터. 기본은 toLocaleString. */
  formatY?: (n: number) => string;
  /** 차트 높이 (px). 기본 300. */
  height?: number;
}

interface BarRow {
  label: string;
  spacer: number; // transparent bottom segment
  bar: number; // visible top segment (absolute height)
  signedValue: number; // 원본 값 (음수 가능, 툴팁용)
  kind: WaterfallStep['kind'];
}

/**
 * Steps를 Recharts에 먹일 row[]로 변환.
 * base/final은 spacer=0, bar=value (positive 가정).
 * contribution은 running total 기준 spacer 위치 계산.
 */
export function buildRows(steps: WaterfallStep[]): {
  rows: BarRow[];
  runningTotals: number[];
} {
  let running = 0;
  const rows: BarRow[] = [];
  const runningTotals: number[] = [];

  steps.forEach((s) => {
    if (s.kind === 'base') {
      rows.push({
        label: s.label,
        spacer: 0,
        bar: s.value,
        signedValue: s.value,
        kind: 'base',
      });
      running = s.value;
    } else if (s.kind === 'final') {
      rows.push({
        label: s.label,
        spacer: 0,
        bar: s.value,
        signedValue: s.value,
        kind: 'final',
      });
    } else {
      // contribution
      const isPositive = s.value >= 0;
      const spacer = isPositive ? running : running + s.value; // 음수면 더 낮은 위치에서 시작
      rows.push({
        label: s.label,
        spacer,
        bar: Math.abs(s.value),
        signedValue: s.value,
        kind: 'contribution',
      });
      running += s.value;
    }
    runningTotals.push(running);
  });

  return { rows, runningTotals };
}

const COLOR_BASE = '#a8a29e'; // Stone 400
const COLOR_FINAL = '#818cf8'; // Indigo 400 (메인)
const COLOR_POS = '#22c55e'; // Emerald 500 (양 기여)
const COLOR_NEG = '#ef4444'; // Rose 500 (음 기여)

function colorFor(kind: BarRow['kind'], signed: number): string {
  if (kind === 'base') return COLOR_BASE;
  if (kind === 'final') return COLOR_FINAL;
  return signed >= 0 ? COLOR_POS : COLOR_NEG;
}

export function WaterfallChart({
  steps,
  formatY = (n) => n.toLocaleString('ko-KR'),
  height = 300,
}: Props) {
  if (!steps || steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-stone-500 text-xs">
        Waterfall 데이터 없음
      </div>
    );
  }

  const { rows } = buildRows(steps);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 16, right: 16, left: 16, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: '#a8a29e' }}
          interval={0}
          axisLine={{ stroke: '#44403c' }}
        />
        <YAxis
          tickFormatter={formatY}
          tick={{ fontSize: 10, fill: '#a8a29e' }}
          axisLine={{ stroke: '#44403c' }}
        />
        <Tooltip
          cursor={{ fill: 'rgba(129,140,248,0.05)' }}
          contentStyle={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #44403c',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(_v, _n, item) => {
            const r = item?.payload as BarRow;
            const sign = r.signedValue >= 0 ? '+' : '';
            return [`${sign}${formatY(r.signedValue)}`, r.label];
          }}
          labelFormatter={() => ''}
        />
        <ReferenceLine y={0} stroke="#44403c" />
        {/* spacer는 invisible, bar만 시각화 */}
        <Bar dataKey="spacer" stackId="a" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="bar" stackId="a" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {rows.map((r, i) => (
            <Cell key={i} fill={colorFor(r.kind, r.signedValue)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
