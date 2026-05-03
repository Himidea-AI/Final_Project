/**
 * TrendSparklinesPanel — 거시·트렌드 환경 (3 의사결정 신호 카드)
 *
 * 데이터: trend_forecast.industry_trend / dong_trend / macro
 * 2026-05-03: 절대 수치 노출 → 비즈니스 의사결정 신호로 전환.
 *   추천 신뢰도 보호: winner 의 약한 절대 점수가 그대로 보이지 않도록 라벨 중심.
 *   1) 업종 검색량  → "업종 진입 시점"   (유리/관망/신중)
 *   2) 동 검색량    → "상권 라이프사이클" (성장/성숙/안정/잠재)
 *   3) 기준금리     → "창업 금융 환경"   (우호적/보통/부담)
 *   raw 수치(yoy, slope, 금리·변동)는 캡션 근거로 보조 노출.
 */

import { TrendingUp, MapPin, Landmark, AlertTriangle } from 'lucide-react';

interface Props {
  industryTrend?: {
    industry?: string;
    current_ratio?: number | null;
    yoy_change_pct?: number | null;
    direction?: string;
    samples?: number[];
  } | null;
  dongTrend?: {
    dong_name?: string;
    recent_score?: number | null;
    slope_pct?: number | null;
    samples?: number[];
    data_staleness_note?: string;
  } | null;
  /** 마포 16동 중 winner 동의 trend_score 기준 순위. 라이프사이클 분류용. */
  dongRank?: { rank: number; total: number } | null;
  macro?: {
    current_base_rate?: number | null;
    base_rate_trend?: string;
    samples?: number[];
  } | null;
}

type SignalTone = 'positive' | 'neutral' | 'negative';

interface CellProps {
  icon: React.ReactNode;
  label: string;
  subLabel?: string;
  /** 큰 글씨로 표시되는 의사결정 라벨. */
  signal: string;
  /** 라벨 톤 — 색상 결정. positive=success, neutral=primary, negative=warning. */
  tone: SignalTone;
  /** 라벨 바로 아래 핵심 raw 수치 (예: "YoY -53.4%", "8분기 +1.2%", "3.50% (12개월 -0.25%p)"). */
  metric?: string;
  /** 메트릭 아래 비즈니스 해석 한 줄. */
  rationale?: string;
  stalenessNote?: string;
}

const TONE_CLASSES: Record<SignalTone, string> = {
  positive: 'text-success',
  neutral: 'text-primary',
  negative: 'text-warning',
};

