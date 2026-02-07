# SPRINT 3: BUSINESS ONTOLOGY ENGINE & CODE ANALYSIS

## Solution Architect's Assessment

**Sprint Goal:** Build the "brain" — domain understanding + deep code analysis
**Duration:** 2 weeks | **Capacity:** 140h | **Planned:** 128h | **Buffer:** 12h

---

## 1. PRODUCT UNDERSTANDING — WHERE WE ARE

### What DokyDoc Is Today (End of Sprint 2)

DokyDoc is a **multi-tenant, AI-powered Document Analysis & Governance Platform** that:

1. **Ingests documents** (PDF, DOCX, TXT) through a robust multi-strategy parser with OCR fallback
2. **Runs a 3-pass AI analysis pipeline** (Composition → Segmentation → Structured Extraction) using Google Gemini
3. **Tracks code components** with AI-powered code analysis (summary + structured analysis)
4. **Links documents to code** via `DocumentCodeLink` join table
5. **Validates** document-vs-code consistency through 3 validation profiles (API endpoints, business logic, general consistency)
6. **Enforces billing** with per-tenant prepaid/postpaid models and real-time cost tracking
7. **Manages tasks** with Kanban-style status flow
8. **Provides role-based dashboards** (CXO, Developer, BA, PM)

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 15)                       │
│  React 19 + Radix UI + Tailwind CSS                                │
│  Pages: Login, Register, Role-Select, Dashboard (role-based),      │
│         Documents, Code, Validation Panel, Tasks, Billing, Settings│
└─────────────────────┬───────────────────────────────────────────────┘
                      │ REST API (Bearer JWT)
