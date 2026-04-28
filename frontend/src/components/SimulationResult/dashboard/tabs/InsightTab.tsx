/**
 * InsightTab — AI 분석 근거 탭
 * 8 에이전트 카드 grid-cols-4 + 상세 모달 (원본 reasoning)
 */

import { BrainCircuit, Maximize2 } from 'lucide-react';
import type { SimulationOutput, AgentId } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { AGENTS_LIST } from '../agents';
import { AgentConfidenceRadar } from '../charts/AgentConfidenceRadar';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function InsightTab({ simResult, openModal }: Props) {
  const attributions = simResult.agent_attributions ?? [];

  // agents_list의 UI id(예: 'market') ↔ 실제 agent_attribution id(예: 'market_analyst') 매핑
  const DISPLAY_TO_BACKEND: Record<string, AgentId> = {
    market: 'market_analyst',
    population: 'population_analyst',
    demographic: 'demographic_depth',
    competitor: 'competitor_intel',
    legal: 'legal',
    trend: 'trend_forecaster',
    ranking: 'district_ranking',
    synthesis: 'synthesis',
  };

  const getAttribution = (displayId: string) => {
    const backendId = DISPLAY_TO_BACKEND[displayId];
    return attributions.find((a) => a.id === backendId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left">
          <BrainCircuit className="text-indigo-400" /> 8대 멀티 에이전트 상세 리포트
        </h3>
        <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
          {attributions.length}/8 에이전트 분석 완료
        </div>
      </div>

      {/* ═══ Radar Overview (가이드 #7) ═══ */}
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
        <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest mb-4">
          8 에이전트 신뢰도 Overview
        </h4>
        <AgentConfidenceRadar attributions={attributions} />
      </div>

      <div className="grid grid-cols-4 gap-4">
        {AGENTS_LIST.map((agent) => {
          const AgentIcon = agent.icon;
          const attr = getAttribution(agent.id);
          const confidencePct = attr?.confidence != null ? Math.round(attr.confidence * 100) : null;
          const sources = attr?.sources ?? [];
          const verdict = attr?.verdict;
          const reasoning = attr?.reasoning;
          const hasData = Boolean(attr);

          return (
            <div
              key={agent.id}
              className={`border p-6 rounded-3xl h-full flex flex-col transition-all text-left group ${
                hasData
                  ? `bg-stone-900/40 ${agent.borderCls}`
                  : 'bg-stone-900/20 border-dashed border-stone-800 opacity-60'
              }`}
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className={`p-2 rounded-xl border shadow-inner group-hover:scale-110 transition-transform ${
                    hasData ? agent.iconBgCls : 'bg-stone-800 border-stone-700/50'
                  }`}
                >
                  <AgentIcon size={18} className={agent.color} />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-bold text-stone-200 leading-tight truncate">
                    {agent.name}
                  </h4>
                  <span className="text-[9px] font-black text-stone-600 uppercase tracking-widest leading-none">
                    {agent.desc}
                  </span>
                </div>
                {confidencePct != null && (
                  <div className="flex flex-col items-end shrink-0">
                    <span className="text-[8px] font-black text-stone-500 uppercase tracking-tighter">
                      신뢰도
                    </span>
                    <span className="text-xs font-black text-indigo-400 tabular-nums">
                      {confidencePct}%
                    </span>
                  </div>
                )}
              </div>

              {/* verdict (한 줄 판정) */}
              {verdict && (
                <div className="mb-3 px-2.5 py-1.5 rounded-md bg-stone-950/40 border border-stone-800/40">
                  <span className="text-[11px] font-bold text-stone-300 leading-tight">
                    {verdict}
                  </span>
                </div>
              )}

              {/* reasoning (요약 3줄) */}
              <p className="text-[11px] text-stone-500 leading-relaxed mb-4 flex-grow line-clamp-3">
                {reasoning ?? '해당 에이전트 분석 결과가 아직 수집되지 않았습니다.'}
              </p>

              {/* sources 배지 */}
              {sources.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {sources.slice(0, 3).map((src, i) => (
                    <span
                      key={`${src}-${i}`}
                      className="text-[8px] font-black text-stone-500 bg-stone-900/50 px-1.5 py-0.5 rounded border border-stone-800 uppercase tracking-tighter"
                    >
                      {src}
                    </span>
                  ))}
                </div>
              )}

              {hasData && (
                <button
                  type="button"
                  onClick={() =>
                    openModal({
                      title: `${agent.name} — ${agent.desc}`,
                      content: [
                        verdict ? `판정\n${verdict}` : '',
                        reasoning ? `분석 근거 (원본)\n${reasoning}` : '',
                        sources.length > 0 ? `데이터 소스\n${sources.join(', ')}` : '',
                        confidencePct != null ? `신뢰도\n${confidencePct}%` : '',
                      ]
                        .filter(Boolean)
                        .join('\n\n'),
                    })
                  }
                  className="w-full py-2.5 bg-stone-800 hover:bg-stone-700 text-[10px] font-black text-stone-400 rounded-xl flex items-center justify-center gap-2 tracking-widest uppercase transition-colors"
                >
                  <Maximize2 size={12} /> 상세 분석 결과
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
