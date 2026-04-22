import { useEffect, useState } from 'react';
import { Calendar, Search } from 'lucide-react';
import type { HistoryFilterParams } from '../../types/simulationHistory';

interface HistoryFilterProps {
  value: HistoryFilterParams;
  onChange: (next: HistoryFilterParams) => void;
}

type RangePreset = 'today' | 'week' | 'month' | '30d' | 'all' | 'custom';

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

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            placeholder="고객명 검색 (부분 일치)"
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 pl-9 pr-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/60"
          />
        </div>

        <div className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 p-1">
          {(
            [
              ['today', '오늘'],
              ['week', '이번 주'],
              ['month', '이번 달'],
              ['30d', '최근 30일'],
              ['all', '전체'],
              ['custom', '커스텀'],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => applyPreset(k)}
              className={`rounded px-2.5 py-1 text-xs font-semibold transition-colors ${
                preset === k
                  ? 'bg-amber-500 text-zinc-900'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {preset === 'custom' && (
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Calendar className="h-4 w-4" />
            <input
              type="date"
              value={value.from_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, from_date: e.target.value || undefined, page: 1 })
              }
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200"
            />
            <span>~</span>
            <input
              type="date"
              value={value.to_date ?? ''}
              onChange={(e) =>
                onChange({ ...value, to_date: e.target.value || undefined, page: 1 })
              }
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200"
            />
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-zinc-500">정렬</span>
          <select
            value={value.sort ?? 'created_at_desc'}
            onChange={(e) =>
              onChange({
                ...value,
                sort: e.target.value as HistoryFilterParams['sort'],
                page: 1,
              })
            }
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-200"
          >
            <option value="created_at_desc">최신순</option>
            <option value="client_name_asc">고객명 가나다순</option>
          </select>
        </div>
      </div>
    </div>
  );
}
