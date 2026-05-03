/**
 * PctElasticitySlider — TCN v3 % 섭동 슬라이더 (단일 PctSliderKey).
 *
 * v3 schema: elasticity[slider][level] = number[] (4분기 시계열).
 *   여기서는 단일 슬라이더 안에서도 4분기 spread 를 미니 sparkline 으로 시각화 +
 *   현재 값의 분기 평균 % 를 칩으로 표시 (단일 값으로 변환).
 *
 * 명세서 §4.2 ⓘ 툴팁 + 7-tick 라벨 (-30~+30, step 10).
 */

import type { PctSliderKey } from '../../../../types/elasticity';
import { SLIDER_TOOLTIPS } from '../../../../types/elasticity';

interface Props {
  sliderKey: PctSliderKey;
  label: string;
  value: number; // -30 ~ +30, step 10
  onChange: (next: number) => void;
  /** 4분기 시계열 (현재 level 의 % 변화). length 4. */
  quarterDeltas: number[];
}

const formatPct = (v: number): string => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

function MiniSpread({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const range = max - min || 1;
  const width = 60;
  const height = 16;
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  const zeroY = height - ((0 - min) / range) * height;
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      className="text-primary"
    >
      <line
        x1={0}
        x2={width}
        y1={zeroY}
        y2={zeroY}
        stroke="var(--border)"
        strokeWidth={0.7}
        strokeDasharray="2 2"
      />
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

export function PctElasticitySlider({ sliderKey, label, value, onChange, quarterDeltas }: Props) {
  const avgDelta =
    quarterDeltas.length > 0 ? quarterDeltas.reduce((s, v) => s + v, 0) / quarterDeltas.length : 0;
  const tone =
    avgDelta > 0
      ? 'border-success/30 bg-success/10 text-success'
      : avgDelta < 0
        ? 'border-danger/30 bg-danger/10 text-danger'
        : 'border-border bg-secondary text-muted-foreground';

  const valueLabel = `${value > 0 ? '+' : ''}${value}%`;
  const tip = SLIDER_TOOLTIPS[sliderKey];
  const ariaLabel = `${label} 슬라이더, 현재 ${valueLabel}, 분기 평균 매출 변화 ${formatPct(avgDelta)}`;

  return (
    <div className="space-y-2 rounded-2xl border border-border bg-secondary/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black tracking-tight text-foreground" title={tip}>
            {label}
          </span>
          <span
            className={`rounded-full border px-2 py-0.5 text-[0.625rem] font-black tabular-nums ${tone}`}
            title={`이 슬라이더 ${valueLabel} 시 분기 평균 매출 변화. 분기별 spread 는 우측 sparkline 참조.`}
          >
            {formatPct(avgDelta)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <MiniSpread values={quarterDeltas} />
          <span className="text-xs font-black text-primary tabular-nums">{valueLabel}</span>
        </div>
      </div>

      <input
        type="range"
        min={-30}
        max={30}
        step={10}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel}
        aria-valuemin={-30}
        aria-valuemax={30}
        aria-valuenow={value}
        aria-valuetext={`${valueLabel}, 분기 평균 ${formatPct(avgDelta)}`}
        className="w-full cursor-pointer rounded accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
      />

      <div className="flex justify-between text-[0.5625rem] font-bold tabular-nums text-muted-foreground">
        <span>-30%</span>
        <span>-20</span>
        <span>-10</span>
        <span>0</span>
        <span>+10</span>
        <span>+20</span>
        <span>+30%</span>
      </div>

      <p className="text-[0.5625rem] leading-relaxed text-muted-foreground">{tip}</p>
    </div>
  );
}
