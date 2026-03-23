# AskyDoc: Complete Implementation Plan — Organization's Personal GPT

## Status: APPROVED AND EXECUTING
Plan was approved by user who said "Okay now start building this". Implementation is actively in progress.
- Task 1: DONE (Org Profile schemas + endpoints added to tenant.py)
- Task 2: DONE (query_orchestrator.py created with DB-first intelligence)
- Task 3-7: Next up (RAG service rewrite with role-awareness, citations, model selection)
- Tasks 8-18: Pending

## Context

DokyDoc has a partially-built chat assistant (Sprint 7 V1) with scaffolding but shallow implementation. The RAG relies on ILIKE keyword matching, there's no role-awareness, no org context, no intelligent query orchestration, no model selection, no source citations, no markdown rendering, no billing integration, no audit trail, and no tests.

**The Vision:** AskyDoc is the organization's personal GPT — like ChatGPT/Gemini/Cursor but trained on YOUR organization's data. It doesn't just search documents — it **decomposes complex questions**, **queries the database directly** (zero AI cost), and only calls AI for synthesis. Users can **select their AI model** (Gemini/Claude) just like in Cursor.

**What AskyDoc Does:**
- **CXO asks**: "How can we increase revenue?" → gets strategic business insights with org context
- **Developer asks**: "When was auth feature first developed? What business impact does it have? What changes are required? Rate the UI." → AskyDoc decomposes this into 4 sub-queries, pulls data from audit_logs + analysis_results + mismatches + ontology (all zero cost), then synthesizes one cohesive answer with AI
- **New joiner asks**: "I'm new, explain what this organization does" → gets onboarding-style explanation
- **Anyone**: switches model from Gemini to Claude mid-conversation if they prefer
- **Anyone on any page**: clicks "Ask AI about this" → opens scoped conversation

**Core Innovation — DB-First Intelligence:**
```
User Question → Decompose into Sub-Queries → Classify Each (DB vs AI)
→ Execute DB Queries (₹0 cost) → Assemble Context → AI Synthesis (1 call)
```

Instead of the traditional RAG approach (search everything → send all to AI), AskyDoc pulls **structured answers from the database first** and only uses AI to synthesize/format. This cuts AI costs by 60-80%.

---

## Architecture: The Query Orchestration Engine

### How AskyDoc Processes a Complex Question

**Example Question:** *"When was the auth feature first developed and what impact it has on business. What changes required. Rate the UI of this feature. What is the daily hit on this API."*

**Step 1: Question Decomposition (lightweight AI call ~200 tokens)**
```
Input: "When was auth feature first developed and what impact it has on business.
        What changes required. Rate the UI. What is the daily hit on this API."

Output (structured JSON):
{
  "sub_queries": [
    {"id": 1, "question": "When was the auth feature first developed?", "type": "temporal_lookup"},
    {"id": 2, "question": "What business impact does the auth feature have?", "type": "business_analysis"},
    {"id": 3, "question": "What changes are required for the auth feature?", "type": "gap_analysis"},
    {"id": 4, "question": "Rate the UI of the auth feature", "type": "evaluation"},
    {"id": 5, "question": "What is the daily API hit count for auth?", "type": "metrics_lookup"}
  ]
}
```

**Step 2: Intent Classification + DB Query Routing (zero AI cost)**

| Sub-Query | Classification | Data Source | AI Needed? |
|-----------|---------------|-------------|------------|
| When was auth first developed? | `temporal_lookup` | `audit_logs` WHERE action=create, resource_name LIKE '%auth%' | NO — pure DB |
| Business impact? | `business_analysis` | `ontology_concepts` + `requirement_traces` + `consolidated_analyses.data` | PARTIAL — DB data exists, AI synthesizes |
| What changes required? | `gap_analysis` | `mismatches` WHERE code_component related to auth + `code_components.analysis_delta` | PARTIAL — DB data exists, AI synthesizes |
| Rate the UI? | `evaluation` | No DB data for subjective UI rating | YES — AI judgment needed |
| Daily API hits? | `metrics_lookup` | `usage_logs` GROUP BY DATE WHERE operation involves auth endpoints | NO — pure DB |

