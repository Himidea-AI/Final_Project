/**
 * AbmGroup — ABM 시뮬레이터 (단일, /vacancy_evaluation 독립)
 * AnalyzeGroup 과 동일 패턴: page(white) → panel(cool gray bg-secondary) → card(white) 퐁당퐁당.
 * 서브탭 없으므로 Gooey filter / pill 없이 panel 만 적용.
 */

import type { SimulationOutput } from '../../../../types';
import { AbmTab } from '../tabs/AbmTab';

interface Props {
  simResult: SimulationOutput;
  brandName?: string;
  /** 업종 (cafe/restaurant/…) — 저장된 이력이면 props로 전달, 라이브 시뮬이면 undefined 가능 */
  businessType?: string | null;
}

export function AbmGroup({ simResult, brandName, businessType }: Props) {
  return (
    <div className="rounded-3xl bg-secondary p-4 sm:p-6">
      <AbmTab simResult={simResult} brandName={brandName} businessType={businessType} />
    </div>
  );
}
