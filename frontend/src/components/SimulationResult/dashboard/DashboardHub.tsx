/**
 * DashboardHub — 시뮬 완료 진입점 (라우트 /dashboard).
 * 작은 헤더 (회사명 + 시뮬 일시 + 문서ID) + 3 HubCard 가로 배치.
 * mobile stack, lg 이상 가로 3등분.
 *
 * 2026-04-28 H7 — `onSelect` prop 추가 (옵셔널).
 *   - undefined: 기존 라우트 모드 (Link to /dashboard/predict 등). /dashboard 인덱스 라우트에서 사용.
 *   - 함수: in-page state 전환 모드 (button onClick). HistoryDashboardView 에서 사용.
 */

import { useNavigate } from 'react-router-dom';
import { ListChecks, Plus } from 'lucide-react';
import type { SimulationOutput } from '../../../types';
import { formatDocumentId } from '../../../types/simulationHistory';
import { useSimulationStore } from '../../../stores/simulationStore';
import { HubCard } from './HubCard';

export type HubView = 'predict' | 'analyze' | 'abm';

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  savedHistoryId?: number | null;
  /** 지정 시 카드 클릭 → onSelect(view) (button 모드). 미지정 시 Link 라우트 모드. */
  onSelect?: (view: HubView) => void;
  /** 헤더 우측 "분석 조건" 버튼 클릭 핸들러. 미지정 시 버튼 hide. */
  onShowConditions?: () => void;
}

const HUB_IMAGES = {
  predict:
    'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&auto=format&fit=crop&q=80',
  analyze: '/images/ai-agent.jpg',
  abm: '/images/abm.png',
};

/**
 * Backend short key → UI 풀 라벨 역매핑 (App.tsx:636 BUSINESS_TYPE_BACKEND_KEY 의 inverse).
 * store.params.business_type 이 backend key 형식("커피", "한식" 등)으로 저장되므로
 * 사용자에게 보이는 라벨로 다시 풀어서 표시.
 */
const BIZ_LABEL_MAP: Record<string, string> = {
  한식: '한식음식점',
  중식: '중식음식점',
  일식: '일식음식점',
  양식: '양식음식점',
  제과점: '제과점',
  패스트푸드: '패스트푸드점',
  치킨: '치킨전문점',
  분식: '분식전문점',
  호프: '호프-간이주점',
  커피: '커피-음료',
};

