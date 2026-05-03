import { useEffect, useRef, useState } from 'react';
import { Calendar, Search, ChevronDown } from 'lucide-react';
import type { HistoryFilterParams } from '../../types/simulationHistory';

interface HistoryFilterProps {
  value: HistoryFilterParams;
  onChange: (next: HistoryFilterParams) => void;
}

type RangePreset = 'today' | 'week' | 'month' | '30d' | 'all' | 'custom';

type SortKey = NonNullable<HistoryFilterParams['sort']>;

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'created_at_desc', label: '최신순' },
  { value: 'client_name_asc', label: '고객명 가나다순' },
];

// 프리셋 → {from, to} ISO date (to는 오늘)
function computeRange(preset: Exclude<RangePreset, 'custom'>): {
  from: string | undefined;
  to: string | undefined;
} {
  const today = new Date();
  const iso = (d: Date) => d.toISOString().slice(0, 10);

  if (preset === 'all') return { from: undefined, to: undefined };
  if (preset === 'today') return { from: iso(today), to: iso(today) };

  if (preset === 'week') {
    const start = new Date(today);
    const day = start.getDay();
    const diffToMon = (day + 6) % 7;
    start.setDate(start.getDate() - diffToMon);
    return { from: iso(start), to: iso(today) };
  }

  if (preset === 'month') {
    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    return { from: iso(start), to: iso(today) };
  }

  // 30d
  const start = new Date(today);
  start.setDate(start.getDate() - 29);
  return { from: iso(start), to: iso(today) };
}

export function HistoryFilter({ value, onChange }: HistoryFilterProps) {
  // 고객명 debounce 300ms
  const [nameDraft, setNameDraft] = useState<string>(value.client_name ?? '');
  useEffect(() => {
    const t = setTimeout(() => {
      if ((value.client_name ?? '') !== nameDraft) {
        onChange({ ...value, client_name: nameDraft || undefined, page: 1 });
      }
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nameDraft]);

  const [preset, setPreset] = useState<RangePreset>('30d');
  const applyPreset = (p: RangePreset) => {
    setPreset(p);
    if (p === 'custom') return;
    const { from, to } = computeRange(p);
    onChange({ ...value, from_date: from, to_date: to, page: 1 });
  };

  // 커스텀 정렬 드롭다운 — outside click close
  const [sortOpen, setSortOpen] = useState(false);
  const sortRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!sortOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (!sortRef.current?.contains(e.target as Node)) setSortOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [sortOpen]);

  const currentSort = value.sort ?? 'created_at_desc';
  const currentSortLabel = SORT_OPTIONS.find((o) => o.value === currentSort)?.label ?? '최신순';

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        {/* 검색 */}
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            placeholder="고객명 검색 (부분 일치)"
            className="w-full rounded-lg border border-border bg-card pl-9 pr-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/60 focus:outline-none focus:ring-1 focus:ring-primary/40 transition-colors"
          />
        </div>

        {/* 기간 프리셋 — 세그먼트 스타일 */}
        <div className="flex items-center gap-0.5 rounded-lg border border-border bg-card p-1">
          {(
            [
              ['today', '오늘'],
              ['week', '이번 주'],
              ['month', '이번 달'],
              ['30d', '최근 30일'],
              ['all', '전체'],
              ['custom', '커스텀'],
            ] as const
          ).map(([k, label]) => {
            const active = preset === k;
            return (
              <button
                key={k}
                type="button"
                onClick={() => applyPreset(k)}
                className={`rounded-md px-3 py-2 min-h-[36px] text-[0.6875rem] font-semibold transition-all ${
                  active
                    ? 'bg-primary/15 text-primary border border-primary/40'
                    : 'border border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* 커스텀 날짜 — native date picker (접근성 + 브라우저 달력 유지) */}
        {preset === 'custom' && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <input
              type="date"
              value={value.from_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, from_date: e.target.value || undefined, page: 1 })
              }
              className="rounded-lg border border-border bg-card px-2 py-1.5 text-foreground focus:border-primary/60 focus:outline-none"
            />
            <span className="text-muted-foreground/70">~</span>
            <input
              type="date"
              value={value.to_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, to_date: e.target.value || undefined, page: 1 })
              }
              className="rounded-lg border border-border bg-card px-2 py-1.5 text-foreground focus:border-primary/60 focus:outline-none"
            />
          </div>
        )}

        {/* 정렬 — 커스텀 드롭다운 (통일성) */}
        <div ref={sortRef} className="relative ml-auto">
          <button
            type="button"
            onClick={() => setSortOpen((o) => !o)}
            aria-haspopup="listbox"
            aria-expanded={sortOpen}
            aria-label="정렬 기준 선택"
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground hover:border-primary/50 transition-colors min-w-[170px] justify-between"
          >
            <span className="text-muted-foreground tracking-wider uppercase text-[0.625rem]">
              정렬
            </span>
            <span className="flex-1 text-left ml-2">{currentSortLabel}</span>
            <ChevronDown
              size={14}
              className={`text-muted-foreground transition-transform duration-200 ${sortOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {sortOpen && (
            <div
              role="listbox"
              className="absolute right-0 z-50 mt-1 min-w-[180px] overflow-hidden rounded-lg border border-border bg-card shadow-2xl"
            >
              {SORT_OPTIONS.map((opt) => {
                const active = currentSort === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onChange({ ...value, sort: opt.value, page: 1 });
                      setSortOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                      active ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted/60'
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
