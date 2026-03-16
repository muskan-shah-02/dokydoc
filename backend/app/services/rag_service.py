"""
Sprint 7: RAG (Retrieval-Augmented Generation) Service

Enables natural-language Q&A over documents, code, and knowledge graphs.

Enhanced 6-Stage Pipeline:
  1. Semantic search → top-K relevant ontology concepts
  2. Graph expansion + cross-graph links via ConceptMapping
  3. Analysis result retrieval from consolidated_analyses
  4. Document segment search with relevance scoring
  5. Code component search including structured_analysis JSONB
  6. Requirement trace retrieval
  7. Assemble context window (respecting token limits)
  8. Generate answer via AI provider (Gemini/Claude)
  9. Track cost via UsageLog
"""

import json
import re
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
    analysis_summaries: List[Dict] = field(default_factory=list)
    cross_graph_links: List[Dict] = field(default_factory=list)
    requirement_traces: List[Dict] = field(default_factory=list)
    live_data: List[Dict] = field(default_factory=list)   # operational/billing/stats data
    token_estimate: int = 0

    def to_prompt_text(self) -> str:
        """Format retrieved context as a text block for the AI prompt."""
        sections = []

        # Live operational data (billing, stats, usage) — highest priority, show first
        if self.live_data:
            for ld in self.live_data[:5]:
                label = ld.get("label", "SYSTEM DATA")
                content = ld.get("content", "")
                sections.append(f"{label}:\n{content}")

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

        if self.cross_graph_links:
            lines = []
            for link in self.cross_graph_links[:10]:
                lines.append(
                    f"  - [Doc] {link['doc_concept']} --[{link['relationship_type']}]--> "
                    f"[Code] {link['code_concept']} (confidence: {link.get('confidence', '?')})"
                )
            sections.append("CROSS-GRAPH LINKS (Document ↔ Code):\n" + "\n".join(lines))

        if self.analysis_summaries:
            for a in self.analysis_summaries[:3]:
                doc_name = a.get("document_name", "Document")
                summary = a.get("summary", "")[:500]
                sections.append(f"ANALYSIS SUMMARY: {doc_name}\n{summary}")

        if self.document_segments:
            for seg in self.document_segments[:5]:
                title = seg.get("title", "Document Segment")
                text = seg.get("text", "")[:500]
                sections.append(f"DOCUMENT: {title}\n{text}")

        if self.code_summaries:
            for cs in self.code_summaries[:5]:
                name = cs.get("name", "File")
                summary = cs.get("summary", "")[:400]
                structured = cs.get("structured_analysis_summary", "")
                text = summary
                if structured:
                    text += f"\n  Key elements: {structured[:200]}"
                sections.append(f"CODE FILE: {name}\n{text}")

        if self.requirement_traces:
            lines = []
            for rt in self.requirement_traces[:8]:
                status_icon = {"fully_covered": "✓", "partially_covered": "◐", "not_covered": "✗", "contradicted": "⚠"}.get(rt.get("coverage_status", ""), "?")
                lines.append(f"  - [{status_icon}] {rt['requirement_key']}: {rt.get('requirement_text', '')[:100]} ({rt.get('coverage_status', 'unknown')})")
            sections.append("REQUIREMENT COVERAGE:\n" + "\n".join(lines))

        return "\n\n".join(sections) if sections else "No relevant context found in the knowledge base."

    def to_summary_dict(self) -> dict:
        """Summary of what context was used (stored on the message)."""
        return {
            "concept_count": len(self.concepts),
            "relationship_count": len(self.relationships),
            "document_segment_count": len(self.document_segments),
            "code_summary_count": len(self.code_summaries),
            "analysis_summary_count": len(self.analysis_summaries),
            "cross_graph_link_count": len(self.cross_graph_links),
            "requirement_trace_count": len(self.requirement_traces),
            "live_data_count": len(self.live_data),
            "token_estimate": self.token_estimate,
            "top_concepts": [c["name"] for c in self.concepts[:5]],
            "live_data_labels": [ld.get("label", "") for ld in self.live_data[:3]],
        }


# -------------------------------------------------------------------
# RAG Service
# -------------------------------------------------------------------

