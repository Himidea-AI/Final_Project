export default function PlanBadge({ planName }: { planName: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#818cf8]/10 border border-[#818cf8]/30 text-sm">
      <span className="text-[#a5b4fc] font-bold">선택한 요금제:</span>
      <span className="text-[#fafafa] font-bold">{planName}</span>
    </div>
  );
}
