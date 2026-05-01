/**
 * AnalyzeGroup — AI 분석 그룹 (5 서브탭 라우팅)
 *
 * 2026-05-02 — 폴더 탭 패턴 (PredictGroup 동일):
 *   GooeyFilter SVG + active pill/bridge 액체 합쳐짐 + AnimatePresence content entrance.
 *   page(white) → panel(cool gray secondary) → card(white) 퐁당퐁당.
 */

import { useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Sparkles, MapPin, Users, Scale, Radar, type LucideIcon } from 'lucide-react';
import type { SimulationOutput, AnalyzeSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { GooeyFilter } from '../../../ui/GooeyFilter';
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

const GOO_FILTER_ID = 'analyze-tab-goo';

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
    <>
      <GooeyFilter id={GOO_FILTER_ID} strength={12} />

      <div className="relative">
        {/* (a) Visual background layer — gooey filter 적용. tab bg row + content panel bg 가
              같은 secondary 색. pill 의 marginBottom -2px 으로 panel 과 액체 합쳐짐. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex flex-col"
          style={{ filter: `url(#${GOO_FILTER_ID})` }}
        >
          <div className="flex w-full px-2">
            {TABS.map((t) => (
              <div key={t.id} className="relative h-14 flex-1">
                {activeSub === t.id && (
                  <motion.div
                    layoutId="analyzeTabPill"
                    className="absolute inset-0 rounded-t-3xl bg-secondary"
                    style={{ marginBottom: '-2px' }}
                    transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="w-full flex-1 rounded-3xl bg-secondary" />
        </div>

        {/* (b) Interactive layer — click + text + content. filter 영향 없음. */}
        <div className="relative z-10">
          <div className="flex w-full px-2">
            {TABS.map((t) => {
              const isActive = activeSub === t.id;
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSub(t.id)}
                  className={`flex h-14 flex-1 items-center justify-center gap-2 text-sm font-bold transition-colors ${
                    isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Icon size={16} />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </div>

          <div className="p-8">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeSub}
                initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                {activeSub === 'ai_summary' && <AnalyzeAiSummaryTab simResult={simResult} />}
                {activeSub === 'market' && (
                  <AnalyzeMarketTab simResult={simResult} openModal={openModal} />
                )}
                {activeSub === 'demographic' && <AnalyzeDemographicTab simResult={simResult} />}
                {activeSub === 'legal' && (
                  <AnalyzeLegalTab simResult={simResult} openModal={openModal} />
                )}
                {activeSub === 'agent_insight' && (
                  <AnalyzeAgentInsightTab simResult={simResult} openModal={openModal} />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </>
  );
}
