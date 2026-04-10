# DokyDoc — Comprehensive Phase-Wise Implementation Master Plan
# Expert Solution Architect + Product Owner Edition
# Branch: claude/autodocs-multiple-sources-MbvDe

---

## HOW TO USE THIS PLAN

Each phase is **independently implementable** by a separate solution architect.
- Phases marked **[PARALLEL-SAFE]** have no dependencies on later phases and can start immediately.
- Phases marked **[DEPENDS: Px]** must wait for their dependency to merge first.
- All changes are **non-breaking** — wrapped in try/except, guarded by feature flags or tier checks.
- Naming convention for migrations: `s{phase}{seq}_{description}.py` (e.g., `s11a1_code_data_flow_edges.py`)

---

## CURRENT STATE SNAPSHOT (as of April 2026)

### What's Already Built
- 26 API endpoint routers (auth, docs, code, ontology, validation, billing, chat, etc.)
- 31 database models fully migrated (42 Alembic migrations)
- 9-Pass Atomic Validation Engine (RequirementAtom → 8 forward + 1 reverse pass)
- 3-Tier Algorithmic Mapping (Exact → Fuzzy/Levenshtein → AI, ~97% cost reduction)
- Business Ontology Engine (concepts, relationships, cross-graph mapping)
- Egocentric Knowledge Graph (bidirectional artifact navigation, `source_component_id` on nodes)
- Code Analysis Engine (ENHANCED_SEMANTIC_ANALYSIS prompt, structured_analysis JSON)
- RAG/Chat Assistant, Auto-Docs, Jira/Confluence integrations
- Multi-tenant RBAC, Audit Trail, Approval Workflow, Notifications
- Vector embeddings (768-dim, pgvector) on OntologyConcept — currently UNUSED in mapping

### What's Missing (ordered by business impact)
1. Cosine similarity in Tier 2 mapping (embeddings generated but ignored)
2. Training examples / data flywheel table (can never be recovered retroactively)
3. Data Flow Diagrams (premium visual feature)
4. 4-Engine integration (validation isolated from BOE)
5. Dynamic prompting (static prompts, no industry/glossary context)
6. Tenant intelligence (no website URL, no industry profile, no self-learning glossary)
7. File upload size limits artificially capped (must be removed)
8. Performance: missing pagination on several endpoints
9. LLM strategy foundation (training pipeline not started)

---

## PHASE 0 — Critical Bugs, Security & Performance Baseline
**Priority: DO FIRST. Blocks all other phases.**
**Parallel-safe: YES (no dependencies)**
**Estimated complexity: Medium**

### Context
The platform is in active use. Before layering new features, harden the foundation.
These are bugs and gaps from the V2 audit that can silently corrupt data or expose vulnerabilities.

### P0.1 — Remove Artificial File Size Limits
**Problem:** Current code enforces hard-coded upload size limits that prevent large BRDs, SRS docs, and codebases from being analyzed. This is a product capability limitation, not a technical requirement.

**Files to change:**
- `backend/app/api/endpoints/documents.py` — Remove any `MAX_FILE_SIZE` checks
- `backend/app/api/endpoints/repositories.py` — Remove file count/size guards
- `backend/main.py` — Check if `upload_max_size` is set in FastAPI config; remove limit
- `backend/app/core/config.py` — Remove or raise `MAX_UPLOAD_SIZE_MB` to unlimited (or 2GB)
- Frontend: Remove any client-side file size validation warnings

**Strategy:** Replace hard limits with soft warnings. If a file is > 50MB, show a banner "Large file — analysis may take longer" but do NOT block the upload. Stream analysis in chunks if needed.

### P0.2 — Pagination on All List Endpoints
**Problem:** Several GET list endpoints return ALL records with no cursor/page — will OOM at scale.

**Endpoints missing proper pagination:**
- `GET /api/v1/ontology/concepts` — must add `skip`, `limit`, `cursor`
- `GET /api/v1/code-components/` — verify limit is enforced (current default=100, max=1000)
- `GET /api/v1/documents/` — verify
- `GET /api/v1/ontology/relationships` — add pagination
- `GET /api/v1/audit/logs` — add `start_date`, `end_date`, `limit` filters
- `GET /api/v1/validation/{document_id}/atoms` — paginate RequirementAtom list

**Implementation:** Add `X-Total-Count` response header. Use SQLAlchemy `.offset(skip).limit(limit)`. For cursor-based (audit logs), use `id > cursor` pattern.

### P0.3 — CORS Hardening
**Problem:** `settings.CORS_ORIGINS` may be `["*"]` in staging, leaking credentials cross-origin.

**File:** `backend/app/core/config.py`
- Validate `CORS_ORIGINS` is never `["*"]` when `ENVIRONMENT != "development"`
- Add `CORS_ALLOW_CREDENTIALS = True` only when origins are explicitly whitelisted
- Startup check: if `ENVIRONMENT == "production"` and `"*"` in `CORS_ORIGINS`, raise `RuntimeError`

### P0.4 — Rate Limiter Coverage Gap
**Problem:** `slowapi` limiter is initialized but not applied to all sensitive endpoints.

**Files:**
- `backend/app/api/endpoints/login.py` — Verify `@limiter.limit("5/minute")` on POST /login
- `backend/app/api/endpoints/tenants.py` — Add `@limiter.limit("3/minute")` on POST /register
- `backend/app/api/endpoints/documents.py` — Add `@limiter.limit("20/minute")` on POST (upload)
- `backend/app/api/endpoints/validation.py` — Add `@limiter.limit("10/minute")` on run_validation

### P0.5 — Tenant Isolation Enforcement Audit
**Problem:** Some endpoints depend on `tenant_id` from JWT but may fall back to `None` if middleware fails, leaking cross-tenant data.

**Action:**
- Audit all `crud.X.get()` calls that accept `tenant_id` parameter — ensure no `tenant_id=None` path returns data
- Add a startup test: create 2 tenants, upload a document to tenant A, verify tenant B's token returns 404
- `backend/app/api/deps.py` — `get_tenant_id()` must raise 401, never return `None`

### P0.6 — Celery Task Idempotency
**Problem:** If `process_document_pipeline` runs twice (Celery retry on network blip), it can create duplicate OntologyConcepts.

**File:** `backend/app/services/business_ontology_service.py`
- `get_or_create_concept()` already uses `name + tenant_id` as unique key — verify this is enforced at DB level with a unique constraint
- Migration: Add `UniqueConstraint("name", "tenant_id", "source_type", name="uq_concept_name_tenant_source")` if missing

### P0.7 — Frontend Error Boundary
**Problem:** JavaScript errors in Mermaid rendering crash the whole page.

**File:** `frontend/app/dashboard/brain/page.tsx`, `frontend/app/dashboard/code/[id]/page.tsx`
- Wrap `<MermaidDiagram />` in a React `ErrorBoundary` component
- On error: show "Diagram rendering failed" card with retry button

### P0.8 — Missing JiraItem in models/__init__.py
**Problem:** The `JiraItem` model exists (`backend/app/models/jira_item.py`) but may not be imported in `__init__.py`, causing Alembic to miss it.

**File:** `backend/app/models/__init__.py`
- Add: `from .jira_item import JiraItem`
- Verify: `from .concept_mapping import ConceptMapping` is present

### Verification
- Run `alembic check` — zero pending migrations
- Run `pytest backend/tests/` — all existing tests pass
- Manually test: upload a 10MB PDF — verify no 413 error
- Manually test: call `GET /api/v1/ontology/concepts?skip=0&limit=10` — verify pagination headers

---

## PHASE 1 — Data Flywheel & Training Infrastructure
**Priority: START IMMEDIATELY. Every day without this loses training data.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Estimated complexity: Medium**

### Context
The most valuable asset DokyDoc can accumulate is **labeled examples of correct/incorrect AI decisions**. When a developer looks at a mismatch and clicks "Accept" or "Reject", that signal is worth gold for future model fine-tuning. This data can NEVER be recovered retroactively — it must be captured from day 1. This phase creates the infrastructure. The UI buttons are intentionally simple: 3 clicks max.

### P1.1 — New DB Model: `TrainingExample`
**New file:** `backend/app/models/training_example.py`

```python
class TrainingExample(Base):
    __tablename__ = "training_examples"

    id: int (PK)
    tenant_id: int (FK tenants.id, indexed)

    # What generated this example
    example_type: str  # "mismatch_judgment", "mapping_judgment", "atom_judgment"
    source_id: int     # FK to mismatch.id / concept_mapping.id / requirement_atom.id (no FK constraint — flexible)
    source_table: str  # "mismatches" / "concept_mappings" / "requirement_atoms"

    # The input context (what AI saw)
    input_context: dict (JSON)  # Full prompt context: concept names, code snippet, document excerpt

    # The AI's output (what AI said)
    ai_output: dict (JSON)      # AI judgment: { match: true/false, confidence: 0.87, reasoning: "..." }

    # The human correction (what human said)
    human_label: str            # "accepted", "rejected", "edited"
    human_correction: dict | None (JSON)  # If edited: { correct_answer: "...", notes: "..." }

    # Who labeled it
    labeled_by_user_id: int | None (FK users.id)
    labeled_at: datetime | None

    # Metadata for fine-tuning data export
    is_exported: bool (default False)     # Whether included in a training export
    export_batch_id: str | None           # Which training batch this went into
    quality_score: float | None           # Set after model evaluation (0.0-1.0)

    created_at: datetime
```

**New migration:** `backend/alembic/versions/s12a1_training_examples.py`

### P1.2 — CRUD for TrainingExample
**New file:** `backend/app/crud/crud_training_example.py`

Methods:
- `create_from_mismatch(db, mismatch_id, tenant_id, ai_output, input_context)` → TrainingExample
- `record_human_label(db, example_id, label, correction=None, user_id=None)` → TrainingExample
- `get_unlabeled(db, tenant_id, example_type=None, limit=50)` → List[TrainingExample]
- `get_export_batch(db, tenant_id, min_quality=None, limit=1000)` → List[TrainingExample]
- `get_label_stats(db, tenant_id)` → dict with counts by example_type and human_label

Add to `backend/app/crud/__init__.py`: `from .crud_training_example import training_example`
Add to `backend/app/models/__init__.py`: `from .training_example import TrainingExample`

### P1.3 — Auto-Capture on Mismatch Creation
**File:** `backend/app/services/validation_service.py`

After each mismatch is created (around the `crud.mismatch.create()` call in `validate_single_link`), add a non-blocking capture:

```python
# Capture training example (non-blocking, fire-and-forget)
try:
    crud.training_example.create_from_mismatch(
        db=db,
        mismatch_id=new_mismatch.id,
        tenant_id=tenant_id,
        ai_output={
            "verdict": pass_result.get("verdict"),
            "confidence": pass_result.get("confidence"),
            "reasoning": pass_result.get("reasoning"),
        },
        input_context={
            "atom_content": atom.content,
            "atom_type": atom.atom_type,
            "code_context": pass_result.get("code_context"),
            "pass_name": pass_name,
        }
    )
except Exception:
    pass  # NEVER let this block validation
```

### P1.4 — Auto-Capture on Concept Mapping
**File:** `backend/app/services/mapping_service.py`

After AI validates a pair in Tier 3 (around line 297), capture:
```python
crud.training_example.create_from_mismatch(
    db=db, source_table="concept_mappings",
    source_id=mapping.id, tenant_id=tenant_id,
    ai_output={"relationship_type": ai_result, "confidence": ai_confidence},
    input_context={"doc_concept": doc_name, "code_concept": code_name}
)
```

### P1.5 — Accept/Reject UI on Mismatch Cards
**File:** `frontend/app/dashboard/validation-panel/page.tsx`

Add to each mismatch card:
```tsx
<div className="flex gap-2 mt-2">
  <button
    onClick={() => recordFeedback(mismatch.id, 'accepted')}
    className="text-xs px-2 py-1 bg-green-100 hover:bg-green-200 text-green-800 rounded"
  >
    ✓ Correct
  </button>
  <button
    onClick={() => recordFeedback(mismatch.id, 'rejected')}
    className="text-xs px-2 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded"
  >
    ✗ Wrong
  </button>
  <button
    onClick={() => setEditingMismatch(mismatch.id)}
    className="text-xs px-2 py-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-800 rounded"
  >
    ✎ Correct it
  </button>
</div>
```

New API call: `POST /api/v1/validation/mismatches/{id}/feedback`
Body: `{ label: "accepted"|"rejected"|"edited", correction?: string }`

### P1.6 — Feedback Endpoint
**File:** `backend/app/api/endpoints/validation.py`

```python
@router.post("/mismatches/{mismatch_id}/feedback")
def record_mismatch_feedback(
    mismatch_id: int,
    label: str,  # "accepted", "rejected", "edited"
    correction: Optional[str] = None,
    ...
):
    # 1. Find training_example for this mismatch
    # 2. Call crud.training_example.record_human_label()
    # 3. Update concept_mapping.feedback_label for threshold calibration
    # 4. Return 200
```

### P1.7 — Training Data Export Endpoint (Admin only)
**File:** `backend/app/api/endpoints/analytics.py`

```
GET /api/v1/analytics/training-data/export?tenant_id=X&format=jsonl&min_quality=0.7
→ Returns JSONL file of TrainingExample rows in OpenAI fine-tune format
→ Admin-only endpoint (role check: superadmin)
```

### P1.8 — Label Quality Dashboard
**File:** `frontend/app/dashboard/analytics/page.tsx`

Add a "Training Data" card showing:
- Total examples captured: N
- Labeled / Unlabeled breakdown
- Acceptance rate by pass type (API_CONTRACT, BUSINESS_RULE, etc.)
- "Export for Training" button (admin only)

### Verification
1. Run validation on any document → check `SELECT COUNT(*) FROM training_examples` increases
2. Click "Correct" on a mismatch → `SELECT human_label FROM training_examples WHERE source_id = X` = "accepted"
3. Call `GET /api/v1/analytics/training-data/export` → downloads valid JSONL

---

## PHASE 2 — Mapping Intelligence Upgrade (Cosine Similarity)
**Priority: Quick win. 5-line fix with massive accuracy gain.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Estimated complexity: Low**

### Context
The 3-tier mapping engine's Tier 2 uses Levenshtein string distance — which fails for semantic synonyms like "User Account" vs "Customer Profile". The OntologyConcept model already stores 768-dimensional embeddings via `text-embedding-004` (confirmed: `backend/app/services/embedding_service.py`). These embeddings are GENERATED but IGNORED in `mapping_service.py`. This fix costs $0 and improves mapping accuracy by ~30%.

### P2.1 — Add Cosine Similarity to Tier 2
**File:** `backend/app/services/mapping_service.py`

Add this function after `_levenshtein_similarity()`:
```python
def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two embedding vectors. Returns 0.0-1.0."""
    if not vec_a or not vec_b:
        return 0.0
    import math
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
```

In the Tier 2 matching loop, replace the pure Levenshtein check with:
```python
# Existing: levenshtein only
lev_score = _levenshtein_similarity(norm_doc, norm_code)

# NEW: add cosine similarity if embeddings available
cos_score = 0.0
if doc_concept.embedding_vector and code_concept.embedding_vector:
    cos_score = _cosine_similarity(doc_concept.embedding_vector, code_concept.embedding_vector)

# Composite score: cosine is more reliable for semantic matching
composite_score = max(token_overlap, lev_score, cos_score)
```

Add `COSINE_SIMILARITY_THRESHOLD = 0.80` constant. Pairs where `cos_score >= 0.80` skip AI validation entirely (Tier 2 confidence = high).

### P2.2 — Embedding Coverage Check
**File:** `backend/app/services/mapping_service.py`

Before running mapping for a tenant, check embedding coverage:
```python
total = db.query(OntologyConcept).filter_by(tenant_id=tenant_id).count()
embedded = db.query(OntologyConcept).filter(
    OntologyConcept.tenant_id == tenant_id,
    OntologyConcept.embedded_at.isnot(None)
).count()
coverage = embedded / total if total > 0 else 0
```
Log warning if coverage < 80%. Trigger background embedding generation if coverage < 50%.

### P2.3 — Background Embedding Backfill Task
**File:** `backend/app/tasks/ontology_tasks.py`

Add new task:
```python
@celery_app.task(name="backfill_embeddings")
def backfill_embeddings(tenant_id: int):
    """Generate embeddings for all OntologyConcepts that don't have one yet."""
    # Query concepts where embedded_at IS NULL
    # Call embedding_service.generate_and_store(concept)
    # Process in batches of 50 (embedding API rate limits)
```

Auto-trigger from `run_cross_graph_mapping` if coverage < 80%.

### P2.4 — Threshold Update in Calibration
**File:** `backend/app/services/mapping_service.py`, `calibrate_thresholds()` method

Add cosine threshold calibration based on TrainingExample feedback (P1). When cosine-matched pairs are consistently rejected, raise `COSINE_SIMILARITY_THRESHOLD`. When pairs below threshold are accepted by users, lower it.

### Verification
1. Find two concepts with embeddings: run `SELECT name, embedding_vector IS NOT NULL FROM ontology_concepts LIMIT 10`
2. Manually call `run_full_mapping` with logging at DEBUG level
3. Verify logs show "cosine_score: 0.92" for semantically related pairs
4. Verify "Payment" ↔ "PaymentProcessor" maps correctly (previously failed with Levenshtein)

---

## PHASE 3 — Request Data Flow Diagrams (Premium Visual Feature)
**Priority: High — core differentiator, zero re-analysis cost**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: High**

### Context
When a developer opens `api/endpoints/users.py` today they see raw JSON. A BA, PM or CXO opening the same file sees nothing useful. The Data Flow Diagram feature assembles a visual swimlane showing exactly what happens when someone hits an API endpoint:

> POST /register → AuthService.validate() → UserCreateSchema (email, password, name) → UserCRUD.create() → users table (id, email, password_hash) → SendGrid API

**Zero re-analysis cost** — all data already exists in `CodeComponent.structured_analysis` (api_contracts, data_flows, component_interactions, internal_imports). 4 new fields are extracted in the SAME AI call for newly analyzed files (no extra cost). Premium gate: free tier sees blurred preview + upsell. Existing knowledge graph / ontology engine is NOT touched.

### P3.1 — Enhance ENHANCED_SEMANTIC_ANALYSIS Prompt (Additive)
**File:** `backend/app/services/ai/prompt_manager.py`

Add 4 new **optional** fields to the prompt JSON output spec, after `data_flows`. Old analyses still work — fields simply absent. New analyses get them for free in the same call.

Fields to add to the output JSON schema section of the prompt:

```
"file_role": "ENDPOINT" | "SERVICE" | "SCHEMA" | "MODEL" | "CRUD" |
             "REPOSITORY" | "MIDDLEWARE" | "UTILITY" | "CONFIG" | "TEST"
  // Normalized role — more stable than the 17-value file_type

"backed_by_model": {   // Only for SCHEMA files
  "table_name": "users",
  "model_class": "User",
  "fields": [
    {"schema_field": "email", "model_column": "email", "type": "EmailStr"},
    {"schema_field": "id", "model_column": "id", "type": "int"}
  ]
}

"model_definition": {   // Only for MODEL files
  "table_name": "users",
  "columns": [
    {"name": "id", "type": "Integer", "primary_key": true, "nullable": false},
    {"name": "email", "type": "String", "nullable": false, "indexed": true}
  ]
}

"outbound_calls": [   // For ENDPOINT / SERVICE / CRUD files
  {
    "caller_function": "create_user",
    "target_module": "services/auth_service",
    "target_function": "AuthService.register",
    "data_in": "UserCreateRequest",
    "data_out": "User"
  }
]
```

Add human-readable explanation above the JSON schema block. Mark all 4 fields as "OPTIONAL — include only when applicable to this file type." This ensures backward compatibility with existing structured_analysis records.

### P3.2 — New DB Model: `CodeDataFlowEdge`
**New file:** `backend/app/models/code_data_flow_edge.py`

```python
class CodeDataFlowEdge(Base):
    __tablename__ = "code_data_flow_edges"

    id: int (PK, autoincrement)
    tenant_id: int (FK tenants.id, indexed)
    repository_id: int (FK repositories.id, indexed)
    source_component_id: int (FK code_components.id, indexed)
    target_component_id: int | None (FK code_components.id, nullable)  # NULL = external system
    source_function: str | None
    target_function: str | None
    edge_type: str  # HTTP_TRIGGER | SERVICE_CALL | SCHEMA_VALIDATION |
                    # DB_READ | DB_WRITE | EXTERNAL_API | CACHE | EVENT
    data_in_description: str | None   # "UserCreateRequest (email, password)"
    data_out_description: str | None  # "User object"
    human_label: str | None           # "Validates registration form fields"
    external_target_name: str | None  # "SendGrid API", "Redis" when target_component_id is NULL
    step_index: int | None            # Ordering within a request trace
    created_at: datetime (default utcnow)
```

**New migration:** `backend/alembic/versions/s13a1_code_data_flow_edges.py`

Add to `backend/app/models/__init__.py`:
```python
from .code_data_flow_edge import CodeDataFlowEdge
```

### P3.3 — CRUD: `crud_code_data_flow_edge`
**New file:** `backend/app/crud/crud_code_data_flow_edge.py`

Methods:
- `get_by_source(db, component_id, tenant_id)` → outgoing edges
- `get_by_target(db, component_id, tenant_id)` → incoming edges ("who calls me")
- `get_egocentric(db, component_id, tenant_id)` → both in + out combined
- `delete_by_component(db, component_id, tenant_id)` → for re-analysis / rebuild
- `bulk_create(db, edges: list[dict])` → batch insert, returns count

Add to `backend/app/crud/__init__.py`:
```python
from .crud_code_data_flow_edge import code_data_flow_edge
```

### P3.4 — New Service: `DataFlowService`
**New file:** `backend/app/services/data_flow_service.py`

#### Method 1: `build_flow_for_component(db, component_id, tenant_id) -> dict`
Zero AI cost — deterministic parse of existing `structured_analysis`:

```
1. Load CodeComponent + structured_analysis JSON
2. Infer file_role:
   - Use new field `structured_analysis.file_role` if present
   - Fallback: map from `language_info.file_type`:
     Controller/Route → ENDPOINT
     Service → SERVICE
     Model/Migration → MODEL
     Schema → SCHEMA
     Repository/CRUD → CRUD
3. Build outgoing edges:
   a. From `api_contracts` → HTTP_TRIGGER edges (only if ENDPOINT)
   b. From `outbound_calls` (new field) → SERVICE_CALL edges
   c. From `component_interactions` (existing) → SERVICE_CALL edges (fallback)
   d. From `data_flows` containing "DB"/"database" → DB_READ or DB_WRITE edges
   e. From `data_flows` containing "external"/"API" → EXTERNAL_API edges
   f. From `backed_by_model` (new field) → SCHEMA_VALIDATION edges
4. Resolve target_component_id: match `target_module` against
   CodeComponent.location in same repository (same logic as
   build_graph_from_code_component in business_ontology_service.py)
5. Generate human_label via template:
   HTTP_TRIGGER: "User calls {method} {path}"
   SERVICE_CALL: "{caller} invokes {callee}"
   SCHEMA_VALIDATION: "Data validated against {schema} ({field_count} fields)"
   DB_READ: "Reads from {table}"
   DB_WRITE: "Saves to {table}"
   EXTERNAL_API: "Calls external: {name}"
6. Delete old edges for this component (idempotent rebuild)
7. Bulk insert new edges
8. Return { edges_created: int, file_role: str }
```

#### Method 2: `get_request_trace(db, component_id, tenant_id, max_depth=5) -> dict`
BFS from an endpoint through all connected edges:

```
1. BFS: start at component_id, follow target_component_id links
2. Stop at max_depth=5 or when no outbound edges remain
3. Collect all nodes: load CodeComponent for each
4. For MODEL nodes: extract model_definition columns from structured_analysis
5. For SCHEMA nodes: extract backed_by_model fields from structured_analysis
6. Build response:
   {
     nodes: [{ id, component_id, file_role, name, location, human_label,
               model_columns?, schema_fields? }],
     edges: [{ source_component_id, target_component_id, edge_type,
               source_function, target_function, human_label, step_index }],
     mermaid_technical: "...",
     mermaid_simple: "..."
   }
```

#### Method 3: `render_mermaid(nodes, edges, mode) -> str`
Converts trace to Mermaid flowchart with swimlane groupings:

**Technical mode:**
```mermaid
flowchart LR
  subgraph API_Layer["API Layer"]
    EP[UserEndpoint\ncreate_user]
  end
  subgraph Business_Logic["Business Logic"]
    SVC[AuthService\nregister]
  end
  subgraph Data_Layer["Data Layer"]
    SCH[UserCreateSchema\nemail · password]
    CRUD[UserCRUD\ncreate]
  end
  subgraph Storage["Storage"]
    DB[(users table\nid · email · password_hash)]
  end
  subgraph External["External"]
    EXT{{SendGrid API}}
  end
  U([User]) -->|POST /register| EP
  EP -->|calls| SVC
  SVC -->|validates| SCH
  SVC -->|writes via| CRUD
  CRUD -->|INSERT| DB
  SVC -->|email| EXT
  click EP "/dashboard/code/42"
  click SVC "/dashboard/code/17"
```

**Simple (Business) mode:** Same structure, human labels only, no function names, swimlane labels: "Entry Point / Processing / Validation / Database / External Services"

Node click directives navigate to `/dashboard/code/{component_id}` using existing `MermaidDiagram.tsx` `onNodeClick` prop.

### P3.5 — Hook into Analysis Pipeline (Non-Breaking)
**File:** `backend/app/services/code_analysis_service.py`

After the existing ontology extraction call (~line 616), add:

```python
# Step 7: Build data flow edges (premium only — zero extra AI cost)
try:
    tenant = crud.tenant.get(db=db, id=tenant_id)
    if tenant and tenant.tier in ("pro", "enterprise"):
        from app.services.data_flow_service import DataFlowService
        DataFlowService().build_flow_for_component(
            db=db, component_id=component.id, tenant_id=tenant_id
        )
except Exception as e:
    self.logger.warning(f"Data flow extraction failed (non-fatal): {e}")
```

Critical: wrapped in `try/except` — NEVER breaks existing analysis. Premium gate via `tenant.tier`.

### P3.6 — Backfill Celery Task
**New file:** `backend/app/tasks/data_flow_tasks.py`

```python
@celery_app.task(name="backfill_data_flow_edges")
def backfill_data_flow_edges(repo_id: int, tenant_id: int):
    """
    Build data flow edges for all already-analyzed components in a repo.
    Non-blocking: per-component errors do not stop batch.
    Useful after: tenant upgrades from free → pro, or after prompt enhancement.
    """
    components = crud.code_component.get_by_repository(db, repo_id, tenant_id)
    results = {"success": 0, "failed": 0}
    for component in components:
        try:
            DataFlowService().build_flow_for_component(db, component.id, tenant_id)
            results["success"] += 1
        except Exception as e:
            logger.warning(f"Backfill failed for component {component.id}: {e}")
            results["failed"] += 1
    return results
```

Register task module in `backend/app/worker.py`:
```python
include=["app.tasks", "app.tasks.ontology_tasks",
         "app.tasks.code_analysis_tasks", "app.tasks.data_flow_tasks"]
```

### P3.7 — New API Endpoints
**File:** `backend/app/api/endpoints/code_components.py`

Add 3 new endpoints:

```
GET /api/v1/code-components/{id}/data-flow
  Description: Egocentric flow for this file (edges in + out)
  Premium gate: 403 if tenant.tier == "free"
  Response: {
    file_role: str,
    edges_in: [CodeDataFlowEdge],
    edges_out: [CodeDataFlowEdge],
    mermaid_technical: str,
    mermaid_simple: str
  }

GET /api/v1/code-components/{id}/request-trace
  Description: Full BFS request trace from this component (up to depth 5)
  Premium gate: 403 if tenant.tier == "free"
  Query params: depth=5, mode=technical|simple
  Response: {
    nodes: [...],
    edges: [...],
    mermaid_technical: str,
    mermaid_simple: str
  }

POST /api/v1/code-components/{id}/data-flow/rebuild
  Description: Trigger backfill for single component (re-analysis or upgrade)
  Premium gate: same
  Response: 202 Accepted { task_id: "..." }
```

Add Pydantic response schemas to `backend/app/schemas/code_component.py`:
- `DataFlowResponse`
- `RequestTraceResponse`
- `DataFlowNode`
- `DataFlowEdgeResponse`

### P3.8 — Frontend: "Data Flow" Tab
**File:** `frontend/app/dashboard/code/[id]/page.tsx`

Add new "Data Flow" tab to the existing tab bar:

```tsx
// New tab definition (add to existing tabs array):
{ id: 'dataflow', label: 'Data Flow', icon: <GitBranch className="h-4 w-4" /> }

// New state:
const [flowData, setFlowData] = useState<RequestTraceResponse | null>(null)
const [flowMode, setFlowMode] = useState<'technical' | 'simple'>('technical')
const [flowView, setFlowView] = useState<'file' | 'trace'>('trace')
const [flowLoading, setFlowLoading] = useState(false)

// Fetch on tab activate:
useEffect(() => {
  if (activeTab === 'dataflow') fetchFlow()
}, [activeTab])

const fetchFlow = async () => {
  setFlowLoading(true)
  const endpoint = flowView === 'trace'
    ? `/api/v1/code-components/${id}/request-trace`
    : `/api/v1/code-components/${id}/data-flow`
  const res = await fetch(endpoint, { headers: authHeaders })
  if (res.status === 403) { setIsPremiumGated(true); return }
  setFlowData(await res.json())
  setFlowLoading(false)
}
```

**Tab content structure:**
```tsx
{activeTab === 'dataflow' && (
  <div>
    {/* Free tier: blurred preview + upsell */}
    {isPremiumGated ? (
      <div className="relative">
        <div className="blur-sm pointer-events-none opacity-40">
          <div className="h-64 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg
                          flex items-center justify-center">
            <span className="text-4xl">📊</span>
          </div>
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
          <h3 className="font-semibold text-lg">Data Flow Diagrams</h3>
          <p className="text-sm text-gray-500 text-center max-w-sm">
            See exactly how data moves through your codebase. Available on Pro and Enterprise plans.
          </p>
          <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
            Upgrade to Pro
          </button>
        </div>
      </div>
    ) : (
      <>
        {/* View toggle: This File vs Full Trace */}
        <div className="flex gap-2 mb-3">
          <button onClick={() => { setFlowView('trace'); fetchFlow() }}
                  className={flowView === 'trace' ? 'btn-active' : 'btn'}>
            Full Request Trace
          </button>
          <button onClick={() => { setFlowView('file'); fetchFlow() }}
                  className={flowView === 'file' ? 'btn-active' : 'btn'}>
            This File Only
          </button>
        </div>

        {/* Mode toggle: Technical vs Business */}
        <div className="flex gap-2 mb-4">
          <button onClick={() => setFlowMode('technical')}
                  className={flowMode === 'technical' ? 'btn-active' : 'btn'}>
            Technical View
          </button>
          <button onClick={() => setFlowMode('simple')}
                  className={flowMode === 'simple' ? 'btn-active' : 'btn'}>
            Business View
          </button>
        </div>

        {/* Mermaid diagram — clicks navigate to other code files */}
        {flowData && (
          <MermaidDiagram
            syntax={flowMode === 'technical'
              ? flowData.mermaid_technical
              : flowData.mermaid_simple}
            title="Request Data Flow"
            height="500px"
            onNodeClick={(nodeId) => router.push(`/dashboard/code/${nodeId}`)}
          />
        )}

        {/* Connected files panel */}
        {flowData && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="border rounded-lg p-3">
              <h4 className="text-sm font-medium mb-2">
                Calls ({flowData.edges?.filter(e => e.source_component_id === id).length})
              </h4>
              {/* list of outgoing edges */}
            </div>
            <div className="border rounded-lg p-3">
              <h4 className="text-sm font-medium mb-2">
                Called By ({flowData.edges?.filter(e => e.target_component_id === id).length})
              </h4>
              {/* list of incoming edges */}
            </div>
          </div>
        )}

        {/* Rebuild button */}
        <button onClick={rebuildFlow}
                className="mt-3 text-xs text-gray-400 hover:text-gray-600">
          Rebuild diagram
        </button>
      </>
    )}
  </div>
)}
```

### P3.9 — Admin Backfill Endpoint
**File:** `backend/app/api/endpoints/repositories.py`

```
POST /api/v1/repositories/{id}/backfill-data-flow
  Description: Trigger data flow edge generation for all components in repo
  Auth: admin or repo owner
  Action: Dispatches backfill_data_flow_edges Celery task
  Response: 202 Accepted { task_id: "...", component_count: N }
```

### What Does NOT Change in Phase 3
- `_extract_ontology_from_analysis()` — untouched
- `OntologyConcept` / `OntologyRelationship` tables — untouched
- Existing code analysis pipeline — new step is additive, try/except guarded
- All existing endpoints — untouched
- Existing `structured_analysis` schema — new fields are additive/optional

### Verification
1. Prompt change: Re-analyze a schema file → `structured_analysis.file_role == "SCHEMA"` and `backed_by_model` populated
2. Edge creation: `SELECT edge_type, COUNT(*) FROM code_data_flow_edges GROUP BY edge_type`
3. Trace: `GET /api/v1/code-components/{endpoint_id}/request-trace` → nodes for endpoint → service → schema → model
4. Mermaid render: Paste `mermaid_technical` into mermaid.live → swimlane renders correctly
5. Node click: Click SERVICE node in frontend diagram → navigates to `/dashboard/code/{id}`
6. Premium gate: Free tier hits `/data-flow` endpoint → 403 with `{"detail": "..."}`
7. Blurred preview: Free tier UI shows blurred diagram + "Upgrade to Pro" button
8. Non-breaking: Run full validation + knowledge graph extraction → zero errors

---

## PHASE 4 — 4-Engine Integration (Document + Code + BOE + Validation)
**Priority: Highest long-term ROI. Eliminates ~75-80% of Gemini API cost per scan.**
**Parallel-safe: NO [DEPENDS: Phase 0]**
**Estimated complexity: Very High**

