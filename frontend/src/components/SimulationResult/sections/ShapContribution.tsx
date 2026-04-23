import type { ShapResult, SimulationOutput } from '../../../types';
import { ShapChart } from '../ShapChart';
import { SectionLabel } from '../shared/SectionLabel';
import { AgentCard } from '../shared/AgentCard';

interface Props {
  simResult: SimulationOutput;
}

// SHAP 결과가 "있긴 하지만 전부 0"인 경우 차트가 빈 축만 남아 망가져 보임 → 별도 empty state로 분기
function hasMeaningfulShap(shap: ShapResult | null | undefined): boolean {
  if (!shap || !shap.feature_importance || shap.feature_importance.length === 0) return false;
  return shap.feature_importance.some((f) => Math.abs(f.shap_value) > 1e-6);
}

function EmptyShapCard() {
  return (
    <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-stone-700 bg-stone-900/40 text-center">
      <div className="mb-2 h-8 w-8 rounded-full bg-stone-700/60" />
      <div className="text-sm text-stone-400">SHAP 분석 데이터 없음</div>
      <div className="mt-1 text-xs text-stone-500">
        매출 데이터 부족으로 피처 기여도를 계산하지 못했습니다
      </div>
    </div>
  );
}

export function ShapContribution({ simResult }: Props) {
  const attrs = simResult.agent_attributions ?? [];
  const demo = attrs.find((a) => a.id === 'demographic_depth');
  const competitor = attrs.find((a) => a.id === 'competitor_intel');
  const meaningful = hasMeaningfulShap(simResult.shap_result);

  return (
    <section>
      <SectionLabel label="FEATURE CONTRIBUTION" subtitle="SHAP 피처 중요도 (상위 10)" />
      <div className="mb-3 rounded-lg border border-stone-700 bg-stone-800 p-4">
        {meaningful && simResult.shap_result ? (
          <ShapChart data={simResult.shap_result} />
        ) : (
          <EmptyShapCard />
        )}
      </div>
      {(demo || competitor) && (
        <div className="grid gap-2 md:grid-cols-2">
          {demo && <AgentCard attribution={demo} size="full" />}
          {competitor && <AgentCard attribution={competitor} size="full" />}
        </div>
      )}
    </section>
  );
}
