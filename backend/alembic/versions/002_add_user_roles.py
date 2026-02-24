"""Add user roles and name fields

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role column (default 'admin' for existing users)
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="admin"))
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))

    # Migrate existing superadmins
    op.execute("UPDATE users SET role = 'superadmin' WHERE is_superadmin = true")

    op.create_index("idx_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("idx_users_role", "users")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "role")
