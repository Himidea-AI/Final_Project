/**
 * SaveSimulationActions — 시뮬 이력 저장 SaveButton + SaveDialog 통합 컴포넌트.
 *
 * IM3-259 분리 호출 (/predict + /analyze/llm 독립 백그라운드) 환경에서
 * "내가 보던 결과 화면" 의 헤더에 저장 버튼이 있어야 UX 자연스러움.
 *
 * 2026-05-02 DB 분리: kind prop 으로 ML(foresee) / AI(ai) 분기 저장.
 * - kind='foresee' : SimulationOutput 의 ML 슬라이스 keys 만 picking → POST /simulation-foresee
 * - kind='ai'      : LLM 슬라이스 keys 만 picking → POST /simulation-ai
 * 2026-05-09 (Phase 4-C): kind='abm' 추가.
 * - kind='abm'     : abmContext.result 그대로 → POST /history/abm. simResult 는 메타(target_district 등)
 *                    fallback 으로만 사용.
 *
 * 같은 RUN 의 두 슬라이스 다 저장하면 두 row 생성 (별개 entry, parent 없음).
 *
 * scenario: store.params 그대로 — backend pydantic 수용 + DB 컬럼 추가 후 활성.
 */

import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useSimulationStore } from '../../stores/simulationStore';
import {
  useSaveAbmHistory,
  useSaveAIHistory,
  useSaveForeseeHistory,
} from '../../hooks/useSaveSimulation';
import { useToast } from '../Toast';
import { formatDocumentId } from '../../types/simulationHistory';
import type { SimulationKind } from '../../types/simulationHistory';
import type { SimulationOutput } from '../../types';
import { SaveButton } from './SaveButton';
import { SaveDialog } from './SaveDialog';

/** ABM 저장 시 필요한 컨텍스트 — kind='abm' 일 때 필수. */
export interface AbmSaveContext {
  /** /simulate-abm/{job_id}/result 응답 그대로. result JSONB 에 저장. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  abmResult: any;
  /** 후보 공실 좌표. */
  spotLat?: number | null;
  spotLon?: number | null;
  /** ABM 시나리오 (weather_override / weekend_force / rent_shock_pct / date_override / store_area). */
  scenario?: Record<string, unknown> | null;
  nAgents?: number | null;
  days?: number | null;
  /** target_district override — focusSpot.label 등. 미지정 시 simResult fallback. */
  targetDistrict?: string | null;
}

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  /** 어느 슬라이스 — DashboardPredictPage='foresee' / DashboardAnalyzePage='ai' / AbmTab='abm'. */
  kind: SimulationKind;
  /** 저장된 history ID (있으면 isSaved 분기). DashboardOutlet context 또는 store 에서 전달. */
  savedHistoryId?: number | null;
  /** kind='abm' 일 때 필수 — ABM 결과 + 시나리오 + 좌표 묶음. */
  abmContext?: AbmSaveContext;
}

/** SimulationOutput → foresee_result body 슬라이스 (ML 키만). backend ForeseeSaveRequest 와 정합. */
function pickForeseeResult(simResult: SimulationOutput): Record<string, unknown> {
  return {
    district_predictions: simResult.district_predictions,
    quarterly_projection: simResult.quarterly_projection,
    scenarios: simResult.scenarios,
    shap_result: simResult.shap_result,
    bep_months: simResult.bep_months,
    predicted_monthly_revenue: simResult.predicted_monthly_revenue,
    closure_rate: simResult.closure_rate,
    closure_risk: simResult.closure_risk,
    final_report: simResult.final_report,
    market_report: simResult.market_report,
    customer_segment: simResult.customer_segment,
    living_pop_forecast: simResult.living_pop_forecast,
  };
}

/** SimulationOutput → ai_result body 슬라이스 (LLM 키만). backend AISaveRequest 와 정합. */
function pickAIResult(
  simResult: SimulationOutput,
  verdictSummary: string | null,
  signal: 'green' | 'yellow' | 'red' | null,
): Record<string, unknown> {
  return {
    top_3_candidates: simResult.top_3_candidates,
    analysis_report: simResult.analysis_report,
    ai_recommendation: simResult.ai_recommendation,
    ai_verdict_summary: verdictSummary,
    market_entry_signal: signal,
    overall_legal_risk: simResult.overall_legal_risk,
    legal_risks: simResult.legal_risks,
    market_report: simResult.market_report,
    trend_forecast: simResult.trend_forecast,
    competitor_intel: simResult.competitor_intel,
    demographic_report: simResult.demographic_report,
    district_rankings: simResult.district_rankings,
    agent_attributions: simResult.agent_attributions,
    vacancy_applied: simResult.vacancy_applied,
    all_competitor_locations: simResult.all_competitor_locations,
  };
}

