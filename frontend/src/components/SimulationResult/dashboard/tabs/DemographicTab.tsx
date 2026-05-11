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

import { Users, AlertTriangle, Lightbulb } from 'lucide-react';
import type { SimulationOutput, TargetAlignmentAlert } from '../../../../types';
import { MetricBox } from '../shared/MetricBox';
import { INCOME_MAP, TREND_MAP, safeMap, mapGender } from '../utils/mappings';
import { formatPeakHours } from '../utils/formatters';
import { CoreDemographicDonut } from '../charts/CoreDemographicDonut';
import { WeekdayWeekendBar } from '../charts/WeekdayWeekendBar';
import { StackedAgeBar } from '../charts/StackedAgeBar';

// 정렬도 점수 → 뱃지 색상 토큰. 60 미만은 빨강(즉시 재검토), 60-79 노랑(주의), 80+ 파랑(양호).
function alignmentColorClasses(score: number): string {
  if (score < 60) return 'bg-danger/10 border-danger/30 text-danger';
  if (score < 80) return 'bg-warning/10 border-warning/30 text-warning';
  return 'bg-primary/10 border-primary/20 text-primary';
}

// severity → alert row 색상 토큰.
function severityClasses(severity: TargetAlignmentAlert['severity']): {
  border: string;
  bg: string;
  text: string;
  label: string;
} {
  if (severity === 'high') {
    return {
      border: 'border-danger/40',
      bg: 'bg-danger/5',
      text: 'text-danger',
      label: '높음',
    };
  }
  if (severity === 'medium') {
    return {
      border: 'border-warning/40',
      bg: 'bg-warning/5',
      text: 'text-warning',
      label: '주의',
    };
  }
  return {
    border: 'border-border',
    bg: 'bg-card',
    text: 'text-muted-foreground',
    label: '경미',
  };
}

