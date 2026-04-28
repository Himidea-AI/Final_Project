/**
 * HubCard — Dashboard Hub 의 3 카드 공통 컴포넌트.
 * - Hero 이미지 (Unsplash CDN, lazy load) + 제목 + 짧은 설명 + arrow CTA
 * - hover: 이미지 scale 1.10 (700ms ease-in-out), 카드 -translate-y-2
 * - 외곽 레이저 효과 (PricingCard.tsx:28-31 패턴 — conic-gradient + animate-spin-slow)
 * - 색 시멘틱: indigo (예측) / cyan (분석) / amber (ABM)
 * - touch ≥44pt (카드 전체 클릭), focus ring, reduced-motion respect
 *
 * 2026-04-28 H7 — `to` (Link) 또는 `onClick` (button) 둘 중 하나 모드.
 *   라우트 기반(/dashboard) 진입은 `to`, History 페이지의 in-page state 전환은 `onClick`.
 *   둘 다 없으면 dev 환경에서 콘솔 경고 (XOR 강제).
 */

import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

type Accent = 'indigo' | 'cyan' | 'amber';

interface BaseProps {
  title: string;
  description: string;
  imgSrc: string;
  imgAlt: string;
  accent: Accent;
}

interface LinkProps extends BaseProps {
  to: string;
  onClick?: never;
}

interface ButtonProps extends BaseProps {
  to?: never;
  onClick: () => void;
}

type Props = LinkProps | ButtonProps;

const ACCENT_CLASS: Record<Accent, { laser: string; arrow: string; ring: string }> = {
  indigo: {
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
    arrow: 'text-indigo-400',
    ring: 'focus-visible:ring-indigo-400',
  },
  cyan: {
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, #22d3ee 50%, #67e8f9 60%, transparent 100%)',
    arrow: 'text-cyan-400',
    ring: 'focus-visible:ring-cyan-400',
  },
  amber: {
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, #f59e0b 50%, #fbbf24 60%, transparent 100%)',
    arrow: 'text-amber-400',
    ring: 'focus-visible:ring-amber-400',
  },
};

export function HubCard(props: Props) {
  const { title, description, imgSrc, imgAlt, accent } = props;
  const a = ACCENT_CLASS[accent];

  // Link/button 양 모드 공통 className — focus ring, hover lift, transition.
  const commonCls = `group relative flex flex-col overflow-hidden rounded-3xl border border-stone-800/60 bg-stone-900/60 shadow-sm transition-all duration-300 ease-out hover:-translate-y-2 hover:shadow-2xl hover:shadow-indigo-500/10 motion-reduce:transition-none motion-reduce:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e1b18] ${a.ring}`;

  const inner = (
    <>
      <div
        className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500 motion-reduce:hidden"
        style={{ background: a.laser }}
        aria-hidden="true"
      />

      <div className="relative z-10 flex h-full flex-col rounded-3xl bg-stone-900/95">
        <div className="aspect-video overflow-hidden rounded-t-3xl">
          <img
            src={imgSrc}
            alt={imgAlt}
            loading="lazy"
            width={640}
            height={360}
            className="h-full w-full object-cover transition-transform duration-700 ease-in-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100"
          />
        </div>

        <div className="flex flex-1 flex-col p-8">
          <h3 className="text-2xl font-black text-stone-100 tracking-tight">{title}</h3>
          <p className="mt-3 flex-1 text-sm text-stone-400 leading-relaxed">{description}</p>

          <div
            className={`mt-6 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest ${a.arrow}`}
          >
            진입
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transition-none" />
          </div>
        </div>
      </div>
    </>
  );

  if (props.to !== undefined) {
    return (
      <Link to={props.to} aria-label={`${title} 화면 진입`} className={commonCls}>
        {inner}
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={props.onClick}
      aria-label={`${title} 화면 진입`}
      className={`text-left ${commonCls}`}
    >
      {inner}
    </button>
  );
}