class RAGService:
    """Retrieval-Augmented Generation service for AskyDoc chat."""

    MAX_CONTEXT_TOKENS = 8000  # Raised from 6000 for richer 6-stage context

    def retrieve_context(
        self,
        db: Session,
        query: str,
        tenant_id: int,
        *,
        context_type: str = "general",
        context_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> RetrievedContext:
        """
        Retrieve relevant context from the knowledge base via intent-aware pipeline.

        Intent routing:
          - billing/cost queries → live billing + usage_logs data
          - stats/count queries → live aggregate counts
          - project/what-is queries → repository synthesis + code overview
          - all queries → semantic concept search + doc/code/graph search
        """
        ctx = RetrievedContext()

        # --- Intent Detection: route to appropriate live data sources first ---
        intents = self._detect_query_intent(query)

        if "billing" in intents:
            try:
                ctx.live_data.extend(
                    self._fetch_billing_context(db, tenant_id, user_id=user_id)
                )
            except Exception as e:
                logger.warning(f"RAG billing context failed: {e}")
                db.rollback()

        if "stats" in intents:
            try:
                ctx.live_data.extend(self._fetch_system_stats_context(db, tenant_id))
            except Exception as e:
                logger.warning(f"RAG stats context failed: {e}")
                db.rollback()

        if "project" in intents or not ctx.live_data:
            # Always fetch project overview for project queries OR as base context
            # when no live data was found (catches "what is dokydoc" type questions)
            try:
                ctx.live_data.extend(
                    self._fetch_project_overview_context(db, tenant_id, query, context_type, context_id)
                )
            except Exception as e:
                logger.warning(f"RAG project overview failed: {e}")
                db.rollback()

        # --- Stage 1: Semantic concept search ---
        try:
            from app.services.semantic_search_service import semantic_search_service
            ctx.concepts = semantic_search_service.search_concepts(
                db, query, tenant_id,
                initiative_id=context_id if context_type == "initiative" else None,
                limit=15,
            )
        except Exception as e:
            logger.warning(f"RAG Stage 1 (concept search) failed: {e}")
            db.rollback()

        concept_ids = [c["id"] for c in ctx.concepts[:10]] if ctx.concepts else []

        # --- Stage 2: Graph expansion + cross-graph links ---
        if concept_ids:
            ctx.relationships = self._expand_relationships(db, tenant_id, concept_ids)
            ctx.cross_graph_links = self._fetch_cross_graph_links(db, tenant_id, concept_ids)

        # --- Stage 3: Consolidated analysis retrieval ---
        doc_ids = set()
        if context_type == "document" and context_id:
            doc_ids.add(context_id)
        new_analysis_summaries = self._fetch_analysis_summaries(db, tenant_id, query, doc_ids)
        # Append (not overwrite) — preserves any Stage 1b results
        ctx.analysis_summaries.extend(new_analysis_summaries)

        # --- Stage 4: Document segment search ---
        ctx.document_segments = self._fetch_document_segments(
            db, tenant_id, query, context_type, context_id
        )
        for seg in ctx.document_segments:
            if seg.get("document_id"):
                doc_ids.add(seg["document_id"])

        # --- Stage 5: Code component search ---
        ctx.code_summaries = self._fetch_code_summaries(
            db, tenant_id, query, context_type, context_id
        )

        # --- Stage 6: Requirement trace retrieval ---
        if doc_ids:
            ctx.requirement_traces = self._fetch_requirement_traces(db, tenant_id, doc_ids)

        # Estimate tokens
        ctx.token_estimate = len(ctx.to_prompt_text()) // 4

        # Priority-based trimming (lowest priority trimmed first)
        self._trim_context(ctx)

        return ctx

    def _trim_context(self, ctx: RetrievedContext) -> None:
        """Trim context to fit within token budget using priority-based ordering."""
        while ctx.token_estimate > self.MAX_CONTEXT_TOKENS:
            trimmed = False
            # Priority order: trim lowest-value items first
            if len(ctx.requirement_traces) > 3:
                ctx.requirement_traces.pop()
                trimmed = True
            elif len(ctx.analysis_summaries) > 2:
                ctx.analysis_summaries.pop()
                trimmed = True
            elif len(ctx.code_summaries) > 2:
                ctx.code_summaries.pop()
                trimmed = True
            elif len(ctx.document_segments) > 2:
                ctx.document_segments.pop()
                trimmed = True
            elif len(ctx.cross_graph_links) > 5:
                ctx.cross_graph_links.pop()
                trimmed = True
            elif len(ctx.concepts) > 5:
                ctx.concepts.pop()
                trimmed = True
            else:
                break
            if trimmed:
                ctx.token_estimate = len(ctx.to_prompt_text()) // 4

    # ------------------------------------------------------------------
    # Stage 2 helpers
    # ------------------------------------------------------------------

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
            db.rollback()
            return []

    def _fetch_cross_graph_links(self, db: Session, tenant_id: int, concept_ids: List[int]) -> List[Dict]:
        """Fetch cross-graph links (doc ↔ code) for matched concepts via ConceptMapping."""
        if not concept_ids:
            return []
        try:
            placeholders = ", ".join([f":cid{i}" for i in range(len(concept_ids))])
            params = {f"cid{i}": cid for i, cid in enumerate(concept_ids)}
            params["tid"] = tenant_id

            sql = f"""
                SELECT
                    dc.name AS doc_concept_name,
                    cc.name AS code_concept_name,
                    cm.relationship_type,
                    cm.confidence_score,
                    cm.mapping_method
                FROM concept_mappings cm
                JOIN ontology_concepts dc ON cm.document_concept_id = dc.id
                JOIN ontology_concepts cc ON cm.code_concept_id = cc.id
                WHERE cm.tenant_id = :tid
                  AND cm.status != 'rejected'
                  AND (cm.document_concept_id IN ({placeholders}) OR cm.code_concept_id IN ({placeholders}))
                ORDER BY cm.confidence_score DESC
                LIMIT 10
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "doc_concept": row[0],
                    "code_concept": row[1],
                    "relationship_type": row[2],
                    "confidence": round(float(row[3]), 2) if row[3] else 0,
                    "method": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG cross-graph link fetch failed: {e}")
            db.rollback()
            return []

    # ------------------------------------------------------------------
    # Stage 3 helper
    # ------------------------------------------------------------------

    def _fetch_analysis_summaries(self, db: Session, tenant_id: int, query: str,
                                   doc_ids: set) -> List[Dict]:
        """Fetch consolidated analysis summaries for relevant documents."""
        try:
            # If we have specific doc_ids, use them; otherwise search by query
            if doc_ids:
                placeholders = ", ".join([f":did{i}" for i in range(len(doc_ids))])
                params = {f"did{i}": did for i, did in enumerate(doc_ids)}
                params["tid"] = tenant_id
                sql = f"""
                    SELECT ca.document_id, d.filename, ca.data
                    FROM consolidated_analyses ca
                    JOIN documents d ON ca.document_id = d.id
                    WHERE ca.tenant_id = :tid
                      AND ca.document_id IN ({placeholders})
                    LIMIT 3
                """
            else:
                # Fall back to searching documents matching the query
                params = {"tid": tenant_id, "q": f"%{query[:100]}%"}
                sql = """
                    SELECT ca.document_id, d.filename, ca.data
                    FROM consolidated_analyses ca
                    JOIN documents d ON ca.document_id = d.id
                    WHERE ca.tenant_id = :tid
                      AND d.filename ILIKE :q
                    LIMIT 3
                """
            rows = db.execute(sql_text(sql), params).fetchall()
            results = []
            for row in rows:
                data = row[2] if row[2] else {}
                # Extract key summary from JSONB data
                summary = self._extract_analysis_summary(data)
                results.append({
                    "document_id": row[0],
                    "document_name": row[1] or "Unknown Document",
                    "summary": summary,
                })
            return results
        except Exception as e:
            logger.warning(f"RAG analysis summary fetch failed: {e}")
            db.rollback()
            return []

    def _extract_analysis_summary(self, data: Any) -> str:
        """Extract a concise summary from consolidated analysis JSONB data."""
        if not data:
            return ""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data[:500]
        if isinstance(data, dict):
            parts = []
            # Look for common summary keys in the analysis data
            for key in ("executive_summary", "summary", "overview", "key_findings",
                        "document_type", "purpose", "scope"):
                val = data.get(key)
                if val:
                    if isinstance(val, str):
                        parts.append(f"{key}: {val[:200]}")
                    elif isinstance(val, list):
                        items = ", ".join(str(v)[:50] for v in val[:5])
                        parts.append(f"{key}: {items}")
            if parts:
                return "; ".join(parts)[:500]
            # Fallback: serialize first 500 chars of JSON
            return json.dumps(data, default=str)[:500]
        return str(data)[:500]

    # ------------------------------------------------------------------
    # Stage 4 helper (enhanced)
    # ------------------------------------------------------------------

    def _fetch_document_segments(self, db: Session, tenant_id: int, query: str,
                                  context_type: str, context_id: Optional[int]) -> List[Dict]:
        """Fetch relevant document segments with relevance scoring."""
        try:
            conditions = ["ds.tenant_id = :tid"]
            params: Dict[str, Any] = {"tid": tenant_id, "lim": 5}

            if context_type == "document" and context_id:
                conditions.append("ds.document_id = :did")
                params["did"] = context_id

            conditions.append("(ds.content ILIKE :q OR ds.title ILIKE :q)")
            params["q"] = f"%{query[:100]}%"
            params["q_exact"] = query[:100]

            where = " AND ".join(conditions)
            # Relevance scoring: title exact > title partial > content match
            sql = f"""
                SELECT ds.id, ds.title, ds.content, ds.document_id,
                    CASE
                        WHEN ds.title ILIKE :q_exact THEN 3
                        WHEN ds.title ILIKE :q THEN 2
                        ELSE 1
                    END AS relevance
                FROM document_segments ds
                WHERE {where}
                ORDER BY relevance DESC, ds.id DESC
                LIMIT :lim
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1] or "Segment",
                    "text": (row[2] or "")[:500],
                    "document_id": row[3],
                    "relevance": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG document segment fetch failed: {e}")
            db.rollback()
            return []

    # ------------------------------------------------------------------
    # Stage 5 helper (enhanced)
    # ------------------------------------------------------------------

    def _fetch_code_summaries(self, db: Session, tenant_id: int, query: str,
                               context_type: str, context_id: Optional[int]) -> List[Dict]:
        """Fetch code component summaries with structured_analysis JSONB.

        First tries an ILIKE match on name/summary. If nothing found, falls back
        to the most recently analyzed files so broad queries always get context.
        """
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
                SELECT cc.id, cc.name, cc.summary, cc.location, cc.structured_analysis
                FROM code_components cc
                WHERE {where}
                ORDER BY cc.id DESC
                LIMIT :lim
            """
            rows = db.execute(sql_text(sql), params).fetchall()

            # Broad fallback: if ILIKE returned nothing, grab the most recently
            # analyzed files so broad/vague queries still get useful context
            if not rows:
                fallback_conditions = ["cc.tenant_id = :tid", "cc.summary IS NOT NULL"]
                fallback_params: Dict[str, Any] = {"tid": tenant_id, "lim": 5}
                if context_type == "repository" and context_id:
                    fallback_conditions.append("cc.repository_id = :rid")
                    fallback_params["rid"] = context_id
                fallback_where = " AND ".join(fallback_conditions)
                fallback_sql = f"""
                    SELECT cc.id, cc.name, cc.summary, cc.location, cc.structured_analysis
                    FROM code_components cc
                    WHERE {fallback_where}
                    ORDER BY cc.analysis_completed_at DESC NULLS LAST, cc.id DESC
                    LIMIT :lim
                """
                rows = db.execute(sql_text(fallback_sql), fallback_params).fetchall()

            results = []
            for row in rows:
                structured_summary = self._extract_structured_analysis(row[4])
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "summary": (row[2] or "")[:400],
                    "location": row[3],
                    "structured_analysis_summary": structured_summary,
                })
            return results
        except Exception as e:
            logger.warning(f"RAG code summary fetch failed: {e}")
            db.rollback()
            return []

    def _extract_structured_analysis(self, data: Any) -> str:
        """Extract key elements from code component structured_analysis JSONB."""
        if not data:
            return ""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return ""
        if isinstance(data, dict):
            parts = []
            for key in ("functions", "classes", "endpoints", "imports", "exports"):
                val = data.get(key)
                if val and isinstance(val, list):
                    names = [v.get("name", str(v)) if isinstance(v, dict) else str(v) for v in val[:5]]
                    parts.append(f"{key}: {', '.join(names)}")
            return "; ".join(parts)[:200] if parts else ""
        return ""

    # ------------------------------------------------------------------
    # Stage 6 helper
    # ------------------------------------------------------------------

    def _fetch_requirement_traces(self, db: Session, tenant_id: int, doc_ids: set) -> List[Dict]:
        """Fetch requirement traces for documents found in earlier stages."""
        if not doc_ids:
            return []
        try:
            placeholders = ", ".join([f":did{i}" for i in range(len(doc_ids))])
            params = {f"did{i}": did for i, did in enumerate(doc_ids)}
            params["tid"] = tenant_id

            sql = f"""
                SELECT rt.requirement_key, rt.requirement_text, rt.coverage_status,
                       rt.validation_status, rt.document_id
                FROM requirement_traces rt
                WHERE rt.tenant_id = :tid
                  AND rt.document_id IN ({placeholders})
                ORDER BY CASE rt.coverage_status
                    WHEN 'contradicted' THEN 1
                    WHEN 'not_covered' THEN 2
                    WHEN 'partially_covered' THEN 3
                    WHEN 'fully_covered' THEN 4
                    ELSE 5
                END
                LIMIT 10
            """
            rows = db.execute(sql_text(sql), params).fetchall()
            return [
                {
                    "requirement_key": row[0],
                    "requirement_text": (row[1] or "")[:150],
                    "coverage_status": row[2],
                    "validation_status": row[3],
                    "document_id": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"RAG requirement trace fetch failed: {e}")
            db.rollback()
            return []

    # ------------------------------------------------------------------
    # Intent Detection — classifies query to route to right data sources
    # ------------------------------------------------------------------

    # Billing/cost keywords
    _BILLING_KEYWORDS = re.compile(
        r'\b(billing|bill|cost|costs|cost\s*to|spend|spent|usage|used|usage\s*log|'
        r'how\s*much|charged|charge|inr|usd|rupee|dollar|balance|budget|invoice|'
        r'token|tokens|credits|remaining|consumed|total\s*cost|this\s*month|'
        r'current\s*month|last\s*month|ai\s*cost|model\s*cost|expensive|afford)\b',
        re.IGNORECASE,
    )

    # System stats / count keywords
    _STATS_KEYWORDS = re.compile(
        r'\b(how\s*many|count|total|number\s*of|statistics|stats|overview|'
        r'summary\s*of\s*all|all\s*documents|all\s*files|all\s*repos|list\s*of|'
        r'analyzed|pending|failed|completed|repositories|documents|files|'
        r'users|members|team)\b',
        re.IGNORECASE,
    )

    # Project / "what is" keywords — means user wants overall system info
    _PROJECT_KEYWORDS = re.compile(
        r'\b(what\s*is|describe|tell\s*me\s*about|explain|overview\s*of|'
        r'what\s*does|what\s*do|purpose\s*of|what\s*are|how\s*does|'
        r'architecture|tech\s*stack|technology|built\s*with|made\s*with)\b',
        re.IGNORECASE,
    )

    def _detect_query_intent(self, query: str) -> set:
        """
        Detect what kinds of data the query needs.
        Returns a set of intent strings: 'billing', 'stats', 'project', 'knowledge'
        """
        intents = set()
        if self._BILLING_KEYWORDS.search(query):
            intents.add("billing")
        if self._STATS_KEYWORDS.search(query):
            intents.add("stats")
        if self._PROJECT_KEYWORDS.search(query):
            intents.add("project")
        # Always include knowledge base search
        intents.add("knowledge")
        return intents

    # ------------------------------------------------------------------
    # Live Data Fetchers (billing, stats, system overview)
    # ------------------------------------------------------------------

    def _fetch_billing_context(self, db: Session, tenant_id: int, user_id: int = None) -> List[Dict]:
        """
        Pull current billing balance + usage summary from live DB tables.
        Returns list of live_data dicts for the AI context.
        """
        results = []
        try:
            # 1. Current billing state
            billing_sql = """
                SELECT billing_type, balance_inr, current_month_cost,
                       last_30_days_cost, monthly_limit_inr, last_billing_reset
                FROM tenant_billing
                WHERE tenant_id = :tid
                LIMIT 1
            """
            billing_row = db.execute(sql_text(billing_sql), {"tid": tenant_id}).fetchone()
            if billing_row:
                btype, balance, cur_month, last30, limit, reset = billing_row
                lines = [f"Billing type: {btype}"]
                if btype == "prepaid":
                    lines.append(f"Current balance: ₹{float(balance or 0):.2f}")
                else:
                    lines.append(f"Current month cost: ₹{float(cur_month or 0):.2f}")
                    lines.append(f"Last 30 days cost: ₹{float(last30 or 0):.2f}")
                if limit:
                    lines.append(f"Monthly limit: ₹{float(limit):.2f}")
                    used_pct = (float(cur_month or 0) / float(limit) * 100) if limit else 0
                    lines.append(f"Budget used: {used_pct:.1f}%")
                if reset:
                    lines.append(f"Last billing reset: {reset.strftime('%Y-%m-%d') if hasattr(reset, 'strftime') else reset}")
                results.append({
                    "label": "CURRENT BILLING STATUS",
                    "content": "\n".join(lines),
                })

            # 2. Usage breakdown by feature type this month
            usage_sql = """
                SELECT
                    feature_type,
                    COUNT(*) as request_count,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost_inr), 0) as total_cost_inr,
                    COALESCE(SUM(cost_usd), 0) as total_cost_usd
                FROM usage_logs
                WHERE tenant_id = :tid
                  AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY feature_type
                ORDER BY total_cost_inr DESC
            """
            usage_rows = db.execute(sql_text(usage_sql), {"tid": tenant_id}).fetchall()
            if usage_rows:
                lines = ["Usage this month (by feature):"]
                grand_inr = 0
                grand_tokens = 0
                for row in usage_rows:
                    feat, count, tokens, cost_inr, cost_usd = row
                    grand_inr += float(cost_inr or 0)
                    grand_tokens += int(tokens or 0)
                    lines.append(
                        f"  - {feat}: {count} requests | "
                        f"{int(tokens or 0):,} tokens | ₹{float(cost_inr or 0):.4f}"
                    )
                lines.append(f"  TOTAL: {grand_tokens:,} tokens | ₹{grand_inr:.4f}")
                results.append({
                    "label": "USAGE THIS MONTH",
                    "content": "\n".join(lines),
                })

            # 3. Most recent 10 usage log entries
            recent_sql = """
                SELECT feature_type, operation, model_used, input_tokens,
                       output_tokens, cost_inr, created_at
                FROM usage_logs
                WHERE tenant_id = :tid
                ORDER BY created_at DESC
                LIMIT 10
            """
            recent_rows = db.execute(sql_text(recent_sql), {"tid": tenant_id}).fetchall()
            if recent_rows:
                lines = ["Recent AI usage (last 10 operations):"]
                for row in recent_rows:
                    feat, op, model, inp, out, cost, ts = row
                    ts_str = ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)
                    lines.append(
                        f"  [{ts_str}] {feat}/{op} via {model or 'unknown'}: "
                        f"{(inp or 0) + (out or 0):,} tokens | ₹{float(cost or 0):.4f}"
                    )
                results.append({
                    "label": "RECENT USAGE",
                    "content": "\n".join(lines),
                })

        except Exception as e:
            logger.warning(f"RAG billing context fetch failed: {e}")
            db.rollback()
        return results

    def _fetch_system_stats_context(self, db: Session, tenant_id: int) -> List[Dict]:
        """
        Pull aggregate counts and system overview from live DB tables.
        Returns list of live_data dicts for the AI context.
        """
        results = []
        try:
            stats_sql = """
                SELECT
                    (SELECT COUNT(*) FROM documents WHERE tenant_id = :tid) as doc_count,
                    (SELECT COUNT(*) FROM repositories WHERE tenant_id = :tid) as repo_count,
                    (SELECT COUNT(*) FROM code_components WHERE tenant_id = :tid) as file_count,
                    (SELECT COUNT(*) FROM code_components WHERE tenant_id = :tid AND analysis_status = 'completed') as analyzed_count,
                    (SELECT COUNT(*) FROM code_components WHERE tenant_id = :tid AND analysis_status = 'failed') as failed_count,
                    (SELECT COUNT(*) FROM code_components WHERE tenant_id = :tid AND analysis_status = 'pending') as pending_count,
                    (SELECT COUNT(*) FROM ontology_concepts WHERE tenant_id = :tid) as concept_count,
                    (SELECT COUNT(*) FROM conversations WHERE tenant_id = :tid) as conv_count
            """
            row = db.execute(sql_text(stats_sql), {"tid": tenant_id}).fetchone()
            if row:
                doc_count, repo_count, file_count, analyzed, failed, pending, concepts, convs = row
                lines = [
                    f"Uploaded documents: {doc_count or 0}",
                    f"Repositories: {repo_count or 0}",
                    f"Code files tracked: {file_count or 0}",
                    f"  - Analyzed: {analyzed or 0}",
                    f"  - Failed: {failed or 0}",
                    f"  - Pending: {pending or 0}",
                    f"Knowledge concepts extracted: {concepts or 0}",
                    f"Chat conversations: {convs or 0}",
                ]
                results.append({
                    "label": "ORGANIZATION SYSTEM OVERVIEW",
                    "content": "\n".join(lines),
                })

            # Per-repo breakdown
            repo_sql = """
                SELECT r.name, r.url, r.analysis_status, r.synthesis_status,
                       r.analyzed_files, r.total_files,
                       COUNT(cc.id) as component_count,
                       SUM(CASE WHEN cc.analysis_status = 'completed' THEN 1 ELSE 0 END) as completed_count
                FROM repositories r
                LEFT JOIN code_components cc ON cc.repository_id = r.id AND cc.tenant_id = :tid
                WHERE r.tenant_id = :tid
                GROUP BY r.id, r.name, r.url, r.analysis_status, r.synthesis_status,
                         r.analyzed_files, r.total_files
                ORDER BY r.id DESC
                LIMIT 10
            """
            repo_rows = db.execute(sql_text(repo_sql), {"tid": tenant_id}).fetchall()
            if repo_rows:
                lines = ["Repositories in this organization:"]
                for rrow in repo_rows:
                    name, url, status, synth, analyzed, total, comp_count, comp_done = rrow
                    prog = f"{comp_done or 0}/{comp_count or 0} files analyzed"
                    synth_str = f" | synthesis: {synth}" if synth else ""
                    lines.append(f"  - {name}: status={status}{synth_str} | {prog}")
                results.append({
                    "label": "REPOSITORIES",
                    "content": "\n".join(lines),
                })

        except Exception as e:
            logger.warning(f"RAG system stats fetch failed: {e}")
            db.rollback()
        return results

    def _fetch_project_overview_context(
        self, db: Session, tenant_id: int, query: str,
        context_type: str, context_id: Optional[int],
    ) -> List[Dict]:
        """
        For "what is X" / "describe X" queries — pull synthesis data from repositories
        and top-level code summaries to describe the project.
        """
        results = []
        try:
            # Extract likely project/repo name from query by finding words
            query_words = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', query.lower()))

            conditions = ["r.tenant_id = :tid"]
            params: Dict[str, Any] = {"tid": tenant_id, "lim": 3}

            if context_type == "repository" and context_id:
                conditions.append("r.id = :rid")
                params["rid"] = context_id

            where = " AND ".join(conditions)
            sql = f"""
                SELECT r.id, r.name, r.description, r.url, r.synthesis_data, r.synthesis_status
                FROM repositories r
                WHERE {where}
                ORDER BY
                    CASE WHEN r.synthesis_status = 'completed' THEN 0 ELSE 1 END,
                    r.id DESC
                LIMIT :lim
            """
            rows = db.execute(sql_text(sql), params).fetchall()

            for row in rows:
                repo_id_val, repo_name, repo_desc, repo_url, synthesis_data, synth_status = row

                # Check if this repo name appears in query words (name relevance boost)
                repo_words = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', repo_name.lower()))
                is_relevant = bool(repo_words & query_words) or context_type == "repository"

                # Always include if only 1 repo, or if name matches query words
                if not rows or len(rows) == 1 or is_relevant or not context_id:
                    parts = []
                    if repo_desc:
                        parts.append(f"Description: {repo_desc[:300]}")
                    if repo_url:
                        parts.append(f"URL: {repo_url}")

                    if synthesis_data:
                        sd = synthesis_data if isinstance(synthesis_data, dict) else {}
                        if sd.get("system_overview"):
                            parts.append(f"\nSystem Overview:\n{sd['system_overview'][:600]}")
                        ts = sd.get("technology_stack", {})
                        if ts:
                            langs = ", ".join(ts.get("languages", [])[:5])
                            frameworks = ", ".join(ts.get("frameworks", [])[:5])
                            dbs = ", ".join(ts.get("databases", [])[:3])
                            if langs:
                                parts.append(f"Languages: {langs}")
                            if frameworks:
                                parts.append(f"Frameworks: {frameworks}")
                            if dbs:
                                parts.append(f"Databases: {dbs}")
                        arch = sd.get("architecture", {})
                        if arch.get("style"):
                            parts.append(f"Architecture: {arch['style']}")
                        sec = sd.get("security_posture", {})
                        if sec.get("authentication"):
                            parts.append(f"Auth: {sec['authentication']}")
                        api = sd.get("api_surface", {})
                        if api.get("total_endpoints"):
                            parts.append(f"Total API endpoints: {api['total_endpoints']}")

                    if parts:
                        results.append({
                            "label": f"PROJECT: {repo_name}",
                            "content": "\n".join(parts),
                        })

            # If no repo results, try to return top code files as context
            if not results:
                fallback_sql = """
                    SELECT cc.name, cc.summary, cc.location
                    FROM code_components cc
                    WHERE cc.tenant_id = :tid
                      AND cc.summary IS NOT NULL
                      AND cc.analysis_status = 'completed'
                    ORDER BY cc.analysis_completed_at DESC NULLS LAST
                    LIMIT 5
                """
                cc_rows = db.execute(sql_text(fallback_sql), {"tid": tenant_id}).fetchall()
                if cc_rows:
                    lines = ["Recently analyzed code files:"]
                    for cc_row in cc_rows:
                        name, summary, loc = cc_row
                        lines.append(f"  - {name}: {(summary or '')[:200]}")
                    results.append({
                        "label": "AVAILABLE CODE CONTEXT",
                        "content": "\n".join(lines),
                    })

        except Exception as e:
            logger.warning(f"RAG project overview fetch failed: {e}")
            db.rollback()
        return results

    # ------------------------------------------------------------------
    # Role-Aware Prompt Intelligence (Task 4)
    # ------------------------------------------------------------------

    # Role → communication style mapping
    ROLE_INSTRUCTIONS = {
        "CXO": {
            "persona": "strategic advisor to a C-level executive",
            "style": (
                "Focus on business impact, ROI, strategic implications, and high-level trends. "
                "Use executive-friendly language. Lead with insights and recommendations. "
                "Quantify impact where possible (costs, coverage %, risk levels). "
                "Avoid deep technical jargon unless specifically asked."
            ),
            "priority_context": ["analysis_summaries", "requirement_traces", "cross_graph_links"],
        },
        "ADMIN": {
            "persona": "operations and compliance advisor",
            "style": (
                "Focus on operational status, user activity, billing, and system health. "
                "Be precise with numbers, dates, and statuses. "
                "Highlight anything requiring administrative action."
            ),
            "priority_context": ["analysis_summaries", "requirement_traces"],
        },
        "DEVELOPER": {
            "persona": "senior technical architect and code expert",
            "style": (
                "Provide deep technical detail — code structures, function signatures, "
                "architecture patterns, and implementation specifics. "
                "Use code snippets and technical terminology freely. "
                "Reference file paths, function names, and component locations. "
                "Highlight code-document mismatches and technical debt."
            ),
            "priority_context": ["code_summaries", "cross_graph_links", "requirement_traces"],
        },
        "BA": {
            "persona": "business analysis and requirements expert",
            "style": (
                "Focus on requirements coverage, business rules, process flows, and gaps. "
                "Map business concepts to their implementation status. "
                "Highlight requirements that are not covered or contradicted. "
                "Use structured formats: tables, numbered lists, coverage matrices."
            ),
            "priority_context": ["requirement_traces", "analysis_summaries", "cross_graph_links"],
        },
        "PRODUCT_MANAGER": {
            "persona": "product strategy and feature analysis expert",
            "style": (
                "Focus on feature completeness, user impact, and product roadmap alignment. "
                "Connect business requirements to implementation status. "
                "Highlight gaps between what's documented and what's built. "
                "Use clear, non-technical language with structured summaries."
            ),
            "priority_context": ["requirement_traces", "analysis_summaries", "document_segments"],
        },
        "AUDITOR": {
            "persona": "compliance and audit specialist",
            "style": (
                "Focus on compliance status, audit trails, requirement traceability, and risk. "
                "Be precise and factual — cite sources for every claim. "
                "Flag contradictions, gaps, and non-compliance. "
                "Use formal, evidence-based language. Structure as findings."
            ),
            "priority_context": ["requirement_traces", "cross_graph_links", "analysis_summaries"],
        },
    }

    def _get_org_context(self, db: Session, tenant_id: int) -> str:
        """Fetch organization profile from Tenant.settings for prompt context."""
        try:
            tenant = crud.tenant.get(db, id=tenant_id)
            if not tenant or not tenant.settings:
                return ""

            profile = tenant.settings.get("org_profile", {})
            if not profile:
                return ""

            parts = []
            if profile.get("company_description"):
                parts.append(f"Company: {profile['company_description'][:300]}")
            if profile.get("mission"):
                parts.append(f"Mission: {profile['mission'][:200]}")
            if profile.get("industry"):
                parts.append(f"Industry: {profile['industry']}")
            if profile.get("products_services"):
                items = ", ".join(str(p) for p in profile["products_services"][:8])
                parts.append(f"Products/Services: {items}")
            if profile.get("key_objectives"):
                items = ", ".join(str(o) for o in profile["key_objectives"][:5])
                parts.append(f"Key Objectives: {items}")
            if profile.get("tech_stack"):
                items = ", ".join(str(t) for t in profile["tech_stack"][:10])
                parts.append(f"Tech Stack: {items}")
            if profile.get("team_size"):
                parts.append(f"Team Size: {profile['team_size']}")

            return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.warning(f"Failed to fetch org context: {e}")
            return ""

    def _get_role_instructions(self, user_roles: List[str]) -> Dict[str, str]:
        """
        Map user roles to communication directives.

        Returns dict with 'persona' and 'style' for prompt injection.
        Uses the highest-priority role when user has multiple roles.
        """
        # Priority order: CXO > ADMIN > DEVELOPER > BA > PRODUCT_MANAGER > AUDITOR
        role_priority = ["CXO", "ADMIN", "DEVELOPER", "BA", "PRODUCT_MANAGER", "AUDITOR"]

        primary_role = None
        for role in role_priority:
            if role in user_roles:
                primary_role = role
                break

        if primary_role and primary_role in self.ROLE_INSTRUCTIONS:
            return self.ROLE_INSTRUCTIONS[primary_role]

        # Default: general-purpose assistant
        return {
            "persona": "knowledgeable AI assistant",
            "style": (
                "Provide clear, well-structured answers. "
                "Balance technical depth with accessibility. "
                "Use markdown formatting for readability."
            ),
            "priority_context": [],
        }

    # ------------------------------------------------------------------
    # Answer generation (Task 4: role-aware, Task 6: model selection)
    # ------------------------------------------------------------------

    async def generate_answer(
        self,
        query: str,
        context: RetrievedContext,
        conversation_history: List[Dict],
        *,
        tenant_id: int,
        user_id: int,
        user_roles: Optional[List[str]] = None,
        model_preference: str = "gemini",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Generate an AI answer using retrieved context with role-aware prompting
        and user-selected model routing.

        Args:
            query: User's question
            context: Retrieved context from 6-stage pipeline
            conversation_history: Recent messages for multi-turn
            tenant_id: Organization ID
            user_id: User ID
            user_roles: User's roles (e.g., ["CXO"], ["DEVELOPER", "BA"])
            model_preference: "gemini" (default) | "claude" | "auto"
            db: Database session (needed for org context fetch)

        Returns dict with: answer, input_tokens, output_tokens, cost_usd, model_used, citations
        """
        # Fetch org context and role instructions
        org_context = ""
        if db:
            org_context = self._get_org_context(db, tenant_id)

        role_info = self._get_role_instructions(user_roles or [])

        # Build prompt with role awareness
        system_context = context.to_prompt_text()

        history_text = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-6:]:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg['content'][:300]}")
            history_text = "\n".join(history_lines)

        prompt = self._build_prompt(
            query, system_context, history_text,
            org_context=org_context,
            role_info=role_info,
        )

        # Resolve model selection (Task 7: auto-detection)
        effective_model = self._resolve_model(model_preference, query, context)

        # Route to selected provider
        start_time = time.time()
        try:
            from app.services.ai.provider_router import provider_router

            if effective_model == "claude" and provider_router.claude_available:
                result = await self._call_claude(provider_router, prompt, tenant_id, user_id)
            else:
                result = await self._call_gemini(provider_router, prompt, tenant_id, user_id)

            elapsed = time.time() - start_time

            answer_text = result["answer_text"]
            input_tokens = result["input_tokens"]
            output_tokens = result["output_tokens"]
            cost_usd = result["cost_usd"]
            model_used = result["model_used"]

            # Extract citations from AI response (Task 5)
            citations = self._extract_citations(answer_text, context)

            return {
                "answer": answer_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "model_used": model_used,
                "elapsed_seconds": round(elapsed, 2),
                "citations": citations,
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
                "citations": [],
            }

    async def _call_gemini(self, provider_router, prompt: str,
                           tenant_id: int, user_id: int) -> Dict[str, Any]:
        """Call Gemini and return normalized result."""
        response = await provider_router.gemini.generate_content(
            prompt,
            tenant_id=tenant_id,
            user_id=user_id,
            operation="chat_response",
        )
        from app.services.ai.gemini import GeminiService
        tokens = GeminiService.extract_token_usage(response)
        answer_text = response.text if response.text else "I couldn't generate a response. Please try rephrasing your question."

        from app.services.cost_service import cost_service
        cost_data = cost_service.calculate_cost_from_actual_tokens(
            input_tokens=tokens.get("input_tokens", 0),
            output_tokens=tokens.get("output_tokens", 0),
            thinking_tokens=tokens.get("thinking_tokens", 0),
        )
        return {
            "answer_text": answer_text,
            "input_tokens": tokens.get("input_tokens", 0),
            "output_tokens": tokens.get("output_tokens", 0),
            "cost_usd": float(cost_data.get("total_cost_usd", 0)),
            "model_used": "gemini-2.5-flash",
        }

    async def _call_claude(self, provider_router, prompt: str,
                           tenant_id: int, user_id: int) -> Dict[str, Any]:
        """Call Claude and return normalized result. Falls back to Gemini on failure."""
        try:
            response = await provider_router.claude.generate_content(prompt)
            # Claude returns dict: {"text": ..., "input_tokens": ..., "output_tokens": ...}
            answer_text = response.get("text", "") or "I couldn't generate a response."
            input_tokens = response.get("input_tokens", 0)
            output_tokens = response.get("output_tokens", 0)

            cost_data = provider_router.calculate_claude_cost(input_tokens, output_tokens)
            return {
                "answer_text": answer_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": float(cost_data.get("cost_usd", 0)),
                "model_used": cost_data.get("model", "claude-sonnet"),
            }
        except Exception as e:
            logger.warning(f"Claude call failed, falling back to Gemini: {e}")
            return await self._call_gemini(provider_router, prompt, tenant_id, user_id)

    # ------------------------------------------------------------------
    # Model selection logic (Task 7: smart auto-routing)
    # ------------------------------------------------------------------

    # Keywords that suggest code-heavy questions → Claude excels
    _CODE_KEYWORDS = re.compile(
        r'\b(function|class|method|endpoint|api|code|implement|bug|error|exception|'
        r'refactor|debug|stack trace|import|module|package|repository|commit|'
        r'pull request|merge|branch|deploy|architecture|struct|interface)\b',
        re.IGNORECASE,
    )

    def _resolve_model(self, preference: str, query: str, context: RetrievedContext) -> str:
        """
        Resolve effective model from preference.

        "gemini" / "claude" → use directly
        "auto" → smart detection based on query + context
        """
        if preference in ("gemini", "claude"):
            return preference
        # Auto mode: detect best model
        return self._auto_select_model(query, context)

    def _auto_select_model(self, query: str, context: RetrievedContext) -> str:
        """
        Auto-select the best model based on question type and context.

        Claude is better for: code understanding, technical architecture, debugging
        Gemini is better for: general business Q&A, document analysis, speed, cost

        Returns "gemini" or "claude".
        """
        # Heuristic 1: Code keyword density in query
        code_matches = len(self._CODE_KEYWORDS.findall(query))
        if code_matches >= 2:
            return "claude"

        # Heuristic 2: Context is code-heavy (more code than docs)
        code_count = len(context.code_summaries)
        doc_count = len(context.document_segments) + len(context.analysis_summaries)
        if code_count > 0 and code_count > doc_count:
            return "claude"

        # Heuristic 3: Cross-graph links present (code-doc bridging = complex)
        if len(context.cross_graph_links) > 3:
            return "claude"

        # Default: Gemini (faster + cheaper)
        return "gemini"

    # ------------------------------------------------------------------
    # Citation extraction (Task 5)
    # ------------------------------------------------------------------

    # Regex patterns for citation tags: [Doc: name], [Code: name], [Concept: name]
    _CITATION_PATTERN = re.compile(
        r'\[(Doc|Code|Concept|Req):\s*([^\]]+)\]',
        re.IGNORECASE,
    )

    # Map citation tag prefix → (citation_type, entity_type)
    _CITATION_TYPE_MAP = {
        "doc": ("document", "document_segment"),
        "code": ("code", "code_component"),
        "concept": ("concept", "ontology_concept"),
        "req": ("requirement", "requirement_trace"),
    }

    def _extract_citations(self, answer_text: str, context: RetrievedContext) -> List[Dict]:
        """
        Parse citation tags from AI response and map to entity IDs.

        Scans for patterns like [Doc: filename], [Code: component_name],
        [Concept: concept_name], [Req: REQ-001] and resolves each to an
        entity ID from the retrieved context for clickable frontend links.

        Returns list of citation dicts with: citation_type, name, entity_id, entity_type
        """
        if not answer_text:
            return []

        matches = self._CITATION_PATTERN.findall(answer_text)
        if not matches:
            return []

        # Build lookup indexes from retrieved context for fast resolution
        concept_index = {}
        for c in context.concepts:
            concept_index[c.get("name", "").lower()] = c.get("id")

        doc_index = {}
        for seg in context.document_segments:
            title = seg.get("title", "").lower()
            if title:
                doc_index[title] = seg.get("id")

        code_index = {}
        for cs in context.code_summaries:
            name = cs.get("name", "").lower()
            if name:
                code_index[name] = cs.get("id")

        req_index = {}
        for rt in context.requirement_traces:
            key = rt.get("requirement_key", "").lower()
            if key:
                req_index[key] = rt.get("document_id")  # link to parent document

        # Deduplicate and resolve
        seen = set()
        citations = []
        for tag_type, name in matches:
            tag_lower = tag_type.lower()
            name_clean = name.strip()
            dedup_key = (tag_lower, name_clean.lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            type_info = self._CITATION_TYPE_MAP.get(tag_lower, ("unknown", None))
            entity_id = None

            # Resolve entity ID from context indexes
            name_lower = name_clean.lower()
            if tag_lower == "doc":
                entity_id = doc_index.get(name_lower)
            elif tag_lower == "code":
                entity_id = code_index.get(name_lower)
            elif tag_lower == "concept":
                entity_id = concept_index.get(name_lower)
            elif tag_lower == "req":
                entity_id = req_index.get(name_lower)

            citations.append({
                "citation_type": type_info[0],
                "name": name_clean,
                "entity_id": entity_id,
                "entity_type": type_info[1],
            })

        return citations

    # ------------------------------------------------------------------
    # Prompt builder (Task 4: role-aware)
    # ------------------------------------------------------------------

    def _build_prompt(self, query: str, context: str, history: str, *,
                      org_context: str = "", role_info: Optional[Dict] = None) -> str:
        """
        Build the role-aware RAG prompt with org context, role instructions, and citation rules.

        Structure:
          1. AskyDoc persona + role-specific communication style
          2. Organization context (mission, industry, products)
          3. Citation rules
          4. Retrieved context
          5. Conversation history
          6. User question
        """
        persona = (role_info or {}).get("persona", "knowledgeable AI assistant")
        style = (role_info or {}).get("style", "Provide clear, well-structured answers.")

        parts = [
            f"You are AskyDoc — your organization's personal AI expert, acting as a {persona}.",
            "",
            "WHAT YOU ARE:",
            "AskyDoc is an AI chat assistant for the organization. You have access to ALL organizational data — "
            "uploaded documents, analyzed code repositories, knowledge graphs, AND live operational data like "
            "billing costs, usage statistics, and system metrics. Think of yourself as an organizational ChatGPT "
            "that knows everything uploaded or generated within this organization's account.",
            "",
            "COMMUNICATION STYLE:",
            style,
        ]

        # Organization context
        if org_context:
            parts.append("")
            parts.append("--- ORGANIZATION CONTEXT ---")
            parts.append(org_context)
            parts.append("--- END ORGANIZATION CONTEXT ---")
            parts.append("")
            parts.append(
                "Use the organization context above to ground your answers in the company's "
                "specific domain, products, and objectives. Tailor terminology and examples accordingly."
            )

        # Citation and formatting rules
        parts.append("")
        parts.append("RESPONSE RULES:")
        parts.append("- Answer using the provided context. Synthesize all available information into a clear, useful response.")
        parts.append("- When referencing sources, use citation tags: [Doc: filename], [Code: component_name], [Concept: concept_name].")
        parts.append("- Use markdown formatting: headers for sections, code blocks for code, tables for comparisons.")
        parts.append("- Be specific — mention exact names, file paths, requirement keys, and coverage statuses.")
        parts.append("- If multiple sources agree, synthesize them into a cohesive answer rather than listing each separately.")
        parts.append("- If the query is vague or could mean multiple things, answer what you can AND ask 1-2 specific clarifying questions at the end to help the user get more precise information.")
        parts.append("- If context is sparse, still provide whatever is available, then suggest 1-2 specific things the user could ask to get more detail (e.g., 'Try asking: How does the authentication flow work?' or 'Ask me about specific files like src/services/auth.py').")
        parts.append("- NEVER just say 'I don't have context' — always tell the user what IS available and how to ask better questions.")

        # Retrieved context
        if context and context != "No relevant context found in the knowledge base.":
            parts.append(f"\n--- RETRIEVED CONTEXT ---\n{context}\n--- END CONTEXT ---")

        # Conversation history
        if history:
            parts.append(f"\n--- CONVERSATION HISTORY ---\n{history}\n--- END HISTORY ---")

        parts.append(f"\nUser question: {query}")

        return "\n".join(parts)


# Module-level singleton
rag_service = RAGService()
