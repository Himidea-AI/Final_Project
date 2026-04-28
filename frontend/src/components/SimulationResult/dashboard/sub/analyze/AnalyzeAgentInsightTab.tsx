/**
 * AnalyzeAgentInsightTab — 분석·AI 분석 근거 (thin wrapper)
 * 2026-04-28 IA 재구조 — 기존 InsightTab 그대로 재노출.
 */

import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { InsightTab } from '../../tabs/InsightTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function AnalyzeAgentInsightTab({ simResult, openModal }: Props) {
  return <InsightTab simResult={simResult} openModal={openModal} />;
}
