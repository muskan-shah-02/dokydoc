# Plan: Multi-Project Architecture + Hierarchical UI + Cross-Project Ontology

## The Problem (3 layers)

1. **UI Flooding**: Uploading a repo with 237 files creates 237 rows in a flat table. Users only want to see repos, with files as drill-down.
2. **No Project Grouping**: Everything is a flat list under the tenant. Need "Project" (Initiative) to group related docs + repos.
3. **Cross-Project Ontology**: Projects in an org are interrelated (APIs talk across repos). Need per-project graphs + an org-wide meta-graph showing connections.

## Key Discovery: Initiative Already Exists!

The backend already has `Initiative` + `InitiativeAsset` models, CRUD, schemas, and API endpoints — but they're **completely unwired** from the frontend and ontology system. We build on top of this.

---

## PHASE 1: Hierarchical UI + Project Wiring (Quick Win)

### 1.1 Restructure Code Page — Repo → Files Hierarchy

**File**: `frontend/app/dashboard/code/page.tsx`

**Current**: Flat table fetching ALL code_components (repos + files mixed).
**Target**: Two-level expandable view:
- **Primary rows**: Repositories (from `GET /api/v1/repositories/`)
- **Expandable children**: Files per repo (lazy-fetch `GET /api/v1/repositories/{id}/components`)
- **Separate section**: Standalone components (repository_id = NULL)

Changes:
- Replace single `/code-components/` fetch with `/repositories/` + `/code-components/?standalone=true`
- Expandable row using Radix `Collapsible` (already in project at `frontend/components/ui/collapsible.tsx`)
- Repo row shows: name, URL, analysis_status, analyzed_files/total_files, cost summary
- Child rows (on expand): file name, status, cost, duration
- Stats cards: switch from per-component counts to per-repo counts

**Backend**: `backend/app/api/endpoints/code_components.py`
- Add `standalone: bool = Query(False)` param — when true, filter `repository_id IS NULL`

### 1.2 Fix Initiative Asset Linking Bug

**File**: `backend/app/api/endpoints/initiatives.py` ~line 156

Bug: REPOSITORY asset linking uses `crud.code_component.get()` instead of `crud.repository.get()`.

### 1.3 Project Context + Sidebar Navigation

**New file**: `frontend/contexts/ProjectContext.tsx`
```typescript
interface ProjectContextType {
  selectedProject: Initiative | null;  // null = "All Projects"
  setSelectedProject: (p: Initiative | null) => void;
  projects: Initiative[];
  refreshProjects: () => void;
}
```
- Persisted in localStorage
- `null` = "All Projects" (backward-compatible, no filtering)

**File**: `frontend/components/layout/Sidebar.tsx`
- Add project selector dropdown between Tenant Info and Main Menu
- Shows: "All Projects" + list from `GET /api/v1/initiatives/`
- "+" button to create new project inline

### 1.4 Project-Filtered API Endpoints

Add optional `initiative_id` query param to:
- `GET /api/v1/documents/` — filter via InitiativeAsset join
- `GET /api/v1/repositories/` — filter via InitiativeAsset join
- `GET /api/v1/code-components/` — filter via repo → InitiativeAsset join

**New CRUD method** (in `crud_repository.py`, `crud_document.py`):
```python
def get_by_initiative(self, db, *, initiative_id, tenant_id, skip=0, limit=100):
    asset_ids = db.query(InitiativeAsset.asset_id).filter(
        InitiativeAsset.initiative_id == initiative_id,
        InitiativeAsset.asset_type == "REPOSITORY",  # or "DOCUMENT"
        InitiativeAsset.tenant_id == tenant_id,
    ).subquery()
    return db.query(self.model).filter(
        self.model.id.in_(asset_ids),
        self.model.tenant_id == tenant_id,
    ).offset(skip).limit(limit).all()
```

Frontend docs/code pages: read `selectedProject` from context, pass `?initiative_id=X` to APIs.

### 1.5 Auto-Link Assets to Active Project

When a user uploads a doc or repo while a project is selected, auto-create an InitiativeAsset linking it.

### 1.6 Asset Linking UI

In project context, provide "Add Document/Repo to Project" buttons that call existing `POST /initiatives/{id}/assets`.

