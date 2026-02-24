"""Add embedding_model column to tenants

Revision ID: 006
Revises: 005
Create Date: 2024-01-06 00:00:00.000000

Allows per-tenant selection of embedding model:
- ollama:nomic-embed-text (default, free, local)
- ollama:mxbai-embed-large (higher quality, local)
- openai (text-embedding-3-small, 768-dim, requires sk-... key)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "embedding_model",
            sa.String(100),
            nullable=False,
            server_default="ollama:nomic-embed-text",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "embedding_model")
