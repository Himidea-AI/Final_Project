/**
 * 마포구 16 행정동 → dong_code 매핑.
 *
 * SoT: backend `src/services/dong_resolver.py` `MAPO_DONG_MAP`.
 * backend 변경 시 이 dict 도 같이 갱신해야 함 (drift 위험).
 *
 * 사용처: TCN 시나리오 시뮬레이터 dong 드롭다운.
 */
export const MAPO_DONGS: { name: string; code: string }[] = [
  { name: '아현동', code: '11440555' },
  { name: '공덕동', code: '11440565' },
  { name: '도화동', code: '11440585' },
  { name: '용강동', code: '11440590' },
  { name: '대흥동', code: '11440600' },
  { name: '염리동', code: '11440610' },
  { name: '신수동', code: '11440630' },
  { name: '서강동', code: '11440655' },
  { name: '서교동', code: '11440660' },
  { name: '합정동', code: '11440680' },
  { name: '망원1동', code: '11440690' },
  { name: '망원2동', code: '11440700' },
  { name: '연남동', code: '11440710' },
  { name: '성산1동', code: '11440720' },
  { name: '성산2동', code: '11440730' },
  { name: '상암동', code: '11440740' },
];

export function resolveDongCode(name: string | undefined | null): string | null {
  if (!name) return null;
  return MAPO_DONGS.find((d) => d.name === name)?.code ?? null;
}

/** 역방향 — 코드(11440660) → 동 이름(서교동). 사용자 노출 텍스트 안 raw code 휴머나이즈용. */
export function resolveDongName(code: string | undefined | null): string | null {
  if (!code) return null;
  return MAPO_DONGS.find((d) => d.code === code)?.name ?? null;
}
