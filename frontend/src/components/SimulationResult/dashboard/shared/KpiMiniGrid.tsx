/**
 * KpiMiniGrid — 헤더 하단 4칸 미니 KPI (참고 v4.3 배치)
 *
 * 실데이터만 표시, delta/피어비교 제거 (이전 원칙 고수).
 * 각 칸: 라벨 + 큰 값 + 보조 태그 + 서브텍스트 + (선택) Sparkline / Bullet.
 */

import { Sparkline } from '../charts/Sparkline';
import { BulletChart } from '../charts/BulletChart';

export interface KpiItem {
  label: string;
  value: string;
  /** 값 옆 작은 태그 (예: "HIGH", "LOW") — 선택 */
  tag?: string;
  /** 태그 색상 — emerald(긍정), amber(주의), rose(위험), stone(중립) */
  tagColor?: 'emerald' | 'amber' | 'rose' | 'stone';
  /** 서브텍스트 (단위 / 맥락) */
  sub?: string;
  /** Sparkline용 시계열 (없으면 표시 안 함) */
  spark?: number[];
  /** Bullet Chart 데이터 (없으면 표시 안 함) */
  bullet?: {
    actual: number | null;
    target?: number;
    max?: number;
    thresholds?: [number, number];
  };
  /**
   * 0~100 normalized score → 카드 하단 progress bar.
   * 색상은 tagColor를 그대로 따라감 (없으면 cyan).
   * 데이터 없을 땐 omit — 가짜 50 채우지 말 것 (실데이터 원칙).
   */
  score?: number | null;
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

/** progress bar 색 — tagColor 트리거. 없으면 cyan(중립 강조색) */
const SCORE_BAR_HEX: Record<NonNullable<KpiItem['tagColor']>, string> = {
  emerald: '#34d399',
  amber: '#fbbf24',
  rose: '#fb7185',
  stone: '#78716c',
};
const DEFAULT_SCORE_HEX = '#22d3ee'; // cyan-400

export function KpiMiniGrid({ items }: KpiMiniGridProps) {
  return (
    <div className="grid grid-cols-4 gap-4 mt-8">
      {items.map((kpi, i) => (
        <div
          key={i}
          className="group relative bg-stone-900/40 border border-stone-800/60 rounded-xl p-4 flex flex-col justify-center hover:border-cyan-500/30 hover:bg-stone-900/60 transition-all overflow-hidden"
        >
          {/* 모서리 micro dot */}
          <span className="absolute top-2.5 right-2.5 w-1 h-1 rounded-full bg-stone-800 group-hover:bg-cyan-500/50 transition-colors" />
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-[0.15em] mb-1">
            {kpi.label}
          </div>
          <div className="flex items-end gap-2">
            <div className="text-2xl font-black text-stone-100 tabular-nums tracking-tighter">
              {kpi.value}
            </div>
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
          {kpi.score != null && (
            <div
              className="relative w-full h-1 bg-stone-800/60 rounded-full overflow-hidden mt-2 shadow-inner"
              role="progressbar"
              aria-valuenow={Math.round(kpi.score)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="absolute left-0 top-0 bottom-0 transition-all duration-700 ease-out rounded-full"
                style={{
                  width: `${Math.min(100, Math.max(0, kpi.score))}%`,
                  backgroundColor: SCORE_BAR_HEX[kpi.tagColor ?? 'stone'] ?? DEFAULT_SCORE_HEX,
                  boxShadow: `0 0 6px ${
                    SCORE_BAR_HEX[kpi.tagColor ?? 'stone'] ?? DEFAULT_SCORE_HEX
                  }80`,
                }}
              />
            </div>
          )}
          {kpi.sub && <div className="text-[9px] text-stone-600 mt-1 font-bold">{kpi.sub}</div>}
          {kpi.spark && kpi.spark.length > 0 && (
            <div className="mt-2">
              <Sparkline data={kpi.spark} />
            </div>
          )}
          {kpi.bullet && (
            <div className="mt-2">
              <BulletChart
                actual={kpi.bullet.actual}
                target={kpi.bullet.target}
                max={kpi.bullet.max ?? 100}
                thresholds={kpi.bullet.thresholds}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
