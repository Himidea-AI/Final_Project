/**
 * SectionLabel — 15 섹션 공통 헤더
 * "§01 COMMAND BAR / 시뮬레이션 실행 정보" 형식
 */

interface SectionLabelProps {
  number: string; // "§01"
  label: string; // "COMMAND BAR"
  subtitle?: string; // "시뮬레이션 실행 정보"
}

export function SectionLabel({ number, label, subtitle }: SectionLabelProps) {
  return (
    <div className="mb-6">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-xs text-amber-500 tracking-widest">{number}</span>
        <h2 className="text-xl font-semibold text-zinc-100 uppercase tracking-wide">{label}</h2>
      </div>
      {subtitle && <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>}
    </div>
  );
}
