import type { LegalRisk } from '../../../../types';

export interface LevelCounts {
  high: number;
  medium: number;
  low: number;
  fallback: number;
}

export function countByLevel(risks: LegalRisk[]): LevelCounts {
  const out: LevelCounts = { high: 0, medium: 0, low: 0, fallback: 0 };
  for (const r of risks ?? []) {
    const lvl = String(r.risk_level ?? '').toUpperCase();
    if (lvl === 'HIGH' || lvl === 'DANGER') out.high++;
    else if (lvl === 'MEDIUM' || lvl === 'CAUTION') out.medium++;
    else out.low++;
    if (r.is_fallback) out.fallback++;
  }
  return out;
}

interface Props {
  risks: LegalRisk[] | null | undefined;
}

export function LegalDistributionBar({ risks }: Props) {
  if (!risks || risks.length === 0) {
    return (
      <div className="flex h-[80px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        legal 분석 대기
      </div>
    );
  }
  const counts = countByLevel(risks);
  const total = counts.high + counts.medium + counts.low;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-6 w-full overflow-hidden rounded-lg border border-stone-800">
        <div
          className="flex items-center justify-center bg-rose-500/80 text-[9px] font-black text-white"
          style={{ width: `${pct(counts.high)}%` }}
          title={`필수이행 ${counts.high}`}
        >
          {counts.high >= 1 && pct(counts.high) > 10 ? counts.high : ''}
        </div>
        <div
          className="flex items-center justify-center bg-amber-500/80 text-[9px] font-black text-stone-950"
          style={{ width: `${pct(counts.medium)}%` }}
          title={`확인필요 ${counts.medium}`}
        >
          {counts.medium >= 1 && pct(counts.medium) > 10 ? counts.medium : ''}
        </div>
        <div
          className="flex items-center justify-center bg-emerald-500/80 text-[9px] font-black text-stone-950"
          style={{ width: `${pct(counts.low)}%` }}
          title={`참고사항 ${counts.low}`}
        >
          {counts.low >= 1 && pct(counts.low) > 10 ? counts.low : ''}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-[10px]">
        <LegendItem color="bg-rose-500" label={`필수이행 ${counts.high}`} />
        <LegendItem color="bg-amber-500" label={`확인필요 ${counts.medium}`} />
        <LegendItem color="bg-emerald-500" label={`참고사항 ${counts.low}`} />
        {counts.fallback > 0 && (
          <span className="text-stone-500 italic">(fallback {counts.fallback})</span>
        )}
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`h-2 w-2 rounded-sm ${color}`} />
      <span className="font-bold text-stone-400 tabular-nums">{label}</span>
    </div>
  );
}
