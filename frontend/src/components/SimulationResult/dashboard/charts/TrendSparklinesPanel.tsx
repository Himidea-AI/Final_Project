/**
 * TrendSparklinesPanel — 거시·트렌드 환경 (3 KPI 카드)
 *
 * 데이터: trend_forecast.industry_trend / dong_trend / macro
 * 디자인: 3-column bento grid, 각 셀에 헤더 + 현재값 + 변화 + valueDescription
 * 2026-05-02: sparkline 제거(가독성 개선), 동 검색량에 16동 중 N위 표시,
 *             하단 통합 캡션 제거(셀별 valueDescription 으로 충분).
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
  // §3.7: backend 가 실제로 보내는 필드만 prop 으로 받음.
  // dong_trend.data_staleness_note 만 backend 가 emit (naver_trend_quarterly 2024 Q4 stale).
  dongTrend?: {
    dong_name?: string;
    recent_score?: number | null;
    slope_pct?: number | null;
    samples?: number[];
    data_staleness_note?: string;
  } | null;
  /** 마포 16동 중 winner 동의 trend_score 기준 순위 (district_rankings 에서 계산). */
  dongRank?: { rank: number; total: number } | null;
  macro?: {
    current_base_rate?: number | null;
    base_rate_trend?: string;
    samples?: number[];
  } | null;
}

interface CellProps {
  icon: React.ReactNode;
  label: string;
  subLabel?: string;
  value: string | null;
  unit?: string;
  /** 큰 숫자 바로 아래 작은 글씨로 표시되는 데이터 정의. */
  valueDescription?: string;
  delta?: number | null;
  deltaUnit?: string;
  /** delta 색 의미 반전 — 거시 지표(예: 금리 인상=부정)에 사용. 기본 false. */
  deltaInverted?: boolean;
  /** delta > 0 일 때 옆에 작게 표시할 의미 캡션 (예: '↑ 부담↑'). 너무 길면 패스. */
  deltaCaption?: string;
  stalenessNote?: string;
}

function TrendCell({
  icon,
  label,
  subLabel,
  value,
  unit,
  valueDescription,
  delta,
  deltaUnit,
  deltaInverted = false,
  deltaCaption,
  stalenessNote,
}: CellProps) {
  const deltaPositive = delta != null && delta > 0;
  // 기본: +값=success(성장), -값=danger(하락).
  // deltaInverted: +값=danger(부담↑), -값=success(완화).
  const deltaColor =
    delta == null
      ? 'text-muted-foreground'
      : delta > 0
        ? deltaInverted
          ? 'text-danger'
          : 'text-success'
        : delta < 0
          ? deltaInverted
            ? 'text-success'
            : 'text-danger'
          : 'text-muted-foreground';

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
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xl font-black tabular-nums text-foreground tracking-tighter">
          {value ?? '—'}
          {value && unit && (
            <span className="text-xs font-bold text-muted-foreground ml-1">{unit}</span>
          )}
        </span>
        {delta != null && (
          <span className="flex items-baseline gap-1 min-w-0">
            <span className={`text-[0.75rem] font-black tabular-nums shrink-0 ${deltaColor}`}>
              {deltaPositive ? '+' : ''}
              {delta.toFixed(1)}
              {deltaUnit ?? '%'}
            </span>
            {deltaPositive && deltaCaption && (
              <span className={`text-[0.625rem] font-bold truncate ${deltaColor}`}>
                {deltaCaption}
              </span>
            )}
          </span>
        )}
      </div>
      {valueDescription && (
        <div className="text-[0.625rem] leading-snug text-muted-foreground -mt-1">
          {valueDescription}
        </div>
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

export function TrendSparklinesPanel({ industryTrend, dongTrend, dongRank, macro }: Props) {
  const hasAny =
    (industryTrend?.samples && industryTrend.samples.length > 0) ||
    (dongTrend?.samples && dongTrend.samples.length > 0) ||
    (macro?.samples && macro.samples.length > 0);

  if (!hasAny) {
    return null;
  }

  const formatScore = (v: number | null | undefined) =>
    v == null ? null : Math.round(v).toString();

  // 기준금리 절대 변동(퍼센트포인트) — samples 첫/마지막 차이.
  const macroDelta =
    macro?.samples && macro.samples.length >= 2
      ? macro.samples[macro.samples.length - 1] - macro.samples[0]
      : null;

  // 동 검색량 valueDescription 을 N위 정보와 합쳐 동적 생성.
  // 데이터 출처가 NAVER 분기별 평균 (각 동 자체 시계열 max=100 기준) 이므로
  // 동 간 직접 비교는 의미 제한적 — N위 라벨이 그 한계를 보완.
  const dongValueDesc = dongRank
    ? `마포 ${dongRank.total}동 중 ${dongRank.rank}위 · NAVER 분기별 검색량 평균`
    : 'NAVER 분기별 검색량 평균 · 동 키워드별 자체 시계열 최댓값=100 기준';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-stretch">
      <TrendCell
        icon={<TrendingUp size={16} className="text-chart-1" />}
        label="업종 검색량 추이"
        subLabel={industryTrend?.industry ?? '—'}
        value={
          industryTrend?.current_ratio != null
            ? Math.round(industryTrend.current_ratio).toString()
            : null
        }
        unit="/100"
        valueDescription="NAVER DataLab · 24개월 중 최댓값=100 기준 · 최근 월값"
        delta={industryTrend?.yoy_change_pct ?? null}
        deltaUnit="%"
      />
      <TrendCell
        icon={<MapPin size={16} className="text-chart-3" />}
        label="동 검색량 추이"
        subLabel={dongTrend?.dong_name ?? '—'}
        value={formatScore(dongTrend?.recent_score)}
        unit="/100"
        valueDescription={dongValueDesc}
        delta={dongTrend?.slope_pct ?? null}
        deltaUnit="%"
        stalenessNote={dongTrend?.data_staleness_note}
      />
      <TrendCell
        icon={<Landmark size={16} className="text-chart-4" />}
        label="한국은행 기준금리"
        subLabel={macro?.base_rate_trend ?? '—'}
        value={macro?.current_base_rate != null ? macro.current_base_rate.toFixed(2) : null}
        unit="%"
        valueDescription="ECOS API · 월별 기준금리 · 인상 시 창업 자금 부담 ↑"
        delta={macroDelta}
        deltaUnit="%p"
        deltaInverted
        deltaCaption="부담↑"
      />
    </div>
  );
}
