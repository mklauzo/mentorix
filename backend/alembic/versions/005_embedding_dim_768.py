"""Change embedding dimension to 768 (Ollama nomic-embed-text compatible)

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 00:00:00.000000

OpenAI text-embedding-3-small supports custom dimensions (dimensions=768).
Ollama nomic-embed-text produces 768-dim vectors natively.
Both backends are now compatible with the same column.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old 1536-dim index and column, recreate with 768 dims
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    # Mark existing documents for re-processing (embeddings are now invalid)
    op.execute(
        "UPDATE documents SET status = 'error', "
        "error_message = 'Wymagane ponowne przetworzenie (zmiana formatu embeddingów)' "
        "WHERE status = 'done'"
    )
    op.execute("DELETE FROM document_chunks")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
