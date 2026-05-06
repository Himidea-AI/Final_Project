/**
 * PredictScenarioSimTab — TCN v3 시나리오 시뮬레이터 (Single-panel).
 *
 * 백엔드: GET /predict/sensitivity?dong_code=&industry_code=
 *   v3 schema: elasticity[slider][level] = number[] (4분기 시계열)
 *
 * 레이아웃 (2026-05-03 v2 — 우측 후보 list 제거 / 헤더 동 드롭다운 통합):
 *   - 단일 컬럼 ScenarioDetailPanel
 *   - 후보 list UI 폐기 (ScenarioCandidateList 컴포넌트 파일은 dead 보존)
 *   - 동 변경: ScenarioDetailPanel 헤더의 4동 드롭다운에서
 *     - 같은 동+업종 후보가 이미 있으면 그 후보로 active 전환
 *     - 없으면 active 후보의 dong/dongCode 변경 (updateCandidateDong)
 *   - 후보별 슬라이더 상태 격리 (sessionStorage persist)
 *   - 동 옵션 = 시뮬 입력 4동 한정 (target_districts → MAPO_DONGS 매핑)
 *
 * 회귀: simResult 없이도 진입 가능. winner_district + business_type 으로 자동 첫 후보 시드.
 *       target_districts 비어있으면 후보 시드/변경 불가.
 */

import { useEffect, useMemo, useRef } from 'react';
import { Sliders } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { useScenarioCandidates } from '../../../../../hooks/useScenarioCandidates';
import { useElasticityComparison } from '../../../../../hooks/useElasticityComparison';
import { ElasticityNotFoundError } from '../../../../../api/elasticity';
import { resolveBizToIndustry } from '../../../../../constants/bizToIndustry';
import { MAPO_DONGS, resolveDongCode } from '../../../../../constants/mapoDongs';
import { useSimulationStore } from '../../../../../stores/simulationStore';
import { useToastStore } from '../../../../../stores/toastStore';
import { ScenarioDetailPanel } from '../../scenario/ScenarioDetailPanel';

interface Props {
  simResult?: SimulationOutput | null;
}

/** target_districts (한국어 동 이름 list) → MAPO_DONGS 매핑. 16동 안 있는 것만. */
function buildAvailableDongs(targetDistricts: string[]): { name: string; code: string }[] {
  return targetDistricts
    .map((name) => MAPO_DONGS.find((d) => d.name === name) ?? null)
    .filter((d): d is { name: string; code: string } => d != null);
}

