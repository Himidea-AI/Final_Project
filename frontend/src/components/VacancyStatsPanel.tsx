import type { VacancyPseSummary, VacancySpotHighlight } from './AbmPersonaMap';

interface VacancyStatsPanelProps {
  summary: VacancyPseSummary | null;
  vacancySpot: VacancySpotHighlight;
  loading?: boolean;
}

/**
 * vacancy_pse 결과 (pse_summary) 를 받아 매출/방문 통계 카드를 표시하는 사이드 패널.
 * AbmPersonaMap 의 mode='vacancy' 시 우측에 렌더 (절대 위치 오버레이).
 */
export default function VacancyStatsPanel({
  summary,
  vacancySpot,
  loading,
}: VacancyStatsPanelProps) {
  const dongLabel = vacancySpot.dong;
  const categoryLabel = vacancySpot.category ?? '';
  const titleSuffix = categoryLabel ? ` ${categoryLabel}` : '';

  if (loading || !summary) {
    return (
      <div className="vacancy-stats-panel bg-background/90 backdrop-blur-sm border border-chart-4/30 rounded-xl p-4 text-foreground text-xs font-mono w-72">
        <h3 className="text-sm font-black text-chart-4 mb-2">
          {dongLabel}
          {titleSuffix} 평가
        </h3>
        <p className="text-muted-foreground">시뮬 진행 중...</p>
      </div>
    );
  }

  const visitsMean = summary.visits_per_day?.mean ?? 0;
  const visitsCi = summary.visits_per_day?.ci95 ?? 0;
  const revenueMean = summary.revenue_per_day?.mean ?? 0;
  const revenueCi = summary.revenue_per_day?.ci95 ?? 0;
  const ratioMean = summary.vacancy_vs_avg_visits_ratio?.mean ?? 0;
  const ratioCi = summary.vacancy_vs_avg_visits_ratio?.ci95 ?? 0;

  const visitsPerQuarter = visitsMean * 90;
  const revenuePerQuarter = revenueMean * 90;
  const revenuePerYear = revenueMean * 365;

  return (
    <div className="vacancy-stats-panel bg-background/90 backdrop-blur-sm border border-chart-4/30 rounded-xl p-4 text-foreground text-xs font-mono w-72 shadow-2xl">
      <h3 className="text-sm font-black text-chart-4 mb-3 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-danger animate-pulse" />
        {dongLabel}
        {titleSuffix} 평가
      </h3>
      <ul className="flex flex-col gap-1.5 text-[0.6875rem] leading-relaxed">
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">일 방문</span>{' '}
          <span className="text-success font-bold">
            {visitsMean.toFixed(1)} ± {visitsCi.toFixed(1)}
          </span>{' '}
          <span className="text-muted-foreground">명</span>
        </li>
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">일 매출</span>{' '}
          <span className="text-success font-bold">
            {(revenueMean / 10000).toFixed(0)} ± {(revenueCi / 10000).toFixed(0)}
          </span>{' '}
          <span className="text-muted-foreground">만원</span>
        </li>
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">분기 방문</span>{' '}
          <span className="text-chart-4 font-bold">{visitsPerQuarter.toFixed(0)}</span>{' '}
          <span className="text-muted-foreground">명</span>
        </li>
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">분기 매출</span>{' '}
          <span className="text-chart-4 font-bold">{(revenuePerQuarter / 1e8).toFixed(2)}</span>{' '}
          <span className="text-muted-foreground">억원</span>
        </li>
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">연 매출</span>{' '}
          <span className="text-chart-4 font-bold">{(revenuePerYear / 1e8).toFixed(2)}</span>{' '}
          <span className="text-muted-foreground">억원</span>
        </li>
        <li className="text-muted-foreground">
          <span className="text-muted-foreground">동 평균 대비</span>{' '}
          <span className="text-warning font-bold">
            {ratioMean.toFixed(1)} ± {ratioCi.toFixed(1)}
          </span>{' '}
          <span className="text-muted-foreground">배</span>
        </li>
        {summary.cannibalization_pct && (
          <li className="text-muted-foreground">
            <span className="text-muted-foreground">카니발 (500m)</span>{' '}
            <span className="text-danger font-bold">
              {summary.cannibalization_pct.mean.toFixed(1)} ±{' '}
              {summary.cannibalization_pct.ci95.toFixed(1)}
            </span>{' '}
            <span className="text-muted-foreground">%</span>
          </li>
        )}
        {summary.dong_net_growth_pct && (
          <li className="text-muted-foreground">
            <span className="text-muted-foreground">동 시장 성장</span>{' '}
            <span className="text-success font-bold">
              {summary.dong_net_growth_pct.mean.toFixed(2)} ±{' '}
              {summary.dong_net_growth_pct.ci95.toFixed(2)}
            </span>{' '}
            <span className="text-muted-foreground">%</span>
          </li>
        )}
      </ul>
    </div>
  );
}
