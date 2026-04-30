import { useState, useRef, useEffect } from 'react';
import { Info } from 'lucide-react';

type Props = {
  text: string;
  size?: number;
  className?: string;
};

/**
 * 옵션 라벨 옆에 붙는 통일된 ⓘ 툴팁.
 * - 14px Lucide Info, muted → hover primary
 * - popover: dark callout (bg-foreground text-card), 라이트 배경에서 명확
 * - 키보드 focus 가능, ESC 닫힘
 */
export function InfoTooltip({ text, size = 14, className = '' }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  return (
    <span ref={ref} className={`relative inline-flex items-center ${className}`}>
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => {
          e.preventDefault();
          setOpen((v) => !v);
        }}
        aria-label="정보"
        className="inline-flex items-center justify-center text-muted-foreground hover:text-primary focus:text-primary focus:outline-none transition-colors"
      >
        <Info size={size} strokeWidth={2} />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-4 py-3 rounded-md bg-foreground text-card text-[11px] leading-relaxed font-medium text-center whitespace-normal max-w-[260px] w-max shadow-lg pointer-events-none"
        >
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-foreground" />
        </span>
      )}
    </span>
  );
}