┌─────────────────────▼───────────────────────────────────────────────┐
│                    BACKEND (FastAPI + SQLAlchemy)                    │
│  12 endpoint modules, 9 services, 16 models                        │
│  Multi-tenant: tenant_id enforced on ALL CRUD operations            │
├─────────────────────────────────────────────────────────────────────┤
│  Services:                                                          │
│  ├── DocumentAnalysisEngine (3-pass AI pipeline)                    │
│  ├── MultiModalDocumentParser (PyMuPDF/pdfplumber/OCR)             │
│  ├── CodeAnalysisService (Gemini-powered code analysis)            │
│  ├── ValidationService (3-profile mismatch detection)              │
│  ├── CostService + BillingEnforcementService                       │
│  ├── CacheService (Redis) + LockService (distributed locks)       │
│  └── AnalysisRunService (run lifecycle tracking)                   │
├─────────────────────────────────────────────────────────────────────┤
│  Infrastructure: PostgreSQL 15 | Redis 7 | Celery | Flower         │
│  Docker Compose: 5 services + Nginx reverse proxy                  │
└─────────────────────────────────────────────────────────────────────┘
```

### What Exists But Is Unused (Sprint 3 Foundation)

These models were **created in Sprint 2 migrations but have NO CRUD, NO API endpoints, NO services:**

| Model | Table | Status | Sprint 3 Role |
|-------|-------|--------|----------------|
| `OntologyConcept` | `ontology_concepts` | Schema only | Core knowledge graph nodes |
| `OntologyRelationship` | `ontology_relationships` | Schema only | Knowledge graph edges |
| `Initiative` | `initiatives` | Schema only | Cross-system project grouping |
| `InitiativeAsset` | `initiative_assets` | Schema only | Initiative ↔ Document/Repo link |

The `_feed_to_business_ontology()` method in the DAE is a **placeholder** returning `True` — this is exactly where Sprint 3 plugs in.

---

## 2. SPRINT 3 TASK INVENTORY (From Planning Sheet)

### Mapping Sprint 3 Sheet to Implementation Tasks

| ID | Type | Task | Owner | Est. | Priority | Dependencies | Status |
|----|------|------|-------|------|----------|--------------|--------|
| DB-01 | DB | Ontology Schema (Tables) | BE1 | 4h | HIGH | Sprint 2 | Ready |
| FEAT-03 | Feature | Pass 4: Entity Extraction | BE1 | 10h | HIGH | DB-01 | Ready |
| FLAW-12-A | AI | Terminology Graph Builder | BE1 | 8h | CRITICAL | FEAT-03 | Blocked |
| FLAW-12-B | AI | Synonym Detection Logic | BE1 | 6h | CRITICAL | FLAW-12-A | Blocked |
| ARCH-04 | DB | CAE Schema (Code Analysis) | BE2 | 5h | HIGH | Sprint 2 | Ready |
| TASK-01 | Feature | Repo Agent Worker (Celery) | BE2 | 12h | HIGH | ARCH-04 | Blocked |
| AI-02 | AI | Static & Semantic Code Analysis | BE2 | 16h | HIGH | TASK-01 | Blocked |
| API-02 | API | Repo Onboarding API | BE2 | 6h | HIGH | TASK-01 | Blocked |
| FLAW-11-B | Fix | N+1 Query Fix (Phase 2) | BE1 | 6h | HIGH | None | Ready |
| UI-02 | UI | Real-Time Polling (Status) | FE | 6h | MED | FLAW-08-B | Blocked |
| BUG-01 | Bug | Mismatch Card Refresh Bug | FE | 4h | HIGH | None | Ready |
| BUG-02 | Bug | Upload Progress Bar Bug | FE | 3h | HIGH | None | Ready |
| CAE-03 | Bug | Multi-Column Doc Segmentation | BE1 | 8h | HIGH | FLAW-03 | Blocked |
| CAE-04 | Bug | Analysis Progress Update Bug | BE2 | 4h | MED | FLAW-08-B | Blocked |
| TESTING | Test | Ontology & CAE Integration Tests | BE1+BE2 | 14h | HIGH | All above | Blocked |
| CODE-REVIEW | Review | Code Review | Team | 8h | HIGH | All above | Blocked |
| DOCS-S3 | Docs | BOE & CAE Documentation | BE1 | 4h | MED | All above | Blocked |
| ADHOC | Buffer | Adhoc Tasks | Team | 10h | N/A | N/A | - |
| UI-DOC-01 | UI | DocumentAnalysisView Component | FE | 12h | HIGH | Sprint 1 | Ready |
| UI-DOC-02 | UI | Replace renderRawData with rich UI | FE | 6h | HIGH | UI-DOC-01 | Blocked |
| UI-DOC-03 | UI | Document type-specific renderers | FE | 8h | MED | UI-DOC-02 | Blocked |

### Known Bug Inventory (From Bug Report Sheet)

**Critical/High Severity (Sprint 3 relevant):**

| ID | Module | Issue | Impact | Resolution |
|----|--------|-------|--------|------------|
| A-01 | Backend/Architecture | Synchronous DAE blocks HTTP request | "Timer keeps elapsing" | Already fixed (Celery async) |
| BE-02 | Backend/Performance | N+1 queries in dashboard/segments | Slow at scale | **Sprint 3: FLAW-11-B** |
| FEAT-03 | AI/Logic | Empty Knowledge Graph — `_feed_to_business_ontology` is placeholder | BOE non-functional | **Sprint 3: FEAT-03** |
| ARCH-03 | Backend/State | Imprecise failure tracking — guesses which step failed | Wrong error in UI | **Sprint 3: CAE-04** |
| ARCH-02 | Backend/Data | No vector search (pgvector) for semantic queries | Blocks "Chat with Document" | **Future — Sprint 4** |

---

## 3. ARCHITECTURAL STRATEGY

### Core Principle: "Activate the Skeleton"

Sprint 2 created the **skeleton** (models exist in DB). Sprint 3 **activates it**:

```
Sprint 2 Created:          Sprint 3 Activates:
─────────────────          ───────────────────
OntologyConcept   ──────►  BusinessOntologyService
OntologyRelationship ────►  TerminologyGraphBuilder
Initiative  ─────────────►  InitiativeService + API
InitiativeAsset  ────────►  Cross-system governance
CodeComponent (basic) ───►  Agentic CAE (workers)
DAE placeholder  ────────►  Pass 4: Entity Extraction → BOE
```

### Dependency Graph (Critical Path)

```
Week 1: Foundation Layer (DB + Services)
═══════════════════════════════════════

  DB-01 (Ontology Schema)──►FEAT-03 (Pass 4)──►FLAW-12-A (Graph Builder)──►FLAW-12-B (Synonyms)
                                                          │
  ARCH-04 (CAE Schema)──►TASK-01 (Repo Agent)──►AI-02 (Code Analysis)
                                    │                     │
                                    └──►API-02 (Onboard)  │
                                                          │
  FLAW-11-B (N+1 Fix) ◄── Independent, can run parallel  │
                                                          │
Week 2: Integration + Polish                              ▼
═══════════════════════════════════
  UI-DOC-01 (View Component)──►UI-DOC-02 (Rich UI)──►UI-DOC-03 (Renderers)
  BUG-01 + BUG-02 (FE Fixes) ◄── Independent
  CAE-03 (Segmentation) + CAE-04 (Progress) ◄── After TASK-01
  TESTING──►CODE-REVIEW──►DOCS-S3
