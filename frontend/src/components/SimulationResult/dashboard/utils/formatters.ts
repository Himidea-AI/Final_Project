/**
 * 대시보드 공용 포맷터
 * 원 → 억/만 / 분수 → 퍼센트 / 피크 시간 정규화 / SHAP raw value / HHI
 */

/** 원 단위 숫자 → "N억 N,NNN만" 또는 "N,NNN만" 형식 */
export function formatKrw(won: number | null | undefined): string {
  if (won == null || !Number.isFinite(won)) return '—';
  if (won >= 1_0000_0000) {
    const eok = won / 1_0000_0000;
    return `${eok.toFixed(eok >= 10 ? 1 : 2)}억`;
  }
  if (won >= 1_0000) {
    return `${Math.round(won / 1_0000).toLocaleString('ko-KR')}만`;
  }
  return won.toLocaleString('ko-KR');
}

/** 0~1 소수 → "42.1%" */
export function formatPct(ratio: number | null | undefined, digits: number = 1): string {
  if (ratio == null || !Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** 0~100 점수 → "92.4" (tabular-nums 용, 소수점 1자리) */
export function formatScore(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return '—';
  return score.toFixed(1);
}

/**
 * 피크 시간 문자열 정규화
 * "18-21" → "18:00 - 21:00"
 * "18:00-21:00" → "18:00 - 21:00"
 * 이미 올바른 형식은 그대로
 */
export function formatPeakHours(raw: string | null | undefined): string {
  if (!raw) return '—';
  const s = raw.trim();
  // "HH-HH" or "HH:MM-HH:MM" 패턴
  const simple = s.match(/^(\d{1,2})\s*-\s*(\d{1,2})$/);
  if (simple) return `${simple[1].padStart(2, '0')}:00 - ${simple[2].padStart(2, '0')}:00`;
  const full = s.match(/^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$/);
  if (full)
    return `${full[1].padStart(2, '0')}:${full[2]} - ${full[3].padStart(2, '0')}:${full[4]}`;
  return s;
}

/** SHAP raw value → 포맷 ("+0.087" / "-0.052") */
export function formatShapValue(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(3)}`;
}

/** SHAP bar width (0~100%) — 절대값 × 1000 배율, 최대 100 clamp */
export function shapBarWidth(value: number): number {
  return Math.min(100, Math.abs(value) * 1000);
}

/**
 * HHI (Herfindahl-Hirschman Index) 계산
 * 매장 수 기반 근사 — samples[]의 brand_name 그룹화
 * 반환: 0 ~ 10000
 */
export function calcHHI(samples: Array<{ brand_name?: string | null }>): number {
  if (!samples || samples.length === 0) return 0;
  const total = samples.length;
  const byBrand: Record<string, number> = {};
  samples.forEach((s) => {
    const key = s.brand_name || '독립점';
    byBrand[key] = (byBrand[key] || 0) + 1;
  });
  return Object.values(byBrand)
    .map((count) => ((count / total) * 100) ** 2)
    .reduce((a, b) => a + b, 0);
}

/** HHI → 다양성 지수 (100 - HHI/100) */
export function hhiToDiversity(hhi: number): number {
  return Math.max(0, Math.min(100, 100 - hhi / 100));
}

/**
 * 신뢰구간 범위 포맷
 * confidence_lower / confidence_upper (원 단위) → "2,460 ~ 3,140만"
 */
export function formatConfidenceRange(
  lower: number | null | undefined,
  upper: number | null | undefined,
): string {
  if (lower == null || upper == null || !Number.isFinite(lower) || !Number.isFinite(upper)) {
    return '—';
  }
  return `${formatKrw(lower)} ~ ${formatKrw(upper)}`;
}

/**
 * 분기 revenue → 월 환산
 * quarterly_projection[0].revenue / 3
 */
export function quarterlyToMonthly(quarterly: number | null | undefined): number | null {
  if (quarterly == null || !Number.isFinite(quarterly)) return null;
  return Math.round(quarterly / 3);
}

/** request_id 앞 8자 slice ("a7b3c2d1...") */
export function shortRequestId(id: string | null | undefined): string {
  if (!id) return '—';
  return id.slice(0, 8);
}
