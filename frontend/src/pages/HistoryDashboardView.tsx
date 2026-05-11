/**
 * HistoryDashboardView — History 페이지 (저장된 이력 상세) 내부의 대시보드 뷰.
 *
 * 라우트 변경 없이 useState 기반으로 hub ↔ predict/analyze/abm 전환.
 * 라우트로 변경하면 History detail URL 의 SPA 진입점이 깨지므로 in-page state 전환 채택.
 *
 * - DashboardHub 의 `onSelect` prop 활용해 button 모드로 카드 동작.
 * - 각 group 은 `/dashboard/*` 라우트 페이지와 동일한 wrapper (max-w-[1728px] px-8 py-8 + ← Hub).
 * - DetailModal 은 view 상관없이 항상 마운트 (포털 기반).
 *
 * 2026-04-28 H7 — TabbedDashboard 삭제와 함께 도입.
 * 2026-05-02 — kind prop 추가:
 *   - kind='foresee' → 3-card hub 안 보이고 PredictGroup 직접 렌더 (← 목록으로)
 *   - kind='ai'      → AnalyzeGroup 직접 렌더
 *   - kind=null (legacy) → 기존 hub (3 card)
 *   ABM 카드는 분리 X — legacy hub 진입 시에만.
 */

import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { SimulationOutput } from '../types';
import type { SimulationKind } from '../types/simulationHistory';
import { DashboardHub, type HubView } from '../components/SimulationResult/dashboard/DashboardHub';
import { PredictGroup } from '../components/SimulationResult/dashboard/groups/PredictGroup';
import { AnalyzeGroup } from '../components/SimulationResult/dashboard/groups/AnalyzeGroup';
import { AbmGroup } from '../components/SimulationResult/dashboard/groups/AbmGroup';
import {
  DetailModal,
  type DetailModalContent,
} from '../components/SimulationResult/dashboard/shared/DetailModal';

type View = 'hub' | HubView;

interface Props {
  simResult: SimulationOutput;
  savedHistoryId?: number | null;
  brandName: string;
  businessType?: string | null;
  /**
   * 슬라이스 종류 — 신규 분리 라우트 (/dashboard/foresee/:id, /dashboard/ai/:id) 진입 시 주입.
   * null 이면 legacy /dashboard/history/:id 라우트 — 기존 3-card hub 그대로.
   */
  kind?: SimulationKind | null;
}

export function HistoryDashboardView({
  simResult,
  savedHistoryId,
  brandName,
  businessType,
  kind = null,
}: Props) {
  const navigate = useNavigate();
  // legacy(kind=null) 만 hub state — 신규 kind 라우트는 단일 view 직접 렌더.
  const [view, setView] = useState<View>('hub');
  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (c: DetailModalContent) => setModalContent(c);

  const backToList = (
    <button
      type="button"
      onClick={() => navigate('/dashboard')}
      className="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      목록으로
    </button>
  );

  const backToHub = (
    <button
      type="button"
      onClick={() => setView('hub')}
      className="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      Hub
    </button>
  );

  // ── 신규 분리 라우트 (kind 'foresee' | 'ai') — hub 우회, 단일 group 직접 렌더 ──
  if (kind === 'foresee') {
    return (
      <>
        <div className="mx-auto max-w-[1728px] px-8 py-8">
          <div className="mb-6">{backToList}</div>
          <PredictGroup simResult={simResult} openModal={openModal} />
        </div>
        <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
      </>
    );
  }

  if (kind === 'ai') {
    return (
      <>
        <div className="mx-auto max-w-[1728px] px-8 py-8">
          <div className="mb-6">{backToList}</div>
          <AnalyzeGroup simResult={simResult} openModal={openModal} />
        </div>
        <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
      </>
    );
  }

  // ── legacy /dashboard/history/:id — 기존 3-card hub 그대로 ──
  return (
    <>
      {view === 'hub' && (
        <DashboardHub
          simResult={simResult}
          brandName={brandName}
          savedHistoryId={savedHistoryId}
          onSelect={(v) => setView(v)}
        />
      )}

      {view === 'predict' && (
        <div className="mx-auto max-w-[1728px] px-8 py-8">
          <div className="mb-6">{backToHub}</div>
          <PredictGroup simResult={simResult} openModal={openModal} />
        </div>
      )}

      {view === 'analyze' && (
        <div className="mx-auto max-w-[1728px] px-8 py-8">
          <div className="mb-6">{backToHub}</div>
          <AnalyzeGroup simResult={simResult} openModal={openModal} />
        </div>
      )}

      {view === 'abm' && (
        <div className="mx-auto max-w-[1728px] px-8 py-8">
          <div className="mb-6">{backToHub}</div>
          <AbmGroup simResult={simResult} brandName={brandName} businessType={businessType} />
        </div>
      )}

      <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
    </>
  );
}
