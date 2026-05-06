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
  /** 동별 자동 매핑 색 — BEP 차트와 동일한 SERIES_COLORS[idx] 전달. 미지정 시 muted-foreground. */
  color?: string;
}

export function ClosureRatePanel({ rate, district, color }: Props) {
  if (!rate || !rate.monthly_closure_rates || rate.monthly_closure_rates.length === 0) {
    return null;
  }
  // 그래프에 표시되는 4분기 값의 산술평균 (소수 둘째 자리에서 반올림 → 첫째 자리 표시).
  // backend `closure_rate` 필드는 "최근 분기"라 그래프 평균과 일치하지 않으므로 프론트에서 직접 계산.
  const rates = rate.monthly_closure_rates;
  const avgPct = ((rates.reduce((sum, r) => sum + r, 0) / rates.length) * 100).toFixed(1);
  return (
    <div className="bg-card border border-border rounded-3xl p-5">
      {district && (
        <div className="mb-3 text-lg font-black text-foreground tracking-tight">{district}</div>
      )}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <h4 className="flex items-center gap-1.5 text-xs font-black uppercase tracking-widest text-muted-foreground">
          <History size={14} className="text-muted-foreground" /> 과거 폐업률
        </h4>
        <span className="text-sm font-black tabular-nums text-foreground">평균 {avgPct}%</span>
      </div>
      <ClosureRateHistoryChart rates={rate.monthly_closure_rates} color={color} />
      <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
        ※ 실측 데이터 기반. 예측은 위험도 패널 참고.
      </p>
    </div>
  );
}
