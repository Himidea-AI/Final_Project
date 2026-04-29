export type StatusColor = 'emerald' | 'indigo' | 'amber' | 'rose';

interface StatusCardProps {
  title: string;
  value: string;
  /** value 보조 서브라벨 (신뢰구간 범위 등) */
  subValue?: string;
  status: StatusColor;
  desc: string;
  drivers: string[];
}

const STATUS_DOT: Record<StatusColor, string> = {
  indigo: 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]',
  emerald: 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]',
  amber: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
  rose: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]',
};

const VALUE_COLOR: Record<StatusColor, string> = {
  indigo: 'text-stone-100',
  emerald: 'text-stone-100',
  amber: 'text-amber-500',
  rose: 'text-rose-400',
};

export function StatusCard({ title, value, subValue, status, desc, drivers }: StatusCardProps) {
  return (
    <div className="p-7 bg-stone-900/40 border border-stone-800/60 rounded-3xl flex flex-col h-full group hover:border-indigo-500/30 transition-all duration-300 shadow-xl text-left overflow-hidden">
      <div className="text-[0.625rem] font-black text-stone-500 uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[status]}`} />
        {title}
      </div>
      <div
        className={`text-3xl font-black mb-1 tracking-tighter tabular-nums ${VALUE_COLOR[status]}`}
      >
        {value}
      </div>
      {subValue && (
        <div className="text-[0.6875rem] font-bold text-stone-500 tabular-nums mb-4">
          {subValue}
        </div>
      )}
      <p className="text-[0.6875rem] text-stone-400 leading-relaxed mb-8 flex-grow font-medium">
        {desc}
      </p>
      <div className="flex flex-wrap gap-1.5 pt-5 border-t border-stone-800/50">
        {drivers.map((d, i) => (
          <span
            key={i}
            className="text-[0.5rem] font-black text-stone-500 bg-stone-900/50 px-2.5 py-1 rounded-md border border-stone-800 uppercase tracking-tighter group-hover:text-stone-400 transition-colors"
          >
            {d}
          </span>
        ))}
      </div>
    </div>
  );
}
