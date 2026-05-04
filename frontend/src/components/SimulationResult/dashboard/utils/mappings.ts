/**
 * 대시보드 공용 Enum → 한글 라벨 매핑
 * 백엔드 demographic_report / competitor_intel 응답의 enum 값을 한글로 치환
 */

export const INCOME_MAP = {
  high: '상위권',
  mid: '중간',
  low: '하위권',
  unknown: '데이터 없음',
} as const;

export const TREND_MAP = {
  growing: '확장',
  stable: '유지',
  declining: '감소',
  unknown: '데이터 없음',
} as const;

export const SIGNAL_MAP = {
  green: { label: '권장', color: 'emerald' },
  yellow: { label: '주의', color: 'amber' },
  red: { label: '위험', color: 'rose' },
} as const;

export const SATURATION_MAP = {
  sparse: '희박',
  low: '낮음',
  medium: '중간',
  high: '높음',
  saturated: '포화',
} as const;

export const GRADE_MAP = {
  EXCELLENT: '최우수',
  GOOD: '우수',
  NORMAL: '보통',
  RISKY: '주의',
} as const;

export const RENT_AFFORDABILITY_MAP = {
  SAFE: '안전',
  CAUTION: '주의',
  DANGER: '위험',
} as const;

export const LEGAL_RISK_LEVEL_MAP = {
  HIGH: { label: '위험', color: 'rose' },
  MEDIUM: { label: '주의', color: 'amber' },
  LOW: { label: '안전', color: 'emerald' },
} as const;

/** core_demographic.gender 영어/약자 → 한글 라벨 */
export function mapGender(raw: string | null | undefined): string {
  if (!raw) return '—';
  const k = raw.toString().trim().toLowerCase();
  if (k === 'male' || k === 'm' || k === '남' || k === '남성') return '남성';
  if (k === 'female' || k === 'f' || k === '여' || k === '여성') return '여성';
  if (k === 'mixed' || k === 'both' || k === 'all') return '혼성';
  return raw; // 알 수 없는 값은 원본 유지 (데이터 디버깅 목적)
}

/**
 * HHI 집중도 해석 — DOJ/FTC Horizontal Merger Guidelines (2010).
 * 공식 임계값은 1500 / 2500. ≥ 2500 은 "Highly concentrated" (고집중) 가 정확한 표현이며
 * 단일 기업 독점에 가까운 5000 이상에서만 통상 "독과점" 으로 칭한다.
 */
export function interpretHHI(hhi: number): { label: string; color: string } {
  if (hhi < 1500) return { label: '경쟁 시장', color: 'emerald' };
  if (hhi < 2500) return { label: '중간 집중', color: 'amber' };
  if (hhi < 5000) return { label: '고집중', color: 'orange' };
  return { label: '독과점', color: 'rose' };
}

/**
 * HHI 임계값 가시화용 — DOJ/FTC 2010 + 5000 추가 단계.
 * 색상 4단계: 초록(경쟁) → 황(중간) → 주황(고집중) → 빨강(독과점).
 */
export const HHI_SEGMENTS = [
  { label: '경쟁', max: 1500, color: 'emerald' },
  { label: '중간', max: 2500, color: 'amber' },
  { label: '고집중', max: 5000, color: 'orange' },
  { label: '독과점', max: 10000, color: 'rose' },
] as const;

/**
 * 반경 포화도 임계값 — backend commercial_intelligence._saturation_bucket 와 동일.
 * 반경 500m 기준 동종업종 매장 수: sparse 0~2 / low 3~5 / medium 6~10 / high 11~20 / saturated 21+.
 * 다른 반경은 면적비율 (radius/500)² 로 보정한 값에 적용.
 */
export const SATURATION_SEGMENTS = [
  { label: '희박', max: 3, color: 'emerald' },
  { label: '낮음', max: 6, color: 'lime' },
  { label: '중간', max: 11, color: 'amber' },
  { label: '높음', max: 21, color: 'orange' },
  { label: '포화', max: 40, color: 'rose' },
] as const;

/** enum 안전 접근 — 키 없으면 fallback */
export function safeMap<T extends Record<string, unknown>>(
  map: T,
  key: string | null | undefined,
  fallback: T[keyof T],
): T[keyof T] {
  if (!key) return fallback;
  return (map[key] as T[keyof T]) ?? fallback;
}
