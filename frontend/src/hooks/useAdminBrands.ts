/**
 * 슈퍼어드민 brand 검색 hook.
 * - debounce 300ms
 * - AbortController 로 stale 요청 취소 (race condition 방지)
 * - 403 (role != superadmin) 시 forbidden=true 반환, error 비움
 */

import axios from 'axios';
import { useCallback, useEffect, useRef, useState } from 'react';
import { listAdminBrands } from '../api/client';
import type { AdminBrand, SupportedIndustry } from '../types/admin';

export interface UseAdminBrandsOptions {
  q?: string;
  industry?: string;
  page?: number;
  size?: number;
  enabled?: boolean;
  debounceMs?: number;
}

export interface UseAdminBrandsResult {
  items: AdminBrand[];
  total: number;
  supportedIndustries: SupportedIndustry[];
  loading: boolean;
  error: string | null;
  forbidden: boolean;
  refetch: () => void;
}

export function useAdminBrands({
  q,
  industry,
  page = 1,
  size = 50,
  enabled = true,
  debounceMs = 300,
}: UseAdminBrandsOptions): UseAdminBrandsResult {
  const [items, setItems] = useState<AdminBrand[]>([]);
  const [total, setTotal] = useState(0);
  const [supportedIndustries, setSupportedIndustries] = useState<SupportedIndustry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [refetchToken, setRefetchToken] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const refetch = useCallback(() => setRefetchToken((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) {
      setItems([]);
      setTotal(0);
      return;
    }

    const handle = window.setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      setError(null);
      setForbidden(false);

      listAdminBrands({ q: q?.trim() || undefined, industry, page, size })
        .then((res) => {
          if (controller.signal.aborted) return;
          setItems(res.items);
          setTotal(res.total);
          if (res.supported_industries?.length > 0) {
            setSupportedIndustries(res.supported_industries);
          }
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted || axios.isCancel(err)) return;
          if (axios.isAxiosError(err) && err.response?.status === 403) {
            setForbidden(true);
            setItems([]);
            setTotal(0);
            return;
          }
          setError(err instanceof Error ? err.message : '브랜드 조회 실패');
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, debounceMs);

    return () => {
      window.clearTimeout(handle);
      abortRef.current?.abort();
    };
  }, [q, industry, page, size, enabled, debounceMs, refetchToken]);

  return { items, total, supportedIndustries, loading, error, forbidden, refetch };
}
