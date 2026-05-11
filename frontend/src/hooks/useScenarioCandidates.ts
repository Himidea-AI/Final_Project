/**
 * useScenarioCandidates — TCN 시나리오 시뮬레이터 후보 N개(max 5) 관리 훅.
 *
 * 명세서 §4.4 Master-Detail UX:
 *   - 후보 = (id, dong, industry) + 후보별 슬라이더 상태 격리
 *   - 최대 5개. 6번째 추가 시 호출 측에서 토스트.
 *   - sessionStorage persist (key = "spotter_scenario_candidates"). 탭 단위 자연 리셋.
 *
 * API:
 *   addCandidate(dong, industry) → 새 후보 추가 + active 설정 (max 미만일 때만)
 *   removeCandidate(id) → 제거. active 였으면 첫 후보로 fallback
 *   setActiveCandidate(id) → 우측 detail 전환
 *   updateSliderValue(id, key, value) → 슬라이더 값 변경 (후보 격리 보존)
 *   resetCandidateSliders(id) → 해당 후보 슬라이더 0 리셋
 *
 * private mode (storage 접근 실패) 는 try/catch 로 ignore — 메모리만 동작.
 */

import { useCallback, useEffect, useState } from 'react';
import type { PctSliderKey, QuarterKey } from '../types/elasticity';

const STORAGE_KEY = 'spotter_scenario_candidates';
export const MAX_CANDIDATES = 5;

/** 후보별 슬라이더 상태 (5종 격리). */
export interface CandidateSliderState {
  vacancy_rate: number; // -30 ~ +30, step 10
  trend_score: number;
  cpi_index: number;
  opr_sale_mt_avg: number;
  quarter_num: QuarterKey; // categorical, 합산 제외
}

export interface ScenarioCandidate {
  id: string;
  dong: string; // 동 한국어 이름 (예: "망원1동")
  dongCode: string;
  industry: string; // 업종 한국어 (예: "한식")
  industryCode: string;
  sliders: CandidateSliderState;
}

const INITIAL_SLIDERS: CandidateSliderState = {
  vacancy_rate: 0,
  trend_score: 0,
  cpi_index: 0,
  opr_sale_mt_avg: 0,
  quarter_num: 'Q1',
};

const PCT_KEYS: ReadonlyArray<PctSliderKey> = [
  'vacancy_rate',
  'trend_score',
  'cpi_index',
  'opr_sale_mt_avg',
];

function isPctSliderKey(k: string): k is PctSliderKey {
  return (PCT_KEYS as readonly string[]).includes(k);
}

function loadFromStorage(): { candidates: ScenarioCandidate[]; activeId: string | null } {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) {
      return { candidates: [], activeId: null };
    }
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { candidates: [], activeId: null };
    const parsed = JSON.parse(raw) as {
      candidates?: ScenarioCandidate[];
      activeId?: string | null;
    };
    const list = Array.isArray(parsed.candidates) ? parsed.candidates : [];
    // 슬라이더 누락 보정 (구버전 schema 마이그레이션 안전망)
    const normalized = list.map<ScenarioCandidate>((c) => ({
      ...c,
      sliders: { ...INITIAL_SLIDERS, ...(c.sliders ?? {}) },
    }));
    const activeId =
      parsed.activeId && normalized.some((c) => c.id === parsed.activeId)
        ? parsed.activeId
        : (normalized[0]?.id ?? null);
    return { candidates: normalized, activeId };
  } catch {
    return { candidates: [], activeId: null };
  }
}

function saveToStorage(candidates: ScenarioCandidate[], activeId: string | null): void {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) return;
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ candidates, activeId }));
  } catch {
    /* private mode — ignore */
  }
}

