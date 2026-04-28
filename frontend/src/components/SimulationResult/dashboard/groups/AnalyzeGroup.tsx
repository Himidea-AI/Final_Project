/**
 * AnalyzeGroup — AI 분석 그룹 (5 서브탭 라우팅)
 */

import { useSearchParams } from 'react-router-dom';
import { Sparkles, MapPin, Users, Scale, Radar, type LucideIcon } from 'lucide-react';
import type { SimulationOutput, AnalyzeSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { TabButton } from '../shared/TabButton';
import { AnalyzeAiSummaryTab } from '../sub/analyze/AnalyzeAiSummaryTab';
import { AnalyzeMarketTab } from '../sub/analyze/AnalyzeMarketTab';
import { AnalyzeDemographicTab } from '../sub/analyze/AnalyzeDemographicTab';
import { AnalyzeLegalTab } from '../sub/analyze/AnalyzeLegalTab';
import { AnalyzeAgentInsightTab } from '../sub/analyze/AnalyzeAgentInsightTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: AnalyzeSubTab[] = ['ai_summary', 'market', 'demographic', 'legal', 'agent_insight'];

const TABS: { id: AnalyzeSubTab; label: string; icon: LucideIcon }[] = [
  { id: 'ai_summary', label: 'AI 분석 요약', icon: Sparkles },
  { id: 'market', label: '상권 분석', icon: MapPin },
  { id: 'demographic', label: '인구 분석', icon: Users },
  { id: 'legal', label: '법률 리스크', icon: Scale },
  { id: 'agent_insight', label: '에이전트 근거', icon: Radar },
];

export function AnalyzeGroup({ simResult, openModal }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subFromUrl = searchParams.get('sub') as AnalyzeSubTab | null;
  const activeSub: AnalyzeSubTab =
    subFromUrl && VALID.includes(subFromUrl) ? subFromUrl : 'ai_summary';

  const setSub = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('sub', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-2 border-b border-stone-800 pb-2 overflow-x-auto scrollbar-hide">
        {TABS.map((t) => (
          <TabButton
            key={t.id}
            id={t.id}
            label={t.label}
            icon={t.icon}
            active={activeSub === t.id}
            onClick={setSub}
          />
        ))}
      </div>

      {activeSub === 'ai_summary' && <AnalyzeAiSummaryTab simResult={simResult} />}
      {activeSub === 'market' && <AnalyzeMarketTab simResult={simResult} openModal={openModal} />}
      {activeSub === 'demographic' && <AnalyzeDemographicTab simResult={simResult} />}
      {activeSub === 'legal' && <AnalyzeLegalTab simResult={simResult} openModal={openModal} />}
      {activeSub === 'agent_insight' && (
        <AnalyzeAgentInsightTab simResult={simResult} openModal={openModal} />
      )}
    </div>
  );
}
