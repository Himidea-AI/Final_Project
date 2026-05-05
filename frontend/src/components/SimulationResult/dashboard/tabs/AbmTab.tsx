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
  // displayResult (history view) 우선, 없으면 active result. 사용자 피드백 (2026-05-05):
  // history click 으로 active 시뮬이 destroy 되지 않도록 displayResult 채널 분리.
  const activeResult = useAbmStore((s) => s.result);
  const displayResult = useAbmStore((s) => s.displayResult);
  const abmResult = displayResult ?? activeResult;
  const abmStatus = useAbmStore((s) => s.status);
  const abmError = useAbmStore((s) => s.error);
  const activeFocusSpot = useAbmStore((s) => s.focusSpot);
  const displayFocusSpot = useAbmStore((s) => s.displayFocusSpot);
  // displayResult 가 있으면 그 spot, 없으면 active focusSpot.
  const focusSpot = displayResult ? displayFocusSpot : activeFocusSpot;
  const enqueueAbm = useAbmStore((s) => s.enqueueAbm);
  const dismissResult = useAbmStore((s) => s.dismissResult);
  const clearDisplayResult = useAbmStore((s) => s.clearDisplayResult);
  const setFocusSpot = useAbmStore((s) => s.setFocusSpot);
  const resumePollingIfNeeded = useAbmStore((s) => s.resumePollingIfNeeded);

  const abmLoading = abmStatus === 'running';

  // mount 시 persist 복원된 running jobId 가 있으면 polling 재개.
  // running 일 때만 ABM 모드 자동 진입 — done 결과는 map 모드에서
  // 공실 스팟 다시 고를 수 있도록 자동 진입 제외 (사용자가 토글로 결과 확인).
  useEffect(() => {
    resumePollingIfNeeded();
    if (abmStatus === 'running' && focusSpot) {
      setMode('abm');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = simResult as any;
  const targetDistrict =
    r?.winner_district || r?.target_district || r?.target_districts?.[0] || '서교동';

  // 지도 마커 데이터 — 상권분석 페이지 (MapSection.buildBestVacancies) 와 동일 로직:
  // winner_district 의 vacancy_spots 중 score 내림차순 top 4. 별도 추천 에이전트 출력 없음.
  // recommended_vacancy_spots 가 있으면 그것 우선 (신규 에이전트 도입 시 자동 활용).
  const winner: string | undefined = r?.winner_district || r?.target_district;
  const recommendedSpots = Array.isArray(r?.recommended_vacancy_spots)
    ? r.recommended_vacancy_spots.slice(0, 4)
    : [];
  const allVacancySpots = Array.isArray(r?.vacancy_spots) ? r.vacancy_spots : [];
  // 상권분석과 동일 — winner dong 만 + score 내림차순 → top 4.
  const winnerVacancySpots = allVacancySpots
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter(
      (s: any) => s.dong_name === winner && typeof s.lat === 'number' && typeof s.lon === 'number',
    )
    .slice()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .sort((a: any, b: any) => {
      const sa = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY;
      const sb = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY;
      if (sa !== sb) return sb - sa;
      return (b.listing_count ?? 0) - (a.listing_count ?? 0);
    })
    .slice(0, 4);
  const vacancySpots = recommendedSpots.length > 0 ? recommendedSpots : winnerVacancySpots;
  // 경쟁업체 — 상권분석 페이지 buildCompetitors 와 동일. all_competitor_locations 우선 (max 200),
  // fallback: competitor_intel.competition_500m.samples (max 100).
  const allCompetitorLocations = Array.isArray(r?.all_competitor_locations)
    ? r.all_competitor_locations.slice(0, 200)
    : [];
  const competitorSamples =
    allCompetitorLocations.length > 0
      ? allCompetitorLocations
      : Array.isArray(r?.competitor_intel?.competition_500m?.samples)
        ? r.competitor_intel.competition_500m.samples.slice(0, 100)
        : [];

  // 동일 브랜드 자사 매장 — winner+top3 4동 안. competitors 와 별도 marker 로 표시.
  const sameBrandLocations = Array.isArray(r?.same_brand_locations) ? r.same_brand_locations : [];

  // recommendedSpots 가 활성이면 'recommended' 타입 + score/reason 전달.
  const isRecommendedMode = recommendedSpots.length > 0;
  const locations = vacancySpots
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((s: any) => ({
      id: `vacancy_${s.id}`,
      name: s.dong_name ?? '공실',
      lat: s.lat,
      lng: s.lon ?? s.lng,
      type: (isRecommendedMode ? 'recommended' : 'vacancy') as 'recommended' | 'vacancy',
      listingCount: s.listing_count,
      score: typeof s.score === 'number' ? s.score : undefined,
      reason: typeof s.reason === 'string' ? s.reason : undefined,
    }))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((l: any) => typeof l.lat === 'number' && typeof l.lng === 'number');

  const competitors = [
    ...competitorSamples
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
      })),
    // 동일 브랜드 자사 매장 — competitors 컴포넌트 슬롯에 합쳐 marker 표시.
    // is_franchise=true 로 marker 색 분기 가능 (자사 = 다른 색 권장).
    ...sameBrandLocations
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((s: any) => s.lat && (s.lng ?? s.lon))
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .map((s: any) => ({
        id: s.id ? `own_${s.id}` : `own_${s.place_name}_${s.lat}`,
        name: s.place_name || s.brand_name || '자사 매장',
        lat: s.lat,
        lng: s.lng ?? s.lon,
        distance_m: undefined,
        is_franchise: true, // 자사 = 동일 브랜드 표식
        category: s.category ?? 'own_brand',
      })),
  ];

  /** store action wrapper — payload 빌드 + enqueueAbm 호출 (active 가 비면 즉시 시작, 아니면 queue). */
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
    return enqueueAbm(payload, params.nextFocusSpot ?? null);
  }

  // spot 클릭 — 즉시 시뮬 실행 X. abm 모드 진입 + focusSpot 만 set.
  // 사용자 피드백 (2026-05-04): 진행 중 시뮬은 cancel 하지 않음. 사용자가 시나리오 패널에서
  // "시뮬 실행" 누르면 enqueueAbm 으로 queue 에 추가됨 (active 종료 후 자동 pop).
  // 사용자 피드백 (2026-05-05): spot 새로 클릭 시 직전 abmResult 가 살아있으면 결과 화면이
  // 바로 나와 시나리오 form 이 안 보임 → dismissResult 호출. result 는 history 에 유지.
  const handleAgentMapSpotClick = async (loc: { lat: number; lng: number; name: string }) => {
    setMode('abm');
    setFocusSpot({ lat: loc.lat, lon: loc.lng, label: loc.name });
    clearDisplayResult();
    if (abmStatus === 'done' || abmStatus === 'error') dismissResult();
  };

  const handleAbmSpotClick = async (spot: { lat: number; lon: number; dong_name: string }) => {
    setFocusSpot({ lat: spot.lat, lon: spot.lon, label: spot.dong_name });
    clearDisplayResult();
    if (abmStatus === 'done' || abmStatus === 'error') dismissResult();
  };

  // 시나리오 패널 "시뮬 실행" 버튼 — focusSpot 좌표 + scenario 로 enqueueAbm.
  const handleRunSimulation = async (scenario: AbmScenario) => {
    runAbm({
      districtOverride: focusSpot?.label,
      spotLat: focusSpot?.lat,
      spotLon: focusSpot?.lon,
      scenario,
      nextFocusSpot: focusSpot,
    });
  };

  // "지도로 돌아가기" — 진행 중 시뮬은 그대로 둔다 (background 에서 계속). 단순 navigation.
  // 사용자가 cancel 하려면 별도 cancel UI (e.g. AbmFloatingWidget) 사용.
  const handleClearResult = () => {
    setFocusSpot(null);
    clearDisplayResult();
    setMode('map');
  };

  return (
    <div className="space-y-4">
      {/* 모드 토글 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-black text-foreground flex items-center gap-2 italic tracking-tight">
            {mode === 'map' ? (
              <>
                <MapPin size={16} className="text-primary" /> 공실 스팟 지도 & Multi-Agent
                Geospatial
              </>
            ) : (
              <>
                <Radar size={16} className="text-primary" /> ABM 페르소나 행동 시뮬 (
                {focusSpot?.label || targetDistrict || '—'})
              </>
            )}
          </h3>
          {abmLoading && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
        </div>
        {mode === 'abm' && (
          <button
            type="button"
            onClick={handleClearResult}
            className="text-[0.6875rem] font-bold text-muted-foreground hover:text-foreground uppercase tracking-widest"
          >
            ← 지도로 돌아가기
          </button>
        )}
      </div>

      {/* 에러 배너 */}
      {abmError && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger flex items-start gap-2">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{abmError}</span>
        </div>
      )}

      {/* 지도 / ABM 뷰 — 퐁당퐁당: AbmGroup(card white) → 여기 panel(secondary gray)
          → 안 inner cards(card white). 사용자 피드백 (2026-05-05): 제일 밖 white. */}
      {mode === 'map' ? (
        <div className="bg-secondary border border-border rounded-3xl p-4 flex flex-col gap-3">
          {/* 시뮬레이션 안내 — 첫 진입 시 컨텍스트. 사용자 피드백 (2026-05-05). */}
          <div className="rounded-2xl border border-primary/25 bg-primary/[0.04] px-4 py-3 flex items-start gap-3">
            <div className="shrink-0 w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center">
              <Radar size={14} className="text-primary" />
            </div>
            <div className="flex flex-col gap-1 min-w-0">
              <p className="text-[12px] font-black text-foreground tracking-tight leading-tight">
                ABM 시뮬레이터 — 마포 5,000 페르소나 행동 시뮬
              </p>
              <p className="text-[11px] text-muted-foreground leading-snug tracking-tight">
                지도에서 <span className="font-bold text-foreground">공실 spot (초록)</span> 클릭 →
                <span className="font-bold text-foreground"> 시나리오 (날씨/요일/임대료)</span> 설정
                → 시뮬 실행. 5,000 가상 에이전트가 마포 전역에서 이동·소비 패턴 시뮬 → 선택 spot 의
                일 방문/매출/잠식 추정. 여러 spot 큐 누적 → 순차 실행 (우하단 패널).
              </p>
              <p className="text-[10px] text-muted-foreground/80 leading-snug">
                범례:{' '}
                <span className="font-bold" style={{ color: '#fb565b' }}>
                  ▲ 자사 매장
                </span>
                {' · '}
                <span className="font-bold" style={{ color: '#ffba00' }}>
                  ▲ 경쟁업체
                </span>
                {' · '}
                <span className="font-bold text-success">● 공실 매물</span>
              </p>
            </div>
          </div>
          <div className="h-14 bg-muted/90 backdrop-blur-md border border-border rounded-2xl flex justify-between items-center px-6 shrink-0">
            <h4 className="text-xs font-black text-foreground flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_10px_rgba(0,44,209,0.8)]" />
              Multi-Agent Geospatial Recommendations
            </h4>
            <p className="text-[0.625rem] text-muted-foreground font-mono tracking-widest">
              AI AGENT TARGETING · {locations.length} VACANCY · {competitors.length} COMP
            </p>
          </div>
          <div className="relative bg-secondary rounded-2xl overflow-hidden">
            <AgentMapVisualizer
              height="640px"
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
          businessType={businessType}
          dongStats={{
            floating_pop: r?.market_report?.floating_population ?? null,
            closure_rate: r?.closure_rate?.closure_rate ?? null,
          }}
        />
      )}
    </div>
  );
}
