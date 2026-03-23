# Sprint 3: Business Ontology Engine & Code Analysis - COMPLETE

**Duration:** ~280 hours (Sprint 3 Core + ADHOC Phase 1 + ADHOC Phase 2)
**Status:** 100% COMPLETE
**Branch:** `claude/dokydoc-evolution-guide-49riQ`
**Final Commit:** `086d70b`
**Last Updated:** 2026-02-18

---

## Executive Summary

Sprint 3 transformed DokyDoc from a document analysis platform into a **full-stack knowledge graph + code intelligence system** with:

- **Business Ontology Engine (BOE)** - Two separate knowledge graphs (document + code) with 3-tier algorithmic cross-graph mapping
- **Enhanced Code Analysis** - Semantic code analysis with delta detection, multi-language support, and dual-AI-provider routing
- **Cross-Graph Architecture** - ConceptMapping table linking document and code ontologies with human-reviewable mappings
- **Repository Management** - Full repo onboarding, file discovery, and Celery-powered async analysis
- **Rich UI** - Ontology dashboard with graph visualization, cross-graph views, gap analysis, and mapping review panels
- **Dual AI Providers** - Google Gemini for documents + Anthropic Claude for code analysis (configurable via ProviderRouter)
- **Git Webhooks** - Auto-trigger incremental analysis on push events
- **56+ New Tests** - Comprehensive integration test coverage across all new features
- **12 User-Reported Issues Fixed** - JWT expiry, billing, timing, ontology, export

---

## Sprint 3 Final Metrics

### Code Statistics
- **Commits:** 29
- **Files Changed:** 97 (58 new, 38 modified, 1 renamed)
- **Lines Added:** 17,195+
- **Lines Removed:** 1,360
- **Net New Lines:** +15,835
- **New Backend Services:** 7
- **New API Endpoint Modules:** 4 (with 27+ individual endpoints)
- **New Models:** 2 (ConceptMapping, Repository)
- **New Alembic Migrations:** 9
- **New Integration Tests:** 11 files (56+ test cases)
- **New Frontend Components:** 9

### Test Coverage
- **New Test Files:** 11
- **Total Test Files:** 22
- **Sprint 3 Test Cases:** 56+
- **Areas Covered:** BOE, mapping service, context assembly, ontology CRUD, ontology API, initiative API, repository API, N+1 queries, multi-column PDF, Sprint 4 ADHOC features

---

## Architecture Overview (End of Sprint 3)

### System Architecture

```
+---------------------------------------------------------------------+
|                      FRONTEND (Next.js 15)                           |
|  React 19 + Radix UI + Tailwind CSS                                 |
|  Pages: Login, Register, Role-Select, Dashboard (6 role views),     |
|         Documents, Code, Validation, Tasks, Billing, Settings,      |
|         Ontology (NEW), Cross-Graph View (NEW)                      |
+-----------------------------+---------------------------------------+
                              | REST API (Bearer JWT, 8h expiry)
+-----------------------------v---------------------------------------+
|                   BACKEND (FastAPI + SQLAlchemy)                      |
|  15 endpoint modules, 13 services, 19 models                        |
|  Multi-tenant: tenant_id enforced on ALL CRUD operations             |
+---------------------------------------------------------------------+
|  Services:                                                           |
|  +-- DocumentAnalysisEngine (3-pass AI pipeline + Pass 4 BOE)       |
|  +-- MultiModalDocumentParser (PyMuPDF/pdfplumber/OCR + columns)    |
|  +-- CodeAnalysisService (semantic analysis + delta detection)       |
|  +-- BusinessOntologyService (3-pass BOE: extract, build, enrich)   |
|  +-- MappingService (3-tier: exact, fuzzy, AI validation)           |
|  +-- ContextAssemblyService (BOE context envelopes, ~3-5K tokens)   |
|  +-- CoordinatorService (cross-service orchestration)               |
|  +-- ValidationService (3-profile mismatch detection)               |
|  +-- CostService + BillingEnforcementService                        |
|  +-- CacheService (Redis) + LockService (distributed locks)         |
|  +-- AnalysisRunService (run lifecycle tracking)                    |
|  +-- AI Providers:                                                   |
|      +-- GeminiService (document analysis, entity extraction)        |
|      +-- AnthropicService (code analysis — Claude API)               |
|      +-- ProviderRouter (intelligent routing: docs->Gemini,          |
|          code->Claude)                                               |
+---------------------------------------------------------------------+
|  Infrastructure: PostgreSQL 15 | Redis 7 | Celery | Flower          |
|  Docker Compose: 5 services + Nginx reverse proxy                    |
+---------------------------------------------------------------------+
```

### Pipeline Architecture

