"""시뮬레이션 이력 Pydantic 스키마 — API 계약.

프론트 타입(``frontend/src/types/simulationHistory.ts``)과 1:1 매칭.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


MarketEntrySignal = Literal["green", "yellow", "red"]
SortKey = Literal["created_at_desc", "client_name_asc"]


class SimulationHistoryCreate(BaseModel):
    """POST 요청 바디."""

    client_name: str = Field(..., min_length=1, max_length=100)
    district: str = Field(..., min_length=1, max_length=50)
    brand_name: str = Field(..., min_length=1, max_length=100)
    business_type: Optional[str] = Field(default=None, max_length=50)
    scenario: Optional[dict[str, Any]] = None
    simulation_result: dict[str, Any]
    ai_verdict_summary: Optional[str] = None
    market_entry_signal: Optional[MarketEntrySignal] = None


class SimulationHistoryListItem(BaseModel):
    """목록 응답 원소 — 전체 simulation_result 제외 (lazy load)."""

    id: int
    manager_id: UUID  # frontend에서 본인/타인 시뮬 카드 분기용
    manager_name: Optional[str] = None  # master 시 "by 매니저명" 표시용. None이면 본인 시뮬
    client_name: str
    district: str
    brand_name: str
    business_type: Optional[str] = None
    ai_verdict_summary: Optional[str] = None
    market_entry_signal: Optional[MarketEntrySignal] = None
    created_at: datetime


class SimulationHistoryDetail(SimulationHistoryListItem):
    """단일 조회 — scenario/simulation_result 포함."""

    scenario: Optional[dict[str, Any]] = None
    simulation_result: dict[str, Any]
    updated_at: Optional[datetime] = None


class SimulationHistoryListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[SimulationHistoryListItem]


class SimulationHistoryCreateResponse(BaseModel):
    id: int
    manager_id: UUID
    client_name: str
    created_at: datetime
