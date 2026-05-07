/**
 * ShapInsightCard — SHAP 기여도를 텍스트 인사이트로 표시
 *
 * 2026-04-27 사용자 결정: WaterfallChart 제거 + 자연어 카드로 대체.
 * 본부 영업팀에 "어떤 요인이 매출에 ±얼마 기여" 직관 전달이 목적.
 * 2026-04-29 M9: district 옵셔널 prop 추가 — 동별 grid 호출용.
 * 2026-05-04 표시 개편:
 *   - "기여도 상위 3개 피처" → "이 동의 매출 예측에 가장 영향을 준 요인 3가지"
 *     (사용자가 "기여도/피처" ML 용어 이해 어려움 피드백)
 *   - 절대 금액 → 비율(%) + 미니 막대 + 방향(↑/↓)
 *     (가산성 분배라 절대값 신뢰도 낮음 + "월 매출 건수 +1.5억원" 단위 부조화)
 *   - summary 자연어 1줄 노출 (백엔드 _generate_tcn_summary 결과 활용)
 */

import type { ShapResult } from '../../../../types';

interface Props {
  shap: ShapResult | null | undefined;
  /** M9: 동별 grid 호출 시 카드 상단에 표시 (옵셔널) */
  district?: string;
  /** 4동 비교 grid 에서 동별 색 (SERIES_COLORS[idx]). 미지정 시 success/danger semantic 폴백.
   *  bar 만 동별 색, 텍스트/화살표(↑↓)는 의미 색(success/danger) 유지 — 기여도 방향 정보 보존. */
  seriesColor?: string;
}

export function ShapInsightCard({ shap, district, seriesColor }: Props) {
  if (!shap) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-8 text-center text-xs text-muted-foreground">
        {district && (
          <div className="text-sm font-black text-foreground tracking-tight mb-2">{district}</div>
        )}
        SHAP 해석 데이터 없음 — 모델 예측 신뢰도가 확정되면 표시됩니다
      </div>
    );
  }

  const top = (shap.feature_importance ?? []).slice(0, 3);
  const isMock = shap.is_mock;

  if (top.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-secondary p-6 text-center text-xs text-muted-foreground">
        {district && (
          <div className="text-sm font-black text-foreground tracking-tight mb-2">{district}</div>
        )}
        피처 기여도 산출 결과 없음
      </div>
    );
  }

  // top 3 abs_shap 합 = 100% — 상대 비율로 환산 (단위 부조화 + 절대값 과장 회피).
  const totalAbs = top.reduce((acc, f) => acc + Math.abs(f.abs_shap ?? f.shap_value), 0);
  const summaryLine = (shap.summary ?? []).find(
    (s) => typeof s === 'string' && s.trim().length > 0,
  );

  return (
    <div
      className={`rounded-2xl border border-border p-5 ${
        isMock ? 'bg-secondary/60 opacity-60' : 'bg-secondary'
      }`}
    >
      {district && (
        <div className="text-sm font-black text-foreground tracking-tight mb-2">{district}</div>
      )}
      <div className="flex items-center justify-between mb-4 gap-2">
        <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest leading-tight">
          이 동의 매출 예측에 가장 영향을 준 요인 3가지
        </div>
        {isMock && (
          <span className="text-[0.5625rem] font-black text-warning bg-warning/10 px-2 py-0.5 rounded-full uppercase shrink-0">
            데이터 신뢰도 검증 중
          </span>
        )}
      </div>
      <div className="space-y-3">
        {top.map((f) => {
          const positive = f.shap_value >= 0;
          const arrow = positive ? '↑' : '↓';
          const colorClass = positive ? 'text-success' : 'text-danger';
          const semanticBarClass = positive ? 'bg-success' : 'bg-danger';
          const pct = totalAbs > 0 ? (Math.abs(f.abs_shap ?? f.shap_value) / totalAbs) * 100 : 0;
          return (
            <div
              key={f.rank}
              className="flex flex-col gap-1.5 border-b border-border/50 pb-2 last:border-b-0"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-foreground font-bold truncate">
                  {f.feature_ko || f.feature}
                </span>
                <span className={`text-sm font-black tabular-nums shrink-0 ${colorClass}`}>
                  {arrow} {pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1 rounded-full bg-border/40 overflow-hidden">
                {seriesColor ? (
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct.toFixed(1)}%`, backgroundColor: seriesColor }}
                  />
                ) : (
                  <div
                    className={`h-full rounded-full ${semanticBarClass}`}
                    style={{ width: `${pct.toFixed(1)}%` }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
      {summaryLine && (
        <p className="mt-4 text-[0.6875rem] text-foreground/80 leading-relaxed">{summaryLine}</p>
      )}
      <p className="mt-2 text-[0.625rem] text-muted-foreground leading-relaxed">
        ↑는 매출 상승, ↓는 하락 영향. 비율은 상위 3개 요인의 상대적 영향도입니다.
      </p>
    </div>
  );
}
