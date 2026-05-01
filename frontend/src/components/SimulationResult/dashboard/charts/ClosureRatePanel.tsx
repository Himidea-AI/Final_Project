/**
 * ClosureRatePanel — 과거 폐업률 추이 패널 (실측 데이터)
 *
 * 2026-04-29 M8: FinancialTab.tsx 의 inline 함수에서 분리.
 * district 옵셔널 prop 추가 — M9 멀티 동 grid 호출용.
 */

import { History } from 'lucide-react';
import type { ClosureRate } from '../../../../types';
import { ClosureRateHistoryChart } from './ClosureRateHistoryChart';

interface Props {
  rate?: ClosureRate | null;
  /** M8: 동별 grid 호출 시 카드 상단에 표시 (옵셔널) */
  district?: string;
}

export function ClosureRatePanel({ rate, district }: Props) {
  if (!rate || !rate.monthly_closure_rates || rate.monthly_closure_rates.length === 0) {
    return null;
  }
  const avgPct = rate.closure_rate != null ? (rate.closure_rate * 100).toFixed(1) : '—';
  return (
    <div className="bg-card border border-border rounded-3xl p-6">
      {district && <div className="text-xs font-bold text-muted-foreground mb-2">{district}</div>}
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest flex items-center gap-2">
          <History size={14} className="text-muted-foreground" /> 과거 폐업률 추이
          <span className="text-[0.625rem] font-black text-muted-foreground normal-case tracking-normal">
            closure_rate · 실측
          </span>
        </h4>
        <div className="flex items-center gap-2">
          <span className="text-[0.6875rem] font-black text-muted-foreground tabular-nums">
            최근 4분기 평균 {avgPct}%
          </span>
        </div>
      </div>
      <ClosureRateHistoryChart rates={rate.monthly_closure_rates} />
      <p className="mt-3 text-[0.625rem] text-muted-foreground leading-relaxed">
        ※ 이 차트는 과거 데이터 기반 실측 폐업률입니다. 예측은 아래 LightGBM + TCN 폐업위험도 패널을
        참고하세요.
      </p>
    </div>
  );
}
