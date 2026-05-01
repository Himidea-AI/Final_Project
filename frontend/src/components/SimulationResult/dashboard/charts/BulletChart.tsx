export type BulletBand = 'bad' | 'ok' | 'good';

export function qualitativeBand(value: number, thresholds: [number, number]): BulletBand {
  const [low, high] = thresholds;
  if (value >= high) return 'good';
  if (value >= low) return 'ok';
  return 'bad';
}

/**
 * polarity — 점수 해석 방향.
 *   'higher-better' (default): 점수가 높을수록 좋음 (예: 매출 점수, 생존율).
 *     low zone(빨강 tint) → ok zone(노랑) → high zone(초록).
 *   'lower-better': 점수가 낮을수록 좋음 (예: 폐업 위험도).
 *     low zone(초록) → ok zone(노랑) → high zone(빨강).
 *
 * 색은 의미 시멘틱 (success/warning/danger) 만 사용 — 12색 토큰 SoT.
 */
type Polarity = 'higher-better' | 'lower-better';

interface Props {
  actual: number | null | undefined;
  target?: number;
  max?: number;
  label?: string;
  thresholds?: [number, number];
  polarity?: Polarity;
}

function bandFor(value: number, thresholds: [number, number], polarity: Polarity): BulletBand {
  const [low, high] = thresholds;
  if (polarity === 'lower-better') {
    if (value <= low) return 'good';
    if (value <= high) return 'ok';
    return 'bad';
  }
  // higher-better
  if (value >= high) return 'good';
  if (value >= low) return 'ok';
  return 'bad';
}

const ZONE_FILL: Record<BulletBand, string> = {
  good: 'bg-success/15',
  ok: 'bg-warning/15',
  bad: 'bg-danger/15',
};
const BAR_FILL: Record<BulletBand, string> = {
  good: 'bg-success',
  ok: 'bg-warning',
  bad: 'bg-danger',
};

export function BulletChart({
  actual,
  target,
  max = 100,
  label,
  thresholds = [40, 70],
  polarity = 'higher-better',
}: Props) {
  const hasValue = actual != null;
  const pct = hasValue ? Math.min(100, Math.max(0, (actual / max) * 100)) : 0;
  const targetPct = target != null ? Math.min(100, Math.max(0, (target / max) * 100)) : null;
  const [lowPct, highPct] = [(thresholds[0] / max) * 100, (thresholds[1] / max) * 100];

  // zone 색 — polarity 에 따라 left→right 순서 반전.
  // higher-better: low(bad) → mid(ok) → high(good)
  // lower-better:  low(good) → mid(ok) → high(bad)
  const [leftBand, midBand, rightBand]: [BulletBand, BulletBand, BulletBand] =
    polarity === 'lower-better' ? ['good', 'ok', 'bad'] : ['bad', 'ok', 'good'];

  // actual 위치의 band — bar 색을 그 zone 의 시멘틱 색으로 동적 매칭.
  const actualBand: BulletBand | null =
    hasValue && actual != null ? bandFor(actual, thresholds, polarity) : null;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        {label && (
          <span className="text-[0.5625rem] font-bold text-muted-foreground uppercase tracking-widest">
            {label}
          </span>
        )}
        <span className="text-xs font-black text-foreground tabular-nums">
          {hasValue ? actual : '—'}
        </span>
      </div>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-card">
        <div
          className={`absolute top-0 left-0 h-full ${ZONE_FILL[leftBand]}`}
          style={{ width: `${lowPct}%` }}
        />
        <div
          className={`absolute top-0 h-full ${ZONE_FILL[midBand]}`}
          style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
        />
        <div
          className={`absolute top-0 h-full ${ZONE_FILL[rightBand]}`}
          style={{ left: `${highPct}%`, width: `${100 - highPct}%` }}
        />
        {hasValue && actualBand && (
          <div
            className={`absolute top-0.5 h-1 rounded-full ${BAR_FILL[actualBand]}`}
            style={{ width: `${pct}%` }}
          />
        )}
        {targetPct != null && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-primary"
            style={{ left: `${targetPct}%` }}
          />
        )}
      </div>
    </div>
  );
}
