/**
 * DifferentiationCard — competitor_intel 차별화 포지션 + 기회/리스크
 *
 * 데이터: competitor_intel.differentiation_position / key_opportunities / key_risks
 * 디자인: pull-quote 스타일 + 양분 칩 리스트
 * Best practice: LLM narrative는 blockquote, 액션 항목은 칩
 */

import { Target, Lightbulb, ShieldAlert } from 'lucide-react';

interface Props {
  differentiation?: string | null;
  opportunities?: string[];
  risks?: string[];
}

export function DifferentiationCard({ differentiation, opportunities, risks }: Props) {
  const hasDiff = differentiation && differentiation.trim().length > 0;
  const hasOpp = opportunities && opportunities.length > 0;
  const hasRisks = risks && risks.length > 0;

  if (!hasDiff && !hasOpp && !hasRisks) {
    return null;
  }

  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <Target size={14} className="text-indigo-400" />
        <h4 className="text-xs font-black uppercase tracking-widest text-stone-500">
          차별화 포지셔닝
        </h4>
        <span className="text-[10px] font-black text-stone-600 normal-case tracking-normal">
          competitor_intel
        </span>
      </div>

      {hasDiff && (
        <div className="relative pl-4 border-l-2 border-indigo-500/40 mb-4">
          <p className="text-sm text-stone-200 leading-relaxed italic">{differentiation}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {/* 기회 */}
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Lightbulb size={12} className="text-emerald-400" />
            <span className="text-[10px] font-black uppercase tracking-widest text-emerald-400">
              핵심 기회
            </span>
          </div>
          {hasOpp ? (
            <ul className="space-y-1.5">
              {opportunities!.map((o, i) => (
                <li
                  key={i}
                  className="text-[11px] text-stone-200 leading-relaxed flex items-start gap-1.5"
                >
                  <span className="text-emerald-500 mt-0.5">•</span>
                  <span>{o}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-[10px] text-stone-500">식별된 기회 없음</span>
          )}
        </div>

        {/* 리스크 */}
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <ShieldAlert size={12} className="text-rose-400" />
            <span className="text-[10px] font-black uppercase tracking-widest text-rose-400">
              핵심 리스크
            </span>
          </div>
          {hasRisks ? (
            <ul className="space-y-1.5">
              {risks!.map((r, i) => (
                <li
                  key={i}
                  className="text-[11px] text-stone-200 leading-relaxed flex items-start gap-1.5"
                >
                  <span className="text-rose-500 mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-[10px] text-stone-500">식별된 리스크 없음</span>
          )}
        </div>
      </div>
    </div>
  );
}
