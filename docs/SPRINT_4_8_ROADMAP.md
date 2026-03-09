# DokyDoc — Sprint 4-8 Unified Development Roadmap

> **Last Updated:** 2026-03-09
> **Current Sprint:** Sprint 5 (COMPLETE)
> **Next Up:** Sprint 4 (Semantic Search + Validation Enhancement)

---

## 1. Sprint Completion Status

### What's Built (Sprints 1-5)

| Sprint | Feature | Status | Key Files |
|--------|---------|--------|-----------|
| **Sprint 1** | Auth (JWT + RBAC) | COMPLETE | `auth.py`, `AuthContext.tsx` |
| **Sprint 1** | Multi-Tenancy | COMPLETE | Tenant model, middleware, subdomain routing |
| **Sprint 1** | Document Upload + Parsing | COMPLETE | `document_parser.py`, `MultiModalDocumentParser` |
| **Sprint 2** | Multi-Pass Document Analysis (DAE) | COMPLETE | `analysis_service.py`, 3-pass pipeline |
| **Sprint 2** | Billing (Prepaid/Postpaid) | COMPLETE | `billing_enforcement_service.py`, `UsageLog` model |
| **Sprint 2** | CXO/Admin Dashboards | COMPLETE | `cxo/page.tsx`, `admin/page.tsx` (real API data) |
| **Sprint 2** | Role-Based Dashboards | COMPLETE | CXO, Admin, Developer, BA dashboards |
| **Sprint 3** | Code Analysis Engine | COMPLETE | `code_analysis_tasks.py`, enhanced analysis with delta |
| **Sprint 3** | Repository Synthesis (Reduce Phase) | COMPLETE | `repo_synthesis_task` in code_analysis_tasks |
| **Sprint 3** | BOE Knowledge Graphs | COMPLETE | `business_ontology_service.py`, concept extraction |
| **Sprint 3** | Brain Dashboard (L1-5 Navigation) | COMPLETE | `brain/page.tsx`, multi-level graph navigation |
| **Sprint 3** | Graph Versioning | COMPLETE | `KnowledgeGraphVersion` model, diff endpoints |
| **Sprint 3** | Requirement Traceability | COMPLETE | `RequirementTrace` model, auto-trace building |
| **Sprint 3** | Context Assembly (BOE) | COMPLETE | `context_assembly_service.py`, zero-cost DB context |
| **Sprint 4** | Validation Engine Core | COMPLETE | `validation_service.py`, document-code link validation |
| **Sprint 4** | Validation Panel UI | COMPLETE | `validation-panel/page.tsx` |
| **Sprint 5** | Auto-Linking (3-Tier Mapping) | COMPLETE | `mapping_service.py` (exact → fuzzy → AI) |
| **Sprint 5** | Git Webhooks (GitHub/GitLab/Bitbucket) | COMPLETE | `webhooks.py`, push/PR event handling |
| **Sprint 5** | Branch Preview (Ephemeral Redis) | COMPLETE | `cache_service.py`, `branch_preview_extraction` task |
| **Sprint 5** | Audit Trail + Middleware | COMPLETE | `AuditLog` model, `audit_middleware.py`, timeline UI |
| **Sprint 5** | Notifications (Backend + Frontend) | COMPLETE | `notification_service.py`, `NotificationContext.tsx`, bell UI |
| **Sprint 5** | Cursor Pagination | COMPLETE | `pagination.py`, audit/documents/timeline endpoints |
| **Sprint 5** | Notification Auto-Triggers | COMPLETE | Document pipeline + repo analysis triggers |
| **Sprint 5** | Admin Dashboard Real Data | COMPLETE | Users, docs, billing, audit wired to APIs |
| **Sprint 5** | Billing Analytics | COMPLETE | `/billing/analytics`, per-user analytics, CXO charts |
| **Sprint 5** | Mapping Feedback Loop | COMPLETE | `POST /ontology/mappings/{id}/feedback`, threshold calibration |
| **Sprint 5** | Branch Comparison View | COMPLETE | `code/compare/page.tsx`, two-column diff with delta highlights |
| **Sprint 5** | PR Comment Integration | COMPLETE | `pr_comment_service.py`, auto-post analysis summary to PRs |
| **Sprint 5** | Mapping Quality Dashboard | COMPLETE | Brain L5 confidence indicators, quality summary panel |

### What's NOT Built Yet (Sprints 4 Remaining, 6-8)