function TrendCell({
  icon,
  label,
  subLabel,
  signal,
  tone,
  metric,
  rationale,
  stalenessNote,
}: CellProps) {
  return (
    <div className="rounded-2xl border border-border bg-secondary p-4 flex flex-col gap-2 min-h-[140px]">
      <div className="flex items-center gap-2">
        {icon}
        <div className="flex-1 min-w-0">
          <div className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground truncate">
            {label}
          </div>
          {subLabel && <div className="text-xs font-bold text-foreground truncate">{subLabel}</div>}
        </div>
      </div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={`text-2xl font-black tracking-tighter ${TONE_CLASSES[tone]}`}>
          {signal}
        </span>
        {metric && (
          <span className="text-xs font-bold tabular-nums text-muted-foreground">{metric}</span>
        )}
      </div>
      {rationale && (
        <div className="text-[0.6875rem] leading-snug text-muted-foreground">{rationale}</div>
      )}
      {stalenessNote && (
        <div className="flex items-center gap-1.5 rounded-md bg-warning/10 border border-warning/20 px-2 py-1 mt-auto">
          <AlertTriangle size={11} className="text-warning shrink-0" />
          <span className="text-xs text-warning leading-snug">{stalenessNote}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 판정 로직 — raw 데이터 → 비즈니스 신호 라벨
// ---------------------------------------------------------------------------

/** 업종 진입 시점 — yoy_change_pct 기준. */
function classifyIndustryEntry(yoyPct: number | null | undefined): {
  signal: string;
  tone: SignalTone;
  metric: string | undefined;
  rationale: string;
} {
  if (yoyPct == null) {
    return {
      signal: '관망',
      tone: 'neutral',
      metric: undefined,
      rationale: '검색량 추세 데이터 부족 — 다른 지표 종합 판단 권장',
    };
  }
  const pct = yoyPct.toFixed(1);
  const sign = yoyPct >= 0 ? '+' : '';
  const metric = `YoY ${sign}${pct}%`;
  if (yoyPct > 5) {
    return {
      signal: '유리',
      tone: 'positive',
      metric,
      rationale: '시장 관심도 상승 국면 — 진입 타이밍 우호적',
    };
  }
  if (yoyPct < -5) {
    return {
      signal: '신중',
      tone: 'negative',
      metric,
      rationale: '시장 관심도 둔화 — 차별화 전략 필수',
    };
  }
  return {
    signal: '관망',
    tone: 'neutral',
    metric,
    rationale: '안정 국면 — 차별화 포지션 검토',
  };
}

/** 상권 라이프사이클 — dongRank(상대 위치) + slope_pct(추세) 조합. */
function classifyLifecycle(
  rank: number | null | undefined,
  total: number | null | undefined,
  slopePct: number | null | undefined,
): { signal: string; tone: SignalTone; metric: string | undefined; rationale: string } {
  // 결측 또는 rank 매칭 실패 → 잠재형 (미개척 = 광고 선점 기회로 framing)
  if (rank == null || total == null || total === 0) {
    return {
      signal: '잠재형',
      tone: 'positive',
      metric: undefined,
      rationale: '검색 데이터 노출 적음 — 경쟁 인지도 낮음, 광고 선점 기회',
    };
  }
  const ratio = rank / total;
  const slope = slopePct ?? 0;
  const slopeStr = `${slope >= 0 ? '+' : ''}${slope.toFixed(1)}%`;
  const metric = slopePct != null ? `${rank}/${total}위 · 8분기 ${slopeStr}` : `${rank}/${total}위`;

  // 상위 1/3 + 상승 → 성숙형 (검증된 핫스팟)
  if (ratio <= 1 / 3 && slope > 0) {
    return {
      signal: '성숙형',
      tone: 'positive',
      metric,
      rationale: '검색 활발 — 검증된 상권, 차별화 전략 권장',
    };
  }
  // 하위 1/3 + 상승 추세 → 성장형 (저비용 + 트렌드 상승)
  if (ratio > 2 / 3 && slope > 5) {
    return {
      signal: '성장형',
      tone: 'positive',
      metric,
      rationale: '저비용 진입 + 트렌드 상승 단계',
    };
  }
  // 변동성 작음 → 안정형 (단골)
  if (Math.abs(slope) <= 5) {
    return {
      signal: '안정형',
      tone: 'neutral',
      metric,
      rationale: '변동성 낮음 — 단골 중심, 매출 예측 신뢰도 ↑',
    };
  }
  // 그 외 → 잠재형 (저인지)
  return {
    signal: '잠재형',
    tone: 'positive',
    metric,
    rationale: '경쟁 인지 낮음 — 마케팅 선점 가능',
  };
}

/** 창업 금융 환경 — 12개월 변동(macroDelta) + 현재 금리. */
function classifyFinancing(
  currentRate: number | null | undefined,
  delta: number | null | undefined,
): { signal: string; tone: SignalTone; metric: string | undefined; rationale: string } {
  if (currentRate == null) {
    return {
      signal: '보통',
      tone: 'neutral',
      metric: undefined,
      rationale: '기준금리 데이터 부족 — 자금 조달 환경 확인 권장',
    };
  }
  const rateStr = currentRate.toFixed(2);
  const deltaStr = delta != null ? `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}%p` : null;
  const metric = deltaStr ? `${rateStr}% · 12개월 ${deltaStr}` : `${rateStr}%`;

  // 금리 하락 + 절대 금리 4% 미만 → 우호적
  if (delta != null && delta <= -0.25 && currentRate < 4) {
    return {
      signal: '우호적',
      tone: 'positive',
      metric,
      rationale: '자금 조달 부담 완화 국면',
    };
  }
  // 금리 상승 또는 4% 이상 → 부담
  if ((delta != null && delta >= 0.25) || currentRate >= 4) {
    return {
      signal: '부담',
      tone: 'negative',
      metric,
      rationale: '대출 이자 부담 ↑, 초기 자본 여유 확보 권장',
    };
  }
  // 그 외 → 보통
  return {
    signal: '보통',
    tone: 'neutral',
    metric,
    rationale: '평이한 금융 환경',
  };
}

// ---------------------------------------------------------------------------
// 메인 컴포넌트
// ---------------------------------------------------------------------------

export function TrendSparklinesPanel({ industryTrend, dongTrend, dongRank, macro }: Props) {
  const hasAny =
    (industryTrend?.samples && industryTrend.samples.length > 0) ||
    (dongTrend?.samples && dongTrend.samples.length > 0) ||
    (macro?.samples && macro.samples.length > 0);

  if (!hasAny) {
    return null;
  }

  // 기준금리 절대 변동(퍼센트포인트) — samples 첫/마지막 차이.
  const macroDelta =
    macro?.samples && macro.samples.length >= 2
      ? macro.samples[macro.samples.length - 1] - macro.samples[0]
      : null;

  const industrySignal = classifyIndustryEntry(industryTrend?.yoy_change_pct);
  const lifecycleSignal = classifyLifecycle(dongRank?.rank, dongRank?.total, dongTrend?.slope_pct);
  const financingSignal = classifyFinancing(macro?.current_base_rate, macroDelta);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-stretch">
      <TrendCell
        icon={<TrendingUp size={16} className="text-chart-1" />}
        label="업종 진입 시점"
        subLabel={industryTrend?.industry ?? '—'}
        signal={industrySignal.signal}
        tone={industrySignal.tone}
        metric={industrySignal.metric}
        rationale={industrySignal.rationale}
      />
      <TrendCell
        icon={<MapPin size={16} className="text-chart-3" />}
        label="상권 라이프사이클"
        subLabel={dongTrend?.dong_name ?? '—'}
        signal={lifecycleSignal.signal}
        tone={lifecycleSignal.tone}
        metric={lifecycleSignal.metric}
        rationale={lifecycleSignal.rationale}
        stalenessNote={dongTrend?.data_staleness_note}
      />
      <TrendCell
        icon={<Landmark size={16} className="text-chart-4" />}
        label="창업 금융 환경"
        subLabel="한국은행 기준금리"
        signal={financingSignal.signal}
        tone={financingSignal.tone}
        metric={financingSignal.metric}
        rationale={financingSignal.rationale}
      />
    </div>
  );
}