### Context
DokyDoc has 4 engines that operate as complete silos today:

| Engine | What it does | Where |
|--------|-------------|-------|
| Document Engine | Parses BRDs, extracts text, creates segments | `document_pipeline.py`, `document_parser.py` |
| Code Engine | Analyzes code files, creates structured_analysis | `code_analysis_service.py` |
| Business Ontology Engine (BOE) | Extracts concepts from both, maps them | `business_ontology_service.py`, `mapping_service.py` |
| Validation Engine (9-pass) | Atomizes BRDs, checks each atom against code | `validation_service.py` |

**The critical gap (confirmed by grep — zero cross-references):**
- Validation Engine re-atomizes documents it has NEVER seen before — BOE already did this
- Validation Engine calls Gemini 9 times per link to check concepts BOE already mapped
- Validation Engine writes mismatches but NEVER updates BOE confidence scores
- BOE extracts concept gaps but validation never reads them
- Result: ~9 Gemini calls per BRD-code link, duplicate work, divergent confidence

**After integration:**
- BRD upload deposits RequirementAtoms immediately (free, reused in validation)
- Validation reads BOE concept mappings before calling Gemini (auto-resolve HIGH confidence matches)
- Validation reads BOE gaps → auto-flag MISSING/UNDOCUMENTED atoms (0 Gemini calls)
- Validation writes results back to BOE (confidence calibration, relationship discovery)
- Net: ~9 calls → ~2 calls per link (75-80% reduction)

### P4.1 — Document Upload Deposits RequirementAtoms
**File:** `backend/app/tasks/document_pipeline.py`

Currently the pipeline flow is: upload → parse → embed → ontology extraction.
Add atom extraction as a new non-blocking step:

```python
# After step 3 (ontology extraction), add step 4:
# Step 4: Pre-atomize document for validation (free cache, no Gemini call yet)
try:
    from app.services.validation_service import ValidationService
    # Only atomize if document_type suggests structured requirements
    if document.document_type in ("BRD", "SRS", "FRD", "USER_STORY", "SPECIFICATION"):
        ValidationService().atomize_document(db=db, document_id=document.id)
        # This caches atoms in requirement_atoms table for future validation runs
        # atomize_document() is already cached per document_version — safe to call early
except Exception as e:
    logger.warning(f"Pre-atomization failed (non-fatal): {e}")
    # NEVER block upload pipeline
```

This means when a developer later runs validation, `atomize_document()` returns cached atoms instantly — no Gemini call needed. The cost is paid once at upload time.

**New field needed in `requirement_atoms` table:**
- `atomized_at_upload: bool (default False)` — tracks whether atom was created at upload vs validation time

**Migration:** `backend/alembic/versions/s14a1_atom_upload_flag.py`

### P4.2 — Shared Context Object: `BOEContext`
**New file:** `backend/app/services/boe_context.py`

This is the bridge that all 4 engines read from. Built once per analysis run, cached in Redis.

```python
class BOEContext:
    """
    Snapshot of BOE knowledge for a specific document-component pair.
    Pre-computed before validation runs. Passed into all 9 passes.
    Eliminates need for validation engine to re-derive what BOE already knows.
    """
    tenant_id: int
    document_id: int
    component_id: int

    # From BOE: existing concept mappings for this pair
    confirmed_mappings: list[ConceptMappingSnapshot]
    # { doc_concept_name, code_concept_name, relationship_type, confidence, mapping_id }

    # From BOE: gaps (document concepts with NO code counterpart)
    document_only_concepts: list[str]  # concept names in BRD with no code match

    # From BOE: orphans (code concepts with NO document counterpart)
    code_only_concepts: list[str]      # concept names in code with no BRD match

    # From BOE: high-confidence pairs (skip AI validation entirely)
    auto_approved_pairs: list[str]     # concept names where confidence >= 0.92

    # From Code Engine: structured_analysis snapshot
    file_role: str | None              # ENDPOINT / SERVICE / SCHEMA / MODEL
    api_contracts: list[dict]          # from structured_analysis
    data_flows: list[dict]             # from structured_analysis

    # Cache metadata
    built_at: datetime
    cache_key: str                     # f"boe_context:{tenant_id}:{document_id}:{component_id}"
    ttl_seconds: int = 3600            # 1 hour — refresh on re-analysis
```

**Methods:**
```python
@classmethod
def build(cls, db, document_id, component_id, tenant_id) -> "BOEContext":
    """Assembles context from BOE + Code Engine data. Cached in Redis."""

def get_mapping_for_concept(self, concept_name: str) -> ConceptMappingSnapshot | None:
    """O(1) lookup — used by all 9 validation passes."""

def is_auto_approved(self, concept_name: str) -> bool:
    """Returns True if BOE confidence >= 0.92 — skip Gemini."""

def get_gaps_for_atom_type(self, atom_type: str) -> list[str]:
    """Returns BOE document-only concepts relevant to this atom type."""
```

### P4.3 — Validation Engine Reads BOEContext
**File:** `backend/app/services/validation_service.py`

Modify `validate_single_link()` to accept and use BOEContext:

```python
async def validate_single_link(
    self, db, document_id, component_id, tenant_id,
    boe_context: BOEContext | None = None  # NEW PARAMETER
) -> ValidationResult:

    # Build BOE context if not provided
    if boe_context is None:
        boe_context = BOEContext.build(db, document_id, component_id, tenant_id)

    # Step 0 (NEW): Auto-resolve from BOE before calling Gemini
    auto_resolved = []
    for atom in atoms:
        if boe_context.is_auto_approved(atom.primary_concept):
            # BOE already confirmed this with high confidence — skip all 9 passes
            mapping = boe_context.get_mapping_for_concept(atom.primary_concept)
            auto_resolved.append(create_resolved_result(atom, mapping))
            continue
        # ... existing 9-pass logic for remaining atoms

    # Step 0b (NEW): Auto-flag MISSING atoms from BOE gaps
    for concept_name in boe_context.document_only_concepts:
        # This concept exists in BRD but has zero code counterpart
        # Automatically create a MISSING mismatch — 0 Gemini calls
        auto_flag_missing(db, document_id, concept_name, tenant_id)

    # Remaining atoms go through existing 8 forward + 1 reverse passes
    # (unchanged — same logic, same prompts)
```

**Impact:** If BOE has 60% of concepts already mapped with high confidence, 60% of atoms skip Gemini entirely. Typical real-world savings: 5-7 of 9 passes eliminated per link.

### P4.4 — Batch BOEContext Building
**File:** `backend/app/services/validation_service.py`

When running validation for an entire document (multiple links):

```python
def run_full_document_validation(self, db, document_id, tenant_id):
    links = crud.document_code_link.get_by_document(db, document_id, tenant_id)

    # Build ALL contexts in parallel before starting validation
    # One DB query per context vs N queries inside each validate_single_link call
    contexts = {
        link.component_id: BOEContext.build(db, document_id, link.component_id, tenant_id)
        for link in links
    }

    # Run validations with pre-built contexts
    results = await asyncio.gather(*[
        self.validate_single_link(
            db, document_id, link.component_id, tenant_id,
            boe_context=contexts[link.component_id]
        )
        for link in links
    ])
```

### P4.5 — Validation Writes Back to BOE
**File:** `backend/app/services/validation_service.py`

After each validation pass creates/updates a mismatch, update the corresponding BOE concept mapping:

```python
# At end of validate_single_link, after mismatches are created:
try:
    for result in pass_results:
        if result.get("concept_name") and result.get("verdict"):
            mapping = boe_context.get_mapping_for_concept(result["concept_name"])
            if mapping:
                # Update BOE confidence based on validation finding
                new_confidence = _calibrate_confidence(
                    old_confidence=mapping.confidence,
                    validation_verdict=result["verdict"],  # MATCH/PARTIAL/MISMATCH
                    validation_confidence=result["confidence"]
                )
                crud.concept_mapping.update(db, id=mapping.mapping_id, obj_in={
                    "confidence_score": new_confidence,
                    "last_validated_at": datetime.utcnow(),
                    "validation_verdict": result["verdict"]
                })
except Exception as e:
    logger.warning(f"BOE writeback failed (non-fatal): {e}")
```

**New fields needed in `concept_mappings` table:**
- `last_validated_at: datetime | None`
- `validation_verdict: str | None` — "MATCH", "PARTIAL_MATCH", "MISMATCH"

**Migration:** `backend/alembic/versions/s14b1_concept_mapping_validation_fields.py`

### P4.6 — Confidence Calibration Function
**File:** `backend/app/services/validation_service.py`

```python
def _calibrate_confidence(
    old_confidence: float,
    validation_verdict: str,
    validation_confidence: float
) -> float:
    """
    Bayesian update: BOE confidence moves toward validation finding.
    Conservative update — never moves more than 0.15 per validation run.
    MATCH verdict → confidence increases toward 1.0
    MISMATCH verdict → confidence decreases toward 0.0
    PARTIAL_MATCH → small adjustment
    """
    delta_map = {"MATCH": +0.10, "PARTIAL_MATCH": +0.02, "MISMATCH": -0.15}
    delta = delta_map.get(validation_verdict, 0) * validation_confidence
    return max(0.0, min(1.0, old_confidence + delta))
```

### P4.7 — Code Engine Notifies BOE on New Analysis
**File:** `backend/app/services/code_analysis_service.py`

After a repository is fully analyzed (all components complete), trigger BOE cross-graph mapping:

```python
# After all components analyzed, at end of analyze_repository():
try:
    from app.tasks.ontology_tasks import run_cross_graph_mapping
    run_cross_graph_mapping.delay(
        tenant_id=tenant_id,
        trigger_source="code_analysis_complete",
        repository_id=repository_id
    )
except Exception as e:
    logger.warning(f"BOE refresh trigger failed (non-fatal): {e}")
```

This ensures the BOE is always fresh after a new code scan, so the next validation run gets an up-to-date BOEContext.

### P4.8 — Unified Analysis Orchestrator Endpoint
**New endpoint in** `backend/app/api/endpoints/analysis_results.py`

```
POST /api/v1/analysis/run-full
  Description: Runs all 4 engines in correct sequence for a document-repository pair
  Body: { document_id: int, repository_id: int }
  Sequence:
    1. Ensure document atoms pre-cached (P4.1)
    2. Build BOEContexts for all doc-component links (P4.2)
    3. Run BOE cross-graph mapping to refresh concept mappings (P4.3)
    4. Run validation with pre-built contexts (P4.4 + P4.5)
  Response: {
    task_id: str,
    estimated_gemini_calls_saved: int,  # based on BOE coverage %
    boe_coverage_pct: float
  }
```

### P4.9 — Cost Savings Dashboard Widget
**File:** `frontend/app/dashboard/analytics/page.tsx`

Add "Engine Efficiency" card:
```
BOE Coverage: 73% of concept pairs already mapped
Gemini calls this month: 1,247  (was: 5,891 before integration)
Cost saved this month: $47.20
Training examples captured: 3,041
```

### P4.10 — New `analysis_run` Metadata Fields
**File:** `backend/app/models/analysis_run.py`

Add fields to `analysis_runs` table to track 4-engine integration metrics:
- `boe_coverage_pct: float | None` — % of atoms auto-resolved from BOE
- `gemini_calls_used: int | None`
- `gemini_calls_saved: int | None`
- `auto_resolved_count: int | None`
- `auto_flagged_missing_count: int | None`

**Migration:** `backend/alembic/versions/s14c1_analysis_run_efficiency_fields.py`

### Verification
1. **Pre-atomization:** Upload a BRD → check `SELECT COUNT(*) FROM requirement_atoms WHERE document_id = X` immediately after upload (before validation is run)
2. **BOE context build:** Log output of `BOEContext.build()` — verify `confirmed_mappings` is populated for a tenant with existing ontology data
3. **Auto-resolution:** Run validation on a document where BOE has high-confidence mappings → check `gemini_calls_used < gemini_calls_saved`
4. **Auto-flag missing:** Verify mismatches are created for `document_only_concepts` without Gemini calls
5. **BOE writeback:** After validation, check `concept_mappings.last_validated_at` is updated
6. **Non-breaking:** All existing `/api/v1/validation/*` endpoints return same response shape as before

---

## PHASE 5 — Dynamic Prompting (Industry Intelligence + Glossary Self-Learning)
**Priority: High — directly improves output quality for every tenant, every prompt**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: Medium-High**

### Context
Every prompt DokyDoc sends to Gemini today is generic. It knows nothing about whether the tenant is a fintech company, a hospital, or a logistics firm. "Payment" in a BRD for a fintech means PCI-DSS regulated card transactions. The same word in a healthcare BRD means insurance reimbursement. The same prompt cannot serve both correctly.

This phase implements a 3-layer dynamic prompt assembly system:

| Layer | Source | Content |
|-------|--------|---------|
| Layer 1 | Industry Context Library (JSON file) | Regulatory context, domain vocabulary, common patterns for 23 industries |
| Layer 2 | Tenant Glossary (`tenant.settings.glossary`) | Company-specific terms confirmed by users during document analysis |
| Layer 3 | Few-Shot Examples (`training_examples` table) | Actual accepted/rejected decisions from this tenant's team (Phase 1) |

These 3 layers are assembled and injected into every prompt via `PromptManager.get_prompt()`. Zero new Gemini calls — same call, smarter context.

### P5.1 — Industry Classification in Tenant Settings
**File:** `backend/app/models/tenant.py`

The `tenant.settings` JSON field already exists. Add structured keys:

```python
# tenant.settings JSON structure (extend existing empty dict):
{
  "industry": "fintech",           # Primary industry code (see full list below)
  "sub_domain": "payments",        # Sub-segment
  "company_website": "https://...", # Added at registration (P5.4)
  "glossary": {                    # Self-learned terms (P5.5)
    "Finacle": "core banking system used for account management",
    "NACH": "National Automated Clearing House — used for recurring debits"
  },
  "regulatory_context": ["PCI-DSS", "RBI"],  # Extracted from website (P5.4)
  "onboarding_complete": false     # Whether industry profile is filled
}
```

**Full Industry Classification (23 major sectors):**
```
Financial Services:
  fintech (payments, lending, wealth_management, insurance_tech, crypto)
  banking (retail_banking, corporate_banking, investment_banking)
  insurance (life, health, property_casualty, reinsurance)

Healthcare & Life Sciences:
  healthcare (hospital_systems, clinical_trials, telemedicine, medical_devices)
  pharma (drug_discovery, manufacturing, distribution)

Technology:
  saas (b2b_saas, b2c_saas, platform, marketplace)
  enterprise_software (erp, crm, scm, hrm)
  devtools (ci_cd, observability, security, infrastructure)

Commerce & Logistics:
  ecommerce (retail, d2c, marketplace)
  logistics (supply_chain, last_mile, freight, warehousing)
  manufacturing (discrete, process, automotive)

Public & Regulated Sectors:
  government (federal, state_local, defense)
  education (k12, higher_ed, edtech)
  legal (law_firms, legaltech, compliance)

Other:
  telecom, media_entertainment, real_estate, agriculture,
  energy_utilities, hospitality_travel, nonprofit
```

**Schema update:** `backend/app/schemas/tenant.py`
Add `industry`, `sub_domain`, `company_website` to `TenantCreate` and `TenantUpdate`.

**Migration:** `backend/alembic/versions/s15a1_tenant_industry_settings.py`
No new columns — `settings` JSON field already exists. Migration adds a GIN index on `settings` for fast JSON queries:
```sql
CREATE INDEX IF NOT EXISTS idx_tenant_settings_gin ON tenants USING gin(settings);
```

### P5.2 — Industry Context Library
**New file:** `backend/app/services/ai/industry_context.json`

A structured JSON file with vocabulary injection blocks for each industry. Each block is injected into prompts as a prefix paragraph. Example structure:

```json
{
  "fintech": {
    "payments": {
      "regulatory": ["PCI-DSS", "PSD2", "EMVCo", "AML/KYC"],
      "vocabulary": {
        "payment_gateway": "intermediary that authorizes card transactions",
        "settlement": "transfer of funds between acquiring and issuing banks",
        "chargeback": "forced reversal of a transaction initiated by the card issuer",
        "acquirer": "bank that processes card payments on behalf of the merchant",
        "ISO 8583": "international standard for financial transaction card messages"
      },
      "common_patterns": [
        "3-tier architecture: API gateway → payment processor → core banking",
        "Dual-message vs single-message authorization flows",
        "Idempotency keys required on all payment mutations"
      ],
      "prompt_injection": "This is a fintech payments system. Key regulatory requirements include PCI-DSS compliance (card data must never be logged), PSD2 strong customer authentication (SCA), and AML/KYC checks for new users. Domain terms: settlement means end-of-day fund transfer, not real-time."
    }
  },
  "healthcare": {
    "hospital_systems": {
      "regulatory": ["HIPAA", "HL7 FHIR", "ICD-10", "HITECH"],
      "vocabulary": {
        "PHI": "Protected Health Information — any data that can identify a patient",
        "EHR": "Electronic Health Record — legally binding clinical documentation",
        "ADT": "Admit/Discharge/Transfer — core HL7 message type"
      },
      "prompt_injection": "This is a healthcare system. PHI (Protected Health Information) must be treated as highly sensitive. All access requires audit logs (HIPAA). HL7 FHIR R4 is the interoperability standard. ICD-10 codes are used for diagnosis classification."
    }
  }
}
```

Full file covers all 23 major sectors with 2-5 sub-domains each.

**Loading:** Loaded once at startup into memory via `PromptManager.__init__()`. Zero runtime I/O.

### P5.3 — Dynamic Prompt Assembly in PromptManager
**File:** `backend/app/services/ai/prompt_manager.py`

Modify `get_prompt()` to accept a `context` parameter and assemble 3-layer injection:

```python
def get_prompt(
    self,
    prompt_type: PromptType,
    variables: dict,
    context: PromptContext | None = None  # NEW PARAMETER
) -> str:
    base_prompt = self._templates[prompt_type]

    if context is None:
        return base_prompt.format(**variables)

    # Assemble 3-layer prefix
    prefix_blocks = []

    # Layer 1: Industry context
    if context.industry and context.sub_domain:
        industry_block = self._get_industry_block(context.industry, context.sub_domain)
        if industry_block:
            prefix_blocks.append(f"## Industry Context\n{industry_block['prompt_injection']}")

    # Layer 2: Tenant glossary
    if context.glossary:
        glossary_lines = "\n".join(
            f"- **{term}**: {definition}"
            for term, definition in context.glossary.items()
        )
        prefix_blocks.append(f"## Company-Specific Terms\n{glossary_lines}")

    # Layer 3: Few-shot examples from training_examples table
    if context.few_shot_examples:
        examples_text = self._format_few_shot(context.few_shot_examples)
        prefix_blocks.append(f"## Examples From Your Team\n{examples_text}")

    if not prefix_blocks:
        return base_prompt.format(**variables)

    full_prefix = "\n\n".join(prefix_blocks)
    return f"{full_prefix}\n\n---\n\n{base_prompt}".format(**variables)
```

**New `PromptContext` dataclass:**
```python
@dataclass
class PromptContext:
    industry: str | None = None
    sub_domain: str | None = None
    glossary: dict[str, str] | None = None      # from tenant.settings.glossary
    few_shot_examples: list[dict] | None = None  # from training_examples table (top 5)
```

**Loading context in callers:**
Every service that calls `get_prompt()` needs to pass context. Add a shared helper:

```python
# New file: backend/app/services/ai/prompt_context_builder.py
def build_prompt_context(db, tenant_id: int, example_type: str | None = None) -> PromptContext:
    """Builds PromptContext from tenant settings + training examples. Cached 5 min in Redis."""
    tenant = crud.tenant.get(db, tenant_id)
    settings = tenant.settings or {}
    examples = []
    if example_type:
        examples = crud.training_example.get_export_batch(
            db, tenant_id, example_type=example_type, limit=5
        )
    return PromptContext(
        industry=settings.get("industry"),
        sub_domain=settings.get("sub_domain"),
        glossary=settings.get("glossary"),
        few_shot_examples=[e.input_context | {"human_label": e.human_label} for e in examples]
    )
```

**Update all callers** of `get_prompt()` in:
- `validation_service.py` — pass `example_type="mismatch_judgment"`
- `business_ontology_service.py` — pass industry context only
- `mapping_service.py` — pass `example_type="mapping_judgment"`
- `auto_docs_service.py` — pass industry + glossary
- `code_analysis_service.py` — pass industry context only

### P5.4 — Website URL Auto-Detection at Registration
**File:** `backend/app/api/endpoints/tenants.py`

When a new tenant registers, if `company_website` URL is provided, dispatch a background job:

```python
@router.post("/register")
def register_tenant(tenant_in: TenantCreate, ...):
    # ... existing registration logic ...
    tenant = crud.tenant.create(db, obj_in=tenant_in)

    # NEW: If website URL provided, kick off industry detection
    if tenant_in.company_website:
        detect_tenant_industry.delay(
            tenant_id=tenant.id,
            website_url=str(tenant_in.company_website)
        )
    return tenant
```

**New Celery task:** `backend/app/tasks/tenant_tasks.py`

```python
@celery_app.task(name="detect_tenant_industry", max_retries=2)
def detect_tenant_industry(tenant_id: int, website_url: str):
    """
    One Gemini call per registration. Analyzes company website to extract:
    - Industry classification
    - Regulatory context
    - Primary domain/sub-domain
    Stores result in tenant.settings. Never blocks registration.
    """
    # 1. Fetch website content (requests.get with 10s timeout, handle errors)
    # 2. Extract text from HTML (strip tags, max 3000 chars)
    # 3. Single Gemini call with structured output:
    prompt = """
    Analyze this company website and extract:
    {
      "industry": "<one of: fintech, banking, healthcare, saas, ...>",
      "sub_domain": "<specific sub-segment>",
      "regulatory_context": ["<regulatory framework 1>", ...],
      "company_description": "<1 sentence>",
      "confidence": 0.0-1.0
    }
    Website content: {content}
    """
    result = gemini_service.generate_structured(prompt, website_content)

    if result and result.get("confidence", 0) >= 0.70:
        crud.tenant.update(db, id=tenant_id, obj_in={
            "settings": {
                **existing_settings,
                "industry": result["industry"],
                "sub_domain": result["sub_domain"],
                "regulatory_context": result["regulatory_context"],
                "onboarding_complete": True
            }
        })
```

Register in `backend/app/worker.py`:
```python
include=[..., "app.tasks.tenant_tasks"]
```

**Onboarding form update:** `frontend/app/dashboard/` onboarding page
- Add `company_website` URL field to registration form (optional)
- Add `industry` + `sub_domain` dropdown (pre-populated from detection, editable)
- Show "Auto-detected from your website" badge when detection succeeds

### P5.5 — Glossary Self-Learning During Document Analysis
**File:** `backend/app/services/business_ontology_service.py`

During document ontology extraction, flag unrecognized domain terms:

```python
def extract_entities_from_document(self, db, document_id, tenant_id):
    # ... existing extraction logic ...

    # NEW: After extraction, check for terms not in tenant glossary or industry library
    existing_glossary = tenant.settings.get("glossary", {})
    industry_vocab = self._get_industry_vocab(tenant.settings.get("industry"))

    unknown_terms = []
    for concept in extracted_concepts:
        term = concept.name.lower()
        if (term not in existing_glossary
                and term not in industry_vocab
                and concept.confidence_score < 0.75
                and len(term.split()) <= 3):  # Only short phrases, not full sentences
            unknown_terms.append({
                "term": concept.name,
                "context": concept.description,
                "concept_id": concept.id,
                "document_id": document_id
            })

    if unknown_terms:
        # Store in tenant.settings.pending_glossary_confirmations
        _store_pending_confirmations(db, tenant_id, unknown_terms[:10])  # Max 10 per run
        # Trigger notification to document owner
        notification_service.create(
            db, tenant_id=tenant_id,
            title="New terms found in your document",
            body=f"DokyDoc found {len(unknown_terms)} unfamiliar terms. Help us understand them.",
            action_url=f"/dashboard/documents/{document_id}?tab=glossary"
        )
```

**New API endpoint:**
```
GET /api/v1/documents/{id}/unknown-terms
  Returns: list of pending glossary confirmations for this document

POST /api/v1/documents/{id}/confirm-term
  Body: { term: str, definition: str, is_company_specific: bool }
  Action: Moves from pending_confirmations → tenant.settings.glossary
          Updates OntologyConcept.confidence_score to 0.95
          Returns: 200 OK
```

**Frontend: Glossary Confirmation Panel**
**File:** `frontend/app/dashboard/documents/[id]/page.tsx`

Add a "Review Terms" tab/card:
```tsx
{unknownTerms.length > 0 && (
  <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 mb-4">
    <h3 className="font-medium text-amber-800 mb-2">
      🔍 {unknownTerms.length} unfamiliar terms found
    </h3>
    <p className="text-sm text-amber-700 mb-3">
      Help DokyDoc understand your company's terminology for better analysis.
    </p>
    {unknownTerms.map(term => (
      <div key={term.term} className="flex items-start gap-3 mb-3">
        <div className="flex-1">
          <span className="font-mono text-sm font-semibold">{term.term}</span>
          <p className="text-xs text-gray-500 mt-0.5">Found in: "{term.context}"</p>
        </div>
        <input
          placeholder="What does this mean at your company?"
          className="flex-1 text-sm border rounded px-2 py-1"
          onBlur={(e) => confirmTerm(term.term, e.target.value)}
        />
        <button onClick={() => dismissTerm(term.term)}
                className="text-xs text-gray-400 hover:text-gray-600">
          Skip
        </button>
      </div>
    ))}
  </div>
)}
```

### P5.6 — Onboarding Industry Profile Screen
**New file:** `frontend/app/dashboard/onboarding/page.tsx`

First-time tenant setup wizard (3 steps):
1. **Company profile** — name, website URL (triggers P5.4 auto-detection)
2. **Industry confirmation** — shows auto-detected industry with dropdown to correct
3. **Glossary kickstart** — optional: paste 5 company-specific terms to pre-seed glossary

Show this page when `tenant.settings.onboarding_complete == false`. Redirect to dashboard when complete.

### P5.7 — Industry Profile Management
**File:** `frontend/app/dashboard/admin/page.tsx` (or new settings page)

Add "Company Intelligence" settings card:
```
Industry: Fintech → Payments  [Edit]
Regulatory Context: PCI-DSS, PSD2, RBI  [Edit]
Custom Glossary: 14 terms  [Manage]
Few-Shot Examples: 347 captured, 89 labeled  [View]
Prompt Quality Score: 8.4/10  (estimated from training examples)
```

### Verification
1. **Industry detection:** Register tenant with `company_website="https://stripe.com"` → after task runs, verify `tenant.settings.industry == "fintech"` and `sub_domain == "payments"`
2. **Layer 1 injection:** Run ontology extraction for a fintech tenant → inspect Gemini request payload → verify "PCI-DSS" and "settlement" appear in prompt prefix
3. **Layer 2 injection:** Add `{"NACH": "National Automated Clearing House"}` to tenant glossary → run validation → verify "NACH" definition appears in prompt
4. **Layer 3 injection:** Create 5 `TrainingExample` rows with `human_label="accepted"` → verify they appear as few-shot examples in next prompt
5. **Glossary self-learning:** Upload a document containing "Finacle" → verify notification is created and term appears in `/unknown-terms` endpoint
6. **Non-breaking:** All existing tenants with no `industry` in settings → prompts behave exactly as before (empty context = no prefix added)

---

## PHASE 6 — Enterprise Governance (RBAC, Approvals, Audit, Initiatives)
**Priority: Required for enterprise sales. Blocker for regulated industry customers.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: High**

### Context
Enterprise customers (banks, hospitals, government agencies) will not adopt DokyDoc without:
1. Fine-grained role-based access control (not just owner/member)
2. Mandatory approval gates before documentation is published or analysis is acted on
3. Immutable audit trails with tamper-evidence
4. Initiative-level governance (group related BRDs + repos into a tracked initiative)
5. Multi-repo analysis (a single BRD may span 3 microservices)

The backend models for approvals, audit logs, and initiatives already exist. This phase hardens them, closes gaps, and builds the missing frontend surfaces.

### P6.1 — RBAC Hardening: Fine-Grained Permissions
**File:** `backend/app/api/deps.py`, `backend/app/models/user.py`

Current state: Users have a `role` field (owner/admin/member/viewer). This is too coarse.

Add a permission matrix system:

```python
# New file: backend/app/core/permissions.py

class Permission(str, Enum):
    # Documents
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_APPROVE = "document:approve"

    # Code & Repositories
    REPO_READ = "repo:read"
    REPO_WRITE = "repo:write"
    REPO_TRIGGER_ANALYSIS = "repo:trigger_analysis"

    # Validation
    VALIDATION_RUN = "validation:run"
    VALIDATION_APPROVE = "validation:approve"
    MISMATCH_RESOLVE = "mismatch:resolve"

    # Ontology
    ONTOLOGY_READ = "ontology:read"
    ONTOLOGY_WRITE = "ontology:write"
    CONCEPT_APPROVE = "concept:approve"

    # Governance
    INITIATIVE_READ = "initiative:read"
    INITIATIVE_WRITE = "initiative:write"

    # Admin
    TENANT_SETTINGS = "tenant:settings"
    USER_MANAGE = "user:manage"
    BILLING_VIEW = "billing:view"
    AUDIT_VIEW = "audit:view"
    EXPORT_DATA = "export:data"
    API_KEY_MANAGE = "apikey:manage"

# Default permission sets per role
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "owner": set(Permission),                    # All permissions
    "admin": set(Permission) - {Permission.BILLING_VIEW},
    "lead_developer": {
        Permission.DOCUMENT_READ, Permission.REPO_WRITE,
        Permission.REPO_TRIGGER_ANALYSIS, Permission.VALIDATION_RUN,
        Permission.MISMATCH_RESOLVE, Permission.ONTOLOGY_READ,
        Permission.ONTOLOGY_WRITE, Permission.INITIATIVE_READ,
    },
    "developer": {
        Permission.DOCUMENT_READ, Permission.REPO_READ,
        Permission.REPO_TRIGGER_ANALYSIS, Permission.VALIDATION_RUN,
        Permission.MISMATCH_RESOLVE, Permission.ONTOLOGY_READ,
    },
    "business_analyst": {
        Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE,
        Permission.VALIDATION_RUN, Permission.ONTOLOGY_READ,
        Permission.INITIATIVE_READ, Permission.INITIATIVE_WRITE,
    },
    "viewer": {
        Permission.DOCUMENT_READ, Permission.REPO_READ,
        Permission.ONTOLOGY_READ, Permission.INITIATIVE_READ,
    },
}
```

**New user roles:** `owner`, `admin`, `lead_developer`, `developer`, `business_analyst`, `viewer`

**Migration:** `backend/alembic/versions/s16a1_user_role_expansion.py`
- Add `CHECK constraint` on `users.role` for new valid values
- Default existing "member" → "developer", existing "admin" → "admin"

**Dependency injection helper:**
```python
# backend/app/api/deps.py
def require_permission(permission: Permission):
    def _check(current_user: User = Depends(get_current_user)):
        user_perms = ROLE_PERMISSIONS.get(current_user.role, set())
        if permission not in user_perms:
            raise HTTPException(403, f"Requires permission: {permission}")
        return current_user
    return Depends(_check)

# Usage in any endpoint:
@router.post("/documents/")
def create_document(
    ...,
    _: User = require_permission(Permission.DOCUMENT_WRITE)
):
```

### P6.2 — Approval Workflow Hardening
**File:** `backend/app/services/approval_service.py`, `backend/app/models/approval.py`

Current state: `Approval` model exists but approval gates are not enforced on publishing.

Add mandatory approval gates for:

**Gate 1 — Document Publishing**
When a document moves to `status="published"`:
- If `tenant.settings.require_doc_approval == true` → create Approval record, block publish
- Notify all users with `Permission.DOCUMENT_APPROVE`
- Document stays in `status="pending_approval"` until approved

**Gate 2 — Mismatch Resolution**
When a mismatch is marked `status="resolved"`:
- If `tenant.settings.require_mismatch_approval == true` → require second approver
- Especially critical in regulated industries (SOX, HIPAA audit trails need dual control)

**Gate 3 — Ontology Concept Publish**
When a new OntologyConcept is created from code analysis with `confidence < 0.70`:
- Flag for human review before it propagates to cross-graph mappings
- Approver can: Confirm, Reject, or Edit concept name

**New approval fields in `approval` model:**
```python
approval_gate: str  # "document_publish", "mismatch_resolve", "concept_confirm", "validation_publish"
auto_approved: bool  # True if confidence >= threshold (no human needed)
auto_approval_reason: str | None
sla_hours: int | None  # SLA before escalation (e.g., 48h for enterprise)
escalated_at: datetime | None
escalated_to_user_id: int | None
```

**Migration:** `backend/alembic/versions/s16b1_approval_gates.py`

**SLA Escalation Task:**
```python
# backend/app/tasks/approval_tasks.py
@celery_app.task(name="check_approval_slas")
def check_approval_slas():
    """Runs hourly. Escalates overdue approvals."""
    overdue = crud.approval.get_overdue(db, sla_hours_exceeded=True)
    for approval in overdue:
        notification_service.escalate(approval)
```

Schedule via Celery beat: `{"check-approval-slas": {"task": "check_approval_slas", "schedule": crontab(minute=0)}}`

### P6.3 — Approval Frontend
**File:** `frontend/app/dashboard/approvals/page.tsx`

Current state: Page exists but may be incomplete. Harden with:

- **My Pending Approvals** — items waiting for current user's decision
- **All Pending** (admin/owner only) — full queue with SLA countdown
- **History** — approved/rejected items with who decided and when
- **Bulk Approve** — for low-risk items (viewer role confirmations)

