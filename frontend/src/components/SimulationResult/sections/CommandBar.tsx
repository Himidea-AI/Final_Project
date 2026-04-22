import type { SimulationOutput } from '../../../types';
import { GitCompare, FileText } from 'lucide-react';

interface Props {
  simResult: SimulationOutput;
  compareMode: boolean;
  onToggleCompare: () => void;
  onExportPdf: () => void;
}

export function CommandBar({ simResult, compareMode, onToggleCompare, onExportPdf }: Props) {
  const sim = simResult as SimulationOutput & Record<string, any>;

  const brand = sim.brand_name ?? '브랜드 미지정';
  const district = sim.winner_district ?? sim.target_district ?? '—';
  const reqId = sim.request_id ?? '—';
  const shortReqId = typeof reqId === 'string' ? reqId.slice(0, 8) : '—';

  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-zinc-700 bg-zinc-900/60 px-5 py-4 backdrop-blur">
      <div className="flex items-center gap-4">
        <div>
          <div className="text-sm font-semibold text-zinc-100">{brand}</div>
          <div className="text-xs text-zinc-400">
            {district} · <span className="font-mono">{shortReqId}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleCompare}
          aria-pressed={compareMode}
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
            compareMode
              ? 'border-amber-500 bg-amber-500/10 text-amber-400'
              : 'border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
          }`}
        >
          <GitCompare className="h-4 w-4" />
          <span>비교 모드 {compareMode ? 'ON' : 'OFF'}</span>
        </button>
        <button
          type="button"
          onClick={onExportPdf}
          className="flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700"
        >
          <FileText className="h-4 w-4" />
          <span>PDF 저장</span>
        </button>
      </div>
    </section>
  );
}
