/**
 * PredictGroup — 예측 결과 그룹 (5 서브탭 라우팅)
 * 2026-04-28 IA 재구조 (T7) — URL ?sub=... query 기반 라우팅.
 */

import { useSearchParams } from 'react-router-dom';
import { Activity, TrendingUp, Gauge, Users, Sparkles } from 'lucide-react';
import type { SimulationOutput, PredictSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { TabButton } from '../shared/TabButton';
import { PredictSummaryTab } from '../sub/predict/PredictSummaryTab';
import { PredictSalesForecastTab } from '../sub/predict/PredictSalesForecastTab';
import { PredictFinancialSimTab } from '../sub/predict/PredictFinancialSimTab';
import { PredictCustomerFlowTab } from '../sub/predict/PredictCustomerFlowTab';
import { PredictEmergingDistrictTab } from '../sub/predict/PredictEmergingDistrictTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: PredictSubTab[] = [
  'summary',
  'sales_forecast',
  'financial_sim',
  'customer_flow',
  'emerging_district',
];

export function PredictGroup({ simResult, openModal }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subFromUrl = searchParams.get('sub') as PredictSubTab | null;
  const activeSub: PredictSubTab =
    subFromUrl && VALID.includes(subFromUrl) ? subFromUrl : 'summary';

  const setSub = (sub: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('sub', sub);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6">
      <nav className="flex border-b border-stone-800/60 overflow-x-auto scrollbar-hide">
        <TabButton
          id="summary"
          label="예측 요약"
          icon={Activity}
          active={activeSub === 'summary'}
          onClick={setSub}
        />
        <TabButton
          id="sales_forecast"
          label="매출 예측"
          icon={TrendingUp}
          active={activeSub === 'sales_forecast'}
          onClick={setSub}
        />
        <TabButton
          id="financial_sim"
          label="재무 시뮬레이션"
          icon={Gauge}
          active={activeSub === 'financial_sim'}
          onClick={setSub}
        />
        <TabButton
          id="customer_flow"
          label="고객·유동인구"
          icon={Users}
          active={activeSub === 'customer_flow'}
          onClick={setSub}
        />
        <TabButton
          id="emerging_district"
          label="신흥상권 감지"
          icon={Sparkles}
          active={activeSub === 'emerging_district'}
          onClick={setSub}
        />
      </nav>

      {activeSub === 'summary' && <PredictSummaryTab simResult={simResult} />}
      {activeSub === 'sales_forecast' && (
        <PredictSalesForecastTab simResult={simResult} openModal={openModal} />
      )}
      {activeSub === 'financial_sim' && <PredictFinancialSimTab simResult={simResult} />}
      {activeSub === 'customer_flow' && <PredictCustomerFlowTab />}
      {activeSub === 'emerging_district' && <PredictEmergingDistrictTab />}
    </div>
  );
}