Add approval action to document detail page:
```tsx
{document.status === 'pending_approval' && canApprove && (
  <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
    <h4 className="font-medium">Approval Required</h4>
    <p className="text-sm text-gray-600 mt-1">
      Requested by {document.created_by} · {timeAgo(approval.created_at)}
    </p>
    <div className="flex gap-2 mt-3">
      <button onClick={() => approve(approval.id)}
              className="bg-green-600 text-white px-3 py-1.5 rounded text-sm">
        Approve & Publish
      </button>
      <button onClick={() => setShowRejectModal(true)}
              className="bg-red-100 text-red-700 px-3 py-1.5 rounded text-sm">
        Request Changes
      </button>
    </div>
  </div>
)}
```

### P6.4 — Audit Trail Hardening
**File:** `backend/app/services/audit_service.py`, `backend/app/models/audit_log.py`

Current state: `AuditLog` model exists. Ensure comprehensive coverage.

**Add audit events for every state-changing action:**
```python
class AuditEvent(str, Enum):
    # Documents
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_PUBLISHED = "document.published"
    DOCUMENT_APPROVED = "document.approved"
    DOCUMENT_REJECTED = "document.rejected"

    # Validation
    VALIDATION_RUN = "validation.run"
    MISMATCH_CREATED = "mismatch.created"
    MISMATCH_RESOLVED = "mismatch.resolved"
    MISMATCH_FEEDBACK = "mismatch.feedback"  # Accept/Reject (Phase 1)

    # Ontology
    CONCEPT_CREATED = "concept.created"
    CONCEPT_APPROVED = "concept.approved"
    CONCEPT_DELETED = "concept.deleted"
    MAPPING_CREATED = "mapping.created"

    # Code
    REPO_CONNECTED = "repo.connected"
    REPO_ANALYSIS_STARTED = "repo.analysis_started"
    REPO_ANALYSIS_COMPLETE = "repo.analysis_complete"

    # Users & Access
    USER_INVITED = "user.invited"
    USER_ROLE_CHANGED = "user.role_changed"
    USER_REMOVED = "user.removed"
    API_KEY_CREATED = "apikey.created"
    API_KEY_REVOKED = "apikey.revoked"

    # Billing
    PLAN_UPGRADED = "billing.plan_upgraded"
    PLAN_DOWNGRADED = "billing.plan_downgraded"
```

**Tamper-evidence:** Add a `checksum` field to `audit_logs`:
```python
checksum: str  # SHA-256 of (previous_checksum + event_type + actor_id + timestamp + payload)
```
Forms a hash chain. Any row deletion or modification breaks the chain. Admin endpoint can verify chain integrity:
```
GET /api/v1/audit/verify-integrity
→ Returns { valid: true, checked: N, broken_at: null }
```

**Migration:** `backend/alembic/versions/s16c1_audit_checksum.py`

**Retention policy:** Add `retained_until: datetime | None` — legal hold flag. Records with this set cannot be deleted.

### P6.5 — Initiative Governance Deep Feature
**File:** `backend/app/api/endpoints/initiatives.py`, `backend/app/services/` (new)

Current state: `Initiative` + `InitiativeAsset` models exist. Endpoints exist. Missing: initiative-level analytics, health score, cross-asset reporting.

**Add to Initiative model** (`backend/app/models/initiative.py`):
```python
health_score: float | None      # 0.0-1.0 composite score
health_computed_at: datetime | None
status: str  # "planning", "in_progress", "at_risk", "blocked", "completed"
target_completion_date: date | None
owner_user_id: int | None (FK users.id)
```

**New `InitiativeHealthService`:**
```python
# backend/app/services/initiative_health_service.py

def compute_health_score(db, initiative_id, tenant_id) -> float:
    """
    Composite score from:
    - Validation coverage: % of linked documents with completed validation
    - Mismatch resolution rate: % of mismatches resolved
    - Document completion: % of assets in "published" state
    - Code analysis coverage: % of linked repos fully analyzed
    - Approval backlog: penalize if > 5 pending approvals

    Weights: validation(30%) + mismatches(30%) + docs(20%) + code(10%) + approvals(10%)
    """
```

**New initiative-level endpoints:**
```
GET /api/v1/initiatives/{id}/health
  Returns: { health_score, breakdown, at_risk_items[], recommendations[] }

GET /api/v1/initiatives/{id}/validation-summary
  Returns: aggregate validation results across all linked documents + repos

GET /api/v1/initiatives/{id}/gap-report
  Returns: all BOE gaps (document_only + code_only concepts) across all initiative assets

POST /api/v1/initiatives/{id}/run-full-analysis
  Triggers: analysis of ALL linked documents + repos in correct sequence
```

**Frontend: Initiative Dashboard**
**File:** `frontend/app/dashboard/projects/[id]/page.tsx`

Add health score widget:
```tsx
<div className="grid grid-cols-4 gap-4 mb-6">
  <HealthScoreCard score={initiative.health_score} />
  <StatCard label="Documents" value={`${published}/${total}`} />
  <StatCard label="Open Mismatches" value={openMismatches} trend="down" />
  <StatCard label="Validation Coverage" value={`${coverage}%`} />
</div>
```

### P6.6 — Multi-Repository Analysis
**File:** `backend/app/api/endpoints/initiatives.py`

A single BRD often spans multiple microservices. Add initiative-level cross-repo analysis:

```
POST /api/v1/initiatives/{id}/cross-repo-analysis
  Description: Runs BOE cross-graph mapping across ALL repos linked to this initiative
  Body: { force_rerun: bool }
  Action:
    1. Collect all repositories from initiative assets
    2. Ensure all repos are analyzed (trigger analysis for any pending)
    3. Run cross_project_mapping across all repo ontologies simultaneously
    4. Generate unified concept graph merging all repo concepts
    5. Run validation for all document-code link combinations across repos
  Response: { task_id, repo_count, estimated_duration_seconds }
```

**New `CrossRepoMappingService`:**
```python
# backend/app/services/cross_repo_mapping_service.py
# (different from existing cross_project_mapping_service.py which maps between tenants)
# This maps WITHIN a tenant across their multiple repos

def build_unified_initiative_graph(db, initiative_id, tenant_id) -> dict:
    """
    Merges ontology graphs from all repos in an initiative.
    Detects: shared concepts (same model in 2 repos), interface contracts,
    data ownership conflicts (2 repos write to same logical entity).
    Returns: unified_graph with cross_repo_edges marked.
    """
```

### P6.7 — User Management Frontend
**File:** `frontend/app/dashboard/admin/page.tsx`

Enhance user management with new roles:
```tsx
<table>
  <thead>
    <tr>
      <th>User</th><th>Role</th><th>Permissions</th>
      <th>Last Active</th><th>Actions</th>
    </tr>
  </thead>
  {users.map(user => (
    <tr key={user.id}>
      <td>{user.email}</td>
      <td>
        <RoleDropdown
          value={user.role}
          options={["owner","admin","lead_developer","developer","business_analyst","viewer"]}
          onChange={(role) => updateUserRole(user.id, role)}
          disabled={user.id === currentUser.id}  // Can't change own role
        />
      </td>
      <td>
        <PermissionBadgeList role={user.role} />
      </td>
      <td>{timeAgo(user.last_active_at)}</td>
      <td>
        <button onClick={() => removeUser(user.id)}>Remove</button>
      </td>
    </tr>
  ))}
</table>
```

### P6.8 — Invite System
**File:** `backend/app/api/endpoints/users.py`

Add email-based invite flow:
```
POST /api/v1/users/invite
  Body: { email: str, role: str, initiative_ids?: int[] }
  Action:
    1. Create pending invite record (new InviteToken model or use existing mechanism)
    2. Send invite email with magic link (expires 7 days)
    3. On click: pre-fill registration with tenant + role
  Response: { invite_id, expires_at }

GET /api/v1/users/pending-invites
  Returns: list of outstanding invites with expiry

DELETE /api/v1/users/invites/{id}
  Revokes an outstanding invite
```

**Migration:** `backend/alembic/versions/s16d1_user_invites.py`

### Verification
1. **RBAC:** Create a "viewer" user → verify calling `POST /documents/` returns 403
2. **Approval gate:** Enable `require_doc_approval` in tenant settings → publish a document → verify it enters `pending_approval` state and notification is sent
3. **SLA escalation:** Create approval with `sla_hours=1`, wait 1h, run `check_approval_slas` → verify escalation notification created
4. **Audit checksum:** Insert a row into `audit_logs` directly via SQL (bypassing service), run `GET /audit/verify-integrity` → verify `broken_at` is reported
5. **Initiative health:** Link 3 documents + 2 repos to an initiative, run analysis → verify `health_score` is between 0 and 1 with meaningful breakdown
6. **Multi-repo:** Create initiative with 2 repos → `POST /initiatives/{id}/cross-repo-analysis` → verify cross-repo concept edges appear in ontology graph
7. **Non-breaking:** Existing users retain their roles, existing documents retain their status

---

## PHASE 7 — Integrations & Export (Jira, Confluence, GitHub, Webhooks, API v2)
**Priority: High — required for enterprise workflow adoption**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: High**

### Context
Enterprise teams don't live in DokyDoc — they live in Jira, Confluence, GitHub, and Slack. If DokyDoc findings don't flow into those tools automatically, adoption stalls at the "pilot" stage. The integration models (`IntegrationConfig`, `JiraItem`, `GeneratedDoc`) already exist. This phase hardens the sync pipelines, adds Confluence publishing, deepens GitHub PR comments, and exposes a clean public API v2 for custom integrations.

### P7.1 — Jira Deep Sync
**File:** `backend/app/services/jira_sync_service.py`

Current state: Basic Jira item creation exists. Harden with bidirectional sync.

**Outbound (DokyDoc → Jira):**
```python
# Sync mismatches as Jira issues
def sync_mismatches_to_jira(db, document_id, tenant_id, project_key):
    mismatches = crud.mismatch.get_open(db, document_id, tenant_id)
    for mismatch in mismatches:
        existing = crud.jira_item.get_by_source(db, source_id=mismatch.id,
                                                 source_type="mismatch")
        if existing:
            # Update existing Jira issue if mismatch changed
            _update_jira_issue(existing.jira_key, mismatch)
        else:
            # Create new Jira issue
            jira_key = _create_jira_issue(
                project_key=project_key,
                summary=f"[DokyDoc] {mismatch.mismatch_type}: {mismatch.title}",
                description=_format_mismatch_description(mismatch),
                issue_type="Bug" if mismatch.severity == "critical" else "Task",
                labels=["dokydoc", mismatch.mismatch_type.lower()],
                priority=_map_severity_to_jira_priority(mismatch.severity)
            )
            crud.jira_item.create(db, jira_key=jira_key,
                                  source_id=mismatch.id, source_type="mismatch")
```

**Inbound (Jira → DokyDoc):**
```python
# Webhook from Jira: issue status changed
@router.post("/webhooks/jira")
def jira_webhook(payload: dict):
    if payload["webhookEvent"] == "jira:issue_updated":
        jira_key = payload["issue"]["key"]
        new_status = payload["issue"]["fields"]["status"]["name"]
        # If Jira issue moved to "Done" → auto-resolve mismatch in DokyDoc
        if new_status in ("Done", "Resolved", "Closed"):
            item = crud.jira_item.get_by_jira_key(db, jira_key)
            if item and item.source_type == "mismatch":
                crud.mismatch.update(db, id=item.source_id,
                                     obj_in={"status": "resolved",
                                             "resolved_via": "jira_sync"})
```

**Sync status tracking on `jira_items` table:**
- Add `last_synced_at`, `sync_status` ("pending", "synced", "error"), `sync_error`
- **Migration:** `backend/alembic/versions/s17a1_jira_sync_fields.py`

**Sync schedule:** Add to Celery beat:
```python
{"jira-sync": {"task": "sync_all_jira", "schedule": crontab(minute="*/15")}}
```

### P7.2 — Confluence Auto-Publish
**File:** `backend/app/services/auto_docs_service.py`

When `GeneratedDoc` status becomes "approved", optionally auto-publish to Confluence:

```python
def publish_to_confluence(db, generated_doc_id, tenant_id, space_key, parent_page_id=None):
    doc = crud.generated_doc.get(db, generated_doc_id)
    config = crud.integration_config.get_confluence(db, tenant_id)

    confluence_api = ConfluenceClient(
        url=config.base_url,
        username=config.credentials["username"],
        token=encryption_service.decrypt(config.credentials["api_token"])
    )

    # Check if page already exists (update vs create)
    existing_page = confluence_api.get_page_by_title(space_key, doc.title)
    if existing_page:
        confluence_api.update_page(
            page_id=existing_page["id"],
            title=doc.title,
            body=_markdown_to_confluence_storage(doc.content),
            version=existing_page["version"]["number"] + 1
        )
    else:
        page = confluence_api.create_page(
            space_key=space_key,
            title=doc.title,
            body=_markdown_to_confluence_storage(doc.content),
            parent_id=parent_page_id
        )

    # Store Confluence page ID for future updates
    crud.generated_doc.update(db, id=generated_doc_id, obj_in={
        "external_url": page["_links"]["webui"],
        "external_id": page["id"],
        "published_at": datetime.utcnow()
    })
```

**New `generated_docs` fields:**
- `external_url: str | None` — Confluence page URL
- `external_id: str | None` — Confluence page ID
- `published_at: datetime | None`
- `publish_target: str | None` — "confluence", "notion", "sharepoint"

**Migration:** `backend/alembic/versions/s17b1_generated_doc_publish_fields.py`

**Frontend publish button:**
```tsx
// frontend/app/dashboard/auto-docs/page.tsx
{doc.status === 'approved' && integrations.confluence && (
  <button onClick={() => publishToConfluence(doc.id)}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded text-sm">
    <ConfluenceIcon className="h-4 w-4" />
    Publish to Confluence
  </button>
)}
```

### P7.3 — GitHub PR Comment Deepening
**File:** `backend/app/services/pr_comment_service.py`

Current state: Basic PR comments exist. Add rich structured comments.

**PR comment format (Markdown):**
```markdown
## 🔍 DokyDoc Analysis: 3 Issues Found

| Severity | Type | Description |
|----------|------|-------------|
| 🔴 Critical | Missing Implementation | `PaymentService.refund()` documented in BRD §4.2 but not found in code |
| 🟡 Warning | API Contract Mismatch | `POST /payments` returns `payment_id` in BRD but `id` in implementation |
| 🟢 Info | New Endpoint | `GET /payments/{id}/status` exists in code but not documented |

**Coverage Score:** 78% → 72% (↓6% from this PR)

<details>
<summary>View full validation report</summary>

[Link to DokyDoc validation panel](https://app.dokydoc.com/dashboard/validation/...)

</details>

---
*Powered by [DokyDoc](https://dokydoc.com) · [Configure](https://app.dokydoc.com/dashboard/integrations)*
```

**New webhook trigger:**
When a PR is opened/updated → GitHub webhook → `POST /api/v1/webhooks/github` → trigger validation for changed files → post comment.

**Add to `integration_configs`:**
```python
settings: {
  "post_pr_comment": true,
  "block_pr_on_critical": false,    # Set PR status check to "failure" on critical mismatches
  "min_coverage_threshold": 70,     # Post warning if coverage drops below this
  "comment_on_passing": false       # Don't post if zero issues
}
```

**PR Status Check (GitHub Checks API):**
```python
def post_github_check(repo_full_name, sha, conclusion, summary):
    """Posts a GitHub Check Run (shows green/red checkmark on PR)."""
    github_client.create_check_run(
        repo=repo_full_name,
        name="DokyDoc Documentation Coverage",
        head_sha=sha,
        status="completed",
        conclusion=conclusion,  # "success" | "failure" | "neutral"
        output={"title": summary["title"], "summary": summary["body"]}
    )
```

### P7.4 — Slack Notifications
**New file:** `backend/app/services/slack_service.py`

```python
class SlackService:
    def post_validation_summary(self, webhook_url: str, summary: dict):
        """Posts Block Kit formatted message to Slack channel."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"DokyDoc: {summary['mismatch_count']} issues in {summary['doc_name']}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Coverage:* {summary['coverage']}%"},
                {"type": "mrkdwn", "text": f"*Critical:* {summary['critical_count']}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "View Report"},
                 "url": summary["report_url"]}
            ]}
        ]
        requests.post(webhook_url, json={"blocks": blocks})

    def post_approval_request(self, webhook_url, approval):
        """Notifies approver in Slack when their action is needed."""
```

**Add Slack to `integration_configs`:**
- `slack_webhook_url` (encrypted)
- `notify_on`: list of events (validation_complete, critical_mismatch, approval_needed)

**Frontend:** Add Slack to integrations page with webhook URL input + test button.

### P7.5 — Public API v2 (External Developers)
**New file:** `backend/app/api/v2/` directory

DokyDoc already has API keys (`api_keys` model). Expose a clean v2 REST API for external developers to integrate DokyDoc into their own pipelines.

**API v2 endpoints:**
```
# Document Operations
POST   /api/v2/documents                    Upload a new document
GET    /api/v2/documents/{id}               Get document with analysis status
GET    /api/v2/documents/{id}/validation    Get validation results
GET    /api/v2/documents/{id}/mismatches    Get list of mismatches

# Repository Operations
POST   /api/v2/repositories                 Connect a repository
GET    /api/v2/repositories/{id}/status     Get analysis status
POST   /api/v2/repositories/{id}/analyze    Trigger re-analysis

# Knowledge Graph
GET    /api/v2/concepts                     List ontology concepts (paginated)
GET    /api/v2/concepts/{id}               Get concept with relationships
GET    /api/v2/mappings                     List document-code mappings

# Webhooks (outbound — DokyDoc calls your URL)
POST   /api/v2/webhook-subscriptions        Subscribe to DokyDoc events
DELETE /api/v2/webhook-subscriptions/{id}   Unsubscribe
GET    /api/v2/webhook-subscriptions        List subscriptions
```

**Outbound webhook events DokyDoc can push:**
```python
class WebhookEvent(str, Enum):
    ANALYSIS_COMPLETE = "analysis.complete"
    VALIDATION_COMPLETE = "validation.complete"
    MISMATCH_CREATED = "mismatch.created"
    CRITICAL_MISMATCH = "mismatch.critical"
    APPROVAL_NEEDED = "approval.needed"
    DOCUMENT_PUBLISHED = "document.published"
```

**New `webhook_subscriptions` table:**
```python
class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"
    id: int
    tenant_id: int (FK)
    target_url: str (encrypted)
    events: list[str] (JSON array)
    secret: str (encrypted — used for HMAC signature on payload)
    is_active: bool
    created_at: datetime
    last_triggered_at: datetime | None
    failure_count: int (default 0)  # disable after 10 consecutive failures
```

**Migration:** `backend/alembic/versions/s17c1_webhook_subscriptions.py`

**Webhook delivery service:**
```python
# backend/app/services/webhook_delivery_service.py
def deliver_event(db, tenant_id, event_type, payload):
    subscriptions = crud.webhook_subscription.get_active(db, tenant_id, event_type)
    for sub in subscriptions:
        # Sign payload with HMAC-SHA256
        signature = hmac.new(sub.secret.encode(), json.dumps(payload).encode(), "sha256").hexdigest()
        # Deliver via Celery task (async, with retry)
        deliver_webhook.delay(
            url=sub.target_url,
            payload=payload,
            signature=signature,
            subscription_id=sub.id
        )
```

### P7.6 — Data Export
**File:** `backend/app/api/endpoints/exports.py`

Add comprehensive export formats:

```
GET /api/v1/exports/validation-report/{document_id}
  Formats: PDF, CSV, XLSX, JSON
  Content: Full validation report with all passes, mismatches, coverage score

GET /api/v1/exports/traceability-matrix/{document_id}
  Format: XLSX (standard RTM format used in regulated industries)
  Content: Requirement ID | Requirement Text | Linked Code | Coverage | Status

GET /api/v1/exports/ontology/{tenant_id}
  Format: JSON-LD, RDF/Turtle, CSV
  Content: Full knowledge graph export

GET /api/v1/exports/gap-report/{initiative_id}
  Format: PDF, XLSX
  Content: All BOE gaps + undocumented code + critical mismatches per initiative
```

**PDF generation:** Use `weasyprint` or `reportlab`. Add to `requirements.txt`.
**XLSX generation:** Use `openpyxl`. Add to `requirements.txt`.

### P7.7 — Integration Configuration Frontend
**File:** `frontend/app/dashboard/integrations/page.tsx`

Dedicated integrations management page with cards per integration:

```tsx
<div className="grid grid-cols-2 gap-4">
  <IntegrationCard
    name="Jira"
    logo={<JiraIcon />}
    status={integrations.jira?.connected ? "connected" : "not_connected"}
    description="Sync mismatches as Jira issues. Two-way status sync."
    onConfigure={() => openJiraModal()}
  />
  <IntegrationCard name="Confluence" ... />
  <IntegrationCard name="GitHub" ... />
  <IntegrationCard name="Slack" ... />
  <IntegrationCard name="Microsoft Teams" status="coming_soon" ... />
  <IntegrationCard name="Notion" status="coming_soon" ... />
</div>
```

Each card opens a configuration modal with:
- Connection credentials (encrypted server-side)
- Test Connection button
- Sync settings (which events trigger actions)
- Last sync status + timestamp

### Verification
1. **Jira sync:** Create a mismatch → verify Jira issue created with correct severity/labels
2. **Jira inbound:** Mark Jira issue "Done" → verify mismatch auto-resolved in DokyDoc
3. **Confluence:** Approve a generated doc → click "Publish to Confluence" → verify page appears in Confluence space
4. **GitHub PR comment:** Open a PR on connected repo → verify DokyDoc comment posted within 2 minutes
5. **Slack:** Create critical mismatch → verify Slack Block Kit message received in configured channel
6. **API v2:** Call `POST /api/v2/documents` with API key → verify document created and `analysis_complete` webhook fires
7. **Outbound webhook:** Subscribe to `mismatch.critical` → create critical mismatch → verify POST received at subscriber URL with valid HMAC signature
8. **Export:** `GET /api/v1/exports/traceability-matrix/{id}?format=xlsx` → download valid Excel file

---

## PHASE 8 — Search, Chat & RAG (Semantic Search, AI Assistant, Cross-Document Q&A)
**Priority: High — key engagement driver, reduces support burden**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline), Phase 5 (dynamic prompting)**
**Estimated complexity: High**

### Context
DokyDoc already has a RAG chat assistant (`rag_service.py`, `chat/page.tsx`), semantic search (`semantic_search_service.py`, `search/page.tsx`), and vector embeddings. The gaps are: search doesn't span code + documents + ontology in a unified way, the chat assistant doesn't leverage the knowledge graph, and there's no cross-document Q&A (e.g., "Which BRDs reference the Payment entity?"). This phase makes search and chat the most powerful features in the product.

### P8.1 — Unified Semantic Search Index
**File:** `backend/app/services/semantic_search_service.py`

Current state: Search may be scoped to documents only. Extend to span all artifact types in a single query.

**Search corpus — index all of:**
```python
SEARCH_ARTIFACT_TYPES = {
    "document":         Document (title + content summary),
    "document_segment": DocumentSegment (section text),
    "requirement_atom": RequirementAtom (atom content + type),
    "code_component":   CodeComponent (name + summary + structured_analysis summary),
    "ontology_concept": OntologyConcept (name + description),
    "mismatch":         Mismatch (title + description),
    "generated_doc":    GeneratedDoc (title + content summary),
}
```

**Unified search endpoint:**
```
GET /api/v1/search?q=payment+refund&types=document,code_component,mismatch&limit=20

Response:
{
  "results": [
    {
      "artifact_type": "mismatch",
      "id": 42,
      "title": "PaymentService.refund() not implemented",
      "snippet": "BRD §4.2 requires refund capability...",
      "score": 0.94,
      "url": "/dashboard/validation-panel?mismatch=42",
      "metadata": { "severity": "critical", "document_id": 7 }
    },
    {
      "artifact_type": "code_component",
      "id": 17,
      "title": "payment_service.py",
      "snippet": "Handles payment processing and settlement...",
      "score": 0.89,
      "url": "/dashboard/code/17"
    }
  ],
  "total": 47,
  "facets": {
    "artifact_type": {"document": 12, "code_component": 8, "mismatch": 5, ...}
  }
}
```

**Implementation — hybrid search (keyword + semantic):**
```python
def unified_search(db, query: str, tenant_id: int,
                   types: list[str] | None = None,
                   limit: int = 20) -> SearchResponse:
    # 1. Generate query embedding (single Gemini call)
    query_embedding = embedding_service.embed(query)

    # 2. BM25 keyword search across all indexed text (PostgreSQL full-text)
    keyword_results = _bm25_search(db, query, tenant_id, types)

    # 3. Vector similarity search via pgvector across all embeddings
    vector_results = _vector_search(db, query_embedding, tenant_id, types)

    # 4. Reciprocal Rank Fusion (RRF) — combine without needing score normalization
    merged = _reciprocal_rank_fusion(keyword_results, vector_results)

    # 5. Re-rank top 50 with cross-encoder if > 20 results (optional, costly)
    return merged[:limit]
```

**New unified search embeddings table:**
```python
# backend/app/models/search_index.py
class SearchIndex(Base):
    __tablename__ = "search_index"
    id: int (PK)
    tenant_id: int (FK, indexed)
    artifact_type: str (indexed)  # document, code_component, etc.
    artifact_id: int (indexed)
    title: str
    content_snippet: str          # First 500 chars
    full_text: str                # For BM25
    embedding: vector(768)        # pgvector
    indexed_at: datetime
    # Composite unique: (artifact_type, artifact_id, tenant_id)
```

**Migration:** `backend/alembic/versions/s18a1_search_index.py`

**Background indexer task:**
```python
# backend/app/tasks/search_tasks.py
@celery_app.task(name="index_artifact")
def index_artifact(artifact_type: str, artifact_id: int, tenant_id: int):
    """Called after any artifact is created or updated."""
    # Upsert into search_index with fresh embedding
```

Trigger `index_artifact` after: document upload, code analysis complete, mismatch created, concept created.

### P8.2 — Search Frontend Upgrade
**File:** `frontend/app/dashboard/search/page.tsx`

Replace basic search with a full-featured search experience:

```tsx
<div className="max-w-4xl mx-auto">
  {/* Search bar with keyboard shortcut hint */}
  <div className="relative mb-6">
    <SearchIcon className="absolute left-4 top-3.5 h-5 w-5 text-gray-400" />
    <input
      ref={inputRef}
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && runSearch()}
      placeholder="Search documents, code, mismatches, concepts..."
      className="w-full pl-12 pr-4 py-3 border-2 rounded-xl text-base focus:border-blue-500"
      autoFocus
    />
    <kbd className="absolute right-4 top-3.5 text-xs text-gray-400">⌘K</kbd>
  </div>

  {/* Type filters */}
  <div className="flex gap-2 mb-4 flex-wrap">
    {['all','document','code_component','mismatch','concept','generated_doc'].map(type => (
      <button
        key={type}
        onClick={() => toggleType(type)}
        className={`px-3 py-1 rounded-full text-sm border
                    ${activeTypes.includes(type) ? 'bg-blue-600 text-white border-blue-600'
                                                 : 'bg-white text-gray-600 border-gray-300'}`}
      >
        {TYPE_LABELS[type]} {facets[type] ? `(${facets[type]})` : ''}
      </button>
    ))}
  </div>

  {/* Results */}
  {results.map(result => (
    <SearchResultCard
      key={`${result.artifact_type}-${result.id}`}
      result={result}
      query={query}  // For snippet highlighting
      onClick={() => router.push(result.url)}
    />
  ))}
</div>
```

Add global `⌘K` keyboard shortcut that opens a command palette (search + recent pages + quick actions).

### P8.3 — Chat Assistant Hardening
**File:** `backend/app/services/rag_service.py`, `backend/app/services/context_assembly_service.py`

Current state: RAG chat exists. Harden context assembly to include knowledge graph data.

**New context sources for chat:**
```python
def assemble_context(db, query: str, tenant_id: int, conversation_id: int) -> str:
    context_blocks = []

    # 1. Semantic search across all artifacts (reuse P8.1)
    search_hits = unified_search(db, query, tenant_id, limit=10)
    context_blocks.append(_format_search_results(search_hits))

    # 2. Knowledge graph — relevant concepts + relationships
    query_concepts = _extract_concepts_from_query(query)  # Simple keyword match
    for concept_name in query_concepts:
        concept = crud.ontology_concept.get_by_name(db, concept_name, tenant_id)
        if concept:
            neighbors = crud.ontology_relationship.get_neighbors(db, concept.id)
            context_blocks.append(_format_concept_neighborhood(concept, neighbors))

    # 3. Recent conversation context (last 5 turns for coherence)
    history = crud.conversation.get_recent_messages(db, conversation_id, limit=5)
    context_blocks.append(_format_conversation_history(history))

    # 4. Active mismatches (if query mentions issues/problems/gaps)
    if _query_mentions_issues(query):
        open_mismatches = crud.mismatch.get_open(db, tenant_id, limit=5)
        context_blocks.append(_format_mismatches(open_mismatches))

    return "\n\n---\n\n".join(context_blocks)
```

**Dynamic prompting in chat (P5 integration):**
```python
context = build_prompt_context(db, tenant_id)
prompt = prompt_manager.get_prompt(
    PromptType.RAG_CHAT,
    variables={"query": user_query, "context": assembled_context},
    context=context  # Layer 1+2+3 injection
)
```

### P8.4 — Cross-Document Q&A
**New capability in chat:** Answer questions that span multiple documents.

Example queries:
- "Which BRDs reference the Payment entity?"
- "Show me all requirements related to authentication across all documents"
- "What's the validation status of every document linked to the Payment Initiative?"

**Implementation — query router:**
```python
# backend/app/services/query_orchestrator.py (extend existing)

def route_query(db, query: str, tenant_id: int) -> QueryRoute:
    """Classifies query intent to pick the right retrieval strategy."""
    if _is_cross_document_query(query):
        return QueryRoute.CROSS_DOCUMENT
    elif _is_code_query(query):
        return QueryRoute.CODE_SEMANTIC
    elif _is_validation_query(query):
        return QueryRoute.VALIDATION_FILTERED
    else:
        return QueryRoute.STANDARD_RAG

def execute_cross_document_query(db, query, tenant_id) -> str:
    """Searches across ALL documents + ontology graph simultaneously."""
    # 1. Find relevant ontology concepts from query
    # 2. Find all documents that mention those concepts (via document_segments + concept_mappings)
    # 3. Find all mismatches across those documents
    # 4. Assemble a cross-document summary
    # 5. Return Gemini-synthesized answer with citations
```

**Slash commands in chat:**
```
/validate {document_name}    → Trigger validation for a document from chat
/gaps {initiative_name}      → Show BOE gaps for an initiative
/compare {doc_a} {doc_b}     → Compare two BRDs for conflicts
/explain {code_file}         → Explain what a code file does in plain English
/coverage                    → Show current documentation coverage score
/export {format}             → Export current conversation as PDF/Markdown
```

**File:** `frontend/components/chat/SlashCommandPalette.tsx` (already exists — extend with above commands)

### P8.5 — Chat Citation & Source Linking
**File:** `frontend/app/dashboard/chat/page.tsx`

Every AI response should show sources used:

```tsx
{message.role === 'assistant' && (
  <div>
    <MarkdownRenderer content={message.content} />
    {message.sources && message.sources.length > 0 && (
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-xs text-gray-400 mb-1">Sources used:</p>
        <div className="flex flex-wrap gap-1">
          {message.sources.map(source => (
            <button
              key={source.id}
              onClick={() => router.push(source.url)}
              className="text-xs px-2 py-0.5 bg-gray-100 hover:bg-gray-200 rounded
                         text-blue-600 hover:underline"
            >
              {SOURCE_ICON[source.type]} {source.title}
            </button>
          ))}
        </div>
      </div>
    )}
  </div>
)}
```

**Backend:** Return `sources: [{id, artifact_type, title, url, relevance_score}]` in chat response alongside the AI message.

### P8.6 — Chat Message Feedback & Improvement Loop
**File:** `backend/app/models/conversation.py` (ChatMessage)

Add to `ChatMessage`:
```python
feedback_label: str | None   # "helpful", "not_helpful", "wrong"
feedback_note: str | None    # Optional free text
feedback_at: datetime | None
```

**Migration:** `backend/alembic/versions/s18b1_chat_message_feedback.py`

**Frontend thumbs up/down on each AI message:**
```tsx
{message.role === 'assistant' && (
  <div className="flex gap-1 mt-1">
    <button onClick={() => submitFeedback(message.id, 'helpful')}
            className={feedback === 'helpful' ? 'text-green-600' : 'text-gray-300 hover:text-green-500'}>
      👍
    </button>
    <button onClick={() => submitFeedback(message.id, 'not_helpful')}
            className={feedback === 'not_helpful' ? 'text-red-500' : 'text-gray-300 hover:text-red-400'}>
      👎
    </button>
  </div>
)}
```

Capture these as `TrainingExample` rows (Phase 1 flywheel) with `example_type="chat_response"`.

### P8.7 — Conversation Management
**File:** `frontend/app/dashboard/chat/page.tsx`

Add conversation history sidebar:
```tsx
<div className="flex h-full">
  {/* Sidebar: conversation history */}
  <div className="w-64 border-r flex flex-col">
    <button onClick={newConversation}
            className="m-3 p-2 bg-blue-600 text-white rounded-lg text-sm">
      + New Chat
    </button>
    <div className="flex-1 overflow-y-auto">
      {conversations.map(conv => (
        <button
          key={conv.id}
          onClick={() => loadConversation(conv.id)}
          className={`w-full text-left px-3 py-2 hover:bg-gray-50 text-sm
                      ${activeConvId === conv.id ? 'bg-blue-50 text-blue-700' : ''}`}
        >
          <div className="font-medium truncate">{conv.title || "New conversation"}</div>
          <div className="text-xs text-gray-400">{timeAgo(conv.updated_at)}</div>
        </button>
      ))}
    </div>
  </div>

  {/* Main chat area */}
  <div className="flex-1 flex flex-col">
    {/* ... existing chat UI ... */}
  </div>
</div>
```

**Auto-title conversations:** After first assistant response, ask Gemini to generate a 5-word title from the first user message (single cheap call). Store in `conversation.title`.

