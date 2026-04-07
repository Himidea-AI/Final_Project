export default function PlanBadge({ planName }: { planName: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#f59e0b]/10 border border-[#f59e0b]/30 text-sm">
      <span className="text-[#fbbf24] font-bold">선택한 요금제:</span>
      <span className="text-[#fafafa] font-bold">{planName}</span>
    </div>
  );
}