export function DashboardHub({
  simResult,
  brandName,
  savedHistoryId,
  onSelect,
  onShowConditions,
}: Props) {
  const navigate = useNavigate();
  const docId = formatDocumentId(savedHistoryId ?? null);
  const createdAt = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });

  // 시뮬 입력 컨텍스트 — store.params 가 SoT (사용자가 1~4동 선택 + 업종).
  // simResult 의 target_districts 는 기본 fallback (history 복원 등 store 비어있는 경로 대비).
  const params = useSimulationStore((s) => s.params);
  const targetDongs: string[] = (() => {
    const fromParams = params?.target_districts;
    if (fromParams && fromParams.length > 0) return fromParams;
    if (params?.target_district) return [params.target_district];
    if (simResult.target_districts && simResult.target_districts.length > 0)
      return simResult.target_districts;
    return simResult.target_district ? [simResult.target_district] : [];
  })();
  const bizKey = params?.business_type ?? '';
  const bizLabel = BIZ_LABEL_MAP[bizKey] ?? bizKey;

  // 슬라이스별 status — error 시 카드 비활성화 + 사용자 안내 + 재시도 hint.
  // running 시 카드 grayscale + spinner — 자동 활성화 안내.
  // ABM 은 별도 endpoint(/simulate-abm) 라 store 슬라이스 미연동 — 일단 활성 유지.
  const predictStatus = useSimulationStore((s) => s.prediction.status);
  const predictError = useSimulationStore((s) => s.prediction.error);
  const analyzeStatus = useSimulationStore((s) => s.analysis.status);
  const analyzeError = useSimulationStore((s) => s.analysis.error);

  const isPredictDisabled = predictStatus === 'error';
  const isAnalyzeDisabled = analyzeStatus === 'error';
  const isPredictLoading = predictStatus === 'running';
  const isAnalyzeLoading = analyzeStatus === 'running';
  // ABM gate — 사용자 피드백 (2026-05-06): AI 분석 'done' 일 때만 ABM 활성. idle/running/error 모두 비활성.
  // (이전엔 isAnalyzeDisabled 만 사용 → error 외 모든 상태에서 ABM clickable 이었음.)
  const isAbmDisabled = analyzeStatus !== 'done';
  const abmDisabledReason =
    analyzeStatus === 'error'
      ? (analyzeError ?? 'AI 분석 실패 — 재시도 후 ABM 가능')
      : analyzeStatus === 'running'
        ? 'AI 분석 진행 중 — 완료 후 ABM 가능'
        : analyzeStatus === 'idle'
          ? 'AI 분석 완료 후 ABM 가능'
          : undefined;

  // 새 시뮬 시작 — store.result 비우고 /simulator 진입.
  // mount-restore (App.tsx:1297-1308) 가 store.result null 보고 setReportState 호출 안 함 → input UI 정상 표시.
  const handleNewSimulation = () => {
    useSimulationStore.getState().dismissResult();
    navigate('/simulator');
  };

  // 시뮬 이력 저장 버튼은 hub 가 아닌 각 결과 페이지(예측/분석) 헤더로 분산.
  // IM3-259 분리 호출이라 두 슬라이스가 다른 시점 도착 — "내가 보던 결과 화면" 에 저장 버튼이
  // 있어야 UX 자연. 공통 컴포넌트: SaveSimulationActions (components/SimulationHistory/).

  return (
    <div className="mx-auto max-w-[1728px] px-8 pt-12 pb-12">
      {/* header height 는 우측 박스 (DOC ID + 새 시뮬 버튼) 자연 높이(~44px)에 의해 결정.
          좌측은 가로 레이아웃 (h1 + 동/업종 한 줄) 으로 자연 height ~35px → 우측보다 작아
          self-center 로 그 안에 가운데 정렬. 우측은 그대로 items-end (= header bottom). */}
      <header className="flex items-end justify-between gap-8">
        {/* 좌측 — h1 옆에 동·업종 chip 을 가로 배치. self-center 로 우측 박스 높이 안 가운데. */}
        <div className="flex min-w-0 items-center gap-5 self-center">
          <h1 className="shrink-0 truncate text-2xl font-black text-foreground tracking-tight">
            {brandName || '—'}
          </h1>
          {(targetDongs.length > 0 || bizLabel) && (
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              {/* 동 — 지역 의미. 1~4개 sub-tone separator 로 묶음. */}
              {targetDongs.length > 0 && (
                <span className="truncate text-xs font-medium text-muted-foreground">
                  {targetDongs.map((d, i) => (
                    <span key={d}>
                      {d}
                      {i < targetDongs.length - 1 && (
                        <span className="mx-1.5 text-border" aria-hidden>
                          ·
                        </span>
                      )}
                    </span>
                  ))}
                </span>
              )}
              {/* 동/업종 시각 분리 — 업종은 카테고리 의미라 별도 chip 으로 격리. */}
              {bizLabel && (
                <span className="inline-flex items-center rounded-md border border-border bg-secondary px-2 py-0.5 text-[0.6875rem] font-bold tracking-wider text-foreground/80">
                  {bizLabel}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-end gap-6">
          <div className="text-right">
            <div className="text-[0.6875rem] font-mono uppercase tracking-widest text-muted-foreground">
              {docId}
            </div>
            <div className="mt-1 text-[0.6875rem] font-mono text-muted-foreground">{createdAt}</div>
          </div>
          {onShowConditions && (
            <button
              type="button"
              onClick={onShowConditions}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold tracking-wider text-foreground transition-all duration-200 hover:bg-secondary hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <ListChecks className="h-4 w-4" strokeWidth={2.5} />
              분석 조건
            </button>
          )}
          <button
            type="button"
            onClick={handleNewSimulation}
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-2.5 text-sm font-bold tracking-wider text-primary-foreground shadow-md shadow-primary/20 transition-all duration-200 hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/30 hover:scale-[1.02] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <Plus className="h-4 w-4" strokeWidth={3} />새 시뮬레이션
          </button>
        </div>
      </header>

      {/* Result Modules introducer — 헤더와 3카드 그룹 사이 시각적 단절 + 다음 섹션 라벨링. */}
      <div className="mb-8 mt-10 flex items-center gap-4">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-border" />
        <span className="text-[0.625rem] font-mono uppercase tracking-[0.25em] text-muted-foreground">
          Result Modules
        </span>
        <div className="h-px flex-1 bg-gradient-to-l from-transparent via-border to-border" />
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('predict')}
            title="예측 결과"
            description="ML 기반 매출 · 재무 · 폐업 위험도 정량 예측"
            imgSrc={HUB_IMAGES.predict}
            imgAlt="데이터 차트 시각화"
            accent="predict"
            ctaLabel="예측 보기"
            disabled={isPredictDisabled}
            disabledReason={predictError ?? undefined}
            loading={isPredictLoading}
          />
        ) : (
          <HubCard
            to="/dashboard/predict"
            title="예측 결과"
            description="ML 기반 매출 · 재무 · 폐업 위험도 정량 예측"
            imgSrc={HUB_IMAGES.predict}
            imgAlt="데이터 차트 시각화"
            accent="predict"
            ctaLabel="예측 보기"
            disabled={isPredictDisabled}
            disabledReason={predictError ?? undefined}
            loading={isPredictLoading}
          />
        )}
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('analyze')}
            title="AI 분석"
            description="LLM 기반 상권 · 인구 · 법률 · 경쟁 정성 분석"
            imgSrc={HUB_IMAGES.analyze}
            imgAlt="도시 거리 풍경"
            accent="analyze"
            ctaLabel="분석 보기"
            disabled={isAnalyzeDisabled}
            disabledReason={analyzeError ?? undefined}
            loading={isAnalyzeLoading}
          />
        ) : (
          <HubCard
            to="/dashboard/analyze"
            title="AI 분석"
            description="LLM 기반 상권 · 인구 · 법률 · 경쟁 정성 분석"
            imgSrc={HUB_IMAGES.analyze}
            imgAlt="도시 거리 풍경"
            accent="analyze"
            ctaLabel="분석 보기"
            disabled={isAnalyzeDisabled}
            disabledReason={analyzeError ?? undefined}
            loading={isAnalyzeLoading}
          />
        )}
        {onSelect ? (
          <HubCard
            onClick={() => onSelect('abm')}
            title="ABM 시뮬레이터"
            description="5,000명 에이전트 행동 시뮬레이션 + 공실 평가"
            imgSrc={HUB_IMAGES.abm}
            imgAlt="사람들이 다니는 거리"
            accent="abm"
            ctaLabel="시뮬 실행"
            disabled={isAbmDisabled}
            disabledReason={abmDisabledReason}
            loading={isAnalyzeLoading}
          />
        ) : (
          <HubCard
            to="/dashboard/abm"
            title="ABM 시뮬레이터"
            description="5,000명 에이전트 행동 시뮬레이션 + 공실 평가"
            imgSrc={HUB_IMAGES.abm}
            imgAlt="사람들이 다니는 거리"
            accent="abm"
            ctaLabel="시뮬 실행"
            disabled={isAbmDisabled}
            disabledReason={abmDisabledReason}
            loading={isAnalyzeLoading}
          />
        )}
      </div>
    </div>
  );
}
