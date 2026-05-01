/**
 * AbmTab — ABM(Agent-Based Model) 공실 시뮬 전용 탭
 *
 * 기존 App.tsx inline 대시보드의 dashboardMode('map'|'abm') 플로우를 탭으로 이관.
 * 플로우:
 *   1) AgentMapVisualizer — 마포 지도 + 공실 마커 + 경쟁점. 공실 클릭 시
 *      /api/simulate-abm 호출로 5000 에이전트 × 1일 시뮬 실행
 *   2) AbmPersonaMap — 결과 수신 후 페르소나 행동 시뮬 오버레이
 *   3) "뒤로" → AgentMapVisualizer 복귀
 *
 * 이 탭은 TabbedDashboard v4.2 마이그레이션 시 누락되어 복원.
 *
 * 상태 관리: useState 로컬 → useAbmStore (zustand+persist+AbortController)로 이관.
 * 새로고침/탭 이동/dashboardMode 토글에도 in-flight 시뮬 결과를 잃지 않는다.
 */

import { useState, useEffect } from 'react';
import { MapPin, Radar, Loader2, AlertCircle } from 'lucide-react';
import type { SimulationOutput } from '../../../../types';
import AgentMapVisualizer from '../../../AgentMapVisualizer';
import AbmPersonaMap from '../../../AbmPersonaMap';
import { useAbmStore } from '../../../../stores/abmStore';

interface Props {
  simResult: SimulationOutput;
  brandName?: string;
  /** 업종 (cafe/restaurant/…) — 저장된 이력이면 props로 전달, 라이브 시뮬이면 undefined 가능 */
  businessType?: string | null;
  /** 신규 매장 평수 — backend seats=storeArea*2 + 잠식 계산에 사용. 미지정 시 simResult 에서 추출 또는 15. */
  storeArea?: number;
}

interface AbmScenario {
  weather_override: string | null;
  date_override: string | null;
  weekend_force: boolean;
  rent_shock_pct: number;
}

type DashboardMode = 'map' | 'abm';

