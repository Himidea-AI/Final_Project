/**
 * SPOTTER 의사결정 임계값 SSOT (Single Source of Truth)
 *
 * Q12 — `market_entry_signal` (green/yellow/red) × `overall_legal_risk` (safe/caution/danger)
 * 조합으로 GO/HOLD/STOP 판정.
 *
 * non-symmetric: 법률 danger는 시장 신호로 상쇄 불가 (사업 폐쇄 가능성).
 */

export type DecisionVerdict = 'GO' | 'HOLD' | 'STOP';

export type MarketEntrySignal = 'green' | 'yellow' | 'red';

export type LegalRiskLevel = 'safe' | 'caution' | 'danger' | string;

export function computeDecision(
  legal: LegalRiskLevel | undefined | null,
  entry: MarketEntrySignal | string | undefined | null,
): DecisionVerdict {
  if (legal === 'danger' || entry === 'red') return 'STOP';
  if (legal === 'safe' && entry === 'green') return 'GO';
  return 'HOLD';
}

export const DECISION_COPY: Record<
  DecisionVerdict,
  { label: string; color: 'emerald' | 'amber' | 'rose' }
> = {
  GO: { label: '진입 권장', color: 'emerald' },
  HOLD: { label: '조건부 진입', color: 'amber' },
  STOP: { label: '진입 비권장', color: 'rose' },
};

/**
 * GRADE 매핑 — analysis_metrics.district_grade (EXCELLENT/GOOD/NORMAL/RISKY)
 * 을 디자인 레이블 A+/B+/C+/D로 변환.
 */
export const GRADE_LABEL: Record<string, { letter: string; color: string }> = {
  EXCELLENT: { letter: 'A+', color: 'emerald' },
  GOOD: { letter: 'B+', color: 'indigo' },
  NORMAL: { letter: 'C+', color: 'amber' },
  RISKY: { letter: 'D', color: 'rose' },
};

export function getGrade(raw: string | undefined | null): {
  letter: string;
  color: string;
} {
  if (!raw) return { letter: '—', color: 'stone' };
  return GRADE_LABEL[raw] ?? { letter: '—', color: 'stone' };
}
