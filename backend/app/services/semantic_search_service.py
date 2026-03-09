"""
Sprint 4: Semantic Search Service
Sprint 5: Unified Search — search across concepts, documents, and code components.

Provides vector-similarity search across ontology concepts and knowledge graphs.
Falls back to text-based search when pgvector is not available.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import text as sql_text

from app.core.logging import logger
from app.services.embedding_service import embedding_service, _check_pgvector_available


class SemanticSearchService:
    """Unified search across ontology concepts, documents, code, and graphs."""

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

    # ============================================================
    # SPRINT 5: Document Search
    # ============================================================

    def search_documents(
        self,
        db,
        query: str,
        tenant_id: int,
        *,
        document_type: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """
        Search documents by filename, raw_text content, and document_type.
        Returns list of dicts with document metadata and match highlights.
        """
        conditions = ["d.tenant_id = :tid"]
        params: Dict[str, Any] = {"tid": tenant_id, "q": f"%{query}%", "lim": limit}

        conditions.append(
            "(d.filename ILIKE :q OR d.raw_text ILIKE :q OR d.document_type ILIKE :q)"
        )

        if document_type:
            conditions.append("d.document_type = :dtype")
            params["dtype"] = document_type

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT d.id, d.filename, d.document_type, d.status,
                   d.file_size_kb, d.created_at,
                   CASE WHEN d.filename ILIKE :q THEN 1.0
                        WHEN d.document_type ILIKE :q THEN 0.8
                        ELSE 0.6
                   END AS relevance,
                   SUBSTRING(d.raw_text FROM 1 FOR 200) AS snippet
            FROM documents d
            WHERE {where_clause}
            ORDER BY
                CASE WHEN d.filename ILIKE :q THEN 0 ELSE 1 END,
                d.created_at DESC
            LIMIT :lim
        """

        try:
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "document_type": row[2],
                    "status": row[3],
                    "file_size_kb": row[4],
                    "created_at": str(row[5]) if row[5] else None,
                    "relevance": round(float(row[6]), 2) if row[6] else 0,
                    "snippet": row[7],
                    "category": "document",
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return []

    # ============================================================
    # SPRINT 5: Code Component Search
    # ============================================================

    def search_code_components(
        self,
        db,
        query: str,
        tenant_id: int,
        *,
        component_type: Optional[str] = None,
        analysis_status: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """
        Search code components by name, summary, and location.
        Returns list of dicts with code component metadata.
        """
        conditions = ["cc.tenant_id = :tid"]
        params: Dict[str, Any] = {"tid": tenant_id, "q": f"%{query}%", "lim": limit}

        conditions.append(
            "(cc.name ILIKE :q OR cc.summary ILIKE :q OR cc.location ILIKE :q)"
        )

        if component_type:
            conditions.append("cc.component_type = :ctype")
            params["ctype"] = component_type
        if analysis_status:
            conditions.append("cc.analysis_status = :astatus")
            params["astatus"] = analysis_status

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT cc.id, cc.name, cc.component_type, cc.location,
                   cc.analysis_status, cc.summary, cc.created_at,
                   r.name AS repo_name,
                   CASE WHEN cc.name ILIKE :q THEN 1.0
                        WHEN cc.summary ILIKE :q THEN 0.7
                        ELSE 0.5
                   END AS relevance
            FROM code_components cc
            LEFT JOIN repositories r ON cc.repository_id = r.id
            WHERE {where_clause}
            ORDER BY
                CASE WHEN cc.name ILIKE :q THEN 0 ELSE 1 END,
                cc.created_at DESC
            LIMIT :lim
        """

        try:
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "component_type": row[2],
                    "location": row[3],
                    "analysis_status": row[4],
                    "summary": (row[5] or "")[:200],
                    "created_at": str(row[6]) if row[6] else None,
                    "repo_name": row[7],
                    "relevance": round(float(row[8]), 2) if row[8] else 0,
                    "category": "code",
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Code component search failed: {e}")
            return []

    # ============================================================
    # SPRINT 5: Unified Search
    # ============================================================

    def unified_search(
        self,
        db,
        query: str,
        tenant_id: int,
        *,
        categories: Optional[List[str]] = None,
        initiative_id: Optional[int] = None,
        limit: int = 30,
    ) -> dict:
        """
        Search across all entity types: concepts, documents, code, and graphs.

        Args:
            categories: Filter to specific categories. Options:
                        ["concepts", "documents", "code", "graphs"].
                        None = search all.
            initiative_id: Filter concepts by initiative.
            limit: Max total results (distributed across categories).

        Returns:
            {
                "query": str,
                "total_count": int,
                "results": [{category, ...}],
                "facets": {"concepts": N, "documents": N, "code": N, "graphs": N}
            }
        """
        search_all = not categories
        per_category = max(5, limit // 4)

        all_results: List[Dict[str, Any]] = []
        facets = {"concepts": 0, "documents": 0, "code": 0, "graphs": 0}

        # 1. Search ontology concepts
        if search_all or "concepts" in categories:
            concept_results = self.search_concepts(
                db, query, tenant_id,
                initiative_id=initiative_id,
                limit=per_category,
            )
            for r in concept_results:
                r["category"] = "concept"
                r["relevance"] = r.get("similarity") or 0.5
            all_results.extend(concept_results)
            facets["concepts"] = len(concept_results)

        # 2. Search documents
        if search_all or "documents" in categories:
            doc_results = self.search_documents(
                db, query, tenant_id,
                limit=per_category,
            )
            all_results.extend(doc_results)
            facets["documents"] = len(doc_results)

        # 3. Search code components
        if search_all or "code" in categories:
            code_results = self.search_code_components(
                db, query, tenant_id,
                limit=per_category,
            )
            all_results.extend(code_results)
            facets["code"] = len(code_results)

        # 4. Search knowledge graphs
        if search_all or "graphs" in categories:
            graph_results = self.search_graphs(
                db, query, tenant_id,
                limit=per_category,
            )
            for r in graph_results:
                r["category"] = "graph"
                r["relevance"] = r.get("similarity") or 0.3
            all_results.extend(graph_results)
            facets["graphs"] = len(graph_results)

        # Sort by relevance (higher first), then by category priority
        category_priority = {"concept": 0, "document": 1, "code": 2, "graph": 3}
        all_results.sort(
            key=lambda r: (
                -float(r.get("relevance") or r.get("similarity") or 0),
                category_priority.get(r.get("category", ""), 9),
            )
        )

        return {
            "query": query,
            "total_count": len(all_results[:limit]),
            "results": all_results[:limit],
            "facets": facets,
        }


# Singleton
semantic_search_service = SemanticSearchService()
