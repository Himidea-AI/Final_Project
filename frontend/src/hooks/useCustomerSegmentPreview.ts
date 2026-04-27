import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { fetchCustomerSegment, type CustomerSegmentRequest } from '../api/client';
import type { CustomerSegment } from '../types';

interface State {
  data: CustomerSegment | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * 타겟 5필드 입력 변경 시 자동으로 customer_segment 미리보기 호출.
 * - 500ms debounce (입력 안정화 기다림)
 * - AbortController로 이전 요청 자동 cancel
 * - req=null 또는 4 타겟 필드 모두 비면 호출 안 함 (전체 고객 = 의미 없음)
 */
export function useCustomerSegmentPreview(req: CustomerSegmentRequest | null): State {
  const [state, setState] = useState<State>({ data: null, isLoading: false, error: null });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // 이전 요청 취소
    if (abortRef.current) abortRef.current.abort();

    if (!req) {
      setState({ data: null, isLoading: false, error: null });
      return;
    }

    // 4 타겟 필드 모두 비면 호출 안 함 (전체 고객 = 의미 없음)
    const hasProfile =
      (req.target_age_groups?.length ?? 0) > 0 ||
      req.target_gender !== null ||
      (req.target_time_slots?.length ?? 0) > 0 ||
      req.target_day_type !== null;
    if (!hasProfile) {
      setState({ data: null, isLoading: false, error: null });
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setState((s) => ({ ...s, isLoading: true, error: null }));

    const debounceTimer = setTimeout(() => {
      fetchCustomerSegment(req, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) {
            setState({ data, isLoading: false, error: null });
          }
        })
        .catch((err) => {
          if (axios.isCancel(err) || controller.signal.aborted) return;
          const detail = (err.response?.data as { detail?: string })?.detail;
          setState({
            data: null,
            isLoading: false,
            error: detail ?? (err instanceof Error ? err.message : '미리보기 실패'),
          });
        });
    }, 500);

    return () => {
      clearTimeout(debounceTimer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    req?.target_district,
    req?.business_type,
    req?.target_age_groups?.join(','),
    req?.target_gender,
    req?.target_time_slots?.join(','),
    req?.target_day_type,
    req?.target_monthly_sales,
    req?.quarter_num,
  ]);

  return state;
}