**No migrations needed for Phase 1** — Initiative + InitiativeAsset tables already exist.

---

## PHASE 2: Project-Scoped Ontology

### 2.1 Add initiative_id to OntologyConcept

**File**: `backend/app/models/ontology_concept.py`
```python
initiative_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("initiatives.id"), nullable=True, index=True
)
```

**nullable=True** is critical:
- Existing concepts keep NULL = "org-wide / unscoped"
- Tenants without projects work exactly as before
- Shared concepts (e.g., "Authentication") can exist across projects

### 2.2 Migration

`s4a1_add_initiative_to_ontology.py`: Add `initiative_id` column + composite index `(tenant_id, initiative_id)`.

### 2.3 CRUD + Dedup Changes

**File**: `backend/app/crud/crud_ontology_concept.py`

`get_or_create()` includes `initiative_id` in dedup match criteria.
New: `get_by_initiative()` returns concepts where `initiative_id = X OR initiative_id IS NULL` (project + shared).

### 2.4 Pipeline: Tag Concepts with Project

**Doc extraction** (`ontology_tasks.py`): Look up `InitiativeAsset` for the document → pass `initiative_id` to extraction.
**Code extraction** (`code_analysis_service.py`): Look up `InitiativeAsset` for the repository → pass `initiative_id` to extraction.

### 2.5 API: Project-Filtered Graph Endpoints

Add `initiative_id` query param to:
- `GET /ontology/concepts` — filter by initiative
- `GET /ontology/graph` — build graph from project's concepts only
- `GET /ontology/graph/document`, `/graph/code` — same
- `GET /ontology/stats` — project-scoped stats

### 2.6 Frontend: Per-Project Ontology View

**File**: `frontend/app/dashboard/ontology/page.tsx`
- Read `selectedProject` from context
- Pass `?initiative_id=X` to all ontology API calls
- "All Projects" = no filter (full tenant graph, same as today)

### 2.7 Project Dashboard Page

**New**: `frontend/app/dashboard/projects/page.tsx` — list all projects with stats
**New**: `frontend/app/dashboard/projects/[id]/page.tsx` — single project view (assets + ontology + mappings)

---

## PHASE 3: Cross-Project Mapping + Org-Wide Meta-Graph

### 3.1 New Model: CrossProjectMapping

**New file**: `backend/app/models/cross_project_mapping.py`

Separate table (NOT extending ConceptMapping) because:
- ConceptMapping columns are `document_concept_id` / `code_concept_id` — semantically locked to doc↔code
- Cross-project maps ANY concept to ANY concept (regardless of source layer)
- Different relationship types: `calls_api`, `shares_data`, `depends_on`, `duplicates`, `extends`

```python
class CrossProjectMapping(Base):
    __tablename__ = "cross_project_mappings"
    concept_a_id     # FK to OntologyConcept (in project A)
    concept_b_id     # FK to OntologyConcept (in project B)
    initiative_a_id  # FK to Initiative (denormalized for queries)
    initiative_b_id  # FK to Initiative
    mapping_method   # exact / fuzzy / ai_validated
    confidence_score, status, relationship_type, ai_reasoning
```

### 3.2 Cross-Project Mapping Algorithm

**New**: `backend/app/services/cross_project_mapping_service.py`

Reuses 3-tier approach (exact → fuzzy → AI) but runs BETWEEN projects:
- Get concepts for Project A (strict, no shared)
- Get concepts for Project B (strict, no shared)
- Tier 1: Exact name match across projects
- Tier 2: Fuzzy token overlap + Levenshtein
- Tier 3: AI validation for ambiguous pairs only

Cost: ~$0.02-0.05 per run (same as existing intra-tenant mapping).

### 3.3 Org-Wide Meta-Graph API

`GET /ontology/graph/meta` — returns:
- All concepts (clustered by initiative_id)
- Intra-project edges (OntologyRelationship)
- Cross-project edges (CrossProjectMapping)

### 3.4 Cross-Project API Endpoints

```
POST   /ontology/cross-project/run
GET    /ontology/cross-project/mappings
PUT    /ontology/cross-project/mappings/{id}/confirm
PUT    /ontology/cross-project/mappings/{id}/reject
GET    /ontology/cross-project/stats
```

