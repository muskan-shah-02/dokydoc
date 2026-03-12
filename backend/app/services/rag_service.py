"""
Sprint 7: RAG (Retrieval-Augmented Generation) Service

Enables natural-language Q&A over documents, code, and knowledge graphs.

Pipeline:
  1. Semantic search → top-K relevant ontology concepts
  2. Graph expansion → walk edges from matched concepts
  3. Fetch relevant document segments / code component summaries
  4. Assemble context window (respecting token limits)
  5. Generate answer via AI provider (Gemini/Claude)
  6. Track cost via UsageLog
"""

import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.core.logging import logger
from app import crud


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class RetrievedContext:
    """All context retrieved for a single query."""
    concepts: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    document_segments: List[Dict] = field(default_factory=list)
    code_summaries: List[Dict] = field(default_factory=list)
    token_estimate: int = 0

    def to_prompt_text(self) -> str:
        """Format retrieved context as a text block for the AI prompt."""
        sections = []

        if self.concepts:
            lines = []
            for c in self.concepts[:20]:
                desc = (c.get("description") or "")[:120]
                lines.append(f"  - {c['name']} ({c.get('concept_type', '?')}): {desc}")
            sections.append("KNOWLEDGE BASE CONCEPTS:\n" + "\n".join(lines))

        if self.relationships:
            lines = [
                f"  - {r['source']} --[{r['type']}]--> {r['target']}"
                for r in self.relationships[:15]
            ]
            sections.append("CONCEPT RELATIONSHIPS:\n" + "\n".join(lines))

        if self.document_segments:
            for seg in self.document_segments[:5]:
                title = seg.get("title", "Document Segment")
                text = seg.get("text", "")[:500]
                sections.append(f"DOCUMENT: {title}\n{text}")

        if self.code_summaries:
            for cs in self.code_summaries[:5]:
                name = cs.get("name", "File")
                summary = cs.get("summary", "")[:400]
                sections.append(f"CODE FILE: {name}\n{summary}")

        return "\n\n".join(sections) if sections else "No relevant context found in the knowledge base."

    def to_summary_dict(self) -> dict:
        """Summary of what context was used (stored on the message)."""
        return {
            "concept_count": len(self.concepts),
            "relationship_count": len(self.relationships),
            "document_segment_count": len(self.document_segments),
            "code_summary_count": len(self.code_summaries),
            "token_estimate": self.token_estimate,
            "top_concepts": [c["name"] for c in self.concepts[:5]],
        }


# -------------------------------------------------------------------
# RAG Service
# -------------------------------------------------------------------