```
DOCUMENT PIPELINE:
  Upload -> Parse (4 strategies + OCR + column detection)
    -> DAE Pass 1: Composition Analysis
    -> DAE Pass 2: Segmentation
    -> DAE Pass 3: Structured Extraction
    -> Pass 4: Entity Extraction -> BOE Enrichment (Celery async)

CODE PIPELINE:
  Repo Onboard -> File Discovery -> Filter (language support)
    -> Enhanced Semantic Analysis (AI-02, per-file with rate limiting)
    -> Delta Detection (compare with previous analysis)
    -> Code Ontology Extraction (inline, no extra AI calls)
    -> Cost/Duration Tracking

CROSS-GRAPH MAPPING:
  Document Graph  <-->  ConceptMapping Table  <-->  Code Graph
  3-tier algorithm:
    Tier 1: Exact match ($0)      -- normalized name equality
    Tier 2: Fuzzy match ($0)      -- token overlap + Levenshtein distance
    Tier 3: AI validation ($0.001/pair) -- only ambiguous pairs
  Cost: ~$0.05/run vs $2-5/run (97% savings)

CONTEXT ASSEMBLY:
  ContextEnvelope = Previous Analysis + BOE Concepts + Mapped Docs + Neighbor Summaries
  ~3,000-5,000 tokens per envelope, $0 (all DB queries)
```

### Two-Graph Architecture (Key Innovation)

```
+-------------------+          +-------------------+
|  DOCUMENT GRAPH   |          |    CODE GRAPH     |
|  (source: doc)    |          |  (source: code)   |
+-------------------+          +-------------------+
| OntologyConcept   |          | OntologyConcept   |
| - "Payment Flow"  |          | - "PaymentService"|
| - "User Auth"     |   LINK   | - "AuthMiddleware"|
| - "Order Process" |<-------->| - "OrderHandler"  |
+-------------------+   via    +-------------------+
                    ConceptMapping
                    (explicit, auditable,
                     human-reviewable)
```

---

## Sprint 3 Task Completion Summary

### Week 1 (Days 1-5): Foundation

| Day | Task IDs | What Was Done |
|-----|----------|---------------|
| Day 1 | DB-01, FEAT-03 | Ontology CRUD (concepts + relationships), Entity extraction prompt, `_feed_to_business_ontology()` implemented, Initiative governance |
| Day 2 | FLAW-12-A, ARCH-04 | Code Analysis Engine, Coordinator service, Ontology status tracking, Bug fixes |
| Day 3 | FLAW-12-B, TASK-01 | Frontend UI overhaul, CoordinatorService, Synonym detection, Repo agent worker |
| Day 4 | Ontology API, API-02, BUG-01, BUG-02 | Ontology Dashboard UI, Validation refresh fix, Upload progress fix |
| Day 5 | AI-02, TESTING | Enhanced Semantic Code Analysis with delta detection, 50+ integration tests |

### ADHOC Phase 1: Cost-Optimized Architecture

| ADHOC | Description | Status |
|-------|-------------|--------|
| ADHOC-03 | Replace AI reconciliation with algorithmic mapping | DONE |
| ADHOC-04 | ConceptMapping model + CRUD + schema + migration | DONE |
| ADHOC-05 | MappingService (3-tier: exact, fuzzy, AI fallback) | DONE |
| ADHOC-06 | ContextAssemblyService (context envelopes from BOE) | DONE |

**Key Achievement:** Reduced cross-graph mapping cost from $2-5/run (AI) to ~$0.05/run (97% savings).

### Week 2 (Days 6-10): Integration & Polish

| Day | Task IDs | What Was Done |
|-----|----------|---------------|
| Day 6 | UI-DOC-01 | DocumentAnalysisView with BRD/API/generic renderers |
| Day 7 | UI-DOC-02, UI-DOC-03, CAE-03 | Rich renderers, type-specific views, multi-column PDF fix |
| Day 8 | CAE-04, UI-02, Cross-wiring | Progress tracking, polling, DAE-BOE-Validation pipeline |
| Day 9 | TESTING | 56+ new tests (concept mapping, mapping service, context assembly, N+1, parser) |
| Day 10 | CODE-REVIEW | All critical areas pass (tenant isolation, API security, error handling, cost tracking, SQL efficiency) |

### ADHOC Phase 2 (Sprint 4 Early Delivery)

| ADHOC | Description | Status |
|-------|-------------|--------|
| ADHOC-07 | Claude API integration (AnthropicService) | DONE |
| ADHOC-08 | ProviderRouter (dual-provider: Claude for code, Gemini for docs) | DONE |
| ADHOC-09 | Git webhook pipeline (auto-trigger on push) | DONE |

### Post-Sprint Fixes (12 User-Reported Issues)

