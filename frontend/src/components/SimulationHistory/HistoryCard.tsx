import { Calendar, FileDown, Store, Trash2, User } from 'lucide-react';
import type { SimulationHistoryItem, SimulationKind } from '../../types/simulationHistory';
import { formatDocumentId } from '../../types/simulationHistory';
import { useAuth } from '../../auth/AuthContext';

interface HistoryCardProps {
  item: SimulationHistoryItem;
  onOpen: (id: number, kind: SimulationKind) => void;
  onDelete?: (id: number, kind: SimulationKind) => void;
  onDownloadPdf?: (id: number, kind: SimulationKind) => void;
}

const SIGNAL_CLS: Record<string, string> = {
  green: 'bg-success/15 text-success border-success/40',
  yellow: 'bg-warning/15 text-warning border-warning/40',
  red: 'bg-danger/15 text-danger border-danger/40',
};

const SIGNAL_LABEL: Record<string, string> = {
  green: 'GREEN',
  yellow: 'YELLOW',
  red: 'RED',
};

/** kind badge — Deep Blue (foresee) / Vibrant Purple chart-4 (ai) / Cyan chart-2 (abm). */
const KIND_BADGE_CLS: Record<SimulationKind, string> = {
  foresee: 'bg-primary/10 text-primary border-primary/40',
  ai: 'bg-chart-4/10 text-chart-4 border-chart-4/40',
  abm: 'bg-chart-2/10 text-chart-2 border-chart-2/40',
};

const KIND_LABEL: Record<SimulationKind, string> = {
  foresee: 'ML 예측',
  ai: 'AI 분석',
  abm: 'ABM 시뮬',
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
  const { user } = useAuth();
  const isMaster = user?.role === 'master';
  const showManagerBadge = isMaster && item.manager_name && item.manager_id !== user?.id;
  const signalKey = item.market_entry_signal ?? '';
  const signalCls = SIGNAL_CLS[signalKey] ?? 'bg-muted/40 text-foreground border-border';
  const signalLbl = SIGNAL_LABEL[signalKey] ?? '—';
  const docId = formatDocumentId(item.id);
  const kindCls = KIND_BADGE_CLS[item.kind];
  const kindLbl = KIND_LABEL[item.kind];

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item.id, item.kind)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(item.id, item.kind);
        }
      }}
      className="cursor-pointer rounded-lg border border-border bg-muted p-4 transition-colors duration-200 hover:border-primary/40 hover:bg-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono">{formatWhen(item.created_at)}</span>
            <span className="ml-1 rounded bg-card/60 px-1.5 py-0.5 text-[0.625rem] font-mono text-primary">
              {docId}
            </span>
            {/* kind badge — DB 분리 후 양 테이블 머지 list 에서 행 출처 식별 */}
            <span
              className={`ml-1 inline-flex items-center rounded-full border px-2 py-0.5 text-[0.625rem] font-bold ${kindCls}`}
            >
              {kindLbl}
            </span>
            {showManagerBadge && (
              <span className="ml-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[0.625rem] font-bold text-primary">
                by {item.manager_name}
              </span>
            )}
          </div>
          <h3 className="mt-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-foreground">
            <User className="h-4 w-4 text-muted-foreground" />
            <span>{item.client_name}</span>
          </h3>
          <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            <Store className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-foreground">{item.brand_name}</span> —{' '}
            <span className="text-primary">{item.district}</span>
            {item.business_type && (
              <span className="ml-1 text-muted-foreground">· {item.business_type}</span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[0.625rem] font-bold ${signalCls}`}
            >
              ● {signalLbl}
            </span>
            {item.ai_verdict_summary && (
              <span className="truncate text-xs text-muted-foreground">
                {item.ai_verdict_summary}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpen(item.id, item.kind);
          }}
          className="rounded-md border border-primary/60 bg-primary/10 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/20"
        >
          상세 보기
        </button>
        {onDownloadPdf && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDownloadPdf(item.id, item.kind);
            }}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-3 py-2 text-xs font-medium text-foreground hover:bg-muted/80"
          >
            <FileDown className="h-3.5 w-3.5" />
            PDF
          </button>
        )}
        {onDelete && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm(`${item.client_name} 고객님 시뮬 이력을 삭제할까요?`)) {
                onDelete(item.id, item.kind);
              }
            }}
            className="ml-auto inline-flex items-center gap-1 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs font-medium text-danger hover:bg-danger/20"
            aria-label="삭제"
          >
            <Trash2 className="h-3.5 w-3.5" />
            삭제
          </button>
        )}
      </div>
    </article>
  );
}
