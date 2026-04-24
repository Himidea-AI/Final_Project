/**
 * KpiMiniGrid — 헤더 하단 4칸 미니 KPI (참고 v4.3 배치)
 *
 * 실데이터만 표시, delta/피어비교 제거 (이전 원칙 고수).
 * 각 칸: 라벨 + 큰 값 + 보조 태그 + 서브텍스트.
 */

export interface KpiItem {
  label: string;
  value: string;
  /** 값 옆 작은 태그 (예: "HIGH", "LOW") — 선택 */
  tag?: string;
  /** 태그 색상 — emerald(긍정), amber(주의), rose(위험), stone(중립) */
  tagColor?: 'emerald' | 'amber' | 'rose' | 'stone';
  /** 서브텍스트 (단위 / 맥락) */
  sub?: string;
}

interface KpiMiniGridProps {
  items: KpiItem[];
}

const TAG_CLS: Record<NonNullable<KpiItem['tagColor']>, string> = {
  emerald: 'text-emerald-400',
  amber: 'text-amber-400',
  rose: 'text-rose-400',
  stone: 'text-stone-400',
};

export function KpiMiniGrid({ items }: KpiMiniGridProps) {
  return (
    <div className="grid grid-cols-4 gap-4 mt-8">
      {items.map((kpi, i) => (
        <div
          key={i}
          className="bg-stone-900/40 border border-stone-800/60 rounded-xl p-4 flex flex-col justify-center"
        >
          <div className="text-[10px] font-bold text-stone-500 uppercase tracking-tight mb-1">
            {kpi.label}
          </div>
          <div className="flex items-end gap-2">
            <div className="text-2xl font-black text-stone-100 tabular-nums">{kpi.value}</div>
            {kpi.tag && (
              <div
                className={`text-[10px] font-black px-1.5 py-0.5 rounded-md mb-1 bg-stone-800 ${
                  TAG_CLS[kpi.tagColor ?? 'stone']
                }`}
              >
                {kpi.tag}
              </div>
            )}
          </div>
          {kpi.sub && <div className="text-[9px] text-stone-600 mt-1 font-bold">{kpi.sub}</div>}
        </div>
      ))}
    </div>
  );
}
