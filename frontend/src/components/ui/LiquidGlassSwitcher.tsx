/**
 * LiquidGlassSwitcher — segmented switcher with painted liquid-glass aesthetic.
 *
 * 외부 Apple liquid glass switcher 레퍼런스 채용 (3-option theme switch). 우리 환경 (light-only,
 * Tailwind v3, Deep Blue brand) 에 맞춰 재구성:
 *  - SVG `feDisplacementMap` 필터는 제거 (작은 토글에 과함 + 30KB base64 부담).
 *  - Painted glass = 반투명 multi-bg + inset highlight stack + soft drop shadow + sliding thumb.
 *  - 2-option 또는 N-option 모두 지원 (binary toggle 부터 3-option segmented 까지).
 *  - 활성 thumb 은 흰 카드 + Deep Blue 텍스트로 brand 색 시그널.
 *
 * 사용:
 *   binary  : options=[{value:false,label:'비활성'},{value:true,label:'활성'}]
 *   3-option: options=[{value:null,label:'전체'}, {value:'male',label:'남성'}, ...]
 */
import type { ReactNode } from 'react';

type Option<T> = {
  value: T;
  label: string;
  icon?: ReactNode;
};

type Props<T> = {
  options: readonly Option<T>[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel?: string;
  className?: string;
};

export function LiquidGlassSwitcher<T extends string | number | boolean | null>({
  options,
  value,
  onChange,
  ariaLabel,
  className = '',
}: Props<T>) {
  const activeIdx = options.findIndex((o) => o.value === value);
  const optionPct = 100 / options.length;

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={
        'relative inline-flex items-center p-1 rounded-full ' +
        // painted glass track — 반투명 multi-bg + 흰 edge ring inset + soft drop
        'bg-gradient-to-r from-white/40 via-white/60 to-white/40 ' +
        'shadow-[inset_0_1px_2px_rgba(0,44,209,0.04),inset_0_-1px_2px_rgba(255,255,255,0.7),0_2px_8px_rgba(20,30,60,0.06)] ' +
        'border border-white/50 ' +
        'transition-all duration-300 ' +
        className
      }
    >
      {/* Sliding thumb — 활성 옵션 자리로 슬라이드 */}
      {activeIdx >= 0 && (
        <div
          aria-hidden="true"
          className="absolute top-1 bottom-1 rounded-full bg-card shadow-[0_1px_2px_rgba(0,0,0,0.06),0_2px_4px_rgba(0,44,209,0.08)] transition-all duration-[350ms] ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{
            width: `calc(${optionPct}% - 4px)`,
            left: `calc(${activeIdx * optionPct}% + 2px)`,
          }}
        />
      )}

      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={
              'relative z-10 flex items-center justify-center gap-1.5 px-4 py-1.5 text-xs font-bold tracking-tight transition-colors duration-200 cursor-pointer select-none whitespace-nowrap ' +
              (active
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground')
            }
            style={{ minWidth: `${optionPct}%` }}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