### P8.8 — Search Analytics
**File:** `backend/app/services/analytics_service.py`

Track search queries to improve relevance:
```python
# Log every search query (anonymized within tenant)
class SearchQueryLog(Base):
    __tablename__ = "search_query_logs"
    id: int
    tenant_id: int
    query_text: str
    result_count: int
    clicked_artifact_id: int | None    # Which result was clicked
    clicked_artifact_type: str | None
    search_duration_ms: int
    created_at: datetime
```

Use logs to:
- Surface "frequently searched, zero results" queries → feed to glossary self-learning (P5.5)
- Track click-through rate per artifact type → weight ranking accordingly
- Identify popular topics → suggest pre-built report templates

**Migration:** `backend/alembic/versions/s18c1_search_query_logs.py`

### Verification
1. **Unified search:** Query "payment refund" → results include documents, code files, mismatches and concepts all in one response with correct `artifact_type` labels
2. **Facets:** Search response includes `facets.artifact_type` count breakdown
3. **Cross-document Q&A:** Ask "Which BRDs reference the User entity?" → response lists document names with links, not hallucinated
4. **Slash commands:** Type `/gaps Payment Initiative` in chat → chat responds with BOE gap analysis
5. **Citations:** Every assistant response includes `sources[]` array with at least one clickable artifact
6. **⌘K shortcut:** Press `⌘K` on any dashboard page → search palette opens with focus on input
7. **Chat feedback:** Click 👎 on a chat response → `ChatMessage.feedback_label = "not_helpful"` stored, `TrainingExample` row created
8. **Non-breaking:** Existing chat history preserved; existing search endpoint still works alongside new unified endpoint

---

## PHASE 9 — Analytics, Billing & Usage Intelligence
**Priority: Required for monetization, retention, and enterprise reporting**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: Medium-High**

### Context
DokyDoc has `UsageLog`, `TenantBilling`, `AnalyticsService`, and `analytics.py` endpoint already. The gaps are: no time-series coverage trends (can't show "your docs improved from 62% → 84% this month"), no per-tenant cost visibility, incomplete tier enforcement (premium features may not be consistently gated), and no self-serve upgrade flow. This phase closes all three and adds an executive-facing analytics dashboard that makes the product sticky.

### P9.1 — Coverage Trend Time-Series
**File:** `backend/app/models/` (new), `backend/app/services/analytics_service.py`

**New model: `CoverageSnapshot`**
```python
# backend/app/models/coverage_snapshot.py
class CoverageSnapshot(Base):
    __tablename__ = "coverage_snapshots"

    id: int (PK)
    tenant_id: int (FK, indexed)
    document_id: int | None (FK — per-document snapshot)
    initiative_id: int | None (FK — per-initiative snapshot)
    scope: str  # "document", "initiative", "tenant"  (indexed)

    # Scores at time of snapshot
    coverage_score: float           # 0.0-1.0 overall
    atom_count: int                 # Total requirement atoms
    atoms_covered: int              # Atoms with MATCH or PARTIAL_MATCH
    atoms_missing: int              # Atoms with MISSING verdict
    mismatch_count: int
    critical_mismatch_count: int
    open_mismatch_count: int
    resolved_mismatch_count: int

    # Delta from previous snapshot
    coverage_delta: float | None    # +0.06 means improved 6 points
    mismatches_delta: int | None

    snapshot_date: date (indexed)   # Daily granularity
    created_at: datetime
```

**Migration:** `backend/alembic/versions/s19a1_coverage_snapshots.py`

**Daily snapshot Celery beat task:**
```python
# backend/app/tasks/analytics_tasks.py
@celery_app.task(name="take_daily_coverage_snapshots")
def take_daily_coverage_snapshots():
    """
    Runs at midnight UTC. Takes one snapshot per active document per tenant.
    Only runs if document has been validated at least once.
    Cost: 0 Gemini calls — reads existing mismatch/atom counts from DB.
    """
    active_docs = crud.document.get_validated(db)
    for doc in active_docs:
        score = _compute_coverage_score(db, doc.id, doc.tenant_id)
        prev = crud.coverage_snapshot.get_latest(db, doc.id, "document")
        crud.coverage_snapshot.create(db, obj_in={
            **score,
            "document_id": doc.id,
            "tenant_id": doc.tenant_id,
            "scope": "document",
            "coverage_delta": score["coverage_score"] - prev.coverage_score if prev else None,
            "snapshot_date": date.today()
        })
```

**Add to Celery beat schedule:**
```python
"daily-snapshots": {
    "task": "take_daily_coverage_snapshots",
    "schedule": crontab(hour=0, minute=5)  # 00:05 UTC daily
}
```

### P9.2 — Analytics API Endpoints
**File:** `backend/app/api/endpoints/analytics.py`

Add time-series endpoints:

```
GET /api/v1/analytics/coverage-trend
  Query: document_id?, initiative_id?, days=30
  Returns: [{ date, coverage_score, delta, mismatch_count }] sorted by date
  Used for: sparklines and trend charts in dashboard

GET /api/v1/analytics/tenant-summary
  Returns: {
    total_documents: int,
    total_repos: int,
    avg_coverage_score: float,
    coverage_trend_7d: float,   # delta over last 7 days
    coverage_trend_30d: float,
    open_mismatches: int,
    critical_mismatches: int,
    atoms_total: int,
    atoms_covered: int,
    most_improved_doc: { id, name, delta },
    most_degraded_doc: { id, name, delta },
    ai_cost_this_month: float,
    ai_cost_savings_this_month: float  # from P4.9 BOE integration
  }

GET /api/v1/analytics/document-leaderboard
  Returns: documents ranked by coverage score, with trend arrows
  Query: sort_by=coverage|mismatches|trend, order=asc|desc, limit=10

GET /api/v1/analytics/initiative-health-history
  Query: initiative_id, days=90
  Returns: time-series of initiative health_score

GET /api/v1/analytics/mismatch-aging
  Returns: open mismatches grouped by age bucket
  { "0-7d": 3, "7-30d": 8, "30-90d": 2, "90d+": 1 }
  Used for: SLA compliance reporting in regulated industries
```

### P9.3 — Executive Analytics Dashboard
**File:** `frontend/app/dashboard/analytics/page.tsx`

Full redesign with role-aware views:

**CXO view (high-level):**
```tsx
<div className="space-y-6">
  {/* Header KPI row */}
  <div className="grid grid-cols-4 gap-4">
    <KPICard
      label="Documentation Coverage"
      value={`${(summary.avg_coverage_score * 100).toFixed(0)}%`}
      trend={summary.coverage_trend_30d}
      trendLabel="vs last month"
      icon={<ShieldCheck />}
      color="blue"
    />
    <KPICard label="Open Issues" value={summary.open_mismatches}
             trend={-mismatchDelta} trendLabel="resolved this week" color="amber" />
    <KPICard label="Critical Issues" value={summary.critical_mismatches}
             color={summary.critical_mismatches > 0 ? "red" : "green"} />
    <KPICard label="Documents Analyzed" value={summary.total_documents} color="purple" />
  </div>

  {/* Coverage trend chart */}
  <Card>
    <CardHeader>
      <CardTitle>Coverage Trend</CardTitle>
      <TimeRangeSelector value={range} onChange={setRange} options={[7,30,90]} />
    </CardHeader>
    <CardContent>
      <CoverageTrendChart data={trendData} />
      {/* Line chart: x=date, y=coverage_score, shaded area under line */}
    </CardContent>
  </Card>

  {/* Document leaderboard */}
  <div className="grid grid-cols-2 gap-4">
    <Card>
      <CardHeader><CardTitle>Most Improved</CardTitle></CardHeader>
      <CardContent>
        {leaderboard.most_improved.map(doc => (
          <div key={doc.id} className="flex items-center justify-between py-2">
            <span className="text-sm font-medium">{doc.name}</span>
            <span className="text-green-600 text-sm font-semibold">
              +{(doc.delta * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
    <Card>
      <CardHeader><CardTitle>Needs Attention</CardTitle></CardHeader>
      <CardContent>
        {leaderboard.most_degraded.map(doc => (
          <div key={doc.id} className="flex items-center justify-between py-2">
            <span className="text-sm font-medium">{doc.name}</span>
            <span className="text-red-500 text-sm font-semibold">
              {(doc.delta * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  </div>

  {/* Mismatch aging */}
  <Card>
    <CardHeader><CardTitle>Issue Aging</CardTitle></CardHeader>
    <CardContent>
      <MismatchAgingChart data={agingData} />
    </CardContent>
  </Card>
</div>
```

**Developer view:** Focus on code coverage per repo, mismatch breakdown by type, recent analysis runs.
**BA view:** Document coverage scores, requirement atom status, pending approvals.

### P9.4 — Usage Tracking & Tier Enforcement
**File:** `backend/app/services/billing_enforcement_service.py`

**Define limits per tier:**
```python
TIER_LIMITS = {
    "free": {
        "documents_per_month": 3,
        "repos_per_tenant": 1,
        "validation_runs_per_month": 10,
        "chat_messages_per_day": 20,
        "api_calls_per_day": 100,
        "export_enabled": False,
        "data_flow_diagrams": False,
        "integrations_enabled": False,
        "custom_glossary": False,
        "initiative_count": 1,
    },
    "pro": {
        "documents_per_month": 50,
        "repos_per_tenant": 10,
        "validation_runs_per_month": 500,
        "chat_messages_per_day": 500,
        "api_calls_per_day": 5000,
        "export_enabled": True,
        "data_flow_diagrams": True,
        "integrations_enabled": True,
        "custom_glossary": True,
        "initiative_count": 20,
    },
    "enterprise": {
        # All unlimited — enforce via contract, not hard limits
        "documents_per_month": None,
        "repos_per_tenant": None,
        "validation_runs_per_month": None,
        "chat_messages_per_day": None,
        "api_calls_per_day": None,
        "export_enabled": True,
        "data_flow_diagrams": True,
        "integrations_enabled": True,
        "custom_glossary": True,
        "initiative_count": None,
        "sso_enabled": True,
        "audit_export": True,
        "dedicated_support": True,
    }
}
```

**Enforcement middleware:**
```python
# backend/app/services/billing_enforcement_service.py
def check_limit(db, tenant_id: str, resource: str, increment: int = 1) -> bool:
    """
    Returns True if within limit, raises BillingLimitError if exceeded.
    Checks monthly usage from usage_logs table.
    Called at start of resource-consuming operations.
    """
    tenant = crud.tenant.get(db, tenant_id)
    limits = TIER_LIMITS[tenant.tier]
    limit = limits.get(resource)
    if limit is None:
        return True  # Unlimited

    # Get current month usage
    current = crud.usage_log.get_monthly_count(db, tenant_id, resource)
    if current + increment > limit:
        raise BillingLimitError(
            resource=resource,
            current=current,
            limit=limit,
            tier=tenant.tier,
            upgrade_url="/dashboard/billing/upgrade"
        )
    return True
```

**Apply enforcement in:**
- `POST /documents/` → check `documents_per_month`
- `POST /repositories/` → check `repos_per_tenant`
- `POST /validation/run` → check `validation_runs_per_month`
- `POST /chat/` → check `chat_messages_per_day`
- `GET /code-components/{id}/data-flow` → check `data_flow_diagrams`

**Graceful degradation — never a hard crash:**
```python
try:
    billing_enforcement_service.check_limit(db, tenant_id, "documents_per_month")
except BillingLimitError as e:
    raise HTTPException(402, detail={
        "error": "limit_exceeded",
        "resource": e.resource,
        "current": e.current,
        "limit": e.limit,
        "message": f"You've reached your {e.resource.replace('_', ' ')} limit on the {e.tier} plan.",
        "upgrade_url": e.upgrade_url
    })
```

### P9.5 — Usage Dashboard
**File:** `frontend/app/dashboard/admin/page.tsx`

Add usage meters per resource:
```tsx
<Card>
  <CardHeader><CardTitle>Plan Usage</CardTitle></CardHeader>
  <CardContent className="space-y-4">
    <UsageMeter
      label="Documents this month"
      current={usage.documents_this_month}
      limit={limits.documents_per_month}
    />
    <UsageMeter
      label="Validation runs"
      current={usage.validation_runs_this_month}
      limit={limits.validation_runs_per_month}
    />
    <UsageMeter
      label="Chat messages today"
      current={usage.chat_messages_today}
      limit={limits.chat_messages_per_day}
    />
    <UsageMeter
      label="Repositories"
      current={usage.repo_count}
      limit={limits.repos_per_tenant}
      type="gauge"  // Not a monthly reset — persistent count
    />
  </CardContent>
</Card>
```

`UsageMeter` component: progress bar that turns amber at 80%, red at 95%, with "Upgrade" CTA at 100%.

### P9.6 — AI Cost Dashboard
**File:** `frontend/app/dashboard/analytics/page.tsx`

Add "AI Cost Intelligence" card (admin/owner only):
```tsx
<Card>
  <CardHeader>
    <CardTitle>AI Cost Intelligence</CardTitle>
    <Badge variant="outline">This Month</Badge>
  </CardHeader>
  <CardContent>
    <div className="grid grid-cols-3 gap-4 mb-4">
      <div>
        <p className="text-2xl font-bold">${costs.total_this_month.toFixed(2)}</p>
        <p className="text-xs text-gray-500">Total AI spend</p>
      </div>
      <div>
        <p className="text-2xl font-bold text-green-600">
          ${costs.saved_this_month.toFixed(2)}
        </p>
        <p className="text-xs text-gray-500">Saved via BOE cache</p>
      </div>
      <div>
        <p className="text-2xl font-bold">{costs.efficiency_pct.toFixed(0)}%</p>
        <p className="text-xs text-gray-500">Cache hit rate</p>
      </div>
    </div>
    <CostBreakdownChart data={costs.by_feature} />
    {/* Stacked bar: validation / code_analysis / chat / mapping / auto_docs */}
  </CardContent>
</Card>
```

**Backend cost endpoint:**
```
GET /api/v1/analytics/ai-costs
  Returns: {
    total_this_month: float,
    saved_this_month: float,
    efficiency_pct: float,
    by_feature: { validation, code_analysis, chat, mapping, auto_docs },
    daily_trend: [{ date, cost, saved }],
    top_consumers: [{ document_name, cost }]
  }
```

Sourced from `UsageLog` + `AnalysisRun.gemini_calls_used` (Phase 4 field).

### P9.7 — Self-Serve Plan Upgrade Flow
**File:** `frontend/app/dashboard/billing/` (new pages)

```
/dashboard/billing/page.tsx          — Current plan + usage summary
/dashboard/billing/upgrade/page.tsx  — Plan comparison + checkout
/dashboard/billing/success/page.tsx  — Post-upgrade confirmation
```

**Plan comparison page:**
```tsx
<div className="grid grid-cols-3 gap-6 max-w-5xl mx-auto">
  {["free","pro","enterprise"].map(plan => (
    <PlanCard
      key={plan}
      plan={plan}
      price={PLAN_PRICES[plan]}
      features={PLAN_FEATURES[plan]}
      current={tenant.tier === plan}
      onSelect={() => startCheckout(plan)}
      highlighted={plan === "pro"}  // Pro is recommended
    />
  ))}
</div>
```

**Checkout:** Integrate Stripe Checkout. On successful payment:
1. Stripe webhook → `POST /api/v1/billing/webhook`
2. Update `tenant.tier` + `tenant_billing` record
3. Log `PLAN_UPGRADED` audit event
4. Send confirmation email
5. Redirect to `/billing/success`

**New billing endpoints:**
```
POST /api/v1/billing/create-checkout-session
  Body: { plan: "pro"|"enterprise" }
  Returns: { checkout_url: str }

POST /api/v1/billing/webhook
  Stripe webhook handler (verify signature)
  Events: checkout.session.completed, customer.subscription.deleted

GET /api/v1/billing/portal
  Returns Stripe Customer Portal URL (for invoice history, payment method update)

GET /api/v1/billing/current
  Returns: { tier, usage, limits, next_reset_date, invoices[] }
```

**Migration:** `backend/alembic/versions/s19b1_billing_stripe_fields.py`
Add `stripe_customer_id`, `stripe_subscription_id` to `tenant_billing`.

### P9.8 — Usage Alerts & Proactive Notifications
**File:** `backend/app/tasks/analytics_tasks.py`

Add to daily analytics task:
```python
def check_usage_alerts(db, tenant_id):
    """Sends proactive notifications when approaching limits."""
    usage = _get_current_usage(db, tenant_id)
    limits = TIER_LIMITS[tenant.tier]

    for resource, limit in limits.items():
        if limit is None:
            continue
        pct = usage.get(resource, 0) / limit
        if pct >= 0.90:
            notification_service.create(db, tenant_id=tenant_id,
                title=f"⚠️ {resource.replace('_',' ').title()} limit at {pct*100:.0f}%",
                body=f"You've used {usage[resource]}/{limit} this month. Upgrade to avoid interruption.",
                action_url="/dashboard/billing/upgrade",
                notification_type="billing_warning")
        elif pct >= 1.0:
            notification_service.create(db, tenant_id=tenant_id,
                title=f"🚫 {resource.replace('_',' ').title()} limit reached",
                body="Upgrade your plan to continue using this feature.",
                action_url="/dashboard/billing/upgrade",
                notification_type="billing_blocked")
```

### Verification
1. **Coverage snapshots:** Run `take_daily_coverage_snapshots` manually → verify rows in `coverage_snapshots` with correct scores
2. **Trend API:** `GET /analytics/coverage-trend?document_id=X&days=30` → returns array with correct dates and scores
3. **Tier enforcement:** Create free tenant, upload 3 documents → 4th upload returns HTTP 402 with `limit_exceeded` error and upgrade URL
4. **Graceful error:** Frontend shows upgrade modal (not a raw error) when 402 is received
5. **Usage meters:** Admin page shows document meter at 3/3 (100%, red) with upgrade CTA
6. **Stripe webhook:** Simulate `checkout.session.completed` → verify `tenant.tier` updated to "pro" and audit log created
7. **Cost dashboard:** After running validation → `GET /analytics/ai-costs` shows non-zero `total_this_month` and non-zero `saved_this_month` (Phase 4 savings)
8. **Usage alerts:** Set usage to 91% of limit manually → run `check_usage_alerts` → verify notification created

---

### Phase 9 Nice-to-Haves — Deferred to Future Phases (N1–N10)

> **Why deferred:** These features are all valuable but NONE of them block the core goal of Phase 9 (start charging customers). Ship the PAYG wallet first, let real customers tell us which of these matter most, then build them based on actual demand. See `PHASE_9_STRATEGY.md` Section 12 for the plain-English version.

#### N1 — Auto-Refill Wallet (Razorpay Subscriptions)
**Effort:** 2–3 days | **Depends:** Phase 9 (G7–G10 Razorpay live), GSTIN acquired
**File:** `backend/app/services/wallet_autorefill_service.py` (new)

**What:** Customer sets a rule: "when my wallet drops below ₹500, automatically top up ₹1,000 from my saved card." Uses Razorpay Subscriptions API with tokenized card.

**Why nice-to-have:** Removes the "oh I ran out of credit mid-analysis" friction. But manual recharge works fine for v1.

**Implementation sketch:**
- Add `autorefill_enabled`, `autorefill_trigger_inr`, `autorefill_amount_inr` to `tenant_billing`
- Celery beat task `check_wallet_autorefill` runs every 15 min
- On trigger: call Razorpay create-subscription-payment API, on success call existing `deduct_cost` inverse (credit)
- Write to `wallet_transactions` with `txn_type="autorefill_topup"`

---

#### N2 — Volume-Based Cost Alerts
**Effort:** 1 day | **Depends:** Phase 9 core
**File:** `backend/app/tasks/cost_anomaly_tasks.py` (new)

**What:** "Your spending jumped 63% this week vs last week. Is this expected?" Catches runaway automation, leaked API keys, or legitimate growth spikes.

**Implementation sketch:**
- Nightly Celery task compares `sum(usage_logs.cost_inr)` for last 7 days vs previous 7 days
- If delta > configurable threshold (default 50%), create notification + email
- Admin can mute per-tenant from settings
- Add `cost_alert_threshold_pct` column to `tenant_billing`

---

#### N3 — Per-User Monthly Spend Caps
**Effort:** 1 day | **Depends:** Phase 9 core
**File:** `backend/app/models/user_spend_cap.py` (new), enforcement hook in `billing_enforcement_service.py`

**What:** Admin sets "Rajesh cannot spend more than ₹500/month on AI analysis." Enforcement happens at pre-check time, blocks with friendly error.

**Implementation sketch:**
- New table `user_spend_caps(id, user_id, tenant_id, cap_inr, period='monthly', cap_used_inr, resets_at)`
- `check_can_afford_analysis()` reads cap, rejects if would exceed
- Admin UI under Settings → Team → per-user cap slider
- Celery task resets `cap_used_inr` on 1st of month

---

#### N4 — One-Click Invoice PDF Download from History
**Effort:** 1 day | **Depends:** N after GSTIN, Razorpay live
**File:** `backend/app/services/invoice_pdf_service.py` (new)

**What:** Every wallet top-up generates a downloadable GST-compliant invoice PDF. Customer sees a "Download Invoice" button next to each past recharge in their billing history.

**Why nice-to-have:** Phase 9 core already generates invoices via Razorpay's own PDF service (sent by email). This is a nicer in-app experience.

**Implementation sketch:**
- Use `reportlab` or `weasyprint` to generate PDFs matching GST format (our GSTIN, HSN code 998315, CGST/SGST split, etc.)
- Store PDFs in S3 / local filesystem with link in `wallet_transactions.extra_data`
- Add `GET /billing/invoices/{txn_id}/download` endpoint

---

#### N5 — In-App Notification Center for Billing Events
**Effort:** 1–2 days | **Depends:** Phase 9 core + existing notification system
**File:** Frontend `components/billing/NotificationBell.tsx` + backend notification categories

**What:** A bell icon with unread counter showing billing events: "₹500 recharge successful", "Wallet is at ₹87", "Invoice generated", "Auto-refill failed — check your card". Clicking jumps to the relevant page.

**Implementation sketch:**
- Extend existing `notification_service` with `category="billing"`
- Backend writes notifications on events (already have most of the hooks)
- Frontend bell reads from `/notifications?category=billing&unread=true`

---

#### N6 — AI-Based Cost Forecasting
**Effort:** 3–4 days | **Depends:** Phase 9 core + 30+ days of usage data
**File:** `backend/app/services/cost_forecast_service.py` (new)

**What:** "At your current rate you'll spend ₹3,200 this month." Simple ML model (moving average + seasonality detection) trained on historical `usage_logs`.

**Implementation sketch:**
- Start with simple 7-day moving average extrapolated to month-end (not ML at all)
- Later: exponential smoothing (statsmodels) if we see weekend dips or Monday spikes
- Show on billing dashboard with confidence band
- Warn if forecast exceeds `monthly_limit_inr`

---

#### N7 — Shareable Public Cost Reports
**Effort:** 2 days | **Depends:** Phase 9 core (export endpoint)
**File:** New model `public_cost_report(id, tenant_id, slug, expires_at, view_count)`, endpoint `/public/reports/{slug}`

**What:** User clicks "Share" on a cost report → gets a tokenized URL that their CFO or auditor can view without logging in. Read-only, expires in 30 days by default.

**Security notes:**
- Slug must be cryptographically random (secrets.token_urlsafe(32))
- Rate-limited per IP
- Never expose raw `tenant_id` in the URL
- Revocable by the owner at any time

---

#### N8 — Slack / Teams Billing Alerts
**Effort:** 2 days | **Depends:** Phase 9 core
**File:** `backend/app/integrations/slack_billing.py`, `backend/app/integrations/teams_billing.py`

**What:** "Post low-balance and auto-refill failures to my #finance Slack channel." OAuth flow to install a Slack/Teams bot, webhook to post messages.

**Implementation sketch:**
- Reuse existing integration pattern (we already have Jira/Confluence OAuth)
- New columns on `tenant_billing`: `slack_webhook_url`, `teams_webhook_url`
- Post JSON message on low_balance, autorefill_failed, monthly_limit_approaching

---

#### N9 — Multi-Currency Display
**Effort:** 1–2 days | **Depends:** Phase 9 core
**File:** `frontend/lib/currency.ts`, backend `exchange_rate_service.py` expansion

**What:** Indian customer sees ₹ everywhere. International customer (once Stripe is added) sees USD or EUR. Costs are stored in INR internally (source of truth) but displayed converted.

**Implementation sketch:**
- Add `preferred_currency` to `users` table (default "INR")
- Frontend `formatCurrency(amount_inr, user.preferred_currency)` helper
- Daily Celery task caches rates for USD, EUR, GBP, SGD, AED
- Important: always show "₹X / ~$Y" tooltip so the customer knows the true billing currency

---

#### N10 — Budget vs Actual Variance Tracking
**Effort:** 2 days | **Depends:** Phase 9 core
**File:** New model `tenant_budget(id, tenant_id, month, budgeted_inr, actual_inr)`, service, endpoint

**What:** CFO sets "budget = ₹2,000 for April". Dashboard shows "Actual so far: ₹2,400 (120% of budget)" with red indicator. Historical variance chart across months.

**Implementation sketch:**
- Admin UI: Settings → Budgets → set monthly budget per tenant (or per team in a future iteration)
- Monthly Celery task snapshots actual from `current_month_cost` into `tenant_budget` on the 1st
- Analytics endpoint returns budget vs actual for last 12 months
- Variance alert notifications at 80%, 100%, 120%

---

### Nice-to-Have Priority Order (Recommended)

If/when we get time for these, build them in this order based on customer value per engineering day:

1. **N1 (Auto-refill)** — removes the biggest friction point in the wallet UX
2. **N5 (Notification center)** — makes the whole billing experience feel more alive
3. **N3 (Per-user spend caps)** — #1 enterprise-customer ask, easy to build
4. **N4 (Invoice PDF download)** — finance teams love this
5. **N2 (Volume alerts)** — catches genuine problems (leaked keys, runaway scripts)
6. **N10 (Budget vs actual)** — strong CFO appeal
7. **N6 (Cost forecasting)** — nice demo feature but not urgent
8. **N8 (Slack/Teams alerts)** — high value for the subset of customers who already live in Slack
9. **N7 (Shareable reports)** — specific use case, ship when a customer asks
10. **N9 (Multi-currency)** — only relevant once we have international customers (Stripe phase)

---

## PHASE 10 — LLM Strategy Foundation (Training Pipeline, LoRA Groundwork, Evaluation)
**Priority: Strategic — not urgent today, but every week without it loses training data value**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 1 (training flywheel must be running to have data)**
**Estimated complexity: Very High**

### Context
The long-term competitive moat for DokyDoc is not the product features — it is the training data accumulating in `training_examples` as developers accept/reject AI judgments every day. Today DokyDoc calls Gemini for everything. The roadmap is:

```
Now:      Gemini API (100% of AI calls) — flexible, expensive, generic
Phase 10: Training pipeline + evaluation harness — capture & measure quality
Phase 14: Fine-tuned shared base model — DokyDoc-specific domain knowledge
Phase 16: Per-tenant LoRA adapters — company-specific understanding at 50-200MB per tenant
```

This phase does NOT require building or hosting an LLM. It builds the **infrastructure** (data pipeline, eval harness, export tooling) so that when the team has funding to fine-tune, the training data is clean, versioned, and ready. It also builds the model quality dashboard so you can measure whether Gemini's current outputs are improving or degrading over time.

**Architecture decision (from conversation):**
- NOT one LLM per tenant (too expensive: 16GB × N tenants)
- Shared base model (16GB) + per-tenant LoRA adapters (50-200MB via vLLM multi-LoRA serving)
- This phase lays the groundwork; actual training happens in Phase 14+

### P10.1 — Training Data Pipeline
**File:** `backend/app/services/training_pipeline_service.py` (new)

```python
class TrainingPipelineService:
    """
    Converts raw TrainingExample rows into clean, versioned training datasets.
    Handles deduplication, quality filtering, format conversion, and versioning.
    """

    def export_dataset(
        self,
        db,
        tenant_id: int | None,  # None = all tenants (for shared model training)
        example_type: str | None,
        min_quality_score: float = 0.0,
        require_human_label: bool = True,
        format: str = "openai_chat",  # "openai_chat" | "alpaca" | "sharegpt"
        split: tuple[float, float, float] = (0.8, 0.1, 0.1),  # train/val/test
    ) -> TrainingDataset:
        """
        Filters, deduplicates, formats, and splits training examples.
        Returns { train: [...], val: [...], test: [...], metadata: {...} }
        """
        examples = self._fetch_and_filter(db, tenant_id, example_type,
                                          min_quality_score, require_human_label)
        examples = self._deduplicate(examples)           # Remove near-duplicates
        examples = self._balance_labels(examples)        # Balance accept/reject ratio
        formatted = self._format_examples(examples, format)
        return self._split_dataset(formatted, split)

    def _format_openai_chat(self, example: TrainingExample) -> dict:
        """
        Converts a TrainingExample to OpenAI fine-tuning JSONL format.
        Uses the actual prompt that was sent to Gemini as the 'user' turn
        and the human-corrected label as the 'assistant' turn.
        """
        return {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_BY_TYPE[example.example_type]},
                {"role": "user",   "content": json.dumps(example.input_context)},
                {"role": "assistant", "content": self._get_ideal_output(example)}
            ]
        }

    def _get_ideal_output(self, example: TrainingExample) -> str:
        """
        If human edited → use correction.
        If human accepted → use AI output (it was correct).
        If human rejected → use inverted/corrected output.
        """
        if example.human_label == "edited" and example.human_correction:
            return json.dumps(example.human_correction)
        elif example.human_label == "accepted":
            return json.dumps(example.ai_output)
        else:  # rejected
            return self._invert_output(example.ai_output, example.example_type)

    def _deduplicate(self, examples: list) -> list:
        """
        Removes near-duplicate input_contexts using cosine similarity.
        Keeps the one with human label (over AI-only), then by recency.
        Threshold: 0.95 cosine similarity = duplicate.
        """
```

### P10.2 — Dataset Versioning
**New model:** `backend/app/models/training_dataset_version.py`

```python
class TrainingDatasetVersion(Base):
    __tablename__ = "training_dataset_versions"

    id: int (PK)
    tenant_id: int | None   # NULL = multi-tenant shared dataset
    version: str            # "v1.0.0", "v1.1.0" — semantic versioning
    example_type: str | None  # "mismatch_judgment" / "mapping_judgment" / None = all
    format: str             # "openai_chat", "alpaca", "sharegpt"

    # Dataset statistics
    total_examples: int
    train_count: int
    val_count: int
    test_count: int
    label_distribution: dict (JSON)  # {"accepted": 234, "rejected": 89, "edited": 41}
    avg_quality_score: float | None

    # Storage
    storage_path: str | None     # S3/GCS path to exported JSONL files
    checksum_train: str | None   # SHA-256 of train.jsonl
    checksum_val: str | None
    checksum_test: str | None

    # Lineage
    created_by_user_id: int | None
    notes: str | None            # "Includes Q1 2026 mismatch feedback"
    is_active: bool (default True)  # Current version used for training

    created_at: datetime
```

**Migration:** `backend/alembic/versions/s20a1_training_dataset_versions.py`

**Export endpoint (admin only):**
```
POST /api/v1/admin/training/export-dataset
  Body: {
    tenant_id?: int,
    example_type?: str,
    format: "openai_chat" | "alpaca",
    min_quality_score?: float,
    notes?: str
  }
  Action:
    1. Call training_pipeline_service.export_dataset()
    2. Upload JSONL files to configured S3 bucket
    3. Create TrainingDatasetVersion record with checksums
    4. Return { version_id, train_count, val_count, test_count, download_urls }
```

### P10.3 — Model Quality Evaluation Harness
**New file:** `backend/app/services/model_evaluation_service.py`

The evaluation harness runs the current AI model against a held-out test set and measures how well it agrees with human labels.

```python
class ModelEvaluationService:
    """
    Runs evaluation against the test split of a TrainingDatasetVersion.
    Produces precision/recall/F1 per example_type.
    Enables tracking quality over time as Gemini changes its model.
    """

    async def evaluate_dataset_version(
        self, db, dataset_version_id: int
    ) -> EvaluationResult:
        """
        For each example in the test split:
          1. Re-run the EXACT same prompt through current AI model
          2. Compare AI output to human_label (ground truth)
          3. Compute metrics
        """
        dataset = crud.training_dataset_version.get(db, dataset_version_id)
        test_examples = self._load_test_split(dataset.storage_path)

        predictions = []
        for example in test_examples:
            # Re-run through current AI (uses same prompt as original)
            ai_output = await self._run_inference(example["messages"][1]["content"],
                                                   example["messages"][0]["content"])
            predictions.append({
                "ground_truth": example["messages"][2]["content"],
                "prediction": ai_output,
                "example_type": dataset.example_type
            })

        return self._compute_metrics(predictions)

    def _compute_metrics(self, predictions: list) -> EvaluationResult:
        """
        Per example_type metrics:
          - Accuracy: % of predictions matching ground truth label
          - Precision / Recall / F1 for binary (match/no-match) verdicts
          - Confidence calibration: does AI's confidence correlate with accuracy?
          - Hallucination rate: AI mentions concepts not in input_context
        """
```

**New model: `ModelEvaluationRun`**
```python
class ModelEvaluationRun(Base):
    __tablename__ = "model_evaluation_runs"

    id: int
    dataset_version_id: int (FK)
    ai_model_name: str          # "gemini-2.0-flash", "gemini-2.5-pro", etc.
    ai_model_version: str | None

    # Overall metrics
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    hallucination_rate: float | None

    # Per example_type breakdown (JSON)
    metrics_by_type: dict

    # Regression detection
    is_regression: bool         # True if accuracy < previous run by > 2%
    previous_run_id: int | None

    run_duration_seconds: int
    examples_evaluated: int
    created_at: datetime
```

**Migration:** `backend/alembic/versions/s20b1_model_evaluation_runs.py`

**Automated evaluation schedule:**
```python
# Run evaluation weekly — catches Gemini model drift automatically
"weekly-model-eval": {
    "task": "run_model_evaluation",
    "schedule": crontab(day_of_week=1, hour=2, minute=0)  # Every Monday 02:00 UTC
}
```

If `is_regression=True`: send alert to admin users immediately.

### P10.4 — Model Quality Dashboard
**File:** `frontend/app/dashboard/admin/page.tsx` (or new `/brain/model-quality` page)

```tsx
<Card>
  <CardHeader>
    <CardTitle>AI Model Quality</CardTitle>
    <Badge variant="outline">{latestEval.ai_model_name}</Badge>
  </CardHeader>
  <CardContent>
    {/* Overall metrics */}
    <div className="grid grid-cols-4 gap-4 mb-6">
      <MetricTile label="Accuracy"
                  value={`${(latestEval.accuracy * 100).toFixed(1)}%`}
                  trend={accuracyDelta} />
      <MetricTile label="Precision" value={`${(latestEval.precision*100).toFixed(1)}%`} />
      <MetricTile label="Recall"    value={`${(latestEval.recall*100).toFixed(1)}%`} />
      <MetricTile label="F1 Score"  value={latestEval.f1_score.toFixed(3)} />
    </div>

    {/* Regression alert */}
    {latestEval.is_regression && (
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
        <p className="text-red-700 text-sm font-medium">
          ⚠️ Regression detected vs previous evaluation
          ({(regressionDelta * 100).toFixed(1)}% accuracy drop)
        </p>
      </div>
    )}

    {/* Per-type breakdown table */}
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-gray-500">
          <th>Type</th><th>Accuracy</th><th>F1</th><th>Examples</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(latestEval.metrics_by_type).map(([type, metrics]) => (
          <tr key={type} className="border-t">
            <td className="py-2 font-mono text-xs">{type}</td>
            <td>{(metrics.accuracy * 100).toFixed(1)}%</td>
            <td>{metrics.f1.toFixed(3)}</td>
            <td className="text-gray-400">{metrics.count}</td>
          </tr>
        ))}
      </tbody>
    </table>

    {/* Training data stats */}
    <div className="mt-4 pt-4 border-t text-sm text-gray-500">
      Training examples: {stats.total} total ·
      {stats.labeled} labeled · {stats.unlabeled} awaiting review
    </div>
  </CardContent>
</Card>
```

### P10.5 — LoRA Adapter Architecture Groundwork
**New file:** `backend/app/services/lora_registry_service.py`

This service does NOT train models yet. It defines the registry, metadata contracts, and serving interface so that when LoRA adapters are introduced, the rest of the codebase doesn't change.

```python
class LoRAAdapterRegistry:
    """
    Registry of per-tenant LoRA adapter metadata.
    Actual adapter weights stored in S3/GCS.
    vLLM multi-LoRA serving loads adapters on demand.
    """

    def register_adapter(self, tenant_id: int, adapter_path: str,
                         base_model: str, version: str,
                         dataset_version_id: int) -> LoRAAdapterRecord:
        """
        Registers a trained LoRA adapter for a tenant.
        adapter_path: s3://bucket/adapters/{tenant_id}/{version}/
        """

    def get_active_adapter(self, tenant_id: int) -> LoRAAdapterRecord | None:
        """Returns the current active adapter for a tenant, or None if using base model."""

    def route_inference(self, tenant_id: int, prompt: str) -> InferenceTarget:
        """
        Returns the inference target for a given tenant:
          - If tenant has active LoRA adapter → route to vLLM with lora_request
          - Else → route to Gemini API (current behavior, unchanged)
        This is the SINGLE switch point. All AI services call this instead of
        calling gemini_service directly.
        """
        adapter = self.get_active_adapter(tenant_id)
        if adapter:
            return InferenceTarget(
                type="lora",
                base_model=adapter.base_model,
                lora_path=adapter.adapter_path,
                lora_id=f"tenant_{tenant_id}"
            )
        return InferenceTarget(type="gemini", model=settings.GEMINI_MODEL)
```

**New model: `LoRAAdapterRecord`**
```python
class LoRAAdapterRecord(Base):
    __tablename__ = "lora_adapter_records"

    id: int
    tenant_id: int (FK)
    version: str                  # "v1.0.0"
    base_model: str               # "gemma-3-9b-it", "llama-3.1-8b-instruct"
    adapter_path: str             # S3 path
    dataset_version_id: int (FK training_dataset_versions.id)

    # Training metrics
    training_loss: float | None
    eval_accuracy: float | None
    eval_f1: float | None
    training_examples_count: int | None

    # Deployment
    is_active: bool (default False)
    activated_at: datetime | None
    deactivated_at: datetime | None
    deactivation_reason: str | None  # "regression", "manual", "superseded"

    created_at: datetime
```

**Migration:** `backend/alembic/versions/s20c1_lora_adapter_records.py`

### P10.6 — AI Provider Router Upgrade
**File:** `backend/app/services/ai/provider_router.py`

Current state: Routes between Claude and Gemini. Extend to support vLLM self-hosted endpoint.

```python
class AIProviderRouter:
    def route(self, tenant_id: int, prompt_type: PromptType) -> AIProvider:
        """
        Routing priority:
        1. If tenant has active LoRA adapter AND vLLM endpoint configured → LoRA
        2. If prompt_type in GEMINI_ONLY_TYPES → Gemini (multimodal, embeddings)
        3. Default → configured primary provider (Gemini or Claude)
        """
        if settings.VLLM_ENDPOINT:
            adapter = lora_registry.get_active_adapter(tenant_id)
            if adapter:
                return VLLMProvider(
                    endpoint=settings.VLLM_ENDPOINT,
                    lora_request=LoRARequest(
                        lora_name=f"tenant_{tenant_id}",
                        lora_path=adapter.adapter_path
                    )
                )
        return self._default_provider(prompt_type)
```

Add `VLLM_ENDPOINT: str | None = None` to `backend/app/core/config.py`. When `None` (default), vLLM path is never taken — zero behavior change.

### P10.7 — Training Data Labeling Queue
**New endpoint:** `backend/app/api/endpoints/analytics.py`

Surface unlabeled examples for admin review (speeds up labeling):
```
GET /api/v1/admin/training/labeling-queue
  Query: example_type?, limit=20
  Returns: list of TrainingExample with input_context + ai_output, awaiting human_label

POST /api/v1/admin/training/labeling-queue/{id}/label
  Body: { label: "accepted"|"rejected"|"edited", correction?: dict }
  Action: calls crud.training_example.record_human_label()
```

**Labeling queue UI (admin only):**
```tsx
// A simple card-by-card review interface — like a flashcard deck
<div className="max-w-2xl mx-auto">
  <div className="text-sm text-gray-500 mb-4">
    {queue.unlabeled_count} examples awaiting review
  </div>
  <Card>
    <CardHeader>
      <Badge>{example.example_type}</Badge>
      <span className="text-xs text-gray-400">
        AI confidence: {(example.ai_output.confidence * 100).toFixed(0)}%
      </span>
    </CardHeader>
    <CardContent>
      <div className="bg-gray-50 rounded p-3 mb-3 text-sm font-mono">
        {JSON.stringify(example.input_context, null, 2)}
      </div>
      <div className="bg-blue-50 rounded p-3 text-sm">
        <p className="font-medium mb-1">AI said:</p>
        {JSON.stringify(example.ai_output, null, 2)}
      </div>
    </CardContent>
    <CardFooter className="flex gap-2">
      <button onClick={() => label('accepted')}
              className="flex-1 bg-green-600 text-white py-2 rounded">
        ✓ Correct
      </button>
      <button onClick={() => label('rejected')}
              className="flex-1 bg-red-500 text-white py-2 rounded">
        ✗ Wrong
      </button>
      <button onClick={() => setEditing(true)}
              className="flex-1 bg-amber-500 text-white py-2 rounded">
        ✎ Correct it
      </button>
    </CardFooter>
  </Card>
</div>
```

### P10.8 — Training Readiness Report
**Endpoint:** `GET /api/v1/admin/training/readiness`

Before investing in fine-tuning, quantify dataset readiness:
```json
{
  "ready_for_training": false,
  "reason": "Insufficient labeled examples (need ≥500, have 127)",
  "current_state": {
    "total_examples": 847,
    "labeled": 127,
    "label_distribution": {"accepted": 89, "rejected": 28, "edited": 10},
    "coverage_by_type": {
      "mismatch_judgment": {"count": 94, "labeled": 94, "ready": true},
      "mapping_judgment": {"count": 503, "labeled": 33, "ready": false},
      "chat_response": {"count": 250, "labeled": 0, "ready": false}
    }
  },
  "recommendations": [
    "Label 467 more mapping_judgment examples to reach training threshold",
    "Start labeling chat_response examples — 250 available",
    "Current mismatch_judgment dataset is ready for LoRA fine-tuning"
  ],
  "estimated_fine_tune_cost": {
    "openai_gpt4o_mini": "$12.40",
    "gemini_flash": "Contact Google",
    "self_hosted_llama3_8b": "~4h on A100 GPU (~$20 on Lambda)"
  }
}
```

### Verification
1. **Dataset export:** Call `POST /admin/training/export-dataset` → downloads valid JSONL with `messages` array format, `train.jsonl` has 80% of examples
2. **Deduplication:** Inject 10 near-identical examples → export → verify deduped to ~2-3
3. **Label balance:** Export with 90% accepted / 10% rejected → verify `_balance_labels` downsamples accepted to ~60/40 ratio
4. **Evaluation harness:** Run `evaluate_dataset_version` on a small test set → verify `ModelEvaluationRun` row created with F1 > 0
5. **Regression detection:** Create two evaluation runs where second has 5% lower accuracy → verify `is_regression=True` and alert notification sent
6. **Provider router:** Set `VLLM_ENDPOINT=None` → verify all AI calls still go to Gemini (zero behavior change)
7. **Labeling queue:** GET labeling queue → returns unlabeled examples; POST label → `human_label` field updated
8. **Readiness report:** `GET /admin/training/readiness` → returns meaningful counts and recommendations

---

## PHASE 11 — Auto-Docs & Living Documentation
**Priority: High — flagship feature, directly drives revenue and retention**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability), Phase 5 (dynamic prompting for industry-aware docs)**
**Estimated complexity: High**

