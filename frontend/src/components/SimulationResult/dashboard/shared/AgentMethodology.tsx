import { Fingerprint } from 'lucide-react';

interface AgentMethodologyProps {
  /** 이 지표 산출에 참여한 에이전트 id 목록 (배지 개수 = 에이전트 수) */
  agents: string[];
  /** 방법론 요약 한 줄 (예: "TCN-v2 + SHAP") */
  method: string;
}

/**
 * Contextual AI Attribution — 각 지표 옆에 분석 엔진 배지 표시
 * 호버 시 indigo 보더로 강조
 */
export function AgentMethodology({ agents, method }: AgentMethodologyProps) {
  if (!agents || agents.length === 0) return null;
  return (
    <div className="group relative flex items-center gap-2 mt-3 cursor-help">
      <div className="flex -space-x-1.5">
        {agents.map((_, i) => (
          <div
            key={i}
            className="w-5 h-5 rounded-full bg-stone-800 border border-stone-700 flex items-center justify-center group-hover:border-indigo-500/50 transition-colors"
          >
            <Fingerprint size={10} className="text-indigo-400" />
          </div>
        ))}
      </div>
      <div className="flex flex-col text-left">
        <span className="text-[9px] font-black text-stone-500 uppercase tracking-tighter leading-none">
          분석 엔진
        </span>
        <span className="text-[10px] font-bold text-stone-400 tracking-tight">{method}</span>
      </div>
    </div>
  );
}
