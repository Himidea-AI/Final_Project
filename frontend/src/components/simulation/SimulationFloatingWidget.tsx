import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '../../stores/simulationStore';
import { Activity, AlertCircle, Loader2, RefreshCw, X } from 'lucide-react';

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

  // [A6] slice별 status / error / retry
  const predStatus = useSimulationStore((s) => s.prediction.status);
  const analysisStatus = useSimulationStore((s) => s.analysis.status);
  const predError = useSimulationStore((s) => s.prediction.error);
  const analysisError = useSimulationStore((s) => s.analysis.error);
  const retryPrediction = useSimulationStore((s) => s.retryPrediction);
  const retryAnalysis = useSimulationStore((s) => s.retryAnalysis);

  const baseClasses =
    'fixed bottom-6 right-6 z-50 flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-card p-4 shadow-2xl ring-1 backdrop-blur';

  // [H4] status='done' 자동 dismiss 제거 — Hub Redesign 흐름에서 store.result 가 /dashboard
  // 가드 통과 키이므로 dismiss 하면 옛 화면으로 redirect 됨. done 알림은 useCompletionToast 담당.
  if (status === 'idle') return null;
  if (status === 'done') {
    // 둘 다 ok 면 hide. 부분 실패면 PARTIAL SUCCESS 표시.
    const hasPartialFail = predStatus === 'error' || analysisStatus === 'error';
    if (!hasPartialFail) return null;
    return (
      <div className={`${baseClasses} ring-warning/60`}>
        <div className="mb-2 flex items-center gap-2">
          <Activity className="h-5 w-5 text-warning" />
          <div className="flex-1 text-sm font-semibold text-foreground">PARTIAL SUCCESS</div>
          <button
            type="button"
            onClick={dismiss}
            className="text-muted-foreground hover:text-foreground"
            aria-label="닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {predStatus === 'error' && (
          <div className="mb-2 flex items-center gap-2 text-xs text-danger">
            <span className="flex-1">ML 예측 실패: {predError?.slice(0, 60)}</span>
            <button
              type="button"
              onClick={() => retryPrediction()}
              className="inline-flex shrink-0 items-center gap-1 rounded border border-danger/40 px-2 py-0.5 text-[11px] text-danger hover:bg-danger/10"
            >
              <RefreshCw className="h-3 w-3" /> 재시도
            </button>
          </div>
        )}
        {analysisStatus === 'error' && (
          <div className="mb-2 flex items-center gap-2 text-xs text-danger">
            <span className="flex-1">AI 분석 실패: {analysisError?.slice(0, 60)}</span>
            <button
              type="button"
              onClick={() => retryAnalysis()}
              className="inline-flex shrink-0 items-center gap-1 rounded border border-danger/40 px-2 py-0.5 text-[11px] text-danger hover:bg-danger/10"
            >
              <RefreshCw className="h-3 w-3" /> 재시도
            </button>
          </div>
        )}
      </div>
    );
  }

  const goToSimulator = () => navigate('/dashboard');

  const etaSec = startedAt ? Math.max(0, Math.round((90 - progress) / 0.9)) : 0;

  if (status === 'running') {
    return (
      <div className={`${baseClasses} ring-primary/60`}>
        <div className="flex items-center gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <div className="flex-1 text-sm font-semibold text-foreground">
            SIMULATING {Math.round(progress)}%
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
          aria-label="시뮬레이션 진행률"
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-primary transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="truncate">{stage}</span>
          <span>ETA ~{etaSec}s</span>
        </div>
        <button
          onClick={goToSimulator}
          className="mt-1 self-start text-xs font-medium text-primary hover:text-primary/80"
        >
          시뮬레이터로 이동 →
        </button>
      </div>
    );
  }

  // error
  return (
    <div className={`${baseClasses} ring-danger/60`}>
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-danger" />
        <div className="flex-1 text-sm font-semibold text-foreground">SIMULATION FAILED</div>
        <button
          onClick={dismiss}
          className="text-muted-foreground hover:text-foreground"
          aria-label="닫기"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <button
        onClick={() => params && start(params)}
        disabled={!params}
        className="rounded-md bg-danger/20 px-3 py-2 text-sm font-medium text-danger hover:bg-danger/30 disabled:opacity-40"
      >
        재시도
      </button>
    </div>
  );
}