**Step 3: DB Query Execution (₹0 cost, ~50ms)**
```sql
-- Sub-query 1: When first developed
SELECT resource_name, created_at, user_email, description
FROM audit_logs WHERE tenant_id = :tid
  AND action = 'create' AND resource_name ILIKE '%auth%'
ORDER BY created_at ASC LIMIT 5;

-- Sub-query 3: Changes required (mismatches)
SELECT m.description, m.severity, m.details, cc.name, cc.location
FROM mismatches m JOIN code_components cc ON m.code_component_id = cc.id
WHERE m.tenant_id = :tid AND cc.name ILIKE '%auth%' AND m.status != 'resolved';

-- Sub-query 5: Daily API hits
SELECT DATE(created_at) as day, COUNT(*) as hits, SUM(cost_inr) as cost
FROM usage_logs WHERE tenant_id = :tid AND operation ILIKE '%auth%'
GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 30;
```

**Step 4: Context Assembly (₹0 cost)**
```
DB RESULTS:
- Auth feature first created: 2026-01-15 by dev@company.com (Sprint 1)
- 3 open mismatches: [password hashing inconsistency (High), JWT expiry mismatch (Medium), ...]
- Auth module concepts: [JWT Authentication, RBAC, Multi-tenancy, Session Management]
- Requirement coverage: 85% (12/14 requirements covered)
- Daily hits last 7 days: [142, 156, 131, 168, 145, 139, 152]
- Business concepts linked: [User Onboarding, Access Control, Data Security]
```

**Step 5: AI Synthesis (1 call, ~2000 tokens — the ONLY paid call)**
```
System: You are AskyDoc. Using the DB results below, answer the user's compound question.
        For "Rate the UI" — provide your assessment based on the available UI-related data.
        Format as a structured response with sections for each sub-question.

Context: {assembled DB results}
Question: {original compound question}
```

**Result: 5 questions answered with only 1 AI call instead of 5.**

---

## The Queryable Knowledge Map

### What AskyDoc Can Answer From DB Alone (₹0 cost):

| Question Category | DB Source | Example |
|------------------|-----------|---------|
| **Temporal** ("when was X created/changed?") | `audit_logs` | "When was billing module first developed?" |
| **Cost/Billing** ("how much did X cost?") | `usage_logs` | "Total AI spend this month?" |
| **Metrics** ("how many X?") | `usage_logs`, `documents`, `code_components` | "Daily API hits for auth?" |
| **Status** ("what's the status of X?") | `documents.status`, `analysis_runs`, `repositories` | "Which documents are still processing?" |
| **Coverage** ("what % of X is Y?") | `requirement_traces` | "What's our requirement coverage?" |
| **Mismatches** ("what's wrong with X?") | `mismatches` | "Show critical code-doc mismatches" |
| **Ownership** ("who owns X?") | `documents.owner_id`, `tasks.assigned_to_id` | "Who uploaded this document?" |
| **Tasks** ("what's assigned to me?") | `tasks` | "Show my overdue tasks" |
| **Activity** ("what happened recently?") | `audit_logs` | "Show all changes in last 24 hours" |
| **Structure** ("what functions/classes in X?") | `code_components.structured_analysis` | "List all API endpoints in auth module" |

### What Needs AI Synthesis (uses DB data as context):

| Question Category | DB Context Used | AI Does |
|------------------|----------------|---------|
| **Business Impact** | ontology_concepts + requirement_traces + analysis_results | Synthesizes narrative |
| **Recommendations** | mismatches + analysis_delta + structured_analysis | Suggests actions |
| **Explanations** | consolidated_analyses.data + document_segments | Explains in role-appropriate language |
| **Comparisons** | Multiple DB sources | Compares and contrasts |
| **Subjective Evaluation** | Available metrics + analysis data | Provides assessment |

### What Requires Full AI (no DB shortcut):

| Question Category | When |
|------------------|------|
| **Creative** ("suggest a name for...") | No DB data relevant |
| **Hypothetical** ("what if we...") | Requires reasoning beyond data |
| **External** ("how does competitor X...") | Data not in DB |

---

