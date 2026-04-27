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

/** HHI 집중도 해석 (미 법무부/FTC 표준) */
export function interpretHHI(hhi: number): { label: string; color: string } {
  if (hhi < 1500) return { label: '경쟁 시장', color: 'emerald' };
  if (hhi < 2500) return { label: '중간 집중', color: 'amber' };
  return { label: '독과점', color: 'rose' };
}

/** enum 안전 접근 — 키 없으면 fallback */
export function safeMap<T extends Record<string, unknown>>(
  map: T,
  key: string | null | undefined,
  fallback: T[keyof T],
): T[keyof T] {
  if (!key) return fallback;
  return (map[key] as T[keyof T]) ?? fallback;
}