// dimension 영문 → 한국어 라벨.
const DIMENSION_LABEL: Record<TargetAlignmentAlert['dimension'], string> = {
  age: '연령대',
  gender: '성별',
  hours: '시간대',
  day: '요일',
  price: '객단가',
};

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
  // 사용자 입력 타겟 vs 실측 정렬도. brand_target_match_score 와 별개의 점수.
  // brand_target_match_score: 브랜드의 일반적 타겟 vs 실측
  // alignmentScore: 사용자가 시뮬 입력폼에 직접 넣은 타겟 vs 실측
  const alignmentScore = demo?.target_alignment_score ?? null;
  const alignmentAlerts = demo?.target_alignment ?? [];
  // 역제안 — high severity alert 발생 시 백엔드가 실측 기반으로 채워줌. 없으면 null.
  const reverseSuggestion = demo?.reverse_target_suggestion ?? null;

  const hasAnyComposition =
    core ||
    (demo?.top_3_age_groups && demo.top_3_age_groups.length > 0) ||
    typeof demo?.weekday_weekend_ratio === 'number';

  const hasReport = Boolean(
    core || peak || demo?.area_income_level || demo?.population_trend || match != null,
  );

  const hasPeakMatrix = Array.isArray(demo?.peak_hour_matrix) && demo.peak_hour_matrix.length === 7;

  // customer_segment 카드는 2026-05-03부로 분석 탭에서 제거됨 — ML 모델(customer_revenue MLP)
  // 결과는 /predict 영역(PredictCustomerFlowTab)에서만 노출. 카테고리 정합성 + 중복 노출 제거.
  if (!hasAnyComposition && !hasReport) {
    return (
      <div className="bg-card border border-dashed border-border rounded-3xl p-10 text-center">
        <Users className="mx-auto mb-3 text-muted-foreground" size={22} />
        <div className="text-sm font-bold text-muted-foreground">인구 심층 분석 데이터 없음</div>
        <div className="mt-1 text-xs text-muted-foreground">
          demographic_depth 에이전트 분석이 완료되면 이 탭이 채워집니다.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 인구 구성 — Donut + StackedAge + WeekdayWeekend (+ optional Heatmap) */}
      {hasAnyComposition && (
        <div className="bg-card border border-border rounded-3xl p-6">
          <div className="mb-4 flex items-center gap-3">
            <h3 className="text-sm font-black text-foreground uppercase tracking-tight">
              인구 구성 상세
            </h3>
            <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
              demographic_depth
            </span>
          </div>
          <div className={`grid gap-6 ${hasPeakMatrix ? 'grid-cols-4' : 'grid-cols-3'}`}>
            <CoreDemographicDonut core={demo?.core_demographic ?? null} />
            <StackedAgeBar groups={demo?.top_3_age_groups ?? []} />
            <WeekdayWeekendBar ratio={demo?.weekday_weekend_ratio} />
            {hasPeakMatrix && (
              <div className="flex h-[140px] items-center justify-center rounded-2xl border border-dashed border-border text-muted-foreground text-xs">
                Calendar Heatmap — Track B #106 구현 대기
              </div>
            )}
          </div>
        </div>
      )}

      {/* 인구 심층 분석 리포트 */}
      {hasReport && (
        <div className="bg-card border border-border rounded-3xl p-8">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-xl font-black text-foreground flex items-center gap-3 italic text-left tracking-tight">
              <Users size={22} className="text-primary" /> 인구 심층 분석 리포트
              <span className="text-[0.6875rem] font-black text-muted-foreground uppercase tracking-widest not-italic">
                demographic_report
              </span>
            </h3>
            {match != null && (
              <div
                className="px-4 py-1.5 bg-primary/10 border border-primary/20 rounded-full text-[0.6875rem] font-black text-primary tracking-widest tabular-nums"
                title="브랜드의 일반적 타겟 고객층 vs 실측 매출 분포 — LLM 종합 판단"
              >
                브랜드 적합도 {Math.round(match)}
                <span className="ml-2 text-[0.5625rem] font-bold opacity-70">LLM 종합</span>
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
            <div className="p-6 bg-card border border-border rounded-2xl text-left space-y-2">
              {narrative && (
                <p className="text-sm text-foreground leading-relaxed font-medium">{narrative}</p>
              )}
              {rationale && (
                <p className="text-xs text-muted-foreground leading-relaxed italic">
                  매칭 근거: {rationale}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* 내 타겟 정렬 카드 — 브랜드 적합도와 분리.
          브랜드 적합도(LLM 종합) ≠ 내 타겟 정렬(룰엔진 5차원 평균)이라 같은 0-100 척도여도
          직접 비교 부적절. 보완 관계로 별도 카드 분리. 사용자 입력이 비어있어 점수 None 이면
          카드 자체를 안 그림. */}
      {alignmentScore != null && (
        <div className="bg-card border border-border rounded-3xl p-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-black text-foreground flex items-center gap-3 italic text-left tracking-tight">
              <Users size={22} className="text-primary" /> 내 타겟 정렬도
              <span className="text-[0.6875rem] font-black text-muted-foreground uppercase tracking-widest not-italic">
                target_alignment
              </span>
            </h3>
            <div
              className={`px-4 py-1.5 border rounded-full text-[0.6875rem] font-black tracking-widest tabular-nums ${alignmentColorClasses(
                alignmentScore,
              )}`}
              title="시뮬 입력 폼에 넣은 타겟(연령·성별·시간·요일·객단가) 대비 실측 매출 정렬도. 룰엔진 5차원 평균."
            >
              {Math.round(alignmentScore)}
              <span className="ml-2 text-[0.5625rem] font-bold opacity-70">5차원 평균</span>
            </div>
          </div>

          {/* 두 점수 의미 차이 설명 — 사용자가 같은 0-100 으로 비교하지 않도록 */}
          <p className="mb-5 text-xs text-muted-foreground leading-relaxed">
            위 <span className="font-bold text-primary">브랜드 적합도</span> 는 *브랜드의 일반적
            타겟* 이 이 입지의 실측 매출 분포와 맞는지 LLM 이 종합 판단한 점수이고, 여기
            <span className="font-bold text-primary"> 내 타겟 정렬도</span> 는 *시뮬 입력 폼에 직접
            넣은 타겟(연령·성별·시간·요일·객단가)* 5차원을 룰엔진으로 평가한 점수입니다. 같은 0-100
            척도지만 측정 방식이 달라 직접 비교는 부적절 — 두 관점을 보완적으로 함께 보세요.
          </p>

          {alignmentAlerts.length > 0 && (
            <div className="text-left mb-6">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle size={16} className="text-warning" />
                <h4 className="text-sm font-black text-foreground tracking-tight">
                  입력 타겟과 실측 불일치 {alignmentAlerts.length}건
                </h4>
              </div>
              <ul className="space-y-2">
                {alignmentAlerts.map((alert, i) => {
                  const cls = severityClasses(alert.severity);
                  return (
                    <li
                      key={i}
                      className={`flex items-start gap-3 p-3 border rounded-xl ${cls.border} ${cls.bg}`}
                    >
                      <span
                        className={`shrink-0 px-2 py-0.5 rounded text-[0.625rem] font-black uppercase tracking-widest ${cls.text} border ${cls.border}`}
                      >
                        {cls.label}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`font-black ${cls.text}`}>
                            {DIMENSION_LABEL[alert.dimension]}
                          </span>
                          <span className="text-muted-foreground tabular-nums">
                            입력: <span className="text-foreground">{alert.user_input}</span>
                          </span>
                          <span className="text-muted-foreground">·</span>
                          <span className="text-muted-foreground tabular-nums">
                            실측: <span className="text-foreground">{alert.actual}</span>
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                          {alert.message}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {alignmentAlerts.length === 0 && (
            <div className="text-left p-4 border border-primary/20 bg-primary/5 rounded-xl">
              <p className="text-xs text-muted-foreground leading-relaxed">
                입력 타겟이 실측 매출 분포와 잘 맞습니다. 미스매치 차원 없음.
              </p>
            </div>
          )}

          {reverseSuggestion && (
            <div className="text-left">
              <div className="mb-3 flex items-center gap-2">
                <Lightbulb size={16} className="text-primary" />
                <h4 className="text-sm font-black text-foreground tracking-tight">
                  타겟 재정의 제안
                </h4>
                <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
                  reverse_target_suggestion
                </span>
              </div>
              <div className="p-4 border border-primary/30 bg-primary/5 rounded-xl space-y-3">
                <p className="text-xs text-muted-foreground leading-relaxed">
                  입지를 그대로 두고{' '}
                  <span className="font-bold text-foreground">타겟·운영전략</span>을 실측 분포에
                  맞춰 재정의할 때 권장:
                </p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
                  {reverseSuggestion.recommended_age_groups.length > 0 && (
                    <div>
                      <div className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                        연령대
                      </div>
                      <div className="mt-0.5 font-black text-primary">
                        {reverseSuggestion.recommended_age_groups.join(', ')}
                      </div>
                    </div>
                  )}
                  {reverseSuggestion.recommended_gender && (
                    <div>
                      <div className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                        성별
                      </div>
                      <div className="mt-0.5 font-black text-primary">
                        {reverseSuggestion.recommended_gender === 'male'
                          ? '남성'
                          : reverseSuggestion.recommended_gender === 'female'
                            ? '여성'
                            : '혼재'}
                      </div>
                    </div>
                  )}
                  {reverseSuggestion.recommended_hours.length > 0 && (
                    <div>
                      <div className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                        시간대
                      </div>
                      <div className="mt-0.5 font-black text-primary">
                        {reverseSuggestion.recommended_hours.join(', ')}
                      </div>
                    </div>
                  )}
                  {reverseSuggestion.recommended_day_type && (
                    <div>
                      <div className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                        요일
                      </div>
                      <div className="mt-0.5 font-black text-primary">
                        {reverseSuggestion.recommended_day_type === 'weekday' ? '평일' : '주말'}
                      </div>
                    </div>
                  )}
                  {reverseSuggestion.recommended_price_range && (
                    <div>
                      <div className="text-[0.625rem] font-bold text-muted-foreground uppercase tracking-widest">
                        객단가
                      </div>
                      <div className="mt-0.5 font-black text-primary">
                        {reverseSuggestion.recommended_price_range}
                      </div>
                    </div>
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed italic border-t border-primary/20 pt-2">
                  {reverseSuggestion.rationale}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
