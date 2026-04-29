/**
 * NarrativeText — AI 나레이션 안의 숫자/퍼센트/배수를 포인트 컬러(cyan)로 자동 하이라이트.
 *
 * 레퍼런스 패턴: *"유동인구 **+38%** 우위, 경쟁 밀도 **+1.2σ**"* — 수치가 한눈에 읽힘.
 * 단순 regex split으로 성능·의존성 0. 서버에서 마크다운 받아올 필요 없음.
 *
 * 매칭 대상: 부호±숫자(+단위) 패턴
 *   - 38%, +38%, -12.5%
 *   - 1.2σ, ±1.5
 *   - 4.8억, 248만, 1,820원, 14건
 *   - 72/100, 3Q, 5년
 *   - P10, P50, P90 (분위수)
 */

import { Fragment, useMemo } from 'react';

// (?<!Q) — Q1·Q2 같은 분기 표기에서 숫자만 강조되어 "115,450,000원"처럼 잘못 읽히는 사례 회피.
//   "Q1 15,450,000원"  → Q1 plain + 15,450,000원 강조 (정상)
//   "1Q 매출"           → 1Q 통째 강조 (단위 Q 매칭은 lookbehind와 무관하게 유지)
const HIGHLIGHT_PATTERN =
  /(?<!Q)([+\-±]?\d[\d,]*(?:\.\d+)?(?:%|σ|억|만|원|건|점|배|분|초|시|일|월|년|Q|\/100|\/10|명)?|P(?:10|25|50|75|90|95))/gu;

interface Props {
  text: string | null | undefined;
  className?: string;
  /** 강조 색상 클래스 (기본: cyan) */
  highlightClass?: string;
}

export function NarrativeText({
  text,
  className = 'text-sm text-stone-500 leading-relaxed',
  highlightClass = 'text-cyan-400 font-bold',
}: Props) {
  const parts = useMemo(() => {
    if (!text) return [] as { text: string; highlight: boolean }[];
    const segments: { text: string; highlight: boolean }[] = [];
    let lastIdx = 0;
    const matches = [...text.matchAll(HIGHLIGHT_PATTERN)];
    for (const m of matches) {
      const idx = m.index ?? 0;
      if (idx > lastIdx) {
        segments.push({ text: text.slice(lastIdx, idx), highlight: false });
      }
      segments.push({ text: m[0], highlight: true });
      lastIdx = idx + m[0].length;
    }
    if (lastIdx < text.length) {
      segments.push({ text: text.slice(lastIdx), highlight: false });
    }
    return segments;
  }, [text]);

  if (!text) return null;

  return (
    <p className={className}>
      {parts.map((p, i) => (
        <Fragment key={i}>
          {p.highlight ? (
            <span className={`tabular-nums ${highlightClass}`}>{p.text}</span>
          ) : (
            p.text
          )}
        </Fragment>
      ))}
    </p>
  );
}