function makeId(): string {
  return `cand-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export interface UseScenarioCandidatesResult {
  candidates: ScenarioCandidate[];
  activeId: string | null;
  activeCandidate: ScenarioCandidate | null;
  /** 최대치 도달 시 false 반환. */
  addCandidate: (input: {
    dong: string;
    dongCode: string;
    industry: string;
    industryCode: string;
  }) => boolean;
  removeCandidate: (id: string) => void;
  setActiveCandidate: (id: string) => void;
  updateSliderValue: (
    id: string,
    key: keyof CandidateSliderState,
    value: number | QuarterKey,
  ) => void;
  resetCandidateSliders: (id: string) => void;
  /**
   * 후보의 동 (이름 + 코드) 변경. 슬라이더 상태 유지.
   * dup (동+업종 중복) 시 변경하지 않고 false 반환.
   */
  updateCandidateDong: (id: string, dong: string, dongCode: string) => boolean;
  isFull: boolean;
}

export function useScenarioCandidates(): UseScenarioCandidatesResult {
  const [candidates, setCandidates] = useState<ScenarioCandidate[]>(
    () => loadFromStorage().candidates,
  );
  const [activeId, setActiveId] = useState<string | null>(() => loadFromStorage().activeId);

  // persist on change
  useEffect(() => {
    saveToStorage(candidates, activeId);
  }, [candidates, activeId]);

  const addCandidate: UseScenarioCandidatesResult['addCandidate'] = useCallback(
    ({ dong, dongCode, industry, industryCode }) => {
      let added = false;
      setCandidates((prev) => {
        if (prev.length >= MAX_CANDIDATES) return prev;
        // 중복 (동+업종) 방지 — 이미 있으면 active 만 갱신, 새로 만들지 않음
        const dup = prev.find((c) => c.dongCode === dongCode && c.industryCode === industryCode);
        if (dup) {
          setActiveId(dup.id);
          added = false;
          return prev;
        }
        const next: ScenarioCandidate = {
          id: makeId(),
          dong,
          dongCode,
          industry,
          industryCode,
          sliders: { ...INITIAL_SLIDERS },
        };
        added = true;
        setActiveId(next.id);
        return [...prev, next];
      });
      return added;
    },
    [],
  );

  const removeCandidate = useCallback((id: string) => {
    setCandidates((prev) => {
      const next = prev.filter((c) => c.id !== id);
      setActiveId((curr) => {
        if (curr !== id) return curr;
        return next[0]?.id ?? null;
      });
      return next;
    });
  }, []);

  const setActiveCandidate = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const updateSliderValue = useCallback<UseScenarioCandidatesResult['updateSliderValue']>(
    (id, key, value) => {
      setCandidates((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c;
          if (key === 'quarter_num') {
            return { ...c, sliders: { ...c.sliders, quarter_num: value as QuarterKey } };
          }
          if (!isPctSliderKey(key)) return c;
          const num = typeof value === 'number' ? value : 0;
          return { ...c, sliders: { ...c.sliders, [key]: num } };
        }),
      );
    },
    [],
  );

  const resetCandidateSliders = useCallback((id: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c.id === id ? { ...c, sliders: { ...INITIAL_SLIDERS } } : c)),
    );
  }, []);

  const updateCandidateDong = useCallback<UseScenarioCandidatesResult['updateCandidateDong']>(
    (id, dong, dongCode) => {
      let changed = false;
      setCandidates((prev) => {
        const target = prev.find((c) => c.id === id);
        if (!target) return prev;
        // 동/코드 동일 → no-op (성공 처리)
        if (target.dong === dong && target.dongCode === dongCode) {
          changed = true;
          return prev;
        }
        // dup 체크 — 같은 (동+업종) 페어가 다른 후보에 이미 존재하면 변경 거부
        const dup = prev.find(
          (c) => c.id !== id && c.dongCode === dongCode && c.industryCode === target.industryCode,
        );
        if (dup) {
          changed = false;
          return prev;
        }
        changed = true;
        return prev.map((c) => (c.id === id ? { ...c, dong, dongCode } : c));
      });
      return changed;
    },
    [],
  );

  const activeCandidate = candidates.find((c) => c.id === activeId) ?? null;
  const isFull = candidates.length >= MAX_CANDIDATES;

  return {
    candidates,
    activeId,
    activeCandidate,
    addCandidate,
    removeCandidate,
    setActiveCandidate,
    updateSliderValue,
    resetCandidateSliders,
    updateCandidateDong,
    isFull,
  };
}