## Model Selection — User's Choice (Like Cursor)

### How It Works:

**Conversation Model:** Add `model_preference` field to `Conversation` model.
- Default: `"gemini"` (Gemini 2.5 Flash — fastest, cheapest)
- Optional: `"claude"` (Claude Sonnet — better for code/reasoning)
- Stored per-conversation so user can use different models for different tasks

**Frontend: Model Selector Dropdown**
```
┌─────────────────────────────────────────────┐
│ AskyDoc                    [Gemini ▼] [CXO] │
│ Your org's AI knowledge expert              │
├─────────────────────────────────────────────┤
│                                             │
│  Model options:                             │
│  ● Gemini 2.5 Flash (Default — Fast)        │
│  ○ Claude Sonnet (Better for Code)          │
│                                             │
```

**Backend Routing:**
```python
# In rag_service.generate_answer():
if conversation.model_preference == "claude" and provider_router.claude_available:
    result = await provider_router.claude.generate_content(prompt, ...)
else:
    result = await provider_router.gemini.generate_content(prompt, ...)
```

**Cost Transparency:** Show estimated cost per model in the selector:
- Gemini 2.5 Flash: ~₹0.15/query (input: $0.15/1M, output: $3.50/1M)
- Claude Sonnet: ~₹0.40/query (higher but better for complex reasoning)

---

## Implementation — 18 Tasks in 5 Phases

### Phase 1: Core Intelligence Engine (Tasks 1-7)

---

#### Task 1: Organization Profile via Tenant Settings

Store org metadata that AskyDoc always has access to, using existing `Tenant.settings["org_profile"]`.

**File: `backend/app/schemas/tenant.py`**
- Add `OrgProfileUpdate` schema: `mission`, `products_services` (list), `industry`, `company_description`, `key_objectives` (list)
- Add `OrgProfileResponse` schema

**File: `backend/app/api/endpoints/tenants.py`**
- `PUT /tenants/org-profile` — protected by `TENANT_MANAGE` permission
- `GET /tenants/org-profile` — any authenticated user

**Reuse:** `Tenant.settings` column (JSONB, `server_default='{}'`). No migration needed.

---

#### Task 2: Query Orchestration Engine (THE CORE INNOVATION)

**File:** `backend/app/services/query_orchestrator.py` (NEW)

This is the brain of AskyDoc. It replaces the naive "search everything → dump into AI" approach with an intelligent multi-step pipeline.

**Class: `QueryOrchestrator`**

```python
class QueryOrchestrator:
    """
    Decomposes complex questions into sub-queries, routes each to the
    optimal data source (DB or AI), and assembles results for synthesis.
    """

    async def process_query(self, query, tenant_id, user_roles, db, model_preference) -> OrchestratedResult:
        # Step 1: Classify the query complexity
        complexity = self._classify_complexity(query)

        if complexity == "simple":
            # Single intent — skip decomposition
            return await self._process_single_query(query, tenant_id, user_roles, db, model_preference)

        # Step 2: Decompose compound question (lightweight AI call ~200 tokens)
        sub_queries = await self._decompose_question(query, model_preference)

        # Step 3: For each sub-query, classify intent and route
        results = []
        for sq in sub_queries:
            intent = self._classify_intent(sq)

            if intent.data_source == "db_only":
                # Pure DB query — ₹0 cost
                result = self._execute_db_query(db, tenant_id, sq, intent)
            elif intent.data_source == "db_plus_ai":
                # DB context + AI synthesis
                db_context = self._execute_db_query(db, tenant_id, sq, intent)
                result = {"db_data": db_context, "needs_synthesis": True}
            else:
                # Full AI needed
                result = {"db_data": None, "needs_synthesis": True}

            results.append({"sub_query": sq, "result": result, "intent": intent})

        # Step 4: Assemble all DB results as context
        assembled_context = self._assemble_context(results)

        # Step 5: Single AI synthesis call for all sub-queries that need it
        return assembled_context

    def _classify_intent(self, query: str) -> QueryIntent:
        """Rule-based intent classification (zero AI cost)."""
        INTENT_PATTERNS = {
            "temporal_lookup": ["when was", "first created", "first developed", "history of", "timeline"],
            "metrics_lookup": ["how many", "daily hit", "api calls", "count of", "total number"],
            "cost_lookup": ["how much cost", "spending", "budget", "expense", "billing"],
            "status_lookup": ["status of", "progress of", "what state", "is it complete"],
            "coverage_lookup": ["coverage", "percentage", "how much is covered", "gaps"],
            "mismatch_lookup": ["what's wrong", "mismatches", "issues", "problems", "errors"],
            "ownership_lookup": ["who owns", "who created", "who uploaded", "assigned to"],
            "task_lookup": ["my tasks", "overdue", "assigned", "pending tasks"],
            "activity_lookup": ["recent changes", "what happened", "activity", "last updated"],
            "structure_lookup": ["functions in", "classes in", "endpoints", "architecture of"],
            "business_analysis": ["business impact", "revenue", "value", "strategic"],
            "gap_analysis": ["changes required", "what needs", "improvements", "fix"],
            "evaluation": ["rate", "evaluate", "assess", "score", "quality of"],
            "explanation": ["explain", "what is", "how does", "describe", "summarize"],
        }
        # Match query against patterns, return QueryIntent with data_source routing
```

