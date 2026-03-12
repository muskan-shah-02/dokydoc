"""
AskyDoc Query Orchestration Engine — DB-First Intelligence

The brain of AskyDoc. Instead of the naive "search everything → dump into AI" approach,
this engine:
  1. Classifies query complexity (simple vs compound)
  2. Decomposes compound questions into sub-queries
  3. Classifies each sub-query's intent (rule-based, zero AI cost)
  4. Routes to optimal data source: DB-only (₹0) or DB+AI
  5. Executes DB queries directly for structured answers
  6. Assembles all results as context for a single AI synthesis call

Result: 5 questions answered with 1 AI call instead of 5. Cuts costs 60-80%.
"""

import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.core.logging import logger


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class QueryIntent:
    """Classification result for a single query."""
    intent_type: str  # e.g., "temporal_lookup", "business_analysis"
    data_source: str  # "db_only", "db_plus_ai", "ai_only"
    search_terms: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class SubQuery:
    """A decomposed sub-question from a compound query."""
    id: int
    question: str
    intent: Optional[QueryIntent] = None
    db_result: Optional[Dict[str, Any]] = None
    needs_synthesis: bool = False


@dataclass
class OrchestratedResult:
    """Final result from the orchestration pipeline."""
    sub_queries: List[SubQuery] = field(default_factory=list)
    db_context: Dict[str, Any] = field(default_factory=dict)
    needs_ai_synthesis: bool = False
    is_compound: bool = False
    total_db_results: int = 0

    def get_context_text(self) -> str:
        """Format all DB results as context text for AI synthesis."""
        sections = []

        for sq in self.sub_queries:
            if sq.db_result and sq.db_result.get("data"):
                section_title = f"DATA FOR: \"{sq.question}\""
                data = sq.db_result["data"]

                if isinstance(data, list):
                    rows = []
                    for item in data[:15]:
                        if isinstance(item, dict):
                            row_parts = [f"{k}: {v}" for k, v in item.items() if v is not None]
                            rows.append("  - " + ", ".join(row_parts))
                        else:
                            rows.append(f"  - {item}")
                    sections.append(f"{section_title}\n" + "\n".join(rows))
                elif isinstance(data, dict):
                    parts = [f"  {k}: {v}" for k, v in data.items() if v is not None]
                    sections.append(f"{section_title}\n" + "\n".join(parts))
                else:
                    sections.append(f"{section_title}\n  {data}")

            elif sq.db_result and sq.db_result.get("summary"):
                sections.append(f"DATA FOR: \"{sq.question}\"\n  {sq.db_result['summary']}")

        return "\n\n".join(sections) if sections else ""


# -------------------------------------------------------------------
# Intent patterns — rule-based classification (zero AI cost)
# -------------------------------------------------------------------

