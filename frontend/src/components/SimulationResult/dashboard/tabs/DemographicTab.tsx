/**
 * DemographicTab — 인구·고객 전용 탭
 *
 * SummaryTab에서 분리. 본부 영업팀이 "이 상권의 고객층"을 가맹점주에게
 * 설명할 때 사용하는 드릴다운 뷰.
 *
 * 구성:
 * 1) 상단: 인구 구성 (Core Donut + StackedAge + Weekday/Weekend + optional Heatmap placeholder)
 * 2) 하단: 인구 심층 리포트 (MetricBox 4 + narrative + match_rationale)
 */

import { Users } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import { MetricBox } from '../shared/MetricBox';
import { INCOME_MAP, TREND_MAP, safeMap, mapGender } from '../utils/mappings';
import { formatPeakHours } from '../utils/formatters';
import { CoreDemographicDonut } from '../charts/CoreDemographicDonut';
import { WeekdayWeekendBar } from '../charts/WeekdayWeekendBar';
import { StackedAgeBar } from '../charts/StackedAgeBar';
import { CustomerSegmentCard } from '../charts/CustomerSegmentCard';

interface Props {
  simResult: SimulationOutput;
}

export function DemographicTab({ simResult }: Props) {
  const demo = simResult.demographic_report ?? null;
  const core = demo?.core_demographic;
  const corePct =
    core && typeof core.share === 'number' ? `${(core.share * 100).toFixed(1)}%` : null;
  const peak = demo?.peak_consumption_hours?.[0];
  const income = safeMap(INCOME_MAP, demo?.area_income_level, INCOME_MAP.unknown);
  const trend = safeMap(TREND_MAP, demo?.population_trend, TREND_MAP.unknown);
  const match = demo?.brand_target_match_score;
  const narrative = demo?.narrative;
  const rationale = demo?.match_rationale;

  const hasAnyComposition =
    core ||
    (demo?.top_3_age_groups && demo.top_3_age_groups.length > 0) ||
    typeof demo?.weekday_weekend_ratio === 'number';

  const hasReport = Boolean(
    core || peak || demo?.area_income_level || demo?.population_trend || match != null,
  );

  const hasPeakMatrix = Array.isArray(demo?.peak_hour_matrix) && demo.peak_hour_matrix.length === 7;

  const customerSegment = simResult.customer_segment ?? null;
  const hasCustomerSegment = Boolean(customerSegment);

  if (!hasAnyComposition && !hasReport && !hasCustomerSegment) {
    return (
      <div className="bg-stone-900/30 border border-dashed border-stone-800 rounded-3xl p-10 text-center">
        <Users className="mx-auto mb-3 text-stone-600" size={22} />
        <div className="text-sm font-bold text-stone-400">인구 심층 분석 데이터 없음</div>
        <div className="mt-1 text-xs text-stone-500">
          demographic_depth 에이전트 분석이 완료되면 이 탭이 채워집니다.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 인구 구성 — Donut + StackedAge + WeekdayWeekend (+ optional Heatmap) */}
      {hasAnyComposition && (
        <div className="bg-stone-900/30 border border-stone-800/40 rounded-3xl p-6">
          <div className="mb-4 flex items-center gap-3">
            <h3 className="text-sm font-black text-stone-100 uppercase tracking-tight">
              인구 구성 상세
            </h3>
            <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
              demographic_depth
            </span>
          </div>
          <div className={`grid gap-6 ${hasPeakMatrix ? 'grid-cols-4' : 'grid-cols-3'}`}>
            <CoreDemographicDonut core={demo?.core_demographic ?? null} />
            <StackedAgeBar groups={demo?.top_3_age_groups ?? []} />
            <WeekdayWeekendBar ratio={demo?.weekday_weekend_ratio} />
            {hasPeakMatrix && (
              <div className="flex h-[140px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
                Calendar Heatmap — Track B #106 구현 대기
              </div>
            )}
          </div>
        </div>
      )}

      {/* 인구 심층 분석 리포트 */}
      {hasReport && (
        <div className="bg-stone-900/30 border border-stone-800/40 rounded-3xl p-8">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic text-left tracking-tight">
              <Users size={22} className="text-indigo-400" /> 인구 심층 분석 리포트
              <span className="text-[11px] font-black text-stone-500 uppercase tracking-widest not-italic">
                demographic_report
              </span>
            </h3>
            {match != null && (
              <div className="px-4 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tracking-widest tabular-nums">
                브랜드 적합도 {Math.round(match)}
              </div>
            )}
          </div>

          <div className="grid grid-cols-4 gap-6 mb-8 text-left">
            <MetricBox
              label="주요 소비 연령대"
              val={core ? `${core.age} ${mapGender(core.gender)}` : '—'}
              sub={corePct ? `전체 방문객의 ${corePct} 차지` : 'core_demographic 기준'}
            />
            <MetricBox
              label="피크 시간대"
              val={peak ? formatPeakHours(peak) : '—'}
              sub="peak_consumption_hours[0]"
            />
            <MetricBox label="지역 소득 수준" val={income} sub="area_income_level 기준" />
            <MetricBox label="인구 증감 추세" val={trend} sub="population_trend 기준" />
          </div>

          {(narrative || rationale) && (
            <div className="p-6 bg-stone-950/40 border border-stone-800 rounded-2xl text-left space-y-2">
              {narrative && (
                <p className="text-sm text-stone-300 leading-relaxed font-medium">{narrative}</p>
              )}
              {rationale && (
                <p className="text-xs text-stone-500 leading-relaxed italic">
                  매칭 근거: {rationale}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* [customer_revenue P1-C] 타겟 고객 매출 기여 카드 */}
      <CustomerSegmentCard segment={customerSegment} />
    </div>
  );
}
