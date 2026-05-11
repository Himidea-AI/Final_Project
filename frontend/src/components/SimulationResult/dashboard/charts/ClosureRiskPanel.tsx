/**
 * ClosureRiskPanel — 동별 폐업 위험도 카드 (통일 레이아웃)
 *
 * 2026-04-29 M8: FinancialTab.tsx 의 inline 함수에서 분리.
 * 2026-05-04 사용자 친화 개편:
 *   - ML 용어 제거 (LightGBM → "과거 데이터 분석", TCN → "최근 추세 분석")
 *   - 메인 카드는 단순화: BulletChart + 합본 자연어 요약 + 위험 신호 TOP 3
 *   - 깊은 분석은 "분석 상세" 모달(ClosureRiskDetailModal)로 분리
 *   - 1~4동 선택 시 카드 형태 통일 — 그리드로 나열만 다름
 *   - "MOCK" → "데이터 검증 중"
 */

import type { ClosureRisk, ClosureRiskSignal } from '../../../../types';
import { BulletChart } from './BulletChart';
import { shapStrengthFullLabel } from '../utils/formatters';

interface Props {
  closure?: ClosureRisk | null;
  district?: string;
  /** "분석 상세" 버튼 클릭 시 부모가 모달 띄움. 없으면 버튼 미노출. */
  onOpenDetail?: () => void;
  /** 4동 비교 grid 에서 동별 색 (SERIES_COLORS[idx]). 위험 점수 막대 색에 적용. */
  seriesColor?: string;
}

export function ClosureRiskPanel({ closure, district, onOpenDetail, seriesColor }: Props) {
  if (!closure) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-card p-6 text-center text-xs text-muted-foreground h-full flex items-center justify-center">
        <div>
          {district && (
            <div className="text-xs font-bold text-muted-foreground mb-2">{district}</div>
          )}
          분석 대기
        </div>
      </div>
    );
  }

  // 백엔드는 risk_score를 0~1 소수점으로 저장 (synthesis.py:209가 *100해서 표시).
  // BulletChart는 0~100 스케일 기대 → 여기서 정규화.
  const scoreRaw = closure.risk_score;
  const score100 =
    scoreRaw == null ? null : scoreRaw <= 1 ? Math.round(scoreRaw * 100) : Math.round(scoreRaw);

  // 두 분석(LGBM/TCN) 신호 합쳐서 |contribution| 큰 순 상위 3개.
  // feature_key 중복 시 더 강한 쪽만 채택해 카드 단순성 유지.
  const merged = mergeTopSignals(closure.top_signals_lgbm ?? [], closure.top_signals_tcn ?? [], 3);

  // summary 단순 합본 — 두 분석의 자연어 요약 첫 줄을 bullet 으로 나열.
  // 백엔드 _generate_*_summary 가 이미 비전문가 친화 문장이라 그대로 노출.
  const summaryLines = [closure.summary_lgbm?.[0], closure.summary_tcn?.[0]].filter(
    (s): s is string => !!s && s.trim().length > 0,
  );

  return (
    <div className="bg-card border border-border rounded-3xl p-6 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3 gap-2">
        {district ? (
          <div className="text-base font-black text-foreground tracking-tight truncate">
            {district}
          </div>
        ) : (
          <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest">
            폐업 위험도
          </h4>
        )}
        {closure.is_mock && (
          <span className="text-[0.5625rem] font-black text-warning bg-warning/10 px-2 py-0.5 rounded-full uppercase shrink-0">
            데이터 검증 중
          </span>
        )}
      </div>

      {/* 폐업 위험도는 lower-better — 점수 낮을수록 안전.
          [30, 60] 임계값은 시각 영역 분할용 (안전/주의/위험 구간 색감 가이드)이며 수치로
          표시되지 않음 → §3.7 위반 아님. */}
      <BulletChart
        actual={score100}
        max={100}
        label="위험 점수"
        thresholds={[30, 60]}
        polarity="lower-better"
        unit="점"
        barColor={seriesColor}
      />

      {summaryLines.length > 0 && (
        <div className="mt-4 space-y-1.5">
          {summaryLines.map((line, i) => (
            <p key={i} className="text-[0.6875rem] text-foreground leading-relaxed">
              · {line}
            </p>
          ))}
        </div>
      )}

      {merged.length > 0 ? (
        <div className="mt-4 rounded-lg border border-border bg-secondary p-3">
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground mb-2">
            주요 위험 신호 TOP 3
          </div>
          <div className="space-y-1.5">
            {merged.map((s, i) => {
              const positive = s.contribution >= 0;
              const labelColor = positive ? 'text-danger' : 'text-success';
              return (
                <div key={i} className="flex items-center justify-between gap-2">
                  <span className="text-[0.6875rem] text-foreground font-bold truncate">
                    {s.feature}
                  </span>
                  <span
                    className={`text-[0.6875rem] font-black tabular-nums shrink-0 ${labelColor}`}
                    title={`원시 SHAP 값: ${positive ? '+' : ''}${s.contribution.toFixed(4)}`}
                  >
                    {shapStrengthFullLabel(s.contribution)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        summaryLines.length === 0 && (
          <p className="mt-4 text-[0.6875rem] text-muted-foreground leading-relaxed">
            분석 결과 미생성
          </p>
        )
      )}

      {onOpenDetail && (merged.length > 0 || summaryLines.length > 0) && (
        <div className="mt-auto pt-4 flex justify-end">
          <button
            type="button"
            onClick={onOpenDetail}
            className="text-[0.6875rem] font-bold text-primary hover:text-primary/80 transition-colors"
          >
            분석 상세 →
          </button>
        </div>
      )}
    </div>
  );
}

function mergeTopSignals(
  lgbm: ClosureRiskSignal[],
  tcn: ClosureRiskSignal[],
  limit: number,
): ClosureRiskSignal[] {
  // 두 분석 결과를 feature_key 기준 dedup 후 |contribution| 큰 순 정렬.
  // 같은 피처가 양쪽에 있으면 절댓값 큰 쪽 채택.
  const map = new Map<string, ClosureRiskSignal>();
  for (const s of [...lgbm, ...tcn]) {
    const key = s.feature_key ?? s.feature;
    if (!key) continue;
    const existing = map.get(key);
    if (!existing || Math.abs(s.contribution) > Math.abs(existing.contribution)) {
      map.set(key, s);
    }
  }
  return Array.from(map.values())
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, limit);
}