### Context
DokyDoc already has `auto_docs_service.py`, `generated_docs` model, and `auto-docs/page.tsx`. The gaps are: generated docs are one-shot snapshots (they go stale immediately), there's no diff view when the underlying BRD or code changes, no structured format templates (IEEE 830, RFC, OpenAPI), no multi-source synthesis (combining 3 BRDs + 2 repos into one unified doc), and no "living documentation" mode where the doc auto-regenerates on code changes. This phase makes auto-docs the product feature that enterprises pay for.

### P11.1 — Multi-Source Document Synthesis
**File:** `backend/app/services/auto_docs_service.py`

Current state: Generates docs from a single source (one BRD or one repo). Extend to synthesize across multiple sources simultaneously.

```python
class AutoDocsService:

    async def generate_from_sources(
        self,
        db,
        tenant_id: int,
        sources: list[DocSource],   # NEW — list of sources
        template: str,
        context: PromptContext | None = None
    ) -> GeneratedDoc:
        """
        sources can be any combination of:
          DocSource(type="document", id=7)
          DocSource(type="repository", id=3)
          DocSource(type="initiative", id=1)  # all assets of initiative
          DocSource(type="concept", id=42)    # ontology concept + all its relationships
        """
        # 1. Collect all artifacts from all sources
        artifacts = await self._collect_artifacts(db, sources, tenant_id)

        # 2. Build unified context from BOE knowledge graph
        #    (already knows relationships between all sources)
        graph_context = self._build_graph_context(db, artifacts, tenant_id)

        # 3. Check token budget — chunk if needed
        if self._estimate_tokens(artifacts) > MAX_CONTEXT_TOKENS:
            return await self._chunked_generation(artifacts, graph_context, template, context)

        # 4. Single Gemini call with all context + template
        prompt = prompt_manager.get_prompt(
            PromptType.GENERATE_DOCUMENT,
            variables={"artifacts": artifacts, "graph": graph_context, "template": template},
            context=context  # Phase 5: industry + glossary injection
        )
        content = await gemini_service.generate(prompt)

        # 5. Store with source tracking
        return crud.generated_doc.create(db, obj_in={
            "tenant_id": tenant_id,
            "content": content,
            "template": template,
            "source_ids": [s.id for s in sources],
            "source_types": [s.type for s in sources],
            "generation_method": "multi_source",
            "status": "draft"
        })
```

**New `generated_docs` fields:**
```python
source_ids: list[int] (JSON array)    # All source artifact IDs
source_types: list[str] (JSON array)  # Corresponding types
generation_method: str                # "single", "multi_source", "incremental"
template: str                         # Template used (see P11.3)
parent_doc_id: int | None             # For versioned docs (points to previous version)
is_latest: bool (default True)        # False for older versions
stale_at: datetime | None             # When source changed, making this doc stale
auto_regen_enabled: bool (default False)
```

**Migration:** `backend/alembic/versions/s21a1_generated_doc_multi_source.py`

**Multi-source endpoint:**
```
POST /api/v1/auto-docs/generate
  Body: {
    sources: [
      { type: "document", id: 7 },
      { type: "repository", id: 3 },
      { type: "initiative", id: 1 }
    ],
    template: "technical_spec" | "brd" | "api_reference" | "release_notes" | ...,
    title: str,
    auto_regen: bool
  }
  Response: GeneratedDoc (status: "generating" initially, then webhook when done)
```

### P11.2 — Living Documentation (Auto-Regeneration)
**File:** `backend/app/tasks/document_pipeline.py`, `backend/app/services/auto_docs_service.py`

When `GeneratedDoc.auto_regen_enabled = True`, any change to a source triggers regeneration:

```python
# Trigger points — add to each source's update handler:

# 1. After new document version uploaded (document_pipeline.py):
_trigger_regen_for_generated_docs(db, source_type="document", source_id=document.id)

# 2. After code analysis complete (code_analysis_service.py):
_trigger_regen_for_generated_docs(db, source_type="repository", source_id=repository_id)

# 3. After validation run creates new mismatches (validation_service.py):
_trigger_regen_for_generated_docs(db, source_type="document", source_id=document_id)

def _trigger_regen_for_generated_docs(db, source_type, source_id):
    docs = crud.generated_doc.get_by_source(db, source_type, source_id,
                                            auto_regen_enabled=True)
    for doc in docs:
        # Mark as stale immediately (UI shows "outdated" badge)
        crud.generated_doc.update(db, id=doc.id, obj_in={"stale_at": datetime.utcnow()})
        # Enqueue regeneration (debounced: don't regen twice in same hour)
        regen_generated_doc.apply_async(
            args=[doc.id, doc.tenant_id],
            countdown=300  # 5 min delay — batch rapid successive changes
        )
```

**Celery task:**
```python
@celery_app.task(name="regen_generated_doc", max_retries=2)
def regen_generated_doc(generated_doc_id: int, tenant_id: int):
    """
    Regenerates a GeneratedDoc from its sources.
    Creates a new version (parent_doc_id = old doc id).
    Sends notification to document owner when complete.
    """
    old_doc = crud.generated_doc.get(db, generated_doc_id)

    # Mark old doc as not latest
    crud.generated_doc.update(db, id=old_doc.id, obj_in={"is_latest": False})

    # Generate new version
    new_doc = await auto_docs_service.generate_from_sources(
        db, tenant_id,
        sources=_rebuild_sources(old_doc),
        template=old_doc.template
    )
    crud.generated_doc.update(db, id=new_doc.id, obj_in={
        "parent_doc_id": old_doc.id,
        "auto_regen_enabled": True,
        "title": old_doc.title
    })

    # Notify owner
    notification_service.create(db, tenant_id=tenant_id,
        title=f"📄 '{old_doc.title}' has been updated",
        body="Your auto-generated document was refreshed based on recent changes.",
        action_url=f"/dashboard/auto-docs/{new_doc.id}")
```

### P11.3 — Document Format Templates
**New file:** `backend/app/services/ai/doc_templates.py`

Structured templates that guide the generation prompt for different output formats:

```python
DOC_TEMPLATES = {
    "technical_spec": TechnicalSpecTemplate(
        sections=["Overview", "Architecture", "API Contracts",
                  "Data Models", "Error Handling", "Security Considerations",
                  "Performance Characteristics", "Dependencies"],
        tone="technical",
        include_code_snippets=True
    ),

    "brd": BRDTemplate(
        sections=["Executive Summary", "Business Objectives", "Scope",
                  "Functional Requirements", "Non-Functional Requirements",
                  "Assumptions & Constraints", "Acceptance Criteria"],
        tone="business",
        format="IEEE_830"
    ),

    "api_reference": APIReferenceTemplate(
        format="openapi_prose",  # Prose description of OpenAPI spec
        sections=["Authentication", "Endpoints", "Request/Response Schemas",
                  "Error Codes", "Rate Limits", "Examples"],
        include_curl_examples=True
    ),

    "release_notes": ReleaseNotesTemplate(
        sections=["Summary", "New Features", "Bug Fixes",
                  "Breaking Changes", "Migration Guide", "Known Issues"],
        tone="product"
    ),

    "runbook": RunbookTemplate(
        sections=["Service Overview", "Prerequisites", "Deployment Steps",
                  "Configuration", "Monitoring & Alerts", "Rollback Procedure",
                  "Troubleshooting FAQ"],
        tone="operational"
    ),

    "onboarding_guide": OnboardingTemplate(
        sections=["What This Service Does", "Getting Started",
                  "Key Concepts", "Common Operations", "FAQs"],
        tone="friendly",
        audience="new_developer"
    ),

    "compliance_report": ComplianceTemplate(
        sections=["Executive Summary", "Regulatory Requirements",
                  "Implementation Evidence", "Gaps & Remediation",
                  "Risk Assessment", "Sign-off"],
        tone="formal",
        regulatory_framework=None  # Filled from tenant.settings.regulatory_context (Phase 5)
    ),

    "custom": CustomTemplate()  # User defines sections manually
}
```

Each template generates a specific prompt structure instructing Gemini on tone, section order, depth, and what to include/exclude from the source artifacts.

### P11.4 — Version Diff View
**File:** `frontend/app/dashboard/auto-docs/[id]/page.tsx` (extend), new diff component

When a GeneratedDoc has a `parent_doc_id`, show a diff view:

```tsx
{doc.parent_doc_id && (
  <div className="flex items-center gap-2 mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
    <RefreshCw className="h-4 w-4 text-amber-600" />
    <span className="text-sm text-amber-700">
      This document was updated. View what changed from the previous version.
    </span>
    <button onClick={() => setShowDiff(true)}
            className="text-sm text-blue-600 hover:underline ml-auto">
      View diff →
    </button>
  </div>
)}

{showDiff && (
  <DocumentDiffModal
    oldDocId={doc.parent_doc_id}
    newDocId={doc.id}
    onClose={() => setShowDiff(false)}
  />
)}
```

**New component:** `frontend/components/documents/DocumentDiffModal.tsx`

Uses `diff` npm library to compute character-level diff between old and new markdown content:
```tsx
import { diffWords } from 'diff'

const parts = diffWords(oldContent, newContent)
return (
  <div className="font-mono text-sm whitespace-pre-wrap">
    {parts.map((part, i) => (
      <span key={i}
            className={part.added ? 'bg-green-100 text-green-800'
                      : part.removed ? 'bg-red-100 text-red-800 line-through'
                      : 'text-gray-700'}>
        {part.value}
      </span>
    ))}
  </div>
)
```

**Backend diff endpoint:**
```
GET /api/v1/auto-docs/{id}/diff?compare_to={parent_id}
  Returns: {
    old_version: { id, title, created_at, content },
    new_version: { id, title, created_at, content },
    stats: { added_chars, removed_chars, sections_changed: ["API Contracts", "Data Models"] }
  }
```

### P11.5 — Version History Panel
**File:** `frontend/app/dashboard/auto-docs/[id]/page.tsx`

Add version history sidebar (reuse pattern from `documents/VersionHistoryPanel.tsx`):

```tsx
<VersionHistoryPanel
  versions={docVersions}  // Fetched via GET /auto-docs/{id}/versions
  currentId={doc.id}
  onSelect={(versionId) => router.push(`/dashboard/auto-docs/${versionId}`)}
  renderItem={(version) => (
    <div>
      <div className="text-sm font-medium">{timeAgo(version.created_at)}</div>
      <div className="text-xs text-gray-400">
        {version.generation_method === 'auto_regen' ? '🔄 Auto-updated' : '✋ Manual'}
      </div>
    </div>
  )}
/>
```

**Backend:**
```
GET /api/v1/auto-docs/{id}/versions
  Returns: all versions in chain (follows parent_doc_id links)
  Sorted: newest first
```

### P11.6 — Staleness Detection & UI
**File:** `frontend/app/dashboard/auto-docs/page.tsx`

Show staleness state prominently in the docs list:

```tsx
{doc.stale_at && (
  <Badge variant="outline" className="text-amber-600 border-amber-400">
    ⚠ Outdated since {timeAgo(doc.stale_at)}
  </Badge>
)}
{doc.auto_regen_enabled && !doc.stale_at && (
  <Badge variant="outline" className="text-green-600 border-green-400">
    ✓ Live
  </Badge>
)}
```

**Staleness endpoint:**
```
GET /api/v1/auto-docs/stale
  Returns: list of GeneratedDocs where stale_at IS NOT NULL, ordered by stale_at
  Used for: admin review queue of outdated docs
```

### P11.7 — Auto-Docs from Code Only (No BRD Required)
**File:** `backend/app/services/auto_docs_service.py`

New generation mode — generate documentation purely from code analysis (useful onboarding tool when no BRDs exist yet):

```python
async def generate_from_repo(
    self, db, tenant_id: int, repository_id: int,
    template: str = "technical_spec"
) -> GeneratedDoc:
    """
    Generates docs from structured_analysis + knowledge graph alone.
    No BRD needed. Uses:
      - CodeComponent.structured_analysis (api_contracts, data_flows, etc.)
      - OntologyConcept + OntologyRelationship (business context)
      - DataFlowEdge (request traces from Phase 3)
      - Repository.synthesis (existing repo-level summary)
    """
```

**Supported templates for code-only:** `technical_spec`, `api_reference`, `runbook`, `onboarding_guide`

### P11.8 — Export Formats
**File:** `backend/app/api/endpoints/auto_docs.py`

```
GET /api/v1/auto-docs/{id}/export
  Query: format=markdown|pdf|docx|confluence_storage|html
  Returns: file download

Formats:
  markdown        → raw .md file (already stored)
  pdf             → weasyprint render of markdown → PDF
  docx            → python-docx conversion
  confluence_storage → Confluence Storage Format XML (for manual import)
  html            → styled HTML with company branding
```

**DOCX export:** `python-docx` library. Add to `requirements.txt`.
Heading levels from markdown → Word heading styles. Code blocks → `Courier New` style.

### P11.9 — Auto-Docs Dashboard
**File:** `frontend/app/dashboard/auto-docs/page.tsx`

Full redesign of the auto-docs page:

```tsx
<div>
  {/* Header with generate button */}
  <div className="flex items-center justify-between mb-6">
    <div>
      <h1 className="text-2xl font-bold">Documentation</h1>
      <p className="text-gray-500">Auto-generated from your BRDs and code</p>
    </div>
    <button onClick={() => setShowGenerateModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2">
      <Plus className="h-4 w-4" /> Generate New
    </button>
  </div>

  {/* Stale docs alert */}
  {staleDocs.length > 0 && (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
      <p className="text-amber-800 font-medium">
        {staleDocs.length} documents need updating
      </p>
      <button onClick={regenAllStale}
              className="text-sm text-blue-600 hover:underline mt-1">
        Regenerate all outdated docs
      </button>
    </div>
  )}

  {/* Doc grid */}
  <div className="grid grid-cols-3 gap-4">
    {docs.map(doc => (
      <DocCard
        key={doc.id}
        doc={doc}
        isStale={!!doc.stale_at}
        isLive={doc.auto_regen_enabled}
        onOpen={() => router.push(`/dashboard/auto-docs/${doc.id}`)}
        onRegenerate={() => regenDoc(doc.id)}
        onPublish={() => publishDoc(doc.id)}
        onExport={(format) => exportDoc(doc.id, format)}
      />
    ))}
  </div>

  {/* Generate modal */}
  <GenerateDocModal
    open={showGenerateModal}
    onClose={() => setShowGenerateModal(false)}
    onGenerate={handleGenerate}
    documents={availableDocs}
    repositories={availableRepos}
    initiatives={availableInitiatives}
    templates={DOC_TEMPLATES}
  />
</div>
```

### Verification
1. **Multi-source:** Generate a doc from 1 document + 1 repo → verify content references both source artifacts
2. **Living doc:** Enable `auto_regen` on a doc, upload a new document version → verify `stale_at` set within seconds, regeneration task enqueued
3. **Version chain:** After regen completes → verify new doc has `parent_doc_id` set, old doc has `is_latest=False`
4. **Diff view:** Open diff between old and new version → green/red highlighted word-level diff renders correctly
5. **Templates:** Generate with `compliance_report` template → output contains "Regulatory Requirements" and "Risk Assessment" sections
6. **Export:** `GET /auto-docs/{id}/export?format=pdf` → downloads valid PDF with correct content
7. **Code-only:** `generate_from_repo` for a repo with no linked BRDs → generates technical_spec with API endpoints from `structured_analysis.api_contracts`
8. **Staleness badge:** Stale doc in list shows "⚠ Outdated" badge; live doc shows "✓ Live"
9. **Non-breaking:** Existing generated docs remain accessible; single-source generation still works unchanged

---

## PHASE 12 — Performance, Scalability & Infrastructure
**Priority: Required before enterprise launch. Non-negotiable for regulated customers.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline)**
**Estimated complexity: High**

### Context
At 10 tenants DokyDoc works fine. At 100 tenants with large repos (500+ files, multi-MB BRDs), the current architecture will hit three walls simultaneously: N+1 query explosion in ontology graph endpoints, Redis cache misses on every BOEContext build, and Celery worker starvation when 5 tenants kick off repo analysis at the same time. This phase instruments, measures, and fixes these before they become customer incidents. The rule: never optimize without measuring first.

### P12.1 — Query Performance Instrumentation
**File:** `backend/app/core/database.py` (SQLAlchemy engine setup)

Add query timing middleware that logs slow queries:

```python
# Add SQLAlchemy event listener
from sqlalchemy import event
import time

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.monotonic())

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.monotonic() - conn.info["query_start_time"].pop(-1)
    if total > 0.200:  # Log queries slower than 200ms
        logger.warning(
            "SLOW QUERY",
            extra={
                "duration_ms": round(total * 1000),
                "statement": statement[:500],  # Truncate for safety
                "tenant_id": getattr(context, "tenant_id", None)
            }
        )
```

Add `SLOW_QUERY_THRESHOLD_MS=200` to `config.py`. Set to 0 in development to log all queries.

**Prometheus metrics:**
```python
# backend/app/core/metrics.py
from prometheus_client import Histogram, Counter, Gauge

db_query_duration = Histogram("dokydoc_db_query_duration_seconds",
                               "Database query duration", ["endpoint", "query_type"])
gemini_call_duration = Histogram("dokydoc_gemini_call_duration_seconds",
                                  "Gemini API call duration", ["prompt_type"])
celery_task_duration = Histogram("dokydoc_celery_task_duration_seconds",
                                  "Celery task duration", ["task_name"])
active_analysis_runs = Gauge("dokydoc_active_analysis_runs", "Active analysis runs")
```

Expose at `GET /metrics` (Prometheus scrape endpoint, IP-whitelisted).

### P12.2 — Critical Missing Indexes
**File:** New migration `backend/alembic/versions/s22a1_performance_indexes.py`

Based on the query patterns from all endpoints, add composite indexes that are currently missing:

```sql
-- Ontology graph queries (most expensive — powers knowledge graph visualization)
CREATE INDEX CONCURRENTLY idx_ontology_concepts_tenant_type
    ON ontology_concepts (tenant_id, concept_type);

CREATE INDEX CONCURRENTLY idx_ontology_relationships_tenant_source
    ON ontology_relationships (tenant_id, source_concept_id);

CREATE INDEX CONCURRENTLY idx_ontology_relationships_tenant_target
    ON ontology_relationships (tenant_id, target_concept_id);

-- Mismatch queries (validation panel — high frequency)
CREATE INDEX CONCURRENTLY idx_mismatches_tenant_doc_status
    ON mismatches (tenant_id, document_id, status);

CREATE INDEX CONCURRENTLY idx_mismatches_tenant_severity
    ON mismatches (tenant_id, severity) WHERE status = 'open';

-- Requirement atoms (9-pass validation)
CREATE INDEX CONCURRENTLY idx_requirement_atoms_document_type
    ON requirement_atoms (document_id, atom_type);

-- Training examples (Phase 1 flywheel — grows fast)
CREATE INDEX CONCURRENTLY idx_training_examples_tenant_type_label
    ON training_examples (tenant_id, example_type, human_label)
    WHERE human_label IS NOT NULL;

-- Coverage snapshots (Phase 9 analytics — time-series queries)
CREATE INDEX CONCURRENTLY idx_coverage_snapshots_tenant_doc_date
    ON coverage_snapshots (tenant_id, document_id, snapshot_date DESC);

-- Code data flow edges (Phase 3)
CREATE INDEX CONCURRENTLY idx_code_data_flow_source
    ON code_data_flow_edges (source_component_id, tenant_id);
CREATE INDEX CONCURRENTLY idx_code_data_flow_target
    ON code_data_flow_edges (target_component_id, tenant_id)
    WHERE target_component_id IS NOT NULL;

-- Search index (Phase 8)
CREATE INDEX CONCURRENTLY idx_search_index_tenant_type
    ON search_index (tenant_id, artifact_type);

-- Audit logs (compliance queries — time range heavy)
CREATE INDEX CONCURRENTLY idx_audit_logs_tenant_created
    ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_audit_logs_tenant_event
    ON audit_logs (tenant_id, event_type, created_at DESC);

-- pgvector HNSW index (cosine similarity — replaces IVFFlat for better recall)
CREATE INDEX CONCURRENTLY idx_ontology_concepts_embedding_hnsw
    ON ontology_concepts
    USING hnsw (embedding_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

Use `CONCURRENTLY` on all indexes — zero downtime, no table lock.

### P12.3 — N+1 Query Elimination
**File:** Multiple CRUD and service files

The most common N+1 patterns to fix:

**Problem 1: Ontology graph endpoint loads each concept's relationships in a loop**
```python
# BEFORE (N+1):
concepts = db.query(OntologyConcept).filter_by(tenant_id=tenant_id).all()
for concept in concepts:
    concept.relationships = db.query(OntologyRelationship)...  # N queries

# AFTER (1 query with joinedload):
concepts = (
    db.query(OntologyConcept)
    .filter_by(tenant_id=tenant_id)
    .options(
        selectinload(OntologyConcept.outgoing_relationships),
        selectinload(OntologyConcept.incoming_relationships)
    )
    .all()
)
```

**Problem 2: Validation panel loads mismatch + document + code_component separately**
```python
# AFTER (single join):
mismatches = (
    db.query(Mismatch)
    .join(Document, Mismatch.document_id == Document.id)
    .join(CodeComponent, Mismatch.component_id == CodeComponent.id)
    .filter(Mismatch.tenant_id == tenant_id)
    .options(
        contains_eager(Mismatch.document),
        contains_eager(Mismatch.component)
    )
    .all()
)
```

**Problem 3: Initiative health score loads all assets then each asset's documents**
```python
# AFTER (batch load):
initiative = (
    db.query(Initiative)
    .filter_by(id=initiative_id)
    .options(
        selectinload(Initiative.assets)
        .selectinload(InitiativeAsset.document)
        .selectinload(Document.mismatches)
    )
    .first()
)
```

**Rule:** All list endpoints that return > 10 items MUST use `selectinload` or `joinedload`. Never `.relationship` access in a loop.

### P12.4 — Redis Caching Strategy
**File:** `backend/app/services/cache_service.py`

Current state: `CacheService` exists. Define a comprehensive caching policy:

```python
CACHE_POLICY = {
    # Key: cache key pattern → TTL (seconds) → invalidation trigger
    "boe_context:{tenant_id}:{doc_id}:{comp_id}":     (3600,  "on_analysis_complete"),
    "prompt_context:{tenant_id}":                      (300,   "on_tenant_settings_update"),
    "tenant_graph:{tenant_id}:{initiative_id}":        (1800,  "on_concept_created_or_deleted"),
    "coverage_summary:{tenant_id}":                    (3600,  "on_snapshot_taken"),
    "user_permissions:{user_id}":                      (600,   "on_role_change"),
    "industry_context:{industry}:{sub_domain}":        (86400, "never — static file"),
    "search_index_warm:{tenant_id}":                   (300,   "on_artifact_indexed"),
    "validation_atoms:{document_id}:{version_hash}":   (None,  "never — permanent until version changes"),
}
```

**Cache invalidation helpers** (called at the right moment):
```python
# backend/app/services/cache_service.py
def invalidate_boe_context(tenant_id, document_id=None, component_id=None):
    pattern = f"boe_context:{tenant_id}:*"
    if document_id:
        pattern = f"boe_context:{tenant_id}:{document_id}:*"
    cache_service.delete_pattern(pattern)

def invalidate_tenant_graph(tenant_id):
    cache_service.delete_pattern(f"tenant_graph:{tenant_id}:*")

def invalidate_user_permissions(user_id):
    cache_service.delete(f"user_permissions:{user_id}")
