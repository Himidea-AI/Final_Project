import type { SimulationOutput } from './index';

export type MarketEntrySignal = 'green' | 'yellow' | 'red';
export type HistorySort = 'created_at_desc' | 'client_name_asc';
/**
 * 시뮬 슬라이스 종류 — DB 분리 후 양 테이블(simulation_foresee/simulation_ai) 에서 온 row.
 * - 'foresee' : ML 예측 (Predict 탭)  → /simulation-foresee
 * - 'ai'      : LLM 분석 (Analyze 탭) → /simulation-ai
 * - null      : legacy /simulation-history (마이그레이션 대상, 읽기 전용 유지)
 */
export type SimulationKind = 'foresee' | 'ai';

export interface SimulationHistoryItem {
  id: number;
  manager_id: string; // backend SimulationHistoryListItem.manager_id 와 동기화 — frontend HistoryCard 본인/타인 분기용
  manager_name?: string | null; // master 시 "by 매니저명" 표시용. 본인 시뮬은 null
  client_name: string;
  district: string;
  brand_name: string;
  business_type: string | null;
  ai_verdict_summary: string | null;
  market_entry_signal: MarketEntrySignal | null;
  created_at: string;
  /** 통합 history list 에서 row 가 어느 테이블 출처인지 식별. 머지 후 client-side 분기. */
  kind: SimulationKind;
}

export interface SimulationHistoryDetail extends SimulationHistoryItem {
  scenario: Record<string, unknown> | null;
  simulation_result: SimulationOutput;
  updated_at: string | null;
}

/** @deprecated — DB 분리(2026-05-02) 이전 통합 simulation_history 페이로드. SaveForeseePayload/SaveAIPayload 로 마이그레이션. */
export interface SaveSimulationPayload {
  client_name: string;
  district: string;
  brand_name: string;
  business_type?: string | null;
  scenario?: Record<string, unknown> | null;
  simulation_result: SimulationOutput;
  ai_verdict_summary?: string | null;
  market_entry_signal?: MarketEntrySignal | null;
}

/**
 * POST /simulation-foresee body — backend ForeseeSaveRequest 와 1:1.
 * foresee_result 는 SimulationOutput 의 ML 슬라이스 키들만 picking (helper: pickForeseeResult).
 */
export interface SaveForeseePayload {
  client_name: string;
  brand_name: string;
  business_type?: string | null;
  districts?: string[] | null;
  target_district?: string | null;
  winner_district?: string | null;
  foresee_result: Record<string, unknown>;
  /** 원본 SimulationInput. DB 컬럼 추가 후 활성. 현재는 backend pydantic 만 수용 + INSERT 무시. */
  scenario?: Record<string, unknown> | null;
}

/**
 * POST /simulation-ai body — backend AISaveRequest 와 1:1.
 * ai_result 는 SimulationOutput 의 LLM 슬라이스 키들만 picking (helper: pickAIResult).
 */
export interface SaveAIPayload {
  client_name: string;
  brand_name: string;
  business_type?: string | null;
  target_district?: string | null;
  winner_district?: string | null;
  ai_result: Record<string, unknown>;
  /** 원본 SimulationInput. DB 컬럼 추가 후 활성. */
  scenario?: Record<string, unknown> | null;
}

export interface SaveSimulationResponse {
  id: number;
  manager_id: string;
  client_name: string;
  created_at: string;
}

export interface HistoryFilterParams {
  client_name?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  size?: number;
  sort?: HistorySort;
}

export interface HistoryListResponse {
  total: number;
  page: number;
  size: number;
  items: SimulationHistoryItem[];
}

// savedId null → 저장 전 임시번호(DRAFT). savedId 있으면 발행번호(6자리 zero-pad).
export function formatDocumentId(savedId: number | null | undefined): string {
  if (savedId == null) {
    const stamp = Date.now().toString().slice(-8);
    return `SPTR-DRAFT-${stamp}`;
  }
  return `SPTR-${String(savedId).padStart(6, '0')}`;
}