| Issue | Fix |
|-------|-----|
| JWT token expiry too short | Increased to 8h, added auto-refresh on 401 |
| Billing not tracking ontology costs | Added usage_log entries for BOE extraction |
| Code analysis timing not displayed | Added cost + duration columns to UI |
| Ontology missing code-layer concepts | Inline extraction from structured_analysis |
| Cross-graph view not scrollable | Fixed CrossGraphView layout |
| CSV export missing for requirements | Added CSV download to documents page |
| Registration UX issues | Fixed form validation and error handling |
| Gemini JSON parsing failures | Strip markdown fences from AI responses |
| GitHub URL not resolving for code | Added GitHub URL resolver |
| Cost columns missing from DB | Catch-up migration (s3a5) |
| Repository ID column missing | Catch-up migration (s3a3) |
| Analysis timing not recorded | Added s3a6 migration for timing fields |

---

## New Backend Components

### Services (7 New)

| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| BusinessOntologyService | `services/business_ontology_service.py` | 550 | 3-pass BOE pipeline: entity extraction from docs/code, concept creation, relationship linking |
| MappingService | `services/mapping_service.py` | 521 | 3-tier cross-graph mapping (exact/fuzzy/AI) |
| ContextAssemblyService | `services/context_assembly_service.py` | 340 | Builds ~3-5K token envelopes from BOE for AI calls |
| CoordinatorService | `services/coordinator_service.py` | 172 | Orchestrates multi-step analysis workflows |
| AnthropicService | `services/ai/anthropic.py` | 204 | Claude API wrapper for code analysis |
| ProviderRouter | `services/ai/provider_router.py` | 186 | Intelligent routing: docs -> Gemini, code -> Claude |
| CodeAnalysisService (enhanced) | `services/code_analysis_service.py` | 359+ | Semantic analysis + delta detection + cost tracking |

### API Endpoints (4 New Modules, 27+ Endpoints)

**Ontology API** (`/api/v1/ontology`):
```
GET    /concepts              - List concepts (filtered by type, source_type)
GET    /concepts/{id}         - Single concept with relationships
POST   /concepts              - Create concept
PUT    /concepts/{id}         - Update concept
DELETE /concepts/{id}         - Delete concept + cascade
GET    /graph                 - Full graph (nodes + edges)
GET    /search?q=term         - Search concepts
POST   /extract-code-concepts - Backfill code ontology from existing analyses
GET    /mappings              - List cross-graph mappings
POST   /mappings              - Create mapping manually
PUT    /mappings/{id}         - Update mapping (approve/reject)
DELETE /mappings/{id}         - Delete mapping
POST   /mappings/auto         - Trigger algorithmic mapping
GET    /mappings/stats        - Mapping coverage statistics
GET    /gap-analysis          - Unmapped concept gap analysis
```

**Repository API** (`/api/v1/repositories`):
```
POST   /                      - Register repository
GET    /                      - List repositories with status
GET    /{id}                  - Repository detail with file summary
POST   /{id}/analyze          - Trigger full analysis via Celery
DELETE /{id}                  - Remove repo + linked components
```

**Initiative API** (`/api/v1/initiatives`):
```
POST   /                      - Create initiative
GET    /                      - List initiatives
GET    /{id}                  - Initiative detail with assets
POST   /{id}/assets           - Link document/repo to initiative
DELETE /{id}/assets/{asset_id} - Unlink asset
```

**Webhook API** (`/api/v1/webhooks`):
```
POST   /github                - GitHub push webhook (auto-triggers incremental analysis)
```

### Models (2 New)

| Model | Table | Key Fields |
|-------|-------|------------|
| ConceptMapping | `concept_mappings` | source_concept_id, target_concept_id, mapping_type (exact/fuzzy/ai), confidence, status (pending/approved/rejected) |
| Repository | `repositories` | tenant_id, name, url, default_branch, last_analyzed_commit, analysis_status, total_files, analyzed_files |

### Enhanced Models

| Model | Changes |
|-------|---------|
| CodeComponent | Added: `analysis_cost`, `analysis_duration`, `analysis_delta`, `repository_id` FK |
| OntologyConcept | Added: `source_type` (document/code), `source_id` |

### Celery Tasks (3 New + 1 Restructured)

| Task File | Tasks | Purpose |
|-----------|-------|---------|
| `tasks/document_pipeline.py` | `process_document_pipeline` | 3-pass DAE + Pass 4 BOE enrichment |
| `tasks/code_analysis_tasks.py` | `analyze_repository`, `analyze_single_file` | Semantic code analysis with dual-provider routing |
| `tasks/ontology_tasks.py` | `extract_ontology`, `run_cross_graph_mapping`, `extract_code_concepts` | Ontology extraction + mapping |

### Alembic Migrations (9 New)