```

**Redis memory policy:** Set `maxmemory-policy allkeys-lru` in Redis config. DokyDoc cache is LRU-safe — all cached data can be recomputed.

### P12.5 — Celery Worker Specialization
**File:** `backend/app/worker.py`, `docker-compose.yml` / `k8s/` deployment

Current state: Single Celery worker pool handles all task types. Problem: a 30-minute repo analysis blocks 3-minute validation tasks queued behind it.

**Separate task queues:**
```python
# Task → Queue assignment
TASK_QUEUES = {
    # High priority — user is waiting
    "high": [
        "validate_document",
        "atomize_document",
        "run_cross_graph_mapping",
        "index_artifact",          # Phase 8 search indexing
    ],
    # Default — background processing
    "default": [
        "process_document_pipeline",
        "extract_ontology_entities",
        "extract_code_ontology_entities",
        "backfill_data_flow_edges",
        "regen_generated_doc",     # Phase 11
        "take_daily_coverage_snapshots",  # Phase 9
        "detect_tenant_industry",  # Phase 5
    ],
    # Low priority — can wait hours
    "low": [
        "repo_analysis_task",      # Long-running (up to 30min for large repos)
        "backfill_embeddings",
        "run_model_evaluation",    # Phase 10
        "sync_all_jira",          # Phase 7
        "backfill_data_flow_edges",
    ]
}
```

**Worker deployment (docker-compose):**
```yaml
celery-high:
  command: celery -A app.worker worker -Q high --concurrency=8 --prefetch-multiplier=1
  replicas: 2

celery-default:
  command: celery -A app.worker worker -Q default --concurrency=4 --prefetch-multiplier=2
  replicas: 2

celery-low:
  command: celery -A app.worker worker -Q low --concurrency=2 --prefetch-multiplier=1
  replicas: 1  # Long-running tasks — fewer workers is fine
```

**Celery beat** (scheduler) runs as its own container, not mixed with workers.

### P12.6 — Async Database Session Upgrade
**File:** `backend/app/core/database.py`

Current state: Synchronous SQLAlchemy sessions block FastAPI's event loop during I/O.

Migrate to `asyncpg` + `sqlalchemy.ext.asyncio`:

```python
# database.py — async engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,          # Max connections per worker
    max_overflow=10,       # Burst capacity
    pool_timeout=30,
    pool_pre_ping=True,    # Detect stale connections
    echo=settings.DEBUG
)

AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**Migration strategy:** Introduce async sessions incrementally — start with the highest-traffic endpoints (ontology graph, validation panel, search). Don't migrate all at once.

**Priority order for async migration:**
1. `GET /ontology/graph` (most complex query, blocking)
2. `GET /validation/{id}/results`
3. `GET /search`
4. `POST /chat/` (already async for streaming)
5. All other endpoints (gradually)

### P12.7 — Connection Pooling & PgBouncer
**File:** `docker-compose.yml`, `k8s/pgbouncer.yaml`

At scale, each FastAPI worker + each Celery worker opens its own PostgreSQL connections. With 4 API workers × 10 connections each + 5 Celery workers × 4 connections = 60 connections minimum. PostgreSQL default max is 100.

Add PgBouncer in transaction mode between application and PostgreSQL:

```yaml
# docker-compose.yml
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DATABASE_URL: "postgresql://user:pass@postgres:5432/dokydoc"
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000    # App-facing connections
    DEFAULT_POOL_SIZE: 25    # Actual PostgreSQL connections
    MAX_DB_CONNECTIONS: 50
  ports:
    - "5432"
```

FastAPI + Celery connect to PgBouncer, not PostgreSQL directly. Reduces actual DB connections to 25-50 regardless of how many workers scale.

**Important:** With PgBouncer in transaction mode, SQLAlchemy `NullPool` must be used (or `pool_size=1`). No persistent connection per session.

### P12.8 — Background Job Monitoring
**New:** Add Flower (Celery monitoring UI) + custom task health endpoint

```yaml
# docker-compose.yml
flower:
  image: mher/flower:latest
  command: celery --broker=${REDIS_URL} flower --port=5555 --basic_auth=admin:${FLOWER_PASSWORD}
  ports: ["5555:5555"]
```

**Custom health endpoint:**
```
GET /api/v1/health/workers
  Returns: {
    "celery_high": { "online": 2, "active_tasks": 3, "queued": 0 },
    "celery_default": { "online": 2, "active_tasks": 1, "queued": 12 },
    "celery_low": { "online": 1, "active_tasks": 1, "queued": 47 },
    "redis": "connected",
    "postgres": "connected",
    "queue_lag": { "high": "0s", "default": "23s", "low": "4m 12s" }
  }
```

Alert if `queue_lag.high > 30s` — means user-facing tasks are backed up.

### P12.9 — API Response Compression & Caching Headers
**File:** `backend/main.py`

```python
from fastapi.middleware.gzip import GZipMiddleware

# Add GZip for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add ETag-based caching for stable endpoints
@router.get("/ontology/graph")
async def get_graph(..., response: Response):
    graph_data = await build_graph(...)
    content_hash = hashlib.md5(json.dumps(graph_data).encode()).hexdigest()
    response.headers["ETag"] = f'"{content_hash}"'
    response.headers["Cache-Control"] = "private, max-age=60"

    if_none_match = request.headers.get("If-None-Match")
    if if_none_match == f'"{content_hash}"':
        return Response(status_code=304)  # Not Modified

    return graph_data
```

Apply ETag caching to: ontology graph, coverage summary, tenant settings, search results.

### P12.10 — Load Testing & Baseline
**New file:** `backend/tests/load/locustfile.py`

```python
from locust import HttpUser, task, between

class DokyDocUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        # Login and get token
        resp = self.client.post("/api/login", json={...})
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def view_ontology_graph(self):
        self.client.get("/api/v1/ontology/graph", headers=self.headers)

    @task(8)
    def view_validation_results(self):
        self.client.get("/api/v1/validation/1/results", headers=self.headers)

    @task(5)
    def search(self):
        self.client.get("/api/v1/search?q=payment", headers=self.headers)

    @task(3)
    def chat_message(self):
        self.client.post("/api/v1/chat/", headers=self.headers,
                         json={"message": "What is the coverage score?"})

    @task(1)
    def trigger_validation(self):
        self.client.post("/api/v1/validation/run", headers=self.headers,
                         json={"document_id": 1})
```

**Baseline targets:**
| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| GET /ontology/graph | < 200ms | < 500ms | < 1s |
| GET /validation/results | < 150ms | < 400ms | < 800ms |
| GET /search | < 100ms | < 300ms | < 600ms |
| POST /chat/ (streaming) | < 500ms TTFB | < 1s TTFB | < 2s TTFB |
| POST /validation/run (enqueue) | < 50ms | < 100ms | < 200ms |

Run with: `locust -f locustfile.py --headless -u 50 -r 5 --run-time 5m`

Add to CI: fail if P95 > 2× baseline.

### P12.11 — Horizontal Scaling Readiness
**File:** `docker-compose.yml`, `backend/app/core/config.py`

Ensure all state is external (nothing in FastAPI worker memory):

**Checklist:**
- [ ] No in-memory caches in FastAPI workers (all cache in Redis) — industry_context.json is read-only, OK
- [ ] No local file writes (uploads go direct to S3/GCS, not local disk)
- [ ] Celery tasks are idempotent (safe to retry, re-run on different worker)
- [ ] Sessions use Redis backend (not in-memory) — verify `SESSION_BACKEND=redis`
- [ ] WebSocket connections (if any for live notifications) use Redis pub/sub, not in-process
- [ ] `PYTHONDONTWRITEBYTECODE=1` in Docker — no bytecode file conflicts across instances

**S3/GCS upload migration:**
Current state: uploaded files likely stored on local disk (`/tmp` or mounted volume). Migrate to object storage:

```python
# backend/app/services/file_storage_service.py (new)
class FileStorageService:
    """Abstraction over S3/GCS/local — swappable via config."""

    def upload(self, file: bytes, key: str, content_type: str) -> str:
        """Returns public/signed URL."""
        if settings.STORAGE_BACKEND == "s3":
            return self._upload_s3(file, key, content_type)
        elif settings.STORAGE_BACKEND == "gcs":
            return self._upload_gcs(file, key, content_type)
        else:
            return self._upload_local(file, key)  # dev only

    def get_signed_url(self, key: str, expires_in=3600) -> str:
        """Generates time-limited download URL."""
```

Add `STORAGE_BACKEND=s3|gcs|local` to config. Default `local` for development, `s3` for production.

### Verification
1. **Slow query log:** Run `GET /ontology/graph` for a tenant with 500 concepts → verify no slow query logged (< 200ms)
2. **Index usage:** `EXPLAIN ANALYZE SELECT * FROM mismatches WHERE tenant_id=1 AND status='open'` → verify index scan, not seq scan
3. **N+1 fix:** Enable SQLAlchemy echo, call ontology graph endpoint → verify single query with joins, not 50+ individual queries
4. **Cache hit:** Call `GET /ontology/graph` twice → second call returns from Redis cache (verify via `X-Cache: HIT` header or Redis `MONITOR`)
5. **Queue separation:** Submit a repo analysis (low queue) + a validation run (high queue) simultaneously → verify validation completes first
6. **Load test:** Run Locust with 50 users → all P95 targets met → save as baseline artifact
7. **PgBouncer:** Check `SHOW POOLS` in PgBouncer admin → confirms < 30 actual PostgreSQL connections even under 50 concurrent users
8. **No local state:** Kill one API worker mid-request → restart → next request succeeds (session persists in Redis)

---

## PHASE 13 — Developer Experience (SDK, CLI, API Playground, Local Dev)
**Priority: Medium-High — required for self-serve enterprise adoption and partner integrations**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 7 (Public API v2 must exist before SDK is built)**
**Estimated complexity: Medium**

### Context
Enterprise developers will not adopt DokyDoc if integrating it requires reading raw API docs and hand-rolling HTTP clients. A Python SDK, a CLI tool for CI/CD pipelines, an interactive API playground, and a clean local dev setup turn a 3-day integration into a 30-minute one. This phase also fixes the onboarding experience — the current first-run experience shows an empty dashboard with no guidance. First impressions determine trial-to-paid conversion.

### P13.1 — Python SDK
**New repo (or monorepo package):** `packages/dokydoc-sdk/` or separate `dokydoc-python` repo

```
dokydoc-python/
├── dokydoc/
│   ├── __init__.py           # Public API: DokuDoc, Document, Repository, etc.
│   ├── client.py             # DokuDocClient — base HTTP client with auth
│   ├── resources/
│   │   ├── documents.py      # Documents resource
│   │   ├── repositories.py   # Repositories resource
│   │   ├── validation.py     # Validation resource
│   │   ├── ontology.py       # Ontology / concepts resource
│   │   ├── chat.py           # Chat resource (streaming)
│   │   └── auto_docs.py      # Auto-docs resource
│   ├── models/               # Pydantic response models
│   │   ├── document.py
│   │   ├── mismatch.py
│   │   └── ...
│   ├── exceptions.py         # DokuDocError, RateLimitError, BillingLimitError
│   └── webhook.py            # Webhook signature verification helper
├── tests/
├── examples/
│   ├── upload_and_validate.py
│   ├── ci_pipeline.py
│   └── webhook_server.py
├── pyproject.toml
└── README.md
```

**SDK design — clean, chainable interface:**
```python
from dokydoc import DokuDoc

client = DokuDoc(api_key="dk_live_...")

# Upload a document and wait for validation
doc = client.documents.upload(
    file_path="requirements/payment-brd.pdf",
    title="Payment Service BRD v2.1",
    document_type="BRD"
)
doc.wait_for_analysis()  # Polls until analysis_status == "complete"

# Run validation against a repository
result = client.validation.run(
    document_id=doc.id,
    repository_id=42,
    wait=True  # Block until validation complete
)

print(f"Coverage: {result.coverage_score:.0%}")
print(f"Critical mismatches: {result.critical_count}")

for mismatch in result.mismatches:
    print(f"  [{mismatch.severity}] {mismatch.title}")

# Exit with non-zero code if critical mismatches exist (CI gate)
if result.critical_count > 0:
    raise SystemExit(1)
```

**Async variant:**
```python
import asyncio
from dokydoc.aio import AsyncDokuDoc

async def main():
    async with AsyncDokuDoc(api_key="dk_live_...") as client:
        doc = await client.documents.upload("requirements.pdf")
        result = await client.validation.run(document_id=doc.id, repository_id=42)
        print(result.coverage_score)

asyncio.run(main())
```

**Webhook verification helper:**
```python
from dokydoc.webhook import verify_signature

@app.post("/webhook")
def handle_webhook(request: Request):
    payload = request.body()
    signature = request.headers["X-DokuDoc-Signature"]
    secret = "whsec_..."

    if not verify_signature(payload, signature, secret):
        raise HTTPException(401)

    event = json.loads(payload)
    # Handle event...
```

**Publish:** PyPI as `dokydoc`. Install: `pip install dokydoc`.

### P13.2 — JavaScript / TypeScript SDK
**New package:** `packages/dokydoc-js/`

```typescript
import { DokuDoc } from '@dokydoc/sdk'

const client = new DokuDoc({ apiKey: 'dk_live_...' })

// Upload document
const doc = await client.documents.upload({
  file: fs.createReadStream('requirements.pdf'),
  title: 'Payment BRD',
  documentType: 'BRD'
})

// Stream chat response
const stream = client.chat.stream({
  message: 'What are the gaps in the payment flow?',
  conversationId: 'conv_123'
})

for await (const chunk of stream) {
  process.stdout.write(chunk.text)
}

// Subscribe to webhook events (local dev helper)
const wh = new DokuDoc.Webhook('whsec_...')
app.post('/webhook', (req, res) => {
  const event = wh.constructEvent(req.rawBody, req.headers['x-dokydoc-signature'])
  console.log(event.type, event.data)
  res.sendStatus(200)
})
```

**Publish:** npm as `@dokydoc/sdk`. Install: `npm install @dokydoc/sdk`.

Generated from OpenAPI spec using `openapi-typescript-codegen` as a base, with hand-written convenience layer on top.

### P13.3 — CLI Tool
**New package:** `packages/dokydoc-cli/` (Python, distributed as `dokydoc-cli` on PyPI)

```bash
# Install
pip install dokydoc-cli

# Authenticate
dokydoc login                          # Opens browser for OAuth or prompts for API key
dokydoc config set api-key dk_live_...

# Document operations
dokydoc docs upload ./requirements.pdf --title "Payment BRD" --type BRD
dokydoc docs list --status pending
dokydoc docs validate 42 --repo 7      # document_id + repo_id

# Validation — designed for CI/CD
dokydoc validate \
  --document "Payment BRD v2.1" \      # Fuzzy name match
  --repo "payment-service" \           # Repo name match
  --fail-on critical \                 # Exit 1 if critical mismatches
  --output json > results.json

# Output for CI:
# {
#   "coverage": 0.84,
#   "critical": 0,
#   "warnings": 3,
#   "passed": true
# }

# Repository operations
dokydoc repos connect https://github.com/org/repo --branch main
dokydoc repos analyze 7                # Trigger analysis
dokydoc repos status 7                 # Check analysis status

# Knowledge graph
dokydoc ontology list                  # List concepts
dokydoc ontology gaps --document 42    # Show BOE gaps

# Auto-docs
dokydoc docs generate \
  --source document:42 \
  --source repo:7 \
  --template technical_spec \
  --output ./docs/payment-spec.md

# Interactive mode
dokydoc shell                          # Opens interactive REPL
```

**CI/CD integration examples (bundled in `examples/`):**

**GitHub Actions:**
```yaml
# .github/workflows/dokydoc.yml
- name: DokyDoc Validation Gate
  uses: dokydoc/action@v1           # GitHub Action wrapper around CLI
  with:
    api-key: ${{ secrets.DOKYDOC_API_KEY }}
    document: "Payment BRD"
    repository: ${{ github.repository }}
    fail-on: critical
```

**GitLab CI:**
```yaml
dokydoc:
  image: dokydoc/cli:latest
  script:
    - dokydoc validate --document "Payment BRD" --repo $CI_PROJECT_NAME --fail-on critical
```

### P13.4 — API Playground
**New page:** `frontend/app/dashboard/api-playground/page.tsx`

Interactive API explorer built into the dashboard (authenticated — uses tenant's own API key):

```tsx
<div className="grid grid-cols-3 h-full">
  {/* Left: Endpoint browser */}
  <div className="border-r overflow-y-auto">
    <div className="p-3 border-b">
      <input placeholder="Search endpoints..." className="w-full text-sm border rounded px-2 py-1" />
    </div>
    {ENDPOINT_GROUPS.map(group => (
      <div key={group.name}>
        <div className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase">
          {group.name}
        </div>
        {group.endpoints.map(ep => (
          <button
            key={ep.path}
            onClick={() => selectEndpoint(ep)}
            className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50
                        flex items-center gap-2
                        ${selected?.path === ep.path ? 'bg-blue-50 text-blue-700' : ''}`}
          >
            <MethodBadge method={ep.method} />
            <span className="font-mono text-xs">{ep.path}</span>
          </button>
        ))}
      </div>
    ))}
  </div>

  {/* Center: Request builder */}
  <div className="border-r flex flex-col">
    <div className="p-4 border-b">
      <div className="flex items-center gap-2 mb-3">
        <MethodBadge method={selected?.method} large />
        <code className="text-sm">{selected?.path}</code>
      </div>
      <p className="text-sm text-gray-500">{selected?.description}</p>
    </div>

    {/* Path params */}
    {selected?.pathParams.map(param => (
      <div key={param.name} className="px-4 py-2 border-b">
        <label className="text-xs font-medium text-gray-500">{param.name}</label>
        <input className="w-full text-sm border rounded px-2 py-1 mt-1 font-mono"
               placeholder={param.example} onChange={e => setParam(param.name, e.target.value)} />
      </div>
    ))}

    {/* Request body */}
    {selected?.hasBody && (
      <div className="flex-1 p-4">
        <label className="text-xs font-medium text-gray-500 mb-1 block">Request Body</label>
        <CodeEditor
          value={requestBody}
          onChange={setRequestBody}
          language="json"
          className="h-48"
        />
      </div>
    )}

    <div className="p-4">
      <button onClick={sendRequest}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium">
        {loading ? 'Sending...' : 'Send Request'}
      </button>
    </div>
  </div>

  {/* Right: Response viewer */}
  <div className="flex flex-col">
    {response && (
      <>
        <div className="p-3 border-b flex items-center gap-3">
          <StatusBadge code={response.status} />
          <span className="text-xs text-gray-400">{response.duration}ms</span>
          <button onClick={() => copyToClipboard(response.body)}
                  className="text-xs text-gray-400 hover:text-gray-600 ml-auto">
            Copy
          </button>
        </div>
        <div className="flex-1 overflow-auto p-3">
          <CodeViewer value={JSON.stringify(response.body, null, 2)} language="json" />
        </div>
        {/* Code snippet generator */}
        <div className="border-t p-3">
          <SnippetGenerator
            request={currentRequest}
            languages={['python', 'javascript', 'curl', 'go']}
          />
        </div>
      </>
    )}
  </div>
</div>
```

**Code snippet generation:** For every API call made in the playground, auto-generate SDK code:
```python
# Python SDK equivalent:
client.documents.upload(file_path="...", title="Payment BRD")

# JavaScript SDK:
await client.documents.upload({ file: ..., title: 'Payment BRD' })

# cURL:
curl -X POST https://api.dokydoc.com/api/v2/documents \
  -H "Authorization: Bearer dk_live_..." \
  -F "file=@requirements.pdf"
