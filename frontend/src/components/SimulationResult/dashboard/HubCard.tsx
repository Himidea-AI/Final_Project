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

import type { CSSProperties } from 'react';
import { ArrowRight, AlertTriangle, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

/** 카드 도메인 — 색은 indigo(예측, brand primary) / violet(분석, --chart-4) / teal(시뮬, --chart-3).
 *  값 자체가 도메인을 가리켜서 색 선택 의도가 코드에서 self-documenting (이전 cyan/amber 네이밍 부채 정정). */
type Accent = 'predict' | 'analyze' | 'abm';

interface BaseProps {
  title: string;
  description: string;
  imgSrc: string;
  imgAlt: string;
  accent: Accent;
  /** CTA 라벨 — 카드별 의미 동사 ("예측 보기", "분석 보기", "시뮬 실행" 등). 이전 일괄 "진입" 대체. */
  ctaLabel: string;
  /**
   * 슬라이스 실패(예: ML 예측 timeout) 시 카드 비활성화.
   * - 시각: grayscale + opacity 50% + 호버 효과 제거
   * - 동작: 클릭 차단 (Link/button 모두 pointer-events-none)
   * - 사용자 안내: disabledReason 표시 + 재시도 hint (SimulationFloatingWidget 의 재시도 버튼)
   */
  disabled?: boolean;
  disabledReason?: string;
  /**
   * 슬라이스 로딩중(예: AI 분석 백그라운드 실행 중) 카드 비활성화.
   * - 시각: grayscale + opacity 50% + 호버 효과 제거 (disabled 와 동일)
   * - 동작: 클릭 차단
   * - 안내: 분석 실패 박스 대신 spinner + "분석 진행 중" 메시지
   * - 슬라이스 done 시 자동 색 복원 (re-render).
   */
  loading?: boolean;
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

/**
 * 카드 빛 효과 — 두 레이어:
 *   (a) laser: hover 시 카드 외곽으로 회전하는 conic-gradient. 평소엔 opacity-25 로 옅게,
 *       hover 시 opacity-100 으로 강해짐 → 카드별 색이 항상 살짝 외곽에 깔리는 인상.
 *   (b) content tint: content area (image 아래) bg 가 accent 색 그라디언트로 깔림 →
 *       정적 상태에서도 카드별 색 정체성. cssVar 로 indirect 참조해서 toggle/test 용이.
 */
const ACCENT_CLASS: Record<
  Accent,
  {
    laser: string;
    arrow: string;
    ring: string;
    chip: string;
    chipLabel: string;
    cssVar: string;
    hoverShadow: string;
  }
> = {
  predict: {
    // Deep Blue (brand primary) — ML 기반 정량 예측의 신뢰 톤
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--primary) 50%, var(--primary) 60%, transparent 100%)',
    arrow: 'text-primary',
    ring: 'focus-visible:ring-primary',
    chip: 'bg-primary text-primary-foreground',
    chipLabel: 'PREDICT',
    cssVar: 'var(--primary)',
    hoverShadow: 'hover:shadow-primary/20',
  },
  analyze: {
    // Vibrant Purple (--chart-4) — LLM/AI 정성 분석의 추상 톤. Deep Blue 와 hue 280° 위치로 시각 분리
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--chart-4) 50%, var(--chart-4) 60%, transparent 100%)',
    arrow: 'text-chart-4',
    ring: 'focus-visible:ring-chart-4',
    chip: 'bg-chart-4 text-white',
    chipLabel: 'ANALYZE',
    cssVar: 'var(--chart-4)',
    hoverShadow: 'hover:shadow-chart-4/20',
  },
  abm: {
    // Teal Green (--chart-3) — 행동/분포 시뮬의 활동 톤. Deep Blue/Purple 와 hue 160° 위치로 시각 분리
    laser:
      'conic-gradient(from 0deg, transparent 0%, transparent 40%, var(--chart-3) 50%, var(--chart-3) 60%, transparent 100%)',
    arrow: 'text-chart-3',
    ring: 'focus-visible:ring-chart-3',
    chip: 'bg-chart-3 text-white',
    chipLabel: 'ABM',
    cssVar: 'var(--chart-3)',
    hoverShadow: 'hover:shadow-chart-3/20',
  },
};