export function AbmTab({ simResult, brandName, businessType, storeArea }: Props) {
  const [mode, setMode] = useState<DashboardMode>('map');

  // store selector — store 가 single source of truth. focusSpot 도 store 에 둠
  // (새로고침 시 어떤 spot 를 시뮬하던 중인지 같이 살리기 위해).
  const abmResult = useAbmStore((s) => s.result);
  const abmStatus = useAbmStore((s) => s.status);
  const abmError = useAbmStore((s) => s.error);
  const focusSpot = useAbmStore((s) => s.focusSpot);
  const startAbm = useAbmStore((s) => s.startAbm);
  const dismissResult = useAbmStore((s) => s.dismissResult);
  const setFocusSpot = useAbmStore((s) => s.setFocusSpot);
  const resumePollingIfNeeded = useAbmStore((s) => s.resumePollingIfNeeded);

  const abmLoading = abmStatus === 'running';

  // mount 시 persist 복원된 running jobId 가 있으면 polling 재개.
  // 또한 done 상태로 복원된 결과가 있으면 ABM 모드로 자동 진입.
  useEffect(() => {
    resumePollingIfNeeded();
    if ((abmStatus === 'running' || abmStatus === 'done') && focusSpot) {
      setMode('abm');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = simResult as any;
  const targetDistrict =
    r?.winner_district || r?.target_district || r?.target_districts?.[0] || '서교동';

  // 지도 마커 데이터 — raw JSONB에서 방어적 추출
  const vacancySpots = Array.isArray(r?.vacancy_spots) ? r.vacancy_spots : [];
  const competitorSamples = Array.isArray(r?.competitor_intel?.competition_500m?.samples)
    ? r.competitor_intel.competition_500m.samples
    : [];

  const locations = vacancySpots
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((s: any) => ({
      id: `vacancy_${s.id}`,
      name: s.dong_name ?? '공실',
      lat: s.lat,
      lng: s.lon,
      type: 'vacancy' as const,
      listingCount: s.listing_count,
    }))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((l: any) => typeof l.lat === 'number' && typeof l.lng === 'number');

  const competitors = competitorSamples
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((s: any) => s.lat && (s.lng ?? s.lon))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((s: any) => ({
      id: s.id ?? `comp_${s.place_name}_${s.lat}`,
      name: s.place_name || s.brand_name || '경쟁업체',
      lat: s.lat,
      lng: s.lng ?? s.lon,
      distance_m: s.distance_m,
      is_franchise: s.is_franchise ?? false,
      category: s.category,
    }));

  /** store action wrapper — payload 빌드 + startAbm 호출. */
  function runAbm(params: {
    districtOverride?: string;
    spotLat?: number;
    spotLon?: number;
    scenario: AbmScenario;
    nextFocusSpot?: { lat: number; lon: number; label?: string } | null;
  }) {
    const payload = {
      target_district: params.districtOverride ?? targetDistrict,
      business_type: businessType ?? 'cafe',
      brand_name: brandName || '신규 매장',
      langgraph_result: r?._raw ?? r,
      n_agents: 5000,
      days: 1,
      spot_lat: params.spotLat,
      spot_lon: params.spotLon,
      scenario: params.scenario,
      // Tier S 50명 LLM thought 활성 — 풍선/PersonaCard 시각화에 필요.
      enable_llm_thought: true,
      // Tier S/A LLM 의사결정 (A 옵션) — Tier 별 행동 차별화.
      enable_llm_decisions: true,
      // 신규 매장 평수.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store_area: storeArea ?? (r as any)?.storeArea ?? (r as any)?.store_area ?? 15,
    };
    return startAbm(payload, params.nextFocusSpot ?? null);
  }

  const handleAgentMapSpotClick = async (loc: { lat: number; lng: number; name: string }) => {
    if (abmLoading) return;
    setMode('abm');
    const next = { lat: loc.lat, lon: loc.lng, label: loc.name };
    await runAbm({
      districtOverride: loc.name,
      spotLat: loc.lat,
      spotLon: loc.lng,
      scenario: {
        weather_override: null,
        date_override: null,
        weekend_force: false,
        rent_shock_pct: 0.0,
      },
      nextFocusSpot: next,
    });
  };

  const handleAbmSpotClick = async (spot: { lat: number; lon: number; dong_name: string }) => {
    if (abmLoading) return;
    const next = { lat: spot.lat, lon: spot.lon, label: spot.dong_name };
    await runAbm({
      districtOverride: spot.dong_name,
      spotLat: spot.lat,
      spotLon: spot.lon,
      scenario: {
        weather_override: null,
        date_override: null,
        weekend_force: false,
        rent_shock_pct: 0.0,
      },
      nextFocusSpot: next,
    });
  };

  const handleRunSimulation = async (scenario: AbmScenario) => {
    await runAbm({ scenario, nextFocusSpot: focusSpot });
  };

  const handleClearResult = () => {
    dismissResult();
    setFocusSpot(null);
    setMode('map');
  };

  return (
    <div className="space-y-4">
      {/* 모드 토글 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-black text-stone-100 flex items-center gap-2 italic tracking-tight">
            {mode === 'map' ? (
              <>
                <MapPin size={16} className="text-indigo-400" /> 공실 스팟 지도 & Multi-Agent
                Geospatial
              </>
            ) : (
              <>
                <Radar size={16} className="text-cyan-400" /> ABM 페르소나 행동 시뮬 (
                {focusSpot?.label ?? '—'})
              </>
            )}
          </h3>
          {abmLoading && <Loader2 size={14} className="animate-spin text-stone-500" />}
        </div>
        {mode === 'abm' && (
          <button
            type="button"
            onClick={handleClearResult}
            className="text-[0.6875rem] font-bold text-stone-400 hover:text-stone-100 uppercase tracking-widest"
          >
            ← 지도로 돌아가기
          </button>
        )}
      </div>

      {/* 에러 배너 */}
      {abmError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300 flex items-start gap-2">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{abmError}</span>
        </div>
      )}

      {/* 지도 / ABM 뷰 */}
      {mode === 'map' ? (
        <div className="bg-stone-900/30 border border-stone-800 rounded-3xl p-4">
          <div className="h-14 bg-[#171717]/90 backdrop-blur-md border border-[#3a3633] rounded-t-2xl flex justify-between items-center px-6 shrink-0 mb-0">
            <h4 className="text-xs font-black text-stone-100 flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-[#818cf8] animate-pulse shadow-[0_0_10px_rgba(129,140,248,0.8)]" />
              Multi-Agent Geospatial Recommendations
            </h4>
            <p className="text-[0.625rem] text-stone-500 font-mono tracking-widest">
              AI AGENT TARGETING · {locations.length} VACANCY · {competitors.length} COMP
            </p>
          </div>
          <div className="relative bg-stone-950 rounded-b-2xl overflow-hidden">
            <AgentMapVisualizer
              height="600px"
              locations={locations.length > 0 ? locations : undefined}
              competitors={competitors}
              onSpotClick={handleAgentMapSpotClick}
            />
          </div>
        </div>
      ) : (
        <AbmPersonaMap
          abmResult={abmResult}
          abmLoading={abmLoading}
          abmError={null /* 에러는 위 배너에서 이미 표시 */}
          targetDistrict={targetDistrict}
          vacancySpots={vacancySpots}
          focusSpot={focusSpot}
          mode="general"
          competitors={competitors}
          onClearResult={handleClearResult}
          onSpotClick={handleAbmSpotClick}
          onRunSimulation={handleRunSimulation}
        />
      )}
    </div>
  );
}
