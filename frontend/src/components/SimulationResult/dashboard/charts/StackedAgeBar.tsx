import { useState } from 'react';

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

// indigo gradient → primary 단색 (opacity 변형으로 단계 표현)
// 4번째는 muted-foreground (기타)
const COLORS = [
  'var(--primary)',
  'color-mix(in oklch, var(--primary) 60%, transparent)',
  'color-mix(in oklch, var(--primary) 35%, transparent)',
  'var(--muted-foreground)',
];

interface Props {
  groups: AgeGroup[] | null | undefined;
}

export function StackedAgeBar({ groups }: Props) {
  const normalized = normalizeAgeGroups(groups);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  if (normalized.length === 0) {
    return (
      <div className="flex h-[100px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3" onMouseLeave={() => setActiveIndex(null)}>
      {/* Stacked bar — hover dim 인터랙션 (Linear 패턴: 활성 외 opacity 30%, 활성은 stroke cyan) */}
      <div className="flex h-9 w-full overflow-hidden rounded-xl border border-stone-800 shadow-inner">
        {normalized.map((g, i) => {
          const isActive = activeIndex === i;
          const isDimmed = activeIndex !== null && !isActive;
          return (
            <div
              key={g.age_group}
              onMouseEnter={() => setActiveIndex(i)}
              className="flex items-center justify-center text-[0.625rem] font-black text-stone-100 transition-all duration-200 cursor-default relative"
              style={{
                width: `${g.share * 100}%`,
                backgroundColor: COLORS[i] ?? COLORS[3],
                opacity: isDimmed ? 0.3 : 1,
                boxShadow: isActive ? 'inset 0 0 0 2px rgba(34,211,238,0.9)' : undefined,
                zIndex: isActive ? 1 : 0,
              }}
            >
              {g.share >= 0.08 ? `${Math.round(g.share * 100)}%` : ''}
            </div>
          );
        })}
      </div>

      {/* Legend — 활성 세그먼트에 맞춰 스타일 동기화 */}
      <div className="flex flex-wrap gap-3 text-[0.625rem]">
        {normalized.map((g, i) => {
          const isActive = activeIndex === i;
          const isDimmed = activeIndex !== null && !isActive;
          return (
            <div
              key={g.age_group}
              onMouseEnter={() => setActiveIndex(i)}
              className={`flex items-center gap-1.5 transition-opacity duration-200 cursor-default ${
                isDimmed ? 'opacity-40' : 'opacity-100'
              }`}
            >
              <div
                className={`h-2 w-2 rounded-sm transition-transform ${isActive ? 'scale-150' : ''}`}
                style={{ backgroundColor: COLORS[i] ?? COLORS[3] }}
              />
              <span className={`font-bold ${isActive ? 'text-stone-100' : 'text-stone-400'}`}>
                {g.age_group}
              </span>
              <span
                className={`tabular-nums ${isActive ? 'text-cyan-400 font-bold' : 'text-stone-500'}`}
              >
                {Math.round(g.share * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
