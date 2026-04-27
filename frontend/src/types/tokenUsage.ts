/**
 * Token Usage / Burn-rate 타입.
 *
 * 백엔드 엔드포인트 계약 (B1 예진 구현 대기):
 *   GET /api/ops/token-usage?from=YYYY-MM-DD&to=YYYY-MM-DD
 *   - JWT Bearer 필수 (master 이상)
 *   - LangSmith Run API(settings.langchain_api_key) 조회 후 집계해서 반환
 *   - runs의 metadata.manager_id 필드로 매니저별 breakdown 집계
 *   - 예상 구현 위치: backend/src/api/ops.py (신규) → main.py에서 라우터 등록
 *
 * 스키마가 backend 구현 전이므로 프론트는 404/500 시 empty state로 렌더.
 */

export interface TokenUsagePeriod {
  from: string; // ISO date (YYYY-MM-DD)
  to: string;
}

export interface TokenUsageDaily {
  date: string; // YYYY-MM-DD
  tokens: number;
  cost_usd: number;
  run_count: number;
}

export interface TokenUsageByManager {
  manager_id: string;
  manager_name: string | null;
  tokens: number;
  cost_usd: number;
  run_count: number;
}

export interface TokenUsageByModel {
  model: string; // e.g. "claude-opus-4-7", "claude-sonnet-4-6"
  tokens: number;
  cost_usd: number;
  run_count: number;
}

export interface TokenUsageResponse {
  period: TokenUsagePeriod;
  total_tokens: number;
  total_cost_usd: number;
  total_runs: number;
  daily: TokenUsageDaily[];
  by_manager: TokenUsageByManager[];
  by_model: TokenUsageByModel[];
  /** LangSmith 프로젝트 이름 — settings.langchain_project */
  langsmith_project?: string | null;
  /** 데이터 최신화 시각 */
  fetched_at: string; // ISO datetime
}
