/**
 * PredictScenarioSimTab — TCN v3 시나리오 시뮬레이터 (Master-Detail).
 *
 * 백엔드: GET /predict/sensitivity?dong_code=&industry_code=
 *   v3 schema: elasticity[slider][level] = number[] (4분기 시계열)
 *
 * 명세서 §4.4 Master-Detail UX:
 *   - 좌측 (lg+ 280px / lg- horizontal scroll chip): ScenarioCandidateList — 후보 N개 (max 5)
 *   - 우측 (lg+ flex-1):                            ScenarioDetailPanel — 액티브 후보 드릴다운
 *   - 후보별 슬라이더 상태 격리 (sessionStorage persist)
 *   - 16동 자유 비교 — target_districts 필터 X
 *
 * 강민 결정 분기 §1/§2/§3:
 *   §1 모바일 lg- → 좌측 후보 list horizontal scroll chip carousel
 *   §2 후보 추가 모달: DongDropdown 패턴 + 업종 dropdown, 16동 자유 비교
 *   §3 sessionStorage persist (key = "spotter_scenario_candidates")
 *
 * 회귀: simResult 없이도 진입 가능. winner_district + business_type 으로 자동 첫 후보 시드.
 */

import { useEffect, useRef } from 'react';
import { Sliders } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { useScenarioCandidates } from '../../../../../hooks/useScenarioCandidates';
import { useElasticityComparison } from '../../../../../hooks/useElasticityComparison';
import { ElasticityNotFoundError } from '../../../../../api/elasticity';
import { resolveBizToIndustry } from '../../../../../constants/bizToIndustry';
import { MAPO_DONGS, resolveDongCode } from '../../../../../constants/mapoDongs';
import { useSimulationStore } from '../../../../../stores/simulationStore';
import { useToastStore } from '../../../../../stores/toastStore';
import { ScenarioCandidateList } from '../../scenario/ScenarioCandidateList';
import { ScenarioDetailPanel } from '../../scenario/ScenarioDetailPanel';

interface Props {
  simResult?: SimulationOutput | null;
}

export function PredictScenarioSimTab({ simResult }: Props) {
  const businessType = useSimulationStore((s) => s.params?.business_type ?? null);
  const industryCode = resolveBizToIndustry(businessType);

  const {
    candidates,
    activeId,
    activeCandidate,
    addCandidate,
    removeCandidate,
    setActiveCandidate,
    updateSliderValue,
    resetCandidateSliders,
    isFull,
  } = useScenarioCandidates();

  const pushToast = useToastStore((s) => s.push);

  // 첫 진입 자동 시드 — candidates 가 비어있고 simResult.winner_district + business_type 매핑되면
  // 한 번만 자동 추가. (사용자가 후보를 모두 지운 뒤엔 재시드 X — seedRef 로 가드.)
  const seedRef = useRef(false);
  useEffect(() => {
    if (seedRef.current) return;
    if (candidates.length > 0) {
      seedRef.current = true;
      return;
    }
    if (!businessType || !industryCode) return;
    const winner = simResult?.winner_district ?? null;
    const dongName =
      winner && MAPO_DONGS.some((d) => d.name === winner) ? winner : MAPO_DONGS[0].name;
    const dongCode = resolveDongCode(dongName);
    if (!dongCode) return;
    addCandidate({
      dong: dongName,
      dongCode,
      industry: businessType,
      industryCode,
    });
    seedRef.current = true;
  }, [candidates.length, simResult, businessType, industryCode, addCandidate]);

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
        });
      } else {
        pushToast({
          variant: 'error',
          title: '데이터 로드 실패',
          description: '잠시 후 다시 시도하세요.',
        });
      }
    }
    // 사라진 후보의 기록은 정리
    for (const id of Array.from(seen.keys())) {
      if (!records.has(id)) seen.delete(id);
    }
  }, [records, pushToast]);

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
              What-if Master-Detail — 후보(동×업종)를 비교하고 슬라이더로 4분기 매출 시뮬
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

      {!businessMissing && (
        <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch">
          <ScenarioCandidateList
            candidates={candidates}
            activeId={activeId}
            records={records}
            isFull={isFull}
            onSelect={setActiveCandidate}
            onRemove={removeCandidate}
            onAdd={addCandidate}
            onLimitReached={() =>
              pushToast({
                variant: 'info',
                title: '비교 후보는 최대 5개까지',
              })
            }
          />

          {activeCandidate ? (
            <ScenarioDetailPanel
              candidate={activeCandidate}
              data={activeRecord?.data ?? null}
              loading={activeRecord?.loading ?? false}
              error={activeRecord?.error ?? null}
              onSliderChange={(key, value) => updateSliderValue(activeCandidate.id, key, value)}
              onReset={() => resetCandidateSliders(activeCandidate.id)}
            />
          ) : (
            <section className="flex-1 rounded-3xl border border-dashed border-border bg-secondary/40 p-12 text-center">
              <p className="text-sm font-bold text-foreground">[+] 후보를 추가해 시작</p>
              <p className="mt-2 text-[0.6875rem] text-muted-foreground">
                동 × 업종 페어를 추가해 4분기 매출 시뮬을 비교하세요. 최대 5개.
              </p>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
