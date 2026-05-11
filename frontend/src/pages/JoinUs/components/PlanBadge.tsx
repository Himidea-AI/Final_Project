export default function PlanBadge({ planName }: { planName: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/30 text-sm">
      <span className="text-primary/60 font-bold">선택한 요금제:</span>
      <span className="text-foreground font-bold">{planName}</span>
    </div>
  );
}