```

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gemini API rate limits (15 RPM) during entity extraction | HIGH | Delays Pass 4 | Batch entity extraction, use 4s throttle already in place |
| N+1 query fix cascades to breaking changes | MEDIUM | Frontend regressions | Write integration tests first, then refactor |
| Terminology graph quality depends on prompt engineering | HIGH | Poor synonym detection | Start with curated seed data, iterate prompts |
| Celery workers for code analysis may timeout on large repos | MEDIUM | Failed analysis | Set file-level timeouts, process in chunks |
| UI-DOC-01 scope creep — rich renderers can grow indefinitely | HIGH | Delays Week 2 | Timebox: 3 core renderers only (BRD, API, Code) |

---

## 4. DETAILED EXECUTION PLAN

### WEEK 1: FOUNDATION (Days 1–5)

---

#### DAY 1: Ontology Schema + CRUD + Pass 4 Entity Extraction Foundation

**Morning: DB-01 — Ontology Schema Activation (4h, BE1)**

The `OntologyConcept` and `OntologyRelationship` models already exist. What's missing:

1. **Create CRUD modules:**
   - `backend/app/crud/crud_ontology_concept.py`
     - `get_or_create(db, name, concept_type, tenant_id)` — Idempotent create
     - `search_by_name(db, query, tenant_id)` — Fuzzy name search
     - `get_by_type(db, concept_type, tenant_id)` — Filter by type
     - `get_with_relationships(db, concept_id, tenant_id)` — Eager load edges
   - `backend/app/crud/crud_ontology_relationship.py`
     - `create_if_not_exists(db, source_id, target_id, relationship_type, tenant_id)`
     - `get_by_concept(db, concept_id, tenant_id)` — All edges for a node
     - `get_graph(db, tenant_id, depth=2)` — BFS traversal up to N hops

2. **Create Pydantic schemas:**
   - `backend/app/schemas/ontology.py`
     - `OntologyConceptCreate`, `OntologyConceptResponse`, `OntologyConceptWithRelationships`
     - `OntologyRelationshipCreate`, `OntologyRelationshipResponse`
     - `OntologyGraphResponse` — Full graph with nodes + edges

3. **Register in `__init__.py` files** (both crud and schemas)

4. **Verify migration** — the tables should already exist from Sprint 2. If not, create a new Alembic migration.

**Afternoon: FEAT-03 Foundation — Entity Extraction Prompt Engineering (6h, BE1)**

1. **Add new prompt type to `prompt_manager.py`:**
   - `PromptType.ENTITY_EXTRACTION` — Prompt that instructs Gemini to extract named entities (actors, systems, features, technologies, business rules) from structured analysis results
   - Expected output schema: `{ "entities": [{ "name": str, "type": str, "context": str, "confidence": float }] }`

2. **Create `backend/app/services/business_ontology_service.py`:**
   - `BusinessOntologyService` class with:
     - `extract_entities_from_analysis(db, analysis_result_id, tenant_id)` — Sends structured_data to Gemini with entity extraction prompt
     - `get_or_create_concept(db, name, concept_type, tenant_id)` — Wraps CRUD with normalization (lowercase, strip)
     - `link_concepts(db, source_id, target_id, relationship_type, tenant_id)` — Creates edge if not exists
     - `ingest_entities(db, entities_list, document_id, tenant_id)` — Takes extracted entities, creates/links concepts

3. **Implement `_feed_to_business_ontology()` in analysis_service.py:**
   - Replace the placeholder with actual logic
   - After Pass 3 completes, iterate through all `AnalysisResult` records for the document
   - For each result, call `business_ontology_service.extract_entities_from_analysis()`
   - Call `business_ontology_service.ingest_entities()` to populate the graph
   - Track cost for this "Pass 4" in `_cost_tracker`

**Deliverables Day 1:**
- Ontology CRUD operational
- Entity extraction prompt engineered and tested
- `_feed_to_business_ontology()` implemented (no longer placeholder)

---

#### DAY 2: Terminology Graph + CAE Schema

**Morning: FLAW-12-A — Terminology Graph Builder (8h, BE1)**

1. **Extend `BusinessOntologyService`** with terminology-specific methods:
   - `build_terminology_graph(db, tenant_id)` — Aggregate all concepts, cluster by type
   - `find_related_terms(db, concept_name, tenant_id, depth=2)` — Graph traversal
   - `get_domain_vocabulary(db, tenant_id)` — All unique concept names for a tenant

2. **Add a Gemini prompt** for relationship inference:
   - `PromptType.RELATIONSHIP_INFERENCE` — Given two concepts and their contexts, infer relationship type
   - Relationship types: `implements`, `depends_on`, `is_part_of`, `is_synonym_of`, `conflicts_with`, `extends`, `validates`

3. **Implement automatic relationship creation:**
   - After entities are ingested, run a second AI pass that takes pairs of co-occurring entities (appeared in same document/segment) and infers relationships
   - Rate-limit: batch pairs, send max 5 per API call

**Afternoon: ARCH-04 — CAE Schema + Worker Foundation (5h, BE2)**

1. **Create new models** (or verify existing and extend):
   - `backend/app/models/repository.py` — Repository model:
     - `id`, `tenant_id`, `name`, `url`, `default_branch`, `last_analyzed_commit`
     - `analysis_status`, `total_files`, `analyzed_files`
     - `created_at`, `updated_at`
   - Assess if `CodeComponent` needs extension or if `Repository` is a new parent entity

2. **Create CRUD + schemas:**
   - `backend/app/crud/crud_repository.py`
   - `backend/app/schemas/repository.py`

3. **Set up Celery task structure:**
   - `backend/app/tasks/` directory (currently tasks.py is flat)
   - `backend/app/tasks/__init__.py` — re-export all tasks
   - `backend/app/tasks/document_tasks.py` — Move `process_document_pipeline` here
   - `backend/app/tasks/code_analysis_tasks.py` — New file for CAE workers

**Also: FLAW-11-B — N+1 Query Fix (6h, BE1 — can run parallel)**

1. **Identify N+1 hotspots:**
   - `GET /documents/{id}/segments` — Loads segments, then lazy-loads analysis_results per segment
   - `GET /validation/mismatches` — Loads mismatches, then lazy-loads document + code_component
   - Dashboard endpoints — Multiple separate queries for stats

2. **Fix with eager loading:**
   - Add `joinedload()` / `selectinload()` to CRUD queries
   - Specific fixes in `crud_document_segment.py`, `crud_mismatch.py`, `crud_document.py`
   - Add composite indexes where missing

**Deliverables Day 2:**
- Terminology graph builder operational
- Relationship inference prompt working
- CAE schema and task structure in place
- N+1 queries fixed with eager loading

---

#### DAY 3: Synonym Detection + Repo Agent Worker

**Morning: FLAW-12-B — Synonym Detection Logic (6h, BE1)**

1. **Add synonym detection to `BusinessOntologyService`:**
   - `detect_synonyms(db, tenant_id)` — Scans all concepts, finds potential synonyms
   - Uses Gemini with a specialized prompt: given a list of concept names, identify which ones are synonyms
   - Creates `is_synonym_of` relationships automatically
   - Merge strategy: keep the most-used term as "canonical", others as aliases

2. **Add concept normalization:**
   - Before creating a new concept, check for existing synonyms
   - If synonym found, link to canonical concept instead of creating duplicate

**Afternoon: TASK-01 — Repo Agent Worker (12h start, BE2)**

1. **Create `backend/app/tasks/code_analysis_tasks.py`:**
   - `static_analysis_worker(file_content, file_path)` — Uses tree-sitter (if available) or regex-based extraction for:
     - Functions/methods (name, params, return type)
     - Classes (name, methods, inheritance)
     - Imports/dependencies
     - Exports
   - `semantic_analysis_worker(file_content, static_analysis, tenant_id)` — Calls Gemini for:
     - Architectural role inference
     - Business logic summary
     - Pattern detection
   - `repo_agent_task(repo_id, file_paths, tenant_id)` — Orchestrator:
     - For each file: static → semantic → save to CodeComponent
     - Handles errors per-file (one failure doesn't kill the batch)
     - Updates Repository.analyzed_files count

2. **Create `backend/app/services/coordinator_service.py`:**
   - `CoordinatorService.enqueue_repo_analysis(repo_id, tenant_id, file_paths=None)`
   - `CoordinatorService.get_repo_status(repo_id, tenant_id)`
   - Manages Celery task lifecycle

**Deliverables Day 3:**
- Synonym detection operational
- Concept normalization prevents duplicates
- Repo agent worker processes files through 2-stage analysis
- Coordinator service manages task lifecycle

---

#### DAY 4: Ontology API + Repo Onboarding API + FE Bug Fixes

**Morning: Ontology & Initiative API Endpoints (6h, BE1)**

1. **Create `backend/app/api/endpoints/ontology.py`:**
   - `GET /ontology/concepts` — List all concepts (paginated, filterable by type)
   - `GET /ontology/concepts/{id}` — Single concept with relationships
   - `POST /ontology/concepts` — Manual concept creation
   - `GET /ontology/graph` — Full graph (nodes + edges) for visualization
   - `GET /ontology/search?q=term` — Search concepts by name
   - `DELETE /ontology/concepts/{id}` — Remove concept + cascade relationships

2. **Create `backend/app/api/endpoints/initiatives.py`:**
   - `POST /initiatives` — Create initiative
   - `GET /initiatives` — List initiatives
   - `GET /initiatives/{id}` — Initiative detail with assets
   - `POST /initiatives/{id}/assets` — Link document/repo to initiative
   - `DELETE /initiatives/{id}/assets/{asset_id}` — Unlink asset

3. **Register routers in `main.py`**

**Afternoon: API-02 — Repo Onboarding API (6h, BE2)**

1. **Create `backend/app/api/endpoints/repositories.py`:**
   - `POST /repositories` — Register a new repository (URL, branch)
   - `GET /repositories` — List repositories with analysis status
   - `GET /repositories/{id}` — Single repo with file analysis summary
   - `POST /repositories/{id}/analyze` — Trigger full repo analysis via coordinator
   - `DELETE /repositories/{id}` — Remove repo + linked code components

2. **Register router in `main.py`**

**Parallel FE Bug Fixes (BUG-01 + BUG-02, 7h total, FE)**

1. **BUG-01: Mismatch Card Refresh Bug (4h)**
   - Validation Panel doesn't refresh mismatches after scan completes
   - Fix: Add proper polling or WebSocket notification after validation scan
   - Update state management to trigger re-fetch

2. **BUG-02: Upload Progress Bar Bug (3h)**
   - Progress bar doesn't show during file upload
   - Fix: Implement XMLHttpRequest with progress event or axios onUploadProgress
   - Update document upload flow in documents page

**Deliverables Day 4:**
- Ontology API fully operational (6 endpoints)
- Initiative API operational (5 endpoints)
- Repository onboarding API operational (5 endpoints)
- FE: Mismatch refresh + upload progress bugs fixed

---

#### DAY 5: AI-02 (Semantic Code Analysis) + Integration Testing

**Full Day: AI-02 — Static & Semantic Code Analysis (16h start, BE2)**

1. **Enhance semantic analysis worker:**
   - Improve the Gemini code analysis prompt to extract:
     - Business rules embedded in code
     - API contracts (endpoints, request/response schemas)
     - Data model relationships
     - Security patterns (auth checks, input validation)
   - Add language-specific analysis templates for:
     - Python (FastAPI/Django patterns)
     - JavaScript/TypeScript (React/Next.js patterns)
     - Java (Spring Boot patterns)

2. **Implement delta analysis:**
   - Compare new analysis with previous analysis for same file
   - Store diff as `analysis_delta` in code component metadata
   - This is the foundation for continuous validation in future sprints

**Parallel: Integration Testing Foundation (BE1)**

1. **Write tests for new services:**
   - `tests/test_business_ontology_service.py` — Entity extraction, concept creation, relationship linking
   - `tests/test_ontology_crud.py` — CRUD operations with tenant isolation
   - `tests/test_ontology_api.py` — API endpoint tests
   - `tests/test_initiative_api.py` — Initiative CRUD tests

**Deliverables Day 5:**
- Semantic code analysis enhanced with business rule extraction
- Delta analysis foundation in place
- Integration test suite for ontology + initiative features

---

### WEEK 2: INTEGRATION + POLISH (Days 6–10)

---

#### DAY 6: UI-DOC-01 — DocumentAnalysisView Component (12h, FE)

**Full Day: Build the Rich Document Analysis View**

1. **Refactor `frontend/components/analysis/FileAnalysisView.tsx`:**
   - Currently renders code analysis only
   - Extend to handle document analysis structured_data

2. **Create `frontend/components/analysis/DocumentAnalysisView.tsx`:**
   - Receives segment analysis results
   - Renders structured data based on segment_type:
     - **BRD segments**: Requirements table with status indicators
     - **API segments**: Endpoint list with method badges
     - **Generic segments**: Key-value pairs with expandable details
   - Collapsible segment panels (already started in `[id]/page.tsx`)
   - Consolidated view toggle (calls `/analysis/document/{id}/consolidated`)

3. **Add visual indicators:**
   - Segment type badges with icons
   - Coverage indicators (analyzed vs total segments)
   - Entity count from ontology (if available)

**Deliverables Day 6:**
- DocumentAnalysisView component complete
- Handles BRD, API, and generic segment types
- Integrated into document detail page

---

#### DAY 7: UI-DOC-02 + UI-DOC-03 — Rich Renderers + Type-Specific Views

**Morning: UI-DOC-02 — Replace renderRawData (6h, FE)**

1. **Remove raw JSON display** from document detail page
2. **Implement structured renderers:**
   - Requirements renderer: table with columns (ID, Description, Priority, Status)
   - API endpoints renderer: card list with method, path, description
   - Business rules renderer: grouped list with conditions and actions
3. **Add export buttons** (JSON, copy to clipboard)

**Afternoon: UI-DOC-03 — Document Type-Specific Renderers (8h, FE)**

1. **BRD Renderer:** Full requirements traceability view
   - Requirement → Code Component mapping (uses DocumentCodeLink)
   - Status indicators (validated, unvalidated, mismatch)
2. **Technical Spec Renderer:** API documentation style
3. **Generic Renderer:** Fallback for unknown document types

**Parallel: CAE-03 — Multi-Column Document Segmentation Bug (8h, BE1)**

1. **Problem:** Documents with multi-column layouts get incorrectly segmented
2. **Fix in `document_parser.py`:**
   - Add column detection logic using pdfplumber's `extract_words()` with positional data
   - Merge columns before segmentation
3. **Fix in `analysis_service.py` Pass 2:**
   - Improve segmentation prompt to handle merged column text
   - Add validation: reject segments that overlap or have invalid char indices

**Deliverables Day 7:**
- Rich renderers replace raw JSON
- Type-specific views for BRD, Tech Spec, Generic
- Multi-column segmentation bug fixed

---

#### DAY 8: CAE-04 (Progress Bug) + UI-02 (Real-Time Polling) + Cross-System Wiring

**Morning: CAE-04 — Analysis Progress Update Bug (4h, BE2)**

1. **Problem:** Frontend shows stale progress during analysis
2. **Root cause:** `_pass_3_structured_extraction` updates progress but frontend polling may miss intermediate states
3. **Fix:**
   - Ensure `PASS_1_COMPOSITION`, `PASS_2_SEGMENTING`, `PASS_3_EXTRACTION` are set as document status
   - Add `current_step` and `steps_completed` fields to status response
   - Ensure atomicity of status updates (commit after each step)

**Morning: UI-02 — Real-Time Polling Enhancement (6h, FE)**

1. **Enhance `useDocumentProcessing` hook:**
   - Add exponential backoff (poll faster during active processing, slower when idle)
   - Add step-level progress (not just percentage)
   - Show current pass name in UI
2. **Add toast notifications** when analysis completes or fails
3. **Update Validation Panel** with scan progress polling

**Afternoon: Cross-System Wiring (4h, BE1+BE2)**

1. **Connect DAE → BOE → Validation:**
   - When a document is analyzed with `learning_mode=True`, entities flow to ontology
   - When validation runs, it can now query ontology for domain context
   - Add `initiative_id` parameter to `run_validation_scan` for cross-system validation

2. **Wire Repository → CodeComponent → Validation:**
   - When repo analysis completes, auto-create `CodeComponent` records
   - Link to existing `DocumentCodeLink` where possible

**Deliverables Day 8:**
- Analysis progress accurately reflected in UI
- Real-time polling enhanced with step-level detail
- DAE → BOE → Validation pipeline connected end-to-end

---

#### DAY 9: TESTING — Comprehensive Integration Tests (14h, BE1+BE2)

**Full Day: Test Suite**

1. **Backend Unit Tests:**
   - `test_business_ontology_service.py` — Entity extraction, concept CRUD, relationship linking, synonym detection
   - `test_coordinator_service.py` — Task enqueueing, status tracking
   - `test_repo_agent.py` — File analysis pipeline, error handling per file
   - `test_analysis_service_pass4.py` — End-to-end Pass 4 entity extraction

2. **Backend Integration Tests:**
   - `test_ontology_api.py` — Full API CRUD cycle with auth
   - `test_initiative_api.py` — Initiative creation, asset linking
   - `test_repository_api.py` — Repo onboarding, analysis trigger
   - `test_validation_with_ontology.py` — Validation using ontology context

3. **Frontend Smoke Tests:**
   - Document upload → analysis → view results flow
   - Validation scan → mismatch display → refresh flow
   - Ontology graph display (if frontend component built)

4. **Performance Tests:**
   - Verify N+1 fix with 50+ segments
   - Measure Pass 4 cost impact (should be < 20% increase)
   - Verify Celery worker memory usage with large repos

**Deliverables Day 9:**
- Test suite with >80% coverage on new Sprint 3 code
- All critical paths tested end-to-end
- Performance baselines established

---

#### DAY 10: CODE-REVIEW + DOCS + Buffer

**Morning: CODE-REVIEW (8h, Team)**

1. **Review checklist:**
   - Tenant isolation: All new CRUD uses `tenant_id`
   - Error handling: No unhandled exceptions in new services
   - API security: All new endpoints require authentication
   - Cost tracking: Pass 4 costs included in billing
   - SQL efficiency: No N+1 regressions
   - Prompt quality: Entity extraction + relationship inference prompts reviewed

**Afternoon: DOCS-S3 — Documentation (4h, BE1)**

1. **Update API documentation** (Swagger/OpenAPI annotations)
2. **Write service documentation:**
   - `BusinessOntologyService` — Entity extraction flow, concept types, relationship types
   - `CoordinatorService` — How to onboard repos, analysis lifecycle
   - `RepoAgent` — Worker architecture, error handling
3. **Update system architecture diagram** with new components

**Buffer: ADHOC (10h available)**
- Remaining bug fixes
- Prompt tuning based on test results
- Performance optimization if needed

**Deliverables Day 10:**
- All code reviewed and approved
- Documentation updated
- Sprint 3 ready for demo

---

## 5. FILE CREATION/MODIFICATION MAP

### New Files to Create

```
backend/app/
├── crud/
│   ├── crud_ontology_concept.py          (NEW)
│   ├── crud_ontology_relationship.py     (NEW)
│   ├── crud_initiative.py                (NEW)
│   ├── crud_initiative_asset.py          (NEW)
│   └── crud_repository.py               (NEW — if new model)
├── schemas/
│   ├── ontology.py                       (NEW)
│   ├── initiative.py                     (NEW)
│   └── repository.py                     (NEW — if new model)
├── services/
│   ├── business_ontology_service.py      (NEW)
│   └── coordinator_service.py            (NEW)
├── models/
│   └── repository.py                     (NEW — if needed beyond CodeComponent)
├── api/endpoints/
│   ├── ontology.py                       (NEW)
│   ├── initiatives.py                    (NEW)
│   └── repositories.py                   (NEW)
├── tasks/
│   ├── __init__.py                       (NEW — restructure)
│   ├── document_tasks.py                 (MOVE from tasks.py)
│   └── code_analysis_tasks.py            (NEW)
└── tests/
    ├── test_business_ontology_service.py (NEW)
    ├── test_ontology_api.py              (NEW)
    ├── test_initiative_api.py            (NEW)
    ├── test_repository_api.py            (NEW)
    └── test_coordinator_service.py       (NEW)

