# DokyDoc — Master Implementation Plan

> **Last Updated:** 2026-03-17
> **Strategy:** Strategist + Solution Architect + Product Owner perspective
> **Principle:** Org Brain = top-down drill-down. Nothing auto-connects to a project unless a user explicitly links a repo or document to it.

---

## Sprint Completion Status

| Sprint | Feature | Status |
|--------|---------|--------|
| Sprint 1 | Auth (JWT + RBAC), Multi-Tenancy, Document Upload | ✅ COMPLETE |
| Sprint 2 | Multi-Pass Document Analysis, Billing, CXO/Admin Dashboards | ✅ COMPLETE |
| Sprint 3 | Code Analysis Engine, BOE Knowledge Graphs, Brain Dashboard (L1-5), Graph Versioning, Requirement Traceability | ✅ COMPLETE |
| Sprint 4 | Validation Engine, pgvector Embeddings, Semantic Search, Auto-Linking | ✅ COMPLETE |
| Sprint 5 | Git Webhooks, Branch Preview (Redis), Audit Trail, Notifications, Cursor Pagination, PR Comment Integration, Billing Analytics | ✅ COMPLETE |
| Sprint 6 | Approval Workflow (model + API + UI), RBAC, Audit Export | ✅ COMPLETE |
| Sprint 7 | RAG/Chat Assistant (models + API + UI), Conversation history, Multi-turn | ✅ COMPLETE |
| Sprint 8 | Jira/Slack integrations (config model), Auto-Docs, Notification Preferences, API Keys | ✅ BACKEND COMPLETE |
| **Sprint 8 Remaining** | Analytics Dashboard (service + API + UI) | ✅ COMPLETE |

---

## Bug Fixes Completed (2026-03-17)

| Bug | Fix | File |
|-----|-----|------|
| Auto Docs page crash (`docs.slice is not a function`) | API returns `{items:[]}` paginated — use `docs.items` with safe fallbacks | `frontend/app/dashboard/auto-docs/page.tsx` |
| Projects page showing 4408 concepts for all projects | `count_by_tenant` included global `initiative_id=NULL` concepts; now strict-scoped per project | `backend/app/crud/crud_ontology_concept.py` |
| remark-gfm ESM module not found | Added `transpilePackages` to next.config.ts | `frontend/next.config.ts` |
| Alembic `document_versions` DuplicateTable | Stamped DB to `s8a7_add_integration_configs` head | Manual DB fix |

---

## Pending Sprint 8: Analytics Dashboard

### P8-1: Analytics Service (Backend)
- **File:** `backend/app/services/analytics_service.py` (NEW)
- Aggregate `UsageLog` into time-series: AI cost per tenant/month, analysis throughput, validation coverage, concept growth
- Cache results in Redis (5-minute TTL) for fast dashboard loads
- Methods: `get_cost_breakdown(tenant_id, period)`, `get_coverage_trend(initiative_id)`, `get_concept_growth(tenant_id)`, `get_activity_metrics(tenant_id)`

### P8-2: Analytics API Endpoints
- **File:** `backend/app/api/endpoints/analytics.py` (NEW)
```
GET /analytics/costs?period=month     → cost breakdown by feature
GET /analytics/coverage?initiative_id → validation coverage over time
GET /analytics/concepts?period=week   → concept growth trend
GET /analytics/activity               → user activity metrics
GET /analytics/overview               → combined dashboard summary
```

### P8-3: Analytics Dashboard Frontend
- **File:** `frontend/app/dashboard/analytics/page.tsx` (NEW)
- Cost charts (line graph per month, pie chart by feature type)
- Validation coverage trend
- Knowledge graph growth (concept/relationship count over time)
- Team activity summary

---

## Brain Vision — Strategic Roadmap (Post-Sprint 8)

> **Business Context:** Think of it like Google's org — 50 simultaneous projects. The Brain is the **entire organization's knowledge graph** with top-down drill-down navigation.

### Brain Architecture (Top-Down Hierarchy)

```
L5 — Organization (Current: All projects as clusters)
  └─► L4 — Alignment (Doc ↔ Code cross-mapping per project)
        └─► L3 — System (Repo architecture — auto-generated flow diagrams)
              └─► L2 — Domain (Module/service/storage breakdown)
                    └─► L1 — File (Classes, functions, columns, APIs)
```

### Brain Bug Fixes (Immediate)

| Bug | Description | Fix |
|-----|-------------|-----|
| L5→L3 click does nothing | Clicking a project node or level card doesn't navigate | Fix `drillState` transitions in `brain/page.tsx` |
| L3/L2/L1 empty on load | Graph data not being fetched for drill levels | Wire `fetchGraphData()` per level correctly |
| Empty L3 even with repo connected | System architecture graph not auto-building from repo data | Auto-generate Mermaid from code_components |

### Brain Enhancement Plan (Post-Sprint 8)