### 3.5 Frontend: Meta-Graph View

**New tab** on ontology page: `[All] [Document] [Code] [Meta-Graph]`
- Nodes clustered by project (different background colors)
- Cross-project edges drawn as dashed lines between clusters
- Cross-project review panel (confirm/reject cross-project mappings)

### 3.6 Migration

`s4a2_cross_project_mappings.py`: Create `cross_project_mappings` table.

---

## Key Files to Modify

| Phase | File | Change |
|-------|------|--------|
| 1 | `frontend/app/dashboard/code/page.tsx` | Hierarchical repo→files view |
| 1 | `frontend/components/layout/Sidebar.tsx` | Project selector dropdown |
| 1 | `frontend/contexts/ProjectContext.tsx` | NEW — project context |
| 1 | `backend/app/api/endpoints/initiatives.py` | Fix asset linking bug |
| 1 | `backend/app/api/endpoints/code_components.py` | Add standalone filter |
| 1 | `backend/app/api/endpoints/repositories.py` | Add initiative_id filter |
| 1 | `backend/app/api/endpoints/documents.py` | Add initiative_id filter |
| 2 | `backend/app/models/ontology_concept.py` | Add initiative_id column |
| 2 | `backend/app/crud/crud_ontology_concept.py` | Project-scoped dedup + queries |
| 2 | `backend/app/tasks/ontology_tasks.py` | Tag concepts with initiative_id |
| 2 | `backend/app/api/endpoints/ontology.py` | Project-filtered graph endpoints |
| 2 | `frontend/app/dashboard/ontology/page.tsx` | Project-scoped graph views |
| 2 | `frontend/app/dashboard/projects/page.tsx` | NEW — project dashboard |
| 3 | `backend/app/models/cross_project_mapping.py` | NEW — cross-project mapping model |
| 3 | `backend/app/services/cross_project_mapping_service.py` | NEW — cross-project algorithm |
| 3 | `frontend/components/ontology/MetaGraphView.tsx` | NEW — org-wide meta-graph |

---

## PHASE 4: Ephemeral Branch Previews & CI/CD Integration (Git-Flow for BOE)

### The Problem

When developers push feature branches, we want to show how their code changes affect the business ontology graph **without bloating PostgreSQL** with temporary data. Currently, ontology concepts go straight into SQL — if we cloned the graph for every branch, we'd multiply storage N times.

### Architecture: Base + Delta

```
┌─────────────────────────────────────────────────────┐
│                  GROUND TRUTH (main)                │
│    PostgreSQL: ontology_concepts + relationships     │
│    Source of truth — only main branch writes here    │
└────────────────────┬────────────────────────────────┘
                     │ READ (base graph)
                     ▼
┌─────────────────────────────────────────────────────┐
│              ON-THE-FLY MERGE (API layer)           │
│  base_graph (SQL) + branch_delta (Redis) → merged   │
│  Annotates each node: unchanged/added/modified/removed│
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        ▼                           ▼
┌──────────────────┐  ┌──────────────────────────────┐
│  EPHEMERAL DELTA │  │      VISUAL DIFF UI          │
│  Redis (7d TTL)  │  │  Grey=unchanged Green=added  │
│  Key: preview:   │  │  Red=removed   Yellow=modified│
│  {tenant}:{repo} │  │  New tab: [Branch Preview]   │
│  :{branch}       │  └──────────────────────────────┘
└──────────────────┘
```

### 4.1 Redis Key Schema for Branch Previews

```
preview_graph:{tenant_id}:{repo_id}:{branch_name}
```

**Value**: JSON payload matching the extraction result format:
```json
{
  "branch": "feature/add-payment",
  "commit_hash": "a1b2c3d4",
  "extracted_at": "2026-02-20T12:00:00Z",
  "entities": [
    {"name": "PaymentGateway", "type": "Service", "confidence": 0.9, "context": "..."},
    {"name": "StripeWebhook", "type": "Process", "confidence": 0.85, "context": "..."}
  ],
  "relationships": [
    {"source": "PaymentGateway", "target": "StripeWebhook", "type": "depends_on", "confidence": 0.8}
  ],
  "changed_files": ["backend/app/services/payment.py", "backend/app/api/endpoints/billing.py"]
}
```