| Sprint | Feature | Status | Blocked By |
|--------|---------|--------|------------|
| **Sprint 4** | pgvector + Embeddings | NOT BUILT | — |
| **Sprint 4** | Semantic Search API | NOT BUILT | pgvector setup |
| **Sprint 4** | Semantic Search UI | NOT BUILT | Search API |
| **Sprint 4** | Validation Report Export (PDF/JSON) | NOT BUILT | — |
| **Sprint 5** | Mapping Feedback (confirm/reject) | COMPLETE | `concept_mapping.py`, feedback endpoint + threshold tuning |
| **Sprint 5** | Branch Comparison View | COMPLETE | `code/compare/page.tsx`, two-column graph diff |
| **Sprint 5** | PR Comment Integration | COMPLETE | `pr_comment_service.py`, webhook auto-post |
| **Sprint 6** | Approval Workflow | NOT BUILT | — |
| **Sprint 6** | Security Hardening (encryption at rest) | NOT BUILT | — |
| **Sprint 7** | RAG/Chat Assistant | NOT BUILT | Embeddings (Sprint 4) |
| **Sprint 8** | Jira Integration | NOT BUILT | — |
| **Sprint 8** | Slack Integration | NOT BUILT | — |
| **Sprint 8** | Analytics Dashboard (dedicated) | PARTIAL | Billing analytics exist |

---

## 2. Dependency Map

```
Sprint 3 (DONE)                Sprint 4                Sprint 5+              Sprint 7
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ Rich Knowledge   │───►│ pgvector Setup   │    │ Branch Compare  │    │                  │
│ Graphs (BOE)     │    │ + Embeddings     │───►│ View (graph     │    │ RAG/Chat         │
│                  │    │                  │    │ diff UI)        │    │ Assistant        │
│ Graph Versioning │───►│ Semantic Search  │    │                 │    │ (needs embeddings│
│                  │    │ API + UI         │───►│ Mapping Quality │───►│  + graph context) │
│ Requirement      │───►│ Validation       │    │ Improvements    │    │                  │
│ Traces           │    │ Dashboard Enhanc │    │                 │    └──────────────────┘
└──────────────────┘    │ + Report Export  │    │ PR Comment      │
                        └──────────────────┘    │ Integration     │
                                                └─────────────────┘
                                                        │
                        ┌──────────────────┐            │           ┌──────────────────┐
                        │ Sprint 6         │            │           │ Sprint 8         │
                        │ Approval Workflow │◄───────────┘           │ Jira Integration │
                        │ Security Harden  │───────────────────────►│ Slack Integration│
                        │ RBAC Enhancement │                        │ Analytics Dashbd │
                        └──────────────────┘                        └──────────────────┘
```

---

## 3. Sprint 4: Semantic Search + Validation Enhancement

**Goal:** Enable natural-language search across all knowledge (concepts, graphs, documents, code) and enhance validation with export capabilities.

**Prerequisites:** Sprint 3 complete (rich graphs with stored JSON provide the data to embed and validate against).

### S4-1: pgvector Setup & Embedding Infrastructure

#### 4-1a. Enable pgvector Extension
- **File:** `backend/alembic/versions/s4_enable_pgvector.py` (NEW migration)
- `CREATE EXTENSION IF NOT EXISTS vector;`
- Add `embedding` column (`vector(1536)`) to `ontology_concepts` table
- Add `embedding` column (`vector(1536)`) to `knowledge_graph_versions` (embed whole-graph summaries)
- Create HNSW index on embedding columns for fast ANN search

#### 4-1b. Embedding Generation Service
- **File:** `backend/app/services/embedding_service.py` (NEW)
- `generate_embedding(text: str) -> list[float]` — call Gemini/OpenAI embedding API
- `embed_concept(concept: OntologyConcept)` — build text from `name + description + type + relationships` -> embed
- `embed_graph_summary(graph_version: KnowledgeGraphVersion)` — build text from graph metadata -> embed
- Batch processing: `embed_all_concepts(tenant_id)` — process in chunks of 100
- Cost tracking via existing `UsageLog` model

#### 4-1c. Wire Into Extraction Pipeline
- After `_extract_ontology_from_analysis()` creates concepts -> queue `generate_embeddings.delay(concept_ids)`
- After `save_version()` stores graph -> queue `embed_graph_summary.delay(version_id)`
- **File:** `backend/app/tasks/embedding_tasks.py` (NEW Celery task)