**DB Query Templates (zero cost execution):**

```python
DB_QUERY_TEMPLATES = {
    "temporal_lookup": """
        SELECT resource_name, created_at, user_email, action, description
        FROM audit_logs WHERE tenant_id = :tid
          AND resource_name ILIKE :q AND action IN ('create', 'update')
        ORDER BY created_at ASC LIMIT 10
    """,
    "metrics_lookup": """
        SELECT DATE(created_at) as day, COUNT(*) as count,
               SUM(cost_inr) as total_cost
        FROM usage_logs WHERE tenant_id = :tid AND operation ILIKE :q
        GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 30
    """,
    "cost_lookup": """
        SELECT feature_type, SUM(cost_inr) as total, COUNT(*) as operations,
               SUM(input_tokens) as tokens_in, SUM(output_tokens) as tokens_out
        FROM usage_logs WHERE tenant_id = :tid
          AND created_at >= :start_date
        GROUP BY feature_type ORDER BY total DESC
    """,
    "mismatch_lookup": """
        SELECT m.description, m.severity, m.status, m.details,
               cc.name as component, cc.location
        FROM mismatches m
        LEFT JOIN code_components cc ON m.code_component_id = cc.id
        WHERE m.tenant_id = :tid AND m.status != 'resolved'
          AND (m.description ILIKE :q OR cc.name ILIKE :q)
        ORDER BY CASE m.severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        LIMIT 20
    """,
    "coverage_lookup": """
        SELECT coverage_status, COUNT(*) as count,
               ROUND(COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER(), 0) * 100, 1) as percentage
        FROM requirement_traces WHERE tenant_id = :tid
        GROUP BY coverage_status
    """,
    # ... more templates for each intent type
}
```

**Reuse:** All existing CRUD operations: `crud.usage_log`, `crud.audit_log`, `crud.requirement_trace`, `crud.mismatch`, `crud.code_component`, `crud.document`, `crud.ontology_concept`.

---

#### Task 3: Enhanced RAG Retrieval Pipeline (6 Stages)

**File:** `backend/app/services/rag_service.py` (rewrite core methods)

This works alongside the Query Orchestrator for questions that need semantic search:

```
Stage 1: SEMANTIC CONCEPT SEARCH (existing — keep)
Stage 2: GRAPH EXPANSION + CROSS-GRAPH via ConceptMapping (enhance)
Stage 3: ANALYSIS RESULT RETRIEVAL from consolidated_analyses (NEW)
Stage 4: DOCUMENT SEGMENT SEARCH with role-based prioritization (enhance)
Stage 5: CODE COMPONENT SEARCH including structured_analysis JSONB (enhance)
Stage 6: REQUIREMENT TRACES (NEW)
```

**Extend `RetrievedContext`** with `analysis_summaries`, `cross_graph_links`, `requirement_traces`.

**Token Budget Manager:** Raise `MAX_CONTEXT_TOKENS` from 6000 to 8000. Priority-based trimming.

