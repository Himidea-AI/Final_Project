/**
 * 대시보드 공용 포맷터
 * 원 → 억/만 / 분수 → 퍼센트 / 피크 시간 정규화 / SHAP raw value / HHI
 */

/** 원 단위 숫자 → "N억 N,NNN만" 또는 "N,NNN만" 형식 */
// 음수(손실)도 절댓값으로 분기하고 부호 보존. 미보존 시 toLocaleString fallback
// 으로 빠져 부동소수점이 그대로 노출됨 — 영업이익 평균이 음수일 때 발생.
export function formatKrw(won: number | null | undefined): string {
  if (won == null || !Number.isFinite(won)) return '—';
  const sign = won < 0 ? '-' : '';
  const abs = Math.abs(won);
  if (abs >= 1_0000_0000) {
    const eok = abs / 1_0000_0000;
    return `${sign}${eok.toFixed(eok >= 10 ? 1 : 2)}억`;
  }
  if (abs >= 1_0000) {
    return `${sign}${Math.round(abs / 1_0000).toLocaleString('ko-KR')}만`;
  }
  return `${sign}${Math.round(abs).toLocaleString('ko-KR')}`;
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
 * SHAP contribution 절댓값을 강도 등급으로 변환.
 * 폐업위험도 모델의 SHAP 값 분포를 기반으로 임계값 선정:
 *   |c| < 0.02 → 약 (영향 미미)
 *   0.02 ≤ |c| < 0.05 → 중 (보통 영향)
 *   |c| ≥ 0.05 → 강 (강한 영향)
 * 등급은 ClosureRiskHeatmap 셀 / ClosureSignalsBar 우측 라벨에서 공유.
 */
export type ShapStrength = 'strong' | 'medium' | 'weak';

export function shapStrength(contribution: number): ShapStrength {
  const abs = Math.abs(contribution);
  if (abs >= 0.05) return 'strong';
  if (abs >= 0.02) return 'medium';
  return 'weak';
}

/** 등급 한글 라벨 — Heatmap 셀 표기용 (방향 화살표 + 강도). */
export function shapStrengthLabel(contribution: number): string {
  const s = shapStrength(contribution);
  const arrow = contribution > 0 ? '↑' : '↓';
  const ko = s === 'strong' ? '강' : s === 'medium' ? '중' : '약';
  return `${arrow} ${ko}`;
}

/** 등급 풀라벨 — SignalsBar 우측 라벨용 ("위험 증가 ↑↑" 형식). */
export function shapStrengthFullLabel(contribution: number): string {
  const s = shapStrength(contribution);
  const dirText = contribution > 0 ? '위험 증가' : '위험 감소';
  const arrowRep = s === 'strong' ? 3 : s === 'medium' ? 2 : 1;
  const arrow = (contribution > 0 ? '↑' : '↓').repeat(arrowRep);
  return `${dirText} ${arrow}`;
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

// LLM 응답에 들어가는 영문 등급 코드 → 한글. 본부 영업팀 페르소나(메모리) 기준 일관 어휘.
const GRADE_KO: Record<string, string> = {
  RISKY: '주의',
  SAFE: '안전',
  CAUTION: '주의',
  GOOD: '양호',
  HIGH: '높음',
  MEDIUM: '보통',
  LOW: '낮음',
};

/** verdict/reasoning 텍스트 안의 RISKY/SAFE/CAUTION 등 영문 등급 코드를 한글로 치환. */
export function humanizeGrade(text: string | null | undefined): string {
  if (!text) return '';
  return text.replace(/\b(RISKY|SAFE|CAUTION|GOOD|HIGH|MEDIUM|LOW)\b/g, (m) => GRADE_KO[m] ?? m);
}
