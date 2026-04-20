import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '../../stores/simulationStore';
import { X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export function SimulationFloatingWidget() {
  const status = useSimulationStore((s) => s.status);
  const progress = useSimulationStore((s) => s.progress);
  const stage = useSimulationStore((s) => s.stage);
  const startedAt = useSimulationStore((s) => s.startedAt);
  const params = useSimulationStore((s) => s.params);
  const cancel = useSimulationStore((s) => s.cancelSimulation);
  const dismiss = useSimulationStore((s) => s.dismissResult);
  const start = useSimulationStore((s) => s.startSimulation);
  const navigate = useNavigate();

  if (status === 'idle') return null;

  const goToSimulator = () => navigate('/simulator');

  const etaSec = startedAt ? Math.max(0, Math.round((90 - progress) / 0.9)) : 0;

  const baseClasses =
    'fixed bottom-6 right-6 z-50 flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-slate-900/95 p-4 shadow-2xl ring-1 backdrop-blur';

  if (status === 'running') {
    return (
      <div className={`${baseClasses} ring-cyan-400/60`}>
        <div className="flex items-center gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
          <div className="flex-1 text-sm font-semibold text-slate-100">
            SIMULATING {Math.round(progress)}%
          </div>
          <button
            onClick={cancel}
            className="text-slate-400 hover:text-slate-200"
            aria-label="취소"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-slate-700"
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="시뮬레이션 진행률"
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="truncate">{stage}</span>
          <span>ETA ~{etaSec}s</span>
        </div>
        <button
          onClick={goToSimulator}
          className="mt-1 self-start text-xs font-medium text-cyan-300 hover:text-cyan-200"
        >
          시뮬레이터로 이동 →
        </button>
      </div>
    );
  }

  if (status === 'done') {
    return (
      <div className={`${baseClasses} ring-cyan-400/60`}>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-cyan-400" />
          <div className="flex-1 text-sm font-semibold text-slate-100">ANALYSIS COMPLETE</div>
          <button
            onClick={dismiss}
            className="text-slate-400 hover:text-slate-200"
            aria-label="닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <button
          onClick={goToSimulator}
          className="rounded-md bg-cyan-500/20 px-3 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/30"
        >
          결과 보기 →
        </button>
      </div>
    );
  }

  // error
  return (
    <div className={`${baseClasses} ring-red-500/60`}>
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <div className="flex-1 text-sm font-semibold text-slate-100">SIMULATION FAILED</div>
        <button onClick={dismiss} className="text-slate-400 hover:text-slate-200" aria-label="닫기">
          <X className="h-4 w-4" />
        </button>
      </div>
      <button
        onClick={() => params && start(params)}
        disabled={!params}
        className="rounded-md bg-red-500/20 px-3 py-2 text-sm font-medium text-red-200 hover:bg-red-500/30 disabled:opacity-40"
      >
        재시도
      </button>
    </div>
  );
}
