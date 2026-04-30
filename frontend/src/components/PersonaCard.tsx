import { X } from 'lucide-react';
import type { AbmThought } from './AbmPersonaMap';

// PersonaCard — Tier S 50명 dot 클릭 시 표시되는 모달.
// Plan T5: archetype, agent_id, dong, 시간별 thought 타임라인.
// 백엔드 trajectory + thoughts 응답에서 추출한 정보를 보여줌.
//
// MVP 범위 — visit count / revenue 는 backend 가 agent 단위로 응답에 추가하면 확장.
// (현재 spotStats 는 매장 단위로만 집계됨)

export interface PersonaCardData {
  agentId: number;
  archetype: string;
  thoughts: AbmThought[]; // 0~23h 정렬된 thought 배열
  dongName?: string; // 가장 최근 hour 의 dong 추정값
  role?: string;
}

interface PersonaCardProps {
  data: PersonaCardData;
  onClose: () => void;
  currentHour?: number; // 현재 sim 의 displayHour — 타임라인 강조 표시용
}

export default function PersonaCard({ data, onClose, currentHour }: PersonaCardProps) {
  // 0~23 hour 그리드 — thought 가 있는 시간만 채움
  const hourMap = new Map<number, AbmThought>();
  for (const t of data.thoughts) {
    hourMap.set(t.hour, t);
  }
  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-[460px] max-w-[92vw] max-h-[88vh] overflow-y-auto rounded-xl border border-warning/30 bg-slate-900 p-5 text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close 버튼 */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          aria-label="닫기"
        >
          <X className="h-4 w-4" />
        </button>

        {/* 헤더 — Tier S 마커 + agent_id + archetype */}
        <div className="mb-4 flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 border-warning bg-warning/20 text-warning">
            <span className="text-lg font-bold">⭐</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-warning">
              <span>Tier S</span>
              <span className="text-slate-500">·</span>
              <span className="text-slate-400">Agent #{data.agentId}</span>
            </div>
            <div className="mt-0.5 text-base font-semibold text-slate-100">
              {data.archetype || '—'}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
              {data.role && <span>{data.role}</span>}
              {data.dongName && (
                <>
                  <span>·</span>
                  <span>{data.dongName}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 시간별 thought 타임라인 — 0~23h 그리드 */}
        <div className="mt-3">
          <div className="mb-2 text-xs font-semibold text-slate-300">
            시간대별 생각 ({data.thoughts.length}건)
          </div>
          <div className="grid grid-cols-12 gap-1 text-[0.625rem]">
            {hours.map((h) => {
              const t = hourMap.get(h);
              const isNow = currentHour === h;
              return (
                <div
                  key={h}
                  className={[
                    'flex flex-col items-center rounded border px-1 py-1.5',
                    isNow
                      ? 'border-warning bg-warning/15'
                      : t
                        ? 'border-slate-700 bg-slate-800/60'
                        : 'border-slate-800/50 bg-slate-900/40 opacity-50',
                  ].join(' ')}
                  title={t?.thought || ''}
                >
                  <div
                    className={[
                      'text-[0.5625rem] font-mono',
                      isNow ? 'text-warning' : 'text-slate-500',
                    ].join(' ')}
                  >
                    {String(h).padStart(2, '0')}
                  </div>
                  {t ? (
                    <div className="mt-0.5 h-2 w-2 rounded-full bg-warning" />
                  ) : (
                    <div className="mt-0.5 h-2 w-2 rounded-full bg-slate-700" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 풀 thought 리스트 — 시간순 */}
        <div className="mt-4 space-y-1.5">
          {data.thoughts
            .slice()
            .sort((a, b) => a.day * 24 + a.hour - (b.day * 24 + b.hour))
            .map((t, i) => {
              const isNow = currentHour === t.hour;
              return (
                <div
                  key={`${t.day}-${t.hour}-${i}`}
                  className={[
                    'flex items-start gap-2 rounded border px-2.5 py-1.5 text-xs',
                    isNow ? 'border-warning/60 bg-warning/10' : 'border-slate-800 bg-slate-800/40',
                  ].join(' ')}
                >
                  <span
                    className={[
                      'shrink-0 font-mono',
                      isNow ? 'text-warning' : 'text-slate-500',
                    ].join(' ')}
                  >
                    {String(t.hour).padStart(2, '0')}:00
                  </span>
                  <span className="flex-1 text-slate-200">{t.thought || '—'}</span>
                </div>
              );
            })}
          {data.thoughts.length === 0 && (
            <div className="rounded border border-dashed border-slate-700 px-3 py-4 text-center text-xs text-slate-500">
              이 에이전트에 대한 thought 데이터가 없습니다.
            </div>
          )}
        </div>

        <div className="mt-4 border-t border-slate-800 pt-3 text-[0.625rem] leading-relaxed text-slate-500">
          Tier S 50명만 LLM thought 생성됩니다 (gpt-4.1-mini, 한국어 ≤ 12자). Decision logic 은
          policy 기반이라 Pearson r=0.95 학술 검증은 보존됩니다.
        </div>
      </div>
    </div>
  );
}
