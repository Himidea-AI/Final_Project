/**
 * ClosureRiskPanel — LightGBM + TCN 기반 폐업 위험도 패널 (예측)
 *
 * 2026-04-29 M8: FinancialTab.tsx 의 inline 함수에서 분리.
 * district 옵셔널 prop 추가 — M9 멀티 동 grid 호출용.
 */

import type { ClosureRisk } from '../../../../types';
import { BulletChart } from './BulletChart';
import { ClosureSignalsBar } from './ClosureSignalsBar';

interface Props {
  closure?: ClosureRisk | null;
  /** M8: 동별 grid 호출 시 카드 상단에 표시 (옵셔널) */
  district?: string;
}

export function ClosureRiskPanel({ closure, district }: Props) {
  if (!closure) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card p-6 text-center text-xs text-muted-foreground">
        {district && <div className="text-xs font-bold text-muted-foreground mb-2">{district}</div>}
        closure_risk 분석 대기
      </div>
    );
  }
  // 백엔드는 risk_score를 0~1 소수점으로 저장 (synthesis.py:209가 *100해서 표시).
  // BulletChart는 0~100 스케일 기대 → 여기서 정규화.
  const scoreRaw = closure.risk_score;
  const score100 =
    scoreRaw == null ? null : scoreRaw <= 1 ? Math.round(scoreRaw * 100) : Math.round(scoreRaw);
  return (
    <div className="bg-card border border-border rounded-3xl p-6">
      {district && <div className="text-xs font-bold text-muted-foreground mb-2">{district}</div>}
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2">
          폐업 위험도
        </h4>
        {closure.is_mock && (
          <span className="text-[0.5625rem] font-black text-warning bg-warning/10 px-2 py-0.5 rounded-full uppercase">
            MOCK
          </span>
        )}
      </div>
      {/* 폐업 위험도는 lower-better — 점수 낮을수록 안전.
          [30, 60] 임계값은 시각 영역 분할용 (안전/주의/위험 구간 색감 가이드)이며 수치로
          표시되지 않음 → §3.7 위반 아님. 이전 target={30} 임의 마커는 misleading 으로 제거.  */}
      <BulletChart
        actual={score100}
        max={100}
        label="위험 점수"
        thresholds={[30, 60]}
        polarity="lower-better"
      />

      {/* 2026-04-27: closure_risk가 LightGBM(과거 패턴) + TCN(시계열) 두 모델 결과를 별도 노출 */}
      {closure.summary_lgbm && closure.summary_lgbm.length > 0 && (
        <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[0.5625rem] font-black uppercase tracking-widest text-primary mb-1">
            <span className="w-1 h-1 rounded-full bg-primary" />
            LightGBM · 과거 패턴
          </div>
          <p className="text-[0.6875rem] text-foreground leading-relaxed">
            {closure.summary_lgbm[0]}
          </p>
        </div>
      )}
      <ClosureSignalsBar
        signals={closure.top_signals_lgbm}
        title="LightGBM 기여 피처 (과거 패턴)"
        accent="indigo"
      />
      {closure.summary_tcn && closure.summary_tcn.length > 0 && (
        <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[0.5625rem] font-black uppercase tracking-widest text-primary mb-1">
            <span className="w-1 h-1 rounded-full bg-primary" />
            TCN · 시계열 흐름
          </div>
          <p className="text-[0.6875rem] text-foreground leading-relaxed">
            {closure.summary_tcn[0]}
          </p>
        </div>
      )}
      <ClosureSignalsBar
        signals={closure.top_signals_tcn}
        title="TCN 기여 피처 (시계열 흐름)"
        accent="cyan"
      />
      {(!closure.summary_lgbm || closure.summary_lgbm.length === 0) &&
        (!closure.summary_tcn || closure.summary_tcn.length === 0) &&
        (!closure.top_signals_lgbm || closure.top_signals_lgbm.length === 0) &&
        (!closure.top_signals_tcn || closure.top_signals_tcn.length === 0) && (
          <p className="mt-3 text-[0.6875rem] text-muted-foreground leading-relaxed">
            폐업 위험도 모델 요약 미생성
          </p>
        )}
    </div>
  );
}
