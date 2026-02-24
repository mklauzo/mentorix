"""Add embedding_api_key to tenants

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("embedding_api_key", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "embedding_api_key")
