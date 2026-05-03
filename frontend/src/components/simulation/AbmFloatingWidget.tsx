import { useNavigate, useLocation } from 'react-router-dom';
import { Activity, AlertCircle, Loader2, X } from 'lucide-react';
import { useAbmStore } from '../../stores/abmStore';
import { useSimulationStore } from '../../stores/simulationStore';

const ABM_ETA_SECONDS = 180;

export function AbmFloatingWidget() {
  const status = useAbmStore((s) => s.status);
  const progress = useAbmStore((s) => s.progress);
  const stage = useAbmStore((s) => s.stage);
  const startedAt = useAbmStore((s) => s.startedAt);
  const error = useAbmStore((s) => s.error);
  const params = useAbmStore((s) => s.params);
  const focusSpot = useAbmStore((s) => s.focusSpot);
  const cancel = useAbmStore((s) => s.cancelAbm);
  const dismiss = useAbmStore((s) => s.dismissResult);
  const start = useAbmStore((s) => s.startAbm);

  const mainSimStatus = useSimulationStore((s) => s.status);

  const navigate = useNavigate();
  const location = useLocation();

  if (status === 'idle' || status === 'done') return null;
  if (location.pathname.startsWith('/dashboard/abm')) return null;
  if (mainSimStatus === 'running' || mainSimStatus === 'error') return null;

  const baseClasses =
    'fixed bottom-6 right-6 z-50 flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-card p-4 shadow-2xl ring-1 backdrop-blur';

  if (status === 'running') {
    const elapsed = startedAt ? (Date.now() - startedAt) / 1000 : 0;
    const etaSec = Math.max(0, Math.round(ABM_ETA_SECONDS - elapsed));
    const goToAbm = () => navigate('/dashboard/abm');

    return (
      <div className={`${baseClasses} ring-primary/60`}>
        <div className="flex items-center gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <div className="flex-1 text-sm font-semibold text-foreground">
            ABM SIMULATING {Math.round(progress)}%
          </div>
          <button
            onClick={cancel}
            className="text-muted-foreground hover:text-foreground"
            aria-label="취소"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="ABM 시뮬레이션 진행률"
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-primary transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="truncate">
            {stage}
            {focusSpot?.label ? ` · ${focusSpot.label}` : ''}
          </span>
          <span>ETA ~{etaSec}s</span>
        </div>
        <button
          onClick={goToAbm}
          className="mt-1 self-start text-xs font-medium text-primary hover:text-primary/80"
        >
          ABM 결과로 이동 →
        </button>
      </div>
    );
  }

  return (
    <div className={`${baseClasses} ring-danger/60`}>
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-danger" />
        <div className="flex-1 text-sm font-semibold text-foreground">ABM SIMULATION FAILED</div>
        <button
          onClick={dismiss}
          className="text-muted-foreground hover:text-foreground"
          aria-label="닫기"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {error && (
        <div className="flex items-start gap-2 text-xs text-danger">
          <Activity className="mt-0.5 h-3 w-3 shrink-0" />
          <span className="line-clamp-3">{error}</span>
        </div>
      )}
      <button
        onClick={() => params && start(params, focusSpot)}
        disabled={!params}
        className="rounded-md bg-danger/20 px-3 py-2 text-sm font-medium text-danger hover:bg-danger/30 disabled:opacity-40"
      >
        재시도
      </button>
    </div>
  );
}