export function HubCard(props: Props) {
  const {
    title,
    description,
    imgSrc,
    imgAlt,
    accent,
    ctaLabel,
    disabled,
    disabledReason,
    loading,
  } = props;
  const a = ACCENT_CLASS[accent];

  // disabled (영구 실패) 또는 loading (진행 중) — 둘 다 시각/동작 비활성. 메시지만 분기.
  const inactive = disabled || loading;

  // Link/button 양 모드 공통 className — focus ring, hover lift, transition.
  // inactive 시: grayscale + opacity-50 + 호버/transition 제거 + cursor-not-allowed.
  // loading 은 transition 부드럽게 — done 시 grayscale → 컬러 복원이 자연스럽게 보이도록.
  const commonCls = inactive
    ? 'group relative flex flex-col overflow-hidden rounded-3xl border border-border bg-card shadow-md grayscale opacity-50 cursor-not-allowed pointer-events-none select-none transition-all duration-500'
    : `group relative flex flex-col overflow-hidden rounded-3xl border border-border bg-card shadow-md transition-all duration-300 ease-out hover:-translate-y-2 hover:shadow-2xl ${a.hoverShadow} motion-reduce:transition-none motion-reduce:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background ${a.ring}`;

  // Content area background — 이미지 아래 영역에 alpha 60% 흰 + accent tint.
  // alpha 로 laser (z-0 회전 광선) 가 카드 내용 영역에 비침. 60% 라 laser 의 40% 가 비침.
  // hover 시 laser opacity 40→100 으로 강해지며 카드 내용에 accent 색 빛이 분명하게 비침.
  // gradient 끝점 accent 12% — 정적 상태에서도 카드별 색감 식별 가능.
  // inactive 시엔 alpha 제거 (laser 도 안 그림 → 투명할 이유 없음).
  const contentBgStyle: CSSProperties = inactive
    ? { background: 'var(--card)' }
    : {
        background: `linear-gradient(180deg, rgba(255,255,255,0.6) 0%, color-mix(in srgb, ${a.cssVar} 12%, rgba(255,255,255,0.6)) 100%)`,
      };

  const inner = (
    <>
      {!inactive && (
        <>
          {/* (a) 회전 laser — 카드 외곽으로 회전하는 conic-gradient. 평소 옅게(40%), hover 시 강하게(100%). */}
          <div
            className="absolute inset-[-50%] z-0 animate-spin-slow opacity-40 group-hover:opacity-100 transition-opacity duration-500 motion-reduce:hidden"
            style={{ background: a.laser }}
            aria-hidden="true"
          />
          {/* (b) hover spotlight — 카드 중앙에서 퍼지는 정적 radial 광원. hover 시만 active.
                 회전 laser 와 달리 angle 에 무관하게 카드 안쪽에 항상 색감 — "카드 내용에 빛 비치는" 효과 핵심. */}
          <div
            className="pointer-events-none absolute inset-0 z-[1] opacity-0 transition-opacity duration-500 group-hover:opacity-100 motion-reduce:hidden"
            style={{
              background: `radial-gradient(ellipse at 50% 55%, color-mix(in srgb, ${a.cssVar} 28%, transparent) 0%, transparent 60%)`,
            }}
            aria-hidden="true"
          />
        </>
      )}

      {/* inner wrapper 는 투명 — laser 가 카드 안쪽까지 그대로 보이도록.
          image wrapper / content area 가 각자 자기 background 로 분리. */}
      <div className="relative z-10 flex h-full flex-col rounded-3xl">
        <div className="relative aspect-video overflow-hidden rounded-t-3xl bg-card">
          <img
            src={imgSrc}
            alt={imgAlt}
            loading="lazy"
            width={640}
            height={360}
            className={
              inactive
                ? 'h-full w-full object-cover'
                : 'h-full w-full object-cover transition-transform duration-700 ease-in-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100'
            }
          />
          {/* Hero 좌상단 도메인 chip — hover 전에도 카드별 정체성 즉시 식별 (h3 한국어 풀명과 분리된 영문 약어). */}
          <span
            className={`absolute left-4 top-4 z-10 inline-flex items-center rounded-full px-3 py-1 text-[0.625rem] font-bold uppercase tracking-[0.18em] shadow-sm ${a.chip}`}
          >
            {a.chipLabel}
          </span>
        </div>

        <div className="flex flex-1 flex-col p-8" style={contentBgStyle}>
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
          ) : loading ? (
            <div className="mt-6 flex items-center gap-2 rounded-lg border border-border bg-secondary p-3 text-[0.6875rem] text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
              <div>
                <div className="font-bold uppercase tracking-widest">분석 진행 중</div>
                <div className="mt-0.5 text-muted-foreground/80">
                  완료되면 자동으로 활성화됩니다.
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-6 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-widest text-foreground/70">
                {ctaLabel}
              </span>
              <span
                className={`inline-flex h-9 w-9 items-center justify-center rounded-full border border-current transition-all duration-300 group-hover:translate-x-1 group-hover:scale-110 motion-reduce:transition-none ${a.arrow}`}
                aria-hidden="true"
              >
                <ArrowRight className="h-4 w-4" />
              </span>
            </div>
          )}
        </div>
      </div>
    </>
  );

  // inactive 일 때 — Link/button 모두 비활성화. 키보드 진입도 차단.
  if (inactive) {
    const ariaLabel = disabled
      ? `${title} (분석 실패 — 비활성화)`
      : `${title} (분석 진행 중 — 비활성화)`;
    return (
      <div aria-label={ariaLabel} aria-disabled="true" className={commonCls}>
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
