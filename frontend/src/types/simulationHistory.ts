import type { SimulationOutput } from './index';

export type MarketEntrySignal = 'green' | 'yellow' | 'red';
export type HistorySort = 'created_at_desc' | 'client_name_asc';

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
}

export interface SimulationHistoryDetail extends SimulationHistoryItem {
  scenario: Record<string, unknown> | null;
  simulation_result: SimulationOutput;
  updated_at: string | null;
}

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
