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
  const selectedDongs: string[] =
    sim.target_districts ?? (sim.target_district ? [sim.target_district] : []);

  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-stone-700 bg-stone-900/60 px-5 py-4 backdrop-blur">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-sm font-semibold text-stone-100">{brand}</div>
            <div className="text-xs text-stone-400">
              추천 입지: <span className="text-indigo-400 font-medium">{district}</span> ·{' '}
              <span className="font-mono">{shortReqId}</span>
            </div>
          </div>
        </div>
        {selectedDongs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-widest text-stone-500">분석 대상</span>
            {selectedDongs.map((dong) => (
              <span
                key={dong}
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                  dong === district
                    ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-300'
                    : 'border-stone-600 bg-stone-800 text-stone-400'
                }`}
              >
                {dong === district && <span className="mr-1">★</span>}
                {dong}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleCompare}
          aria-pressed={compareMode}
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
            compareMode
              ? 'border-indigo-500 bg-indigo-500/10 text-indigo-400'
              : 'border-stone-700 bg-stone-800 text-stone-300 hover:bg-stone-700'
          }`}
        >
          <GitCompare className="h-4 w-4" />
          <span>비교 모드 {compareMode ? 'ON' : 'OFF'}</span>
        </button>
        <button
          type="button"
          onClick={onExportPdf}
          className="flex items-center gap-2 rounded-md border border-stone-700 bg-stone-800 px-3 py-2 text-xs font-medium text-stone-300 hover:bg-stone-700"
        >
          <FileText className="h-4 w-4" />
          <span>PDF 저장</span>
        </button>
      </div>
    </section>
  );
}
