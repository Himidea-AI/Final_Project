/**
 * PlaceholderPanel — 미연동 서브탭용 "준비 중" 안내
 * 2026-04-28 — B2 미연동 ML (customer_revenue, emerging_district) endpoint 노출 전 임시 표시.
 */

interface Props {
  modelName?: string;
  description?: string;
}

export function PlaceholderPanel({
  modelName,
  description = '해당 분석 모델 연동 후 활성화됩니다.',
}: Props) {
  return (
    <div className="flex h-64 flex-col items-center justify-center rounded-3xl border border-dashed border-stone-800 bg-stone-950/30 text-stone-500">
      <p className="text-sm font-bold">준비 중입니다.</p>
      <p className="mt-1 text-xs">{description}</p>
      {modelName && (
        <p className="mt-3 text-[0.625rem] font-mono uppercase tracking-widest text-stone-600">
          {modelName}
        </p>
      )}
    </div>
  );
}
