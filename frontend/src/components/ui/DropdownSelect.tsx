/**
 * DropdownSelect — 자체 listbox 드롭다운 (native select 회피).
 *
 * AddCandidateModal 에서 추출 (2026-05-04) — 디자인 통일 위해 시나리오 헤더 등 다른 자리에서 재사용.
 *
 * 패턴:
 *   - button (ChevronRight, rotate-90 on open) + listbox (mt-1, max-h-52, custom-scrollbar)
 *   - outside click + ESC close (옵션)
 *   - compact: 라벨 없이 h-9 (인라인 헤더용) / default: 라벨 + h-10 (form input)
 */

import { useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';

interface Props {
  /** 옵션 라벨 (없으면 인라인). compact 모드에선 사용 X. */
  label?: string;
  value: string;
  onChange: (next: string) => void;
  options: string[];
  disabled?: boolean;
  placeholder?: string;
  /** true: h-9 인라인 (헤더용). false: h-10 + 라벨 (form input). */
  compact?: boolean;
  /** ARIA label — compact 모드처럼 라벨 없을 때 screen reader 용. */
  ariaLabel?: string;
}

export function DropdownSelect({
  label,
  value,
  onChange,
  options,
  disabled = false,
  placeholder = '—',
  compact = false,
  ariaLabel,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handle);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const triggerCls = compact
    ? 'relative flex h-9 items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 text-sm font-bold text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50'
    : 'relative flex h-10 w-full items-center justify-between rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50';

  const triggerEl = (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled || options.length === 0}
        className={triggerCls}
      >
        <span className="truncate">{value || placeholder}</span>
        <ChevronRight
          size={14}
          className={`text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          className="custom-scrollbar absolute z-50 mt-1 max-h-52 min-w-full overflow-y-auto rounded-lg border border-border bg-card shadow-2xl"
          style={{ overscrollBehavior: 'contain' }}
        >
          {options.map((opt) => {
            const active = opt === value;
            return (
              <button
                key={opt}
                role="option"
                aria-selected={active}
                onClick={() => {
                  onChange(opt);
                  setOpen(false);
                }}
                className={`flex w-full items-center whitespace-nowrap px-3 py-2 text-left text-xs transition-colors ${
                  active ? 'bg-primary/10 font-bold text-primary' : 'text-foreground hover:bg-muted'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );

  if (compact || !label) return triggerEl;

  return (
    <div>
      <label className="mb-1 block text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
        {label}
      </label>
      <div className="w-full">{triggerEl}</div>
    </div>
  );
}
