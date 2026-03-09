"""
Sprint 4: Embedding Generation Service

Generates vector embeddings for ontology concepts and knowledge graph summaries
using Google's Gemini embedding API (text-embedding-004, 768 dimensions).

Embeddings enable semantic search across the knowledge base.
"""

import time
from datetime import datetime
from typing import Optional

from app.core.logging import logger

# Embedding model config
EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSIONS = 768
BATCH_SIZE = 100  # Gemini supports up to 100 texts per batch


def _get_genai():
    """Lazy import to avoid import-time failures if API key is not configured."""
    import google.generativeai as genai
    from app.core.config import settings
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


def _check_pgvector_available(db) -> bool:
    """Check if pgvector extension is available in the database."""
    try:
        from sqlalchemy import text
        result = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        return result.fetchone() is not None
    except Exception:
        return False


class EmbeddingService:
    """Service for generating and storing vector embeddings."""

    def generate_embedding(self, text: str) -> Optional[list]:
        """
        Generate a vector embedding for a text string.

        Returns:
            list of floats (768 dimensions) or None on failure
        """
        if not text or not text.strip():
            return None

        try:
            genai = _get_genai()
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return None

    def generate_query_embedding(self, query: str) -> Optional[list]:
        """
        Generate an embedding optimized for search queries.
        Uses task_type="retrieval_query" for better search relevance.
        """
        if not query or not query.strip():
            return None

        try:
            genai = _get_genai()
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            logger.warning(f"Query embedding generation failed: {e}")
            return None

    def build_concept_text(self, concept) -> str:
        """
        Build a rich text representation of an ontology concept for embedding.
        Includes name, type, description, and relationship context.
        """
        parts = [
            f"Concept: {concept.name}",
            f"Type: {concept.concept_type}",
        ]
        if concept.description:
            parts.append(f"Description: {concept.description}")
        parts.append(f"Source: {concept.source_type}")

        # Add relationship context if available
        try:
            for rel in (concept.outgoing_relationships or [])[:5]:
                target = rel.target_concept
                if target:
                    parts.append(f"Related to: {target.name} ({rel.relationship_type})")
            for rel in (concept.incoming_relationships or [])[:5]:
                source = rel.source_concept
                if source:
                    parts.append(f"Referenced by: {source.name} ({rel.relationship_type})")
        except Exception:
            pass

        return "\n".join(parts)

    def build_graph_summary_text(self, graph_version) -> str:
        """
        Build a text summary of a knowledge graph version for embedding.
        """
        graph_data = graph_version.graph_data or {}
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        metadata = graph_data.get("metadata", {})

        parts = [
            f"Knowledge Graph: {metadata.get('source_name', 'Unknown')}",
            f"Type: {graph_version.source_type}",
            f"Nodes: {len(nodes)}, Edges: {len(edges)}",
        ]

        # Include node names
        node_names = [n.get("label", n.get("name", "")) for n in nodes[:20]]
        if node_names:
            parts.append(f"Concepts: {', '.join(node_names)}")

        # Include edge types
        edge_types = set(e.get("label", e.get("type", "")) for e in edges[:20])
        if edge_types:
            parts.append(f"Relationships: {', '.join(edge_types)}")

        return "\n".join(parts)

    def embed_concept(self, db, concept_id: int, tenant_id: int) -> bool:
        """
        Generate and store embedding for a single ontology concept.
        Returns True if successful.
        """
        from app import crud

        concept = crud.ontology_concept.get(db=db, id=concept_id, tenant_id=tenant_id)
        if not concept:
            return False

        text = self.build_concept_text(concept)
        embedding = self.generate_embedding(text)
        if not embedding:
            return False

        try:
            if _check_pgvector_available(db):
                from sqlalchemy import text as sql_text
                db.execute(
                    sql_text(
                        "UPDATE ontology_concepts SET embedding = :emb, "
                        "embedding_model = :model, embedded_at = :ts "
                        "WHERE id = :id"
                    ),
                    {
                        "emb": str(embedding),
                        "model": EMBEDDING_MODEL,
                        "ts": datetime.utcnow(),
                        "id": concept_id,
                    },
                )
            else:
                # Fallback: store as JSON
                from sqlalchemy import text as sql_text
                import json
                db.execute(
                    sql_text(
                        "UPDATE ontology_concepts SET embedding = :emb::jsonb, "
                        "embedding_model = :model, embedded_at = :ts "
                        "WHERE id = :id"
                    ),
                    {
                        "emb": json.dumps(embedding),
                        "model": EMBEDDING_MODEL,
                        "ts": datetime.utcnow(),
                        "id": concept_id,
                    },
                )
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding for concept {concept_id}: {e}")
            db.rollback()
            return False

    def embed_concepts_batch(self, db, tenant_id: int, concept_ids: list) -> dict:
        """
        Batch-embed multiple concepts. Returns {embedded: N, failed: N, skipped: N}.
        """
        from app import crud

        stats = {"embedded": 0, "failed": 0, "skipped": 0}

        for i, cid in enumerate(concept_ids):
            try:
                concept = crud.ontology_concept.get(db=db, id=cid, tenant_id=tenant_id)
                if not concept:
                    stats["skipped"] += 1
                    continue

                # Skip if already embedded recently (within 24h)
                if concept.embedded_at and hasattr(concept, 'embedded_at'):
                    try:
                        if (datetime.utcnow() - concept.embedded_at).total_seconds() < 86400:
                            stats["skipped"] += 1
                            continue
                    except Exception:
                        pass

                if self.embed_concept(db, cid, tenant_id):
                    stats["embedded"] += 1
                else:
                    stats["failed"] += 1

                # Rate limiting: ~1500 RPM for Gemini embedding API
                if (i + 1) % 50 == 0:
                    time.sleep(2)

            except Exception as e:
                logger.warning(f"Batch embed failed for concept {cid}: {e}")
                stats["failed"] += 1

        return stats

    def embed_all_concepts(self, db, tenant_id: int) -> dict:
        """
        Embed all ontology concepts for a tenant that don't have embeddings yet.
        """
        from sqlalchemy import text as sql_text

        # Find concepts without embeddings
        result = db.execute(
            sql_text(
                "SELECT id FROM ontology_concepts "
                "WHERE tenant_id = :tid AND is_active = true "
                "AND (embedded_at IS NULL OR embedding IS NULL) "
                "ORDER BY id"
            ),
            {"tid": tenant_id},
        )
        concept_ids = [row[0] for row in result.fetchall()]

        if not concept_ids:
            return {"embedded": 0, "failed": 0, "skipped": 0, "total": 0}

        logger.info(f"Embedding {len(concept_ids)} concepts for tenant {tenant_id}")
        stats = self.embed_concepts_batch(db, tenant_id, concept_ids)
        stats["total"] = len(concept_ids)
        logger.info(f"Embedding complete: {stats}")
        return stats

    def embed_graph_version(self, db, version_id: int, tenant_id: int) -> bool:
        """
        Generate and store embedding for a knowledge graph version.
        """
        from app.models.knowledge_graph_version import KnowledgeGraphVersion

        version = db.query(KnowledgeGraphVersion).filter(
            KnowledgeGraphVersion.id == version_id,
            KnowledgeGraphVersion.tenant_id == tenant_id,
        ).first()

        if not version:
            return False

        summary_text = self.build_graph_summary_text(version)
        embedding = self.generate_embedding(summary_text)
        if not embedding:
            return False

        try:
            if _check_pgvector_available(db):
                from sqlalchemy import text as sql_text
                db.execute(
                    sql_text(
                        "UPDATE knowledge_graph_versions SET embedding = :emb, "
                        "summary_text = :summary WHERE id = :id"
                    ),
                    {"emb": str(embedding), "summary": summary_text, "id": version_id},
                )
            else:
                import json
                from sqlalchemy import text as sql_text
                db.execute(
                    sql_text(
                        "UPDATE knowledge_graph_versions SET embedding = :emb::jsonb, "
                        "summary_text = :summary WHERE id = :id"
                    ),
                    {"emb": json.dumps(embedding), "summary": summary_text, "id": version_id},
                )
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store graph embedding for version {version_id}: {e}")
            db.rollback()
            return False


# Singleton
embedding_service = EmbeddingService()