**TTL**: 7 days (604800 seconds). Auto-expires when branch goes stale.

### 4.2 Cache Service Extension

**File**: `backend/app/services/cache_service.py`

Add 3 new methods:

```python
def set_branch_preview(self, *, tenant_id: int, repo_id: int, branch: str,
                       preview_data: dict, ttl_seconds: int = 604800) -> bool:
    """Store ephemeral branch preview graph in Redis (7-day TTL)."""
    key = f"preview_graph:{tenant_id}:{repo_id}:{branch}"
    return self.redis_client.setex(key, ttl_seconds, json.dumps(preview_data, default=str))

def get_branch_preview(self, *, tenant_id: int, repo_id: int, branch: str) -> Optional[dict]:
    """Retrieve branch preview graph from Redis."""
    key = f"preview_graph:{tenant_id}:{repo_id}:{branch}"
    data = self.redis_client.get(key)
    return json.loads(data) if data else None

def delete_branch_preview(self, *, tenant_id: int, repo_id: int, branch: str) -> bool:
    """Clean up preview when branch is merged or deleted."""
    key = f"preview_graph:{tenant_id}:{repo_id}:{branch}"
    return self.redis_client.delete(key) > 0
```

### 4.3 Celery Task: Branch Preview Extraction

**File**: `backend/app/tasks/code_analysis_tasks.py`

Modify `webhook_triggered_analysis` (line 712) to detect main vs. feature branch:

```python
@celery_app.task(name="webhook_triggered_analysis", bind=True, max_retries=2)
def webhook_triggered_analysis(
    self, repo_id, tenant_id, changed_files, branch="", commit_hash=""
):
    # Determine if this is a preview branch or main
    is_main = branch in ("main", "master", "develop", repo.default_branch)

    if is_main:
        # EXISTING FLOW: Permanent write to PostgreSQL
        # ... (existing code unchanged) ...
        # After file analysis completes, run ontology extraction as before
        from app.tasks.ontology_tasks import extract_code_ontology_entities
        extract_code_ontology_entities.delay(repo_id=repo_id, tenant_id=tenant_id)
    else:
        # NEW FLOW: Ephemeral preview → write to Redis, NOT PostgreSQL
        branch_preview_extraction.delay(
            repo_id=repo_id, tenant_id=tenant_id,
            branch=branch, commit_hash=commit_hash,
            changed_files=changed_files,
        )
```

**New task**: `branch_preview_extraction`

```python
@celery_app.task(name="branch_preview_extraction", bind=True)
def branch_preview_extraction(
    self, repo_id: int, tenant_id: int, branch: str,
    commit_hash: str, changed_files: list
):
    """
    Analyze changed files on a feature branch and store extracted
    concepts/relationships in Redis as an ephemeral preview.
    Does NOT write to PostgreSQL.
    """
    db = SessionLocal()
    try:
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            return

        entities = []
        relationships = []

        for file_path in changed_files:
            # 1. Fetch file content from branch (raw GitHub URL with branch)
            raw_url = f"https://raw.githubusercontent.com/{_extract_owner_repo(repo.url)}/{branch}/{file_path}"
            code_content = httpx.get(raw_url).text

            # 2. Run AI analysis (same as enhanced analysis)
            from app.services.ai.provider_router import provider_router
            analysis_result = _run_async(
                provider_router.analyze_code_enhanced(
                    code_content, repo_name=repo.name,
                    file_path=file_path, language=_detect_language(file_path)
                )
            )

            # 3. Extract inline ontology concepts from structured_analysis
            structured = analysis_result.get("structured_analysis", {})
            file_entities, file_rels = _extract_entities_from_structured(
                structured, file_path
            )
            entities.extend(file_entities)
            relationships.extend(file_rels)

        # 4. Store in Redis (NOT PostgreSQL)
        from app.services.cache_service import cache_service
        cache_service.set_branch_preview(
            tenant_id=tenant_id, repo_id=repo_id, branch=branch,
            preview_data={
                "branch": branch,
                "commit_hash": commit_hash,
                "extracted_at": datetime.utcnow().isoformat(),
                "entities": entities,
                "relationships": relationships,
                "changed_files": changed_files,
            }
        )
        logger.info(
            f"Branch preview stored: {repo.name}/{branch} — "
            f"{len(entities)} entities, {len(relationships)} relationships"
        )
    finally:
        db.close()
```

