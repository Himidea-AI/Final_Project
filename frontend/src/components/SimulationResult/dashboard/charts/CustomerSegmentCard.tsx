import { Users } from 'lucide-react';
import type { CustomerSegment } from '../../../../types';
import { formatKrw } from '../utils/formatters';

interface Props {
  segment: CustomerSegment | null | undefined;
}

export function CustomerSegmentCard({ segment }: Props) {
  if (!segment) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card/40 p-6 text-center">
        <Users className="mx-auto text-muted-foreground mb-2" size={24} />
        <p className="text-xs text-muted-foreground">
          타겟 고객 프로필을 입력하면 분석 결과가 표시됩니다
        </p>
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
    <div className="bg-card/40 border border-border/60 rounded-3xl p-8 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-black text-foreground flex items-center gap-2 uppercase tracking-tight">
          <Users size={16} className="text-primary" /> 타겟 고객 매출 기여
          <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
            customer_revenue
          </span>
        </h4>
        <div className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tabular-nums">
          전체의 {ratioPct}%
        </div>
      </div>

      {/* 자연어 요약 */}
      <p className="text-[0.8125rem] text-foreground leading-relaxed">{segment.profile_summary}</p>

      {/* 매출 요약 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card/40 border border-border rounded-xl p-4">
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
            세그먼트 매출
          </div>
          <div className="text-2xl font-black text-primary tabular-nums tracking-tighter">
            {sales != null ? `₩${formatKrw(sales)}` : '—'}
          </div>
        </div>
        <div className="bg-card/40 border border-border rounded-xl p-4">
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
            식별 매출
          </div>
          <div className="text-2xl font-black text-foreground tabular-nums tracking-tighter">
            {identified != null ? `₩${formatKrw(identified)}` : '—'}
          </div>
        </div>
        <div className="bg-card/40 border border-border rounded-xl p-4">
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
            전체 매출 기준
          </div>
          <div className="text-2xl font-black text-muted-foreground tabular-nums tracking-tighter">
            {totalRef != null ? `₩${formatKrw(totalRef)}` : '—'}
          </div>
        </div>
      </div>

      {/* dimension 비율 (상위 6개) */}
      {dimensions.length > 0 && (
        <div>
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-3">
            차원별 비율
          </div>
          <div className="space-y-2">
            {dimensions.map(({ key, value }) => (
              <div key={key} className="flex items-center gap-3">
                <span className="text-[0.6875rem] font-bold text-muted-foreground w-32 truncate">
                  {key}
                </span>
                <div className="flex-1 bg-card h-1.5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, value * 100)}%` }}
                  />
                </div>
                <span className="text-[0.6875rem] font-black text-foreground tabular-nums w-12 text-right">
                  {(value * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 한계 disclaimer — BEP 인건비 면책 패턴(api-contract §3.7).
          customer_revenue MLPPredictor 모델 자체 제약을 결과와 함께 명시. */}
      <div className="pt-4 border-t border-border/50 space-y-1">
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 4차원(연령·성별·시간대·요일) 독립 가정(곱셈)으로 산출됩니다 — 실제 분포와 차이 가능,
          유동인구 실측치로 일부 보정.
        </p>
        <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 학습 데이터는 마포구 16동 × 10업종 · 2019~2024 4분기 기준. 다른 조합/연도는 외삽 결과.
        </p>
      </div>
    </div>
  );
}
