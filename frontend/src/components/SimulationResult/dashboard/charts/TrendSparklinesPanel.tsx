/**
 * TrendSparklinesPanel — 거시·트렌드 환경 (3 Sparkline + KPI)
 *
 * 데이터: trend_forecast.industry_trend.samples / dong_trend.samples / macro.samples
 * 디자인: 3-column bento grid, 각 셀에 헤더 + 현재값 + 변화 + Sparkline
 * Best practice: KPI 숫자는 큰 글씨, 변화율 ± 색상, sparkline은 보조 시각
 */

import { TrendingUp, MapPin, Landmark } from 'lucide-react';
import { Sparkline } from './Sparkline';

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
  samples?: number[];
}

function TrendCell({ icon, label, subLabel, value, unit, delta, deltaUnit, samples }: CellProps) {
  const deltaPositive = delta != null && delta > 0;
  const deltaColor =
    delta == null
      ? 'text-muted-foreground'
      : delta > 0
        ? 'text-success'
        : delta < 0
          ? 'text-danger'
          : 'text-muted-foreground';

  return (
    <div className="rounded-2xl border border-border/60 bg-card/40 p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {icon}
        <div className="flex-1 min-w-0">
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground truncate">
            {label}
          </div>
          {subLabel && (
            <div className="text-[0.625rem] font-bold text-muted-foreground truncate">
              {subLabel}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-black tabular-nums text-foreground tracking-tighter">
          {value ?? '—'}
          {value && unit && (
            <span className="text-[0.6875rem] font-bold text-muted-foreground ml-1">{unit}</span>
          )}
        </span>
        {delta != null && (
          <span className={`text-[0.6875rem] font-black tabular-nums ${deltaColor}`}>
            {deltaPositive ? '+' : ''}
            {delta.toFixed(1)}
            {deltaUnit ?? '%'}
          </span>
        )}
      </div>
      <div className="mt-1 -mx-1 h-7">
        {samples && samples.length > 1 ? (
          <Sparkline data={samples} height={28} />
        ) : (
          <span className="text-[0.5625rem] text-muted-foreground">시계열 데이터 부족</span>
        )}
      </div>
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

  return (
    <div className="grid grid-cols-3 gap-3">
      <TrendCell
        icon={<TrendingUp size={14} className="text-primary" />}
        label="업종 트렌드"
        subLabel={industryTrend?.industry ?? '—'}
        value={
          industryTrend?.current_ratio != null
            ? Math.round(industryTrend.current_ratio).toString()
            : null
        }
        unit="pt"
        delta={industryTrend?.yoy_change_pct ?? null}
        deltaUnit="%"
        samples={industryTrend?.samples}
      />
      <TrendCell
        icon={<MapPin size={14} className="text-primary" />}
        label="동 트렌드"
        subLabel={dongTrend?.dong_name ?? '—'}
        value={formatScore(dongTrend?.recent_score)}
        unit="pt"
        delta={dongTrend?.slope_pct ?? null}
        deltaUnit="%"
        samples={dongTrend?.samples}
      />
      <TrendCell
        icon={<Landmark size={14} className="text-warning" />}
        label="한국은행 기준금리"
        subLabel={macro?.base_rate_trend ?? '—'}
        value={macro?.current_base_rate != null ? macro.current_base_rate.toFixed(2) : null}
        unit="%"
        delta={null}
        samples={macro?.samples}
      />
    </div>
  );
}