| Migration | Purpose |
|-----------|---------|
| `merge_s2_s3_merge_heads` | Merge Sprint 2 + Sprint 3 Alembic heads |
| `s3a1` | Repository table creation |
| `s3a2` | ConceptMapping table creation |
| `s3a3` | Fix repository_id column (catch-up) |
| `s3a4` | Code cost tracking columns on code_components |
| `s3a5` | Fix cost columns (catch-up) |
| `s3a6` | Analysis timing columns |
| `s3b1` | source_type column on ontology concepts |
| `s3d5` | Delta detection fields on code_components |

---

## New Frontend Components

### Ontology Dashboard (`/dashboard/ontology`)

Full ontology management page with:
- **Layer Tabs:** All / Document / Code — filter concepts by source_type
- **Scrollable Table View:** All concepts with type badges, relationship counts
- **Graph Visualization:** Interactive D3-based ontology graph
- **CRUD Dialogs:** Create/edit concepts and relationships
- **Source Type Badges:** Visual distinction between document and code concepts

### Two-Graph UI Components (6 New)

| Component | Lines | Purpose |
|-----------|-------|---------|
| `CrossGraphView.tsx` | 257 | Side-by-side document and code graph visualization |
| `MappingReviewPanel.tsx` | 244 | Review, approve, or reject cross-graph mappings |
| `GapAnalysis.tsx` | 196 | Show unmapped concepts in both graphs |
| `ConceptDetail.tsx` | 370 | Detailed concept view with relationships |
| `ConceptDialog.tsx` | 182 | Create/edit concept modal |
| `RelationshipDialog.tsx` | 267 | Create/edit relationship modal |
| `ConceptPanel.tsx` | 176 | Concept list with filtering |
| `OntologyGraph.tsx` | 395 | D3-based force-directed graph rendering |

### Analysis Views (Enhanced)

| Component | Changes |
|-----------|---------|
| `DocumentAnalysisView.tsx` | NEW: Full document analysis detail with segment renderers |
| `RepositoryAnalysisView.tsx` | Enhanced: Cost + Duration columns, cost summary card |
| `DynamicAnalysisView.tsx` | Enhanced: Role-based + document-type adaptive views |

### Other Frontend Enhancements

- **JWT:** 8-hour expiry with automatic refresh on 401
- **Code Page:** Cost and Duration columns in analysis table
- **Documents Page:** CSV export for requirements
- **Sidebar:** Ontology navigation link
- **Billing:** Ontology extraction costs visible in analytics

---

## Integration Test Suite

### Test Files (11 New, 56+ Cases)

| Test File | Cases | Coverage Area |
|-----------|-------|---------------|
| `test_business_ontology_service.py` | 8 | BOE entity extraction, concept creation, relationship linking |
| `test_concept_mapping_crud.py` | 12 | ConceptMapping CRUD with tenant isolation |
| `test_context_assembly.py` | 8 | Context envelope assembly from BOE |
| `test_mapping_service.py` | 10 | 3-tier mapping (exact, fuzzy, AI validation) |
| `test_ontology_crud.py` | 9 | Ontology concept/relationship CRUD |
| `test_ontology_api.py` | 6 | Ontology REST API endpoints |
| `test_initiative_api.py` | 5 | Initiative CRUD API |
| `test_repository_api.py` | 7 | Repository management API |
| `test_n1_query_fix.py` | 3 | N+1 query prevention verification |
| `test_document_parser_columns.py` | 4 | Multi-column PDF parsing |
| `test_sprint4_adhoc.py` | 8 | AnthropicService, ProviderRouter, webhook endpoint |

---

## Complete File Inventory

### New Files Created (58)

