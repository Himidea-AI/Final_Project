import { FileDown, Trash2 } from 'lucide-react';
import type { SimulationHistoryItem } from '../../types/simulationHistory';
import { formatDocumentId } from '../../types/simulationHistory';

interface HistoryCardProps {
  item: SimulationHistoryItem;
  onOpen: (id: number) => void;
  onDelete?: (id: number) => void;
  onDownloadPdf?: (id: number) => void;
}

const SIGNAL_CLS: Record<string, string> = {
  green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  yellow: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/40',
  red: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

const SIGNAL_LABEL: Record<string, string> = {
  green: 'GREEN',
  yellow: 'YELLOW',
  red: 'RED',
};

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d
      .toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
      .replace(/\. /g, '-')
      .replace(/\./g, '')
      .trim();
  } catch {
    return iso;
  }
}

export function HistoryCard({ item, onOpen, onDelete, onDownloadPdf }: HistoryCardProps) {
  const signalKey = item.market_entry_signal ?? '';
  const signalCls = SIGNAL_CLS[signalKey] ?? 'bg-stone-700/40 text-stone-300 border-stone-600';
  const signalLbl = SIGNAL_LABEL[signalKey] ?? '—';
  const docId = formatDocumentId(item.id);

  return (
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-4 transition-colors hover:border-stone-600">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-stone-500">
            <span>📅</span>
            <span className="font-mono">{formatWhen(item.created_at)}</span>
            <span className="ml-1 rounded bg-stone-900/60 px-1.5 py-0.5 text-[10px] font-mono text-indigo-400">
              {docId}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-stone-100">👤 {item.client_name}</span>
          </div>
          <div className="mt-1 text-xs text-stone-400">
            🏪 <span className="text-stone-200">{item.brand_name}</span> —{' '}
            <span className="text-indigo-400">{item.district}</span>
            {item.business_type && (
              <span className="ml-1 text-stone-500">· {item.business_type}</span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${signalCls}`}
            >
              ● {signalLbl}
            </span>
            {item.ai_verdict_summary && (
              <span className="truncate text-xs text-stone-400">{item.ai_verdict_summary}</span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => onOpen(item.id)}
          className="rounded-md border border-indigo-500/60 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20"
        >
          상세 보기
        </button>
        {onDownloadPdf && (
          <button
            type="button"
            onClick={() => onDownloadPdf(item.id)}
            className="inline-flex items-center gap-1 rounded-md border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs font-medium text-stone-300 hover:bg-stone-700"
          >
            <FileDown className="h-3.5 w-3.5" />
            PDF
          </button>
        )}
        {onDelete && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm(`${item.client_name} 고객님 시뮬 이력을 삭제할까요?`)) {
                onDelete(item.id);
              }
            }}
            className="ml-auto inline-flex items-center gap-1 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20"
            aria-label="삭제"
          >
            <Trash2 className="h-3.5 w-3.5" />
            삭제
          </button>
        )}
      </div>
    </div>
  );
}
