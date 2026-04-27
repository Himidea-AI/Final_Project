import type { LucideIcon } from 'lucide-react';

interface Props {
  icon: LucideIcon;
  title: string; // uppercase 영문 권장 (예: "Core Parameters")
  sub: string; // 서브 설명 (예: "Primary Analysis Target")
}

/**
 * SectionLabel — SIMULATION CONTROLS 패널 내부 의미 섹션의 헤더.
 * 외부 mockup 패턴 채택: indigo accent + uppercase tracking-[0.2em] 영문 타이틀 + 서브 한국어 설명.
 */
export function SectionLabel({ icon: Icon, title, sub }: Props) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="p-1.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
        <Icon size={14} className="text-indigo-400" />
      </div>
      <div className="flex flex-col text-left">
        <span className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] leading-none">
          {title}
        </span>
        <span className="text-[9px] font-bold text-stone-600 uppercase mt-1 leading-none">
          {sub}
        </span>
      </div>
    </div>
  );
}

export default SectionLabel;