### S4-2: Semantic Search API

#### 4-2a. Search Service
- **File:** `backend/app/services/semantic_search_service.py` (NEW)
- `search_concepts(query, tenant_id, filters) -> list[ConceptMatch]`
  - Embed query -> vector similarity search on `ontology_concepts.embedding`
  - Filters: concept_type, source_type, initiative_id, min_confidence
  - Return top-K with similarity scores
- `search_graphs(query, tenant_id) -> list[GraphMatch]`
  - Search across graph summaries for file/domain-level matches
- `find_related(concept_id, depth=1) -> list[RelatedConcept]`
  - Graph traversal + vector similarity for "semantically related but not graph-connected" results

#### 4-2b. Search Endpoints
- **File:** Add to `backend/app/api/endpoints/ontology.py`
```
GET /ontology/search?q=...&type=...&source=...   -> semantic search across concepts
GET /ontology/search/related/{concept_id}         -> related concepts (graph + vector)
```

#### 4-2c. Frontend Search Component
- **File:** `frontend/components/ontology/SemanticSearch.tsx` (NEW)
- Search bar in Brain Dashboard header and Knowledge Graph pages
- Auto-suggest as user types (debounced query)
- Results grouped by: concept type, source file, initiative
- Click result -> navigate to graph containing that concept

### S4-3: Validation Enhancement

#### 4-3a. Validation Dashboard Enhancement
- **File:** `frontend/app/dashboard/validation-panel/page.tsx` (ENHANCE)
- Currently shows mismatches list. Add:
  - Requirement coverage heatmap (from `RequirementTrace` data)
  - Per-document validation summary cards
  - "Run Full Validation" button per linked doc-code pair
  - Timeline of validation runs

#### 4-3b. Validation Report Export
- **File:** `backend/app/api/endpoints/validation.py` (ADD endpoint)
```
GET /validation/report/{initiative_id}?format=pdf|json
```
- **PDF:** Executive summary + requirement traceability matrix + mismatch details
- **JSON:** Structured data for CI/CD integration

### S4 Estimated Effort

| Task | Complexity | Files |
|------|-----------|-------|
| pgvector migration | Low | 1 migration |
| Embedding service | Medium | 1 service + 1 task |
| Semantic search service | Medium | 1 service |
| Search endpoints | Low | 1 endpoint file |
| Frontend search UI | Medium | 1 component + brain page integration |
| Validation dashboard enhance | Medium | 1 page enhancement |
| Report export | Medium | 1 endpoint + PDF generation |

---

## 4. Sprint 5 Remaining: Auto-Linking Polish + Git Flow

**Status:** Core auto-linking (`mapping_service.py`) and Git webhooks are fully built. These items are polish/enhancement.

### S5-R1: Mapping Quality Improvements

#### 5-R1a. Mapping Feedback Loop
- **File:** `backend/app/api/endpoints/ontology.py` (ADD endpoint)
```
POST /ontology/mappings/{mapping_id}/feedback   -> confirm/reject mapping
```
- Users confirm or reject auto-generated mappings
- Feedback stored to improve future matching thresholds
- **File:** `backend/app/services/mapping_service.py` (ENHANCE)
  - Adjust fuzzy matching thresholds based on accumulated feedback data

#### 5-R1b. Cross-Project Mapping Dashboard
- **File:** `frontend/app/dashboard/brain/page.tsx` (ENHANCE Level 5)
- MetaGraphView already shows cross-project links
- Add: mapping confidence indicators, click-to-explore links

### S5-R2: Git Flow Enhancements

#### 5-R2a. Branch Comparison View
- **File:** `frontend/app/dashboard/repositories/[id]/compare/page.tsx` (NEW)
- Uses graph versioning to show diff between branches
- Two-column layout: before/after graph visualization
- Delta highlights: green (added), red (removed), yellow (changed)
- Uses existing `GET /ontology/graph/component/{id}/diff?v1=X&v2=Y` endpoint

#### 5-R2b. PR Analysis Integration
- **File:** `backend/app/api/endpoints/webhooks.py` (ENHANCE)
- On PR merge -> trigger re-analysis of changed files (already exists)
- Add: post analysis summary as PR comment (via GitHub API)
- Add: flag if PR introduces validation mismatches

---

## 5. Sprint 6: Approval Workflow + Security Hardening