### 4.4 Ontology API: Branch Preview Endpoint

**File**: `backend/app/api/endpoints/ontology.py`

Add new endpoint that performs the on-the-fly merge:

```python
@router.get("/graph/preview/{repo_id}/{branch}", response_model=BranchPreviewGraphResponse)
def get_branch_preview_graph(
    repo_id: int,
    branch: str,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    On-the-fly merge: base graph (PostgreSQL) + branch delta (Redis).
    Returns nodes annotated with diff_status: unchanged/added/modified/removed.
    """
    # 1. Fetch base graph from PostgreSQL (main branch ground truth)
    base_concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    base_relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)

    # 2. Fetch branch delta from Redis
    from app.services.cache_service import cache_service
    preview = cache_service.get_branch_preview(
        tenant_id=tenant_id, repo_id=repo_id, branch=branch
    )

    if not preview:
        raise HTTPException(status_code=404, detail="No preview available for this branch")

    # 3. Build base concept lookup
    base_names = {c.name.lower(): c for c in base_concepts}

    # 4. Merge: annotate each node with diff_status
    nodes = []
    branch_entity_names = set()

    # Add base concepts (mark as "unchanged" or "modified")
    for c in base_concepts:
        diff_status = "unchanged"
        # Check if this concept appears in the branch delta
        for be in preview.get("entities", []):
            if be["name"].lower() == c.name.lower():
                diff_status = "modified"  # Exists in both base and branch
                break
        nodes.append(BranchPreviewNode(
            id=c.id, name=c.name, concept_type=c.concept_type,
            source_type=c.source_type, confidence_score=c.confidence_score,
            diff_status=diff_status,
        ))

    # Add branch-only concepts (marked "added")
    next_id = max((c.id for c in base_concepts), default=0) + 1000
    for be in preview.get("entities", []):
        if be["name"].lower() not in base_names:
            nodes.append(BranchPreviewNode(
                id=next_id, name=be["name"], concept_type=be.get("type", "Entity"),
                source_type="code", confidence_score=be.get("confidence", 0.8),
                diff_status="added",
            ))
            next_id += 1

    # 5. Build edges (base + branch)
    edges = [
        BranchPreviewEdge(
            id=r.id, source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score,
            diff_status="unchanged",
        ) for r in base_relationships
    ]
    # Add branch-only relationships (resolve by name → id)
    # ... (name-to-id resolution for branch entities)

    return BranchPreviewGraphResponse(
        nodes=nodes, edges=edges,
        total_nodes=len(nodes), total_edges=len(edges),
        branch=branch, commit_hash=preview.get("commit_hash", ""),
        changed_files=preview.get("changed_files", []),
    )
```

### 4.5 New Schemas for Branch Preview

**File**: `backend/app/schemas/ontology.py`

```python
class BranchPreviewNode(OntologyGraphNode):
    diff_status: str = "unchanged"  # "unchanged", "added", "modified", "removed"

class BranchPreviewEdge(OntologyGraphEdge):
    diff_status: str = "unchanged"

class BranchPreviewGraphResponse(BaseModel):
    nodes: List[BranchPreviewNode]
    edges: List[BranchPreviewEdge]
    total_nodes: int
    total_edges: int
    branch: str
    commit_hash: str
    changed_files: List[str] = []
```

### 4.6 Webhook Enhancement: Push vs. PR Merge

**File**: `backend/app/api/endpoints/webhooks.py`

Extend to handle **two new event types** beyond push:

