/**
 * DecisionCard — SummaryTab 상단 3 카드.
 * 질문형 제목 + Hero 배지 + 본문 설명 + 체크리스트 + footer 에이전트 아이콘.
 *
 * 모든 데이터는 상위에서 실 simResult 필드로 조립하여 props로 전달.
 * 디자인: italic 제목 + 모서리 micro dot + highlight 항목은 cyan 다이아 glow.
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
  /** footer "근거" 영역 클릭 시 실행. 지정되면 row가 버튼으로 활성화되고 hover/focus 링 표시. */
  onFootnoteClick?: () => void;
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
  onFootnoteClick,
}: DecisionCardProps) {
  const FootnoteEl = onFootnoteClick ? 'button' : 'div';
  const footnoteInteractive = onFootnoteClick != null;
  return (
    <div className="relative bg-[#141210] border border-stone-800/60 rounded-3xl p-8 flex flex-col h-full hover:border-stone-700 hover:shadow-[0_20px_50px_-25px_rgba(34,211,238,0.15)] transition-all group overflow-hidden">
      {/* 모서리 micro dot — 디자인 "완결감" */}
      <div className="absolute top-6 right-6 w-1 h-1 rounded-full bg-stone-800" />

      <h3 className="text-[20px] font-black text-stone-100 mb-6 italic tracking-tighter leading-tight">
        {title}
      </h3>

      <div
        className={`inline-block self-start px-4 py-2 rounded-xl border font-black text-lg mb-6 tracking-tight shadow-inner ${HERO_CLS[heroColor]}`}
      >
        {heroBadge}
      </div>

      <p className="text-[13px] text-stone-400 leading-relaxed mb-8 flex-grow font-medium">
        {description}
      </p>

      <div className="border-t border-dashed border-stone-800/80 mb-6 w-full" />

      <ul className="space-y-3 mb-8">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-3">
            <span
              className={`w-1.5 h-1.5 rotate-45 transition-colors shrink-0 ${
                item.highlight
                  ? 'bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]'
                  : 'bg-stone-700'
              }`}
            />
            <span
              className={`text-[13px] tracking-tight ${
                item.highlight ? 'text-stone-100 font-bold' : 'text-stone-500'
              }`}
            >
              {item.text}
            </span>
          </li>
        ))}
      </ul>

      <FootnoteEl
        {...(footnoteInteractive
          ? {
              type: 'button' as const,
              onClick: onFootnoteClick,
              'aria-label': `${title} — 근거 상세 보기`,
            }
          : {})}
        className={`w-full flex items-center justify-between mt-auto pt-6 border-t border-stone-900 text-left transition-colors ${
          footnoteInteractive
            ? 'cursor-pointer rounded-b-3xl -mx-8 -mb-8 px-8 pb-8 hover:bg-stone-900/40 hover:border-cyan-500/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40'
            : 'group-hover:border-stone-800'
        }`}
      >
        <div className="flex items-center gap-2">
          <span
            className={`text-[9px] font-black uppercase tracking-[0.2em] transition-colors ${
              footnoteInteractive ? 'text-stone-500 group-hover:text-cyan-400' : 'text-stone-600'
            }`}
          >
            근거
          </span>
          <div className="flex -space-x-1.5">
            {footer.agents.map((agent) => {
              const AgentIcon = agent.icon;
              return (
                <div
                  key={agent.id}
                  className="w-6 h-6 rounded-full bg-stone-900 border-2 border-[#141210] flex items-center justify-center shadow-md"
                >
                  <AgentIcon size={11} className={agent.color} />
                </div>
              );
            })}
          </div>
        </div>
        <div
          className={`flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest truncate max-w-[180px] transition-colors ${
            footnoteInteractive
              ? 'text-stone-500 group-hover:text-cyan-400'
              : 'text-stone-600 group-hover:text-stone-400'
          }`}
        >
          {footer.methodology}
          <ChevronRight
            size={12}
            className={`shrink-0 transition-all ${
              footnoteInteractive
                ? 'text-stone-600 group-hover:text-cyan-400 group-hover:translate-x-0.5'
                : 'text-stone-800 group-hover:text-stone-500'
            }`}
          />
        </div>
      </FootnoteEl>
    </div>
  );
}
