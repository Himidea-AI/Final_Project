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
      <div className="rounded-2xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        {district && <div className="text-xs font-bold text-stone-400 mb-2">{district}</div>}
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
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
      {district && <div className="text-xs font-bold text-stone-400 mb-2">{district}</div>}
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2">
          폐업 위험도
        </h4>
        {closure.is_mock && (
          <span className="text-[0.5625rem] font-black text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full uppercase">
            MOCK
          </span>
        )}
      </div>
      <BulletChart
        actual={score100}
        target={30}
        max={100}
        label="위험 점수"
        thresholds={[30, 60]}
      />

      {/* 2026-04-27: closure_risk가 LightGBM(과거 패턴) + TCN(시계열) 두 모델 결과를 별도 노출 */}
      {closure.summary_lgbm && closure.summary_lgbm.length > 0 && (
        <div className="mt-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[0.5625rem] font-black uppercase tracking-widest text-indigo-400 mb-1">
            <span className="w-1 h-1 rounded-full bg-indigo-400" />
            LightGBM · 과거 패턴
          </div>
          <p className="text-[0.6875rem] text-stone-300 leading-relaxed">
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
        <div className="mt-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[0.5625rem] font-black uppercase tracking-widest text-cyan-400 mb-1">
            <span className="w-1 h-1 rounded-full bg-cyan-400" />
            TCN · 시계열 흐름
          </div>
          <p className="text-[0.6875rem] text-stone-300 leading-relaxed">
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
          <p className="mt-3 text-[0.6875rem] text-stone-500 leading-relaxed">
            폐업 위험도 모델 요약 미생성
          </p>
        )}
    </div>
  );
}