**Goal:** Add formal approval gates for critical actions and harden security posture.

### S6-1: Approval Workflow

#### 6-1a. Approval Model
- **File:** `backend/app/models/approval.py` (NEW)
```python
class Approval(Base):
    __tablename__ = "approvals"
    id, tenant_id
    entity_type: str     # "document" | "repository" | "mismatch_resolution" | "requirement_trace"
    entity_id: int
    status: str          # "pending" | "approved" | "rejected" | "revision_requested"
    requested_by_id: int # FK -> User
    approved_by_id: int  # FK -> User (nullable)
    approval_notes: str
    approval_level: int  # 1=developer, 2=lead, 3=CXO
    created_at, updated_at, resolved_at
```

#### 6-1b. Approval Service
- **File:** `backend/app/services/approval_service.py` (NEW)
- Per-tenant approval policies (who can approve what)
- Multi-level approval chains (Developer -> Lead -> CXO)
- Auto-approve low-risk items (e.g., mismatches with "info" severity)
- Gate validation results: mismatches with "critical" severity require CXO sign-off

#### 6-1c. Approval Endpoints
- **File:** `backend/app/api/endpoints/approvals.py` (NEW)
```
GET    /approvals/pending          -> list items awaiting user's approval
POST   /approvals/{id}/approve     -> approve an item
POST   /approvals/{id}/reject      -> reject an item
POST   /approvals/{id}/request-revision -> request changes
GET    /approvals/history          -> audit trail of past decisions
```

#### 6-1d. Frontend Approval UI
- **File:** `frontend/app/dashboard/approvals/page.tsx` (NEW)
- Approval inbox per user (pending items to approve/reject)
- Approval history with audit trail
- In-context approval buttons on mismatch detail, validation result pages

### S6-2: Security Hardening

#### 6-2a. RBAC Enhancement
- Current: roles[] in User model (CXO, Admin, Developer, BA, Product Manager)
- Add: fine-grained permission matrix per role
- Add: route-level permission guards on ALL API endpoints (some currently unguarded)

#### 6-2b. Audit Log Export
- **File:** `backend/app/api/endpoints/audit.py` (ENHANCE)
- Currently has `/audit/export` endpoint (offset-based)
- Add: PDF export for auditors
- Add: date range filtering on export

#### 6-2c. Data Encryption at Rest
- Encrypt sensitive fields (`raw_text`, `structured_data`) at rest
- Key management via environment config
- Transparent encryption/decryption layer in CRUD operations

### S6 Estimated Effort

| Task | Complexity | Files |
|------|-----------|-------|
| Approval model + migration | Low | 1 model + 1 migration |
| Approval service | High | 1 service (multi-level logic) |
| Approval endpoints | Medium | 1 endpoint file |
| Approval UI | Medium | 1 page + inline components |
| RBAC fine-grained permissions | Medium | Enhance auth middleware |
| Audit export PDF | Low | 1 endpoint enhancement |
| Encryption at rest | High | CRUD layer + migration |

---

## 6. Sprint 7: RAG/Chat Assistant

**Goal:** Enable users to ask natural-language questions about their documents, code, and knowledge graphs using retrieval-augmented generation.

**Prerequisites:** Sprint 4 embeddings must be complete (semantic search is the retrieval backbone for RAG).

### S7-1: Data Models

#### 7-1a. Conversation & Message Models
- **File:** `backend/app/models/conversation.py` (NEW)
```python
class Conversation(Base):
    __tablename__ = "conversations"
    id, tenant_id, user_id, title
    context_type: str      # "general" | "document" | "repository" | "initiative"
    context_id: int | None # Scoped to specific entity
    created_at, updated_at

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id, conversation_id, role  # "user" | "assistant"
    content: str
    context_used: dict (JSONB)  # Which concepts/files were retrieved
    token_count: int
    cost_inr: float
    created_at
```

### S7-2: RAG Service

#### 7-2a. Retrieval + Generation Pipeline
- **File:** `backend/app/services/rag_service.py` (NEW)
- `retrieve_context(query, tenant_id, context_type, context_id) -> RetrievedContext`
  1. Semantic search -> top-K relevant concepts (Sprint 4 embeddings)
  2. Graph expansion -> walk edges from matched concepts for neighborhood
  3. Fetch graph JSON from `knowledge_graph_versions` (pre-built, fast)
  4. Fetch relevant `structured_analysis` snippets for code context
  5. Fetch relevant `structured_data` snippets for document context
  6. Assemble into context window respecting token limits
