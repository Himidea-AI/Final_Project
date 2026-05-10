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
import { useSimulationStore } from '../../../../stores/simulationStore';
import { SaveSimulationActions } from '../../../SimulationHistory/SaveSimulationActions';

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
  /** 시뮬 일수 — scenario panel 에서 1/3/7 선택 (default 1). */
  days?: number;
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

  // ABM 시뮬 영구 저장 — store.savedAbmId 가 있으면 저장됨 표시.
  const savedAbmId = useSimulationStore((s) => s.savedAbmId);
  // 저장 버튼은 result 가 있고 진행 중이 아닐 때만 활성.
  const canSaveAbm = abmResult != null && abmStatus !== 'running';
  // active params (abmStore.params) 우선, 없으면 displayResult 의 params (loadHistory 시).
  const abmParams = useAbmStore((s) => s.params);
  const abmScenarioParams = abmParams?.scenario ?? null;

  // mount 시 persist 복원된 running jobId 가 있으면 polling 재개.
  useEffect(() => {
    resumePollingIfNeeded();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 사용자 피드백 (2026-05-06): AbmFloatingWidget "ABM 결과로 이동" 클릭 시 spot select
  // 화면이 아니라 선택 spot + 시나리오 페이지로 가야 함. abmStatus / focusSpot 변경 시
  // 자동으로 mode='abm' 전환 (이전엔 mount 시 1회만 → 위젯 click 후 재진입 시 안 먹힘).
  useEffect(() => {
    if ((abmStatus === 'running' || abmStatus === 'done') && focusSpot) {
      setMode('abm');
    }
  }, [abmStatus, focusSpot]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = simResult as any;
  const targetDistrict =
    r?.winner_district || r?.target_district || r?.target_districts?.[0] || '서교동';

  // 지도 마커 데이터 — 상권분석 MapSection.buildBestVacancies 와 동일 로직:
  // winner 동 spot (score 정렬) + 부족분 top3 동 spot 으로 채움 (listing_count 정렬) + 50m dedup.
  // 사용자 피드백 (2026-05-06): 이전엔 winner 만 filter 라 AI 추천 화면과 spot 달랐음 →
  // top3 fallback 추가로 두 화면 일치.
  const winner: string | undefined = r?.winner_district || r?.target_district;
  const recommendedSpots = Array.isArray(r?.recommended_vacancy_spots)
    ? r.recommended_vacancy_spots.slice(0, 4)
    : [];
  const top3List: string[] = Array.isArray(r?.top_3_candidates)
    ? r.top_3_candidates.filter((d: unknown): d is string => typeof d === 'string')
    : [];
  const allVacancySpots = Array.isArray(r?.vacancy_spots) ? r.vacancy_spots : [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const validVacancy = allVacancySpots.filter(
    (s: any) =>
      typeof s.lat === 'number' &&
      typeof s.lon === 'number' &&
      Number.isFinite(s.lat) &&
      Number.isFinite(s.lon),
  );
  // 1) winner 동 spot — score 우선
  const winnerSorted = validVacancy
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((s: any) => s.dong_name === winner)
    .slice()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .sort((a: any, b: any) => {
      const sa = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY;
      const sb = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY;
      if (sa !== sb) return sb - sa;
      return (b.listing_count ?? 0) - (a.listing_count ?? 0);
    });
  // 2) top3 동 spot (winner 제외) — listing_count 정렬
  const top3Set = new Set(top3List);
  const top3Sorted = validVacancy
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((s: any) => top3Set.has(String(s.dong_name)) && s.dong_name !== winner)
    .slice()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .sort((a: any, b: any) => (b.listing_count ?? 0) - (a.listing_count ?? 0));
  // 3) merge + 50m dedup
  const merged = [...winnerSorted, ...top3Sorted];
  const haversineM = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const R = 6_371_000;
    const toRad = (d: number) => (d * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const dedupedTop4: any[] = [];
  for (const cand of merged) {
    const tooClose = dedupedTop4.some(
      (k) => haversineM(k.lat, k.lon ?? k.lng, cand.lat, cand.lon ?? cand.lng) <= 50,
    );
    if (!tooClose) dedupedTop4.push(cand);
    if (dedupedTop4.length >= 4) break;
  }
  const winnerVacancySpots = dedupedTop4;
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
      days: params.scenario.days ?? 1,
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
  // 사용자 피드백 (2026-05-10): 새 스팟 선택 시 직전 저장 ID 도 초기화 → 새 시뮬 별도로 저장 가능.
  const handleAgentMapSpotClick = async (loc: { lat: number; lng: number; name: string }) => {
    setMode('abm');
    setFocusSpot({ lat: loc.lat, lon: loc.lng, label: loc.name });
    clearDisplayResult();
    useSimulationStore.getState().setSavedAbmId(null);
    if (abmStatus === 'done' || abmStatus === 'error') dismissResult();
  };

  const handleAbmSpotClick = async (spot: { lat: number; lon: number; dong_name: string }) => {
    setFocusSpot({ lat: spot.lat, lon: spot.lon, label: spot.dong_name });
    clearDisplayResult();
    useSimulationStore.getState().setSavedAbmId(null);
    if (abmStatus === 'done' || abmStatus === 'error') dismissResult();
  };

  // 시나리오 패널 "시뮬 실행" 버튼 — focusSpot 좌표 + scenario 로 enqueueAbm.
  const handleRunSimulation = async (scenario: AbmScenario) => {
    // 새 시뮬 시작 시 직전 저장 ID 초기화 — 새 결과는 새로 저장 가능해야 함.
    useSimulationStore.getState().setSavedAbmId(null);
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
    useSimulationStore.getState().setSavedAbmId(null);
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
        <div className="flex items-center gap-3">
          {/* ABM 시뮬 결과가 있으면 저장 버튼 노출. 진행 중이면 disabled. */}
          {canSaveAbm && (
            <SaveSimulationActions
              simResult={simResult}
              brandName={brandName ?? ''}
              kind="abm"
              savedHistoryId={savedAbmId}
              abmContext={{
                abmResult,
                spotLat: focusSpot?.lat ?? null,
                spotLon: focusSpot?.lon ?? null,
                scenario: abmScenarioParams as Record<string, unknown> | null,
                nAgents: abmParams?.n_agents ?? 5000,
                days: abmParams?.days ?? 1,
                targetDistrict: focusSpot?.label ?? targetDistrict ?? null,
              }}
            />
          )}
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
          {/* 시뮬레이션 안내 — 첫 진입 시 컨텍스트. 사용자 피드백 (2026-05-05).
              초심자 친화 재구성 (2026-05-03): "ABM이 뭐지?" 문답 + 3단계 사용법 + 출력 설명 + 범례. */}
          <div className="rounded-2xl border border-primary/25 bg-primary/[0.04] px-4 py-3.5 flex flex-col gap-2.5">
            <div className="flex items-start gap-3">
              <div className="shrink-0 w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center">
                <Radar size={14} className="text-primary" />
              </div>
              <div className="flex flex-col gap-1 min-w-0">
                <p className="text-[12px] font-black text-foreground tracking-tight leading-tight">
                  ABM 시뮬레이터 — "이 자리에 매장 열면 하루에 얼마 팔릴까?"
                </p>
                <p className="text-[11px] text-muted-foreground leading-snug tracking-tight">
                  마포에 사는 가상 시민{' '}
                  <span className="font-bold text-foreground">5,000명(페르소나)</span>이 실제처럼
                  돌아다니며 점심·저녁을 사 먹습니다. 후보 공실에 매장을 차렸다고 가정하면 누가
                  들르는지, 하루 매출은 얼마인지, 근처 자사 매장 매출이 얼마나 줄어드는지(잠식)를
                  계산해줍니다.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-1">
              <div className="rounded-xl bg-card border border-border/60 px-3 py-2 flex flex-col gap-0.5">
                <span className="text-[9px] font-mono font-black text-primary tracking-widest">
                  STEP 1
                </span>
                <span className="text-[11px] font-bold text-foreground leading-tight">
                  공실 클릭
                </span>
                <span className="text-[10px] text-muted-foreground leading-snug">
                  지도에서 초록 점(임대 가능 매물) 하나 선택
                </span>
              </div>
              <div className="rounded-xl bg-card border border-border/60 px-3 py-2 flex flex-col gap-0.5">
                <span className="text-[9px] font-mono font-black text-primary tracking-widest">
                  STEP 2
                </span>
                <span className="text-[11px] font-bold text-foreground leading-tight">
                  조건 설정
                </span>
                <span className="text-[10px] text-muted-foreground leading-snug">
                  날씨·요일·임대료 시나리오 입력 후 "시뮬 실행"
                </span>
              </div>
              <div className="rounded-xl bg-card border border-border/60 px-3 py-2 flex flex-col gap-0.5">
                <span className="text-[9px] font-mono font-black text-primary tracking-widest">
                  STEP 3
                </span>
                <span className="text-[11px] font-bold text-foreground leading-tight">
                  결과 확인
                </span>
                <span className="text-[10px] text-muted-foreground leading-snug">
                  방문객·매출·자사 잠식률 (1~2분 소요)
                </span>
              </div>
            </div>

            <p className="text-[10px] text-muted-foreground/80 leading-snug pt-0.5 border-t border-border/40">
              <span className="font-bold text-muted-foreground">지도 범례 ─ </span>
              <span className="font-bold" style={{ color: 'var(--decor-cyan)' }}>
                ● 공실 매물
              </span>
              <span className="text-muted-foreground/60"> (클릭 가능)</span>
              {' · '}
              <span className="font-bold" style={{ color: '#fb565b' }}>
                ▲ 자사 매장
              </span>
              {' · '}
              <span className="font-bold" style={{ color: '#ffba00' }}>
                ▲ 경쟁업체
              </span>
              <span className="text-muted-foreground/60">
                {' '}
                · 여러 곳 시뮬 시 우하단 큐 패널 확인
              </span>
            </p>
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