class RAGService:
    """Retrieval-Augmented Generation service for DokyDoc chat."""

    MAX_CONTEXT_TOKENS = 6000  # Reserve space for query + history + generation

    def retrieve_context(
        self,
        db: Session,
        query: str,
        tenant_id: int,
        *,
        context_type: str = "general",
        context_id: Optional[int] = None,
    ) -> RetrievedContext:
        """
        Retrieve relevant context from the knowledge base.

        Steps:
          1. Semantic search across ontology concepts
          2. Expand matched concepts via graph edges
          3. Fetch related document segments
          4. Fetch related code component summaries
        """
        ctx = RetrievedContext()

        # 1. Semantic concept search
        try:
            from app.services.semantic_search_service import semantic_search_service
            ctx.concepts = semantic_search_service.search_concepts(
                db, query, tenant_id,
                initiative_id=context_id if context_type == "initiative" else None,
                limit=15,
            )
        except Exception as e:
            logger.warning(f"RAG concept search failed: {e}")

        # 2. Expand via graph relationships
        if ctx.concepts:
            ctx.relationships = self._expand_relationships(
                db, tenant_id, [c["id"] for c in ctx.concepts[:10]]
            )

        # 3. Fetch document segments matching concepts
        ctx.document_segments = self._fetch_document_segments(
            db, tenant_id, query, context_type, context_id
        )

        # 4. Fetch code component summaries
        ctx.code_summaries = self._fetch_code_summaries(
            db, tenant_id, query, context_type, context_id
        )

        # Estimate tokens
        ctx.token_estimate = len(ctx.to_prompt_text()) // 4

        # Trim if over budget
        while ctx.token_estimate > self.MAX_CONTEXT_TOKENS and (ctx.concepts or ctx.code_summaries or ctx.document_segments):
            if len(ctx.code_summaries) > 2:
                ctx.code_summaries.pop()
            elif len(ctx.document_segments) > 2:
                ctx.document_segments.pop()
            elif len(ctx.concepts) > 5:
                ctx.concepts.pop()
            else:
                break
            ctx.token_estimate = len(ctx.to_prompt_text()) // 4

        return ctx

    def _expand_relationships(self, db: Session, tenant_id: int, concept_ids: List[int]) -> List[Dict]:
        """Get relationships connecting the retrieved concepts."""
        if not concept_ids:
            return []
        try:
            placeholders = ", ".join([f":cid{i}" for i in range(len(concept_ids))])
            params = {f"cid{i}": cid for i, cid in enumerate(concept_ids)}
            params["tid"] = tenant_id

            sql = f"""
                SELECT
                    src.name AS source_name,
                    r.relationship_type,
                    tgt.name AS target_name
                FROM ontology_relationships r
                JOIN ontology_concepts src ON r.source_concept_id = src.id
                JOIN ontology_concepts tgt ON r.target_concept_id = tgt.id
                WHERE r.tenant_id = :tid
                  AND (r.source_concept_id IN ({placeholders}) OR r.target_concept_id IN ({placeholders}))
                LIMIT 20
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {"source": row[0], "type": row[1], "target": row[2]}
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG relationship expansion failed: {e}")
            return []

    def _fetch_document_segments(self, db: Session, tenant_id: int, query: str,
                                  context_type: str, context_id: Optional[int]) -> List[Dict]:
        """Fetch relevant document segments via text search."""
        try:
            conditions = ["ds.tenant_id = :tid"]
            params: Dict[str, Any] = {"tid": tenant_id, "lim": 5}

            # Scope to specific document if context_type is "document"
            if context_type == "document" and context_id:
                conditions.append("ds.document_id = :did")
                params["did"] = context_id

            # Text match in segment content
            conditions.append("(ds.content ILIKE :q OR ds.title ILIKE :q)")
            params["q"] = f"%{query[:100]}%"

            where = " AND ".join(conditions)
            sql = f"""
                SELECT ds.id, ds.title, ds.content, ds.document_id
                FROM document_segments ds
                WHERE {where}
                ORDER BY ds.id DESC
                LIMIT :lim
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {"id": row[0], "title": row[1] or "Segment", "text": (row[2] or "")[:500], "document_id": row[3]}
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG document segment fetch failed: {e}")
            return []

    def _fetch_code_summaries(self, db: Session, tenant_id: int, query: str,
                               context_type: str, context_id: Optional[int]) -> List[Dict]:
        """Fetch code component summaries relevant to the query."""
        try:
            conditions = ["cc.tenant_id = :tid", "cc.summary IS NOT NULL"]
            params: Dict[str, Any] = {"tid": tenant_id, "lim": 5}

            if context_type == "repository" and context_id:
                conditions.append("cc.repository_id = :rid")
                params["rid"] = context_id

            conditions.append("(cc.name ILIKE :q OR cc.summary ILIKE :q)")
            params["q"] = f"%{query[:100]}%"

            where = " AND ".join(conditions)
            sql = f"""
                SELECT cc.id, cc.name, cc.summary, cc.location
                FROM code_components cc
                WHERE {where}
                ORDER BY cc.id DESC
                LIMIT :lim
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {"id": row[0], "name": row[1], "summary": (row[2] or "")[:400], "location": row[3]}
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG code summary fetch failed: {e}")
            return []

    async def generate_answer(
        self,
        query: str,
        context: RetrievedContext,
        conversation_history: List[Dict],
        *,
        tenant_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Generate an AI answer using retrieved context.

        Returns dict with: answer, input_tokens, output_tokens, cost_usd, model_used
        """
        # Build prompt
        system_context = context.to_prompt_text()

        history_text = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-6:]:  # Last 6 messages
                role_label = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg['content'][:300]}")
            history_text = "\n".join(history_lines)

        prompt = self._build_prompt(query, system_context, history_text)

        # Call AI provider
        start_time = time.time()
        try:
            from app.services.ai.provider_router import provider_router
            response = await provider_router.gemini.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="chat_response",
            )
            elapsed = time.time() - start_time

            from app.services.ai.gemini import GeminiService
            tokens = GeminiService.extract_token_usage(response)
            answer_text = response.text if response.text else "I couldn't generate a response. Please try rephrasing your question."

            # Calculate cost (Gemini 2.5 Flash pricing)
            from app.services.cost_service import cost_service
            cost_data = cost_service.calculate_cost_from_actual_tokens(
                input_tokens=tokens.get("input_tokens", 0),
                output_tokens=tokens.get("output_tokens", 0),
                thinking_tokens=tokens.get("thinking_tokens", 0),
            )

            return {
                "answer": answer_text,
                "input_tokens": tokens.get("input_tokens", 0),
                "output_tokens": tokens.get("output_tokens", 0),
                "cost_usd": float(cost_data.get("total_cost_usd", 0)),
                "model_used": "gemini-2.5-flash",
                "elapsed_seconds": round(elapsed, 2),
            }
        except Exception as e:
            logger.error(f"RAG generation failed: {e}")
            return {
                "answer": f"I encountered an error while generating a response: {str(e)[:200]}",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model_used": None,
                "elapsed_seconds": 0,
            }

    def _build_prompt(self, query: str, context: str, history: str) -> str:
        """Build the RAG prompt with context and conversation history."""
        parts = [
            "You are DokyDoc AI Assistant — an expert on the user's documents, code, and knowledge graphs.",
            "Answer questions accurately using ONLY the provided context. If the context doesn't contain enough information, say so clearly.",
            "When referencing specific concepts, documents, or code files, mention them by name.",
            "Keep answers concise but thorough. Use markdown formatting for code snippets and lists.",
        ]

        if context and context != "No relevant context found in the knowledge base.":
            parts.append(f"\n--- RETRIEVED CONTEXT ---\n{context}\n--- END CONTEXT ---")

        if history:
            parts.append(f"\n--- CONVERSATION HISTORY ---\n{history}\n--- END HISTORY ---")

        parts.append(f"\nUser question: {query}")

        return "\n\n".join(parts)


# Module-level singleton
rag_service = RAGService()
