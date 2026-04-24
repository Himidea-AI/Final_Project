import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitCompareArrows, X } from 'lucide-react';
import { HistoryCard } from './HistoryCard';
import { HistoryFilter } from './HistoryFilter';
import { useSimulationHistory } from '../../hooks/useSimulationHistory';
import type { HistoryFilterParams } from '../../types/simulationHistory';

interface HistoryListProps {
  /** 초기 필터 — 기본: 최근 30일 · 최신순 */
  initialFilter?: HistoryFilterParams;
}

const MAX_COMPARE = 4;

function getInitialRange30d(): { from: string; to: string } {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - 29);
  return { from: iso(start), to: iso(today) };
}

export function HistoryList({ initialFilter }: HistoryListProps) {
  const navigate = useNavigate();
  const defaultRange = useMemo(() => getInitialRange30d(), []);
  const [filter, setFilter] = useState<HistoryFilterParams>(
    initialFilter ?? {
      from_date: defaultRange.from,
      to_date: defaultRange.to,
      page: 1,
      size: 20,
      sort: 'created_at_desc',
    },
  );

  const { items, total, isLoading, error, remove, refetch } = useSimulationHistory(filter);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const handleOpen = (id: number) => navigate(`/dashboard/history/${id}`);
  const handleDelete = async (id: number) => {
    await remove(id);
    setSelectedIds((prev) => prev.filter((sid) => sid !== id));
  };
  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((sid) => sid !== id);
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, id];
    });
  };
  const clearSelection = () => setSelectedIds([]);
  const goCompare = () => {
    if (selectedIds.length < 2) return;
    navigate(`/dashboard/compare?ids=${selectedIds.join(',')}`);
  };

  const selectionFull = selectedIds.length >= MAX_COMPARE;

  return (
    <div className="space-y-4">
      <HistoryFilter value={filter} onChange={setFilter} />

      <div className="flex items-center justify-between text-xs text-stone-400">
        <span>
          총 <span className="font-mono text-stone-100">{total}</span>건
          {selectedIds.length > 0 && (
            <span className="ml-3 text-indigo-400">
              · <span className="font-mono">{selectedIds.length}</span>건 선택됨
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={() => void refetch()}
          className="text-stone-400 hover:text-stone-100"
          aria-label="새로고침"
        >
          새로고침
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center text-sm text-stone-500">
          불러오는 중…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center text-sm text-stone-400">
          조건에 맞는 시뮬 이력이 없습니다
        </div>
      ) : (
        <div className="space-y-3 pb-24">
          {items.map((item) => (
            <HistoryCard
              key={item.id}
              item={item}
              onOpen={handleOpen}
              onDelete={handleDelete}
              selectable={{
                checked: selectedIds.includes(item.id),
                disabled: selectionFull,
                onToggle: toggleSelect,
              }}
            />
          ))}
        </div>
      )}

      {/* 선택 플로팅 바 */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2">
          <div className="flex items-center gap-3 rounded-2xl border border-indigo-500/40 bg-[#2c2825] px-5 py-3 shadow-[0_10px_40px_rgba(129,140,248,0.25)]">
            <span className="text-xs text-stone-400">
              <span className="font-mono text-stone-100">{selectedIds.length}</span>
              <span className="text-stone-500">/{MAX_COMPARE}</span> 건 선택됨
              {selectionFull && (
                <span className="ml-2 text-[10px] text-amber-400">· 최대 도달</span>
              )}
            </span>
            <button
              type="button"
              onClick={goCompare}
              disabled={selectedIds.length < 2}
              className="inline-flex items-center gap-2 rounded-lg bg-[#818cf8] px-4 py-2 text-xs font-bold text-[#1e1b18] transition-colors hover:bg-[#6366f1] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <GitCompareArrows className="h-3.5 w-3.5" />
              비교하기
            </button>
            <button
              type="button"
              onClick={clearSelection}
              className="inline-flex items-center gap-1 rounded-lg border border-stone-700 bg-transparent px-3 py-2 text-xs font-medium text-stone-400 hover:bg-stone-800 hover:text-stone-100"
              aria-label="선택 해제"
            >
              <X className="h-3.5 w-3.5" />
              해제
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