frontend/
├── components/analysis/
│   └── DocumentAnalysisView.tsx          (NEW)
└── (existing files modified)
```

### Files to Modify

```
backend/app/
├── crud/__init__.py                      (ADD new CRUD imports)
├── schemas/__init__.py                   (ADD new schema imports)
├── models/__init__.py                    (ADD Repository if new)
├── services/analysis_service.py          (IMPLEMENT _feed_to_business_ontology)
├── services/ai/prompt_manager.py         (ADD ENTITY_EXTRACTION, RELATIONSHIP_INFERENCE prompts)
├── services/validation_service.py        (ADD ontology context + initiative support)
├── services/code_analysis_service.py     (REFACTOR to use coordinator)
├── crud/crud_document_segment.py         (FIX N+1 with eager loading)
├── crud/crud_mismatch.py                 (FIX N+1 with eager loading)
├── tasks.py                              (REFACTOR — may keep or restructure)
├── main.py                               (ADD new routers)
└── requirements.txt                      (ADD tree-sitter if used)

frontend/
├── app/dashboard/documents/[id]/page.tsx (INTEGRATE DocumentAnalysisView)
├── app/dashboard/validation-panel/page.tsx (FIX refresh bug, add progress)
├── components/analysis/FileAnalysisView.tsx (EXTEND for document analysis)
├── hooks/useDocumentProcessing.ts        (ENHANCE polling)
└── lib/api.ts                            (ADD new endpoint methods)
```

---

## 6. SPRINT 3 DELIVERABLES CHECKLIST

| # | Deliverable | Acceptance Criteria |
|---|-------------|-------------------|
| 1 | Business Ontology Engine operational | Concepts + relationships created automatically during document analysis |
| 2 | Domain-specific terminology matching | Synonym detection finds and links related terms |
| 3 | Deep code analysis with tree-sitter AST | Static + semantic analysis produces structured code understanding |
| 4 | Repository agent for automated scanning | Celery worker processes entire repos file-by-file |
| 5 | Real-time status updates in UI | Frontend shows current pass, step count, and progress accurately |
| 6 | All document/code parsing bugs fixed | Multi-column segmentation, progress updates, N+1 queries resolved |
| 7 | Rich document analysis UI | Structured renderers replace raw JSON for BRD, API, generic types |
| 8 | Initiative & Ontology APIs | Full CRUD endpoints for governance layer |
| 9 | Integration test coverage >80% | All new services and endpoints tested |
| 10 | Documentation updated | API docs, service docs, architecture diagram |

---

## 7. SPRINT 3 RISKS & MITIGATIONS

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| 1 | Gemini rate limits (15 RPM) during Pass 4 entity extraction | HIGH | Schedule delays | Batch entities per segment (1 call per segment, not per entity). Keep 4s throttle. |
| 2 | tree-sitter installation complexity in Docker | MEDIUM | Blocks CAE | Fallback: regex-based AST extraction. Add tree-sitter as optional. |
| 3 | Synonym detection produces false positives | HIGH | Dirty ontology | Require confidence > 0.8. Admin review queue for new synonyms. |
| 4 | Pass 4 increases document analysis cost by >30% | MEDIUM | Billing complaints | Make learning_mode opt-in per analysis. Show estimated cost increase. |
| 5 | Multi-column fix breaks single-column documents | MEDIUM | Regression | Add column detection threshold. Test with both single and multi-column docs. |
| 6 | Frontend scope creep on rich renderers | HIGH | Delays testing | Strict timebox: 3 renderer types only. No custom styling beyond cards/tables. |

---

## 8. TEAM ALLOCATION

| Role | Person | Week 1 Focus | Week 2 Focus |
|------|--------|-------------|-------------|
| BE1 | Backend Engineer 1 | DB-01, FEAT-03, FLAW-12-A, FLAW-12-B, FLAW-11-B, Ontology API | CAE-03, Cross-system wiring, Testing, Docs |
| BE2 | Backend Engineer 2 | ARCH-04, TASK-01, AI-02, API-02, Repo API | CAE-04, Coordinator polish, Testing |
| FE | Frontend Engineer | BUG-01, BUG-02 | UI-DOC-01, UI-DOC-02, UI-DOC-03, UI-02 |

---

## 9. DEFINITION OF DONE

Each task is considered DONE when:

1. Code is written and passes linting (`black`, `isort`, `flake8`)
2. Unit/integration tests pass with >80% coverage on new code
3. API endpoints are documented in OpenAPI/Swagger
4. Multi-tenancy is enforced (tenant_id on all CRUD operations)
5. Error handling follows existing patterns (`AIAnalysisException`, `DocumentProcessingException`)
6. Cost tracking is implemented for any new Gemini API calls
7. Code review is completed by at least one other team member
8. No N+1 query regressions (verified with SQL logging)

---

## 10. DAILY STANDUP CHECKPOINTS

| Day | Expected State |
|-----|---------------|
| Day 1 EOD | Ontology CRUD works. Entity extraction prompt tested. `_feed_to_business_ontology()` no longer placeholder. |
| Day 2 EOD | Terminology graph builder works. CAE schema in place. N+1 queries fixed. |
| Day 3 EOD | Synonym detection works. Repo agent processes files through Celery. |
| Day 4 EOD | All 3 new API modules registered and working. FE bugs fixed. |
| Day 5 EOD | Semantic code analysis enhanced. First integration tests passing. |
| Day 6 EOD | DocumentAnalysisView component renders all segment types. |
| Day 7 EOD | Rich renderers replace raw JSON. Multi-column bug fixed. |
| Day 8 EOD | Progress tracking works end-to-end. DAE → BOE → Validation pipeline connected. |
| Day 9 EOD | Full test suite passing. Performance baselines established. |
| Day 10 EOD | Code reviewed. Docs updated. Sprint 3 demo-ready. |