INTENT_PATTERNS: Dict[str, Dict[str, Any]] = {
    "temporal_lookup": {
        "patterns": [
            r"\bwhen was\b", r"\bfirst created\b", r"\bfirst developed\b",
            r"\bhistory of\b", r"\btimeline\b", r"\bwhen did\b",
            r"\bdate of\b", r"\bhow old\b", r"\bsince when\b",
        ],
        "data_source": "db_only",
    },
    "metrics_lookup": {
        "patterns": [
            r"\bhow many\b", r"\bdaily hit\b", r"\bapi calls?\b",
            r"\bcount of\b", r"\btotal number\b", r"\bfrequency\b",
            r"\bhow often\b", r"\busage stats?\b",
        ],
        "data_source": "db_only",
    },
    "cost_lookup": {
        "patterns": [
            r"\bhow much (?:did|does|will)?\s*(?:it\s+)?cost\b", r"\bspending\b",
            r"\bbudget\b", r"\bexpense\b", r"\bbilling\b",
            r"\bai spend\b", r"\btotal cost\b", r"\bcost of\b",
        ],
        "data_source": "db_only",
    },
    "status_lookup": {
        "patterns": [
            r"\bstatus of\b", r"\bprogress of\b", r"\bwhat state\b",
            r"\bis it complete\b", r"\bcurrent state\b", r"\bstill processing\b",
        ],
        "data_source": "db_only",
    },
    "coverage_lookup": {
        "patterns": [
            r"\bcoverage\b", r"\bpercentage\b", r"\bhow much is covered\b",
            r"\bgaps?\b", r"\brequirement coverage\b", r"\btraceability\b",
        ],
        "data_source": "db_only",
    },
    "mismatch_lookup": {
        "patterns": [
            r"\bwhat'?s wrong\b", r"\bmismatche?s?\b", r"\bissues?\b",
            r"\bproblems?\b", r"\berrors?\b", r"\binconsistenc(?:y|ies)\b",
            r"\bcode.?doc\b", r"\bdiscrepanc(?:y|ies)\b",
        ],
        "data_source": "db_only",
    },
    "ownership_lookup": {
        "patterns": [
            r"\bwho owns?\b", r"\bwho created\b", r"\bwho uploaded\b",
            r"\bassigned to\b", r"\bowner of\b", r"\bcreated by\b",
        ],
        "data_source": "db_only",
    },
    "task_lookup": {
        "patterns": [
            r"\bmy tasks?\b", r"\boverdue\b", r"\bassigned\b",
            r"\bpending tasks?\b", r"\btask list\b", r"\bto.?do\b",
            r"\bwhat.?s assigned\b", r"\bblocked tasks?\b",
        ],
        "data_source": "db_only",
    },
    "activity_lookup": {
        "patterns": [
            r"\brecent changes?\b", r"\bwhat happened\b", r"\bactivity\b",
            r"\blast updated\b", r"\bchangelog\b", r"\brecent activity\b",
        ],
        "data_source": "db_only",
    },
    "structure_lookup": {
        "patterns": [
            r"\bfunctions? in\b", r"\bclasses? in\b", r"\bendpoints?\b",
            r"\barchitecture of\b", r"\bmodules? in\b", r"\bapis? in\b",
            r"\bcomponents? of\b", r"\bcode structure\b",
        ],
        "data_source": "db_plus_ai",
    },
    "business_analysis": {
        "patterns": [
            r"\bbusiness impact\b", r"\brevenue\b", r"\bvalue\b",
            r"\bstrategic\b", r"\broi\b", r"\bmarket\b",
            r"\bbusiness benefit\b", r"\bimpact on business\b",
        ],
        "data_source": "db_plus_ai",
    },
    "gap_analysis": {
        "patterns": [
            r"\bchanges? required\b", r"\bwhat needs?\b", r"\bimprovements?\b",
            r"\bfix(?:es)?\b", r"\bwhat.?s (?:missing|needed)\b",
            r"\baction items?\b", r"\brecommendations?\b",
        ],
        "data_source": "db_plus_ai",
    },
    "evaluation": {
        "patterns": [
            r"\brate\b", r"\bevaluate\b", r"\bassess\b",
            r"\bscore\b", r"\bquality of\b", r"\bhow good\b",
            r"\breview\b",
        ],
        "data_source": "db_plus_ai",
    },
    "explanation": {
        "patterns": [
            r"\bexplain\b", r"\bwhat is\b", r"\bhow does\b",
            r"\bdescribe\b", r"\bsummarize\b", r"\btell me about\b",
            r"\bwhat does .+ do\b", r"\bhelp me understand\b",
        ],
        "data_source": "db_plus_ai",
    },
    "onboarding": {
        "patterns": [
            r"\bi'?m new\b", r"\bnew (?:here|joiner|employee)\b",
            r"\bonboarding\b", r"\bget started\b", r"\boverview of\b",
            r"\bwhat does (?:this|our|the) (?:company|org|organization)\b",
        ],
        "data_source": "db_plus_ai",
    },
}


# -------------------------------------------------------------------
# DB Query Templates
# -------------------------------------------------------------------

