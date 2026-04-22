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
    <div className="rounded-xl border border-[#3a3633] bg-[#2c2825] p-4">
      <div className="flex flex-wrap items-center gap-3">
        {/* 검색 */}
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9ca3af]" />
          <input
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            placeholder="고객명 검색 (부분 일치)"
            className="w-full rounded-lg border border-[#3a3633] bg-[#1e1b18] pl-9 pr-3 py-2.5 text-sm text-[#e2e8f0] placeholder:text-[#9ca3af]/60 focus:border-[#818cf8]/60 focus:outline-none focus:ring-1 focus:ring-[#818cf8]/40 transition-colors"
          />
        </div>

        {/* 기간 프리셋 — 세그먼트 스타일 */}
        <div className="flex items-center gap-0.5 rounded-lg border border-[#3a3633] bg-[#1e1b18] p-1">
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
                className={`rounded-md px-2.5 py-1.5 text-[11px] font-semibold transition-all ${
                  active
                    ? 'bg-[#818cf8]/15 text-[#818cf8] border border-[#818cf8]/40'
                    : 'border border-transparent text-[#9ca3af] hover:text-[#e2e8f0] hover:bg-[#3a3633]/40'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* 커스텀 날짜 — native date picker (접근성 + 브라우저 달력 유지) */}
        {preset === 'custom' && (
          <div className="flex items-center gap-2 text-xs text-[#9ca3af]">
            <Calendar className="h-4 w-4" />
            <input
              type="date"
              value={value.from_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, from_date: e.target.value || undefined, page: 1 })
              }
              className="rounded-lg border border-[#3a3633] bg-[#1e1b18] px-2 py-1.5 text-[#e2e8f0] focus:border-[#818cf8]/60 focus:outline-none"
            />
            <span className="text-[#9ca3af]/70">~</span>
            <input
              type="date"
              value={value.to_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, to_date: e.target.value || undefined, page: 1 })
              }
              className="rounded-lg border border-[#3a3633] bg-[#1e1b18] px-2 py-1.5 text-[#e2e8f0] focus:border-[#818cf8]/60 focus:outline-none"
            />
          </div>
        )}

        {/* 정렬 — 커스텀 드롭다운 (통일성) */}
        <div ref={sortRef} className="relative ml-auto">
          <button
            type="button"
            onClick={() => setSortOpen((o) => !o)}
            className="flex items-center gap-2 rounded-lg border border-[#3a3633] bg-[#1e1b18] px-3 py-2 text-xs text-[#e2e8f0] hover:border-[#818cf8]/50 transition-colors min-w-[170px] justify-between"
          >
            <span className="text-[#9ca3af] tracking-wider uppercase text-[10px]">정렬</span>
            <span className="flex-1 text-left ml-2">{currentSortLabel}</span>
            <ChevronDown
              size={14}
              className={`text-[#9ca3af] transition-transform duration-200 ${sortOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {sortOpen && (
            <div className="absolute right-0 z-50 mt-1 min-w-[180px] overflow-hidden rounded-lg border border-[#3a3633] bg-[#2c2825] shadow-2xl">
              {SORT_OPTIONS.map((opt) => {
                const active = currentSort === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      onChange({ ...value, sort: opt.value, page: 1 });
                      setSortOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                      active
                        ? 'bg-[#818cf8]/10 text-[#818cf8]'
                        : 'text-[#e2e8f0] hover:bg-[#3a3633]/60'
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