```python
@router.post("/git")
async def handle_git_webhook(request, db, ...):
    # ... existing provider detection ...

    if event_type == "push":
        # Existing: extract push data
        push_data = _extract_github_push(payload)
        branch = push_data["branch"]
        is_main = branch in ("main", "master", "develop")

        if is_main:
            # Main branch push → permanent analysis (existing flow)
            webhook_triggered_analysis.delay(...)
        else:
            # Feature branch push → ephemeral preview extraction
            branch_preview_extraction.delay(
                repo_id=repo.id, tenant_id=repo.tenant_id,
                branch=branch, commit_hash=push_data["head_commit"],
                changed_files=push_data["changed_files"],
            )

    elif event_type == "pull_request":
        # PR merged → promote ephemeral delta to permanent SQL
        pr_data = _extract_github_pr(payload)
        if pr_data["action"] == "closed" and pr_data["merged"]:
            promote_branch_preview.delay(
                repo_id=repo.id, tenant_id=repo.tenant_id,
                branch=pr_data["head_branch"],
            )

    elif event_type == "delete":
        # Branch deleted → clean up Redis preview
        branch = _extract_branch_from_delete(payload)
        cache_service.delete_branch_preview(
            tenant_id=repo.tenant_id, repo_id=repo.id, branch=branch,
        )
```

**New helper**:
```python
def _extract_github_pr(payload: dict) -> dict:
    """Extract PR merge data from GitHub pull_request event."""
    pr = payload.get("pull_request", {})
    return {
        "action": payload.get("action"),           # "closed"
        "merged": pr.get("merged", False),          # True if actually merged
        "head_branch": pr.get("head", {}).get("ref", ""),
        "base_branch": pr.get("base", {}).get("ref", ""),
        "pr_number": pr.get("number"),
    }
```

### 4.7 Celery Task: Promote Preview to Permanent

**New task**: `promote_branch_preview`

```python
@celery_app.task(name="promote_branch_preview")
def promote_branch_preview(repo_id: int, tenant_id: int, branch: str):
    """
    When a PR is merged, take the ephemeral Redis preview and write
    its concepts/relationships permanently to PostgreSQL.
    Then clean up the Redis key.
    """
    from app.services.cache_service import cache_service
    preview = cache_service.get_branch_preview(
        tenant_id=tenant_id, repo_id=repo_id, branch=branch
    )
    if not preview:
        logger.info(f"No preview to promote for {branch}")
        return

    db = SessionLocal()
    try:
        # Ingest the preview entities/relationships into PostgreSQL
        from app.services.business_ontology_service import business_ontology_service
        business_ontology_service._ingest_extraction_result(
            db=db,
            entities=preview.get("entities", []),
            relationships=preview.get("relationships", []),
            tenant_id=tenant_id,
            source_type="code",
        )
        db.commit()

        # Clean up Redis
        cache_service.delete_branch_preview(
            tenant_id=tenant_id, repo_id=repo_id, branch=branch
        )
        logger.info(f"Promoted branch preview {branch} to permanent ontology")

        # Trigger cross-graph mapping
        from app.tasks.ontology_tasks import run_cross_graph_mapping
        run_cross_graph_mapping.delay(tenant_id=tenant_id)
    finally:
        db.close()
```

### 4.8 Frontend: Visual Diff Graph

**New file**: `frontend/components/ontology/BranchPreviewGraph.tsx`

Extends `OntologyGraph.tsx` with diff-aware rendering:

```typescript
// Diff color overrides (take priority over TYPE_COLORS)
const DIFF_COLORS: Record<string, { bg: string; border: string; badge: string }> = {
  unchanged: { bg: "inherit", border: "#9ca3af", badge: "" },        // Grey border
  added:     { bg: "#dcfce7", border: "#22c55e", badge: "+" },       // Green
  modified:  { bg: "#fef9c3", border: "#eab308", badge: "~" },       // Yellow
  removed:   { bg: "#fee2e2", border: "#ef4444", badge: "-" },       // Red, 40% opacity
};

// Node rendering override:
// - If diff_status !== "unchanged", override border color with DIFF_COLORS
// - Add diff badge ("+", "~", "-") in top-right
// - "removed" nodes rendered at 40% opacity with strikethrough name
// - "added" nodes get a subtle green glow animation
```

**File**: `frontend/app/dashboard/ontology/page.tsx`

Add a 4th tab (only visible when a repo has active branches):

```typescript
const tabs = [
  { key: "all", label: "All" },
  { key: "document", label: "Document" },
  { key: "code", label: "Code" },
  // Conditionally shown when branches have previews:
  { key: "branch", label: "Branch Preview" },
];
```

