import { Users } from 'lucide-react';
import type { CustomerSegment } from '../../../../types';
import { formatKrw } from '../utils/formatters';

interface Props {
  segment: CustomerSegment | null | undefined;
}

/** dimension_ratios 키 → 한국어 라벨. backend customer_segment 의 4 차원 (연령/성별/시간대/요일).
 *  키 형태가 _ratio suffix 유무 두 가지 다 와도 매칭되도록 양쪽 등록.
 *  미정의 키는 raw 그대로 fallback (디버그 단서).
 *
 *  profile_summary 자연어 후처리에도 사용 — backend 가 "20대+30대 time_06_11" 같은
 *  raw key 혼합 텍스트를 보내면 frontend 에서 정규식으로 한국어 + 연결사(·) 로 치환. */
const DIMENSION_LABEL: Record<string, string> = {
  // 연령
  age_10: '10대',
  age_20: '20대',
  age_30: '30대',
  age_40: '40대',
  age_50: '50대',
  age_60_above: '60대 이상',
  age_10_ratio: '10대',
  age_20_ratio: '20대',
  age_30_ratio: '30대',
  age_40_ratio: '40대',
  age_50_ratio: '50대',
  age_60_above_ratio: '60대 이상',
  // 성별
  male: '남성',
  female: '여성',
  male_ratio: '남성',
  female_ratio: '여성',
  gender_male: '남성',
  gender_female: '여성',
  gender_male_ratio: '남성',
  gender_female_ratio: '여성',
  // 시간대 (6 buckets)
  time_00_06: '심야',
  time_06_11: '오전',
  time_11_14: '점심',
  time_14_17: '오후',
  time_17_21: '저녁',
  time_21_24: '야간',
  time_00_06_ratio: '심야',
  time_06_11_ratio: '오전',
  time_11_14_ratio: '점심',
  time_14_17_ratio: '오후',
  time_17_21_ratio: '저녁',
  time_21_24_ratio: '야간',
  // 요일
  weekday: '평일',
  weekend: '주말',
  weekday_ratio: '평일',
  weekend_ratio: '주말',
};

/** profile_summary 텍스트 안 raw key 를 한국어로 + "+" 기호를 가운뎃점(·) 으로 치환.
 *  긴 키(time_06_11_ratio) 가 짧은 키(time_06_11) 보다 먼저 매칭되도록 길이 내림차순 정렬.
 *  word boundary(\b) 로 키가 다른 단어 부분에 매칭되는 회귀 차단. */
function humanizeProfileSummary(text: string): string {
  let out = text;
  const keys = Object.keys(DIMENSION_LABEL).sort((a, b) => b.length - a.length);
  for (const key of keys) {
    const pattern = new RegExp(`\\b${key}\\b`, 'g');
    out = out.replace(pattern, DIMENSION_LABEL[key]);
  }
  // "+" 양 옆에 한글/영숫자 있을 때 가운뎃점으로 (예: "20대+30대" → "20대·30대").
  out = out.replace(/([가-힣\w)])\s*\+\s*([가-힣\w(])/g, '$1·$2');
  return out;
}

export function CustomerSegmentCard({ segment }: Props) {
  if (!segment) {
    // Layer 2 outer card — panel(cool gray) 위에서 명확히 떠 있는 white surface.
    // 헤더는 일반 모드와 동일 위계로 유지 → 데이터 없어도 "칸"이 사라지지 않음.
    return (
      <div className="rounded-3xl border border-border bg-card p-8">
        <h3 className="mb-6 flex items-center gap-3 text-xl font-black italic leading-none tracking-tight text-foreground">
          <Users className="text-primary" /> 타겟 고객 매출 기여
        </h3>
        <div className="rounded-2xl border border-dashed border-border bg-secondary p-10 text-center">
          <Users className="mx-auto mb-3 text-muted-foreground" size={28} />
          <p className="text-sm font-bold text-foreground">타겟 고객 프로필 미입력</p>
          <p className="mt-1 text-xs text-muted-foreground">
            연령·성별·시간대·요일 chip 을 1개 이상 선택하면 세그먼트 매출 분석이 표시됩니다.
          </p>
        </div>
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
    <div className="rounded-3xl border border-border bg-card p-8 space-y-6">
      {/* 헤더 — 분기별 예상 매출과 동일 위계 */}
      <div className="flex items-center justify-between gap-4">
        <h3 className="flex items-center gap-3 text-xl font-black italic leading-none tracking-tight text-foreground">
          <Users className="text-primary" /> 타겟 고객 매출 기여
        </h3>
        <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
          전체의 {ratioPct}%
        </div>
      </div>

      {/* 자연어 요약 — backend raw key("time_06_11" 등) + "+" 혼합 텍스트를 한국어/가운뎃점으로 후처리. */}
      <p className="text-[0.8125rem] text-foreground leading-relaxed">
        {humanizeProfileSummary(segment.profile_summary)}
      </p>

      {/* 매출 요약 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-secondary p-4">
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
            세그먼트 매출
          </div>
          <div className="text-2xl font-black text-primary tabular-nums tracking-tighter">
            {sales != null ? `₩${formatKrw(sales)}` : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-secondary p-4">
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mb-2">
            식별 매출
          </div>
          <div className="text-2xl font-black text-foreground tabular-nums tracking-tighter">
            {identified != null ? `₩${formatKrw(identified)}` : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-secondary p-4">
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
                  {DIMENSION_LABEL[key] ?? key}
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
