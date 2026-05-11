"""add simulation_foresee and simulation_ai tables

Revision ID: 1ea09aac2adb
Revises: bfd610a9aa07
Create Date: 2026-05-01 19:28:25.718557

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "1ea09aac2adb"
down_revision: Union[str, Sequence[str], None] = "bfd610a9aa07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_foresee",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("manager_id", UUID(as_uuid=True), nullable=False, comment="작성자 ID"),
        sa.Column("user_type", sa.String(10), server_default="manager", comment="master | manager"),
        sa.Column("client_name", sa.String(100), nullable=False, comment="예비 가맹점주 이름"),
        sa.Column("brand_name", sa.String(100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(50), comment="업종"),
        sa.Column("districts", JSONB, comment="선택 동 목록"),
        sa.Column("target_district", sa.String(50), comment="대상 동"),
        sa.Column("winner_district", sa.String(50), comment="1순위 추천 동"),
        sa.Column("district_predictions", JSONB, comment="동별 ML 예측 전체"),
        sa.Column("quarterly_projection", JSONB, comment="분기 매출 예측"),
        sa.Column("scenarios", JSONB, comment="낙관/기본/비관 시나리오"),
        sa.Column("shap_result", JSONB, comment="SHAP 피처 기여도"),
        sa.Column("bep_months", sa.Integer, comment="BEP 도달 개월수"),
        sa.Column("predicted_monthly_revenue", sa.BigInteger, comment="예측 월매출"),
        sa.Column("closure_rate", JSONB, comment="폐업률"),
        sa.Column("closure_risk", JSONB, comment="폐업위험도"),
        sa.Column("final_report", JSONB, comment="수익성 시뮬"),
        sa.Column("market_report", JSONB, comment="7개 지표"),
        sa.Column("customer_segment", JSONB, comment="고객 세그먼트"),
        sa.Column("living_pop_forecast", JSONB, comment="유동인구 예측"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="담당: 봉환 | 예측 결과 이력 (Predict 탭) | ML 매출/재무/고객/신흥상권",
    )
    op.create_index("idx_foresee_manager_created", "simulation_foresee", ["manager_id", "created_at"])

    op.create_table(
        "simulation_ai",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("manager_id", UUID(as_uuid=True), nullable=False, comment="작성자 ID"),
        sa.Column("user_type", sa.String(10), server_default="manager", comment="master | manager"),
        sa.Column("client_name", sa.String(100), nullable=False, comment="예비 가맹점주 이름"),
        sa.Column("brand_name", sa.String(100), nullable=False, comment="브랜드명"),
        sa.Column("business_type", sa.String(50), comment="업종"),
        sa.Column("target_district", sa.String(50), comment="대상 동"),
        sa.Column("winner_district", sa.String(50), comment="1순위 추천 동"),
        sa.Column("top_3_candidates", JSONB, comment="상위 3동"),
        sa.Column("analysis_report", sa.Text, comment="synthesis 종합 리포트"),
        sa.Column("ai_recommendation", sa.Text, comment="최종 권고"),
        sa.Column("ai_verdict_summary", sa.Text, comment="한 줄 판단 요약"),
        sa.Column("market_entry_signal", sa.String(10), comment="green | yellow | red"),
        sa.Column("overall_legal_risk", sa.String(10), comment="safe | caution | danger"),
        sa.Column("legal_risks", JSONB, comment="14개 법률 리스크"),
        sa.Column("market_report", JSONB, comment="7개 정규화 지표"),
        sa.Column("trend_forecast", JSONB, comment="트렌드 전망"),
        sa.Column("competitor_intel", JSONB, comment="경쟁사 분석"),
        sa.Column("demographic_report", JSONB, comment="인구통계 심화"),
        sa.Column("district_rankings", JSONB, comment="16동 랭킹"),
        sa.Column("agent_attributions", JSONB, comment="에이전트별 판단 근거"),
        sa.Column("vacancy_applied", sa.Boolean, server_default="false", comment="공실 페널티 반영"),
        sa.Column("all_competitor_locations", JSONB, comment="경쟁점포 좌표 목록"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="담당: 봉환 | AI 분석 이력 (Analyze 탭) | LLM 상권/법률/인구/트렌드/경쟁",
    )
    op.create_index("idx_ai_manager_created", "simulation_ai", ["manager_id", "created_at"])


def downgrade() -> None:
    op.drop_table("simulation_ai")
    op.drop_table("simulation_foresee")