DB_QUERY_TEMPLATES: Dict[str, str] = {
    "temporal_lookup": """
        SELECT resource_name, action, description, user_email,
               created_at AT TIME ZONE 'UTC' as created_at
        FROM audit_logs
        WHERE tenant_id = :tid
          AND (resource_name ILIKE :q OR description ILIKE :q)
          AND action IN ('create', 'update', 'analyze')
        ORDER BY created_at ASC
        LIMIT 10
    """,
    "metrics_lookup": """
        SELECT DATE(created_at) as day, COUNT(*) as count,
               COALESCE(SUM(cost_inr), 0) as total_cost_inr,
               COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
        FROM usage_logs
        WHERE tenant_id = :tid
          AND (operation ILIKE :q OR feature_type ILIKE :q)
        GROUP BY DATE(created_at)
        ORDER BY day DESC
        LIMIT 30
    """,
    "cost_lookup": """
        SELECT feature_type,
               COALESCE(SUM(cost_inr), 0) as total_cost_inr,
               COALESCE(SUM(cost_usd), 0) as total_cost_usd,
               COUNT(*) as operations,
               COALESCE(SUM(input_tokens), 0) as tokens_in,
               COALESCE(SUM(output_tokens), 0) as tokens_out
        FROM usage_logs
        WHERE tenant_id = :tid
          AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY feature_type
        ORDER BY total_cost_inr DESC
    """,
    "status_lookup": """
        SELECT filename, status, progress, document_type,
               created_at AT TIME ZONE 'UTC' as created_at,
               updated_at AT TIME ZONE 'UTC' as updated_at
        FROM documents
        WHERE tenant_id = :tid
          AND (filename ILIKE :q OR document_type ILIKE :q)
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 10
    """,
    "mismatch_lookup": """
        SELECT m.description, m.severity, m.status, m.mismatch_type,
               m.confidence, cc.name as component_name, cc.location,
               m.created_at AT TIME ZONE 'UTC' as created_at
        FROM mismatches m
        LEFT JOIN code_components cc ON m.code_component_id = cc.id
        WHERE m.tenant_id = :tid AND m.status != 'resolved'
          AND (m.description ILIKE :q OR cc.name ILIKE :q OR m.mismatch_type ILIKE :q)
        ORDER BY CASE m.severity
            WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2 ELSE 3 END,
            m.created_at DESC
        LIMIT 20
    """,
    "ownership_lookup": """
        SELECT d.filename as resource_name, 'document' as resource_type,
               u.email as owner_email, d.created_at AT TIME ZONE 'UTC' as created_at
        FROM documents d
        JOIN users u ON d.owner_id = u.id
        WHERE d.tenant_id = :tid AND (d.filename ILIKE :q)
        UNION ALL
        SELECT cc.name as resource_name, 'code_component' as resource_type,
               u.email as owner_email, cc.created_at AT TIME ZONE 'UTC' as created_at
        FROM code_components cc
        JOIN users u ON cc.owner_id = u.id
        WHERE cc.tenant_id = :tid AND (cc.name ILIKE :q)
        ORDER BY created_at DESC
        LIMIT 10
    """,
    "task_lookup": """
        SELECT t.title, t.status, t.priority, t.due_date,
               u.email as assigned_to,
               t.created_at AT TIME ZONE 'UTC' as created_at
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to_id = u.id
        WHERE t.tenant_id = :tid
          AND (t.title ILIKE :q OR t.description ILIKE :q)
        ORDER BY CASE t.priority
            WHEN 'critical' THEN 0 WHEN 'high' THEN 1
            WHEN 'medium' THEN 2 ELSE 3 END,
            t.due_date ASC NULLS LAST
        LIMIT 15
    """,
    "task_lookup_user": """
        SELECT t.title, t.status, t.priority, t.due_date,
               t.created_at AT TIME ZONE 'UTC' as created_at
        FROM tasks t
        WHERE t.tenant_id = :tid AND t.assigned_to_id = :uid
          AND t.status NOT IN ('done', 'cancelled')
        ORDER BY CASE t.priority
            WHEN 'critical' THEN 0 WHEN 'high' THEN 1
            WHEN 'medium' THEN 2 ELSE 3 END,
            t.due_date ASC NULLS LAST
        LIMIT 15
    """,
    "activity_lookup": """
        SELECT action, resource_type, resource_name, description,
               user_email, created_at AT TIME ZONE 'UTC' as created_at
        FROM audit_logs
        WHERE tenant_id = :tid
          AND created_at >= NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC
        LIMIT 20
    """,
    "structure_lookup": """
        SELECT cc.name, cc.component_type, cc.location, cc.summary,
               cc.structured_analysis, cc.analysis_delta
        FROM code_components cc
        WHERE cc.tenant_id = :tid
          AND (cc.name ILIKE :q OR cc.location ILIKE :q OR cc.summary ILIKE :q)
          AND cc.analysis_status = 'completed'
        ORDER BY cc.updated_at DESC NULLS LAST
        LIMIT 10
    """,
    "business_analysis": """
        SELECT oc.name, oc.concept_type, oc.description, oc.confidence_score,
               oc.source_type
        FROM ontology_concepts oc
        WHERE oc.tenant_id = :tid AND oc.is_active = true
          AND (oc.name ILIKE :q OR oc.description ILIKE :q)
          AND oc.concept_type IN ('FEATURE', 'PROCESS', 'BUSINESS_RULE', 'STAKEHOLDER', 'KPI')
        ORDER BY oc.confidence_score DESC NULLS LAST
        LIMIT 15
    """,
    "gap_analysis": """
        SELECT m.description, m.severity, m.status, m.details,
               cc.name as component, cc.location,
               cc.analysis_delta
        FROM mismatches m
        LEFT JOIN code_components cc ON m.code_component_id = cc.id
        WHERE m.tenant_id = :tid AND m.status != 'resolved'
          AND (m.description ILIKE :q OR cc.name ILIKE :q)
        ORDER BY CASE m.severity
            WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2 ELSE 3 END
        LIMIT 20
    """,
}


