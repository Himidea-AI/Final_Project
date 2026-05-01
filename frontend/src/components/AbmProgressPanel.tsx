/**
 * AbmProgressPanel — ABM 시뮬 진행 추적기 (우측 사이드 패널 안)
 *
 * abmStore 의 progress / stage / startedAt 을 표시:
 *   - 진행률 바 + 경과시간/ETA
 *   - 7단계 체크리스트 (완료/진행/대기)
 *   - 시뮬레이션 취소 버튼
 *
 * AbmPersonaMap.tsx 의 abmLoading 분기에서 렌더. 지도 컨텍스트는 유지한 채
 * 우측 패널만 결과 → 진행 으로 전환.
 */

import { useEffect, useState } from 'react';
import { Loader2, X, CheckCircle2, Circle } from 'lucide-react';
import { useAbmStore } from '../stores/abmStore';

interface StageDef {
  at: number;
  label: string;
  sub: string;
}

const STAGES: readonly StageDef[] = [
  { at: 0, label: 'ABM 엔진 초기화', sub: 'Initializing engine' },
  { at: 10, label: '5,000 에이전트 생성', sub: 'Spawning agents' },
  { at: 25, label: '일과 패턴 계산', sub: 'Daily routines' },
  { at: 45, label: 'Tier A/B 의사결정', sub: 'Tier A/B decisions' },
  { at: 60, label: 'Tier S LLM 추론', sub: 'Tier S LLM reasoning' },
  { at: 80, label: '방문·매출 집계', sub: 'Aggregating visits & revenue' },
  { at: 90, label: '결과 마무리', sub: 'Finalizing' },
];

const ETA_SECONDS = 180;

function formatElapsed(seconds: number): string {
  if (seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s.toString().padStart(2, '0')}s` : `${s}s`;
}

export default function AbmProgressPanel() {
  const progress = useAbmStore((s) => s.progress);
  const startedAt = useAbmStore((s) => s.startedAt);
  const cancelAbm = useAbmStore((s) => s.cancelAbm);
  const focusSpot = useAbmStore((s) => s.focusSpot);

  // 1초 tick — 경과시간 갱신용. progress 자체는 store 에서 polling 으로 갱신.
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const elapsedSec = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0;
  const remainingSec = Math.max(0, ETA_SECONDS - elapsedSec);

  return (
    <div className="relative w-full flex flex-col gap-4">
      {/* 헤더 */}
      <div className="flex items-baseline justify-between">
        <div className="flex flex-col gap-1">
          <h4 className="text-lg font-black text-white italic tracking-tighter leading-none">
            ABM Simulation
          </h4>
          <p className="text-[9px] font-black text-stone-600 uppercase tracking-[0.3em]">
            5,000 agents · {focusSpot?.label ?? '마포구'}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 text-emerald-400 animate-spin" />
          <span className="text-[9px] font-mono text-emerald-400 tracking-widest">RUNNING</span>
        </div>
      </div>

      {/* 진행률 바 */}
      <div className="flex flex-col gap-2 rounded-xl border border-emerald-500/15 bg-gradient-to-b from-emerald-500/[0.04] to-transparent p-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] font-black text-emerald-300 uppercase tracking-widest">
            Progress
          </span>
          <span className="text-base font-black text-emerald-200 tabular-nums leading-none">
            {Math.round(progress)}
            <span className="text-[10px] text-emerald-400/70 font-mono ml-0.5">%</span>
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-stone-900 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-emerald-400 to-cyan-400 transition-all duration-700 ease-out"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
        <div className="flex justify-between text-[9px] font-mono tabular-nums text-stone-500 uppercase tracking-widest">
          <span>{formatElapsed(elapsedSec)} elapsed</span>
          <span>~{formatElapsed(remainingSec)} left</span>
        </div>
      </div>

      {/* 단계 체크리스트 */}
      <div className="flex flex-col gap-2">
        <span className="text-[10px] font-black text-amber-300 uppercase tracking-widest">
          Pipeline
        </span>
        <div className="flex flex-col gap-2 rounded-xl border border-stone-800 bg-stone-950/50 p-3">
          {STAGES.map((s, i) => {
            const nextAt = STAGES[i + 1]?.at ?? 100;
            const isComplete = progress >= nextAt;
            const isActive = progress >= s.at && !isComplete;
            return (
              <div key={s.label} className="flex items-start gap-2">
                <div className="mt-0.5 shrink-0">
                  {isComplete ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : isActive ? (
                    <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  ) : (
                    <Circle className="w-3.5 h-3.5 text-stone-700" />
                  )}
                </div>
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span
                    className={`text-[11px] font-bold tracking-tight leading-tight ${
                      isComplete ? 'text-stone-500' : isActive ? 'text-cyan-200' : 'text-stone-600'
                    }`}
                  >
                    {s.label}
                  </span>
                  <span
                    className={`text-[9px] font-mono uppercase tracking-wider leading-tight ${
                      isActive ? 'text-cyan-500/80' : 'text-stone-700'
                    }`}
                  >
                    {s.sub}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 안내 문구 — 비동기 시뮬이라 새로고침해도 결과 살아남음을 사용자에게 알림 */}
      <p className="text-[9.5px] font-mono text-stone-600 leading-relaxed tracking-tight">
        백엔드에서 비동기 실행 중. 새로고침·탭 이동 후에도 결과는 자동 복원됩니다.
      </p>

      {/* 취소 버튼 */}
      <button
        type="button"
        onClick={() => cancelAbm()}
        className="mt-1 flex items-center justify-center gap-1.5 rounded-lg border border-rose-500/25 bg-rose-500/[0.04] px-3 py-2 text-[11px] font-bold text-rose-300 hover:bg-rose-500/10 hover:border-rose-500/40 transition-colors"
      >
        <X className="w-3 h-3" />
        시뮬레이션 취소
      </button>
    </div>
  );
}
