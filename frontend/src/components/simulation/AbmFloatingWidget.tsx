import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Activity, AlertCircle, GripVertical, Loader2, X } from 'lucide-react';
import { useAbmStore } from '../../stores/abmStore';
import { useSimulationStore } from '../../stores/simulationStore';

const ABM_ETA_SECONDS = 180;

/** localStorage 에 위치 저장 — 새로고침 후에도 사용자가 옮긴 위치 유지. */
const POS_STORAGE_KEY = 'abm-floating-widget-pos';

interface Pos {
  x: number; // px from left
  y: number; // px from top
}

function loadInitialPos(): Pos | null {
  try {
    const raw = sessionStorage.getItem(POS_STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (typeof p.x === 'number' && typeof p.y === 'number') return p;
  } catch {
    /* noop */
  }
  return null;
}

function savePos(p: Pos) {
  try {
    sessionStorage.setItem(POS_STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* noop */
  }
}

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

  // 드래그 위치 — 사용자가 마우스로 옮길 수 있음. session 동안 유지.
  // null = 기본 위치 (우하단 bottom-6 right-6).
  const [pos, setPos] = useState<Pos | null>(() => loadInitialPos());
  const dragStateRef = useRef<{
    startMx: number;
    startMy: number;
    startX: number;
    startY: number;
  } | null>(null);

  const onPointerDown = (e: React.PointerEvent) => {
    // 핸들에서만 드래그 시작 (X 버튼·결과보기 버튼 등 클릭 방해 X)
    e.preventDefault();
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    const startX = pos?.x ?? window.innerWidth - 320; // 기본 위치 추정
    const startY = pos?.y ?? window.innerHeight - 200;
    dragStateRef.current = {
      startMx: e.clientX,
      startMy: e.clientY,
      startX,
      startY,
    };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const ds = dragStateRef.current;
    if (!ds) return;
    const dx = e.clientX - ds.startMx;
    const dy = e.clientY - ds.startMy;
    const nx = Math.max(0, Math.min(window.innerWidth - 100, ds.startX + dx));
    const ny = Math.max(0, Math.min(window.innerHeight - 60, ds.startY + dy));
    setPos({ x: nx, y: ny });
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const target = e.currentTarget as HTMLElement;
    try {
      target.releasePointerCapture(e.pointerId);
    } catch {
      /* noop */
    }
    if (dragStateRef.current && pos) savePos(pos);
    dragStateRef.current = null;
  };

  // 화면 resize 시 위젯이 화면 밖이면 안쪽으로 보정.
  useEffect(() => {
    if (!pos) return;
    const handler = () => {
      setPos((p) => {
        if (!p) return p;
        const nx = Math.min(p.x, window.innerWidth - 100);
        const ny = Math.min(p.y, window.innerHeight - 60);
        if (nx === p.x && ny === p.y) return p;
        return { x: nx, y: ny };
      });
    };
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [pos]);

  if (status === 'idle' || status === 'done') return null;
  if (location.pathname.startsWith('/dashboard/abm')) return null;
  if (mainSimStatus === 'running' || mainSimStatus === 'error') return null;

  // 드래그 위치 있으면 fixed top/left 로, 없으면 기본 우하단. z-[60] 으로 다른 floating 보다 위.
  const positionClasses = pos
    ? 'fixed z-[60] flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-card p-4 shadow-2xl ring-1 backdrop-blur'
    : 'fixed bottom-6 right-6 z-[60] flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-card p-4 shadow-2xl ring-1 backdrop-blur';
  const positionStyle = pos ? { left: `${pos.x}px`, top: `${pos.y}px` } : undefined;

  // 드래그 핸들 — 위젯 상단 좌측 grip 아이콘 영역. cursor-move + onPointerDown.
  const dragHandle = (
    <button
      type="button"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      className="cursor-move text-muted-foreground hover:text-foreground touch-none"
      aria-label="드래그하여 이동"
      title="드래그하여 이동"
    >
      <GripVertical className="h-4 w-4" />
    </button>
  );

  if (status === 'running') {
    const elapsed = startedAt ? (Date.now() - startedAt) / 1000 : 0;
    const etaSec = Math.max(0, Math.round(ABM_ETA_SECONDS - elapsed));
    const goToAbm = () => navigate('/dashboard/abm');

    return (
      <div className={`${positionClasses} ring-primary/60`} style={positionStyle}>
        <div className="flex items-center gap-2">
          {dragHandle}
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
    <div className={`${positionClasses} ring-danger/60`} style={positionStyle}>
      <div className="flex items-center gap-2">
        {dragHandle}
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
