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
      <div className="p-1.5 bg-primary/10 rounded-lg border border-primary/20">
        <Icon size={14} className="text-primary" />
      </div>
      <div className="flex flex-col text-left">
        <span className="text-[0.625rem] font-black text-primary uppercase tracking-[0.2em] leading-none">
          {title}
        </span>
        <span className="text-[0.5625rem] font-bold text-muted-foreground uppercase mt-1 leading-none">
          {sub}
        </span>
      </div>
    </div>
  );
}

export default SectionLabel;
