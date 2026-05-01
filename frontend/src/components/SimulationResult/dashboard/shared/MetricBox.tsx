interface MetricBoxProps {
  label: string;
  val: string;
  sub?: string;
}

export function MetricBox({ label, val, sub }: MetricBoxProps) {
  return (
    <div className="space-y-1 text-left">
      <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest leading-none mb-2">
        {label}
      </div>
      <div className="text-2xl font-black text-foreground tracking-tighter tabular-nums">{val}</div>
      {sub && <div className="text-[0.625rem] font-bold text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}
