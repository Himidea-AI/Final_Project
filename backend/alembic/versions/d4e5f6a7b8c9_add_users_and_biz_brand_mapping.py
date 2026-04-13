"""add users and biz_brand_mapping tables

Revision ID: d4e5f6a7b8c9
Revises: c3c01b64fb39
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Union, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3c01b64fb39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('company_name', sa.String(100), nullable=False),
        sa.Column('biz_number', sa.String(12), unique=True, nullable=False),
        sa.Column('contact_name', sa.String(50), nullable=False),
        sa.Column('position', sa.String(50), nullable=True),
        sa.Column('email', sa.String(100), unique=True, nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('store_count', sa.Integer(), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('plan', sa.String(20), server_default='starter'),
        sa.Column('agree_terms', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'biz_brand_mapping',
        sa.Column('biz_number', sa.String(12), primary_key=True),
        sa.Column('company_name', sa.String(100), nullable=False),
        sa.Column('brand_name', sa.String(100), nullable=True),
        sa.Column('industry_large', sa.String(50), nullable=True),
        sa.Column('industry_medium', sa.String(50), nullable=True),
        sa.Column('franchise_count', sa.Integer(), nullable=True),
        sa.Column('avg_sales', sa.BigInteger(), nullable=True),
        sa.Column('mapo_store_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    op.drop_table('biz_brand_mapping')
