interface MetricBoxProps {
  label: string;
  val: string;
  sub?: string;
}

export function MetricBox({ label, val, sub }: MetricBoxProps) {
  return (
    <div className="space-y-1 text-left">
      <div className="text-[10px] font-black text-stone-500 uppercase tracking-widest leading-none mb-2">
        {label}
      </div>
      <div className="text-2xl font-black text-stone-100 tracking-tighter tabular-nums">{val}</div>
      {sub && <div className="text-[10px] font-bold text-stone-600 mt-1">{sub}</div>}
    </div>
  );
}