```

### P13.5 — Local Development Improvements
**New file:** `docker-compose.dev.yml`

One-command local setup for new developers:

```yaml
# docker-compose.dev.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_DB: dokydoc, POSTGRES_PASSWORD: dev }
    ports: ["5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build: { context: ./backend, target: development }
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql://postgres:dev@postgres:5432/dokydoc
      REDIS_URL: redis://redis:6379
      GEMINI_API_KEY: ${GEMINI_API_KEY}  # Only external dependency
      ENVIRONMENT: development
    volumes: ["./backend:/app"]  # Live reload
    ports: ["8000:8000"]
    depends_on: [postgres, redis]

  celery:
    build: { context: ./backend, target: development }
    command: celery -A app.worker worker -Q high,default,low --concurrency=2 --loglevel=info
    environment: *backend_env
    volumes: ["./backend:/app"]
    depends_on: [postgres, redis]

  frontend:
    build: { context: ./frontend, target: development }
    command: npm run dev
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    volumes: ["./frontend:/app", "/app/node_modules"]
    ports: ["3000:3000"]
```

**Setup script:** `scripts/dev-setup.sh`
```bash
#!/bin/bash
set -e
echo "🚀 Setting up DokyDoc development environment..."

# Check dependencies
command -v docker >/dev/null || { echo "Docker required"; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.11+ required"; exit 1; }

# Copy env file
cp .env.example .env
echo "⚙️  Edit .env and add your GEMINI_API_KEY"

# Start services
docker-compose -f docker-compose.dev.yml up -d postgres redis

# Run migrations
cd backend
pip install -e ".[dev]"
alembic upgrade head

# Seed development data
python scripts/seed_dev_data.py

echo "✅ Ready! Run: docker-compose -f docker-compose.dev.yml up"
echo "   Frontend: http://localhost:3000"
echo "   API:      http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
```

**Seed data script:** `backend/scripts/seed_dev_data.py`
```python
"""
Creates a realistic dev environment:
- 1 tenant (Acme Corp, fintech/payments industry)
- 3 users (admin, developer, BA roles)
- 2 documents (a BRD + an SRS)
- 1 repository (mock Python microservice)
- Pre-run analysis so the UI isn't empty on first load
"""
```

### P13.6 — OpenAPI Spec Export & Documentation Site
**File:** `backend/main.py`

Enhance the auto-generated OpenAPI spec:

```python
app = FastAPI(
    title="DokyDoc API",
    version="2.0.0",
    description="""
    ## DokyDoc API — Documentation Intelligence Platform

    Connect your BRDs, code repositories, and business ontology.
    Validate documentation automatically. Generate living documentation.

    ### Authentication
    Use API keys from your dashboard: `Authorization: Bearer dk_live_...`

    ### Rate Limits
    - Free: 100 requests/day
    - Pro: 5,000 requests/day
    - Enterprise: Unlimited

    ### Webhooks
    Subscribe to events at `/api/v2/webhook-subscriptions`.
    All payloads are signed with HMAC-SHA256.
    """,
    openapi_tags=[
        {"name": "Documents", "description": "Upload and manage BRDs, SRS, and other documents"},
        {"name": "Validation", "description": "Run the 9-pass atomic validation engine"},
        {"name": "Repositories", "description": "Connect and analyze code repositories"},
        {"name": "Ontology", "description": "Business knowledge graph — concepts and relationships"},
        {"name": "Auto-Docs", "description": "Generate and publish living documentation"},
        {"name": "Chat", "description": "RAG-powered AI assistant"},
        {"name": "Analytics", "description": "Coverage trends, usage metrics, cost intelligence"},
        {"name": "Webhooks", "description": "Subscribe to DokyDoc events"},
    ]
)
```

Add response examples to every endpoint using `openapi_extra`:
```python
@router.post("/documents/", openapi_extra={
    "requestBody": {"content": {"multipart/form-data": {"example": {...}}}},
    "responses": {"200": {"content": {"application/json": {"example": {...}}}}}
})
```

**Static docs site:** Export `GET /openapi.json` → run `redoc-cli` to generate static HTML docs. Host at `docs.dokydoc.com`. Auto-rebuild on API change via CI.

### P13.7 — Onboarding Flow (First-Run Experience)
**New pages:** `frontend/app/dashboard/welcome/page.tsx`

Redirect new tenants to onboarding wizard on first login (when `tenant.settings.onboarding_complete == false`):

**Step 1 — Welcome & Company Profile (P5.6 from Phase 5)**
Already planned. Industry detection from website URL.

**Step 2 — Connect Your First Repository**
```tsx
<div className="text-center mb-6">
  <Code2 className="h-12 w-12 text-blue-600 mx-auto mb-3" />
  <h2 className="text-xl font-semibold">Connect your codebase</h2>
  <p className="text-gray-500 mt-1">
    DokyDoc analyzes your code to understand what's actually built.
  </p>
</div>
<div className="grid grid-cols-3 gap-3">
  <RepoProviderCard provider="github" onClick={() => connectGitHub()} />
  <RepoProviderCard provider="gitlab" onClick={() => connectGitLab()} />
  <RepoProviderCard provider="bitbucket" onClick={() => connectBitbucket()} />
</div>
<button className="text-sm text-gray-400 mt-4" onClick={skipStep}>
  Skip for now — I'll do this later
</button>
```

**Step 3 — Upload Your First Document**
```tsx
<DocumentUploadDropzone
  onUpload={handleUpload}
  acceptedTypes={["pdf", "docx", "md"]}
  hint="Try uploading a BRD, SRS, or any requirements document"
/>
<div className="mt-4 text-sm text-gray-400 text-center">
  Don't have one? <button className="text-blue-600">Use our sample BRD</button>
</div>
```

**Step 4 — Watch the Magic (Progress)**
```tsx
<div className="space-y-3">
  <ProgressStep label="Parsing document" status={steps.parse} />
  <ProgressStep label="Extracting requirements" status={steps.extract} />
  <ProgressStep label="Analyzing code structure" status={steps.code} />
  <ProgressStep label="Building knowledge graph" status={steps.graph} />
  <ProgressStep label="Running validation" status={steps.validation} />
</div>
```

Uses WebSocket or polling to show real-time progress.

**Step 5 — Your First Results**
```tsx
<div className="text-center">
  <div className="text-5xl font-bold text-blue-600 mb-2">
    {(coverage * 100).toFixed(0)}%
  </div>
  <p className="text-gray-500">Documentation Coverage</p>
  <div className="grid grid-cols-3 gap-4 mt-6">
    <StatBox label="Requirements Found" value={atomCount} />
    <StatBox label="Issues Detected" value={mismatchCount} />
    <StatBox label="Concepts Mapped" value={conceptCount} />
  </div>
  <button onClick={goToDashboard}
          className="mt-6 bg-blue-600 text-white px-6 py-2 rounded-lg">
    Explore Your Results →
  </button>
</div>
```

### P13.8 — Developer Documentation Site
**New:** `docs/` directory (or separate `dokydoc-docs` repo)

Built with Docusaurus or Mintlify. Sections:

```
Getting Started
  ├── Quickstart (5 minutes)
  ├── Core Concepts (BRD, validation, ontology)
  └── Authentication

Guides
  ├── Uploading Documents
  ├── Connecting a Repository
  ├── Running Validation
  ├── Setting Up CI/CD Integration
  ├── Using the Knowledge Graph
  ├── Generating Auto-Documentation
  └── Configuring Webhooks

SDK Reference
  ├── Python SDK
  ├── JavaScript SDK
  └── CLI Reference

API Reference
  └── (Embedded Redoc from OpenAPI spec)

Self-Hosting
  ├── Docker Compose Setup
  ├── Kubernetes Deployment
  ├── Environment Variables
  └── Upgrading
```

### Verification
1. **Python SDK:** `pip install dokydoc && python examples/upload_and_validate.py` → completes without error, prints coverage score
2. **CLI CI gate:** `dokydoc validate --document "Payment BRD" --fail-on critical` → exits 0 when no criticals, exits 1 when criticals exist
3. **API playground:** Open `/api-playground`, select `POST /documents/`, fill form, click Send → real document created, response shown with status 200
4. **Code snippets:** API playground shows correct Python/JS/cURL snippets matching the request made
5. **Local setup:** Fresh machine, run `./scripts/dev-setup.sh` + `docker-compose -f docker-compose.dev.yml up` → frontend loads at :3000 with seed data visible
6. **Onboarding:** Register new tenant → redirected to onboarding wizard → complete all steps → arrives at dashboard with real coverage score shown
7. **OpenAPI spec:** `GET /openapi.json` returns spec with descriptions, examples, and tags for all endpoints
8. **SDK webhook verification:** Call `verify_signature(payload, sig, secret)` with valid and invalid signatures → correct True/False

---

## PHASE 14 — Security Hardening (SOC 2, Secrets, Encryption, Zero-Trust)
**Priority: Non-negotiable for enterprise sales. Banks and hospitals will not sign without it.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline), Phase 6 (RBAC + audit trail)**
**Estimated complexity: Very High**

### Context
Enterprise customers in fintech, healthcare, and government require evidence of security controls before signing. SOC 2 Type II is the baseline expectation. HIPAA and PCI-DSS customers need additional controls. The existing codebase has `encryption_service.py` and `field_encryption.py` — but coverage is incomplete, secrets may be in environment variables instead of a secrets manager, and there is no formal evidence of security controls for auditors. This phase systematically closes every gap.

The principle: **defense in depth** — assume any single layer can be breached, build so the next layer contains the damage.

### P14.1 — Secrets Management Migration
**File:** `backend/app/core/config.py`, new `backend/app/core/secrets.py`

Current state: Secrets (API keys, DB passwords, Gemini API key) are plain environment variables. This works locally but fails SOC 2 because secrets are often visible in CI logs, `.env` files get committed, and rotation requires redeployment.

**Migrate to AWS Secrets Manager / HashiCorp Vault / GCP Secret Manager:**

```python
# backend/app/core/secrets.py
from functools import lru_cache
from typing import Any

class SecretsManager:
    """
    Abstraction over secrets backends.
    In development: reads from environment variables (unchanged behavior).
    In production: reads from AWS Secrets Manager / Vault with caching.
    """

    def __init__(self, backend: str):
        self.backend = backend  # "env" | "aws_secrets_manager" | "vault" | "gcp_secret_manager"
        self._cache: dict[str, tuple[str, datetime]] = {}

    def get(self, key: str, ttl_seconds: int = 300) -> str:
        """
        Fetches secret with local TTL cache.
        Rotation: old secret continues working until TTL expires.
        """
        cached_value, cached_at = self._cache.get(key, (None, None))
        if cached_value and (datetime.utcnow() - cached_at).seconds < ttl_seconds:
            return cached_value

        value = self._fetch(key)
        self._cache[key] = (value, datetime.utcnow())
        return value

    def _fetch(self, key: str) -> str:
        if self.backend == "env":
            return os.environ[key]
        elif self.backend == "aws_secrets_manager":
            import boto3
            client = boto3.client("secretsmanager")
            return client.get_secret_value(SecretId=key)["SecretString"]
        elif self.backend == "vault":
            import hvac
            client = hvac.Client(url=settings.VAULT_ADDR, token=settings.VAULT_TOKEN)
            return client.secrets.kv.read_secret_version(path=key)["data"]["data"]["value"]

secrets = SecretsManager(backend=os.getenv("SECRETS_BACKEND", "env"))
```

**All secret accesses go through `secrets.get()`:**
```python
# In config.py — replace direct os.environ with secrets.get()
GEMINI_API_KEY: str = secrets.get("GEMINI_API_KEY")
DATABASE_URL: str = secrets.get("DATABASE_URL")
JWT_SECRET_KEY: str = secrets.get("JWT_SECRET_KEY")
ENCRYPTION_KEY: str = secrets.get("ENCRYPTION_KEY")
```

**Secret rotation procedure (zero-downtime):**
1. Create new secret version in Secrets Manager
2. Both old and new values active for 24h (dual-active window)
3. After TTL expires in all running instances, deactivate old version
4. No redeployment required

### P14.2 — Field-Level Encryption Audit & Coverage
**File:** `backend/app/services/field_encryption.py`, `backend/app/services/encryption_service.py`

Current state: Field encryption exists but coverage is incomplete. Audit all models and ensure every sensitive field is encrypted at rest.

**Fields that MUST be encrypted (PII + credentials):**
```python
ENCRYPTED_FIELDS = {
    # User data
    "users.email": EncryptionLevel.PII,
    "users.full_name": EncryptionLevel.PII,
    "users.phone_number": EncryptionLevel.PII,

    # Integration credentials (currently using field_encryption — verify coverage)
    "integration_configs.credentials": EncryptionLevel.SECRET,  # Jira/Confluence tokens
    "api_keys.key_hash": EncryptionLevel.SECRET,                # Already hashed — verify
    "webhook_subscriptions.target_url": EncryptionLevel.SECRET,  # Phase 7
    "webhook_subscriptions.secret": EncryptionLevel.SECRET,

    # Tenant data
    "tenants.settings": EncryptionLevel.SENSITIVE,  # Contains glossary, API keys
    "tenant_billing.stripe_customer_id": EncryptionLevel.PII,
    "tenant_billing.stripe_subscription_id": EncryptionLevel.PII,

    # Training data (may contain customer document content)
    "training_examples.input_context": EncryptionLevel.SENSITIVE,
    "training_examples.ai_output": EncryptionLevel.SENSITIVE,
    "training_examples.human_correction": EncryptionLevel.SENSITIVE,

    # Chat history (may contain sensitive business info)
    "chat_messages.content": EncryptionLevel.SENSITIVE,
    "conversations.title": EncryptionLevel.SENSITIVE,

    # Document content
    "documents.content": EncryptionLevel.SENSITIVE,  # If stored in DB (not S3)
    "document_segments.content": EncryptionLevel.SENSITIVE,
}
```

**Envelope encryption:** Use a two-key system:
- **DEK (Data Encryption Key):** AES-256-GCM, unique per tenant, stored encrypted in DB
- **KEK (Key Encryption Key):** RSA-4096 or AES-256, stored in Secrets Manager
- Rotating the KEK rotates all tenant DEKs without re-encrypting every row

```python
class EnvelopeEncryptionService:
    def encrypt_for_tenant(self, tenant_id: int, plaintext: str) -> str:
        dek = self._get_or_create_dek(tenant_id)  # Cached per tenant
        return aes_gcm_encrypt(plaintext, dek)

    def decrypt_for_tenant(self, tenant_id: int, ciphertext: str) -> str:
        dek = self._get_or_create_dek(tenant_id)
        return aes_gcm_decrypt(ciphertext, dek)

    def _get_or_create_dek(self, tenant_id: int) -> bytes:
        tenant = crud.tenant.get(db, tenant_id)
        if tenant.encrypted_dek:
            # Decrypt DEK using KEK from Secrets Manager
            kek = secrets.get("MASTER_KEK")
            return rsa_decrypt(tenant.encrypted_dek, kek)
        else:
            # First time: generate + store DEK
            dek = os.urandom(32)
            kek = secrets.get("MASTER_KEK")
            tenant.encrypted_dek = rsa_encrypt(dek, kek)
            db.commit()
            return dek
```

**New `tenants` field:** `encrypted_dek: str | None` — Migration: `s24a1_tenant_dek.py`

### P14.3 — JWT Hardening
**File:** `backend/app/core/security.py`, `backend/app/api/deps.py`

Current gaps:
- JWT secret may be short or predictable
- No token rotation / refresh token implementation
- No JTI (JWT ID) tracking — stolen tokens can't be revoked
- `exp` claim may be too long (common: 24h or 7d — too long)

**Fixes:**

```python
# JWT configuration
JWT_ALGORITHM = "RS256"           # Asymmetric — private key signs, public key verifies
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15    # Short-lived access tokens
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7       # Long-lived refresh tokens (stored in DB)

# JTI tracking for revocation
class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"
    jti: str (PK)               # JWT ID — UUID
    tenant_id: int
    user_id: int
    token_type: str             # "access" | "refresh"
    expires_at: datetime
    revoked_at: datetime
    revocation_reason: str      # "logout", "password_change", "admin_revoke", "suspicious"
```

**Refresh token flow:**
```
POST /api/auth/refresh
  Body: { refresh_token: str }
  Validation:
    1. Verify JWT signature
    2. Check JTI not in token_blocklist
    3. Check refresh token not expired
    4. Rotate: revoke old refresh token, issue new access + refresh token pair
  Response: { access_token, refresh_token, expires_in }

POST /api/auth/logout
  Action: Add current token's JTI to token_blocklist
  Response: 200 OK
```

**Migration:** `backend/alembic/versions/s24b1_token_blocklist.py`

Cron job: `DELETE FROM token_blocklist WHERE expires_at < NOW()` — daily cleanup.

### P14.4 — Input Validation & Injection Prevention
**File:** All API endpoint files

Systematic audit and fix of injection vectors:

**SQL Injection:** All queries use SQLAlchemy ORM or parameterized queries. Grep for raw SQL:
```bash
grep -rn "text(" backend/app/ | grep -v "alembic"
# Every hit must use bindparams() not string formatting
```

**NoSQL/JSON Injection in `tenant.settings`:** Validate all JSON inputs with Pydantic before storage. Never use `json.loads(user_input)` without schema validation.

**SSRF (Server-Side Request Forgery):** The website URL auto-detection (Phase 5) and Jira/Confluence integrations make outbound HTTP requests. Prevent SSRF:
```python
# backend/app/core/ssrf_protection.py
BLOCKED_PREFIXES = ["169.254.", "10.", "172.16.", "192.168.", "127.", "::1", "fc00:"]
ALLOWED_SCHEMES = ["https"]  # Never http in production

def validate_outbound_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Only HTTPS URLs allowed")

    # Resolve hostname and check for private IP
    ip = socket.gethostbyname(parsed.hostname)
    if any(ip.startswith(prefix) for prefix in BLOCKED_PREFIXES):
        raise ValueError(f"Outbound requests to private IPs not allowed")

    return url
```

Apply `validate_outbound_url()` to: `detect_tenant_industry`, `jira_sync_service`, `confluence_service`, `webhook_delivery_service`.

**Path Traversal:** Any file path from user input must be sanitized:
```python
def safe_path(user_input: str, base_dir: str) -> str:
    resolved = os.path.realpath(os.path.join(base_dir, user_input))
    if not resolved.startswith(os.path.realpath(base_dir)):
        raise ValueError("Path traversal attempt detected")
    return resolved
```

**XSS in Mermaid diagrams:** `MermaidDiagram.tsx` already uses `securityLevel: "loose"` for click handlers. Sanitize concept names and file names before injecting into Mermaid syntax:
```typescript
function sanitizeMermaidLabel(label: string): string {
    // Remove characters that could break Mermaid syntax or inject JS
    return label.replace(/["\[\](){}|<>]/g, ' ').slice(0, 100)
}
```

### P14.5 — Data Isolation Verification
**File:** `backend/tests/security/test_tenant_isolation.py` (new)

Automated test suite that verifies cross-tenant data leakage is impossible:

```python
class TestTenantIsolation:
    """
    Creates two tenants, populates both with data,
    verifies tenant A's token cannot access tenant B's data.
    Runs against every resource type.
    """

    @pytest.fixture(autouse=True)
    def setup_tenants(self, db):
        self.tenant_a = create_test_tenant(db, name="Tenant A")
        self.tenant_b = create_test_tenant(db, name="Tenant B")
        self.token_a = create_test_token(self.tenant_a)
        self.token_b = create_test_token(self.tenant_b)

        # Create resources for tenant B
        self.doc_b = create_test_document(db, tenant_id=self.tenant_b.id)
        self.repo_b = create_test_repository(db, tenant_id=self.tenant_b.id)
        self.concept_b = create_test_concept(db, tenant_id=self.tenant_b.id)

    @pytest.mark.parametrize("endpoint", [
        "/api/v1/documents/{doc_b_id}",
        "/api/v1/repositories/{repo_b_id}",
        "/api/v1/ontology/concepts/{concept_b_id}",
        "/api/v1/validation/{doc_b_id}/results",
        "/api/v1/auto-docs/?document_id={doc_b_id}",
    ])
    def test_cross_tenant_returns_404(self, client, endpoint):
        url = endpoint.format(
            doc_b_id=self.doc_b.id,
            repo_b_id=self.repo_b.id,
            concept_b_id=self.concept_b.id
        )
        response = client.get(url, headers={"Authorization": f"Bearer {self.token_a}"})
        assert response.status_code == 404, f"Cross-tenant leak on {url}"

    def test_list_endpoints_dont_leak(self, client):
        """List endpoints must only return current tenant's data."""
        for endpoint in ["/api/v1/documents/", "/api/v1/repositories/",
                         "/api/v1/ontology/concepts"]:
            response = client.get(endpoint,
                                  headers={"Authorization": f"Bearer {self.token_a}"})
            ids = [item["id"] for item in response.json()["items"]]
            assert self.doc_b.id not in ids
            assert self.repo_b.id not in ids
```

Run this test suite in CI on every PR. Zero tolerance: any test failure blocks merge.

### P14.6 — Security Headers Middleware
**File:** `backend/main.py`

Add security headers to all responses:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # unsafe-inline needed for Mermaid
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' https://generativelanguage.googleapis.com; "
            "frame-ancestors 'none'"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

**Frontend security headers** (Next.js `next.config.js`):
```javascript
const securityHeaders = [
  { key: 'X-DNS-Prefetch-Control', value: 'on' },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
]
module.exports = {
  async headers() {
    return [{ source: '/(.*)', headers: securityHeaders }]
  }
}
```

### P14.7 — Audit Log Completeness for SOC 2
**File:** `backend/app/services/audit_service.py`

SOC 2 requires evidence that every sensitive action is logged. Complete the audit coverage:

**Events that MUST generate audit logs (SOC 2 CC6 — Logical Access):**
```python
# Every one of these must call audit_service.log() — verify with grep
SOC2_REQUIRED_EVENTS = [
    "user.login_success",
    "user.login_failure",           # Track failed logins (brute force detection)
    "user.logout",
    "user.password_changed",
    "user.mfa_enabled",
    "user.mfa_disabled",
    "user.role_changed",
    "user.invited",
    "user.removed",
    "apikey.created",
    "apikey.used",                  # Log every API key usage (sampling OK)
    "apikey.revoked",
    "tenant.settings_changed",      # Track config changes
    "data.exported",                # Any data export
    "data.bulk_deleted",
    "billing.plan_changed",
    "integration.credentials_updated",
]
```

**Failed login tracking + brute force lockout:**
```python
# backend/app/api/endpoints/login.py
def login(email, password, db, request):
    user = crud.user.get_by_email(db, email)

    # Check if account is locked
    if user and user.failed_login_count >= 10:
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(423, "Account temporarily locked. Try again in 30 minutes.")

    if not user or not verify_password(password, user.hashed_password):
        # Increment failure counter
        if user:
            crud.user.increment_failed_logins(db, user.id)
            if user.failed_login_count >= 10:
                crud.user.set_lockout(db, user.id, minutes=30)

        audit_service.log(db, event="user.login_failure",
                          metadata={"email": email, "ip": request.client.host})
        raise HTTPException(401, "Invalid credentials")

    # Success: reset counter
    crud.user.reset_failed_logins(db, user.id)
    audit_service.log(db, event="user.login_success", user_id=user.id)
```

**New `users` fields:** `failed_login_count`, `locked_until` — Migration: `s24c1_user_lockout.py`

### P14.8 — MFA (Multi-Factor Authentication)
**File:** `backend/app/api/endpoints/users.py`, new `backend/app/services/mfa_service.py`

TOTP-based MFA (Google Authenticator compatible):

```python
# backend/app/services/mfa_service.py
import pyotp

class MFAService:
    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def get_provisioning_uri(self, secret: str, user_email: str) -> str:
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(user_email, issuer_name="DokyDoc")

    def verify_code(self, secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)  # ±30 seconds tolerance
```

**New `users` fields:** `mfa_secret` (encrypted), `mfa_enabled`, `mfa_backup_codes` (JSON, hashed)
**Migration:** `s24d1_user_mfa.py`

**MFA enforcement per tenant:** `tenant.settings.require_mfa: bool` — if True, users without MFA enabled are redirected to MFA setup on every login.

**Enterprise requirement:** SOC 2 auditors expect MFA to be available. PCI-DSS requires it for admin accounts.

### P14.9 — Dependency Vulnerability Scanning
**File:** `.github/workflows/security.yml`

```yaml
name: Security Scan
on: [push, pull_request, schedule: [{cron: "0 6 * * 1"}]]  # Also weekly

jobs:
  python-deps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan Python dependencies
        run: |
          pip install safety pip-audit
          safety check -r backend/requirements.txt --json > safety-report.json
          pip-audit -r backend/requirements.txt

  js-deps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan JS dependencies
        run: |
          cd frontend
          npm audit --audit-level=high

  container-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Scan Docker images
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: dokydoc/backend:latest
          severity: HIGH,CRITICAL
          exit-code: 1  # Fail CI on HIGH/CRITICAL CVEs

  secret-scan:
    steps:
      - name: Scan for committed secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
```

Add `pyproject.toml` security constraints:
```toml
[tool.safety]
ignore = []  # Document any ignored CVEs with justification
```

### P14.10 — SOC 2 Evidence Package
**New directory:** `docs/security/soc2/`

Documentation artifacts required by SOC 2 auditors:

```
docs/security/soc2/
├── CC1_Control_Environment/
│   ├── security_policy.md
│   └── code_of_conduct.md
├── CC6_Logical_Access/
│   ├── access_control_policy.md    # RBAC roles + permissions matrix (Phase 6)
│   ├── mfa_policy.md               # MFA enforcement rules
│   └── audit_log_evidence.md       # Links to audit_logs table schema + retention
├── CC7_System_Operations/
│   ├── incident_response_plan.md
│   ├── vulnerability_management.md # Points to automated scanning (P14.9)
│   └── monitoring_setup.md         # Prometheus + alerting
├── CC8_Change_Management/
│   ├── deployment_process.md       # CI/CD pipeline, PR reviews required
│   └── database_migration_policy.md # Alembic migrations, rollback procedures
├── CC9_Risk_Mitigation/
│   ├── vendor_assessment.md        # Gemini/Google, AWS, Stripe vendor risk
│   └── data_classification.md      # PII, SENSITIVE, PUBLIC classification
├── A1_Availability/
│   ├── sla_commitments.md          # Uptime targets, maintenance windows
│   └── backup_restore_policy.md    # DB backup schedule, RTO/RPO
└── C1_Confidentiality/
    ├── encryption_at_rest.md       # Field encryption (P14.2) evidence
    ├── encryption_in_transit.md    # TLS 1.3 only
    └── data_retention_policy.md    # How long data is kept, deletion process
```

**Automated evidence collection script:** `scripts/collect_soc2_evidence.py`
Queries the audit_logs table and generates a CSV report of all SOC 2 relevant events for a given time period. Used by auditors to sample-check controls are operating.

### Verification
1. **Secrets manager:** Set `SECRETS_BACKEND=aws_secrets_manager`, rotate `GEMINI_API_KEY` in Secrets Manager → verify API still works after TTL without restart
2. **Field encryption:** Insert a user row, query PostgreSQL directly → verify `email` column is ciphertext, not plaintext
3. **JWT rotation:** Login → get access token → wait 15 min → verify expired → use refresh token → get new access token without re-login
4. **Token revocation:** Logout → attempt to use old access token → verify 401 (JTI in blocklist)
5. **SSRF:** Call `detect_tenant_industry` with URL `http://169.254.169.254/` (AWS metadata) → verify rejected with validation error
6. **Tenant isolation:** Run `pytest backend/tests/security/test_tenant_isolation.py` → all tests pass (zero cross-tenant leaks)
7. **Brute force:** POST `/api/login` with wrong password 11 times → verify 423 "Account locked" on 11th attempt
8. **MFA:** Enable MFA, generate TOTP code, login → verify second factor required; use backup code → verify works once
9. **Security headers:** `curl -I https://app.dokydoc.com` → verify all 7 security headers present
10. **Dependency scan:** `safety check -r requirements.txt` → zero HIGH or CRITICAL CVEs

---

## PHASE 15 — Observability & SRE (Tracing, SLOs, Alerting, Incident Management)
**Priority: Required for enterprise SLAs. Enables data-driven performance improvements.**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 0 (stability baseline), Phase 12 (Prometheus metrics already set up)**
**Estimated complexity: Medium-High**

### Context
When an enterprise customer files a support ticket saying "DokyDoc was slow for 20 minutes this morning," the current answer is "let me check the logs." That is not acceptable. Observability means: within 30 seconds of any degradation, the on-call engineer knows exactly which service, which tenant, which query, and which Gemini call caused the problem. This phase implements the three pillars of observability (metrics, logs, traces) plus formal SLOs, alerting, and incident response runbooks.

### P15.1 — Distributed Tracing with OpenTelemetry
**New dependency:** `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-exporter-otlp`

**File:** `backend/app/core/telemetry.py` (new)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_telemetry(app):
    if not settings.OTEL_ENDPOINT:
        return  # No-op in development if not configured

    provider = TracerProvider(
        resource=Resource.create({
            "service.name": "dokydoc-api",
            "service.version": settings.APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        })
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT))
    )
    trace.set_tracer_provider(provider)

    # Auto-instrument all HTTP, DB, Redis, outbound HTTP calls
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()  # Catches Gemini API calls
```

**Add tenant_id to every span** (critical for multi-tenant debugging):
```python
# backend/app/api/deps.py — after get_current_tenant()
from opentelemetry import trace
span = trace.get_current_span()
if span.is_recording():
    span.set_attribute("tenant.id", str(tenant_id))
    span.set_attribute("user.id", str(current_user.id))
    span.set_attribute("user.role", current_user.role)
```

**Manual spans for critical operations:**
```python
# In validation_service.py
tracer = trace.get_tracer("dokydoc.validation")

async def validate_single_link(self, ...):
    with tracer.start_as_current_span("validation.single_link") as span:
        span.set_attribute("document.id", document_id)
        span.set_attribute("component.id", component_id)
        span.set_attribute("boe.coverage_pct", boe_context.coverage_pct)

        with tracer.start_as_current_span("validation.gemini_calls"):
            span.set_attribute("gemini.call_count", len(passes_to_run))
            results = await asyncio.gather(*passes)
```

**Trace backend options:** Jaeger (self-hosted, free), Grafana Tempo (free), Honeycomb (managed). Config via `OTEL_ENDPOINT` environment variable. `None` = tracing disabled (default for dev).

### P15.2 — Structured Logging
**File:** `backend/app/core/logging.py` (new or extend existing)

Replace plain text logging with structured JSON logs parseable by Datadog/Loki/CloudWatch:

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer()  # JSON output in production
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()
```

**Bind request context to all logs within a request:**
```python
# Middleware: bind tenant_id + request_id to log context for entire request
class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid4())
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response
```

**After authentication, bind tenant:**
```python
structlog.contextvars.bind_contextvars(
    tenant_id=tenant_id,
    user_id=current_user.id,
    user_role=current_user.role
)
```

Every log line now automatically includes `request_id`, `tenant_id`, `user_id`, `path` — making log correlation trivial.

**Log levels policy:**
- `DEBUG`: Query plans, cache hit/miss, prompt token counts (dev only)
- `INFO`: Request start/end, task enqueue/complete, analysis milestones
- `WARNING`: Slow queries (>200ms), Gemini retries, cache misses on hot paths
- `ERROR`: Unhandled exceptions, DB connection failures, Gemini 5xx errors
- `CRITICAL`: Data corruption suspected, cross-tenant leak detected

### P15.3 — Service Level Objectives (SLOs)
**New file:** `docs/sre/slos.md` + Prometheus recording rules

Define formal SLOs for each user-facing operation:

```yaml
# prometheus/recording_rules.yml
groups:
  - name: dokydoc_slos
    interval: 60s
    rules:

      # SLO 1: API Availability — 99.9% of requests succeed (non-5xx)
      - record: job:dokydoc_api_success_rate:5m
        expr: |
          sum(rate(http_requests_total{job="dokydoc-api",status!~"5.."}[5m]))
          /
          sum(rate(http_requests_total{job="dokydoc-api"}[5m]))

      # SLO 2: API Latency — 95% of requests complete in < 500ms
      - record: job:dokydoc_api_latency_p95:5m
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{job="dokydoc-api"}[5m]))
            by (le, endpoint)
          )

      # SLO 3: Validation Completeness — 99% of submitted validations complete within 5min
      - record: job:dokydoc_validation_completion_rate:1h
        expr: |
          sum(celery_task_succeeded_total{task="validate_document"})
          /
          (sum(celery_task_succeeded_total{task="validate_document"})
           + sum(celery_task_failed_total{task="validate_document"}))

      # SLO 4: Code Analysis — 99% of repos analyzed without error within 30min
      - record: job:dokydoc_analysis_success_rate:1h
        expr: |
          sum(celery_task_succeeded_total{task="repo_analysis_task"})
          /
          (sum(celery_task_succeeded_total{task="repo_analysis_task"})
           + sum(celery_task_failed_total{task="repo_analysis_task"}))

      # SLO 5: Gemini API — P99 call latency < 10s (external dependency)
      - record: job:gemini_latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(dokydoc_gemini_call_duration_seconds_bucket[5m]))
            by (le, prompt_type)
          )
```

**Error budget tracking:**
```
SLO: 99.9% availability → Error budget: 0.1% = 43.8 min/month
Current burn rate: X req failed / Y total = Z% over 30 days
Remaining budget: 43.8 - consumed = N minutes
Budget exhausted at current rate: ~D days
```

Surface error budget on the ops dashboard.

### P15.4 — Alerting Rules
**New file:** `prometheus/alert_rules.yml`

```yaml
groups:
  - name: dokydoc_critical
    rules:

      # Page immediately — customer impact
      - alert: APIHighErrorRate
        expr: job:dokydoc_api_success_rate:5m < 0.99
        for: 2m
        labels: { severity: critical, team: backend }
        annotations:
          summary: "API error rate > 1% for 2 minutes"
          runbook: "https://docs.dokydoc.com/runbooks/api-error-rate"

      - alert: APIHighLatency
        expr: job:dokydoc_api_latency_p95:5m > 2.0
        for: 5m
        labels: { severity: critical }
        annotations:
          summary: "API P95 latency > 2s for 5 minutes"
          runbook: "https://docs.dokydoc.com/runbooks/high-latency"

      - alert: DatabaseConnectionPoolExhausted
        expr: pg_stat_activity_count > pg_settings_max_connections * 0.9
        for: 1m
        labels: { severity: critical }
        annotations:
          summary: "PostgreSQL connection pool at 90% capacity"

      - alert: CeleryQueueBacklogHigh
        expr: celery_queue_length{queue="high"} > 50
        for: 3m
        labels: { severity: critical }
        annotations:
          summary: "High-priority Celery queue has > 50 tasks — user-facing delays"

  - name: dokydoc_warning
    rules:

      - alert: GeminiAPIHighLatency
        expr: job:gemini_latency_p99:5m > 8.0
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Gemini API P99 latency > 8s — analysis slowing down"

      - alert: ErrorBudgetBurnRateHigh
        expr: |
          (1 - job:dokydoc_api_success_rate:5m) > 14.4 * (1 - 0.999)
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "Error budget burning 14x faster than target — investigate now"

      - alert: DiskSpaceRunningLow
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.15
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Less than 15% disk space remaining"

      - alert: CeleryWorkerDown
        expr: celery_workers_online{queue="high"} < 1
        for: 1m
        labels: { severity: critical }
        annotations:
          summary: "No high-priority Celery workers online — validation blocked"

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Redis memory at 85% — cache evictions imminent"
```

**Alert routing (Alertmanager):**
```yaml
# alertmanager.yml
route:
  receiver: slack-ops
  routes:
    - match: { severity: critical }
      receiver: pagerduty-oncall
      continue: true
    - match: { severity: warning }
      receiver: slack-ops

receivers:
  - name: pagerduty-oncall
    pagerduty_configs:
      - service_key: ${PAGERDUTY_SERVICE_KEY}
        description: "{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}"

  - name: slack-ops
    slack_configs:
      - api_url: ${SLACK_WEBHOOK_URL}
        channel: "#ops-alerts"
        title: "{{ .GroupLabels.alertname }}"
        text: "{{ .Annotations.summary }}\nRunbook: {{ .Annotations.runbook }}"
```

### P15.5 — Grafana Dashboards
**New directory:** `monitoring/grafana/dashboards/`

Four dashboards, each as a JSON file importable into Grafana:

**Dashboard 1: `api-overview.json` — Operations Command Center**
```
Row 1: Key metrics (request rate, error rate, P95 latency, active users)
Row 2: Error budget gauge + burn rate chart
Row 3: Request rate by endpoint (top 10 by volume)
Row 4: Error rate by endpoint (top 10 by error count)
Row 5: Latency heatmap (all endpoints)
```

**Dashboard 2: `ai-intelligence.json` — Gemini & Analysis**
```
Row 1: Gemini calls/min, P95 latency, error rate, cost/hour
Row 2: Active analysis runs, queue depth by queue (high/default/low)
Row 3: Celery task success rate by task name
Row 4: BOE cache hit rate, Gemini calls saved (Phase 4)
Row 5: Training examples captured today (Phase 1 flywheel)
```

**Dashboard 3: `tenant-health.json` — Per-Tenant View**
```
Variables: tenant_id dropdown
Row 1: Coverage score trend (last 30 days)
Row 2: Validation runs, mismatch counts, resolution rate
Row 3: API usage vs tier limits (Phase 9)
Row 4: AI cost this month vs previous month
```

**Dashboard 4: `infrastructure.json` — System Health**
```
Row 1: CPU, memory, disk per service
Row 2: PostgreSQL: connections, query rate, slow queries, replication lag
Row 3: Redis: memory, hit rate, command rate, evictions
Row 4: PgBouncer: pool utilization, wait time
Row 5: Node health: uptime, load average
```

Provision dashboards automatically via Grafana `provisioning/` config — no manual import needed on new deployments.

### P15.6 — Health Check Endpoints
**File:** `backend/main.py`

```python
@app.get("/health")
def health_check():
    """Kubernetes liveness probe — fast, no DB."""
    return {"status": "ok", "version": settings.APP_VERSION}

@app.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe — checks all dependencies."""
    checks = {}
    overall = "ok"

    # PostgreSQL
    try:
        db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)[:50]}"
        overall = "degraded"

    # Redis
    try:
        cache_service.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:50]}"
        overall = "degraded"

    # Celery (check if at least 1 worker online)
    try:
        workers = celery_app.control.ping(timeout=2)
        checks["celery"] = "ok" if workers else "no_workers"
        if not workers:
            overall = "degraded"
    except Exception:
        checks["celery"] = "timeout"
        overall = "degraded"

    status_code = 200 if overall == "ok" else 503
    return JSONResponse({"status": overall, "checks": checks}, status_code=status_code)

@app.get("/health/workers")  # From Phase 12 — extended here
def worker_health():
    """Detailed Celery queue status — not used by k8s, used by ops."""
    ...
```

**Kubernetes probe config:**
```yaml
livenessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 2
```

### P15.7 — Incident Response Runbooks
**New directory:** `docs/runbooks/`

Each alert has a corresponding runbook:

**`api-error-rate.md`:**
```markdown
# Runbook: API High Error Rate

## Symptoms
- Alert: APIHighErrorRate
- Error rate > 1% sustained for 2+ minutes

## Immediate Actions (first 5 minutes)
1. Check Grafana: api-overview dashboard → which endpoints are erroring?
2. Check recent deployments: `kubectl rollout history deployment/dokydoc-api`
3. Check DB connections: `SHOW POOLS` in PgBouncer admin
4. Check Celery workers: GET /health/workers

## Common Causes & Fixes
| Cause | Fix |
|-------|-----|
| DB connection exhaustion | Scale PgBouncer pool or add DB read replica |
| Bad deployment | `kubectl rollout undo deployment/dokydoc-api` |
| Gemini API outage | Check status.google.com — enable fallback mode |
| OOM kills | Check memory metrics, scale pod replicas |

## Escalation
If not resolved in 15 minutes: escalate to backend lead.
Customer communications template: `docs/runbooks/templates/customer-comms.md`
```

**`high-latency.md`, `celery-queue-backlog.md`, `gemini-timeout.md`, `db-connection-pool.md`** — same structure.

**Incident management process:**
```markdown
# Incident Response Process

## Severity Definitions
- P1 (Critical): Complete outage or data loss — respond in 15 min
- P2 (High): Degraded performance affecting > 10% of users — respond in 1 hour
- P3 (Medium): Non-critical feature broken — respond in 4 hours
- P4 (Low): Minor bug, no user impact — next sprint

## During an Incident
1. Acknowledge PagerDuty alert (stops escalation)
2. Post to #incidents Slack: "I'm investigating [alert name]. Will update in 10 min."
3. Open incident doc from template: docs/runbooks/incident-template.md
4. Fix or mitigate (rollback, scale, toggle feature flag)
5. Post resolution: "Resolved. Root cause: X. Follow-up: Y."

## Post-Incident Review (all P1/P2)
Within 48 hours, complete blameless post-mortem:
- Timeline of events
- Root cause (5 Whys)
- What went well / what didn't
- Action items with owners and due dates
```

### P15.8 — Synthetic Monitoring
**New file:** `monitoring/synthetic/checks.py`

Runs every 5 minutes from an external location to verify end-to-end functionality:

```python
# Synthetic monitor — runs from a separate worker, not the main app
class SyntheticMonitor:
    """
    End-to-end health checks from outside the cluster.
    If these fail, the app is down from a user's perspective.
    """

    def check_api_health(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200

    def check_login(self):
        resp = requests.post(f"{BASE_URL}/api/login",
                             json={"email": SYNTHETIC_EMAIL, "password": SYNTHETIC_PASS})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def check_document_list(self):
        resp = requests.get(f"{BASE_URL}/api/v1/documents/",
                            headers=self.auth_headers, timeout=10)
        assert resp.status_code == 200
        assert "items" in resp.json()

    def check_ontology_graph(self):
        resp = requests.get(f"{BASE_URL}/api/v1/ontology/graph",
                            headers=self.auth_headers, timeout=15)
        assert resp.status_code == 200

    def check_search(self):
        resp = requests.get(f"{BASE_URL}/api/v1/search?q=test",
                            headers=self.auth_headers, timeout=10)
        assert resp.status_code == 200
```

Run via Celery beat every 5 minutes. On failure: trigger `critical` alert immediately (not waiting for Prometheus scrape interval).

### Verification
1. **Traces:** Make a validation API call → open Jaeger/Tempo → verify end-to-end trace with spans for FastAPI, SQLAlchemy queries, Redis lookups, and Gemini call. `tenant_id` attribute present on root span.
2. **Structured logs:** `GET /api/v1/documents/` → check application logs → verify JSON line with `request_id`, `tenant_id`, `path`, `duration_ms`
3. **SLO recording rules:** `curl prometheus:9090/api/v1/query?query=job:dokydoc_api_success_rate:5m` → returns value between 0.99 and 1.0
4. **Alert firing:** Manually set `HTTP_ERROR_RATE_OVERRIDE=0.05` env var → trigger `APIHighErrorRate` → verify Slack + PagerDuty notification within 3 minutes
5. **Grafana dashboard:** Open `api-overview` dashboard → all panels load with real data, no "No data" panels
6. **Liveness probe:** `curl /health` → 200 OK with `{"status": "ok"}`
7. **Readiness probe:** Stop PostgreSQL container → `curl /health/ready` → 503 with `{"checks": {"postgres": "error: ..."}}`
8. **Synthetic monitor:** Run `SyntheticMonitor().check_all()` → all checks pass in < 15s total
9. **Runbook links:** Every Prometheus alert has a `runbook` annotation URL pointing to an existing file in `docs/runbooks/`

---

## PHASE 16 — Multi-Region, Disaster Recovery & Data Residency
**Priority: Required for EU/APAC enterprise deals and regulated industry customers**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 12 (infrastructure), Phase 14 (security), Phase 15 (observability)**
**Estimated complexity: Very High**

### Context
Three forcing functions drive this phase:
1. **EU customers** require data to never leave EU jurisdiction (GDPR Article 46)
2. **Banks and hospitals** require RTO < 4 hours, RPO < 1 hour for business continuity sign-off
3. **Series A due diligence** will ask: "What happens if your primary region goes down?" The answer today is "we're down." That is unacceptable past 50 enterprise customers.

This phase implements: automated daily backups with tested restore, active-passive multi-region failover, per-tenant data residency routing, and a formal DR playbook.

### P16.1 — Backup Strategy & Automation
**New file:** `infrastructure/backup/backup.sh`, `infrastructure/backup/restore.sh`

**PostgreSQL backups:**
```bash
#!/bin/bash
# infrastructure/backup/postgres_backup.sh
# Runs daily at 02:00 UTC via cron/k8s CronJob

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="dokydoc_${ENVIRONMENT}_${TIMESTAMP}.dump"
S3_PATH="s3://${BACKUP_BUCKET}/postgres/${BACKUP_FILE}"

# pg_dump with compression (parallel jobs for speed on large DBs)
pg_dump \
    --format=custom \
    --compress=9 \
    --jobs=4 \
    --no-password \
    "${DATABASE_URL}" \
    --file="/tmp/${BACKUP_FILE}"

# Encrypt before upload (AES-256)
openssl enc -aes-256-cbc -pbkdf2 \
    -in "/tmp/${BACKUP_FILE}" \
    -out "/tmp/${BACKUP_FILE}.enc" \
    -pass "env:BACKUP_ENCRYPTION_KEY"

# Upload to S3 with server-side encryption
aws s3 cp "/tmp/${BACKUP_FILE}.enc" "${S3_PATH}" \
    --sse aws:kms \
    --storage-class STANDARD_IA  # Infrequent access = cheaper storage

# Verify backup integrity
aws s3api head-object --bucket "${BACKUP_BUCKET}" --key "postgres/${BACKUP_FILE}"

# Cleanup local temp files
rm -f "/tmp/${BACKUP_FILE}" "/tmp/${BACKUP_FILE}.enc"

echo "Backup complete: ${S3_PATH}"
```

**Retention policy:**
```
Daily backups:   Keep 30 days
Weekly backups:  Keep 12 weeks (keep every Sunday's backup)
Monthly backups: Keep 12 months (keep every 1st of month)
```

**Cross-region backup replication:**
```bash
# After primary backup, replicate to DR region
aws s3 sync \
    "s3://${PRIMARY_BACKUP_BUCKET}/" \
    "s3://${DR_BACKUP_BUCKET}/" \
    --source-region us-east-1 \
    --region eu-west-1
```

**Kubernetes CronJob:**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"     # 02:00 UTC daily
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: dokydoc/backup-runner:latest
              command: ["/scripts/postgres_backup.sh"]
              envFrom:
                - secretRef: { name: backup-credentials }
```

### P16.2 — Backup Restore Testing (Automated)
**Critical:** A backup that has never been tested is not a backup.

**New file:** `infrastructure/backup/test_restore.sh`

```bash
#!/bin/bash
# Runs weekly — restores backup to ephemeral test DB and runs smoke tests

set -euo pipefail

# Find latest backup
LATEST=$(aws s3 ls "s3://${BACKUP_BUCKET}/postgres/" --recursive \
         | sort | tail -1 | awk '{print $4}')

# Create ephemeral test database
psql -c "CREATE DATABASE dokydoc_restore_test_${TIMESTAMP};"

# Decrypt and restore
aws s3 cp "s3://${BACKUP_BUCKET}/${LATEST}" /tmp/restore.enc
openssl enc -d -aes-256-cbc -pbkdf2 \
    -in /tmp/restore.enc \
    -out /tmp/restore.dump \
    -pass "env:BACKUP_ENCRYPTION_KEY"

pg_restore \
    --dbname="dokydoc_restore_test_${TIMESTAMP}" \
    --jobs=4 \
    /tmp/restore.dump

# Run smoke tests against restored DB
DATABASE_URL="postgresql://.../${TIMESTAMP}" \
    pytest backend/tests/smoke/ -v

# Verify row counts match expectations
python3 scripts/verify_restore_integrity.py

# Cleanup
psql -c "DROP DATABASE dokydoc_restore_test_${TIMESTAMP};"
rm -f /tmp/restore.enc /tmp/restore.dump

echo "Restore test PASSED ✓ Latest backup is verified restorable"
```

**Celery beat schedule:** Weekly restore test every Sunday 03:00 UTC.
**Alert:** If restore test fails → PagerDuty P1 immediately.

**RTO/RPO targets (document in SLA):**
```
RPO (Recovery Point Objective): 1 hour
  → Daily backup + PostgreSQL streaming replication (1hr max lag)

RTO (Recovery Time Objective): 4 hours
  → Automated restore script + DNS failover + smoke test validation

For enterprise contracts: can offer RPO 15min (continuous WAL archiving) at premium tier
```

### P16.3 — PostgreSQL Streaming Replication
**File:** `infrastructure/postgres/` config files

Set up a read replica for disaster recovery and read offloading:

```
Primary DB (us-east-1)
    ↓ streaming replication (WAL, real-time)
Read Replica (us-east-1) — for analytics queries, read-heavy endpoints
    ↓ async replication (pg_basebackup daily + WAL shipping)
DR Standby (eu-west-1) — for disaster recovery
```

**Application-level read/write splitting:**
```python
# backend/app/core/database.py

# Write operations → primary
write_engine = create_engine(settings.DATABASE_URL_PRIMARY)

# Read-heavy operations → replica (analytics, search, graph queries)
read_engine = create_engine(settings.DATABASE_URL_REPLICA or settings.DATABASE_URL_PRIMARY)

def get_read_db():
    """Use for GET endpoints that don't need real-time consistency."""
    with SessionLocal(bind=read_engine) as session:
        yield session

def get_write_db():
    """Use for all writes and reads requiring latest data."""
    with SessionLocal(bind=write_engine) as session:
        yield session
```

**Endpoints that safely use read replica:**
- `GET /ontology/graph` — graph rarely changes mid-request
- `GET /analytics/*` — analytics can be slightly stale
- `GET /search` — search index is eventually consistent anyway
- `GET /documents/` list — listing fine with 1s lag

**Endpoints that MUST use primary:**
- All POST/PUT/DELETE
- `GET /validation/{id}/results` — needs fresh mismatch data
- `GET /health/ready` — must check primary

### P16.4 — Multi-Region Architecture
**New file:** `infrastructure/multi-region/architecture.md`

**Active-Passive multi-region setup:**

```
Region: us-east-1 (PRIMARY — all writes)
├── API servers (3 replicas)
├── Celery workers (high/default/low queues)
├── PostgreSQL primary
├── Redis primary
└── S3 bucket (uploads + backups)

Region: eu-west-1 (DR STANDBY — read-only until failover)
├── API servers (1 replica, read-only mode)
├── Celery workers (paused — activate on failover)
├── PostgreSQL DR standby (streaming from primary)
├── Redis replica
└── S3 bucket (replicated from primary)

Global:
├── Cloudflare (or AWS Route 53) — GeoDNS + health checks
├── CDN — frontend static assets (all regions)
└── Secrets Manager — replicated across regions
```

**GeoDNS routing rules:**
```yaml
# Route 53 health check + failover
primary:
  region: us-east-1
  health_check: https://api.dokydoc.com/health/ready
  failover_type: PRIMARY

standby:
  region: eu-west-1
  health_check: https://api-eu.dokydoc.com/health/ready
  failover_type: SECONDARY  # Only activated when primary health check fails
```

**Failover trigger:** If `/health/ready` returns non-200 for 3 consecutive checks (30 seconds) → Route 53 automatically routes to EU standby.

### P16.5 — Data Residency Routing
**File:** `backend/app/core/config.py`, `backend/app/models/tenant.py`

Enterprise EU/APAC customers cannot have data leave their jurisdiction. Implement per-tenant data residency:

```python
# New tenant field
class DataRegion(str, Enum):
    US = "us"          # Default — us-east-1
    EU = "eu"          # EU only — eu-west-1 (Frankfurt or Ireland)
    APAC = "apac"      # Asia-Pacific — ap-southeast-1 (Singapore)
    US_GOV = "us-gov"  # GovCloud for US federal customers

# In tenant model:
data_region: Mapped[str] = mapped_column(String, default="us")
```

**Region-aware DB connections:**
```python
# backend/app/api/deps.py
def get_tenant_db(tenant: Tenant = Depends(get_current_tenant)):
    """Returns DB session connected to tenant's data region."""
    region_url = settings.DATABASE_URLS.get(tenant.data_region,
                                             settings.DATABASE_URL)
    with get_regional_session(region_url) as session:
        yield session
```

**Region-aware S3 storage:**
```python
# backend/app/services/file_storage_service.py
REGIONAL_BUCKETS = {
    "us": "dokydoc-uploads-us-east-1",
    "eu": "dokydoc-uploads-eu-west-1",
    "apac": "dokydoc-uploads-ap-southeast-1",
}

def upload(self, file, key, tenant_id):
    tenant = crud.tenant.get(db, tenant_id)
    bucket = REGIONAL_BUCKETS[tenant.data_region]
    # Upload to region-specific bucket
    s3_client = boto3.client("s3", region_name=BUCKET_REGIONS[bucket])
    s3_client.put_object(Bucket=bucket, Key=key, Body=file)
```

**Gemini API residency:** Google Vertex AI (which powers Gemini) offers regional endpoints. Route EU tenants to `europe-west4` Vertex AI endpoint:
```python
GEMINI_ENDPOINTS = {
    "us":   "https://us-central1-aiplatform.googleapis.com",
    "eu":   "https://europe-west4-aiplatform.googleapis.com",
    "apac": "https://asia-southeast1-aiplatform.googleapis.com",
}
```

**Migration:** `backend/alembic/versions/s26a1_tenant_data_region.py`

**Onboarding:** During tenant registration, show region selector:
```tsx
<RegionSelector
  value={region}
  onChange={setRegion}
  options={[
    { value: "us", label: "United States", flag: "🇺🇸",
      description: "Default. Fastest for US-based teams." },
    { value: "eu", label: "European Union", flag: "🇪🇺",
      description: "GDPR compliant. Data stays in EU." },
    { value: "apac", label: "Asia-Pacific", flag: "🌏",
      description: "Optimized for APAC teams." },
  ]}
/>
```

### P16.6 — Failover Runbook & DR Drill
**New file:** `docs/runbooks/disaster-recovery.md`

```markdown
# Disaster Recovery Runbook

## Scenario: Primary Region (us-east-1) Complete Outage

### Automatic Actions (0-2 minutes)
1. Route 53 health check detects /health/ready failures
2. After 3 failures (30s), DNS automatically points to eu-west-1
3. EU standby API servers begin receiving traffic (read-only mode)
4. PagerDuty P1 alert fires

### Manual Actions Required (2-30 minutes)
1. Confirm outage: check AWS console for us-east-1 status
2. Activate EU Celery workers:
   `kubectl scale deployment/celery-workers --replicas=4 -n dokydoc-eu`
3. Promote EU PostgreSQL standby to primary:
   `pg_ctl promote -D /var/lib/postgresql/data`
4. Update DATABASE_URL secret in EU Secrets Manager to point to promoted DB
5. Restart API pods to pick up new DB URL:
   `kubectl rollout restart deployment/dokydoc-api -n dokydoc-eu`
6. Verify health: `curl https://api.dokydoc.com/health/ready`
7. Post status update to status page

### Recovery (30-240 minutes)
1. When us-east-1 restored, sync data from EU primary back to US
2. Take EU primary out of primary mode (demote back to standby)
3. Update Route 53 back to us-east-1 as primary
4. Verify no data loss: compare row counts between regions

### Expected Data Loss
RPO: Up to 1 hour of writes if replication was lagging
RTO: 30 minutes for manual failover, 2 minutes for DNS failover (read-only mode)
```

**Quarterly DR drill:**
- Schedule: First Monday of each quarter, 08:00 UTC (low traffic)
- Procedure: Simulate primary region failure, execute failover, verify EU works, restore
- Success criteria: Full failover complete in < 30 minutes, zero data corruption
- Document results in `docs/dr-drill-results/YYYY-QN.md`

### P16.7 — Status Page
**New:** Public status page at `status.dokydoc.com`

Options: Atlassian Statuspage (managed), Cachet (self-hosted), or simple static page updated by CI.

**Components tracked:**
```
API (api.dokydoc.com)              ● Operational
Document Analysis                  ● Operational
Code Analysis                      ● Operational
AI / Validation Engine             ● Operational
Knowledge Graph                    ● Operational
Auto-Documentation                 ● Operational
Chat Assistant                     ● Operational
Integrations (Jira, Confluence)    ● Operational
EU Region (eu.dokydoc.com)         ● Operational
```

**Automated status updates:**
- Prometheus alerts → webhook → update status page component
- Incident creation → post status page incident automatically
- Resolution → post resolution + mean time to recover

**Subscribe to updates:** Email/SMS/webhook subscriptions for customers.

**Historical uptime:** Show 90-day uptime history per component. Enterprise customers will check this during procurement.

### P16.8 — Data Deletion & Right to Erasure (GDPR)
**File:** `backend/app/api/endpoints/tenants.py`, new `backend/app/services/data_deletion_service.py`

GDPR Article 17 requires the ability to delete all data for a tenant or user.

```python
class DataDeletionService:
    def delete_tenant_data(self, db, tenant_id: int, dry_run: bool = True):
        """
        Soft-deletes all tenant data. Hard-delete after 30-day grace period.
        dry_run=True returns what would be deleted without deleting.
        """
        manifest = {
            "documents": crud.document.count(db, tenant_id),
            "repositories": crud.repository.count(db, tenant_id),
            "users": crud.user.count(db, tenant_id),
            "ontology_concepts": crud.ontology_concept.count(db, tenant_id),
            "mismatches": crud.mismatch.count(db, tenant_id),
            "training_examples": crud.training_example.count(db, tenant_id),
            "chat_messages": crud.conversation.count_messages(db, tenant_id),
            "audit_logs": "retained per legal hold policy",
            "s3_objects": file_storage_service.count_objects(tenant_id),
        }

        if dry_run:
            return {"action": "dry_run", "would_delete": manifest}

        # Soft-delete: set deleted_at on tenant record
        crud.tenant.soft_delete(db, tenant_id)

        # Schedule hard-delete in 30 days (grace period for accidental deletion)
        hard_delete_tenant_data.apply_async(
            args=[tenant_id],
            countdown=30 * 24 * 3600  # 30 days
        )

        # Immediately anonymize PII (cannot wait 30 days)
        self._anonymize_pii(db, tenant_id)

        # Log for GDPR compliance
        audit_service.log(db, event="tenant.deletion_requested",
                          metadata={"tenant_id": tenant_id, "manifest": manifest})

        return {"action": "soft_deleted", "hard_delete_at": datetime.utcnow() + timedelta(days=30)}
```

**Endpoints:**
```
DELETE /api/v1/tenants/{id}/data
  Auth: owner role only + MFA confirmation required
  Body: { confirm: true, reason: str }
  Response: { manifest, hard_delete_at }

GET /api/v1/tenants/{id}/data-export
  GDPR Article 20 — data portability
  Returns: ZIP of all tenant data in JSON format
  Auth: owner only
```

**Migration:** `backend/alembic/versions/s26b1_tenant_soft_delete.py`
Add `deleted_at: datetime | None` + `deletion_reason: str | None` to tenants table.

### Verification
1. **Backup runs:** Check Kubernetes CronJob history → backup jobs succeeded for last 7 days
2. **Restore test:** Run `test_restore.sh` manually → smoke tests pass against restored DB
3. **Replication lag:** `SELECT now() - pg_last_xact_replay_timestamp() AS lag` on replica → lag < 60 seconds under normal load
4. **Failover drill:** Manually stop primary API → verify Route 53 DNS switches to EU standby within 2 minutes, `GET /health` returns 200 from EU
5. **Data residency:** Create EU tenant → upload document → verify `SELECT storagekey FROM documents WHERE tenant_id = X` points to `eu-west-1` bucket prefix
6. **GDPR deletion:** Call `DELETE /tenants/{id}/data?dry_run=true` → manifest shows correct counts. Call without dry_run → verify tenant soft-deleted, PII anonymized immediately
7. **Status page:** Trigger `APIHighErrorRate` Prometheus alert → verify status page auto-updates to "Degraded" within 2 minutes
8. **Backup encryption:** Download backup from S3, attempt to restore without decryption key → fails with OpenSSL error (verify encryption works)

---

## PHASE 17 — Advanced AI & Future Roadmap (LoRA Execution, Multimodal, Sovereign LLM)
**Priority: Strategic — competitive moat, not required for launch**
**Parallel-safe: YES [PARALLEL-SAFE]**
**Depends: Phase 10 (training pipeline must have data), Phase 14 (security), Phase 16 (multi-region)**
**Estimated complexity: Extreme**

### Context
This is the phase where DokyDoc stops being a "great product" and becomes an "uncopyable platform." The training flywheel from Phase 1 has been accumulating labeled examples. The evaluation harness from Phase 10 has been measuring model quality. The LoRA adapter registry is ready. Now: execute the actual fine-tuning, deploy self-hosted inference, add multimodal analysis (diagrams, wireframes, architecture images), and build the research foundation for a sovereign multi-tenant LLM architecture.

This phase is explicitly designed to be **executed in parts as funding milestones are reached** — not all at once. Each sub-phase is independently valuable.

### P17.1 — First LoRA Fine-Tune: Mismatch Judgment Model
**Trigger:** Phase 10 readiness report shows `mismatch_judgment` dataset ready (≥500 labeled examples)

**Target model for fine-tuning:** `gemma-3-9b-it` (Google's open model, free weights, 9B params)
- Reason: Already using Google ecosystem (Gemini), weights are open, fits on a single A100 GPU
- Alternative: `Llama-3.1-8b-instruct` (Meta's open model, better benchmarks, larger community)
- Decision criteria: Whichever performs better on internal eval harness (Phase 10)

**Fine-tuning pipeline:**
```python
# backend/app/services/lora_training_service.py (new)
class LoRATrainingService:
    """
    Orchestrates fine-tuning jobs on GPU infrastructure.
    Supports: Lambda Labs, RunPod, Google Vertex AI Training, self-hosted.
    """

    def submit_training_job(
        self,
        db,
        dataset_version_id: int,
        base_model: str = "google/gemma-3-9b-it",
        lora_config: LoRAConfig = None,
        target_tenant_id: int | None = None  # None = shared base model
    ) -> TrainingJob:
        """
        Submits a LoRA fine-tuning job.
        Returns immediately with job_id — training is async (4-8 hours).
        """
        dataset = crud.training_dataset_version.get(db, dataset_version_id)

        config = lora_config or LoRAConfig(
            r=16,                    # LoRA rank — higher = more capacity, more memory
            lora_alpha=32,           # Scaling factor
            target_modules=["q_proj", "v_proj"],  # Which layers to adapt
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )

        job = self._submit_to_provider(
            dataset_s3_path=dataset.storage_path,
            base_model=base_model,
            lora_config=config,
            hyperparams=TrainingHyperparams(
                num_epochs=3,
                learning_rate=2e-4,
                batch_size=4,
                gradient_accumulation_steps=4,  # Effective batch = 16
                warmup_ratio=0.03,
                lr_scheduler="cosine",
                max_seq_length=2048
            )
        )

        # Track in DB
        return crud.training_job.create(db, obj_in={
            "dataset_version_id": dataset_version_id,
            "base_model": base_model,
            "target_tenant_id": target_tenant_id,
            "provider_job_id": job.id,
            "status": "submitted",
            "estimated_cost_usd": job.estimated_cost
        })
```

**Training infrastructure options (in order of preference at each funding stage):**

| Stage | Option | Cost | GPU |
|-------|--------|------|-----|
| Pre-seed | Lambda Labs on-demand | ~$20-40/run | A100 40GB |
| Seed | RunPod spot instances | ~$8-15/run | A100 80GB |
| Series A | Google Vertex AI Training | Managed, ~$50/run | TPU v4 |
| Series B+ | Self-hosted A100 cluster | CapEx, ~$0.30/hr amortized | 8× A100 |

**New DB model:** `TrainingJob`
```python
class TrainingJob(Base):
    __tablename__ = "training_jobs"
    id: int
    dataset_version_id: int (FK)
    target_tenant_id: int | None  # NULL = shared model
    base_model: str
    provider: str          # "lambda", "runpod", "vertex_ai", "self_hosted"
    provider_job_id: str
    status: str            # "submitted", "running", "completed", "failed"
    lora_adapter_path: str | None   # S3 path when complete
    training_loss: float | None
    eval_accuracy: float | None
    cost_usd: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
```

**Migration:** `backend/alembic/versions/s27a1_training_jobs.py`

### P17.2 — vLLM Self-Hosted Inference
**New directory:** `infrastructure/vllm/`

Once a fine-tuned adapter exists, serve it via vLLM with multi-LoRA support:

```yaml
# infrastructure/vllm/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
spec:
  replicas: 1  # Scale up as tenant count grows
  template:
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          command:
            - python
            - -m
            - vllm.entrypoints.openai.api_server
            - --model
            - google/gemma-3-9b-it
            - --enable-lora                    # Critical: enables LoRA adapter loading
            - --max-loras
            - "50"                            # Max concurrent tenant adapters in memory
            - --max-lora-rank
            - "64"
            - --gpu-memory-utilization
            - "0.90"
            - --tensor-parallel-size
            - "1"                             # 1 GPU per instance (scale horizontally)
          resources:
            limits:
              nvidia.com/gpu: "1"
              memory: "40Gi"
          volumeMounts:
            - name: model-cache
              mountPath: /root/.cache/huggingface
            - name: lora-adapters
              mountPath: /adapters
      volumes:
        - name: model-cache
          persistentVolumeClaim: { claimName: model-cache-pvc }
        - name: lora-adapters
          persistentVolumeClaim: { claimName: lora-adapters-pvc }
      nodeSelector:
        cloud.google.com/gke-accelerator: "nvidia-tesla-a100"
```

**Per-tenant LoRA request:**
```python
# backend/app/services/ai/vllm_provider.py (new)
import openai  # vLLM exposes OpenAI-compatible API

class VLLMProvider:
    def __init__(self, endpoint: str):
        self.client = openai.AsyncOpenAI(
            base_url=f"{endpoint}/v1",
            api_key="not-required"  # vLLM doesn't need API key internally
        )

    async def generate(self, prompt: str, tenant_id: int) -> str:
        adapter = lora_registry.get_active_adapter(tenant_id)

        extra_body = {}
        if adapter:
            extra_body["lora_request"] = {
                "lora_name": f"tenant_{tenant_id}",
                "lora_path": adapter.adapter_path,
                "lora_int_id": tenant_id  # Unique per tenant for caching
            }

        response = await self.client.chat.completions.create(
            model="google/gemma-3-9b-it",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
            extra_body=extra_body
        )
        return response.choices[0].message.content
```

**Cost comparison at scale:**
```
Gemini Flash API:     $0.075 / 1M input tokens
Self-hosted vLLM:     ~$0.003 / 1M tokens (A100 @ $2/hr, 700 tokens/sec)
Savings at 10B tokens/month: $720,000/yr → $30,000/yr (96% reduction)
Break-even: ~500M tokens/month (roughly 50-100 enterprise tenants)
```

### P17.3 — Multimodal Document Analysis
**File:** `backend/app/services/ai/prompt_manager.py`, `backend/app/services/document_parser.py`

Gemini 2.0 Flash and Pro are natively multimodal. Extend document analysis to process images embedded in documents:

**What to extract from images in BRDs/SRS documents:**
```python
MULTIMODAL_EXTRACTION_TARGETS = {
    "architecture_diagram": {
        "extract": ["services", "databases", "APIs", "data flows", "external systems"],
        "output": "structured component list + relationship edges for BOE",
        "prompt": "This is a software architecture diagram. List every component, database, API, and external system visible. For each, describe what it does and what it connects to."
    },
    "wireframe": {
        "extract": ["UI components", "user actions", "data fields", "navigation flows"],
        "output": "user story atoms for validation engine",
        "prompt": "This is a UI wireframe. Extract every form field, button action, navigation link, and implied business rule visible."
    },
    "er_diagram": {
        "extract": ["entities", "relationships", "cardinality", "key fields"],
        "output": "data model requirements for validation against actual DB models",
        "prompt": "This is an ER/database diagram. Extract every entity, its fields, and the relationships between entities with their cardinality (1:1, 1:N, N:M)."
    },
    "flow_chart": {
        "extract": ["decision points", "process steps", "outcomes", "actors"],
        "output": "business process requirement atoms",
        "prompt": "This is a business process flowchart. Extract every step, decision point, actor, and outcome as discrete requirements."
    },
    "sequence_diagram": {
        "extract": ["actors", "messages", "order", "conditions"],
        "output": "API contract requirements for validation",
        "prompt": "This is a sequence diagram. Extract every actor, every message/API call between actors, the order of operations, and any conditional flows."
    }
}
```

**Document parser extension:**
```python
# backend/app/services/document_parser.py

def extract_images_from_pdf(pdf_bytes: bytes) -> list[ExtractedImage]:
    """Extract all images from PDF with their page number and position."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page_num, page in enumerate(doc):
        for img_ref in page.get_images():
            xref = img_ref[0]
            img_data = doc.extract_image(xref)
            images.append(ExtractedImage(
                page_num=page_num,
                image_bytes=img_data["image"],
                mime_type=f"image/{img_data['ext']}",
                width=img_data["width"],
                height=img_data["height"]
            ))
    return images

async def analyze_image(image: ExtractedImage, context: str) -> ImageAnalysisResult:
    """Send image to Gemini for multimodal extraction."""
    # Classify image type first (cheap call)
    image_type = await _classify_image_type(image)
    if image_type == "irrelevant":  # logos, decorative images
        return None

    # Extract structured data based on image type
    target = MULTIMODAL_EXTRACTION_TARGETS.get(image_type)
    if not target:
        return None

    prompt = f"{target['prompt']}\n\nDocument context: {context}"
    result = await gemini_service.generate_multimodal(prompt, image.image_bytes)
    return ImageAnalysisResult(
        image_type=image_type,
        extracted_data=result,
        output_type=target["output"],
        page_num=image.page_num
    )
```

**Integration into document pipeline:**
```python
# backend/app/tasks/document_pipeline.py
# After text extraction, add image analysis step:
images = document_parser.extract_images_from_pdf(raw_bytes)
for image in images:
    result = await analyze_image(image, document.content[:2000])
    if result:
        # Route to correct engine based on output_type
        if result.output_type == "structured component list":
            business_ontology_service.ingest_diagram_entities(db, result, document.id)
        elif result.output_type == "user story atoms":
            validation_service.ingest_diagram_atoms(db, result, document.id)
        elif result.output_type == "data model requirements":
            validation_service.ingest_er_requirements(db, result, document.id)
```

**Frontend:** Show extracted diagram entities alongside text requirements in the document detail view. Each extracted entity is clickable and links to the corresponding OntologyConcept.

### P17.4 — Agentic Analysis Workflows
**New file:** `backend/app/services/ai/agent_orchestrator.py`

Instead of single-shot prompts, implement multi-step agentic analysis for complex queries:

```python
class AnalysisAgent:
    """
    Multi-step agent that can use DokyDoc's own APIs as tools.
    Used for: complex gap analysis, cross-initiative impact assessment,
    regulatory compliance checks, security review automation.
    """

    TOOLS = [
        Tool(name="search_codebase",
             description="Search code components by functionality",
             fn=lambda q: unified_search(q, types=["code_component"])),

        Tool(name="get_validation_gaps",
             description="Get all unimplemented requirements for a document",
             fn=lambda doc_id: crud.mismatch.get_by_document(db, doc_id, status="open")),

        Tool(name="trace_data_flow",
             description="Trace data flow from an API endpoint through all layers",
             fn=lambda comp_id: data_flow_service.get_request_trace(db, comp_id, tenant_id)),

        Tool(name="check_regulatory_compliance",
             description="Check if a requirement meets regulatory standards",
             fn=lambda req, framework: compliance_checker.check(req, framework)),

        Tool(name="cross_reference_initiatives",
             description="Find all initiatives affected by a concept change",
             fn=lambda concept: initiative_service.find_by_concept(db, concept, tenant_id)),
    ]

    async def run(self, goal: str, max_steps: int = 10) -> AgentResult:
        """ReAct-style agent loop: Reason → Act → Observe → Repeat."""
        history = [{"role": "system", "content": AGENT_SYSTEM_PROMPT},
                   {"role": "user", "content": goal}]
        for step in range(max_steps):
            response = await gemini_service.generate_with_tools(history, self.TOOLS)
            if response.finish_reason == "stop":
                return AgentResult(answer=response.content, steps=step+1)
            # Execute tool call
            tool_result = await self._execute_tool(response.tool_call)
            history.append({"role": "tool", "content": str(tool_result)})
        return AgentResult(answer="Max steps reached", steps=max_steps)
```

**Example agent use cases:**
- "Find all regulatory gaps in our payment BRD against PCI-DSS requirements"
- "Which code changes from last week's PR might break documented requirements?"
- "Generate a remediation plan for all critical mismatches in the Payment Initiative"
- "Check if our authentication implementation matches OWASP ASVS Level 2"

**Expose via chat:** Slash command `/agent` in chat activates the agentic mode. User sees step-by-step reasoning as the agent works (streamed to frontend).

### P17.5 — Cross-Tenant Anonymized Intelligence
**Opt-in feature for enterprise tenants who want aggregated industry benchmarks**

```python
class IndustryBenchmarkService:
    """
    With tenant consent, aggregate anonymized metrics across tenants
    in the same industry to produce benchmark data.
    Data is: anonymized, aggregated, never individual records shared.
    """

    def get_industry_benchmark(self, industry: str, metric: str) -> BenchmarkResult:
        """
        Returns: p25, p50, p75, p90 of a metric across consenting tenants
        in the same industry. Minimum 10 tenants required (k-anonymity).
        """
        # Only tenants where settings.benchmark_opt_in = True
        consenting = crud.tenant.get_consenting_benchmarkers(db, industry)
        if len(consenting) < 10:
            return BenchmarkResult(available=False, reason="insufficient_sample")

        values = [self._get_metric(t, metric) for t in consenting]
        return BenchmarkResult(
            available=True,
            p25=np.percentile(values, 25),
            p50=np.percentile(values, 50),
            p75=np.percentile(values, 75),
            p90=np.percentile(values, 90),
            sample_size=len(consenting)
        )
```

**Example benchmark metrics:**
- Average documentation coverage score (fintech: p50 = 74%)
- Average open mismatch count per document
- Average time from BRD upload to first validation
- Most common mismatch types by industry

**Frontend:** "Industry Benchmark" card on analytics page:
```tsx
<BenchmarkCard
  metric="Documentation Coverage"
  yourScore={tenant.avg_coverage}
  industryP50={benchmark.p50}
  industryP75={benchmark.p75}
  label={`You're in the top ${percentile}% of ${industry} companies`}
/>
```

### P17.6 — Regulatory Compliance Engine
**New service:** `backend/app/services/compliance_engine.py`

A specialized validation pass that checks requirements against regulatory frameworks:

```python
REGULATORY_FRAMEWORKS = {
    "PCI_DSS_v4": PCIDSSFramework(version="4.0", requirements=load_pci_requirements()),
    "HIPAA":      HIPAAFramework(requirements=load_hipaa_requirements()),
    "GDPR":       GDPRFramework(requirements=load_gdpr_requirements()),
    "SOC2_TYPE2": SOC2Framework(requirements=load_soc2_requirements()),
    "ISO_27001":  ISO27001Framework(requirements=load_iso27001_requirements()),
    "RBI":        RBIFramework(requirements=load_rbi_guidelines()),   # India
    "MAS":        MASFramework(requirements=load_mas_guidelines()),   # Singapore
    "FCA":        FCAFramework(requirements=load_fca_guidelines()),   # UK
}

class ComplianceEngine:
    def check_document_compliance(
        self,
        db,
        document_id: int,
        tenant_id: int,
        frameworks: list[str]
    ) -> ComplianceReport:
        """
        For each RequirementAtom, checks if it satisfies requirements
        from the selected regulatory frameworks.
        Returns: coverage per framework + gaps + risk assessment.
        """
        atoms = crud.requirement_atom.get_by_document(db, document_id)
        results = {}

        for framework_name in frameworks:
            framework = REGULATORY_FRAMEWORKS[framework_name]
            coverage = framework.assess_coverage(atoms)
            results[framework_name] = {
                "coverage_pct": coverage.covered / coverage.total,
                "covered_requirements": coverage.covered_list,
                "missing_requirements": coverage.missing_list,
                "risk_level": coverage.risk_level,  # LOW/MEDIUM/HIGH/CRITICAL
            }

        return ComplianceReport(frameworks=results, document_id=document_id)
```

**New endpoint:**
```
POST /api/v1/validation/{document_id}/compliance-check
  Body: { frameworks: ["PCI_DSS_v4", "GDPR"] }
  Returns: ComplianceReport with per-framework coverage + gaps

GET /api/v1/validation/{document_id}/compliance-report
  Format: PDF download (enterprise feature)
  Content: Formal compliance assessment suitable for auditors
```

**Auto-detection:** If `tenant.settings.regulatory_context` includes "PCI-DSS" (set in Phase 5), automatically run compliance check on every validation run. Surface gaps in validation panel.

### P17.7 — Product Vision & Execution Roadmap
**Non-code deliverable:** `docs/product/vision-2027.md`

```markdown
# DokyDoc — Product Vision 2027

## The North Star
Every engineering team's documentation is as current as their code.
No BRD ever goes stale. No code ever lacks documentation.
The gap between "what we said we'd build" and "what we built" is zero.

## Revenue Model Evolution

### 2026: SaaS (Current + Phase 0-16)
- Free: 3 docs/month, 1 repo, basic validation
- Pro ($99/mo): 50 docs, 10 repos, data flow diagrams, integrations
- Enterprise ($2,000-10,000/mo): Unlimited, SSO, SOC 2, SLA, dedicated support

### 2027: Platform + Data Flywheel (Phase 17+)
- Shared fine-tuned model: all pro/enterprise tenants benefit from collective training
- Per-tenant LoRA adapters: company-specific model included in Enterprise
- Industry models: "DokyDoc for Fintech," "DokyDoc for Healthcare" — premium tiers
- Compliance Engine add-on: PCI-DSS/HIPAA/GDPR automated assessment ($500/mo)
- API platform revenue: pay-per-call for the DokyDoc API (developer ecosystem)

### 2028: Sovereign LLM (if funding secured)
- Self-hosted vLLM inference: 96% cost reduction at scale
- Per-tenant model personalization: adapts to each company's terminology
- Benchmark marketplace: anonymized industry intelligence as a product
- Regulatory framework library: 50+ frameworks, updated continuously

## Competitive Moat Stack
Layer 1 (now):     Product quality — better validation accuracy than competitors
Layer 2 (2026):    Network effects — training data from every team's decisions
Layer 3 (2027):    Model advantage — fine-tuned on domain > generic LLMs
Layer 4 (2028):    Data lock-in — switching costs increase as model learns your company

## Key Metrics to Track
- Documentation coverage score (p50 across all tenants) — quality signal
- Mismatch resolution rate — engagement signal
- Training examples labeled / month — flywheel health signal
- Gemini cost / document validated — efficiency signal
- Net Revenue Retention — enterprise health signal (target: > 120%)
```

### Sprint Planning Summary (All 18 Phases)

| Phase | Name | Priority | Parallel-Safe | Complexity |
|-------|------|----------|---------------|------------|
| 0 | Critical Bugs & Security Baseline | P0 — Do First | Yes | Medium |
| 1 | Data Flywheel | P0 — Start Now | Yes | Medium |
| 2 | Cosine Similarity Fix | P0 — Quick Win | Yes | Low |
| 3 | Data Flow Diagrams | P1 — High | Yes | High |
| 4 | 4-Engine Integration | P1 — High ROI | No | Very High |
| 5 | Dynamic Prompting | P1 — High | Yes | Medium-High |
| 6 | Enterprise Governance | P1 — Enterprise | Yes | High |
| 7 | Integrations & Export | P1 — Revenue | Yes | High |
| 8 | Search, Chat & RAG | P2 — Engagement | Yes | High |
| 9 | Analytics & Billing | P2 — Monetization | Yes | Medium-High |
| 10 | LLM Strategy Foundation | P2 — Strategic | Yes | Very High |
| 11 | Auto-Docs & Living Docs | P2 — Flagship | Yes | High |
| 12 | Performance & Scalability | P2 — Scale | Yes | High |
| 13 | Developer Experience | P3 — Adoption | Yes | Medium |
| 14 | Security Hardening | P3 — Enterprise | Yes | Very High |
| 15 | Observability & SRE | P3 — Reliability | Yes | Medium-High |
| 16 | Multi-Region & DR | P3 — Enterprise | Yes | Very High |
| 17 | Advanced AI & Roadmap | P4 — Future | Yes | Extreme |

**Recommended sprint sequence for a team of 4 engineers:**

```
Sprint 1 (Weeks 1-2):  Phase 0 + Phase 1 + Phase 2 (all parallel-safe, all high priority)
Sprint 2 (Weeks 3-4):  Phase 3 + Phase 5 (parallel — both standalone)
Sprint 3 (Weeks 5-6):  Phase 4 (depends on Phase 0) + Phase 6 (parallel)
Sprint 4 (Weeks 7-8):  Phase 7 + Phase 8 (parallel)
Sprint 5 (Weeks 9-10): Phase 9 + Phase 11 (parallel)
Sprint 6 (Weeks 11-12):Phase 12 + Phase 13 (parallel)
Sprint 7 (Weeks 13-14):Phase 14 + Phase 15 (parallel)
Sprint 8 (Weeks 15-16):Phase 10 + Phase 16 (parallel)
Sprint 9+:             Phase 17 (milestone-gated by funding + data availability)
```

---

## PLAN COMPLETE

**Total phases:** 18 (Phase 0 through Phase 17)
**Total new DB models:** ~25 (TrainingExample, CodeDataFlowEdge, CoverageSnapshot, SearchIndex, WebhookSubscription, LoRAAdapterRecord, TrainingJob, TrainingDatasetVersion, ModelEvaluationRun, TokenBlocklist, and more)
**Total new migrations:** ~35
**Total new services:** ~20
**Total new API endpoints:** ~80+
**Total new frontend pages/components:** ~25

**Nothing currently working breaks.** Every change is:
- Non-breaking (additive models, try/except guarded hooks)
- Feature-flagged (tier checks, config flags)
- Independently deployable (each phase has its own migrations, no cross-phase DB dependencies at deployment time)


