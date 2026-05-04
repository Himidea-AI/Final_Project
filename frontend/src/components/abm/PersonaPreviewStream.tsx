/**
 * PersonaPreviewStream — ABM 시뮬 진행 중 페르소나 추론 "샘플" 카드 rotate.
 *
 * 진짜 partial result streaming 은 backend 인프라 미존재 (vacancy-evaluation
 * /{job_id}/chats 등은 done 후만 응답). 사용자가 ~3분 대기 동안 "AI 가 뭔가
 * 하고 있다" 감각 부여를 위해 카테고리별 사전 정의 dialog pool 을 6초 간격
 * fade-in 으로 누적 표시. 카드 하단 "샘플" 명시 필수.
 *
 * AbmPersonaMap 우측 패널에서 abmLoading=true 분기일 때 AbmProgressPanel 아래
 * 마운트.
 */

import { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { useAbmStore } from '../../stores/abmStore';
import { pickDialogPool, type PersonaDialog } from '../../data/personaSampleDialogs';

interface Props {
  businessType?: string | null;
  spotLabel?: string | null;
}

interface QueueEntry {
  id: number;
  dialog: PersonaDialog;
  addedAt: number;
}

const ROTATE_INTERVAL_MS = 6_000;
const MAX_VISIBLE = 4;

const TIER_BADGE: Record<PersonaDialog['tier'], { color: string; label: string }> = {
  S: { color: 'bg-amber-500/15 text-amber-300 border-amber-500/40', label: 'TIER S' },
  A: { color: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40', label: 'TIER A' },
  B: { color: 'bg-stone-500/15 text-stone-300 border-stone-500/40', label: 'TIER B' },
};

function relativeAge(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 5) return '방금';
  if (sec < 60) return `${sec}s 전`;
  const m = Math.floor(sec / 60);
  return `${m}m 전`;
}

export function PersonaPreviewStream({ businessType, spotLabel }: Props) {
  const stage = useAbmStore((s) => s.stage);

  const pool = pickDialogPool(businessType);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [tickNow, setTickNow] = useState(Date.now());

  // 6초 간격으로 dialog 1개 push (cumulative, 최근 MAX_VISIBLE 만 유지).
  useEffect(() => {
    let counter = 0;
    let poolIdx = 0;
    const shuffled = [...pool].sort(() => Math.random() - 0.5);

    const push = () => {
      const dialog = shuffled[poolIdx % shuffled.length];
      poolIdx += 1;
      counter += 1;
      setQueue((prev) => {
        const next = [{ id: counter, dialog, addedAt: Date.now() }, ...prev];
        return next.slice(0, MAX_VISIBLE);
      });
    };

    // 마운트 직후 즉시 1개 + 그 후 interval.
    push();
    const tid = setInterval(push, ROTATE_INTERVAL_MS);
    return () => clearInterval(tid);
  }, [pool]);

  // 1초 tick — relativeAge 갱신용.
  useEffect(() => {
    const t = setInterval(() => setTickNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-cyan-500/20 bg-gradient-to-b from-cyan-500/[0.04] to-transparent p-3">
      <div className="flex items-baseline justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-cyan-300" />
          <span className="text-[10px] font-black text-cyan-300 uppercase tracking-widest">
            AI Persona Preview
          </span>
        </div>
        <span className="text-[9px] font-mono text-stone-500 tabular-nums uppercase tracking-widest">
          {stage || 'WARMING UP'}
        </span>
      </div>

      <div className="flex flex-col gap-1.5">
        {queue.length === 0 && (
          <p className="text-[10px] text-stone-500 italic">페르소나 로딩 중…</p>
        )}
        {queue.map((entry, idx) => {
          const tier = TIER_BADGE[entry.dialog.tier];
          const age = relativeAge(tickNow - entry.addedAt);
          // 위쪽 (최신) 일수록 진하게, 아래쪽은 흐리게.
          const fadeStyle = {
            opacity: 1 - idx * 0.18,
          };
          return (
            <div
              key={entry.id}
              className="flex flex-col gap-1 rounded-lg border border-stone-800 bg-stone-950/60 px-2.5 py-2 animate-in fade-in slide-in-from-top-1 duration-500"
              style={fadeStyle}
            >
              <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest">
                <span className={`px-1.5 py-px rounded border ${tier.color} font-black`}>
                  {tier.label}
                </span>
                <span className="text-stone-300 font-bold normal-case tracking-tight">
                  {entry.dialog.persona}
                </span>
                <span className="ml-auto text-stone-600 tabular-nums">{age}</span>
              </div>
              <p className="text-[10.5px] text-stone-200 leading-snug tracking-tight">
                "{entry.dialog.text}"
              </p>
            </div>
          );
        })}
      </div>

      <p className="text-[8.5px] font-mono text-stone-600 leading-snug tracking-tight uppercase">
        ⓘ 샘플 페르소나 — 실제 시뮬 결과는 완료 후 표시됩니다
        {spotLabel ? ` · ${spotLabel}` : ''}
      </p>
    </div>
  );
}

export default PersonaPreviewStream;
