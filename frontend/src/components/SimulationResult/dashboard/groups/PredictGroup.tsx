/**
 * PredictGroup — 예측 결과 그룹 (4 서브탭 라우팅)
 * 2026-04-28 IA 재구조 (T7) — URL ?sub=... query 기반 라우팅.
 * 2026-04-28 (Task B2) — PredictSummaryTab 제거. ?sub=summary → ?sub=sales_forecast redirect.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { TrendingUp, Gauge, Users, Sparkles } from 'lucide-react';
import type { SimulationOutput, PredictSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { TabButton } from '../shared/TabButton';
import { PredictSalesForecastTab } from '../sub/predict/PredictSalesForecastTab';
import { PredictFinancialSimTab } from '../sub/predict/PredictFinancialSimTab';
import { PredictCustomerFlowTab } from '../sub/predict/PredictCustomerFlowTab';
import { PredictEmergingDistrictTab } from '../sub/predict/PredictEmergingDistrictTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: PredictSubTab[] = [
  'sales_forecast',
  'financial_sim',
  'customer_flow',
  'emerging_district',
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
    <div className="space-y-6">
      <nav className="flex border-b border-border/60 overflow-x-auto scrollbar-hide">
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

      {activeSub === 'sales_forecast' && (
        <PredictSalesForecastTab simResult={simResult} openModal={openModal} />
      )}
      {activeSub === 'financial_sim' && <PredictFinancialSimTab simResult={simResult} />}
      {activeSub === 'customer_flow' && <PredictCustomerFlowTab simResult={simResult} />}
      {activeSub === 'emerging_district' && <PredictEmergingDistrictTab simResult={simResult} />}
    </div>
  );
}
