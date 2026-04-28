/**
 * AnalyzeDemographicTab — 분석·인구·고객 (thin wrapper)
 * 2026-04-28 IA 재구조 — 기존 DemographicTab 그대로 재노출.
 */

import type { SimulationOutput } from '../../../../../types';
import { DemographicTab } from '../../tabs/DemographicTab';

interface Props {
  simResult: SimulationOutput;
}

export function AnalyzeDemographicTab({ simResult }: Props) {
  return <DemographicTab simResult={simResult} />;
}
