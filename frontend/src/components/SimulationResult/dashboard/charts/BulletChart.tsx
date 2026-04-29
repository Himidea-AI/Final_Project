export type BulletBand = 'bad' | 'ok' | 'good';

export function qualitativeBand(value: number, thresholds: [number, number]): BulletBand {
  const [low, high] = thresholds;
  if (value >= high) return 'good';
  if (value >= low) return 'ok';
  return 'bad';
}

interface Props {
  actual: number | null | undefined;
  target?: number;
  max?: number;
  label?: string;
  thresholds?: [number, number];
}

export function BulletChart({ actual, target, max = 100, label, thresholds = [40, 70] }: Props) {
  const hasValue = actual != null;
  const pct = hasValue ? Math.min(100, Math.max(0, (actual / max) * 100)) : 0;
  const targetPct = target != null ? Math.min(100, Math.max(0, (target / max) * 100)) : null;
  const [lowPct, highPct] = [(thresholds[0] / max) * 100, (thresholds[1] / max) * 100];

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        {label && (
          <span className="text-[0.5625rem] font-bold text-stone-500 uppercase tracking-widest">
            {label}
          </span>
        )}
        <span className="text-xs font-black text-stone-200 tabular-nums">
          {hasValue ? actual : '—'}
        </span>
      </div>
      <div className="relative h-2 w-full rounded-full bg-stone-800 overflow-hidden">
        <div
          className="absolute top-0 left-0 h-full bg-stone-700/40"
          style={{ width: `${lowPct}%` }}
        />
        <div
          className="absolute top-0 h-full bg-stone-600/40"
          style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
        />
        <div
          className="absolute top-0 h-full bg-stone-500/40"
          style={{ left: `${highPct}%`, width: `${100 - highPct}%` }}
        />
        {hasValue && (
          <div
            className="absolute top-0.5 h-1 rounded-full bg-indigo-400"
            style={{ width: `${pct}%` }}
          />
        )}
        {targetPct != null && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-indigo-200"
            style={{ left: `${targetPct}%` }}
          />
        )}
      </div>
    </div>
  );
}
