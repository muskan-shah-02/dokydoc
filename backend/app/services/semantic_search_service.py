"""
Sprint 4: Semantic Search Service

Provides vector-similarity search across ontology concepts and knowledge graphs.
Falls back to text-based search when pgvector is not available.
"""

from typing import Optional
from sqlalchemy import text as sql_text

from app.core.logging import logger
from app.services.embedding_service import embedding_service, _check_pgvector_available


class SemanticSearchService:
    """Search across ontology concepts using vector similarity + text matching."""

    def search_concepts(
        self,
        db,
        query: str,
        tenant_id: int,
        *,
        concept_type: Optional[str] = None,
        source_type: Optional[str] = None,
        initiative_id: Optional[int] = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list:
        """
        Search ontology concepts by semantic similarity.
        Falls back to ILIKE text search if pgvector is not available.

        Returns list of dicts: [{id, name, concept_type, description, source_type,
                                  confidence_score, similarity, initiative_id}]
        """
        results = []

        if _check_pgvector_available(db):
            results = self._vector_search_concepts(
                db, query, tenant_id,
                concept_type=concept_type,
                source_type=source_type,
                initiative_id=initiative_id,
                min_confidence=min_confidence,
                limit=limit,
            )

        # Fallback or supplement with text search
        if len(results) < limit:
            text_results = self._text_search_concepts(
                db, query, tenant_id,
                concept_type=concept_type,
                source_type=source_type,
                initiative_id=initiative_id,
                min_confidence=min_confidence,
                limit=limit - len(results),
            )
            # Merge: avoid duplicates
            seen_ids = {r["id"] for r in results}
            for tr in text_results:
                if tr["id"] not in seen_ids:
                    results.append(tr)

        return results[:limit]

    def _vector_search_concepts(
        self, db, query, tenant_id, *, concept_type, source_type,
        initiative_id, min_confidence, limit,
    ) -> list:
        """Vector similarity search using pgvector cosine distance."""
        query_embedding = embedding_service.generate_query_embedding(query)
        if not query_embedding:
            return []

        # Build WHERE clauses
        conditions = ["c.tenant_id = :tid", "c.is_active = true", "c.embedding IS NOT NULL"]
        params = {"tid": tenant_id, "emb": str(query_embedding), "lim": limit}

        if concept_type:
            conditions.append("c.concept_type = :ctype")
            params["ctype"] = concept_type
        if source_type:
            conditions.append("c.source_type = :stype")
            params["stype"] = source_type
        if initiative_id:
            conditions.append("c.initiative_id = :iid")
            params["iid"] = initiative_id
        if min_confidence > 0:
            conditions.append("c.confidence_score >= :minconf")
            params["minconf"] = min_confidence

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT c.id, c.name, c.concept_type, c.description, c.source_type,
                   c.confidence_score, c.initiative_id,
                   1 - (c.embedding <=> :emb::vector) AS similarity
            FROM ontology_concepts c
            WHERE {where_clause}
            ORDER BY c.embedding <=> :emb::vector
            LIMIT :lim
        """

        try:
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "concept_type": row[2],
                    "description": row[3],
                    "source_type": row[4],
                    "confidence_score": float(row[5]) if row[5] else None,
                    "initiative_id": row[6],
                    "similarity": round(float(row[7]), 4) if row[7] else 0,
                    "match_type": "vector",
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to text: {e}")
            return []

    def _text_search_concepts(
        self, db, query, tenant_id, *, concept_type, source_type,
        initiative_id, min_confidence, limit,
    ) -> list:
        """Fallback text search using ILIKE pattern matching."""
        conditions = ["c.tenant_id = :tid", "c.is_active = true"]
        params = {"tid": tenant_id, "lim": limit}

        # Search in name and description
        conditions.append("(c.name ILIKE :q OR c.description ILIKE :q)")
        params["q"] = f"%{query}%"

        if concept_type:
            conditions.append("c.concept_type = :ctype")
            params["ctype"] = concept_type
        if source_type:
            conditions.append("c.source_type = :stype")
            params["stype"] = source_type
        if initiative_id:
            conditions.append("c.initiative_id = :iid")
            params["iid"] = initiative_id
        if min_confidence > 0:
            conditions.append("c.confidence_score >= :minconf")
            params["minconf"] = min_confidence

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT c.id, c.name, c.concept_type, c.description, c.source_type,
                   c.confidence_score, c.initiative_id
            FROM ontology_concepts c
            WHERE {where_clause}
            ORDER BY
                CASE WHEN c.name ILIKE :exact THEN 0 ELSE 1 END,
                c.confidence_score DESC NULLS LAST
            LIMIT :lim
        """
        params["exact"] = f"%{query}%"

        try:
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "concept_type": row[2],
                    "description": row[3],
                    "source_type": row[4],
                    "confidence_score": float(row[5]) if row[5] else None,
                    "initiative_id": row[6],
                    "similarity": None,
                    "match_type": "text",
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []

    def search_graphs(
        self,
        db,
        query: str,
        tenant_id: int,
        *,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """
        Search knowledge graph versions by summary similarity.
        Returns list of dicts with graph metadata and similarity score.
        """
        results = []

        if _check_pgvector_available(db):
            query_embedding = embedding_service.generate_query_embedding(query)
            if query_embedding:
                conditions = ["kgv.tenant_id = :tid", "kgv.is_current = true", "kgv.embedding IS NOT NULL"]
                params = {"tid": tenant_id, "emb": str(query_embedding), "lim": limit}

                if source_type:
                    conditions.append("kgv.source_type = :stype")
                    params["stype"] = source_type

                where_clause = " AND ".join(conditions)

                sql = f"""
                    SELECT kgv.id, kgv.source_type, kgv.source_id, kgv.version,
                           kgv.summary_text, kgv.created_at,
                           1 - (kgv.embedding <=> :emb::vector) AS similarity
                    FROM knowledge_graph_versions kgv
                    WHERE {where_clause}
                    ORDER BY kgv.embedding <=> :emb::vector
                    LIMIT :lim
                """

                try:
                    rows = db.execute(sql_text(sql), params).fetchall()
                    results = [
                        {
                            "id": row[0],
                            "source_type": row[1],
                            "source_id": row[2],
                            "version": row[3],
                            "summary": row[4],
                            "created_at": str(row[5]) if row[5] else None,
                            "similarity": round(float(row[6]), 4) if row[6] else 0,
                        }
                        for row in rows
                    ]
                except Exception as e:
                    logger.warning(f"Graph vector search failed: {e}")

        # Fallback: text search on summary_text
        if not results:
            conditions = ["kgv.tenant_id = :tid", "kgv.is_current = true", "kgv.summary_text IS NOT NULL"]
            params = {"tid": tenant_id, "q": f"%{query}%", "lim": limit}

            if source_type:
                conditions.append("kgv.source_type = :stype")
                params["stype"] = source_type

            conditions.append("kgv.summary_text ILIKE :q")
            where_clause = " AND ".join(conditions)

            sql = f"""
                SELECT kgv.id, kgv.source_type, kgv.source_id, kgv.version,
                       kgv.summary_text, kgv.created_at
                FROM knowledge_graph_versions kgv
                WHERE {where_clause}
                ORDER BY kgv.created_at DESC
                LIMIT :lim
            """

            try:
                rows = db.execute(sql_text(sql), params).fetchall()
                results = [
                    {
                        "id": row[0],
                        "source_type": row[1],
                        "source_id": row[2],
                        "version": row[3],
                        "summary": row[4],
                        "created_at": str(row[5]) if row[5] else None,
                        "similarity": None,
                    }
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Graph text search failed: {e}")

        return results

    def find_related(
        self,
        db,
        concept_id: int,
        tenant_id: int,
        *,
        depth: int = 1,
        limit: int = 20,
    ) -> list:
        """
        Find concepts related to a given concept via graph traversal
        and optionally vector similarity.

        Returns list of dicts: [{id, name, concept_type, relationship_type, distance}]
        """
        results = []
        seen_ids = {concept_id}

        # Graph traversal: walk outgoing and incoming edges
        sql = """
            SELECT DISTINCT c.id, c.name, c.concept_type, c.description,
                   c.source_type, c.confidence_score,
                   r.relationship_type, 1 as distance
            FROM ontology_relationships r
            JOIN ontology_concepts c ON (
                (r.source_concept_id = :cid AND c.id = r.target_concept_id)
                OR (r.target_concept_id = :cid AND c.id = r.source_concept_id)
            )
            WHERE r.tenant_id = :tid AND c.is_active = true
            LIMIT :lim
        """

        try:
            rows = db.execute(
                sql_text(sql),
                {"cid": concept_id, "tid": tenant_id, "lim": limit},
            ).fetchall()

            for row in rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    results.append({
                        "id": row[0],
                        "name": row[1],
                        "concept_type": row[2],
                        "description": row[3],
                        "source_type": row[4],
                        "confidence_score": float(row[5]) if row[5] else None,
                        "relationship_type": row[6],
                        "distance": row[7],
                        "match_type": "graph",
                    })
        except Exception as e:
            logger.error(f"Graph traversal failed for concept {concept_id}: {e}")

        # Optionally supplement with vector-similar concepts (not graph-connected)
        if len(results) < limit and _check_pgvector_available(db):
            try:
                from app import crud
                concept = crud.ontology_concept.get(db=db, id=concept_id, tenant_id=tenant_id)
                if concept and hasattr(concept, 'embedding') and concept.embedding:
                    # Use concept's own embedding to find similar
                    sql_vec = """
                        SELECT c.id, c.name, c.concept_type, c.description,
                               c.source_type, c.confidence_score,
                               1 - (c.embedding <=> (
                                   SELECT embedding FROM ontology_concepts WHERE id = :cid
                               )) AS similarity
                        FROM ontology_concepts c
                        WHERE c.tenant_id = :tid AND c.is_active = true
                              AND c.id != :cid AND c.embedding IS NOT NULL
                        ORDER BY c.embedding <=> (
                            SELECT embedding FROM ontology_concepts WHERE id = :cid
                        )
                        LIMIT :lim
                    """
                    vec_rows = db.execute(
                        sql_text(sql_vec),
                        {"cid": concept_id, "tid": tenant_id, "lim": limit - len(results)},
                    ).fetchall()

                    for row in vec_rows:
                        if row[0] not in seen_ids:
                            seen_ids.add(row[0])
                            results.append({
                                "id": row[0],
                                "name": row[1],
                                "concept_type": row[2],
                                "description": row[3],
                                "source_type": row[4],
                                "confidence_score": float(row[5]) if row[5] else None,
                                "relationship_type": None,
                                "distance": None,
                                "similarity": round(float(row[6]), 4) if row[6] else 0,
                                "match_type": "vector_similar",
                            })
            except Exception as e:
                logger.warning(f"Vector similarity lookup failed: {e}")

        return results


# Singleton
semantic_search_service = SemanticSearchService()
