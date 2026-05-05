/**
 * AbmQueuePanel — ABM 시뮬 queue 우하단 패널.
 *
 * 표시 항목:
 *   1. 현재 실행 중 (status === 'running') — progress bar + 취소 X
 *   2. 대기 중 (pendingQueue) — clock + 취소 X (cancelPending)
 *   3. 완료 (history top 5) — checkmark + click 시 loadHistory
 *
 * 데이터는 모두 useAbmStore 에서 직접 구독. props 없음.
 */

import { Loader2, Clock, CheckCircle2, X } from 'lucide-react';
import { useAbmStore, type AbmRequestPayload } from '../../stores/abmStore';

/** 시나리오 요약 chip 텍스트 — "맑음·평일·임대+0%" 형식. */
function summarizeScenario(params: AbmRequestPayload | null): string {
  if (!params) return '';
  const sc = params.scenario;
  if (!sc) return '';
  const parts: string[] = [];
  if (sc.weather_override) parts.push(sc.weather_override);
  if (sc.weekend_force) parts.push('주말');
  else if (sc.date_override) parts.push(sc.date_override);
  if (typeof sc.rent_shock_pct === 'number' && sc.rent_shock_pct !== 0) {
    const sign = sc.rent_shock_pct > 0 ? '+' : '';
    parts.push(`임대${sign}${sc.rent_shock_pct}%`);
  }
  return parts.join('·');
}

/** focusSpot 라벨 fallback — label 없으면 좌표. */
function spotLabel(spot: { lat: number; lon: number; label?: string } | null): string {
  if (!spot) return '공실 후보';
  if (spot.label) return spot.label;
  return `${spot.lat.toFixed(4)}, ${spot.lon.toFixed(4)}`;
}

export function AbmQueuePanel() {
  const status = useAbmStore((s) => s.status);
  const progress = useAbmStore((s) => s.progress);
  const focusSpot = useAbmStore((s) => s.focusSpot);
  const params = useAbmStore((s) => s.params);
  const pendingQueue = useAbmStore((s) => s.pendingQueue);
  const history = useAbmStore((s) => s.history);
  const cancelAbm = useAbmStore((s) => s.cancelAbm);
  const cancelPending = useAbmStore((s) => s.cancelPending);
  const loadHistory = useAbmStore((s) => s.loadHistory);

  const isRunning = status === 'running';
  const runningCount = isRunning ? 1 : 0;
  const pendingCount = pendingQueue.length;
  const recentDone = history.slice(0, 5);
  const doneCount = recentDone.length;

  const isEmpty = !isRunning && pendingCount === 0 && doneCount === 0;

  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-3 h-full overflow-y-auto flex flex-col gap-2">
      {/* 헤더 */}
      <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-stone-200">
        <h4 className="text-xs font-black text-stone-900 tracking-tight">시뮬 큐</h4>
        <span className="text-[9px] font-mono uppercase tracking-widest text-stone-500 tabular-nums">
          실행 {runningCount} · 대기 {pendingCount} · 완료 {doneCount}
        </span>
      </div>

      {/* 빈 상태 */}
      {isEmpty && (
        <div className="flex-1 flex items-center justify-center px-3 py-6">
          <p className="text-[11px] text-stone-400 text-center tracking-tight leading-snug">
            공실 spot 선택 후 시뮬 실행
          </p>
        </div>
      )}

      {/* 1. 현재 실행 중 */}
      {isRunning && (
        <div className="flex flex-col gap-1">
          <span className="text-[8.5px] font-black text-cyan-700 uppercase tracking-widest">
            실행 중
          </span>
          <div className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-50/40 px-2.5 py-2 min-h-[38px]">
            <Loader2 className="w-3.5 h-3.5 shrink-0 text-cyan-700 animate-spin" />
            <div className="flex flex-col min-w-0 flex-1 gap-0.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-bold text-cyan-900 tracking-tight truncate">
                  {spotLabel(focusSpot)}
                </span>
                <span className="text-[9px] font-mono tabular-nums text-cyan-700 shrink-0">
                  {Math.round(progress)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-1 flex-1 rounded-full bg-cyan-100 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </div>
                {summarizeScenario(params) && (
                  <span className="text-[9px] text-cyan-700/80 tabular-nums truncate max-w-[120px]">
                    {summarizeScenario(params)}
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => cancelAbm()}
              aria-label="실행 취소"
              className="shrink-0 p-1 rounded hover:bg-cyan-100 text-cyan-700 transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* 2. 대기 중 */}
      {pendingCount > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-[8.5px] font-black text-stone-600 uppercase tracking-widest">
            대기 중
          </span>
          <ul className="flex flex-col gap-1">
            {pendingQueue.map((p) => {
              const summary = summarizeScenario(p.payload);
              return (
                <li
                  key={p.id}
                  className="flex items-center gap-2 rounded-lg border border-stone-300 bg-stone-50 px-2.5 py-2 min-h-[38px]"
                >
                  <Clock className="w-3.5 h-3.5 shrink-0 text-stone-600" />
                  <div className="flex flex-col min-w-0 flex-1 gap-0.5">
                    <span className="text-[11px] font-bold text-stone-800 tracking-tight truncate">
                      {spotLabel(p.focusSpot)}
                    </span>
                    {summary && (
                      <span className="text-[9px] text-stone-500 tracking-tight truncate">
                        {summary}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => cancelPending(p.id)}
                    aria-label="대기 취소"
                    className="shrink-0 p-1 rounded hover:bg-stone-200 text-stone-600 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* 3. 완료 (최근 5) */}
      {doneCount > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-[8.5px] font-black text-emerald-700 uppercase tracking-widest">
            완료
          </span>
          <ul className="flex flex-col gap-1">
            {recentDone.map((h) => {
              const summary = summarizeScenario(h.params);
              return (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => loadHistory(h.id)}
                    className="w-full flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-50/40 px-2.5 py-2 min-h-[38px] text-left hover:bg-emerald-50 hover:border-emerald-500/50 transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-700" />
                    <div className="flex flex-col min-w-0 flex-1 gap-0.5">
                      <span className="text-[11px] font-bold text-emerald-900 tracking-tight truncate">
                        {spotLabel(h.focusSpot)}
                      </span>
                      {summary && (
                        <span className="text-[9px] text-emerald-700/80 tracking-tight truncate">
                          {summary}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default AbmQueuePanel;