```
backend/app/
+-- api/endpoints/
|   +-- initiatives.py              (186 lines)
|   +-- ontology.py                 (585 lines)
|   +-- repositories.py            (247 lines)
|   +-- webhooks.py                (204 lines)
+-- crud/
|   +-- crud_concept_mapping.py    (223 lines)
|   +-- crud_initiative.py         (69 lines)
|   +-- crud_initiative_asset.py   (86 lines)
|   +-- crud_ontology_concept.py   (180 lines)
|   +-- crud_ontology_relationship.py (155 lines)
|   +-- crud_repository.py         (113 lines)
+-- models/
|   +-- concept_mapping.py         (80 lines)
|   +-- repository.py              (50 lines)
+-- schemas/
|   +-- concept_mapping.py         (66 lines)
|   +-- initiative.py              (59 lines)
|   +-- ontology.py                (100 lines)
|   +-- repository.py              (82 lines)
+-- services/
|   +-- ai/__init__.py             (13 lines)
|   +-- ai/anthropic.py            (204 lines)
|   +-- ai/provider_router.py      (186 lines)
|   +-- business_ontology_service.py (550 lines)
|   +-- context_assembly_service.py (340 lines)
|   +-- coordinator_service.py     (172 lines)
|   +-- mapping_service.py         (521 lines)
+-- tasks/
|   +-- __init__.py                (10 lines)
|   +-- code_analysis_tasks.py     (470 lines)
|   +-- ontology_tasks.py          (246 lines)
+-- tests/
    +-- test_business_ontology_service.py (244 lines)
    +-- test_concept_mapping_crud.py      (332 lines)
    +-- test_context_assembly.py          (244 lines)
    +-- test_document_parser_columns.py   (137 lines)
    +-- test_initiative_api.py            (169 lines)
    +-- test_mapping_service.py           (286 lines)
    +-- test_n1_query_fix.py              (88 lines)
    +-- test_ontology_api.py              (209 lines)
    +-- test_ontology_crud.py             (371 lines)
    +-- test_repository_api.py            (251 lines)
    +-- test_sprint4_adhoc.py             (423 lines)

alembic/versions/
+-- merge_s2_s3_merge_heads.py
+-- s3a1_sprint3_repository_table.py
+-- s3a2_concept_mapping_table.py
+-- s3a3_fix_repository_id_column.py
+-- s3a4_code_cost_tracking.py
+-- s3a5_fix_cost_columns.py
+-- s3a6_add_analysis_timing.py
+-- s3b1_add_source_type_to_ontology.py
+-- s3d5_add_delta_analysis_fields.py

frontend/
+-- app/dashboard/ontology/page.tsx      (883 lines)
+-- components/analysis/DocumentAnalysisView.tsx (604 lines)
+-- components/ontology/ConceptDetail.tsx     (370 lines)
+-- components/ontology/ConceptDialog.tsx     (182 lines)
+-- components/ontology/ConceptPanel.tsx      (176 lines)
+-- components/ontology/CrossGraphView.tsx    (257 lines)
+-- components/ontology/GapAnalysis.tsx       (196 lines)
+-- components/ontology/MappingReviewPanel.tsx (244 lines)
+-- components/ontology/OntologyGraph.tsx     (395 lines)
+-- components/ontology/RelationshipDialog.tsx (267 lines)

docs/
+-- MANUAL_TESTING_GUIDE.md              (1,361 lines)
```

### Key Modified Files (38)

```
backend/app/
+-- services/ai/prompt_manager.py      (+758 lines - code analysis, ontology, delta prompts)
+-- services/code_analysis_service.py  (+359 lines - full engine with delta detection)
+-- services/ai/gemini.py              (+179 lines - cost tracking, multi-model)
+-- services/document_parser.py        (+81 lines - multi-column PDF)
+-- services/analysis_service.py       (+51 lines - N+1 fix, coordinator)
+-- models/code_component.py           (+48 lines - cost, timing, delta columns)
+-- main.py                            (+33 lines - 4 new router registrations)
+-- crud/__init__.py                   (+12 lines - 6 new CRUD registrations)
+-- schemas/__init__.py                (+23 lines - new schema registrations)
+-- core/config.py                     (+17 lines - Anthropic API key, provider config)
+-- worker.py                          (+6 lines - new task module imports)
+-- requirements.txt                   (+1 line - anthropic package)

frontend/
+-- components/analysis/RepositoryAnalysisView.tsx (+311 lines - cost display)
+-- hooks/useDocumentProcessing.ts     (+160 lines - upload progress, refresh)
+-- app/dashboard/code/page.tsx        (+88 lines - enhancements)
+-- lib/api.ts                         (+64 lines - ontology, mapping, repo APIs)
+-- app/dashboard/documents/page.tsx   (+69 lines - CSV export)
+-- contexts/AuthContext.tsx           (+5 lines - JWT 8h, auto-refresh)
+-- components/layout/Sidebar.tsx      (+8 lines - ontology nav)
```

---

## API Reference (All 15 Endpoint Modules)

### Authentication
```
POST /api/v1/login/access-token       - JWT authentication
POST /api/v1/login/refresh-token      - Token refresh
POST /api/v1/register                 - User registration
```

### Tenant Management
```
POST /api/v1/tenants/register         - Register new tenant
GET  /api/v1/tenants/me               - Get current tenant
PUT  /api/v1/tenants/me               - Update tenant settings
```

### User Management
```
GET  /api/v1/users/me                 - Current user profile
GET  /api/v1/users                    - List tenant users
POST /api/v1/users/invite             - Invite new users
PUT  /api/v1/users/{id}/roles         - Manage roles
DELETE /api/v1/users/{id}             - Remove user
```

### Documents
```
POST /api/v1/documents/upload         - Upload document
GET  /api/v1/documents                - List documents
GET  /api/v1/documents/{id}           - Document details
POST /api/v1/documents/{id}/analyze   - Trigger analysis
GET  /api/v1/documents/{id}/analysis  - Get full analysis
```

