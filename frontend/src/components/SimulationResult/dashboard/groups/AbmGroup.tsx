/**
 * AbmGroup — ABM 시뮬레이터 (단일, /vacancy_evaluation 독립)
 * 기존 AbmTab 그대로 wrapping. 서브탭 없음.
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
  return <AbmTab simResult={simResult} brandName={brandName} businessType={businessType} />;
}