# -------------------------------------------------------------------
# Query Orchestrator
# -------------------------------------------------------------------

class QueryOrchestrator:
    """
    Decomposes complex questions into sub-queries, routes each to the
    optimal data source (DB or AI), and assembles results for synthesis.
    """

    def process_query(
        self,
        db: Session,
        query: str,
        tenant_id: int,
        user_id: int,
        user_roles: List[str],
    ) -> OrchestratedResult:
        """
        Main entry point. Orchestrates the full query pipeline.

        Returns an OrchestratedResult with DB context assembled and
        a flag indicating whether AI synthesis is needed.
        """
        result = OrchestratedResult()

        # Step 1: Classify complexity
        is_compound = self._is_compound_query(query)
        result.is_compound = is_compound

        if is_compound:
            # Step 2: Decompose into sub-queries
            sub_questions = self._decompose_question(query)
            result.sub_queries = [
                SubQuery(id=i + 1, question=sq)
                for i, sq in enumerate(sub_questions)
            ]
        else:
            result.sub_queries = [SubQuery(id=1, question=query)]

        # Step 3: Classify intent and route each sub-query
        for sq in result.sub_queries:
            sq.intent = self._classify_intent(sq.question)

            if sq.intent.data_source in ("db_only", "db_plus_ai"):
                # Execute DB query
                sq.db_result = self._execute_db_query(
                    db, tenant_id, user_id, sq.question, sq.intent
                )
                if sq.db_result and sq.db_result.get("data"):
                    result.total_db_results += (
                        len(sq.db_result["data"]) if isinstance(sq.db_result["data"], list)
                        else 1
                    )

            if sq.intent.data_source in ("db_plus_ai", "ai_only"):
                sq.needs_synthesis = True
                result.needs_ai_synthesis = True

        # If we got DB results but all intents were db_only, still synthesize
        # for a polished answer (but the context is cheap)
        if result.total_db_results > 0 and not result.needs_ai_synthesis:
            result.needs_ai_synthesis = True

        return result

    def _is_compound_query(self, query: str) -> bool:
        """Check if query contains multiple distinct questions."""
        # Multiple question marks
        if query.count("?") > 1:
            return True

        # Multiple sentences with question-like patterns
        sentences = re.split(r'[.?!]\s+', query)
        question_count = sum(
            1 for s in sentences
            if s.strip() and (
                s.strip().endswith("?") or
                re.match(r'^(what|when|how|why|who|where|which|is|are|do|does|can|will|rate|explain|tell)', s.strip(), re.I)
            )
        )
        if question_count > 1:
            return True

        # Conjunctions joining distinct topics
        if re.search(r'\b(and also|and what|also tell|additionally)\b', query, re.I):
            return True

        return False

    def _decompose_question(self, query: str) -> List[str]:
        """
        Split a compound question into individual sub-questions.
        Uses rule-based decomposition (zero AI cost).
        """
        sub_questions = []

        # Split on sentence boundaries
        parts = re.split(r'(?<=[.?!])\s+', query)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Further split on "and" connecting distinct questions
            # But be careful not to split "pros and cons" type phrases
            and_parts = re.split(r'\.\s*(?:and|also)\s+', part, flags=re.I)
            for ap in and_parts:
                ap = ap.strip().rstrip(".")
                if ap and len(ap) > 5:
                    sub_questions.append(ap)

        # If decomposition didn't work well, fall back to original
        if not sub_questions:
            sub_questions = [query]

        return sub_questions

    def _classify_intent(self, query: str) -> QueryIntent:
        """
        Rule-based intent classification (zero AI cost).
        Matches query against intent patterns to determine data source routing.
        """
        query_lower = query.lower()
        best_match = None
        best_confidence = 0.0

        for intent_type, config in INTENT_PATTERNS.items():
            match_count = 0
            for pattern in config["patterns"]:
                if re.search(pattern, query_lower):
                    match_count += 1

            if match_count > 0:
                confidence = min(match_count / len(config["patterns"]) + 0.3, 1.0)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = intent_type

        if best_match:
            return QueryIntent(
                intent_type=best_match,
                data_source=INTENT_PATTERNS[best_match]["data_source"],
                search_terms=self._extract_search_terms(query),
                confidence=best_confidence,
            )

        # Default: needs AI
        return QueryIntent(
            intent_type="general",
            data_source="db_plus_ai",
            search_terms=self._extract_search_terms(query),
            confidence=0.2,
        )

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from a query for DB ILIKE matching."""
        # Remove common question words and stop words
        stop_words = {
            "what", "when", "where", "who", "how", "why", "which", "is", "are",
            "was", "were", "do", "does", "did", "can", "will", "would", "should",
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "by",
            "from", "and", "or", "but", "not", "this", "that", "it", "its",
            "our", "my", "your", "we", "they", "has", "have", "had", "been",
            "being", "about", "tell", "me", "please", "also", "first", "rate",
            "explain", "describe", "show", "give", "get",
        }

        words = re.findall(r'\b[a-zA-Z_]{3,}\b', query.lower())
        terms = [w for w in words if w not in stop_words]

        # Return unique terms, preserving order
        seen = set()
        unique = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return unique[:5]

    def _execute_db_query(
        self,
        db: Session,
        tenant_id: int,
        user_id: int,
        question: str,
        intent: QueryIntent,
    ) -> Dict[str, Any]:
        """Execute a DB query based on intent classification."""
        try:
            # Special handling for user-specific task queries
            if intent.intent_type == "task_lookup" and self._is_personal_query(question):
                return self._execute_user_task_query(db, tenant_id, user_id)

            # Special handling for coverage queries
            if intent.intent_type == "coverage_lookup":
                return self._execute_coverage_query(db, tenant_id)

            # Special handling for cost queries (no search term needed)
            if intent.intent_type == "cost_lookup":
                return self._execute_cost_query(db, tenant_id)

            # Special handling for activity queries (no search term needed)
            if intent.intent_type == "activity_lookup":
                return self._execute_activity_query(db, tenant_id)

            # General template-based query
            template = DB_QUERY_TEMPLATES.get(intent.intent_type)
            if not template:
                return {"data": None, "summary": "No DB template for this query type"}

            # Build search pattern from terms
            search_pattern = "%"
            if intent.search_terms:
                search_pattern = "%" + "%".join(intent.search_terms[:3]) + "%"
            else:
                # Use first meaningful chunk of the question
                search_pattern = f"%{question[:50]}%"

            params = {"tid": tenant_id, "q": search_pattern}
            rows = db.execute(sql_text(template), params).fetchall()

            if not rows:
                return {
                    "data": [],
                    "summary": f"No results found for {intent.intent_type}",
                    "query_type": intent.intent_type,
                }

            # Convert rows to dicts
            columns = rows[0]._fields if hasattr(rows[0], '_fields') else [f"col_{i}" for i in range(len(rows[0]))]
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    # Convert datetime to string
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    # Truncate long JSON fields
                    elif isinstance(val, (dict, list)):
                        val_str = str(val)
                        if len(val_str) > 500:
                            val = val_str[:500] + "..."
                    row_dict[col] = val
                data.append(row_dict)

            return {
                "data": data,
                "count": len(data),
                "query_type": intent.intent_type,
                "summary": f"Found {len(data)} result(s) for {intent.intent_type}",
            }

        except Exception as e:
            logger.warning(f"DB query failed for intent {intent.intent_type}: {e}")
            return {
                "data": None,
                "summary": f"DB query failed: {str(e)[:100]}",
                "query_type": intent.intent_type,
            }

    def _is_personal_query(self, question: str) -> bool:
        """Check if query is about the current user's tasks."""
        return bool(re.search(r'\b(my|assigned to me|i have)\b', question, re.I))

    def _execute_user_task_query(self, db: Session, tenant_id: int, user_id: int) -> Dict[str, Any]:
        """Get tasks assigned to the current user."""
        try:
            template = DB_QUERY_TEMPLATES["task_lookup_user"]
            rows = db.execute(sql_text(template), {"tid": tenant_id, "uid": user_id}).fetchall()

            if not rows:
                return {"data": [], "summary": "No active tasks assigned to you"}

            columns = rows[0]._fields if hasattr(rows[0], '_fields') else []
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    row_dict[col] = val
                data.append(row_dict)

            return {"data": data, "count": len(data), "query_type": "task_lookup_user",
                    "summary": f"You have {len(data)} active task(s)"}
        except Exception as e:
            logger.warning(f"User task query failed: {e}")
            return {"data": None, "summary": f"Failed to fetch tasks: {str(e)[:100]}"}

    def _execute_coverage_query(self, db: Session, tenant_id: int) -> Dict[str, Any]:
        """Get requirement coverage summary."""
        try:
            sql = """
                SELECT coverage_status, COUNT(*) as count
                FROM requirement_traces
                WHERE tenant_id = :tid
                GROUP BY coverage_status
            """
            rows = db.execute(sql_text(sql), {"tid": tenant_id}).fetchall()

            if not rows:
                return {"data": [], "summary": "No requirement traces found"}

            total = sum(r[1] for r in rows)
            coverage_data = {
                "total_requirements": total,
                "breakdown": {r[0]: r[1] for r in rows},
            }
            covered = sum(r[1] for r in rows if r[0] in ("fully_covered", "partially_covered"))
            if total > 0:
                coverage_data["coverage_percentage"] = round(covered / total * 100, 1)

            return {"data": coverage_data, "query_type": "coverage_lookup",
                    "summary": f"Requirement coverage: {coverage_data.get('coverage_percentage', 0)}%"}
        except Exception as e:
            logger.warning(f"Coverage query failed: {e}")
            return {"data": None, "summary": f"Failed: {str(e)[:100]}"}

    def _execute_cost_query(self, db: Session, tenant_id: int) -> Dict[str, Any]:
        """Get cost/billing summary."""
        try:
            template = DB_QUERY_TEMPLATES["cost_lookup"]
            rows = db.execute(sql_text(template), {"tid": tenant_id}).fetchall()

            if not rows:
                return {"data": [], "summary": "No usage data found for the last 30 days"}

            columns = rows[0]._fields if hasattr(rows[0], '_fields') else []
            data = []
            total_cost = 0
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    elif isinstance(val, float):
                        val = round(val, 4)
                    row_dict[col] = val
                data.append(row_dict)
                total_cost += float(row_dict.get("total_cost_inr", 0))

            return {"data": data, "total_cost_inr": round(total_cost, 2),
                    "query_type": "cost_lookup",
                    "summary": f"Total AI spend (30 days): ₹{round(total_cost, 2)}"}
        except Exception as e:
            logger.warning(f"Cost query failed: {e}")
            return {"data": None, "summary": f"Failed: {str(e)[:100]}"}

    def _execute_activity_query(self, db: Session, tenant_id: int) -> Dict[str, Any]:
        """Get recent activity."""
        try:
            template = DB_QUERY_TEMPLATES["activity_lookup"]
            rows = db.execute(sql_text(template), {"tid": tenant_id}).fetchall()

            if not rows:
                return {"data": [], "summary": "No activity in the last 7 days"}

            columns = rows[0]._fields if hasattr(rows[0], '_fields') else []
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    row_dict[col] = val
                data.append(row_dict)

            return {"data": data, "count": len(data), "query_type": "activity_lookup",
                    "summary": f"{len(data)} events in the last 7 days"}
        except Exception as e:
            logger.warning(f"Activity query failed: {e}")
            return {"data": None, "summary": f"Failed: {str(e)[:100]}"}


# Module-level singleton
query_orchestrator = QueryOrchestrator()