### Code Components
```
GET  /api/v1/code-components          - List code components
GET  /api/v1/code-components/{id}     - Component details
POST /api/v1/code-components          - Create component
PUT  /api/v1/code-components/{id}     - Update component
DELETE /api/v1/code-components/{id}   - Delete component
```

### Ontology (Sprint 3 NEW)
```
GET    /api/v1/ontology/concepts              - List concepts
GET    /api/v1/ontology/concepts/{id}         - Concept detail
POST   /api/v1/ontology/concepts              - Create concept
PUT    /api/v1/ontology/concepts/{id}         - Update concept
DELETE /api/v1/ontology/concepts/{id}         - Delete concept
GET    /api/v1/ontology/graph                 - Full graph
GET    /api/v1/ontology/search                - Search concepts
POST   /api/v1/ontology/extract-code-concepts - Backfill extraction
GET    /api/v1/ontology/mappings              - List mappings
POST   /api/v1/ontology/mappings              - Create mapping
PUT    /api/v1/ontology/mappings/{id}         - Update mapping
DELETE /api/v1/ontology/mappings/{id}         - Delete mapping
POST   /api/v1/ontology/mappings/auto         - Auto-map
GET    /api/v1/ontology/mappings/stats        - Coverage stats
GET    /api/v1/ontology/gap-analysis          - Gap analysis
```

### Initiatives (Sprint 3 NEW)
```
POST   /api/v1/initiatives                    - Create initiative
GET    /api/v1/initiatives                    - List initiatives
GET    /api/v1/initiatives/{id}               - Initiative detail
POST   /api/v1/initiatives/{id}/assets        - Link asset
DELETE /api/v1/initiatives/{id}/assets/{aid}  - Unlink asset
```

### Repositories (Sprint 3 NEW)
```
POST   /api/v1/repositories                   - Register repository
GET    /api/v1/repositories                   - List repositories
GET    /api/v1/repositories/{id}              - Repository detail
POST   /api/v1/repositories/{id}/analyze      - Trigger analysis
DELETE /api/v1/repositories/{id}              - Delete repository
```

### Webhooks (Sprint 4 ADHOC-09)
```
POST   /api/v1/webhooks/github                - GitHub push webhook
```

### Billing & Analytics
```
GET  /api/v1/billing/current                  - Current cost summary
GET  /api/v1/billing/usage                    - Usage statistics
GET  /api/v1/billing/analytics                - Full dashboard
GET  /api/v1/billing/analytics/by-feature     - By feature type
GET  /api/v1/billing/analytics/by-operation   - By operation
GET  /api/v1/billing/analytics/trends         - Time series
GET  /api/v1/billing/analytics/top-documents  - Top costly docs
GET  /api/v1/billing/analytics/users          - All users breakdown
GET  /api/v1/billing/analytics/users/{id}     - Single user
POST /api/v1/billing/balance/topup            - Add balance
PUT  /api/v1/billing/settings                 - Update settings
```

### Validation, Tasks, Dashboard, Analysis, Links
```
POST /api/v1/validation/scan                  - Run validation scan
GET  /api/v1/validation/mismatches            - List mismatches
GET  /api/v1/tasks                            - List tasks (Kanban)
POST /api/v1/tasks                            - Create task
GET  /api/dashboard                           - Role-based dashboard
GET  /api/v1/analysis/document/{id}/consolidated - Consolidated view
```

---

## Database Models (19 Total)

| Model | Table | Sprint | Purpose |
|-------|-------|--------|---------|
| User | users | S1 | User accounts with roles |
| Tenant | tenants | S2 | Multi-tenant organizations |
| TenantBilling | tenant_billing | S2 | Billing config per tenant |
| UsageLog | usage_logs | S2 | AI cost tracking per operation |
| Document | documents | S1 | Uploaded documents |
| DocumentSegment | document_segments | S1 | Document segments from analysis |
| AnalysisResult | analysis_results | S1 | AI analysis structured output |
| AnalysisRun | analysis_runs | S2 | Analysis run lifecycle |
| ConsolidatedAnalysis | consolidated_analyses | S1 | Consolidated document analysis |
| CodeComponent | code_components | S1 | Code files/modules with analysis |
| DocumentCodeLink | document_code_links | S1 | Document-to-code relationships |
| Mismatch | mismatches | S1 | Validation discrepancies |
| Task | tasks | S2 | Kanban task management |
| OntologyConcept | ontology_concepts | S3 | Knowledge graph nodes |
| OntologyRelationship | ontology_relationships | S3 | Knowledge graph edges |
| Initiative | initiatives | S3 | Cross-system project grouping |
| InitiativeAsset | initiative_assets | S3 | Initiative-to-asset links |
| Repository | repositories | S3 | Git repository tracking |
| ConceptMapping | concept_mappings | S3 | Cross-graph mapping links |