- `generate_answer(query, context, conversation_history) -> Answer`
  - Send context + query to Gemini/Claude
  - Include conversation history for multi-turn support
  - Track cost via `UsageLog` (FeatureType.CHAT)

### S7-3: Chat API

#### 7-3a. Chat Endpoints
- **File:** `backend/app/api/endpoints/chat.py` (NEW)
```
POST   /chat/conversations                   -> create conversation
GET    /chat/conversations                   -> list user's conversations
POST   /chat/conversations/{id}/messages     -> send message, get AI response
GET    /chat/conversations/{id}/messages     -> message history
DELETE /chat/conversations/{id}              -> delete conversation
```

### S7-4: Chat Frontend

#### 7-4a. Chat Interface
- **File:** `frontend/app/dashboard/chat/page.tsx` (NEW)
- Conversation sidebar with history
- Context-aware: can ask "What does auth_service do?" -> uses BOE knowledge
- Code snippets in answers with syntax highlighting
- "Ask about this file" button on code detail pages -> opens chat with file context
- "Ask about this requirement" button on validation pages

### S7 Estimated Effort

| Task | Complexity | Files |
|------|-----------|-------|
| Conversation models + migration | Low | 2 models + 1 migration |
| CRUD for conversations/messages | Low | 2 CRUD files |
| RAG service (retrieval + generation) | High | 1 service (core logic) |
| Chat endpoints | Medium | 1 endpoint file |
| Chat frontend | High | 1 page + components |

---

## 7. Sprint 8: External Integrations + Analytics Dashboard

**Goal:** Connect DokyDoc to external tools (Jira, Slack) and provide a dedicated analytics dashboard.

### S8-1: Jira Integration

#### 8-1a. Jira Service
- **File:** `backend/app/services/integrations/jira_service.py` (NEW)
- OAuth 2.0 Jira Cloud authentication
- Sync mismatches -> Jira issues (auto-create bug tickets from validation failures)
- Sync tasks <-> Jira issues (bidirectional)
- Map Jira epics -> DokyDoc initiatives

#### 8-1b. Jira Settings UI
- **File:** `frontend/app/settings/integrations/jira/page.tsx` (NEW)
- Per-tenant Jira connection settings
- Field mapping configuration
- Sync trigger: manual or automatic

### S8-2: Slack Integration

#### 8-2a. Slack Service
- **File:** `backend/app/services/integrations/slack_service.py` (NEW)
- Slack App installation (OAuth)
- Deliver notifications to Slack channels (extend existing `notification_service.py`)
- Slash commands: `/dokydoc search <query>` -> semantic search in Slack
- Weekly digest: post summary of validation status to team channel

#### 8-2b. Slack Settings UI
- **File:** `frontend/app/settings/integrations/slack/page.tsx` (NEW)
- Channel configuration per notification type
- Digest schedule settings

### S8-3: Dedicated Analytics Dashboard

**Note:** Billing analytics already exist (`/billing/analytics`, per-user analytics, cost breakdown by feature/operation). This sprint adds a unified analytics view.

#### 8-3a. Analytics Service
- **File:** `backend/app/services/analytics_service.py` (NEW)
- Aggregate `UsageLog` data into time-series metrics
- Metrics: AI cost per tenant/month, analysis throughput, validation coverage trends, concept growth
- Cache computed metrics (Redis) for fast dashboard loads

#### 8-3b. Analytics Endpoints
- **File:** `backend/app/api/endpoints/analytics.py` (NEW)
```
GET /analytics/costs?period=month&tenant_id=...      -> cost breakdown
GET /analytics/coverage?initiative_id=...            -> validation coverage over time
GET /analytics/concepts?tenant_id=...&period=week    -> concept growth trend
GET /analytics/activity?tenant_id=...                -> user activity metrics
```

#### 8-3c. Analytics Frontend
- **File:** `frontend/app/dashboard/analytics/page.tsx` (NEW)
- Cost charts (line graph per month, pie chart by feature type)
- Validation coverage trend (line graph showing % coverage improvement)
- Knowledge graph growth (concept/relationship count over time)
- Team activity heatmap

### S8 Estimated Effort