When "Branch Preview" tab is active:
- Show a branch selector dropdown (populated from Redis keys or a list endpoint)
- Fetch `GET /ontology/graph/preview/{repo_id}/{branch}`
- Render using `BranchPreviewGraph` with diff coloring
- Show legend: Grey=unchanged, Green=added, Yellow=modified, Red=removed
- Show changed files list as context

### 4.9 List Available Branch Previews

**File**: `backend/app/api/endpoints/ontology.py`

```python
@router.get("/graph/branches/{repo_id}")
def list_branch_previews(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List all active branch previews for a repo."""
    from app.services.cache_service import cache_service
    pattern = f"preview_graph:{tenant_id}:{repo_id}:*"
    keys = cache_service.redis_client.keys(pattern) if cache_service.redis_client else []
    branches = []
    for key in keys:
        branch = key.split(":")[-1]
        data = cache_service.get_branch_preview(
            tenant_id=tenant_id, repo_id=repo_id, branch=branch
        )
        if data:
            branches.append({
                "branch": branch,
                "commit_hash": data.get("commit_hash", ""),
                "extracted_at": data.get("extracted_at", ""),
                "entity_count": len(data.get("entities", [])),
                "changed_files": len(data.get("changed_files", [])),
            })
    return branches
```

---

## Phase 4 Key Files to Modify

| File | Change |
|------|--------|
| `backend/app/services/cache_service.py` | Add `set_branch_preview()`, `get_branch_preview()`, `delete_branch_preview()` |
| `backend/app/tasks/code_analysis_tasks.py` | Add `branch_preview_extraction` task, modify `webhook_triggered_analysis` for branch routing |
| `backend/app/tasks/code_analysis_tasks.py` | Add `promote_branch_preview` task (PR merge → permanent SQL) |
| `backend/app/api/endpoints/webhooks.py` | Handle `pull_request` and `delete` events, route feature branches to preview |
| `backend/app/api/endpoints/ontology.py` | Add `GET /graph/preview/{repo_id}/{branch}` (on-the-fly merge) + `GET /graph/branches/{repo_id}` |
| `backend/app/schemas/ontology.py` | Add `BranchPreviewNode`, `BranchPreviewEdge`, `BranchPreviewGraphResponse` |
| `frontend/components/ontology/BranchPreviewGraph.tsx` | NEW — diff-aware graph rendering with color-coded nodes |
| `frontend/app/dashboard/ontology/page.tsx` | Add "Branch Preview" tab with branch selector |

---

## Backward Compatibility (All Phases)

- `initiative_id = NULL` everywhere means "All Projects" / "org-wide"
- ALL new query params are optional with None defaults
- Tenants that never create projects → everything works exactly as today
- Existing ConceptMapping table is untouched
- Phase 4: Feature branches write to Redis only — **zero impact on existing PostgreSQL data**
- Main branch pushes continue the existing permanent-write pipeline unchanged

## Cost Impact

- **Phase 1**: $0 additional AI cost (pure frontend/API restructuring)
- **Phase 2**: $0 additional AI cost (same extraction, just tags concepts with initiative_id)
- **Phase 3**: ~$0.02-0.05 per cross-project mapping run (same 3-tier approach)
- **Phase 4**: Same AI cost per file analysis (Gemini call). Redis storage is negligible (~1KB per branch preview, auto-expires in 7 days). No additional PostgreSQL storage for branches.

## Verification

- **Phase 1**: Upload a repo → only 1 row in code table (expandable to see files). Create a project, link repo + doc to it, select project → only those assets shown.
- **Phase 2**: Extract ontology for a project-linked doc → concepts tagged with initiative_id. Switch project in selector → graph shows only that project's concepts.
- **Phase 3**: Run cross-project mapping between two projects → discover shared concepts. View meta-graph → see project clusters with cross-project edges.
- **Phase 4**: Push to feature branch → webhook dispatches `branch_preview_extraction` → Redis stores preview → `GET /graph/preview/{repo}/{branch}` returns merged graph with diff annotations → frontend renders green/yellow/red nodes → merge PR → `promote_branch_preview` writes to PostgreSQL → Redis key cleaned up.
