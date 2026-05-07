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
      <div className="flex h-[80px] items-center justify-center rounded-2xl border border-dashed border-border text-muted-foreground text-xs">
        legal 분석 대기
      </div>
    );
  }
  const counts = countByLevel(risks);
  const total = counts.high + counts.medium + counts.low;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-6 w-full overflow-hidden rounded-lg border border-border">
        <div
          className="flex items-center justify-center bg-danger text-[0.5625rem] font-black text-white"
          style={{ width: `${pct(counts.high)}%`, minWidth: counts.high >= 1 ? '20px' : 0 }}
          title={`필수이행 ${counts.high}`}
        >
          {counts.high >= 1 ? counts.high : ''}
        </div>
        <div
          className="flex items-center justify-center bg-warning text-[0.5625rem] font-black text-white"
          style={{ width: `${pct(counts.medium)}%`, minWidth: counts.medium >= 1 ? '20px' : 0 }}
          title={`확인필요 ${counts.medium}`}
        >
          {counts.medium >= 1 ? counts.medium : ''}
        </div>
        <div
          className="flex items-center justify-center bg-success text-[0.5625rem] font-black text-white"
          style={{ width: `${pct(counts.low)}%`, minWidth: counts.low >= 1 ? '20px' : 0 }}
          title={`참고사항 ${counts.low}`}
        >
          {counts.low >= 1 ? counts.low : ''}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-[0.625rem]">
        <LegendItem color="bg-danger" label={`필수이행 ${counts.high}`} />
        <LegendItem color="bg-warning" label={`확인필요 ${counts.medium}`} />
        <LegendItem color="bg-success" label={`참고사항 ${counts.low}`} />
        {counts.fallback > 0 && (
          <span className="text-muted-foreground italic">(fallback {counts.fallback})</span>
        )}
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`h-2 w-2 rounded-sm ${color}`} />
      <span className="font-bold text-muted-foreground tabular-nums">{label}</span>
    </div>
  );
}
