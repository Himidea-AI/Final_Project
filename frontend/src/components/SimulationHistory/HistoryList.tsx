import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HistoryCard } from './HistoryCard';
import { HistoryFilter } from './HistoryFilter';
import { ActivityDashboard } from './ActivityDashboard';
import { useSimulationHistory } from '../../hooks/useSimulationHistory';
import type { HistoryFilterParams } from '../../types/simulationHistory';

interface HistoryListProps {
  /** 초기 필터 — 기본: 최근 30일 · 최신순 */
  initialFilter?: HistoryFilterParams;
}

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

  const handleOpen = (id: number) => navigate(`/dashboard/history/${id}`);
  const handleDownloadPdf = (id: number) => navigate(`/dashboard/history/${id}?autopdf=1`);
  const handleDelete = async (id: number) => {
    await remove(id);
  };

  return (
    <div className="space-y-4">
      <ActivityDashboard items={items} total={total} isLoading={isLoading} />

      <HistoryFilter value={filter} onChange={setFilter} />

      <div className="flex items-center justify-between text-xs text-stone-400">
        <span>
          총 <span className="font-mono text-stone-100">{total}</span>건
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
              onDownloadPdf={handleDownloadPdf}
            />
          ))}
        </div>
      )}
    </div>
  );
}
