/**
 * ClosureRatePanel — 동 전체 과거 폐업률 추이 패널 (4분기 실측, 업종 통합)
 *
 * 2026-04-29 M8: FinancialTab.tsx 의 inline 함수에서 분리.
 * district 옵셔널 prop 추가 — M9 멀티 동 grid 호출용.
 *
 * 다른 패널과 혼동 방지: 상권분석 탭의 IndustryClosureTrendCard ("동 + 업종 폐업률 추세 8분기")
 *   는 업종별 필터링된 분기별 실측이라 본 카드 (동 전체 4분기 통합) 와 값이 다를 수 있음.
 *   카드 우측 ℹ️ 툴팁으로 사용자 안내.
 */

import { History, Info } from 'lucide-react';
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
          <History size={14} className="text-muted-foreground" />
          {district ? `${district} ` : ''}동 전체 폐업률 (4분기)
          {/* 혼동 방지 ℹ️ 툴팁 — 상권분석 탭의 동+업종 8분기 폐업률과 다른 데이터임을 안내. */}
          <span className="group relative inline-flex">
            <Info
              size={12}
              className="text-muted-foreground/60 hover:text-muted-foreground cursor-help"
            />
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-20 mt-1 w-64 -translate-x-1/2 rounded-lg border border-border bg-card/95 p-2 text-[0.625rem] font-normal normal-case tracking-normal text-foreground opacity-0 shadow-lg backdrop-blur transition-opacity group-hover:opacity-100"
            >
              <span className="font-bold text-foreground">동 전체 4분기</span> 폐업률 (전 업종
              통합).
              <br />
              상권분석 탭의 <span className="font-bold">"폐업률 추세 8분기"</span>
              (동 + 업종별 분기 실측) 와 단위·기간이 달라 값이 다를 수 있습니다.
            </span>
          </span>
        </h4>
        <span className="text-sm font-black tabular-nums text-foreground">평균 {avgPct}%</span>
      </div>
      <ClosureRateHistoryChart rates={rate.monthly_closure_rates} color={color} />
      <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
        ※ 동 전체 4분기 실측. 예측은 위험도 패널 참고. 상권분석 탭 업종별 8분기와 다를 수 있음.
      </p>
    </div>
  );
}
