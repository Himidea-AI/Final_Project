/**
 * Elasticity API — TCN 시나리오 시뮬레이터.
 *
 * 엔드포인트: GET /predict/sensitivity?dong_code=&industry_code=
 *
 * 응답 헤더: ETag + Cache-Control: public, must-revalidate (브라우저 자동 처리, axios 기본값 그대로).
 *
 * 404: { detail: "탄성치 데이터 없음: {dong}_{industry}. 배치 스크립트를 먼저 실행하세요." }
 *      → ElasticityNotFoundError 로 throw.
 */

import axios from 'axios';
import apiClient from './client';
import type { SensitivityResponse } from '../types/elasticity';

export class ElasticityNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ElasticityNotFoundError';
  }
}

export async function fetchElasticity(
  dongCode: string,
  industryCode: string,
  signal?: AbortSignal,
): Promise<SensitivityResponse> {
  try {
    const response = await apiClient.get<SensitivityResponse>('/predict/sensitivity', {
      params: { dong_code: dongCode, industry_code: industryCode },
      signal,
    });
    return response.data;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      const detail =
        (err.response.data as { detail?: string } | undefined)?.detail ?? '탄성치 데이터 없음';
      throw new ElasticityNotFoundError(detail);
    }
    throw err instanceof Error ? err : new Error('elasticity 조회 실패');
  }
}
