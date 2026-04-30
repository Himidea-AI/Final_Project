import { Play, Info, CheckCircle2, Loader2, StopCircle, RotateCcw } from 'lucide-react';

export type SimState = 'null' | 'ready' | 'running' | 'done';

type Props = {
  state: SimState;
  onRun?: () => void;
  onCancel?: () => void;
  onReanalyze?: () => void;
  /** null 상태에서 표시할 미충족 사유 (예: "동을 선택하세요") */
  pendingHint?: string;
  /** running 상태 진행률 0~100 */
  progress?: number;
  /** running 상태 헤드 텍스트 */
  runningTitle?: string;
};

/**
 * 화면 하단 단일 floating slot — 옵션 입력/실행/진행/완료 4 상태를 한 자리에서 morph.
 * 기존 SimulationFloatingWidget 와 충돌하지 않도록 마운트 시점은 시뮬 페이지에 한정.
 */
export function FloatingCta({
  state,
  onRun,
  onCancel,
  onReanalyze,
  pendingHint = '필수 조건을 모두 입력해주세요',
  progress = 0,
  runningTitle = '시뮬레이션 분석 중...',
}: Props) {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-[1400px] z-50 transition-all duration-500 ease-in-out pointer-events-none">
      <div className="pointer-events-auto">
        {state === 'null' && (
          <div className="bg-card/95 backdrop-blur-md border border-border shadow-xl rounded-2xl p-4 px-6 flex items-center justify-between">
            <div className="flex items-center gap-3 opacity-70">
              <div className="bg-muted text-muted-foreground p-2 rounded-full">
                <Info size={18} />
              </div>
              <div>
                <p className="text-sm font-bold text-muted-foreground">{pendingHint}</p>
                <p className="text-xs text-muted-foreground/80 mt-0.5">
                  필수 입력 완료 시 자동으로 활성화됩니다
                </p>
              </div>
            </div>
            <button
              disabled
              className="bg-muted text-muted-foreground font-bold py-3 px-8 rounded-lg flex items-center gap-2 cursor-not-allowed"
            >
              <Play size={16} fill="currentColor" />
              RUN SIMULATION
            </button>
          </div>
        )}

        {state === 'ready' && (
          <div className="bg-card/95 backdrop-blur-md border border-border shadow-xl rounded-2xl p-4 px-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-success/10 text-success p-2 rounded-full">
                <CheckCircle2 size={18} />
              </div>
              <div>
                <p className="text-sm font-bold text-foreground">모든 조건이 설정되었습니다</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  예상 시뮬레이션 소요 시간: 약 20초
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onRun}
              className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3 px-8 rounded-lg shadow-md transition-all flex items-center gap-2 transform hover:scale-[1.02] active:scale-[0.98]"
            >
              <Play size={16} fill="currentColor" />
              RUN SIMULATION
            </button>
          </div>
        )}

        {state === 'running' && (
          <div className="bg-foreground/95 backdrop-blur-md border border-border shadow-2xl rounded-2xl p-5 px-6 flex items-center justify-between">
            <div className="flex items-center gap-4 w-full max-w-2xl">
              <Loader2 size={24} className="text-primary animate-spin shrink-0" />
              <div className="flex-1">
                <div className="flex justify-between items-end mb-2">
                  <p className="text-sm font-bold text-background">{runningTitle}</p>
                  <span className="text-xs font-mono text-primary">{Math.round(progress)}%</span>
                </div>
                <div className="w-full h-1.5 bg-muted-foreground/30 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-1000"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={onCancel}
              className="ml-6 flex items-center gap-2 px-4 py-2 bg-muted/20 hover:bg-muted/30 text-muted-foreground rounded-lg text-xs font-bold transition-colors border border-border/20"
            >
              <StopCircle size={14} />
              중지
            </button>
          </div>
        )}

        {state === 'done' && (
          <div className="bg-primary/5 backdrop-blur-md border border-primary/20 shadow-xl rounded-2xl p-4 px-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-primary/20 text-primary p-2 rounded-full">
                <CheckCircle2 size={18} />
              </div>
              <div>
                <p className="text-sm font-bold text-primary">시뮬레이션 분석 완료</p>
                <p className="text-xs text-primary/80 mt-0.5">상세 리포트 화면으로 이동했습니다</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onReanalyze}
              className="bg-card border border-border hover:bg-muted text-foreground font-bold py-2.5 px-6 rounded-lg transition-all flex items-center gap-2 shadow-sm"
            >
              <RotateCcw size={14} />
              재분석
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
