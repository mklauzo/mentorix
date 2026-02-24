"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from alembic import op
import sqlalchemy.dialects.postgresql as pg

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── tenants ──────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_blocked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("blocked_reason", sa.Text, nullable=True),
        # LLM config
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("welcome_message", sa.Text, nullable=False, server_default="Cześć! Jak mogę Ci pomóc? 👋"),
        # Branding
        sa.Column("chat_title", sa.String(255), nullable=False, server_default="AI Assistant"),
        sa.Column("chat_color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("chat_logo_url", sa.Text, nullable=True),
        # Token limits
        sa.Column("monthly_token_limit", sa.BigInteger, nullable=False, server_default="1000000"),
        sa.Column("daily_token_limit", sa.BigInteger, nullable=False, server_default="50000"),
        sa.Column("tokens_used_month", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tokens_used_day", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("last_reset_daily", sa.Date, nullable=True),
        sa.Column("last_reset_monthly", sa.Integer, nullable=True),  # month number
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("idx_tenants_is_active", "tenants", ["is_active"])

    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])

    # ── documents ─────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # status: pending | processing | done | error
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("idx_documents_status", "documents", ["status"])

    # ── document_chunks ───────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding", sa.Text, nullable=True),  # stored as vector(1536) via raw SQL
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_chunks_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("idx_chunks_document_id", "document_chunks", ["document_id"])

    # Add pgvector column (must use raw SQL)
    op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ── conversations ─────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("user_ip_hash", sa.String(64), nullable=True),  # SHA-256 + salt, NOT raw IP
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("idx_conversations_session_id", "conversations", ["session_id"])

    # ── messages ──────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user | assistant
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("retrieved_chunk_ids", pg.ARRAY(pg.UUID(as_uuid=True)), nullable=True),
        sa.Column("flagged_injection", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("idx_messages_tenant_id", "messages", ["tenant_id"])

    # ── api_usage ─────────────────────────────────────────────
    op.create_table(
        "api_usage",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("embedding_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("chat_tokens_input", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("chat_tokens_output", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("total_queries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_api_usage_tenant_date", "api_usage", ["tenant_id", "date"], unique=True)

    # ── audit_log ─────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("idx_audit_log_tenant_id", "audit_log", ["tenant_id"])

    # ── Triggers: auto-update updated_at ──────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    for table in ("tenants", "users", "documents"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)


def downgrade() -> None:
    for table in ("tenants", "users", "documents"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
    op.drop_table("audit_log")
    op.drop_table("api_usage")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
