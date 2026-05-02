/**
 * TrendSparklinesPanel — 거시·트렌드 환경 (3 Sparkline + KPI)
 *
 * 데이터: trend_forecast.industry_trend.samples / dong_trend.samples / macro.samples
 * 디자인: 3-column bento grid, 각 셀에 헤더 + 현재값 + 변화 + Sparkline
 * Best practice: KPI 숫자는 큰 글씨, 변화율 ± 색상, sparkline은 보조 시각
 */

import { TrendingUp, MapPin, Landmark, AlertTriangle } from 'lucide-react';
import { Sparkline } from './Sparkline';

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
  delta?: number | null;
  deltaUnit?: string;
  /** delta 색 의미 반전 — 거시 지표(예: 금리 인상=부정)에 사용. 기본 false. */
  deltaInverted?: boolean;
  /** delta > 0 일 때 옆에 작게 표시할 의미 캡션 (예: '↑ 부담↑'). 너무 길면 패스. */
  deltaCaption?: string;
  samples?: number[];
  stalenessNote?: string;
  /** 스크린리더용 sparkline 설명 (예: "동 트렌드 8분기 추이") */
  sparklineAriaLabel?: string;
}

function TrendCell({
  icon,
  label,
  subLabel,
  value,
  unit,
  delta,
  deltaUnit,
  deltaInverted = false,
  deltaCaption,
  samples,
  stalenessNote,
  sparklineAriaLabel,
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
    <div className="rounded-2xl border border-border bg-secondary p-4 flex flex-col gap-2 min-h-[180px]">
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
      <div
        className="mt-1 -mx-1 h-8"
        role="img"
        aria-label={sparklineAriaLabel ?? `${label} 시계열`}
      >
        {samples && samples.length > 1 ? (
          <Sparkline data={samples} height={32} />
        ) : (
          <span className="text-xs text-muted-foreground">시계열 데이터 부족</span>
        )}
      </div>
      {stalenessNote && (
        <div className="flex items-center gap-1.5 rounded-md bg-warning/10 border border-warning/20 px-2 py-1 mt-1">
          <AlertTriangle size={11} className="text-warning shrink-0" />
          <span className="text-xs text-warning leading-snug">{stalenessNote}</span>
        </div>
      )}
    </div>
  );
}

export function TrendSparklinesPanel({ industryTrend, dongTrend, macro }: Props) {
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

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-stretch">
        <TrendCell
          icon={<TrendingUp size={16} className="text-chart-1" />}
          label="업종 트렌드"
          subLabel={industryTrend?.industry ?? '—'}
          value={
            industryTrend?.current_ratio != null
              ? Math.round(industryTrend.current_ratio).toString()
              : null
          }
          unit="/100"
          delta={industryTrend?.yoy_change_pct ?? null}
          deltaUnit="%"
          samples={industryTrend?.samples}
          sparklineAriaLabel={`업종 트렌드 ${industryTrend?.samples?.length ?? 0}개월 추이`}
        />
        <TrendCell
          icon={<MapPin size={16} className="text-chart-3" />}
          label="동 트렌드"
          subLabel={dongTrend?.dong_name ?? '—'}
          value={formatScore(dongTrend?.recent_score)}
          unit="/100"
          delta={dongTrend?.slope_pct ?? null}
          deltaUnit="%"
          samples={dongTrend?.samples}
          stalenessNote={dongTrend?.data_staleness_note}
          sparklineAriaLabel={`동 트렌드 ${dongTrend?.samples?.length ?? 0}분기 추이`}
        />
        <TrendCell
          icon={<Landmark size={16} className="text-chart-4" />}
          label="한국은행 기준금리"
          subLabel={macro?.base_rate_trend ?? '—'}
          value={macro?.current_base_rate != null ? macro.current_base_rate.toFixed(2) : null}
          unit="%"
          delta={macroDelta}
          deltaUnit="%p"
          deltaInverted
          deltaCaption="부담↑"
          samples={macro?.samples}
          sparklineAriaLabel={`기준금리 ${macro?.samples?.length ?? 0}개월 추이`}
        />
      </div>
      <p className="text-[0.6875rem] text-muted-foreground leading-relaxed">
        업종/동 트렌드 = naver 검색 기반 0~100 지수. 변동률(%) = YoY/기간 시작 대비. 기준금리
        변동(%p) = 절대 변화(퍼센트포인트).
      </p>
    </div>
  );
}
