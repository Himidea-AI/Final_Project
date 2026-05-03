/**
 * useElasticityComparison — 후보 N개의 elasticity 응답을 병렬로 fetch.
 *
 * 입력: 후보 list (id + dongCode + industryCode).
 * 출력: Map<candidateId, SensitivityResponse | null>  + per-candidate error/loading.
 *
 * 구현:
 *   - candidates 의 (dongCode, industryCode) 페어를 의존성으로 effect 재실행.
 *   - Promise.allSettled 로 병렬 fetch — 한 후보 실패해도 나머지는 표시.
 *   - AbortController 로 prev request cancel.
 *   - 후보별 캐시 (Map by signature "dongCode__industryCode") — 동일 페어 중복 호출 회피.
 */

import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { fetchElasticity, ElasticityNotFoundError } from '../api/elasticity';
import type { SensitivityResponse } from '../types/elasticity';

export interface ComparisonRecord {
  data: SensitivityResponse | null;
  error: Error | null;
  loading: boolean;
}

interface CandidateInput {
  id: string;
  dongCode: string;
  industryCode: string;
}

export interface UseElasticityComparisonResult {
  /** id → ComparisonRecord. id 가 candidates 에 있으면 항상 record 존재. */
  records: Map<string, ComparisonRecord>;
  /** 모든 후보가 로딩 끝났는지. */
  allLoaded: boolean;
}

const sig = (dongCode: string, industryCode: string) => `${dongCode}__${industryCode}`;

export function useElasticityComparison(
  candidates: ReadonlyArray<CandidateInput>,
): UseElasticityComparisonResult {
  const [records, setRecords] = useState<Map<string, ComparisonRecord>>(() => new Map());
  // signature → response 캐시 (동일 dong+industry 재호출 회피)
  const cacheRef = useRef<Map<string, SensitivityResponse>>(new Map());

  // candidates 변경 감지 — id+signature 직렬화로 비교
  const candidatesKey = candidates
    .map((c) => `${c.id}:${sig(c.dongCode, c.industryCode)}`)
    .join('|');

  useEffect(() => {
    if (candidates.length === 0) {
      setRecords(new Map());
      return;
    }

    const controller = new AbortController();
    let cancelled = false;

    // 초기 state — 캐시 hit 면 즉시 data, miss 면 loading=true
    const initial = new Map<string, ComparisonRecord>();
    for (const c of candidates) {
      const cached = cacheRef.current.get(sig(c.dongCode, c.industryCode));
      if (cached) {
        initial.set(c.id, { data: cached, error: null, loading: false });
      } else {
        initial.set(c.id, { data: null, error: null, loading: true });
      }
    }
    setRecords(initial);

    const toFetch = candidates.filter(
      (c) => !cacheRef.current.has(sig(c.dongCode, c.industryCode)),
    );

    if (toFetch.length === 0) return () => controller.abort();

    Promise.allSettled(
      toFetch.map((c) =>
        fetchElasticity(c.dongCode, c.industryCode, controller.signal).then((res) => ({
          c,
          res,
        })),
      ),
    ).then((results) => {
      if (cancelled || controller.signal.aborted) return;
      setRecords((prev) => {
        const next = new Map(prev);
        results.forEach((r, idx) => {
          const c = toFetch[idx];
          if (r.status === 'fulfilled') {
            cacheRef.current.set(sig(c.dongCode, c.industryCode), r.value.res);
            next.set(c.id, { data: r.value.res, error: null, loading: false });
          } else {
            const reason = r.reason;
            if (axios.isCancel(reason)) return;
            const err =
              reason instanceof ElasticityNotFoundError
                ? reason
                : reason instanceof Error
                  ? reason
                  : new Error('elasticity 조회 실패');
            next.set(c.id, { data: null, error: err, loading: false });
          }
        });
        return next;
      });
    });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidatesKey]);

  const allLoaded =
    candidates.length === 0 || candidates.every((c) => records.get(c.id)?.loading === false);

  return { records, allLoaded };
}
