interface AgeGroup {
  age_group: string;
  share: number;
}

export function normalizeAgeGroups(raw: AgeGroup[] | null | undefined): AgeGroup[] {
  if (!raw || raw.length === 0) return [];
  const sum = raw.reduce((s, r) => s + (r.share ?? 0), 0);
  if (sum <= 0) return [];
  if (sum > 1.0) {
    return raw.map((r) => ({ ...r, share: r.share / sum }));
  }
  if (sum < 0.99) {
    return [...raw, { age_group: '기타', share: 1 - sum }];
  }
  return raw;
}

const COLORS = ['#818cf8', '#a5b4fc', '#c7d2fe', '#a8a29e'];

interface Props {
  groups: AgeGroup[] | null | undefined;
}

export function StackedAgeBar({ groups }: Props) {
  const normalized = normalizeAgeGroups(groups);
  if (normalized.length === 0) {
    return (
      <div className="flex h-[100px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-8 w-full overflow-hidden rounded-xl border border-stone-800">
        {normalized.map((g, i) => (
          <div
            key={g.age_group}
            className="flex items-center justify-center text-[10px] font-black text-stone-100"
            style={{ width: `${g.share * 100}%`, backgroundColor: COLORS[i] ?? COLORS[3] }}
          >
            {g.share >= 0.08 ? `${Math.round(g.share * 100)}%` : ''}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-[10px]">
        {normalized.map((g, i) => (
          <div key={g.age_group} className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-sm"
              style={{ backgroundColor: COLORS[i] ?? COLORS[3] }}
            />
            <span className="font-bold text-stone-400">{g.age_group}</span>
            <span className="tabular-nums text-stone-500">{Math.round(g.share * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