export function PredictScenarioSimTab({ simResult }: Props) {
  const businessType = useSimulationStore((s) => s.params?.business_type ?? null);
  const paramsTargetDistricts = useSimulationStore((s) => s.params?.target_districts ?? null);
  const industryCode = resolveBizToIndustry(businessType);

  // 시뮬 입력 동 우선, 없으면 응답의 target_districts fallback (history 복원 경로 안전)
  const availableDongs = useMemo(() => {
    const fromParams = paramsTargetDistricts ?? [];
    if (fromParams.length > 0) return buildAvailableDongs(fromParams);
    const fromResult = simResult?.target_districts ?? [];
    return buildAvailableDongs(fromResult);
  }, [paramsTargetDistricts, simResult]);

  const {
    candidates,
    activeId,
    activeCandidate,
    addCandidate,
    setActiveCandidate,
    updateSliderValue,
    resetCandidateSliders,
    updateCandidateDong,
  } = useScenarioCandidates();

  const pushToast = useToastStore((s) => s.push);

  // 첫 진입 자동 시드 — candidates 가 비어있고 simResult.winner_district + business_type 매핑되면
  // 한 번만 자동 추가. (사용자가 후보를 모두 지운 뒤엔 재시드 X — seedRef 로 가드.)
  // 시드 동은 availableDongs (시뮬 입력 4동) 안에 있어야 함. winner 우선, 없으면 첫 입력 동.
  const seedRef = useRef(false);
  useEffect(() => {
    if (seedRef.current) return;
    if (candidates.length > 0) {
      seedRef.current = true;
      return;
    }
    if (!businessType || !industryCode) return;
    if (availableDongs.length === 0) return;
    const winner = simResult?.winner_district ?? null;
    const dongName =
      winner && availableDongs.some((d) => d.name === winner) ? winner : availableDongs[0].name;
    const dongCode = resolveDongCode(dongName);
    if (!dongCode) return;
    addCandidate({
      dong: dongName,
      dongCode,
      industry: businessType,
      industryCode,
    });
    seedRef.current = true;
  }, [candidates.length, simResult, businessType, industryCode, availableDongs, addCandidate]);

  const { records } = useElasticityComparison(
    candidates.map((c) => ({
      id: c.id,
      dongCode: c.dongCode,
      industryCode: c.industryCode,
    })),
  );

  // 액티브 후보의 응답 (없으면 null)
  const activeRecord = activeId ? (records.get(activeId) ?? null) : null;

  // 후보별 에러 toast — 404 만 friendly 멘트
  // dedupe: 후보 id 별 last-error signature 기록 — records Map 이 새 인스턴스로 set 될 때마다
  // 동일 후보의 동일 에러가 N번 반복 push 되는 것을 차단.
  const lastErrorRef = useRef<Map<string, string>>(new Map());
  useEffect(() => {
    const seen = lastErrorRef.current;
    for (const [id, rec] of records) {
      const sig = rec.error ? `${rec.error.name}:${rec.error.message}` : '';
      if (seen.get(id) === sig) continue;
      seen.set(id, sig);
      if (!rec.error) continue;
      if (rec.error instanceof ElasticityNotFoundError) {
        pushToast({
          variant: 'error',
          title: '일시 오류, 다른 동 시도해주세요',
          dedupeKey: 'scenario-sim-error',
        });
      } else {
        pushToast({
          variant: 'error',
          title: '데이터 로드 실패',
          description: '잠시 후 다시 시도하세요.',
          dedupeKey: 'scenario-sim-error',
        });
      }
    }
    // 사라진 후보의 기록은 정리
    for (const id of Array.from(seen.keys())) {
      if (!records.has(id)) seen.delete(id);
    }
  }, [records, pushToast]);

  // 헤더 동 드롭다운 핸들러 — 같은 동+업종 후보가 이미 있으면 그 후보로 active 전환,
  // 없으면 active 후보의 dong 변경.
  function handleChangeDong(newDong: string) {
    if (!activeCandidate) return;
    const target = availableDongs.find((d) => d.name === newDong);
    if (!target) return;
    const existing = candidates.find(
      (c) => c.dong === newDong && c.industryCode === activeCandidate.industryCode,
    );
    if (existing) {
      setActiveCandidate(existing.id);
      return;
    }
    updateCandidateDong(activeCandidate.id, newDong, target.code);
  }

  const businessMissing = !industryCode;

  return (
    <div className="space-y-6">
      <header>
        <div className="flex flex-wrap items-start gap-4">
          <div>
            <h3 className="flex items-center gap-3 text-2xl font-black italic text-foreground">
              <Sliders className="text-primary" /> 시나리오 시뮬레이터
            </h3>
            <p className="mt-2 text-xs text-muted-foreground">
              What-if 시뮬 — 동 × 업종을 바꿔가며 슬라이더로 4분기 매출 변화를 실험
            </p>
            <p className="mt-1 text-[0.625rem] text-muted-foreground">
              점포당 분기 매출 (원) · *업종 평균 점포 1개 기준
            </p>
          </div>
        </div>
      </header>

      {businessMissing && (
        <div className="rounded-3xl border border-dashed border-border bg-secondary p-8 text-center">
          <Sliders size={32} className="mx-auto mb-3 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm font-bold text-foreground">업종 정보 필요</p>
          <p className="mt-2 text-[0.6875rem] text-muted-foreground">
            시뮬레이션 인풋(업종)을 먼저 입력해주세요.
          </p>
        </div>
      )}

      {!businessMissing &&
        (activeCandidate ? (
          <ScenarioDetailPanel
            candidate={activeCandidate}
            data={activeRecord?.data ?? null}
            loading={activeRecord?.loading ?? false}
            error={activeRecord?.error ?? null}
            onSliderChange={(key, value) => updateSliderValue(activeCandidate.id, key, value)}
            onReset={() => resetCandidateSliders(activeCandidate.id)}
            availableDongs={availableDongs}
            onChangeDong={handleChangeDong}
          />
        ) : (
          <section className="rounded-3xl border border-dashed border-border bg-secondary/40 p-12 text-center">
            <p className="text-sm font-bold text-foreground">시뮬 입력 필요</p>
            <p className="mt-2 text-[0.6875rem] text-muted-foreground">
              시뮬레이션 인풋(동 × 업종)을 먼저 입력하면 자동으로 시나리오가 시드됩니다.
            </p>
          </section>
        ))}
    </div>
  );
}
