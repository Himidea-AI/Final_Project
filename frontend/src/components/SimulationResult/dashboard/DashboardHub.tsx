/**
 * DashboardHub — 시뮬 완료 진입점 (라우트 /dashboard).
 * 작은 헤더 (회사명 + 시뮬 일시 + 문서ID) + 3 HubCard 가로 배치.
 * mobile stack, lg 이상 가로 3등분.
 *
 * 2026-04-28 H7 — `onSelect` prop 추가 (옵셔널).
 *   - undefined: 기존 라우트 모드 (Link to /dashboard/predict 등). /dashboard 인덱스 라우트에서 사용.
 *   - 함수: in-page state 전환 모드 (button onClick). HistoryDashboardView 에서 사용.
 */

import type { SimulationOutput } from '../../../types';
import { formatDocumentId } from '../../../types/simulationHistory';
import { HubCard } from './HubCard';

export type HubView = 'predict' | 'analyze' | 'abm';

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  savedHistoryId?: number | null;
  /** 지정 시 카드 클릭 → onSelect(view) (button 모드). 미지정 시 Link 라우트 모드. */
  onSelect?: (view: HubView) => void;
}

const HUB_IMAGES = {
  predict:
    'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&auto=format&fit=crop&q=80',
  analyze:
    'https://images.unsplash.com/photo-1486325212027-8081e485255e?w=800&auto=format&fit=crop&q=80',
  abm: 'https://images.unsplash.com/photo-1519567241046-7f570eee3ce6?w=800&auto=format&fit=crop&q=80',
};

export function DashboardHub({
  simResult: _simResult,
  brandName,
  savedHistoryId,
  onSelect,
}: Props) {
  const docId = formatDocumentId(savedHistoryId ?? null);
  const createdAt = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });

  return (
    <div className="mx-auto max-w-[1728px] px-8 pt-28 pb-12">
      <header className="mb-12 flex items-end justify-between border-b border-stone-800/60 pb-6">
        <h1 className="text-2xl font-black text-stone-100 tracking-tight">{brandName || '—'}</h1>
        <div className="text-right">
          <div className="text-[10px] font-mono uppercase tracking-widest text-stone-500">
            {docId}
          </div>
          <div className="mt-1 text-[10px] font-mono text-stone-600">{createdAt}</div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('predict')}
            title="예측 결과"
            description="ML 기반 매출 · 재무 · 폐업 위험도 정량 예측"
            imgSrc={HUB_IMAGES.predict}
            imgAlt="데이터 차트 시각화"
            accent="indigo"
          />
        ) : (
          <HubCard
            to="/dashboard/predict"
            title="예측 결과"
            description="ML 기반 매출 · 재무 · 폐업 위험도 정량 예측"
            imgSrc={HUB_IMAGES.predict}
            imgAlt="데이터 차트 시각화"
            accent="indigo"
          />
        )}
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('analyze')}
            title="AI 분석"
            description="LLM 기반 상권 · 인구 · 법률 · 경쟁 정성 분석"
            imgSrc={HUB_IMAGES.analyze}
            imgAlt="도시 거리 풍경"
            accent="cyan"
          />
        ) : (
          <HubCard
            to="/dashboard/analyze"
            title="AI 분석"
            description="LLM 기반 상권 · 인구 · 법률 · 경쟁 정성 분석"
            imgSrc={HUB_IMAGES.analyze}
            imgAlt="도시 거리 풍경"
            accent="cyan"
          />
        )}
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('abm')}
            title="ABM 시뮬레이터"
            description="100명 에이전트 행동 시뮬레이션 + 공실 평가"
            imgSrc={HUB_IMAGES.abm}
            imgAlt="사람들이 다니는 거리"
            accent="amber"
          />
        ) : (
          <HubCard
            to="/dashboard/abm"
            title="ABM 시뮬레이터"
            description="100명 에이전트 행동 시뮬레이션 + 공실 평가"
            imgSrc={HUB_IMAGES.abm}
            imgAlt="사람들이 다니는 거리"
            accent="amber"
          />
        )}
      </div>
    </div>
  );
}
