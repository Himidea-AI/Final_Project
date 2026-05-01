type Props = {
  on: boolean;
  onChange: (on: boolean) => void;
  ariaLabel?: string;
  size?: 'sm' | 'md';
};

/**
 * ON/OFF 토글 스위치 — painted liquid-glass 시각 (2026-05-01).
 * - ON  : track bg-primary (Deep Blue) + inset highlight + brand soft glow
 * - OFF : track bg-card (white) + inset 미묘한 brand-tint + 흰 edge ring
 * - thumb: bg-card 흰 알약, 부드러운 cubic-bezier 슬라이드
 */
export function Toggle({ on, onChange, ariaLabel, size = 'md' }: Props) {
  const dim =
    size === 'sm'
      ? { track: 'w-9 h-5', thumb: 'h-3.5 w-3.5', shift: 16 }
      : { track: 'w-11 h-6', thumb: 'h-4 w-4', shift: 20 };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={() => onChange(!on)}
      className={
        `relative ${dim.track} rounded-full transition-all duration-300 shrink-0 focus:outline-none focus:ring-2 focus:ring-primary/30 ` +
        (on
          ? // ON: Deep Blue track + 위쪽 inset white highlight + 아래쪽 inset darken + 외곽 soft glow
            'bg-primary shadow-[inset_0_1px_2px_rgba(255,255,255,0.25),inset_0_-1px_2px_rgba(0,0,0,0.15),0_2px_6px_rgba(0,44,209,0.3)]'
          : // OFF: white track + 미묘한 inset brand-tint + 흰 edge ring + soft drop
            'bg-card border border-border shadow-[inset_0_1px_2px_rgba(0,44,209,0.04),inset_0_-1px_2px_rgba(255,255,255,0.6),0_1px_3px_rgba(20,30,60,0.08)]')
      }
    >
      <span
        className={`absolute top-1/2 -translate-y-1/2 left-0.5 ${dim.thumb} rounded-full bg-card shadow-[0_1px_2px_rgba(0,0,0,0.18),0_0_0_0.5px_rgba(0,0,0,0.05)] transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]`}
        style={{ transform: `translate(${on ? dim.shift : 0}px, -50%)` }}
      />
    </button>
  );
}