---

#### Task 4: Role-Aware System Prompts + Org Context

**File:** `backend/app/services/rag_service.py`

- `_get_org_context(db, tenant_id)` — fetches org profile from Tenant.settings
- `_get_role_instructions(user_roles)` — maps roles to communication directives (CXO=strategy, Developer=technical depth, BA=requirements, Auditor=compliance)
- Rewrite `_build_prompt()` — AskyDoc persona with org context, role instructions, citation rules
- Role-based retrieval priority weights

---

#### Task 5: Source Citations in AI Responses

**File:** `backend/app/services/rag_service.py`

- `_extract_citations(answer_text, context)` — parses `[Doc: ...]`, `[Code: ...]`, `[Concept: ...]` patterns
- Maps to entity IDs for clickable frontend links
- Store in `context_used` JSON on ChatMessage

**File:** `backend/app/schemas/conversation.py` — Add `CitationItem` schema

---

#### Task 6: Model Selection (User's Choice — Like Cursor)

**File: `backend/app/models/conversation.py`**
- Add `model_preference: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini")`
- Values: `"gemini"` (default), `"claude"`
- Requires Alembic migration

**File: `backend/app/schemas/conversation.py`**
- Add `model_preference: Optional[str]` to `ConversationCreate` and `ConversationResponse`

**File: `backend/app/api/endpoints/chat.py`**
- In `create_conversation()`: accept `model_preference` from payload
- In `send_message()`: pass `conversation.model_preference` to the orchestrator
- Add `PUT /chat/conversations/{id}/model` endpoint to switch model mid-conversation

**File: `backend/app/services/rag_service.py`**
- In `generate_answer()`: route to selected provider
```python
if model_preference == "claude" and provider_router.claude_available:
    result = await provider_router.claude.generate_content(prompt, ...)
else:
    result = await provider_router.gemini.generate_content(prompt, ...)
```

**File: `frontend/app/dashboard/chat/page.tsx`**
- Model selector dropdown in chat header (next to role badge)
- Show model name + estimated cost per query
- Persist selection per conversation
- Options: "Gemini 2.5 Flash (Fast)" / "Claude Sonnet (Deep Reasoning)"

---

#### Task 7: Smart Provider Routing (Auto-Detection)

When model_preference is `"auto"` (or not explicitly set by user):

```python
def _auto_select_model(self, query, context):
    """Auto-select best model based on question type."""
    if self._is_code_question(query, context):
        return "claude"  # Better for code understanding
    return "gemini"  # Faster + cheaper for general/business
```

This is the default behavior. User can override by selecting a specific model.

---

### Phase 2: Backend Hardening (Tasks 8-12)

---

#### Task 8: RBAC + Billing + Usage Logging Integration

**CRITICAL GAP:** Chat usage NOT logged to `usage_logs`. `FeatureType.CHAT` exists but is never called. No billing pre-check.

**File: `backend/app/core/permissions.py`** — Add `CHAT_USE` permission
**File: `backend/app/api/endpoints/chat.py`** — Add billing pre-check, usage logging, RBAC guard

---

#### Task 9: Audit Trail Integration for Chat

**CRITICAL GAP:** `/api/v1/chat` NOT in `TRACKED_PREFIXES` in audit middleware.

**File: `backend/app/middleware/audit_middleware.py`** — Add `"/api/v1/chat"` to TRACKED_PREFIXES

---

#### Task 10: Role-Based Suggested Prompts API

**File:** `backend/app/api/endpoints/chat.py`

`GET /chat/suggested-prompts` — returns role-specific starter questions. CXO gets business prompts, Developer gets technical prompts, new joiners get onboarding prompts.

---

#### Task 11: Message Feedback (Thumbs Up/Down)

**File: `backend/app/models/conversation.py`** — Add `feedback` column to ChatMessage
**File: `backend/app/api/endpoints/chat.py`** — Add `POST /chat/messages/{id}/feedback`
**Migration** required for new column.

---

#### Task 12: Conversation Management + Rate Limiting + Error Handling + Export

