import { Users } from 'lucide-react';
import type { CustomerSegment } from '../../../../types';
import { formatKrw } from '../utils/formatters';

interface Props {
  segment: CustomerSegment | null | undefined;
  monthlyRev?: number | null;
}

export function CustomerSegmentCard({ segment }: Props) {
  if (!segment) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center">
        <Users className="mx-auto text-stone-600 mb-2" size={24} />
        <p className="text-xs text-stone-500">타겟 고객 프로필을 입력하면 분석 결과가 표시됩니다</p>
      </div>
    );
  }

  const ratioPct = (segment.segment_ratio * 100).toFixed(1);
  const sales = segment.segment_sales;
  const identified = segment.identified_sales;
  const totalRef = segment.total_sales_ref;

  // dimension_ratios에서 상위 6개 차원 추출
  const dimensions = Object.entries(segment.dimension_ratios)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-black text-stone-100 flex items-center gap-2 uppercase tracking-tight">
          <Users size={16} className="text-indigo-400" /> 타겟 고객 매출 기여
          <span className="text-[10px] font-black text-stone-500 normal-case tracking-normal">
            customer_revenue
          </span>
        </h4>
        <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tabular-nums">
          전체의 {ratioPct}%
        </div>
      </div>

      {/* 자연어 요약 */}
      <p className="text-[13px] text-stone-300 leading-relaxed">{segment.profile_summary}</p>

      {/* 매출 요약 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-stone-950/40 border border-stone-800 rounded-xl p-4">
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
            세그먼트 매출
          </div>
          <div className="text-2xl font-black text-indigo-400 tabular-nums tracking-tighter">
            {sales != null ? `₩${formatKrw(sales)}` : '—'}
          </div>
        </div>
        <div className="bg-stone-950/40 border border-stone-800 rounded-xl p-4">
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
            식별 매출
          </div>
          <div className="text-2xl font-black text-stone-100 tabular-nums tracking-tighter">
            {identified != null ? `₩${formatKrw(identified)}` : '—'}
          </div>
        </div>
        <div className="bg-stone-950/40 border border-stone-800 rounded-xl p-4">
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-2">
            전체 매출 기준
          </div>
          <div className="text-2xl font-black text-stone-400 tabular-nums tracking-tighter">
            {totalRef != null ? `₩${formatKrw(totalRef)}` : '—'}
          </div>
        </div>
      </div>

      {/* dimension 비율 (상위 6개) */}
      {dimensions.length > 0 && (
        <div>
          <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-3">
            차원별 비율
          </div>
          <div className="space-y-2">
            {dimensions.map(({ key, value }) => (
              <div key={key} className="flex items-center gap-3">
                <span className="text-[11px] font-bold text-stone-400 w-32 truncate">{key}</span>
                <div className="flex-1 bg-stone-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 transition-all"
                    style={{ width: `${Math.min(100, value * 100)}%` }}
                  />
                </div>
                <span className="text-[11px] font-black text-stone-300 tabular-nums w-12 text-right">
                  {(value * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
