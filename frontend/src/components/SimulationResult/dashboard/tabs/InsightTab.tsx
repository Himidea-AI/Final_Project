/**
 * InsightTab — AI 분석 근거 탭
 * 9 에이전트 카드 grid-cols-3 + 상세 모달 (원본 reasoning)
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
    inflow: 'inflow',
    synthesis: 'synthesis',
  };

  const getAttribution = (displayId: string) => {
    const backendId = DISPLAY_TO_BACKEND[displayId];
    return attributions.find((a) => a.id === backendId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-black text-foreground flex items-center gap-3 italic tracking-tight text-left">
          <BrainCircuit className="text-primary" /> 멀티 에이전트 상세 리포트
        </h3>
        <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
          {attributions.length}/{AGENTS_LIST.length} 에이전트 분석 완료
        </div>
      </div>

      {/* ═══ Radar Overview (가이드 #7) ═══ */}
      <div className="bg-card border border-border rounded-3xl p-8">
        <h4 className="text-xs font-black text-muted-foreground uppercase tracking-widest mb-4">
          9 에이전트 신뢰도 Overview
        </h4>
        <AgentConfidenceRadar attributions={attributions} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {AGENTS_LIST.map((agent) => {
          const attr = getAttribution(agent.id);
          const sources = attr?.sources ?? [];
          const verdict = attr?.verdict;
          const reasoning = attr?.reasoning;
          const hasData = Boolean(attr);

          return (
            <div
              key={agent.id}
              className={`border p-6 rounded-3xl h-full flex flex-col transition-all text-left group ${
                hasData
                  ? `bg-card ${agent.borderCls}`
                  : 'bg-card/20 border-dashed border-border opacity-60'
              }`}
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className={`overflow-hidden rounded-xl border shadow-inner group-hover:scale-110 transition-transform ${
                    hasData ? agent.iconBgCls : 'bg-card border-border/50'
                  }`}
                >
                  <img
                    src={agent.iconSrc}
                    alt={agent.name}
                    className="h-12 w-12 object-cover"
                    loading="lazy"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-bold text-foreground leading-tight truncate">
                    {agent.name}
                  </h4>
                  <span className="text-[0.5625rem] font-black text-muted-foreground uppercase tracking-widest leading-none">
                    {agent.desc}
                  </span>
                </div>
              </div>

              {/* verdict (한 줄 판정) */}
              {verdict && (
                <div className="mb-3 px-2.5 py-1.5 rounded-md bg-card border border-border">
                  <span className="text-[0.6875rem] font-bold text-foreground leading-tight">
                    {verdict}
                  </span>
                </div>
              )}

              {/* reasoning (요약 3줄) */}
              <p className="text-[0.6875rem] text-muted-foreground leading-relaxed mb-4 flex-grow line-clamp-3">
                {reasoning ?? '해당 에이전트 분석 결과가 아직 수집되지 않았습니다.'}
              </p>

              {/* sources 배지 */}
              {sources.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {sources.slice(0, 3).map((src, i) => (
                    <span
                      key={`${src}-${i}`}
                      className="text-[0.5rem] font-black text-muted-foreground bg-card px-1.5 py-0.5 rounded border border-border uppercase tracking-tighter"
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
                      ]
                        .filter(Boolean)
                        .join('\n\n'),
                    })
                  }
                  className="w-full py-2.5 bg-card hover:bg-muted text-[0.625rem] font-black text-muted-foreground rounded-xl flex items-center justify-center gap-2 tracking-widest uppercase transition-colors"
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