- Conversation search (`GET /conversations/search?q=...`)
- Rate limiting (20 msg/min per user)
- Graceful error handling (RAG fails → empty context, AI fails → error message)
- Conversation export (`GET /conversations/{id}/export?format=json`)
- Max conversation length check (>200 messages → suggest new conversation)

---

### Phase 3: Frontend Polish (Tasks 13-16)

---

#### Task 13: Frontend — AskyDoc Branding + Role UI + Markdown + Model Selector

**File:** `frontend/app/dashboard/chat/page.tsx`

- **AskyDoc branding** (replace "DokyDoc AI Assistant")
- **Model selector dropdown** in header (Gemini / Claude)
- **Role badge** showing current role mode
- **Markdown rendering** with react-markdown + syntax highlighting
- **Source citation chips** (clickable, linked to entities)
- **Message feedback** (thumbs up/down buttons)
- **Dynamic suggested prompts** from API
- **Conversation search** in sidebar
- **Context type selector** (General / Document / Repository / Initiative)
- **URL param handling** for contextual entry points
- **Query plan visibility** — show "Searching database..." → "Found 3 records" → "Synthesizing answer..." (like Claude's thinking)

---

#### Task 14: Global AskyDoc Access — Header + Sidebar + Dashboards

- **Sidebar:** Add "AskyDoc" as primary nav item (#2 after Dashboard)
- **Header:** Add AskyDoc icon button (always visible)
- **CXO Dashboard:** "Ask about costs" quick-action
- **Developer Dashboard:** "Ask about mismatches" quick-action
- **BA Dashboard:** "Ask about documents" quick-action

---

#### Task 15: Contextual Entry Points ("Ask About This")

- Documents page: "Ask AI about this document" button
- Code page: "Ask AI about this codebase" button
- Brain page: "Ask about this concept" button
- Validation panel: "Explain this mismatch" button
- Chat page reads URL params on mount to auto-create scoped conversations

---

#### Task 16: Backend Branding Cleanup

Update chatbot persona from "DokyDoc" to "AskyDoc" in rag_service.py, Sidebar, Header.

---

### Phase 4: Adoption & Onboarding (Task 17)

---

#### Task 17: Notification Bridge + Contextual Onboarding

- Analysis complete notifications include "Ask AskyDoc about it →" link
- First-time onboarding card with role-specific example questions
- "Set up org profile for better answers" prompt for CXO/Admin

---

### Phase 5: Testing (Task 18)

---

#### Task 18: Comprehensive Tests (42 total)

**`test_chat_api.py` (22 tests):** Conversations, messages, billing, rate limiting, feedback, model selection, suggested prompts

**`test_conversation_crud.py` (9 tests):** CRUD operations, search, export

**`test_rag_service.py` (11 tests):** Retrieval, prompt building, role-awareness, citations, model routing, query orchestration

---

## Execution Order

```
Phase 1: Core Intelligence Engine (THE DIFFERENTIATOR)
  Task 1  → Org Profile endpoints
  Task 2  → Query Orchestration Engine (DB-first intelligence)
  Task 3  → Enhanced 6-stage RAG retrieval
  Task 4  → Role-aware prompts + org context
  Task 5  → Source citations
  Task 6  → Model selection (Gemini / Claude toggle)
  Task 7  → Smart auto-routing

Phase 2: Backend Hardening (COMPLIANCE & BILLING)
  Task 8  → RBAC + billing + usage logging
  Task 9  → Audit trail for chat
  Task 10 → Suggested prompts API
  Task 11 → Message feedback
  Task 12 → Conversation mgmt + rate limiting + export

Phase 3: Frontend Polish (USER EXPERIENCE)
  Task 13 → Full chat UI (branding, markdown, model selector, feedback, query plan)
  Task 14 → Global access (header, sidebar, dashboard widgets)
  Task 15 → Contextual entry points
  Task 16 → Branding cleanup

Phase 4: Adoption & Onboarding
  Task 17 → Notifications + onboarding

Phase 5: Testing
  Task 18 → 42 comprehensive tests
```

---

## Key Existing Code to Reuse

| What | Where | How |
|------|-------|-----|
| Tenant.settings JSONB | `models/tenant.py:45` | Store org_profile without migration |
| User.roles | `models/user.py` | `current_user.roles` in every endpoint |
| useAuth() | `contexts/AuthContext.tsx` | Frontend role detection (28+ files) |
| PermissionChecker | `core/permissions.py` | Role hierarchy + permission checking |
| ConsolidatedAnalysis | `models/consolidated_analysis.py` | Pre-synthesized analysis (skip re-analysis) |
| RequirementTrace | `models/requirement_trace.py` | Coverage data for DB queries |
| ConceptMapping | `models/concept_mapping.py` | Cross-graph links |
| SemanticSearchService | `services/semantic_search_service.py` | RAG Stage 1 |
| ProviderRouter | `services/ai/provider_router.py` | Model routing |
| BillingEnforcementService | `services/billing_enforcement_service.py` | Balance pre-check |
| FeatureType.CHAT | `models/usage_log.py` | Exists but never wired |
| TRACKED_PREFIXES | `middleware/audit_middleware.py` | Missing `/api/v1/chat` |
| crud.usage_log | `crud/crud_usage_log.py` | Has `get_total_summary()`, `get_by_feature()`, `get_daily_usage()`, `get_user_summary()` |
| crud.audit_log | `crud/crud_audit_log.py` | Has `get_stats()`, `get_timeline()` |
| crud.requirement_trace | `crud/crud_requirement_trace.py` | Has `get_coverage_summary()` |
| audit_logs table | `models/audit_log.py` | Tracks create/update/delete with timestamps |
| usage_logs table | `models/usage_log.py` | Tracks API hits, costs, tokens per operation |
| mismatches table | `models/mismatch.py` | Code-doc mismatches with severity/status |
| code_components.structured_analysis | `models/code_component.py` | Pre-extracted functions, classes, APIs |
| code_components.analysis_delta | `models/code_component.py` | What changed since last analysis |

---

## Deferred to Sprint 8+

| Feature | Why Deferred | Sprint |
|---------|-------------|--------|
| **Streaming/SSE responses** | Requires architectural changes to both AI clients + FastAPI SSE + frontend streaming UI | 8 |
| **Conversation pinning/favorites** | Nice UX, not core | 8 |
| **AI-generated conversation titles** | Extra AI cost per conversation | 8 |
| **Auto-extract org profile from documents** | Complex — requires scanning all docs for org-level info | 8 |
| **Floating chat widget** | Complex React portal + state management | 9+ |
| **i18n / Multi-language** | No i18n infrastructure exists | 9+ |

---

## Verification Plan

### Manual Testing:
1. **Compound Question**: Ask "When was auth developed? What's its business impact? What changes needed? Daily API hits?" → Verify decomposition, DB queries, single AI synthesis
2. **Model Selection**: Switch from Gemini to Claude mid-conversation → verify response uses Claude
3. **DB-Only Question**: Ask "How much did we spend on AI this month?" → verify ₹0 AI cost (pure DB)
4. **Org Profile**: Set mission/products → ask "What does our company do?" → verify org context used
5. **Role-Aware**: Same question as CXO vs Developer → different tone/depth
6. **Citations**: Any question → source badges appear with entity links
7. **Billing**: Zero balance → 402 error
8. **Audit**: Send chat message → verify audit log entry
9. **Usage Logging**: Send message → verify usage_logs populated with feature_type=chat
10. **Feedback**: Thumbs up/down → stored correctly
11. **Global Access**: AskyDoc visible in sidebar + header
12. **Dashboard Widgets**: CXO/Dev/BA have "Ask AI" quick-actions
13. **Contextual Entry**: Click "Ask AI" on document page → scoped conversation opens

### Automated Testing:
```bash
cd backend
python -m pytest app/tests/test_chat_api.py -v          # 22 tests
python -m pytest app/tests/test_conversation_crud.py -v  # 9 tests
python -m pytest app/tests/test_rag_service.py -v        # 11 tests
```

### Build Verification:
```bash
cd frontend && npm run build   # No TypeScript errors
cd backend && python -m pytest app/tests/ -v  # Full test suite passes
```