---

## Key Design Decisions

### 1. Two Separate Graphs (Not Merged)
- Document concepts and code concepts stay in separate ontology layers
- `source_type` field distinguishes them ("document" vs "code")
- Avoids concept collision and preserves domain-specific terminology
- ConceptMapping table provides explicit, auditable links

### 2. 3-Tier Algorithmic Mapping (Not AI-Only)
- Tier 1 (Exact): Normalized name equality — $0
- Tier 2 (Fuzzy): Token overlap + Levenshtein distance — $0
- Tier 3 (AI): Gemini validation for ambiguous pairs — ~$0.001/pair
- Total cost: ~$0.05/run vs $2-5/run with pure AI approach (97% savings)

### 3. Inline Code Ontology Extraction
- Extract concepts directly from code analysis `structured_analysis` JSON
- No extra AI calls needed — parse the existing analysis output
- Classes, functions, patterns become code-layer ontology concepts

### 4. Dual-Provider AI Architecture
- Gemini: Document analysis (3-pass pipeline, entity extraction)
- Claude: Code analysis (better at understanding code patterns)
- ProviderRouter: Configurable routing with fallback

### 5. Context Assembly from BOE
- Build ~3-5K token envelopes from existing DB data
- Include: previous analysis, related concepts, mapped documents, neighbor summaries
- $0 cost (all database queries, no AI calls)
- Improves AI analysis quality with domain context

---

## RBAC System (6 Roles)

| Role | Permissions | Dashboard |
|------|------------|-----------|
| CXO | Full admin (all 25+ permissions) | Executive overview |
| Admin | Operations (users, billing, org) | Admin dashboard |
| Developer | Code + analysis (15 perms) | Developer dashboard |
| BA | Documents + validation (14 perms) | BA dashboard |
| Product Manager | Product features (10 perms) | PM dashboard |
| Auditor | Read-only compliance (12 perms) | Audit dashboard |

---

## Sprint 3 Deliverables Checklist

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Business Ontology Engine operational (3-pass: extract, build, enrich) | DONE |
| 2 | Domain-specific terminology matching (synonym detection) | DONE |
| 3 | Deep code analysis with semantic extraction + delta detection | DONE |
| 4 | Repository agent for automated scanning (Celery workers) | DONE |
| 5 | Real-time status updates in UI (polling, progress tracking) | DONE |
| 6 | Multi-column PDF + N+1 query bugs fixed | DONE |
| 7 | Rich document analysis UI (BRD, API, generic renderers) | DONE |
| 8 | Initiative & Ontology APIs (27+ endpoints) | DONE |
| 9 | Integration test coverage (56+ tests across 11 files) | DONE |
| 10 | Code review complete (tenant isolation, security, cost tracking) | DONE |
| 11 | Two-Graph Architecture with algorithmic mapping (ADHOC Phase 1) | DONE |
| 12 | Cross-graph UI (visualization, review panel, gap analysis) | DONE |
| 13 | Dual AI provider support (Gemini + Claude via ProviderRouter) | DONE |
| 14 | Git webhooks for incremental analysis | DONE |
| 15 | 12 user-reported issues fixed (JWT, billing, timing, export) | DONE |

---

## Commit History (29 Commits)

```
bd749eb docs: Update Sprint 2 documentation with all recent work for Sprint 3 context
2c124f0 docs: Add comprehensive Sprint 3 execution plan
d339d29 feat: Sprint 3 Day 1 — Business Ontology Engine + Initiative Governance + N+1 Fix
3957be1 feat: Sprint 3 Day 2 — Code Analysis Engine + Bug Fixes + Ontology Status
387f905 feat: Sprint 3 Day 3 — Frontend UI Overhaul + CoordinatorService + Bug Fixes
37f5359 feat: Sprint 3 Day 4 — Ontology Dashboard UI + ImportError fix
1b37de2 fix: merge divergent Alembic heads (Sprint 2 tasks + Sprint 3 repos)
8878a02 fix: add Admin role to Role enum to fix login validation error
fd63eae merge: integrate Sprint 2 prep branch (26 commits) into Sprint 3
95819f1 fix: include usage_logs migration in merge (3-way head merge)
8738bad fix: make branch migrations idempotent to prevent DuplicateTable errors
72ace78 fix: BUG-01 validation refresh + BUG-02 upload progress (Sprint 3 Day 4)
ee9445e feat: dual-source Business Ontology Engine — code + documents (Sprint 3)
391e382 feat: layered BOE with reconciliation pass — fix collision architecture
b7ea1cc feat: Sprint 3 Day 5 — Enhanced Semantic Code Analysis (AI-02) + Integration Tests
10a97bd feat: two-graph architecture with algorithmic mapping — ADHOC Phase 1
cd455d7 fix: FLAW-11-B N+1 queries + CAE-03 multi-column PDF + task registry
037df6a test: Sprint 3 Day 9 — comprehensive integration tests
4e69dfc docs: Sprint 3 completion status — all deliverables done
fe4e57c feat: Sprint 4 ADHOC-07/08/09 — Claude API, dual-provider routing, git webhooks
e4b375a feat: Two-Graph UI — cross-graph visualization, mapping review, gap analysis
cfe3f1d Add comprehensive manual testing guide for Sprint 4
2b2f912 Fix concept_mappings migration to handle pre-existing table
ead53a2 feat: Redesign ontology page UX — scrollable table + graph dual-view
0232212 fix: repository_id migration guard + scrollable CrossGraphView
7ff7ff4 fix: add catch-up migration for repository_id column
4d1507b feat: Add cost tracking for code analysis (matching document pattern)
56372ce fix: Code analysis — JSON parsing, GitHub URL handling, registration UX
ab7fa3f fix: Catch-up migration for missing cost columns on code_components
94b6fcf feat: Code analysis UI enhancements — cost display, billing integration, ontology extraction
086d70b feat: Address all 12 user-reported issues — JWT, timing, billing, ontology, export
```

