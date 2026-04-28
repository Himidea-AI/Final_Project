/**
 * AnalyzeLegalTab — 분석·법률·규제 (thin wrapper)
 * 2026-04-28 IA 재구조 — 기존 LegalTab 그대로 재노출.
 */

import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { LegalTab } from '../../tabs/LegalTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function AnalyzeLegalTab({ simResult, openModal }: Props) {
  return <LegalTab simResult={simResult} openModal={openModal} />;
}
