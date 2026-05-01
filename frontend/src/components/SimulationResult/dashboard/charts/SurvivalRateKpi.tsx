/**
 * SurvivalRateKpi — 생존률 보조 KPI 카드
 *
 * 2026-05-01 정합 fix: backend 의 survival_rate 가 임의 변환식 (score × 0.9 floor 30) 이라
 *   misleading. 생존률을 폐업률의 보완값 (100 - closure_rate × 100) 으로 직접 산출 →
 *   두 값이 동일 모델 출처에서 정합. survivalRate prop 더 이상 사용하지 않음 (deprecated).
 *
 * 데이터: market_report.closure_rate (DB 실측, 0~1 비율 또는 0~100)
 * 디자인: 폐업률(danger) ↔ 생존률(success) — 합 100% 보장
 */

import { ShieldCheck } from 'lucide-react';

interface Props {
  /** @deprecated backend 임의 변환식 — closure 의 보완값으로 자동 산출. 무시됨. */
  survivalRate?: number | null | undefined;
  closureRate: number | null | undefined;
}

function normalizePct(value: number | null | undefined): number | null {
  if (value == null) return null;
  // 0~1 범위면 100 곱, 그 외엔 그대로 (0~100 정규화)
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

export function SurvivalRateKpi({ closureRate }: Props) {
  const cPct = normalizePct(closureRate);
  // 생존률 = 100 - 폐업률 (실측 보완). closure_rate 가 null 이면 둘 다 null.
  const sPct = cPct != null ? 100 - cPct : null;

  if (cPct == null) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-border bg-secondary p-5">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck size={14} className="text-success" />
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
          3년 생존 vs 폐업
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-success mb-1">
            생존률
          </div>
          <div className="text-3xl font-black tabular-nums text-success tracking-tighter">
            {sPct != null ? `${sPct}` : '—'}
            <span className="text-sm font-bold text-muted-foreground ml-0.5">%</span>
          </div>
        </div>
        <div>
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-danger mb-1">
            폐업률
          </div>
          <div className="text-3xl font-black tabular-nums text-danger tracking-tighter">
            {cPct != null ? `${cPct}` : '—'}
            <span className="text-sm font-bold text-muted-foreground ml-0.5">%</span>
          </div>
        </div>
      </div>
      {/* 생존률 + 폐업률 = 100 보장 (cPct + sPct = 100). 단순 width 비율로 시각화. */}
      {sPct != null && (
        <div className="mt-3 flex h-1.5 w-full overflow-hidden rounded-full bg-card">
          <div className="h-full bg-success" style={{ width: `${sPct}%` }} />
          <div className="h-full bg-danger" style={{ width: `${cPct}%` }} />
        </div>
      )}
      <p className="mt-3 text-[0.625rem] leading-relaxed text-muted-foreground">
        DB 실측 폐업률 기반 — 생존률 = 100 − 폐업률.
      </p>
    </div>
  );
}