---

## Sprint 4 Context & Preparation

### What's Built (Foundation for Sprint 4)

Sprint 3 delivered a complete knowledge graph + code intelligence platform. Sprint 4 can build on:

1. **Two-Graph Architecture** - Document and code ontologies with cross-mapping
2. **Dual AI Providers** - Gemini + Claude routing infrastructure
3. **Git Webhooks** - Incremental analysis pipeline
4. **Context Assembly** - BOE context envelopes for enhanced AI analysis
5. **56+ Tests** - Solid test foundation to build on

### Suggested Sprint 4 Priorities

1. **Chat with Document** - RAG-based Q&A using BOE context envelopes
2. **Real-Time Collaboration** - WebSocket-based live updates
3. **Advanced Validation** - Cross-graph validation using ontology context
4. **Notification System** - Email/Slack alerts for analysis completion, billing
5. **Version Comparison** - Document diff tracking over time
6. **Performance Optimization** - Async DB I/O, cursor-based pagination
7. **Enhanced Export** - PDF reports, compliance reports for Auditor role

### Key Files to Read for Sprint 4

```
# Architecture & Context
SPRINT_3_COMPLETE.md                                  - This file (full Sprint 3 context)
SPRINT2_COMPLETE.md                                   - Sprint 2 context
SPRINT_3_EXECUTION_PLAN.md                            - Sprint 3 execution details
docs/MANUAL_TESTING_GUIDE.md                          - Testing guide

# Core Services
backend/app/services/business_ontology_service.py     - BOE pipeline
backend/app/services/mapping_service.py               - Cross-graph mapping
backend/app/services/context_assembly_service.py       - Context envelopes
backend/app/services/code_analysis_service.py          - Code analysis engine
backend/app/services/ai/provider_router.py             - AI provider routing

# API Layer
backend/app/api/endpoints/ontology.py                 - Ontology endpoints
backend/app/api/endpoints/repositories.py              - Repository endpoints
backend/app/api/endpoints/webhooks.py                  - Git webhook endpoint

# Frontend
frontend/app/dashboard/ontology/page.tsx              - Ontology dashboard
frontend/components/ontology/CrossGraphView.tsx        - Two-graph visualization
frontend/lib/api.ts                                    - API client methods

# Configuration
backend/app/core/config.py                            - App config (API keys, providers)
backend/app/core/permissions.py                        - RBAC system
```

### Tech Stack (Complete)

```
Backend:
  - FastAPI 0.109.0
  - SQLAlchemy 2.0 (sync)
  - PostgreSQL 15
  - Redis 7
  - Celery 5.3
  - Google Generative AI SDK (Gemini)
  - Anthropic SDK (Claude)
  - Alembic (migrations)
  - PyMuPDF + pdfplumber (PDF parsing)
  - python-docx (DOCX parsing)

Frontend:
  - Next.js 15
  - React 19
  - TypeScript
  - Tailwind CSS
  - Radix UI (Dialog, Tabs, Select, etc.)
  - Lucide React (icons)

Infrastructure:
  - Docker Compose (5 services)
  - Nginx (reverse proxy)
  - Flower (Celery monitoring)
```

---

**Sprint 3 Status:** 100% COMPLETE
**Total Duration:** ~280 hours
**Lines of Code:** 17,195+ added
**Files Changed:** 97
**Tests:** 56+ new (22 files total)
**Production Ready:** YES

---

**Branch:** `claude/dokydoc-evolution-guide-49riQ`
**Final Commit:** `086d70b`
**Last Updated:** 2026-02-18
