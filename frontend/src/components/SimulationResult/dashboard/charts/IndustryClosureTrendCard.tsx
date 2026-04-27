/**
 * IndustryClosureTrendCard — 동 + 업종 폐업률 추세 (분기별 8개)
 *
 * 데이터: competitor_intel.industry_closure_trend
 *   { samples: [{quarter, closure_rate, ...}], current_closure_rate, historical_avg, trend }
 * 디자인: KPI(현재/평균) + 추세 배지 + Sparkline
 * Best practice: 추세 라벨(improving/worsening) 색상 시멘틱 + 분기 시계열 미니 차트
 */

import { Activity } from 'lucide-react';
import { Sparkline } from './Sparkline';

interface Sample {
  quarter?: string | number;
  closure_rate?: number | null;
  store_count?: number | null;
  open_count?: number | null;
  close_count?: number | null;
  franchise_count?: number | null;
  [k: string]: unknown;
}

interface Props {
  trend?:
    | {
        samples?: Sample[];
        current_closure_rate?: number | null;
        historical_avg?: number | null;
        trend?: string;
      }
    | null
    | undefined;
}

const TREND_LABEL: Record<string, { label: string; color: string; bg: string }> = {
  improving: {
    label: '개선 중',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10 border-emerald-500/30',
  },
  worsening: {
    label: '악화 중',
    color: 'text-rose-400',
    bg: 'bg-rose-500/10 border-rose-500/30',
  },
  stable: {
    label: '안정',
    color: 'text-stone-300',
    bg: 'bg-stone-700/30 border-stone-600/40',
  },
  unknown: {
    label: '데이터 부족',
    color: 'text-stone-500',
    bg: 'bg-stone-800/30 border-stone-700/40',
  },
};

export function IndustryClosureTrendCard({ trend }: Props) {
  if (!trend || !trend.samples || trend.samples.length === 0) {
    return null;
  }

  const samples = trend.samples;
  const numericSamples = samples
    .map((s) => (typeof s.closure_rate === 'number' ? s.closure_rate * 100 : null))
    .filter((v): v is number => v != null);

  const cur = trend.current_closure_rate;
  const avg = trend.historical_avg;
  const tinfo = TREND_LABEL[trend.trend ?? 'unknown'] ?? TREND_LABEL.unknown;

  const fmtPct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(2)}%`);

  return (
    <div className="rounded-2xl border border-stone-800/60 bg-stone-950/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-stone-400" />
          <span className="text-[10px] font-black uppercase tracking-widest text-stone-500">
            동 업종 폐업률 추세
          </span>
          <span className="text-[9px] font-bold text-stone-600 normal-case tracking-normal">
            8 분기
          </span>
        </div>
        <span
          className={`text-[10px] font-black px-2 py-0.5 rounded-full border ${tinfo.color} ${tinfo.bg} uppercase tracking-widest`}
        >
          {tinfo.label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="rounded-lg border border-stone-800/60 bg-stone-900/40 p-3">
          <div className="text-[9px] font-black uppercase tracking-widest text-stone-500 mb-1">
            현재 분기
          </div>
          <div className="text-xl font-black tabular-nums text-stone-100 tracking-tighter">
            {fmtPct(cur)}
          </div>
        </div>
        <div className="rounded-lg border border-stone-800/60 bg-stone-900/40 p-3">
          <div className="text-[9px] font-black uppercase tracking-widest text-stone-500 mb-1">
            과거 평균
          </div>
          <div className="text-xl font-black tabular-nums text-stone-300 tracking-tighter">
            {fmtPct(avg)}
          </div>
        </div>
      </div>

      <div className="h-12">
        {numericSamples.length > 1 ? (
          <Sparkline data={numericSamples} width={undefined as unknown as number} height={48} />
        ) : (
          <span className="text-[9px] text-stone-600">시계열 데이터 부족</span>
        )}
      </div>
    </div>
  );
}
