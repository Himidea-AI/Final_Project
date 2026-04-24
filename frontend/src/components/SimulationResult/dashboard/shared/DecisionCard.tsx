/**
 * DecisionCard — SummaryTab 상단 3 카드 (참고 v4.3 디자인 배치 차용)
 * 질문형 제목 + Hero 배지 + 본문 설명 + 체크리스트 + footer 에이전트 아이콘
 *
 * 모든 데이터는 상위에서 실 simResult 필드로 조립하여 props로 전달.
 */

import { ChevronRight, type LucideIcon } from 'lucide-react';

export interface DecisionCardAgent {
  id: string;
  icon: LucideIcon;
  color: string;
}

export interface DecisionCardItem {
  text: string;
  highlight?: boolean;
}

interface DecisionCardProps {
  title: string;
  heroBadge: string;
  /** Tailwind color 토큰명 (emerald/amber/rose/indigo) */
  heroColor: 'emerald' | 'amber' | 'rose' | 'indigo';
  description: string;
  items: DecisionCardItem[];
  footer: {
    agents: DecisionCardAgent[];
    methodology: string;
  };
}

const HERO_CLS: Record<DecisionCardProps['heroColor'], string> = {
  emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  rose: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  indigo: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
};

export function DecisionCard({
  title,
  heroBadge,
  heroColor,
  description,
  items,
  footer,
}: DecisionCardProps) {
  return (
    <div className="bg-[#141210] border border-stone-800/60 rounded-3xl p-8 flex flex-col h-full hover:border-stone-700 transition-all group">
      <h3 className="text-xl font-bold text-stone-100 mb-6">{title}</h3>

      <div
        className={`inline-block self-start px-4 py-2 rounded-xl border font-black text-lg mb-6 ${HERO_CLS[heroColor]}`}
      >
        {heroBadge}
      </div>

      <p className="text-sm text-stone-400 leading-relaxed mb-8 flex-grow">{description}</p>

      <div className="border-t border-dashed border-stone-800 mb-6 w-full" />

      <ul className="space-y-3 mb-8">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-3">
            <span
              className={`w-1.5 h-1.5 rotate-45 ${item.highlight ? 'bg-indigo-400' : 'bg-stone-700'}`}
            />
            <span
              className={`text-[13px] ${item.highlight ? 'text-stone-300 font-bold' : 'text-stone-500'}`}
            >
              {item.text}
            </span>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between mt-auto pt-6 border-t border-stone-900 group-hover:border-stone-800 transition-colors">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-stone-600 uppercase">근거</span>
          <div className="flex -space-x-1.5">
            {footer.agents.map((agent) => {
              const AgentIcon = agent.icon;
              return (
                <div
                  key={agent.id}
                  className="w-5 h-5 rounded-full bg-stone-800 border border-[#141210] flex items-center justify-center"
                >
                  <AgentIcon size={10} className={agent.color} />
                </div>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-stone-500 tracking-tight truncate max-w-[180px]">
          {footer.methodology}
          <ChevronRight size={12} className="text-stone-700" />
        </div>
      </div>
    </div>
  );
}