export function SaveSimulationActions({
  simResult,
  brandName,
  kind,
  savedHistoryId,
  abmContext,
}: Props) {
  const { user, brand } = useAuth();
  const { showToast } = useToast();
  const saveForesee = useSaveForeseeHistory();
  const saveAI = useSaveAIHistory();
  const saveAbm = useSaveAbmHistory();
  const active = kind === 'foresee' ? saveForesee : kind === 'ai' ? saveAI : saveAbm;
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const params = useSimulationStore((s) => s.params);
  const isSaved = savedHistoryId != null;

  // 저장에 사용될 동/업종 — store.params 우선, simResult fallback
  const targetDistrict =
    params?.target_districts?.[0] ?? params?.target_district ?? simResult.target_district ?? '';
  const targetDistricts =
    params?.target_districts ??
    (params?.target_district ? [params.target_district] : null) ??
    simResult.target_districts ??
    null;
  const bizKey = params?.business_type ?? '';

  const handleConfirmSave = async (clientName: string) => {
    const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
    const signalRaw = compIntel?.['market_entry_signal'];
    const signal =
      signalRaw === 'green' || signalRaw === 'yellow' || signalRaw === 'red' ? signalRaw : null;
    const verdictSummary =
      simResult.ai_recommendation?.split(/[.!?。]/)[0]?.slice(0, 200) ??
      simResult.analysis_report?.slice(0, 200) ??
      null;

    const finalBrandName = brand?.brand_name || user?.company_name || brandName || '브랜드 미지정';
    const businessType = bizKey || null;
    const scenario = params ? (params as unknown as Record<string, unknown>) : null;
    const winner = simResult.winner_district ?? null;

    let res = null;
    if (kind === 'foresee') {
      res = await saveForesee.save({
        client_name: clientName,
        brand_name: finalBrandName,
        business_type: businessType,
        districts: targetDistricts,
        target_district: targetDistrict || null,
        winner_district: winner,
        foresee_result: pickForeseeResult(simResult),
        scenario,
      });
    } else if (kind === 'ai') {
      res = await saveAI.save({
        client_name: clientName,
        brand_name: finalBrandName,
        business_type: businessType,
        target_district: targetDistrict || null,
        winner_district: winner,
        ai_result: pickAIResult(simResult, verdictSummary, signal),
        scenario,
      });
    } else {
      // kind === 'abm' — abmContext.result 그대로 result JSONB 로 저장.
      if (!abmContext || !abmContext.abmResult) {
        showToast('error', 'ABM 시뮬 결과가 없습니다. 시뮬을 먼저 실행해주세요.');
        return;
      }
      const abmTargetDistrict = abmContext.targetDistrict ?? targetDistrict ?? null;
      res = await saveAbm.save({
        client_name: clientName,
        brand_name: finalBrandName,
        business_type: businessType,
        target_district: abmTargetDistrict || null,
        spot_lat: abmContext.spotLat ?? null,
        spot_lon: abmContext.spotLon ?? null,
        n_agents: abmContext.nAgents ?? null,
        days: abmContext.days ?? null,
        scenario: (abmContext.scenario as Record<string, unknown> | null | undefined) ?? scenario,
        result: abmContext.abmResult as Record<string, unknown>,
      });
    }

    if (res) {
      // 2026-05-07: kind 별 저장 ID 분리 — 예측/분석 탭 저장 상태 독립.
      // 2026-05-09: ABM kind 추가.
      const store = useSimulationStore.getState();
      if (kind === 'foresee') {
        store.setSavedForeseeId(res.id);
      } else if (kind === 'ai') {
        store.setSavedAIId(res.id);
      } else {
        store.setSavedAbmId(res.id);
      }
      // legacy 단일 savedHistoryId — PDF/기타 호환용 마지막 저장 id 유지.
      store.setSavedHistoryId(res.id);
      setSaveDialogOpen(false);
      const kindLabel = kind === 'foresee' ? 'ML 예측' : kind === 'ai' ? 'AI 분석' : 'ABM 시뮬';
      showToast(
        'success',
        `${clientName} 고객님 ${kindLabel} 시뮬 이력이 저장되었습니다. (${formatDocumentId(res.id)})`,
      );
    }
  };

  return (
    <>
      <SaveButton
        onClick={() => setSaveDialogOpen(true)}
        saved={isSaved}
        label={isSaved ? `저장됨 · ${formatDocumentId(savedHistoryId ?? null)}` : undefined}
      />
      <SaveDialog
        open={saveDialogOpen}
        onClose={() => {
          setSaveDialogOpen(false);
          active.reset();
        }}
        meta={{
          brandName: brand?.brand_name || user?.company_name || brandName || '브랜드',
          district: targetDistrict,
          managerName: user?.contact_name || user?.email || '매니저',
        }}
        isSaving={active.isSaving}
        errorMessage={active.error}
        onConfirm={handleConfirmSave}
      />
    </>
  );
}