#### B1 — Fix L5→L4→L3→L2→L1 Navigation ✅ COMPLETE
- **File:** `frontend/app/dashboard/brain/page.tsx`
- L5 → click project node → load L4 (Alignment/doc-code mapping) — DONE
- L4 → click → load L3 (System architecture with auto-diagrams) — DONE
- L3 → click a service/module node → load L2 (Domain: tables, modules) — DONE
- L2 → click a table → load L1 (Columns, methods, schemas) — DONE
- Each level shows a breadcrumb trail — DONE

#### B2 — Auto-Generated Architecture Diagrams at L3 ✅ COMPLETE
- **File:** `backend/app/api/endpoints/ontology.py`
- Auto-generates 3 diagram types from code_components:
  - **Architecture Flow Diagram** (`graph TD`) — DONE
  - **Data Flow Diagram** (`sequenceDiagram`) — DONE
  - **ER Diagram** (`erDiagram`) — DONE
- **Frontend:** 4-tab selector `[Graph][Architecture][Data Flow][ER Diagram]` — DONE
- **Component:** `frontend/components/ontology/MermaidDiagram.tsx` — DONE

#### B3 — L2 Interactive Concept Drill-Down ✅ COMPLETE
- L2 domain view: concept type filter pills (ALL / REQUIREMENT / ENTITY / etc.) — DONE
- Concept detail side panel: name, type, confidence, relationships, source — DONE
- L2 bug fixed: was calling `domain.nodes` on summary objects; now filters `drillData.nodes` by domain — DONE

#### B4 — L4 Alignment Inline View ✅ COMPLETE
- L4 now renders inline inside Brain (no routing to projects page)
- Bipartite 3-column layout: Document concepts | Mappings | Code concepts — DONE
- Coverage stats bar with color coding — DONE
- Gap analysis panel for unmapped requirement concepts — DONE
- Run Mapping button + back-to-L3 navigation — DONE

#### B5 — Cross-Project L4 Mappings (Priority: MEDIUM)
- L4 shows concept bridges between Project A and Project B
- Confidence score indicators on cross-project edges
- "Run Cross-Project Mapping" button at L4

#### B6 — L3 Diagram Export (Priority: LOW)
- Export Mermaid diagrams as SVG/PNG
- "Copy Mermaid source" button for embedding in docs
- Integration with Auto-Docs (Architecture Diagram doc type already defined)

---

## Execution Order

```
✅ Sprint 8 Analytics (P8-1, P8-2, P8-3) — COMPLETE
✅ Brain Bug Fixes (B1 — navigation) — COMPLETE
✅ Brain Enhancements (B2 — auto-diagrams, B3 — drill-down, B4 — L4 alignment) — COMPLETE
      ↓
NEXT → B5 Cross-project mappings (L4 shows concept bridges between projects)
NEXT → B6 Diagram Export improvements
FUTURE → Jira OAuth full implementation (config model exists, UI exists)
         → Slack OAuth full implementation
```

---

## Architecture Principle: Project Isolation

> **Rule:** A project's Brain, ontology, and concept count must only reflect what the user has explicitly connected to it.

- Concept count for a project = `COUNT(*) WHERE initiative_id = project_id` (strict, no NULL fallback)
- Brain graph for a project = only concepts from linked repos and linked documents
- Cross-project mappings = explicitly triggered by user, not automatic
- L5 org view = all projects visible, but each is isolated until explicitly mapped

---

## Key Files Reference

| Area | File | Status |
|------|------|--------|
| Brain page | `frontend/app/dashboard/brain/page.tsx` | ✅ Built, L1-L5 navigation complete |
| Brain breadcrumb | `frontend/components/ontology/BrainBreadcrumb.tsx` | Built |
| Meta graph view | `frontend/components/ontology/MetaGraphView.tsx` | Built |
| Ontology graph | `frontend/components/ontology/OntologyGraph.tsx` | Built |
| Analytics service | `backend/app/services/analytics_service.py` | ✅ Built |
| Analytics API | `backend/app/api/endpoints/analytics.py` | ✅ Built |
| Analytics dashboard | `frontend/app/dashboard/analytics/page.tsx` | ✅ Built |
| Auto-docs page | `frontend/app/dashboard/auto-docs/page.tsx` | Built (crash fixed) |
| Projects page | `frontend/app/dashboard/projects/page.tsx` | Built (count fixed) |
| Ontology CRUD | `backend/app/crud/crud_ontology_concept.py` | Built (count fixed) |
| Validation export | `backend/app/api/endpoints/validation.py` | Built |
| Export UI | `frontend/app/dashboard/export/page.tsx` | Built |
| Chat | `frontend/app/dashboard/chat/page.tsx` | Built |
| Approvals | `frontend/app/dashboard/approvals/page.tsx` | Built |
| Integrations | `frontend/app/dashboard/integrations/page.tsx` | Built |
