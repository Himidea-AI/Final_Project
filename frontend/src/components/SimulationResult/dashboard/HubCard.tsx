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

import { ArrowRight, AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';

type Accent = 'indigo' | 'cyan' | 'amber';

interface BaseProps {
  title: string;
  description: string;
  imgSrc: string;
  imgAlt: string;
  accent: Accent;
  /**
   * 슬라이스 실패(예: ML 예측 timeout) 시 카드 비활성화.
   * - 시각: grayscale + opacity 50% + 호버 효과 제거
   * - 동작: 클릭 차단 (Link/button 모두 pointer-events-none)
   * - 사용자 안내: disabledReason 표시 + 재시도 hint (SimulationFloatingWidget 의 재시도 버튼)
   */
  disabled?: boolean;
  disabledReason?: string;
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
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--primary) 50%, var(--primary) 60%, transparent 100%)',
    arrow: 'text-primary',
    ring: 'focus-visible:ring-primary',
  },
  cyan: {
    // AI 분석 카드 — chart-4 (Vibrant Purple, AI 톤). indigo(Deep Blue)/amber(Teal Green) 와 hue 280° 위치로 시각 분리.
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--chart-4) 50%, var(--chart-4) 60%, transparent 100%)',
    arrow: 'text-chart-4',
    ring: 'focus-visible:ring-chart-4',
  },
  amber: {
    // ABM 시뮬레이터 — chart-3 (Teal Green, 행동/분포 톤). indigo/cyan 와 hue 160° 위치로 시각 분리.
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--chart-3) 50%, var(--chart-3) 60%, transparent 100%)',
    arrow: 'text-chart-3',
    ring: 'focus-visible:ring-chart-3',
  },
};

export function HubCard(props: Props) {
  const { title, description, imgSrc, imgAlt, accent, disabled, disabledReason } = props;
  const a = ACCENT_CLASS[accent];

  // Link/button 양 모드 공통 className — focus ring, hover lift, transition.
  // disabled 일 때: grayscale + opacity-50 + 호버/transition 제거 + cursor-not-allowed.
  const commonCls = disabled
    ? 'group relative flex flex-col overflow-hidden rounded-3xl border border-border/60 bg-card/60 shadow-sm grayscale opacity-50 cursor-not-allowed pointer-events-none select-none'
    : `group relative flex flex-col overflow-hidden rounded-3xl border border-border/60 bg-card/60 shadow-sm transition-all duration-300 ease-out hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 motion-reduce:transition-none motion-reduce:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card ${a.ring}`;

  const inner = (
    <>
      {!disabled && (
        <div
          className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500 motion-reduce:hidden"
          style={{ background: a.laser }}
          aria-hidden="true"
        />
      )}

      <div className="relative z-10 flex h-full flex-col rounded-3xl bg-card/95">
        <div className="aspect-video overflow-hidden rounded-t-3xl">
          <img
            src={imgSrc}
            alt={imgAlt}
            loading="lazy"
            width={640}
            height={360}
            className={
              disabled
                ? 'h-full w-full object-cover'
                : 'h-full w-full object-cover transition-transform duration-700 ease-in-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100'
            }
          />
        </div>

        <div className="flex flex-1 flex-col p-8">
          <h3 className="text-2xl font-black text-foreground tracking-tight">{title}</h3>
          <p className="mt-3 flex-1 text-sm text-muted-foreground leading-relaxed">{description}</p>

          {disabled ? (
            <div className="mt-6 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-[0.6875rem] text-danger">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <div className="font-bold uppercase tracking-widest">분석 실패</div>
                {disabledReason && (
                  <div className="mt-1 text-danger/80 leading-relaxed">{disabledReason}</div>
                )}
                <div className="mt-1 text-danger/60">우측 위젯에서 재시도하세요</div>
              </div>
            </div>
          ) : (
            <div
              className={`mt-6 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest ${a.arrow}`}
            >
              진입
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transition-none" />
            </div>
          )}
        </div>
      </div>
    </>
  );

  // disabled 일 때 — Link/button 모두 비활성화. tabIndex=-1 로 키보드 진입도 차단.
  if (disabled) {
    return (
      <div
        aria-label={`${title} (분석 실패 — 비활성화)`}
        aria-disabled="true"
        className={commonCls}
      >
        {inner}
      </div>
    );
  }

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