| Task | Complexity | Files |
|------|-----------|-------|
| Jira service + OAuth | High | 1 service + settings |
| Jira settings UI | Medium | 1 page |
| Slack service + OAuth | High | 1 service + settings |
| Slack settings UI | Medium | 1 page |
| Analytics service | Medium | 1 service |
| Analytics endpoints | Low | 1 endpoint file |
| Analytics frontend | High | 1 page + chart components |

---

## 8. Sprint Execution Timeline

| Sprint | Duration | Focus | Prerequisites |
|--------|----------|-------|---------------|
| **Sprint 5** | Completing | Audit trail, notifications, pagination, admin dashboard | Sprint 3 |
| **Sprint 4** | Next | pgvector, semantic search, validation export | Sprint 3 graphs + traces |
| **Sprint 5 Remaining** | After S4 | Mapping feedback, branch compare, PR comments | Graph versioning (done) |
| **Sprint 6** | After S5R | Approval workflow, security hardening, RBAC | Task model (exists) |
| **Sprint 7** | After S6 | RAG/chat assistant | Sprint 4 embeddings |
| **Sprint 8** | After S7 | Jira, Slack, analytics dashboard | Sprint 7 notifications |

> **Note:** Sprint numbers reflect logical grouping, not strict sequential order. Sprint 4's semantic search work runs after Sprint 5 completion because Sprint 5 was prioritized for audit/notification features.

---

## 9. Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
├─────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ CXO     │ Admin    │ Developer│ Brain    │ Chat     │ Analytics│
│ Dash    │ Dash     │ Dash     │ Dashboard│ (S7)     │ (S8)     │
├─────────┴──────────┴──────────┴──────────┴──────────┴──────────┤
│ Notifications │ Validation Panel │ Audit Trail │ Approvals (S6)│
├───────────────┴──────────────────┴─────────────┴───────────────┤
│                      API Layer (FastAPI)                        │
├────────────┬──────────┬──────────┬──────────┬──────────────────┤
│ Auth/RBAC  │ Documents│ Billing  │ Ontology │ Webhooks         │
│ (JWT)      │ + Code   │ Analytics│ + Search │ (GitHub/GitLab)  │
├────────────┴──────────┴──────────┴──────────┴──────────────────┤
│                     Service Layer                               │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│ DAE      │ Code     │ Mapping  │ RAG      │ Integrations       │
│ (3-pass) │ Analysis │ (3-tier) │ (S7)     │ Jira/Slack (S8)   │
│          │ + Synth  │          │          │                    │
├──────────┼──────────┼──────────┼──────────┼────────────────────┤
│ Billing  │ Notif    │ Approval │ Semantic │ Analytics          │
│ Enforce  │ Service  │ (S6)     │ Search   │ Service (S8)       │
│          │          │          │ (S4)     │                    │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│                     Data Layer                                  │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│ PostgreSQL│ Redis   │ pgvector │ Celery   │ File Storage       │
│ (all     │ (cache, │ (S4)     │ (workers)│ (uploads)          │
│  models) │  preview)│          │          │                    │
└──────────┴──────────┴──────────┴──────────┴────────────────────┘
```

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Polling for notifications** (30s interval) | Simpler than WebSockets; notifications are non-critical latency |
| **Cursor pagination** over offset | Better performance for large datasets; no row-skip overhead |
| **Fail-silent notifications** | Notification failures must never break main operations |
| **pgvector over external vector DB** | Keep everything in PostgreSQL; simpler ops, same transaction guarantees |
| **RAG uses pre-built graph JSON** | Avoid expensive graph computation at query time; graphs stored by versioning system |
| **Branch preview in Redis** (ephemeral) | Feature branch analysis is temporary; auto-expires, no DB bloat |
| **Approval model is generic** (entity_type + entity_id) | One approval system for documents, mismatches, traces, etc. |
| **Billing auto-deduction in AI calls** | Centralized in `generate_content()` — no manual deduction needed per feature |

---

## 11. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| pgvector extension not available in hosted PostgreSQL | Blocks Sprint 4 | Verify provider supports pgvector; fallback to external Pinecone/Weaviate |
| Gemini embedding API cost | Medium | Batch processing, cache embeddings, skip re-embedding unchanged concepts |
| RAG context window limits | Medium | Intelligent truncation in `rag_service.py`; prioritize high-relevance chunks |
| Jira OAuth complexity | Low | Use official `jira-python` library; follow Atlassian's documented OAuth 2.0 flow |
| Multi-level approval latency | Low | Auto-approve low-risk items; notification reminders for pending approvals |
