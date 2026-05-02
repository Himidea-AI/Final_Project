/**
 * PredictGroup — 예측 결과 그룹 (4 서브탭 라우팅)
 * 2026-04-28 IA 재구조 (T7) — URL ?sub=... query 기반 라우팅.
 * 2026-04-28 (Task B2) — PredictSummaryTab 제거. ?sub=summary → ?sub=sales_forecast redirect.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { TrendingUp, Gauge, Users, Sparkles, Sliders, type LucideIcon } from 'lucide-react';
import type { SimulationOutput, PredictSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { GooeyFilter } from '../../../ui/GooeyFilter';
import { PredictSalesForecastTab } from '../sub/predict/PredictSalesForecastTab';
import { PredictFinancialSimTab } from '../sub/predict/PredictFinancialSimTab';
import { PredictCustomerFlowTab } from '../sub/predict/PredictCustomerFlowTab';
import { PredictEmergingDistrictTab } from '../sub/predict/PredictEmergingDistrictTab';
import { PredictScenarioSimTab } from '../sub/predict/PredictScenarioSimTab';

const TABS: { id: PredictSubTab; label: string; icon: LucideIcon }[] = [
  { id: 'sales_forecast', label: '매출 예측', icon: TrendingUp },
  { id: 'financial_sim', label: '재무 시뮬레이션', icon: Gauge },
  { id: 'customer_flow', label: '고객·유동인구', icon: Users },
  { id: 'emerging_district', label: '신흥상권 감지', icon: Sparkles },
  { id: 'scenario', label: '시나리오', icon: Sliders },
];

const GOO_FILTER_ID = 'predict-tab-goo';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: PredictSubTab[] = [
  'sales_forecast',
  'financial_sim',
  'customer_flow',
  'emerging_district',
  'scenario',
];

export function PredictGroup({ simResult, openModal }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subFromUrl = searchParams.get('sub');

  // Legacy ?sub=summary → ?sub=sales_forecast redirect (B2 — summary 탭 제거)
  useEffect(() => {
    if (subFromUrl === 'summary') {
      const next = new URLSearchParams(searchParams);
      next.set('sub', 'sales_forecast');
      setSearchParams(next, { replace: true });
    }
  }, [subFromUrl, searchParams, setSearchParams]);

  const activeSub: PredictSubTab =
    subFromUrl && VALID.includes(subFromUrl as PredictSubTab)
      ? (subFromUrl as PredictSubTab)
      : 'sales_forecast';

  const setSub = (sub: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('sub', sub);
    setSearchParams(next, { replace: true });
  };

  return (
    <>
      {/* SVG goo filter 정의 — DOM 한 번 mount, panel wrapper 가 url(#) 로 참조. */}
      <GooeyFilter id={GOO_FILTER_ID} strength={12} />

      {/* 레퍼런스 패턴 — folder tab + content panel 통합 surface:
          panel bg 와 active tab pill 이 같은 secondary 색이라 둘이 같은 filter 안에서
          액체로 합쳐짐. tab 이 panel 위로 솟아오른 폴더 탭 형태. motion 시 액체로 늘어남.
          page bg = white, panel bg = secondary 로 시각 분리. */}
      <div className="relative">
        {/* (a) Visual background layer — gooey filter 적용.
              flex flex-col + inset-0 으로 absolute container 가 부모 height (= interactive layer
              자연 콘텐츠) 채우고, panel bg 는 flex-1 로 tab row 제외 remaining 자동 차지.
              탭마다 콘텐츠 양이 달라도 동적 high 따라감 (이전 minHeight 400 hardcoded 제거). */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex flex-col"
          style={{ filter: `url(#${GOO_FILTER_ID})` }}
        >
          {/* Tab 배경 row */}
          <div className="flex w-full px-2">
            {TABS.map((t) => (
              <div key={t.id} className="relative h-14 flex-1">
                {activeSub === t.id && (
                  <motion.div
                    layoutId="predictTabPill"
                    className="absolute inset-0 rounded-t-3xl bg-secondary"
                    style={{ marginBottom: '-2px' }}
                    transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
                  />
                )}
              </div>
            ))}
          </div>
          {/* Content panel bg — flex-1 로 remaining height. pill 과 -2px 겹쳐 액체 연결. */}
          <div className="w-full flex-1 rounded-3xl bg-secondary" />
        </div>

        {/* (b) Interactive layer — click + text + content. filter 영향 없음. */}
        <div className="relative z-10">
          {/* Tab buttons row */}
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

          {/* Content area — entrance transition (Layer 2 그대로 유지) */}
          <div className="p-8">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeSub}
                initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                {activeSub === 'sales_forecast' && (
                  <PredictSalesForecastTab simResult={simResult} openModal={openModal} />
                )}
                {activeSub === 'financial_sim' && <PredictFinancialSimTab simResult={simResult} />}
                {activeSub === 'customer_flow' && <PredictCustomerFlowTab simResult={simResult} />}
                {activeSub === 'emerging_district' && (
                  <PredictEmergingDistrictTab simResult={simResult} />
                )}
                {activeSub === 'scenario' && <PredictScenarioSimTab simResult={simResult} />}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </>
  );
}
