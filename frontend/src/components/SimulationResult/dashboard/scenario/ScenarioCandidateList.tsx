/**
 * ScenarioCandidateList — Master-Detail 좌측 패널.
 *
 * - lg+ 280px width 세로 stack
 * - lg 미만 (mobile) horizontal scroll chip carousel
 * - [+] 후보 추가 버튼 → AddCandidateModal 오픈
 * - 6번째 추가 시 호출 측에서 토스트 ("비교 후보는 최대 5개까지")
 *
 * 강민 결정 분기 §1: 모바일 lg 미만 → horizontal scroll chip carousel.
 */

import { useState } from 'react';
import { Plus } from 'lucide-react';
import {
  MAX_CANDIDATES,
  type ScenarioCandidate,
  type UseScenarioCandidatesResult,
} from '../../../../hooks/useScenarioCandidates';
import type { ComparisonRecord } from '../../../../hooks/useElasticityComparison';
import { ScenarioCandidateCard } from './ScenarioCandidateCard';
import { AddCandidateModal } from './AddCandidateModal';
import { selectPerStoreBaseline } from './baseline';

interface Props {
  candidates: ScenarioCandidate[];
  activeId: string | null;
  records: Map<string, ComparisonRecord>;
  isFull: boolean;
  /** 시뮬 입력 동 list (4동 한정). 카드 dropdown / AddCandidateModal 옵션 source. */
  availableDongs: { name: string; code: string }[];
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  onAdd: UseScenarioCandidatesResult['addCandidate'];
  onChangeDong: UseScenarioCandidatesResult['updateCandidateDong'];
  onLimitReached: () => void;
}

export function ScenarioCandidateList({
  candidates,
  activeId,
  records,
  isFull,
  availableDongs,
  onSelect,
  onRemove,
  onAdd,
  onChangeDong,
  onLimitReached,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const noDongs = availableDongs.length === 0;
  const addDisabled = isFull || noDongs;

  const handleAddClick = () => {
    if (isFull) {
      onLimitReached();
      return;
    }
    if (noDongs) return;
    setModalOpen(true);
  };

  return (
    <>
      <aside
        aria-label="후보 비교 리스트"
        className="rounded-3xl border border-border bg-card p-4 lg:w-[280px] lg:flex-shrink-0"
      >
        <div className="flex items-center justify-between gap-2 pb-3">
          <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
            비교 후보 ({candidates.length}/{MAX_CANDIDATES})
          </h4>
          <button
            type="button"
            onClick={handleAddClick}
            aria-label="후보 추가"
            title={noDongs ? '시뮬 입력 동이 없어 추가할 수 없습니다' : undefined}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-[0.625rem] font-black text-foreground transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={addDisabled}
          >
            <Plus size={12} /> 추가
          </button>
        </div>

        {candidates.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-secondary/40 p-4 text-center">
            <p className="text-[0.625rem] font-bold text-muted-foreground">
              {noDongs ? '시뮬 입력이 필요합니다' : '[+] 후보를 추가해 시작'}
            </p>
          </div>
        ) : (
          <div
            className="
              flex gap-2 overflow-x-auto pb-1
              lg:flex-col lg:gap-2 lg:overflow-visible lg:pb-0
            "
            style={{ scrollSnapType: 'x mandatory' }}
          >
            {candidates.map((c) => {
              const rec = records.get(c.id);
              return (
                <div
                  key={c.id}
                  className="min-w-[180px] flex-shrink-0 lg:min-w-0"
                  style={{ scrollSnapAlign: 'start' }}
                >
                  <ScenarioCandidateCard
                    candidate={c}
                    active={c.id === activeId}
                    baseline={rec?.data ? selectPerStoreBaseline(rec.data) : null}
                    availableDongs={availableDongs}
                    onChangeDong={onChangeDong}
                    removeDisabled={candidates.length <= 1}
                    loading={rec?.loading ?? false}
                    error={rec?.error ?? null}
                    onClick={() => onSelect(c.id)}
                    onRemove={() => onRemove(c.id)}
                  />
                </div>
              );
            })}
          </div>
        )}
      </aside>

      {modalOpen && (
        <AddCandidateModal
          onClose={() => setModalOpen(false)}
          availableDongs={availableDongs}
          onAdd={(input) => {
            const ok = onAdd(input);
            setModalOpen(false);
            return ok;
          }}
        />
      )}
    </>
  );
}
