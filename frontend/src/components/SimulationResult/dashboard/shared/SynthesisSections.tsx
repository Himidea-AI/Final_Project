/**
 * SynthesisSections — synthesis_node final_recommendation 텍스트를 섹션별 블록으로 구조화 렌더링
 *
 * 2026-04-29 IM3-263 — 긴 텍스트 한 덩어리 → 의미 단위 섹션별 카드 블록으로 분리.
 *
 * 입력: synthesis_node 가 생성한 마크다운 텍스트
 *   "## 섹션명\n- bullet 1\n- bullet 2\n## 다음 섹션\n..."
 *
 * 처리:
 *   1. ## 헤더 패턴으로 섹션 분리 (줄바꿈 무관 — LLM 형식 변동성 대응)
 *   2. 각 섹션 본문에서 "- " bullet 추출
 *   3. 숫자/퍼센트/단위는 cyan 하이라이트 (NarrativeText 동일 패턴)
 *   4. 섹션 키워드 매칭으로 아이콘 부여
 *
 * CSS 제약 (사용자 요구):
 *   - height: auto, overflow 잘림 X, white-space: normal, word-break: keep-all
 *   - line-height 1.6~1.8 (leading-relaxed ~ leading-loose)
 *
 * Fallback: ## 헤더가 없으면 NarrativeText 형태로 단일 paragraph 렌더 (legacy 호환)
 */

import { useMemo } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Building2,
  MapPin,
  Target,
  TrendingUp,
  Users,
  type LucideIcon,
} from 'lucide-react';

interface Section {
  title: string;
  bullets: string[];
  paragraphs: string[];
}

interface Props {
  text: string | null | undefined;
  /** 헤더에 매칭 안 되는 섹션의 기본 아이콘 */
  fallbackIcon?: LucideIcon;
}

const HIGHLIGHT_PATTERN =
  /([+\-±]?\d[\d,]*(?:\.\d+)?(?:%|σ|억|만|원|건|점|배|분|초|시|일|월|년|Q|\/100|\/10|명)?|P(?:10|25|50|75|90|95))/gu;

// 섹션 헤더 키워드 → 아이콘 매핑 (한 키워드라도 포함되면 매칭)
const SECTION_ICONS: { keywords: string[]; icon: LucideIcon }[] = [
  { keywords: ['유동', '인구', '방문'], icon: Users },
  { keywords: ['입지', '추천', '위치', '접근성', '교통'], icon: MapPin },
  { keywords: ['상권', '경쟁'], icon: Building2 },
  { keywords: ['매출', '수익', '재무', '예측', '전망'], icon: TrendingUp },
  { keywords: ['리스크', '위험', '대응', '경고'], icon: AlertTriangle },
  { keywords: ['타겟', '전략', '제언', '권고', '타이밍'], icon: Target },
  { keywords: ['근거'], icon: BookOpen },
];

function pickIcon(title: string, fallback: LucideIcon): LucideIcon {
  for (const { keywords, icon } of SECTION_ICONS) {
    if (keywords.some((k) => title.includes(k))) return icon;
  }
  return fallback;
}

/**
 * 텍스트를 섹션별로 파싱.
 * - "## 헤더" 발견 시 새 섹션 시작.
 * - "- bullet" 발견 시 bullet 배열에 push.
 * - 그 외 라인은 paragraphs.
 */
function parseSections(raw: string): Section[] {
  // "## "가 줄 중간에 있어도 섹션 경계로 인식하도록 정규화 — LLM 출력이 줄바꿈 안 넣는 케이스 대응
  const normalized = raw.replace(/(\S)(##\s)/g, '$1\n$2');

  const sections: Section[] = [];
  let current: Section | null = null;

  for (const rawLine of normalized.split(/\n+/)) {
    const line = rawLine.trim();
    if (!line) continue;

    // 섹션 헤더
    const headerMatch = line.match(/^##\s+(.+?)\s*$/);
    if (headerMatch) {
      current = { title: headerMatch[1].trim(), bullets: [], paragraphs: [] };
      sections.push(current);
      continue;
    }

    if (!current) {
      // 헤더 없이 시작하는 텍스트는 "본문" 가짜 섹션으로 묶음
      current = { title: '', bullets: [], paragraphs: [] };
      sections.push(current);
    }

    // 한 줄 안에 여러 bullet이 - 로 인라인된 케이스 분리
    const inlineBullets = line.split(/\s-\s+/);
    for (let i = 0; i < inlineBullets.length; i++) {
      const piece = inlineBullets[i].trim();
      if (!piece) continue;
      const isBullet = i > 0 || piece.startsWith('- ');
      const cleaned = piece.replace(/^-\s+/, '').trim();
      if (!cleaned) continue;
      if (isBullet) current.bullets.push(cleaned);
      else current.paragraphs.push(cleaned);
    }
  }

  return sections.filter((s) => s.bullets.length > 0 || s.paragraphs.length > 0 || s.title);
}

/** 한 텍스트 안 숫자/단위 자동 하이라이트 */
function HighlightedText({ text }: { text: string }) {
  const parts = useMemo(() => {
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

  return (
    <>
      {parts.map((p, i) =>
        p.highlight ? (
          <span key={i} className="font-bold text-cyan-400">
            {p.text}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

export function SynthesisSections({ text, fallbackIcon = BookOpen }: Props) {
  const sections = useMemo(() => (text ? parseSections(text) : []), [text]);

  if (!text) return null;

  // ## 헤더가 하나도 없으면 단일 paragraph fallback
  const hasAnyHeader = sections.some((s) => s.title);
  if (!hasAnyHeader) {
    return (
      <p
        className="text-base text-stone-300"
        style={{
          lineHeight: '1.75',
          whiteSpace: 'normal',
          wordBreak: 'keep-all',
          height: 'auto',
        }}
      >
        <HighlightedText text={text} />
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {sections.map((section, idx) => {
        const Icon = section.title ? pickIcon(section.title, fallbackIcon) : fallbackIcon;
        return (
          <section
            key={`${section.title || 'intro'}-${idx}`}
            className="rounded-2xl border border-stone-700/50 bg-stone-900/50 p-6"
            style={{
              height: 'auto',
              wordBreak: 'keep-all',
            }}
          >
            {section.title && (
              <header className="mb-4 flex items-center gap-2.5">
                <Icon className="h-4 w-4 shrink-0 text-cyan-400" />
                <h4 className="text-sm font-black tracking-tight text-stone-100">
                  {section.title}
                </h4>
              </header>
            )}

            {section.paragraphs.length > 0 && (
              <div className="mb-3 space-y-2">
                {section.paragraphs.map((p, i) => (
                  <p
                    key={i}
                    className="text-sm text-stone-300"
                    style={{
                      lineHeight: '1.75',
                      whiteSpace: 'normal',
                      wordBreak: 'keep-all',
                    }}
                  >
                    <HighlightedText text={p} />
                  </p>
                ))}
              </div>
            )}

            {section.bullets.length > 0 && (
              <ul className="space-y-2.5">
                {section.bullets.map((b, i) => (
                  <li
                    key={i}
                    className="flex gap-2.5 text-sm text-stone-300"
                    style={{
                      lineHeight: '1.7',
                      whiteSpace: 'normal',
                      wordBreak: 'keep-all',
                    }}
                  >
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-cyan-400/70" />
                    <span className="flex-1">
                      <HighlightedText text={b} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
