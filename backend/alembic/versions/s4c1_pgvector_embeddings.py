"""Enable pgvector extension and add embedding columns

Revision ID: s4c1_pgvector_embeddings
Revises: s5a2_notifications
Create Date: 2026-03-09 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "s4c1_pgvector_embeddings"
down_revision: Union[str, None] = "s5a2_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _try_in_savepoint(conn, sql):
    """Execute SQL in a savepoint so failures don't abort the transaction."""
    try:
        nested = conn.begin_nested()
        conn.execute(text(sql))
        nested.commit()
        return True
    except Exception:
        nested.rollback()
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # Enable pgvector extension (requires superuser or CREATE privilege)
    pgvector_available = _try_in_savepoint(conn, "CREATE EXTENSION IF NOT EXISTS vector")

    inspector = inspect(conn)

    # Add embedding column to ontology_concepts
    existing_cols = [c["name"] for c in inspector.get_columns("ontology_concepts")]
    if "embedding" not in existing_cols:
        if not pgvector_available or not _try_in_savepoint(
            conn, "ALTER TABLE ontology_concepts ADD COLUMN embedding vector(768)"
        ):
            # Fallback: use JSONB if pgvector is not available
            op.add_column("ontology_concepts", sa.Column("embedding", sa.JSON(), nullable=True))

    if "embedding_model" not in existing_cols:
        op.add_column("ontology_concepts", sa.Column("embedding_model", sa.String(50), nullable=True))

    if "embedded_at" not in existing_cols:
        op.add_column("ontology_concepts", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))

    # Add embedding column to knowledge_graph_versions
    existing_kgv_cols = [c["name"] for c in inspector.get_columns("knowledge_graph_versions")]
    if "embedding" not in existing_kgv_cols:
        if not pgvector_available or not _try_in_savepoint(
            conn, "ALTER TABLE knowledge_graph_versions ADD COLUMN embedding vector(768)"
        ):
            op.add_column("knowledge_graph_versions", sa.Column("embedding", sa.JSON(), nullable=True))

    if "summary_text" not in existing_kgv_cols:
        op.add_column("knowledge_graph_versions", sa.Column("summary_text", sa.Text(), nullable=True))

    # Create HNSW indexes for fast ANN search (only if pgvector is available)
    if pgvector_available:
        _try_in_savepoint(
            conn,
            "CREATE INDEX IF NOT EXISTS idx_ontology_concepts_embedding_hnsw "
            "ON ontology_concepts USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)",
        )
        _try_in_savepoint(
            conn,
            "CREATE INDEX IF NOT EXISTS idx_kgv_embedding_hnsw "
            "ON knowledge_graph_versions USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)",
        )


def downgrade() -> None:
    op.drop_column("knowledge_graph_versions", "summary_text")
    try:
        op.drop_column("knowledge_graph_versions", "embedding")
    except Exception:
        pass
    op.drop_column("ontology_concepts", "embedded_at")
    op.drop_column("ontology_concepts", "embedding_model")
    try:
        op.drop_column("ontology_concepts", "embedding")
    except Exception:
        pass
