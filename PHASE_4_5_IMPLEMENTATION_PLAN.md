# DokyDoc — Phase 4 & 5: Developer Implementation Plan
# Solution Architect Edition — Every file, every line, every step

---

## HOW TO READ THIS PLAN

Each task has:
- **Ticket ID** — reference in your sprint board (e.g. P4-01)
- **Priority** — P0 = blocks everything, P1 = blocks other tasks, P2 = independent
- **File(s)** — exact file path(s) relative to repo root
- **Why** — root cause / business reason
- **Current state** — exact lines in the file right now (read the file before editing)
- **What to change** — step-by-step with exact before/after code
- **Test commands** — how to verify it works
- **Risk** — what can break if done wrong

**Rules for all developers:**
1. Never edit a file without reading it first with `cat -n`
2. Every DB change needs an Alembic migration — never `ALTER TABLE` by hand
3. Wrap all new code integrations in try/except — these are non-breaking additions
4. Run `alembic upgrade head` after every migration before testing
5. All new endpoints need a tenant_id check — no exceptions
6. Phase 4 and Phase 5 can be developed in parallel — see ownership table at bottom
7. Phase 5 devs must NOT touch `validation_service.py` — that file belongs to Phase 4

---

## DEVELOPER OWNERSHIP (Parallelization Map)

| File | Owner |
|------|-------|
| `backend/app/services/validation_service.py` | **Phase 4 only** |
| `backend/app/tasks/document_pipeline.py` | Phase 4 only |
| `backend/app/services/code_analysis_service.py` | Phase 4 only |
| `backend/app/services/boe_context.py` | Phase 4 only (new file) |
| `backend/app/api/endpoints/analysis_results.py` | Phase 4 only |
| `backend/app/services/ai/industry_context.json` | Phase 5 only (new file) |
| `backend/app/services/ai/prompt_context.py` | Phase 5 only (new file) |
| `backend/app/services/ai/prompt_context_builder.py` | Phase 5 only (new file) |
| `backend/app/tasks/tenant_tasks.py` | Phase 5 only (new file) |
| `backend/app/services/ai/prompt_manager.py` | **Phase 5 only** (add `context` param) |
| `backend/app/services/business_ontology_service.py` | Phase 5 only |
| `backend/app/api/endpoints/documents.py` | Phase 5 only (new endpoints) |
| `backend/app/api/endpoints/tenants.py` | Phase 5 only (dispatch task) |
| `frontend/app/dashboard/analytics/page.tsx` | Phase 4 only |
| `frontend/app/dashboard/documents/[id]/page.tsx` | Phase 5 only |
| `frontend/app/dashboard/onboarding/page.tsx` | Phase 5 only (new file) |

Tasks within Phase 4 that can be parallelized: P4-02, P4-06, P4-07 have zero dependencies
on each other and can all be coded simultaneously. P4-01, P4-03, P4-04, P4-05 are sequential.

Tasks within Phase 5 that can be parallelized: P5-02, P5-04, P5-07 are fully independent.
P5-03 depends on P5-02. P5-05, P5-06 depend on P5-03. P5-08, P5-09 depend on P5-03.

---

# PHASE 4 — BOE-Aware Validation Engine

**Goal:** Cut Gemini API calls by 75–80% by sharing the Business Ontology Engine's
confirmed concept mappings with the validation engine. Concepts that are already
confirmed as matching (confidence >= 0.92) skip Gemini entirely.

**Sprint estimate:** 5–6 days for 2 developers working on Phase 4 tasks.

**Migration chain for Phase 4:**
```
s12a1 (existing) → s14a1 (new) → s14b1 (new)
```

---

## P4-01 — Pre-Atomize Document at Upload Time

**Ticket:** P4-01
**Priority:** P1 (unblocks P4-03 — validation needs atoms ready before scan starts)
**File:** `backend/app/tasks/document_pipeline.py`
**Lines to read first:** Lines 165–174 (the ontology extraction block)
**New migration:** `backend/alembic/versions/s14a1_atom_upload_flag.py`

### Why:
`atomize_document` is currently called lazily inside `validate_single_link`. This means
the first validation scan for a new document always pays full Gemini atomization cost.
If we atomize at upload time — right after ontology extraction — every subsequent
validation scan for that document is free (atoms are cached by document_id + version).
For tenants running frequent re-validation scans this is a 30–40% additional saving on
top of BOE context skipping.

### Current state (lines 168–174 of document_pipeline.py):
```python
            # SPRINT 3: Fire-and-forget ontology enrichment (non-blocking)
            # Document is already "completed" — user sees results immediately
            # Entity extraction runs in a separate Celery task
            if tenant_id:
                try:
                    from app.tasks.ontology_tasks import extract_ontology_entities
                    extract_ontology_entities.delay(document_id, tenant_id)
                    logger.info(f"🧠 Ontology extraction task enqueued for document {document_id}")
                except Exception as ontology_err:
                    logger.warning(f"Failed to enqueue ontology task (non-critical): {ontology_err}")
```

### Step 1 — Add pre-atomization block after line 174:
In `backend/app/tasks/document_pipeline.py`, immediately after the ontology extraction
try/except block (after line 174), add a new block:

```python
            # PHASE 4 P4-01: Pre-atomize BRD/SRS/FRD documents at upload time
            # This caches atoms so validation scans never pay Gemini atomization cost again.
            # Only BRD/SRS/FRD document types are worth atomizing — plain API docs are not.
            BRD_TYPES = {"brd", "srs", "frd", "prd", "requirements", "specification"}
            doc_type_lower = (getattr(document, "document_type", "") or "").lower()
            should_atomize = any(t in doc_type_lower for t in BRD_TYPES) or doc_type_lower in BRD_TYPES

            if tenant_id and should_atomize:
                try:
                    from app.services.validation_service import ValidationService
                    import asyncio
                    vs = ValidationService()
                    # We are already inside run_async() context — use asyncio directly
                    asyncio.ensure_future(
                        vs.atomize_document(
                            db=db,
                            document=document,
                            tenant_id=tenant_id,
                            user_id=document.owner_id,
                        )
                    )
                    logger.info(f"Pre-atomization queued for document {document_id} (type={doc_type_lower})")
                except Exception as atom_err:
                    logger.warning(f"Pre-atomization failed (non-critical): {atom_err}")
```

**Note on async:** `_run_async_pipeline` is already an `async def` function running
inside `run_async()`. You can safely `await` or use `asyncio.ensure_future()`. Prefer
`await` for simplicity:

```python
            if tenant_id and should_atomize:
                try:
                    from app.services.validation_service import ValidationService
                    vs = ValidationService()
                    await vs.atomize_document(
                        db=db,
                        document=document,
                        tenant_id=tenant_id,
                        user_id=document.owner_id,
                    )
                    logger.info(f"Pre-atomization complete for document {document_id}")
                except Exception as atom_err:
                    logger.warning(f"Pre-atomization failed (non-critical): {atom_err}")
```

This is the correct form — `_run_async_pipeline` is already `async def` at line 92.

### Step 2 — Create migration s14a1:
Create `backend/alembic/versions/s14a1_atom_upload_flag.py`:

```python
"""Add atomized_at_upload flag to requirement_atoms

Revision ID: s14a1
Revises: s12a1
Create Date: 2026-04-05

Purpose: Tracks whether a document was pre-atomized at upload time vs on-demand
during validation. Used by the analytics dashboard to calculate BOE coverage.
"""
import sqlalchemy as sa
from alembic import op

revision = 's14a1'
down_revision = 's12a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'requirement_atoms',
        sa.Column('atomized_at_upload', sa.Boolean(), nullable=False, server_default='false')
    )
    # Index for analytics queries: "how many atoms were pre-atomized?"
    op.create_index(
        'ix_requirement_atoms_atomized_at_upload',
        'requirement_atoms',
        ['atomized_at_upload'],
    )


def downgrade() -> None:
    op.drop_index('ix_requirement_atoms_atomized_at_upload', table_name='requirement_atoms')
    op.drop_column('requirement_atoms', 'atomized_at_upload')
```

### Step 3 — Set the flag in atomize_document:
After the migration adds the column, update `atomize_document` in
`validation_service.py` to accept and pass through an `atomized_at_upload` flag.
This is a minor addition — at line 201 of `validation_service.py` where
`crud.requirement_atom.create_atoms_bulk(...)` is called, add `atomized_at_upload=False`
as default. The pre-atomization call from pipeline sets it to `True`.

Add optional param to `atomize_document` signature at line 122:
```python
# BEFORE:
async def atomize_document(self, db, document, tenant_id: int, user_id: int) -> list:

# AFTER:
async def atomize_document(self, db, document, tenant_id: int, user_id: int,
                           atomized_at_upload: bool = False) -> list:
```

Then at line 201 (the `create_atoms_bulk` call), thread the flag through:
```python
        new_atoms = crud.requirement_atom.create_atoms_bulk(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            document_version=doc_version,
            atoms_data=atoms_data,
            atomized_at_upload=atomized_at_upload,
        )
```

Update the pipeline call to pass `atomized_at_upload=True`.

### Test commands:
```bash
# Run migration
cd /home/user/dokydoc/backend
alembic upgrade head

# Upload a BRD document and check atoms are created immediately
# (before any validation scan is run)
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_brd.pdf" \
  -F "title=Test BRD" \
  -F "document_type=brd"

# After upload completes, query atoms table
psql $DATABASE_URL -c "SELECT id, document_id, atomized_at_upload FROM requirement_atoms WHERE atomized_at_upload = true LIMIT 5;"
# Expected: rows with atomized_at_upload = true
```

### Risk: LOW — try/except wrapper means this never blocks document upload.

---

## P4-02 — BOEContext Shared Context Object

**Ticket:** P4-02
**Priority:** P1 (P4-03 and P4-04 depend on this)
**File:** `backend/app/services/boe_context.py` (NEW FILE)
**Parallelizable:** YES — can be coded simultaneously with P4-06 and P4-07

### Why:
The validation engine currently has zero knowledge of what the BOE already confirmed.
Every RequirementAtom goes through a Gemini call even when there is an existing
confirmed mapping with 0.95 confidence saying "PaymentService implements payment_processing".
BOEContext is a plain dataclass that gets built once per document/component pair and
carries all confirmed mappings into the validation engine.

### What to create:
Create new file `backend/app/services/boe_context.py`:

```python
"""
BOEContext — Business Ontology Engine Shared Context

Built once per document/component pair before validation begins.
Carries confirmed concept mappings into the validation engine so
atoms whose concepts are already confirmed can skip Gemini.

Cache key: "{tenant_id}:{document_id}:{component_id}"
TTL: Not cached in Redis — rebuilt per validation scan (cheap DB query).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session


@dataclass
class BOEContext:
    """
    Immutable snapshot of BOE knowledge for one document/component pair.
    Build via BOEContext.build() — do not instantiate directly.
    """
    tenant_id: int
    document_id: int
    component_id: int

    # List of confirmed cross-graph mappings (doc concept ↔ code concept)
    # Each dict: {doc_concept_name, code_concept_name, confidence, mapping_id}
    confirmed_mappings: List[Dict] = field(default_factory=list)

    # Concept names that exist only in the document graph (code gaps)
    document_only_concepts: List[str] = field(default_factory=list)

    # Concept names that exist only in the code graph (undocumented implementations)
    code_only_concepts: List[str] = field(default_factory=list)

    # Auto-approved pairs: concept names with confidence >= 0.92.
    # Stored as a set for O(1) membership test.
    _auto_approved_set: set = field(default_factory=set, repr=False)

    # O(1) lookup: doc_concept_name -> mapping dict
    _mapping_index: Dict[str, Dict] = field(default_factory=dict, repr=False)

    # Metadata
    built_at: float = field(default_factory=time.time)
    cache_key: str = ""

    AUTO_APPROVE_THRESHOLD: float = 0.92

    @classmethod
    def build(
        cls,
        db: Session,
        document_id: int,
        component_id: int,
        tenant_id: int,
    ) -> "BOEContext":
        """
        Query the DB and build a BOEContext for this document/component pair.

        Uses crud.concept_mapping.get_confirmed() which returns ConceptMapping
        objects with document_concept and code_concept relationships loaded
        (see backend/app/crud/crud_concept_mapping.py line 112).

        Uses crud.ontology_concept.get_by_source_type() to find doc-only
        and code-only concept names.

        Args:
            db: SQLAlchemy session
            document_id: The document being validated
            component_id: The code component being validated against
            tenant_id: Tenant ID for data isolation

        Returns:
            Populated BOEContext instance
        """
        from app import crud

        # 1. Load all confirmed cross-graph mappings for this tenant
        confirmed = crud.concept_mapping.get_confirmed(db, tenant_id=tenant_id)

        confirmed_mappings = []
        auto_approved_set: set = set()
        mapping_index: Dict[str, Dict] = {}

        for m in confirmed:
            doc_name = (m.document_concept.name or "").strip().lower()
            code_name = (m.code_concept.name or "").strip().lower()
            if not doc_name or not code_name:
                continue

            entry = {
                "doc_concept_name": doc_name,
                "code_concept_name": code_name,
                "confidence": m.confidence_score,
                "mapping_id": m.id,
                "relationship_type": m.relationship_type,
            }
            confirmed_mappings.append(entry)
            mapping_index[doc_name] = entry

            if m.confidence_score >= cls.AUTO_APPROVE_THRESHOLD:
                auto_approved_set.add(doc_name)
                auto_approved_set.add(code_name)

        # 2. Load document-only and code-only concepts for this tenant
        doc_only: List[str] = []
        code_only: List[str] = []

        try:
            doc_concepts = crud.ontology_concept.get_by_source_type(
                db, source_type="document", tenant_id=tenant_id
            )
            code_concepts = crud.ontology_concept.get_by_source_type(
                db, source_type="code", tenant_id=tenant_id
            )

            confirmed_doc_names = {m["doc_concept_name"] for m in confirmed_mappings}
            confirmed_code_names = {m["code_concept_name"] for m in confirmed_mappings}

            doc_only = [
                c.name.strip().lower()
                for c in (doc_concepts or [])
                if c.name and c.name.strip().lower() not in confirmed_doc_names
            ]
            code_only = [
                c.name.strip().lower()
                for c in (code_concepts or [])
                if c.name and c.name.strip().lower() not in confirmed_code_names
            ]
        except Exception:
            # Non-fatal: just skip gap calculation if concepts not available
            pass

        cache_key = f"{tenant_id}:{document_id}:{component_id}"

        ctx = cls(
            tenant_id=tenant_id,
            document_id=document_id,
            component_id=component_id,
            confirmed_mappings=confirmed_mappings,
            document_only_concepts=doc_only,
            code_only_concepts=code_only,
            cache_key=cache_key,
        )
        # Bypass frozen dataclass restriction for private fields
        object.__setattr__(ctx, '_auto_approved_set', auto_approved_set)
        object.__setattr__(ctx, '_mapping_index', mapping_index)
        return ctx

    def is_auto_approved(self, concept_name: str) -> bool:
        """
        Check if a concept name is already confirmed with confidence >= 0.92.
        O(1) set lookup — safe to call in a tight loop.

        Args:
            concept_name: The concept name to check (case-insensitive)

        Returns:
            True if this concept can skip Gemini validation
        """
        if not concept_name:
            return False
        return concept_name.strip().lower() in self._auto_approved_set

    def get_mapping_for_concept(self, concept_name: str) -> Optional[Dict]:
        """
        Return the confirmed mapping dict for a document concept name, or None.
        O(1) dict lookup.

        Args:
            concept_name: Document concept name (case-insensitive)

        Returns:
            Dict with keys: doc_concept_name, code_concept_name, confidence,
            mapping_id, relationship_type — or None if not found
        """
        if not concept_name:
            return None
        return self._mapping_index.get(concept_name.strip().lower())

    @property
    def coverage_pct(self) -> float:
        """
        Percentage of document concepts that have confirmed mappings.
        Used by the cost savings analytics widget (P4-09).
        """
        total = len(self.confirmed_mappings) + len(self.document_only_concepts)
        if total == 0:
            return 0.0
        return round(len(self.confirmed_mappings) / total * 100, 1)

    @property
    def auto_approved_count(self) -> int:
        """Number of doc-side concept names that will skip Gemini."""
        return len(self._auto_approved_set)

    def __repr__(self) -> str:
        return (
            f"<BOEContext tenant={self.tenant_id} doc={self.document_id} "
            f"comp={self.component_id} confirmed={len(self.confirmed_mappings)} "
            f"auto_approved={self.auto_approved_count} "
            f"coverage={self.coverage_pct}%>"
        )
```

### Test commands:
```bash
# Unit test — run from backend/
python3 -c "
from app.db.session import SessionLocal
from app.services.boe_context import BOEContext
db = SessionLocal()
ctx = BOEContext.build(db, document_id=1, component_id=1, tenant_id=1)
print(ctx)
print('Auto-approved:', ctx.auto_approved_count)
print('Coverage:', ctx.coverage_pct, '%')
db.close()
"
# Expected: BOEContext repr with counts, no exceptions
```

### Risk: LOW — pure new file, nothing imports it yet.


---

## P4-03 — Validation Engine Reads BOEContext

**Ticket:** P4-03
**Priority:** P1 (core of Phase 4 — depends on P4-02 being merged first)
**File:** `backend/app/services/validation_service.py`
**Lines to modify:** 211 (validate_single_link signature), 256–302 (forward passes section)

### Why:
With BOEContext available, `validate_single_link` can short-circuit Gemini calls for
atoms whose concepts are already confirmed. The auto-approved check happens before the
`call_gemini_for_typed_validation` loop. Document-only concepts with no code counterpart
automatically generate MISSING mismatches with zero AI cost.

### Current state — validate_single_link signature (line 211):
```python
    async def validate_single_link(self, link: DocumentCodeLink, user_id: int, tenant_id: int = None):
```

### Step 1 — Add boe_context param to signature:
```python
# BEFORE (line 211):
    async def validate_single_link(self, link: DocumentCodeLink, user_id: int, tenant_id: int = None):

# AFTER:
    async def validate_single_link(
        self,
        link: DocumentCodeLink,
        user_id: int,
        tenant_id: int = None,
        boe_context: "BOEContext" = None,
    ):
```

Add import at top of `validation_service.py` (after existing imports, around line 22):
```python
# Phase 4: BOE-aware validation
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.boe_context import BOEContext
```

### Step 2 — Insert BOE auto-approve filter before forward passes (after line 282):
The current code at lines 288–302 builds `forward_tasks` and gathers them. Insert the
following block BEFORE line 288 (the `if gemini_service:` check for forward tasks):

```python
                        # ── Step 3.5: BOE auto-approve filter ────────────────────────
                        # Skip Gemini for atoms whose concepts are already confirmed by BOE
                        if boe_context is not None:
                            filtered_atoms_by_type: dict[str, list] = {}
                            skipped_count = 0
                            for atype, atype_atoms in atoms_by_type.items():
                                non_approved = []
                                for atom_dict in atype_atoms:
                                    atom_content_lower = (atom_dict.get("content", "") or "").lower()
                                    if boe_context.is_auto_approved(atom_content_lower):
                                        skipped_count += 1
                                        # Auto-approved: no mismatch, no Gemini call
                                        self.logger.debug(
                                            f"[Link {link.id}] BOE auto-approved atom: "
                                            f"{atom_dict.get('atom_id')} — skipping Gemini"
                                        )
                                    else:
                                        non_approved.append(atom_dict)
                                if non_approved:
                                    filtered_atoms_by_type[atype] = non_approved
                            if skipped_count > 0:
                                self.logger.info(
                                    f"[Link {link.id}] BOE skipped {skipped_count} atoms "
                                    f"({len(atoms) - skipped_count} remaining for Gemini)"
                                )
                            atoms_by_type = filtered_atoms_by_type
```

### Step 3 — Auto-create MISSING mismatches for document_only_concepts:
After the forward passes gather (after line 345 in current code, which is the end
of the `for result in forward_results:` loop), add:

```python
                        # ── Step 4.5: BOE document-only gaps → auto MISSING mismatches ──
                        # These concepts exist in the document but have no code counterpart.
                        # We know this from BOE without any Gemini call.
                        if boe_context is not None and boe_context.document_only_concepts:
                            for gap_concept in boe_context.document_only_concepts[:20]:  # cap at 20
                                try:
                                    crud.mismatch.create_with_link(
                                        db=db,
                                        obj_in={
                                            "mismatch_type": "MISSING_IMPLEMENTATION",
                                            "severity": "medium",
                                            "title": f"No code found for: {gap_concept}",
                                            "description": (
                                                f"The business concept '{gap_concept}' is documented "
                                                f"but has no corresponding implementation in the codebase. "
                                                f"(Detected by BOE gap analysis — no Gemini call)"
                                            ),
                                            "direction": "forward",
                                            "confidence": 0.85,
                                        },
                                        link_id=link.id,
                                        owner_id=user_id,
                                        tenant_id=tenant_id,
                                    )
                                except Exception as gap_err:
                                    self.logger.debug(f"Could not store BOE gap mismatch: {gap_err}")
```

### Test commands:
```bash
# Run a validation scan and check logs for "BOE skipped N atoms"
docker-compose logs backend | grep "BOE skipped"
# Expected: lines like "[Link 3] BOE skipped 5 atoms (2 remaining for Gemini)"

# Check that mismatches with "Detected by BOE gap analysis" description were created
psql $DATABASE_URL -c "SELECT title, description FROM mismatches WHERE description LIKE '%BOE gap%' LIMIT 5;"
```

### Risk: MEDIUM — modifying the core validation path. The boe_context defaults to None
which preserves 100% existing behavior when the caller doesn't pass it. The auto-approve
check only skips atoms — it never creates false negatives for non-skipped atoms.

---

## P4-04 — Batch Context Building in run_validation_scan

**Ticket:** P4-04
**Priority:** P1 (depends on P4-02 and P4-03)
**File:** `backend/app/services/validation_service.py`
**Lines to modify:** 103–105 (the asyncio.gather call for validate_single_link tasks)

### Why:
P4-03 added the `boe_context` param to `validate_single_link` but P4-03 alone does
nothing — the caller (`run_validation_scan`) has to actually build and pass the contexts.
We build all BOEContexts before the gather call so the DB queries run once per document
rather than once per link.

### Current state (lines 103–105 of validation_service.py):
```python
                # SPRINT 2 Phase 6: Pass tenant_id to validate_single_link
                tasks = [self.validate_single_link(link, user_id, tenant_id) for link in links]
                results = await asyncio.gather(*tasks, return_exceptions=True)
```

### What to change — replace lines 103–105 with:
```python
                # PHASE 4 P4-04: Build BOEContext per document before the gather call.
                # One DB query per document (not per link) — amortized cost is near zero.
                boe_contexts: dict[int, "BOEContext"] = {}
                if tenant_id:
                    try:
                        from app.services.boe_context import BOEContext
                        # Unique document IDs across all links
                        unique_doc_ids = list({link.document_id for link in links})
                        for doc_id in unique_doc_ids:
                            # Use component_id=0 as a sentinel — BOEContext uses
                            # document-level confirmed mappings, not component-specific.
                            boe_contexts[doc_id] = BOEContext.build(
                                db=db,
                                document_id=doc_id,
                                component_id=0,
                                tenant_id=tenant_id,
                            )
                        self.logger.info(
                            f"Built {len(boe_contexts)} BOEContext(s) for validation scan. "
                            f"Total auto-approved concepts: "
                            f"{sum(c.auto_approved_count for c in boe_contexts.values())}"
                        )
                    except Exception as boe_err:
                        self.logger.warning(
                            f"BOEContext build failed (non-critical, proceeding without): {boe_err}"
                        )

                # Pass BOEContext per link (None if build failed or no tenant)
                tasks = [
                    self.validate_single_link(
                        link, user_id, tenant_id,
                        boe_context=boe_contexts.get(link.document_id)
                    )
                    for link in links
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Test commands:
```bash
# Trigger a full validation scan via API
curl -X POST http://localhost:8000/api/v1/analysis/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [1, 2]}'

# Check logs for BOEContext build summary
docker-compose logs backend | grep "BOEContext"
# Expected: "Built 2 BOEContext(s) for validation scan. Total auto-approved concepts: N"
```

### Risk: LOW — try/except ensures scan proceeds even if BOEContext build throws.

---

## P4-05 — Validation Writes Back to BOE (Confidence Calibration)

**Ticket:** P4-05
**Priority:** P2 (depends on P4-03, P4-06)
**File:** `backend/app/services/validation_service.py`
**New migration:** `backend/alembic/versions/s14b1_concept_mapping_validation_fields.py`

### Why:
Validation results are ground truth about whether a concept mapping is correct.
If Gemini says "MATCH with 0.95 confidence", the corresponding ConceptMapping should
increase its confidence score. If "MISMATCH", it should decrease. Over time this
keeps the BOE auto-approve threshold calibrated to reality — preventing false
auto-approvals as the codebase evolves.

### Step 1 — Create migration s14b1:
Create `backend/alembic/versions/s14b1_concept_mapping_validation_fields.py`:

```python
"""Add last_validated_at and validation_verdict to concept_mappings

Revision ID: s14b1
Revises: s14a1
Create Date: 2026-04-05

Purpose: Stores the most recent validation outcome on each concept mapping
so the confidence calibration loop can update confidence_score based on
real validation results rather than only on initial mapping confidence.
"""
import sqlalchemy as sa
from alembic import op

revision = 's14b1'
down_revision = 's14a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'concept_mappings',
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'concept_mappings',
        sa.Column(
            'validation_verdict',
            sa.String(20),
            nullable=True,
        )
        # Allowed values: 'MATCH', 'PARTIAL_MATCH', 'MISMATCH', None (never validated)
    )
    op.create_index(
        'ix_concept_mappings_last_validated_at',
        'concept_mappings',
        ['last_validated_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_concept_mappings_last_validated_at', table_name='concept_mappings')
    op.drop_column('concept_mappings', 'validation_verdict')
    op.drop_column('concept_mappings', 'last_validated_at')
```

### Step 2 — Add columns to ConceptMapping model:
In `backend/app/models/concept_mapping.py`, after line 65 (the `feedback_at` column),
add:

```python
    # Phase 4: Validation feedback loop — set by validation_service after each scan
    last_validated_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validation_verdict: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'MATCH', 'PARTIAL_MATCH', 'MISMATCH' — None means never validated
```

### Step 3 — Call calibration in validate_single_link:
After the mismatch creation loop (after all `crud.mismatch.create_with_link` calls
for forward results, approximately line 345 in the current file), add:

```python
                        # ── Step 4.8: Write calibration verdicts back to BOE ─────────
                        # For each forward mismatch, find the matching ConceptMapping
                        # and update its confidence via _calibrate_confidence().
                        if boe_context is not None and gemini_service:
                            try:
                                from datetime import datetime, timezone
                                for result in forward_results:
                                    if isinstance(result, Exception):
                                        continue
                                    for m in result.get("mismatches", []):
                                        verdict = m.get("mismatch_type", "MISMATCH")
                                        val_confidence = m.get("confidence", 0.5)
                                        # Normalise verdict to calibration categories
                                        if verdict in ("MATCH", "CONSISTENT"):
                                            cal_verdict = "MATCH"
                                        elif verdict in ("PARTIAL_MATCH", "PARTIAL"):
                                            cal_verdict = "PARTIAL_MATCH"
                                        else:
                                            cal_verdict = "MISMATCH"

                                        # Find the ConceptMapping for this atom's concept
                                        atom_content = m.get("title", "")
                                        mapping_entry = boe_context.get_mapping_for_concept(
                                            atom_content.lower()
                                        ) if atom_content else None

                                        if mapping_entry:
                                            mapping_id = mapping_entry["mapping_id"]
                                            old_conf = mapping_entry["confidence"]
                                            new_conf = self._calibrate_confidence(
                                                old_confidence=old_conf,
                                                validation_verdict=cal_verdict,
                                                validation_confidence=val_confidence,
                                            )
                                            # Update DB record
                                            cm = db.query(
                                                __import__('app.models', fromlist=['ConceptMapping']).ConceptMapping
                                            ).filter_by(id=mapping_id).first()
                                            if cm:
                                                cm.confidence_score = new_conf
                                                cm.last_validated_at = datetime.now(timezone.utc)
                                                cm.validation_verdict = cal_verdict
                                                db.add(cm)
                                db.commit()
                            except Exception as cal_err:
                                self.logger.debug(f"Confidence calibration failed (non-fatal): {cal_err}")
                                db.rollback()
```

### Test commands:
```bash
alembic upgrade head

# After a validation scan, check that concept_mappings have updated confidence
psql $DATABASE_URL -c "
  SELECT id, confidence_score, last_validated_at, validation_verdict
  FROM concept_mappings
  WHERE last_validated_at IS NOT NULL
  LIMIT 5;
"
# Expected: rows with non-null last_validated_at and a verdict
```

### Risk: MEDIUM — writes to concept_mappings during validation. The try/except and
db.rollback() ensure a calibration failure never corrupts the validation result.

---

## P4-06 — Confidence Calibration Function

**Ticket:** P4-06
**Priority:** P1 (P4-05 depends on this)
**File:** `backend/app/services/validation_service.py`
**Parallelizable:** YES — pure function, no dependencies on other P4 tasks

### Why:
The calibration math needs to live in a single place so it can be unit tested in
isolation. Mixing it inline in validate_single_link would make the logic invisible.

### What to add — new static method on ValidationService:
Add after `atomize_document` method (after line 209 in validation_service.py), before
`validate_single_link` at line 211:

```python
    @staticmethod
    def _calibrate_confidence(
        old_confidence: float,
        validation_verdict: str,
        validation_confidence: float,
    ) -> float:
        """
        Update a concept mapping's confidence score based on a validation result.

        The delta is weighted by the validation_confidence (how sure Gemini was
        about the verdict). A low-confidence MISMATCH verdict shouldn't tank a
        well-established mapping.

        Args:
            old_confidence: Current confidence_score on the ConceptMapping (0.0-1.0)
            validation_verdict: 'MATCH', 'PARTIAL_MATCH', or 'MISMATCH'
            validation_confidence: Gemini's confidence in its verdict (0.0-1.0)

        Returns:
            New confidence score, clamped to [0.0, 1.0]

        Examples:
            _calibrate_confidence(0.80, 'MATCH', 0.90)         -> 0.89  (0.80 + 0.10*0.90)
            _calibrate_confidence(0.80, 'PARTIAL_MATCH', 0.85) -> 0.817 (0.80 + 0.02*0.85)
            _calibrate_confidence(0.80, 'MISMATCH', 0.95)      -> 0.657 (0.80 - 0.15*0.95)
            _calibrate_confidence(0.05, 'MISMATCH', 1.00)      -> 0.0   (clamped)
            _calibrate_confidence(0.98, 'MATCH', 1.00)         -> 1.0   (clamped)
        """
        DELTAS = {
            "MATCH": +0.10,
            "PARTIAL_MATCH": +0.02,
            "MISMATCH": -0.15,
        }
        delta = DELTAS.get(validation_verdict, 0.0)
        weighted_delta = delta * max(0.0, min(1.0, validation_confidence))
        new_confidence = old_confidence + weighted_delta
        return max(0.0, min(1.0, new_confidence))
```

### Test commands:
```bash
python3 -c "
from app.services.validation_service import ValidationService
cal = ValidationService._calibrate_confidence

# Test MATCH
result = cal(0.80, 'MATCH', 0.90)
assert abs(result - 0.89) < 0.001, f'Expected 0.89 got {result}'

# Test MISMATCH
result = cal(0.80, 'MISMATCH', 0.95)
assert abs(result - 0.6575) < 0.001, f'Expected 0.6575 got {result}'

# Test floor clamp
result = cal(0.05, 'MISMATCH', 1.00)
assert result == 0.0, f'Expected 0.0 got {result}'

# Test ceiling clamp
result = cal(0.98, 'MATCH', 1.00)
assert result == 1.0, f'Expected 1.0 got {result}'

print('All calibration tests passed')
"
```

### Risk: LOW — pure function with no side effects.

---

## P4-07 — Code Engine Notifies BOE on Completion

**Ticket:** P4-07
**Priority:** P2 (nice-to-have for keeping BOE current — does not block validation)
**File:** `backend/app/services/code_analysis_service.py`
**Lines to read:** ~787–870 (the `_extract_ontology_from_component` method)
**Parallelizable:** YES — independent of all other P4 tasks

### Why:
Currently, after a repository analysis completes, the cross-graph mapping task
(`run_cross_graph_mapping`) must be manually triggered or runs on a schedule.
Wiring an automatic dispatch here means the BOE is refreshed within seconds of
new code being analyzed — keeping auto-approve confidence scores current.

### Where to add — find the successful analysis completion point:
Read `backend/app/services/code_analysis_service.py` from line 780 onward.
Find the method that signals completion of the full repository scan (look for
`logger.info` lines mentioning "analysis complete" or the final return from
the main analysis method). The cross-graph mapping call should fire after all
component analyses have been written to DB.

Search for the repository-level completion signal:
```bash
grep -n "repo.*complete\|analysis.*complete\|repository.*finish" \
  backend/app/services/code_analysis_service.py
```

At the found line, add after a successful return from `analyze_repository` (or
equivalent method):

```python
            # PHASE 4 P4-07: Trigger cross-graph mapping after code analysis
            # This keeps BOE confidence scores fresh — new code may confirm or
            # refute existing document-concept mappings.
            try:
                from app.tasks.ontology_tasks import run_cross_graph_mapping
                run_cross_graph_mapping.delay(tenant_id)
                self.logger.info(
                    f"Cross-graph mapping queued after repo analysis for tenant {tenant_id}"
                )
            except Exception as mapping_err:
                self.logger.warning(
                    f"Failed to dispatch cross-graph mapping (non-critical): {mapping_err}"
                )
```

### Test commands:
```bash
# Trigger a repo analysis and check logs for the dispatch
curl -X POST http://localhost:8000/api/v1/repositories/{repo_id}/analyze \
  -H "Authorization: Bearer $TOKEN"

docker-compose logs backend | grep "Cross-graph mapping queued"
# Expected: "Cross-graph mapping queued after repo analysis for tenant N"
```

### Risk: LOW — try/except wrapper. Worst case: mapping doesn't auto-trigger (same
behavior as today).


---

## P4-08 — Unified Analysis Orchestrator Endpoint

**Ticket:** P4-08
**Priority:** P2 (quality-of-life for frontend — not a blocker)
**File:** `backend/app/api/endpoints/analysis_results.py`
**Lines to read:** Lines 1–60 (existing router setup)

### Why:
The frontend currently has to make 3 separate API calls to run a full analysis
sequence: (1) trigger document analysis, (2) trigger code analysis, (3) trigger
validation scan. This endpoint wraps all three in a single call with a single
background task chain.

### What to add — new endpoint after existing routes:
In `backend/app/api/endpoints/analysis_results.py`, after the existing endpoints,
add:

```python
from pydantic import BaseModel
from typing import Optional

class FullAnalysisRequest(BaseModel):
    document_id: int
    repository_id: int
    force_reanalyze: bool = False  # Re-run even if results exist


class FullAnalysisResponse(BaseModel):
    status: str
    message: str
    document_id: int
    repository_id: int
    validation_queued: bool


@router.post(
    "/run-full",
    response_model=FullAnalysisResponse,
    summary="Run full 4-engine analysis sequence",
)
async def run_full_analysis(
    request: FullAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    POST /api/v1/analysis/run-full

    Triggers the complete DokyDoc analysis pipeline in sequence:
    1. Document ontology extraction (if not already done)
    2. Cross-graph mapping (BOE refresh)
    3. Validation scan against the linked repository

    The endpoint returns immediately (202) with a job reference.
    All heavy work happens in background Celery tasks.

    Args:
        document_id: ID of the document to analyze
        repository_id: ID of the code repository to validate against
        force_reanalyze: If true, re-runs even if fresh results exist
    """
    logger = analysis_endpoints.logger

    # 1. Verify document belongs to tenant
    document = crud.document.get(db=db, id=request.document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found for this tenant"
        )

    # 2. Verify repository belongs to tenant
    repo = crud.code_component.get_repository(
        db=db, repository_id=request.repository_id, tenant_id=tenant_id
    )
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {request.repository_id} not found for this tenant"
        )

    logger.info(
        f"run-full analysis requested: doc={request.document_id} "
        f"repo={request.repository_id} tenant={tenant_id}"
    )

    # 3. Queue ontology extraction (idempotent — skips if atoms are fresh)
    try:
        from app.tasks.ontology_tasks import extract_ontology_entities
        extract_ontology_entities.delay(request.document_id, tenant_id)
    except Exception as e:
        logger.warning(f"Could not enqueue ontology extraction: {e}")

    # 4. Queue cross-graph mapping refresh
    try:
        from app.tasks.ontology_tasks import run_cross_graph_mapping
        run_cross_graph_mapping.delay(tenant_id)
    except Exception as e:
        logger.warning(f"Could not enqueue cross-graph mapping: {e}")

    # 5. Queue validation scan (runs after the above tasks via Celery chain)
    validation_queued = False
    try:
        from app.tasks.validation_tasks import run_validation_scan_task
        run_validation_scan_task.delay(
            user_id=current_user.id,
            document_ids=[request.document_id],
            tenant_id=tenant_id,
        )
        validation_queued = True
    except Exception as e:
        logger.warning(f"Could not enqueue validation scan: {e}")

    return FullAnalysisResponse(
        status="queued",
        message="Full analysis pipeline queued. Check document status for progress.",
        document_id=request.document_id,
        repository_id=request.repository_id,
        validation_queued=validation_queued,
    )
```

**Note:** If `app.tasks.validation_tasks` does not exist, check whether the validation
scan runs through `app.tasks` directly or as a method call. Adjust the import path
to match what's in `worker.py`. The key pattern is: queue it as a Celery task, not
an inline `await`.

### Test commands:
```bash
curl -X POST http://localhost:8000/api/v1/analysis/run-full \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id": 1, "repository_id": 1}'
# Expected: {"status": "queued", "message": "...", "validation_queued": true}
```

### Risk: LOW — queues tasks, returns immediately. Individual task failures don't
affect the response.

---

## P4-09 — Cost Savings Analytics Widget

**Ticket:** P4-09
**Priority:** P2 (business value visibility — not a technical blocker)
**File:** `frontend/app/dashboard/analytics/page.tsx`

### Why:
Stakeholders need to see that Phase 4 is actually saving money. The widget shows
BOE coverage %, total Gemini calls avoided this month, and estimated INR savings.
This data must come from a backend endpoint — see data requirements below.

### Backend — new endpoint (add to analysis_results.py):
```python
@router.get("/boe-savings-summary")
def get_boe_savings_summary(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    GET /api/v1/analysis/boe-savings-summary

    Returns BOE coverage metrics for the analytics dashboard:
    - confirmed_mapping_count: total confirmed cross-graph mappings
    - auto_approved_count: mappings with confidence >= 0.92 (skip Gemini)
    - coverage_pct: auto_approved / total document concepts * 100
    - estimated_calls_saved_this_month: rough count from validation logs
    - estimated_inr_saved: calls_saved * avg_gemini_cost_per_call
    """
    try:
        confirmed = crud.concept_mapping.get_confirmed(db, tenant_id=tenant_id)
        auto_approved = [m for m in confirmed if m.confidence_score >= 0.92]

        # Rough savings estimate: avg Gemini validation call costs ~₹0.08
        AVG_CALL_COST_INR = 0.08
        # Estimate calls saved as auto_approved_count * 2 (forward + reverse pass)
        calls_saved_estimate = len(auto_approved) * 2

        return {
            "confirmed_mapping_count": len(confirmed),
            "auto_approved_count": len(auto_approved),
            "coverage_pct": round(
                len(auto_approved) / max(len(confirmed), 1) * 100, 1
            ),
            "estimated_calls_saved_this_month": calls_saved_estimate,
            "estimated_inr_saved": round(calls_saved_estimate * AVG_CALL_COST_INR, 2),
        }
    except Exception as e:
        return {
            "confirmed_mapping_count": 0,
            "auto_approved_count": 0,
            "coverage_pct": 0.0,
            "estimated_calls_saved_this_month": 0,
            "estimated_inr_saved": 0.0,
        }
```

### Frontend — add BOE savings card to analytics page:
In `frontend/app/dashboard/analytics/page.tsx`, after the existing cost overview
cards (look for the `DollarSign` icon card), add a new card component:

```tsx
{/* BOE Coverage & Cost Savings Card */}
<div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
  <div className="flex items-center justify-between mb-4">
    <div className="flex items-center gap-2">
      <div className="p-2 bg-green-100 rounded-lg">
        <Zap className="h-5 w-5 text-green-600" />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900">BOE Coverage</h3>
        <p className="text-xs text-gray-500">Gemini calls avoided by ontology engine</p>
      </div>
    </div>
  </div>

  {boeSavings ? (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-600">Auto-approved concepts</span>
        <span className="font-bold text-green-700">
          {boeSavings.auto_approved_count} / {boeSavings.confirmed_mapping_count}
        </span>
      </div>

      {/* Coverage progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className="bg-green-500 h-2 rounded-full transition-all duration-500"
          style={{ width: `${boeSavings.coverage_pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 text-right">{boeSavings.coverage_pct}% coverage</p>

      <div className="pt-2 border-t border-gray-100 flex justify-between">
        <div>
          <p className="text-xs text-gray-500">Calls saved (est.)</p>
          <p className="font-semibold text-gray-900">{boeSavings.estimated_calls_saved_this_month}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">INR saved (est.)</p>
          <p className="font-semibold text-green-700">₹{boeSavings.estimated_inr_saved}</p>
        </div>
      </div>
    </div>
  ) : (
    <p className="text-sm text-gray-400 text-center py-4">Loading BOE metrics...</p>
  )}
</div>
```

Add state and fetch:
```tsx
const [boeSavings, setBoeSavings] = useState<BoeSavings | null>(null)

interface BoeSavings {
  confirmed_mapping_count: number
  auto_approved_count: number
  coverage_pct: number
  estimated_calls_saved_this_month: number
  estimated_inr_saved: number
}

// Inside useEffect or fetchData:
const savingsRes = await api.get('/api/v1/analysis/boe-savings-summary')
setBoeSavings(savingsRes.data)
```

### Test commands:
```bash
# Backend endpoint
curl http://localhost:8000/api/v1/analysis/boe-savings-summary \
  -H "Authorization: Bearer $TOKEN"
# Expected: JSON with coverage_pct, auto_approved_count, estimated_inr_saved

# Frontend: navigate to /dashboard/analytics and verify card renders
```

### Risk: LOW — read-only endpoint, frontend card is additive.

---

## Phase 4 — Migration Dependency Chain

Run migrations in this exact order:
```bash
cd /home/user/dokydoc/backend

# Step 1: s14a1 — adds atomized_at_upload to requirement_atoms
alembic upgrade s14a1

# Step 2: s14b1 — adds last_validated_at + validation_verdict to concept_mappings
alembic upgrade s14b1

# Or in one shot (safe — chain is linear):
alembic upgrade head
```

Verify with:
```bash
psql $DATABASE_URL -c "\d requirement_atoms" | grep atomized_at_upload
psql $DATABASE_URL -c "\d concept_mappings" | grep last_validated_at
```

---

## Phase 4 — Completion Checklist

Before marking Phase 4 done, every item below must be verified:

- [ ] `s14a1_atom_upload_flag.py` migration created with correct `down_revision = 's12a1'`
- [ ] `s14b1_concept_mapping_validation_fields.py` migration created with `down_revision = 's14a1'`
- [ ] `alembic upgrade head` runs clean with zero errors
- [ ] `backend/app/services/boe_context.py` file created (P4-02)
- [ ] `BOEContext.build()` tested manually — returns object with correct counts
- [ ] `atomize_document` signature updated with `atomized_at_upload` param (P4-01)
- [ ] `_run_async_pipeline` pre-atomization block added and wrapped in try/except
- [ ] `validate_single_link` signature updated with `boe_context=None` param (P4-03)
- [ ] BOE auto-approve filter block inserted before forward pass gather (P4-03)
- [ ] Document-only gap auto-mismatches added after forward pass loop (P4-03)
- [ ] `run_validation_scan` builds BOEContexts before gather call (P4-04)
- [ ] `_calibrate_confidence()` static method added to ValidationService (P4-06)
- [ ] Calibration verdict write-back added after mismatch creation (P4-05)
- [ ] `ConceptMapping` model updated with `last_validated_at` + `validation_verdict` columns
- [ ] Code analysis service dispatches `run_cross_graph_mapping` on completion (P4-07)
- [ ] `/api/v1/analysis/run-full` endpoint added and tested (P4-08)
- [ ] `/api/v1/analysis/boe-savings-summary` endpoint added (P4-09)
- [ ] Analytics dashboard BOE card renders without errors (P4-09)
- [ ] Logs show "BOE skipped N atoms" during a real validation scan
- [ ] At least one validation run recorded `last_validated_at` on a ConceptMapping


---

# PHASE 5 — Industry-Aware Prompt Injection

**Goal:** Make every Gemini call domain-aware by injecting regulatory context, company
glossary terms, and few-shot examples from the tenant's own document history. A fintech
tenant's validation prompts will automatically include PCI-DSS vocabulary. A healthcare
tenant's prompts will include HIPAA language. No static prompt editing required.

**Sprint estimate:** 6–7 days for 2 developers working on Phase 5 tasks.

**Migration chain for Phase 5:**
```
s14b1 (Phase 4) → s15a1 (new)
```

**No new DB columns needed** beyond the GIN index on `tenants.settings`.
The `settings` JSON field already exists on `Tenant` model at
`backend/app/models/tenant.py` line 45:
```python
settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, server_default='{}')
```

---

## P5-01 — Industry Settings in tenant.settings JSON

**Ticket:** P5-01
**Priority:** P1 (everything in Phase 5 reads from tenant.settings)
**New migration:** `backend/alembic/versions/s15a1_tenant_settings_gin_index.py`

### Why:
The `settings` column is a plain JSON column with no index. As tenant count grows,
queries that filter by `settings->>'industry'` (e.g. "all fintech tenants") become
full table scans. A GIN index on the `settings` column enables fast JSON key queries.

### Step 1 — Create migration s15a1:
Create `backend/alembic/versions/s15a1_tenant_settings_gin_index.py`:

```python
"""Add GIN index on tenants.settings for fast JSON queries

Revision ID: s15a1
Revises: s14b1
Create Date: 2026-04-05

Purpose:
  - Enables fast queries on tenants.settings JSON paths
  - Required for industry-aware prompt injection (Phase 5)
  - No new columns — settings JSON field already exists
"""
import sqlalchemy as sa
from alembic import op

revision = 's15a1'
down_revision = 's14b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on the full settings column — enables @>, ?, ?& operators
    # CONCURRENTLY = zero downtime, does not lock the table
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenants_settings_gin
        ON tenants USING GIN (settings jsonb_path_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_tenants_settings_gin;")
```

**IMPORTANT:** Alembic cannot run `CREATE INDEX CONCURRENTLY` inside a transaction.
Add `connection.execute(text("COMMIT"))` before the index creation, or run the
migration with `--no-transaction` flag:

```python
def upgrade() -> None:
    # Must be outside a transaction for CONCURRENTLY
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenants_settings_gin
        ON tenants USING GIN (settings jsonb_path_ops);
    """)
```

### Step 2 — Document the tenant.settings JSON schema (no DB changes):

The `settings` JSON must follow this structure going forward. Add this as a docstring
in `backend/app/models/tenant.py` above the `settings` column definition:

```python
    # Settings (JSON field for flexible tenant configuration)
    # Schema (Phase 5+):
    # {
    #   "industry": str,              # e.g. "fintech/payments", "healthcare", "saas"
    #   "sub_domain": str,            # e.g. "lending", "insurance", "b2b"
    #   "company_website": str,       # e.g. "https://acme.com"
    #   "glossary": {                 # tenant-defined term overrides
    #     "term": "definition",
    #     ...
    #   },
    #   "regulatory_context": [       # list of applicable regulations
    #     "PCI-DSS", "GDPR", ...
    #   ],
    #   "onboarding_complete": bool,  # False until wizard is finished
    #   "pending_glossary_confirmations": [  # terms awaiting human review
    #     {"term": str, "suggested_definition": str, "source_document_id": int}
    #   ]
    # }
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, server_default='{}')
```

### Test commands:
```bash
alembic upgrade head

# Verify index was created
psql $DATABASE_URL -c "\di+ ix_tenants_settings_gin"
# Expected: one row showing the GIN index on tenants.settings

# Test index is used for JSON path queries
psql $DATABASE_URL -c "EXPLAIN SELECT * FROM tenants WHERE settings @> '{\"industry\": \"fintech/payments\"}';"
# Expected: "Index Scan using ix_tenants_settings_gin" in plan
```

### Risk: LOW — no schema changes. GIN index is non-blocking (`CONCURRENTLY`).

---

## P5-02 — Industry Context Library

**Ticket:** P5-02
**Priority:** P1 (P5-03 imports from this file)
**File:** `backend/app/services/ai/industry_context.json` (NEW FILE)
**Parallelizable:** YES — pure data file, no code dependencies

### Why:
Instead of hardcoding industry knowledge in prompts (which requires redeployment to
update), we store it in a JSON file that PromptManager reads at startup. Each industry
entry has: a list of applicable regulations, a vocabulary dict of domain-specific terms,
and a `prompt_injection` string that gets prepended verbatim to Gemini prompts.

### What to create:
Create `backend/app/services/ai/industry_context.json` with the following content.
Each key is an industry slug matching the `settings.industry` values:

```json
{
  "fintech/payments": {
    "regulatory": ["PCI-DSS v4.0", "PSD2", "ISO 27001", "SOC 2 Type II"],
    "vocabulary": {
      "acquirer": "The bank that processes card payments on behalf of merchants",
      "issuer": "The bank that issues payment cards to consumers",
      "interchange": "Fee paid between banks for card transactions",
      "tokenization": "Replacing sensitive card data with a non-sensitive surrogate value",
      "3DS": "3D Secure — additional authentication layer for online card transactions",
      "BIN": "Bank Identification Number — first 6-8 digits of a payment card",
      "chargeback": "Reversal of a payment by the card issuer at the cardholder's request",
      "settlement": "Transfer of funds from acquiring bank to merchant after transaction",
      "KYC": "Know Your Customer — identity verification requirements",
      "AML": "Anti-Money Laundering — regulatory framework to prevent financial crimes"
    },
    "prompt_injection": "REGULATORY CONTEXT: This system processes payment data and must comply with PCI-DSS v4.0 and PSD2. When analyzing requirements, flag any that involve card data storage, transmission, or processing as HIGH PRIORITY. PCI-DSS requires: cardholder data must be encrypted at rest and in transit, access to cardholder data must be logged, security scans must be performed quarterly. PSD2 requires: Strong Customer Authentication (SCA) for transactions over €30."
  },
  "fintech/lending": {
    "regulatory": ["FCRA", "ECOA", "TILA", "HMDA", "BSA/AML"],
    "vocabulary": {
      "underwriting": "Process of evaluating loan risk and setting terms",
      "DTI": "Debt-to-Income ratio — borrower's monthly debt vs monthly income",
      "LTV": "Loan-to-Value ratio — loan amount vs asset value",
      "origination": "Process of applying for and processing a new loan",
      "FICO": "Credit scoring model from Fair Isaac Corporation",
      "APR": "Annual Percentage Rate — total cost of borrowing including fees",
      "adverse action": "Denial of credit or unfavorable terms — ECOA requires written notice",
      "seasoning": "Time a loan has been active — affects secondary market eligibility"
    },
    "prompt_injection": "REGULATORY CONTEXT: This is a lending platform subject to FCRA, ECOA, and TILA. When analyzing requirements: (1) Any credit decision logic must be auditable for fair lending compliance — flag hard-coded scoring rules. (2) Adverse action notices are legally required within 30 days of credit denial. (3) APR calculations must follow Regulation Z methodology."
  },
  "banking": {
    "regulatory": ["Basel III", "Dodd-Frank", "BSA/AML", "GDPR", "FFIEC guidelines"],
    "vocabulary": {
      "correspondent banking": "Relationship where one bank holds accounts for another bank",
      "SWIFT": "Society for Worldwide Interbank Financial Telecommunication messaging network",
      "nostro": "Account held by a domestic bank at a foreign bank in foreign currency",
      "vostro": "Account held by a foreign bank at a domestic bank in domestic currency",
      "RTGS": "Real-Time Gross Settlement — immediate interbank fund transfers",
      "core banking": "Central processing systems for deposits, loans, and transactions",
      "tier 1 capital": "Core capital — equity capital and disclosed reserves",
      "liquidity ratio": "Proportion of liquid assets to total liabilities"
    },
    "prompt_injection": "REGULATORY CONTEXT: This is a banking system subject to Basel III capital requirements and BSA/AML regulations. When analyzing requirements: (1) Any transaction monitoring system must flag transactions over $10,000 for CTR filing. (2) Suspicious activity must trigger SAR filing within 30 days. (3) Capital adequacy ratios must be maintained — any system affecting risk-weighted assets needs compliance review."
  },
  "healthcare": {
    "regulatory": ["HIPAA", "HITECH", "HL7 FHIR R4", "21 CFR Part 11", "ICD-10"],
    "vocabulary": {
      "PHI": "Protected Health Information — any individually identifiable health data",
      "EHR": "Electronic Health Record — digital version of a patient's chart",
      "EMR": "Electronic Medical Record — digital record within one practice",
      "HL7": "Health Level 7 — standards for exchanging health data",
      "FHIR": "Fast Healthcare Interoperability Resources — modern HL7 API standard",
      "CPT": "Current Procedural Terminology — codes for medical procedures",
      "ICD-10": "International Classification of Diseases — diagnostic billing codes",
      "covered entity": "HIPAA term for healthcare providers, plans, and clearinghouses",
      "BAA": "Business Associate Agreement — required HIPAA contract with vendors",
      "de-identification": "Removing 18 HIPAA identifiers to make data non-PHI"
    },
    "prompt_injection": "REGULATORY CONTEXT: This is a healthcare system handling Protected Health Information (PHI) under HIPAA/HITECH. CRITICAL REQUIREMENTS: (1) PHI must be encrypted in transit (TLS 1.2+) and at rest (AES-256). (2) Audit logs must track all PHI access — who accessed what, when. (3) Minimum Necessary standard — systems should only access PHI required for their function. (4) Any breach of unsecured PHI triggers 60-day notification requirement."
  },
  "saas": {
    "regulatory": ["SOC 2 Type II", "GDPR", "CCPA", "ISO 27001"],
    "vocabulary": {
      "MRR": "Monthly Recurring Revenue — predictable monthly subscription income",
      "ARR": "Annual Recurring Revenue — MRR multiplied by 12",
      "churn": "Rate at which customers cancel subscriptions",
      "CAC": "Customer Acquisition Cost — total cost to acquire one new customer",
      "LTV": "Lifetime Value — total revenue expected from one customer relationship",
      "onboarding": "Process of activating a new customer account",
      "multi-tenancy": "Architecture where one instance serves multiple customer organizations",
      "SSO": "Single Sign-On — unified authentication across applications",
      "RBAC": "Role-Based Access Control — permissions based on user roles",
      "webhook": "HTTP callback triggered by events in one system to notify another"
    },
    "prompt_injection": "CONTEXT: This is a B2B SaaS platform. When analyzing requirements: (1) Multi-tenancy is critical — verify data isolation between tenants in every feature. (2) GDPR requires data portability (export) and right to erasure (delete) for EU customers. (3) SOC 2 compliance requires: access controls, audit logging, encryption, incident response procedures. (4) Webhook implementations must include retry logic, payload signing, and delivery confirmation."
  },
  "ecommerce": {
    "regulatory": ["PCI-DSS", "GDPR", "CCPA", "CAN-SPAM"],
    "vocabulary": {
      "SKU": "Stock Keeping Unit — unique product identifier",
      "GMV": "Gross Merchandise Value — total value of goods sold",
      "cart abandonment": "When a shopper adds items to cart but does not complete purchase",
      "fulfillment": "Process of picking, packing, and shipping orders",
      "dropshipping": "Selling products without holding inventory",
      "marketplace": "Platform connecting multiple sellers with buyers",
      "AOV": "Average Order Value — average revenue per completed order",
      "RMA": "Return Merchandise Authorization — process for handling returns",
      "backorder": "Order for an item not currently in stock",
      "catalog": "Master list of all products available for sale"
    },
    "prompt_injection": "CONTEXT: This is an e-commerce platform processing customer orders and payments. Key requirements to check: (1) Payment processing must be PCI-DSS compliant — never store raw card numbers. (2) Order state machine must handle: placed → confirmed → fulfilled → shipped → delivered → (returned). (3) Inventory must handle race conditions for limited-stock items. (4) GDPR/CCPA: customers must be able to download and delete their data."
  },
  "logistics": {
    "regulatory": ["DOT regulations", "FMCSA", "IATA", "Incoterms 2020"],
    "vocabulary": {
      "BOL": "Bill of Lading — legal document for shipment of goods",
      "POD": "Proof of Delivery — signed confirmation of delivery",
      "ETA": "Estimated Time of Arrival",
      "FTL": "Full Truckload — shipment that fills an entire truck",
      "LTL": "Less Than Truckload — multiple shippers sharing truck space",
      "last mile": "Final delivery leg from distribution center to end customer",
      "dwell time": "Time a truck sits idle at a facility",
      "lane": "Regular shipping route between two locations",
      "tender": "Offer of freight to a carrier",
      "SCAC": "Standard Carrier Alpha Code — unique carrier identifier"
    },
    "prompt_injection": "CONTEXT: This is a logistics management system. When analyzing requirements: (1) Real-time tracking data must handle intermittent GPS connectivity — design for eventual consistency. (2) Route optimization calculations can be expensive — cache results with appropriate TTLs. (3) Driver hours-of-service rules (HOS) must be enforced — max 11 driving hours per day. (4) Hazmat shipments require additional documentation and routing constraints."
  },
  "devtools": {
    "regulatory": ["SOC 2", "GitHub/GitLab API ToS", "OSS license compliance"],
    "vocabulary": {
      "CI/CD": "Continuous Integration / Continuous Deployment pipeline",
      "SAST": "Static Application Security Testing — code analysis for vulnerabilities",
      "DAST": "Dynamic Application Security Testing — runtime security scanning",
      "SBOM": "Software Bill of Materials — inventory of software components and licenses",
      "shift left": "Moving testing/security checks earlier in the development lifecycle",
      "trunk-based development": "All developers commit directly to main branch frequently",
      "feature flags": "Toggles to enable/disable features without code deployment",
      "canary deployment": "Gradual rollout to a small percentage of users first",
      "observability": "Ability to understand system state from external outputs",
      "SLO": "Service Level Objective — target reliability metric"
    },
    "prompt_injection": "CONTEXT: This is a developer tooling product used by engineering teams. When analyzing requirements: (1) Security scanning features must not slow down CI pipelines — flag any synchronous security checks that could add >30s. (2) API rate limits from GitHub/GitLab/Bitbucket must be respected — implement caching and backoff. (3) Any code that is analyzed may contain secrets — never log raw code content. (4) Webhook endpoints must respond within 5 seconds or the source system will retry."
  }
}
```

### Test commands:
```bash
# Verify JSON is valid
python3 -c "import json; data = json.load(open('backend/app/services/ai/industry_context.json')); print('Industries:', list(data.keys()))"
# Expected: Industries: ['fintech/payments', 'fintech/lending', 'banking', ...]

# Verify all required keys are present for each industry
python3 -c "
import json
data = json.load(open('backend/app/services/ai/industry_context.json'))
for k, v in data.items():
    assert 'regulatory' in v, f'Missing regulatory in {k}'
    assert 'vocabulary' in v, f'Missing vocabulary in {k}'
    assert 'prompt_injection' in v, f'Missing prompt_injection in {k}'
print('All industries valid')
"
```

### Risk: LOW — pure data file, read-only.


---

## P5-03 — PromptContext Dataclass + Dynamic Prompt Assembly

**Ticket:** P5-03
**Priority:** P1 (P5-05, P5-06, P5-08 all depend on this)
**Files:**
  - `backend/app/services/ai/prompt_context.py` (NEW FILE)
  - `backend/app/services/ai/prompt_context_builder.py` (NEW FILE)
  - `backend/app/services/ai/prompt_manager.py` (MODIFY — add `context` param only)

### Why:
`PromptManager.get_prompt()` currently ignores all tenant context. With PromptContext,
callers can pass a single context object and every prompt automatically gains an
industry preamble, glossary block, and few-shot examples. The change to `get_prompt`
is backwards-compatible — existing callers that don't pass `context` see zero change.

### Step 1 — Create prompt_context.py:
Create `backend/app/services/ai/prompt_context.py`:

```python
"""
PromptContext — Tenant-specific context for AI prompt injection

Carries the industry profile, glossary terms, and few-shot examples
that get prepended to every Gemini call for a tenant.

Built via prompt_context_builder.build_prompt_context() — do not
instantiate directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PromptContext:
    """
    Tenant-specific context injected into AI prompts.

    Attributes:
        industry: Industry slug from tenant.settings (e.g. 'fintech/payments')
        sub_domain: Sub-domain from tenant.settings (e.g. 'lending')
        glossary: Tenant's custom term definitions (overrides industry defaults)
        few_shot_examples: Up to 5 labeled examples from crud.training_example.get_labeled()
            Each dict has keys: input_text, expected_output, feedback_type
        regulatory: List of applicable regulations (from industry_context.json)
        industry_vocabulary: Industry-standard term definitions
        prompt_injection: Verbatim text to prepend from industry_context.json
    """
    industry: str = ""
    sub_domain: str = ""
    glossary: Dict[str, str] = field(default_factory=dict)
    few_shot_examples: List[Dict] = field(default_factory=list)
    regulatory: List[str] = field(default_factory=list)
    industry_vocabulary: Dict[str, str] = field(default_factory=dict)
    prompt_injection: str = ""

    @property
    def is_empty(self) -> bool:
        """True if no context data is available — caller can skip injection."""
        return (
            not self.industry
            and not self.glossary
            and not self.few_shot_examples
            and not self.prompt_injection
        )

    def render_industry_block(self) -> str:
        """
        Render the industry context block as a prompt string.
        Called by PromptManager.get_prompt() when context is provided.

        Returns empty string if no industry data available.
        """
        if not self.industry and not self.prompt_injection:
            return ""

        parts = []
        if self.prompt_injection:
            parts.append(self.prompt_injection)
        if self.regulatory:
            parts.append(
                f"APPLICABLE REGULATIONS: {', '.join(self.regulatory)}"
            )
        return "\n".join(parts)

    def render_glossary_block(self) -> str:
        """
        Render glossary + industry vocabulary as a prompt string.

        Tenant glossary takes precedence over industry vocabulary for
        conflicting terms (tenant knows their own terminology).
        """
        merged = {**self.industry_vocabulary, **self.glossary}  # tenant overrides
        if not merged:
            return ""

        lines = ["DOMAIN GLOSSARY (use these definitions when analyzing this document):"]
        for term, definition in list(merged.items())[:30]:  # cap at 30 terms
            lines.append(f"  - {term}: {definition}")
        return "\n".join(lines)

    def render_few_shot_block(self) -> str:
        """
        Render few-shot examples as a prompt string.
        Uses the 5 most recent labeled training examples for this tenant.
        """
        if not self.few_shot_examples:
            return ""

        lines = [
            "FEW-SHOT EXAMPLES (these are real examples from this tenant's documents):"
        ]
        for i, example in enumerate(self.few_shot_examples[:5], 1):
            input_text = example.get("input_text", "")[:300]
            expected = example.get("expected_output", "")[:300]
            lines.append(f"\nExample {i}:")
            lines.append(f"  Input: {input_text}")
            lines.append(f"  Expected output: {expected}")
        return "\n".join(lines)

    def render_full_preamble(self) -> str:
        """
        Render the complete context preamble to prepend before the base prompt.
        Returns empty string if context is empty.
        """
        if self.is_empty:
            return ""

        blocks = []
        industry_block = self.render_industry_block()
        glossary_block = self.render_glossary_block()
        few_shot_block = self.render_few_shot_block()

        if industry_block:
            blocks.append(industry_block)
        if glossary_block:
            blocks.append(glossary_block)
        if few_shot_block:
            blocks.append(few_shot_block)

        if not blocks:
            return ""

        header = "=== TENANT CONTEXT (injected by DokyDoc) ==="
        footer = "=== END TENANT CONTEXT ==="
        return f"{header}\n" + "\n\n".join(blocks) + f"\n{footer}\n\n"
```

### Step 2 — Create prompt_context_builder.py:
Create `backend/app/services/ai/prompt_context_builder.py`:

```python
"""
PromptContextBuilder — Builds PromptContext from DB + industry library

The single function build_prompt_context() is called by gemini.py methods
before calling get_prompt(). It reads tenant.settings once and returns a
PromptContext that carries all the context needed for prompt injection.

Performance note: This does 2 DB queries (tenant settings + training examples).
At average prompt sizes this adds ~2ms — acceptable overhead for context injection.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from sqlalchemy.orm import Session

from app.services.ai.prompt_context import PromptContext


# Load industry context library once at module import time
_INDUSTRY_CONTEXT: dict = {}
_INDUSTRY_CONTEXT_PATH = os.path.join(
    os.path.dirname(__file__), "industry_context.json"
)

try:
    with open(_INDUSTRY_CONTEXT_PATH, "r", encoding="utf-8") as f:
        _INDUSTRY_CONTEXT = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    pass  # Non-fatal — context injection simply won't work until file exists


def build_prompt_context(
    db: Session,
    tenant_id: int,
    example_type: Optional[str] = None,
) -> PromptContext:
    """
    Build a PromptContext for a tenant by reading:
    1. tenant.settings (industry, glossary, regulatory_context)
    2. industry_context.json (matching industry slug)
    3. crud.training_example.get_labeled() (up to 5 few-shot examples)

    Args:
        db: SQLAlchemy session
        tenant_id: Tenant to build context for
        example_type: Optional filter for training example type (e.g. 'validation')
                      Pass None to get all labeled examples.

    Returns:
        PromptContext — always returns a valid object even if data is missing.
        An empty PromptContext (is_empty=True) is safe to pass to get_prompt().
    """
    from app import crud

    ctx = PromptContext()

    # ── Step 1: Read tenant settings ─────────────────────────────────────
    try:
        tenant = crud.tenant.get(db, id=tenant_id)
        if not tenant:
            return ctx

        settings = tenant.settings or {}
        ctx.industry = settings.get("industry", "")
        ctx.sub_domain = settings.get("sub_domain", "")
        ctx.glossary = settings.get("glossary", {}) or {}
    except Exception:
        return ctx

    # ── Step 2: Look up industry context library ──────────────────────────
    if ctx.industry and _INDUSTRY_CONTEXT:
        industry_data = _INDUSTRY_CONTEXT.get(ctx.industry, {})
        if not industry_data and "/" in ctx.industry:
            # Try parent industry (e.g. 'fintech/payments' → 'fintech')
            parent = ctx.industry.split("/")[0]
            industry_data = _INDUSTRY_CONTEXT.get(parent, {})

        ctx.regulatory = industry_data.get("regulatory", [])
        ctx.industry_vocabulary = industry_data.get("vocabulary", {})
        ctx.prompt_injection = industry_data.get("prompt_injection", "")

    # ── Step 3: Load few-shot examples from training data ─────────────────
    try:
        examples = crud.training_example.get_labeled(
            db,
            tenant_id=tenant_id,
            limit=5,
            example_type=example_type,
        )
        ctx.few_shot_examples = [
            {
                "input_text": ex.input_text,
                "expected_output": ex.expected_output,
                "feedback_type": ex.feedback_source,
            }
            for ex in (examples or [])
            if ex.input_text and ex.expected_output
        ]
    except Exception:
        pass  # Non-fatal — few-shot injection is optional

    return ctx
```

### Step 3 — Modify PromptManager.get_prompt() to accept context param:
In `backend/app/services/ai/prompt_manager.py`, modify the `get_prompt` method
at **line 1362**. This is the ONLY change Phase 5 makes to this file.

#### Current code (lines 1362–1384):
```python
    def get_prompt(self, prompt_type: PromptType, **kwargs) -> str:
        """
        Get a prompt of the specified type.
        
        Args:
            prompt_type: The type of prompt to retrieve
            **kwargs: Variables to substitute in the prompt
            
        Returns:
            The formatted prompt string
        """
        if prompt_type.value not in self.prompts:
            raise ValueError(f"Unknown prompt type: {prompt_type.value}")
        
        prompt_data = self.prompts[prompt_type.value]
        prompt = prompt_data["prompt"]
        
        # Apply any variable substitutions
        if kwargs:
            prompt = prompt.format(**kwargs)
        
        self.logger.debug(f"Retrieved prompt for type: {prompt_type.value}")
        return prompt
```

#### Replace with:
```python
    def get_prompt(self, prompt_type: PromptType, context=None, **kwargs) -> str:
        """
        Get a prompt of the specified type, optionally prepending tenant context.

        Args:
            prompt_type: The type of prompt to retrieve
            context: Optional PromptContext — when provided, prepends industry block,
                     glossary block, and few-shot examples before the base prompt.
                     Pass None (default) for backwards-compatible behavior.
            **kwargs: Variables to substitute in the prompt

        Returns:
            The formatted prompt string, with context preamble if context provided.
        """
        if prompt_type.value not in self.prompts:
            raise ValueError(f"Unknown prompt type: {prompt_type.value}")

        prompt_data = self.prompts[prompt_type.value]
        prompt = prompt_data["prompt"]

        # Apply any variable substitutions
        if kwargs:
            prompt = prompt.format(**kwargs)

        # Phase 5: Prepend tenant context preamble if provided
        if context is not None and not context.is_empty:
            preamble = context.render_full_preamble()
            if preamble:
                prompt = preamble + prompt
                self.logger.debug(
                    f"Context-enriched prompt for type: {prompt_type.value} "
                    f"(industry={context.industry}, "
                    f"glossary_terms={len(context.glossary)}, "
                    f"few_shot={len(context.few_shot_examples)})"
                )

        self.logger.debug(f"Retrieved prompt for type: {prompt_type.value}")
        return prompt
```

**This change is 100% backwards-compatible** — `context=None` preserves all existing
behavior. No existing callers need to change unless they want context injection.

### Test commands:
```bash
# Test PromptContext renders correctly
python3 -c "
from app.services.ai.prompt_context import PromptContext
ctx = PromptContext(
    industry='fintech/payments',
    glossary={'settlement': 'Transfer of funds to merchant'},
    prompt_injection='CONTEXT: PCI-DSS applies.',
    regulatory=['PCI-DSS v4.0'],
)
preamble = ctx.render_full_preamble()
assert '=== TENANT CONTEXT' in preamble
assert 'PCI-DSS' in preamble
assert 'settlement' in preamble
print('PromptContext render OK')
print(preamble[:200])
"

# Test build_prompt_context reads from DB
python3 -c "
from app.db.session import SessionLocal
from app.services.ai.prompt_context_builder import build_prompt_context
db = SessionLocal()
ctx = build_prompt_context(db, tenant_id=1)
print('Context:', ctx.industry, '| Glossary terms:', len(ctx.glossary))
print('Empty?', ctx.is_empty)
db.close()
"

# Test PromptManager with context
python3 -c "
from app.services.ai.prompt_manager import prompt_manager, PromptType
from app.services.ai.prompt_context import PromptContext

ctx = PromptContext(industry='saas', prompt_injection='SAAS CONTEXT TEST')
prompt = prompt_manager.get_prompt(PromptType.VALIDATION, context=ctx)
assert 'SAAS CONTEXT TEST' in prompt
print('PromptManager context injection OK')
"
```

### Risk: MEDIUM — modifying `get_prompt` which is called many times. The `context=None`
default makes this safe. Read `prompt_manager.py` lines 1362–1384 before editing to
confirm no other call sites pass a positional second argument.


---

## P5-04 — Website URL Auto-Detection at Tenant Registration

**Ticket:** P5-04
**Priority:** P2 (good UX — not required for prompt injection to work)
**Files:**
  - `backend/app/tasks/tenant_tasks.py` (NEW FILE)
  - `backend/app/api/endpoints/tenants.py` (MODIFY — dispatch task after registration)
  - `backend/app/worker.py` (MODIFY — register new task module)
**Parallelizable:** YES — independent of P5-02, P5-03

### Why:
Most tenants register with a company website URL. We can classify their industry
automatically with a single Gemini call during onboarding (fetching the website and
analyzing its content). This saves the user from manually selecting their industry
in the onboarding wizard and makes the onboarding wizard feel intelligent.

### Step 1 — Create tenant_tasks.py:
Create `backend/app/tasks/tenant_tasks.py`:

```python
"""
Tenant background tasks (Phase 5)

detect_tenant_industry: Celery task that fetches the tenant's website,
  extracts visible text, and classifies the industry using Gemini.
  Runs as a fire-and-forget task after tenant registration.

Design constraints:
  - Must complete in < 30 seconds (website fetch timeout = 10s, Gemini = 15s)
  - Must never block registration response — always dispatched as .delay()
  - If classification fails, tenant.settings remains empty — no silent corruption
"""
import json
import re
import time
from typing import Optional

from app.worker import celery_app
from app.db.session import SessionLocal
from app import crud
from app.core.logging import logger

# Industry slugs that Gemini can output — must match keys in industry_context.json
VALID_INDUSTRY_SLUGS = {
    "fintech/payments",
    "fintech/lending",
    "banking",
    "healthcare",
    "saas",
    "ecommerce",
    "logistics",
    "devtools",
}

WEBSITE_FETCH_TIMEOUT = 10  # seconds
MAX_TEXT_LENGTH = 4000       # chars sent to Gemini


@celery_app.task(
    name="detect_tenant_industry",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def detect_tenant_industry(self, tenant_id: int, website_url: str):
    """
    Celery task: Fetch website, classify industry, update tenant.settings.

    Flow:
      1. Fetch website HTML (requests, 10s timeout)
      2. Strip HTML tags to get visible text
      3. Single Gemini call: "Classify this company's industry"
      4. Validate response is a known slug
      5. Update tenant.settings["industry"] and settings["onboarding_complete"] = false

    Args:
        tenant_id: Tenant to update
        website_url: Company website URL from registration
    """
    logger.info(f"DETECT_INDUSTRY started for tenant {tenant_id}, url={website_url}")
    db = SessionLocal()

    try:
        # ── Step 1: Fetch website ─────────────────────────────────────────
        import requests
        try:
            resp = requests.get(
                website_url,
                timeout=WEBSITE_FETCH_TIMEOUT,
                headers={"User-Agent": "DokyDoc/1.0 (industry classification bot)"},
                allow_redirects=True,
            )
            raw_html = resp.text
        except Exception as fetch_err:
            logger.warning(f"DETECT_INDUSTRY: fetch failed for {website_url}: {fetch_err}")
            return

        # ── Step 2: Strip HTML to visible text ───────────────────────────
        # Remove script/style tags entirely
        clean = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        # Remove remaining HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        website_text = clean[:MAX_TEXT_LENGTH]

        if len(website_text) < 50:
            logger.warning(f"DETECT_INDUSTRY: insufficient text from {website_url}")
            return

        # ── Step 3: Gemini classification call ───────────────────────────
        from app.services.ai.gemini import gemini_service
        if not gemini_service:
            logger.warning("DETECT_INDUSTRY: gemini_service not available")
            return

        valid_slugs_str = ", ".join(sorted(VALID_INDUSTRY_SLUGS))
        classification_prompt = f"""
Analyze the following website text and classify the company into exactly ONE industry.

VALID INDUSTRY SLUGS (respond with ONLY one of these, nothing else):
{valid_slugs_str}

WEBSITE TEXT:
{website_text}

INSTRUCTIONS:
- Respond with ONLY the industry slug, nothing else
- No explanation, no punctuation, no extra words
- If uncertain, choose the closest match
- Example valid response: fintech/payments
"""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            response = loop.run_until_complete(
                gemini_service.generate_content(classification_prompt)
            )
            loop.close()
        except Exception as gemini_err:
            logger.warning(f"DETECT_INDUSTRY: Gemini call failed: {gemini_err}")
            return

        detected_slug = (response.text or "").strip().lower().strip('"').strip("'")

        # ── Step 4: Validate slug ─────────────────────────────────────────
        if detected_slug not in VALID_INDUSTRY_SLUGS:
            logger.warning(
                f"DETECT_INDUSTRY: invalid slug returned '{detected_slug}' "
                f"for tenant {tenant_id}"
            )
            return

        # ── Step 5: Update tenant.settings ───────────────────────────────
        tenant = crud.tenant.get(db, id=tenant_id)
        if not tenant:
            logger.error(f"DETECT_INDUSTRY: tenant {tenant_id} not found")
            return

        current_settings = dict(tenant.settings or {})
        # Only set if not already set by the user (don't overwrite manual selection)
        if not current_settings.get("industry"):
            current_settings["industry"] = detected_slug
            current_settings.setdefault("onboarding_complete", False)
            crud.tenant.update(
                db,
                db_obj=tenant,
                obj_in={"settings": current_settings}
            )
            db.commit()
            logger.info(
                f"DETECT_INDUSTRY: set industry='{detected_slug}' for tenant {tenant_id}"
            )
        else:
            logger.info(
                f"DETECT_INDUSTRY: tenant {tenant_id} already has industry set — skipping"
            )

    except Exception as e:
        logger.error(f"DETECT_INDUSTRY: unexpected error for tenant {tenant_id}: {e}")
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"DETECT_INDUSTRY permanently failed for tenant {tenant_id}")
    finally:
        db.close()
```

### Step 2 — Dispatch task from tenant registration:
In `backend/app/api/endpoints/tenants.py`, at line 138 (after the `"tenant": tenant`
return block is assembled but before the `return {}` statement), add:

```python
        # Phase 5 P5-04: Auto-detect industry from company website
        # Fire-and-forget — never blocks registration
        company_website = getattr(tenant_in, 'company_website', None)
        if company_website:
            try:
                from app.tasks.tenant_tasks import detect_tenant_industry
                detect_tenant_industry.delay(tenant.id, company_website)
                logger.info(
                    f"Industry detection queued for tenant {tenant.id} ({company_website})"
                )
            except Exception as detect_err:
                logger.warning(f"Could not queue industry detection: {detect_err}")
```

**Note:** `company_website` may not be in the current `TenantCreate` schema. Check
`backend/app/schemas/tenant.py` — if it's missing, add:
```python
company_website: Optional[str] = None
```

### Step 3 — Register tenant_tasks module in worker.py:
In `backend/app/worker.py`, add `"app.tasks.tenant_tasks"` to the `include` list:

```python
# BEFORE (lines 11-16):
    include=[
        "app.tasks",
        "app.tasks.ontology_tasks",
        "app.tasks.code_analysis_tasks",
        "app.tasks.embedding_tasks",
    ]

# AFTER:
    include=[
        "app.tasks",
        "app.tasks.ontology_tasks",
        "app.tasks.code_analysis_tasks",
        "app.tasks.embedding_tasks",
        "app.tasks.tenant_tasks",       # Phase 5: Industry detection
    ]
```

### Test commands:
```bash
# Restart worker to pick up new task registration
docker-compose restart worker

# Register a test tenant with a website URL
curl -X POST http://localhost:8000/api/v1/tenants/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Fintech Co",
    "subdomain": "testfintech42",
    "admin_email": "admin@testfintech.com",
    "admin_password": "TestPass123!",
    "admin_name": "Test Admin",
    "company_website": "https://stripe.com"
  }'

# Wait ~20 seconds, then check if industry was detected
psql $DATABASE_URL -c "SELECT id, name, settings FROM tenants WHERE subdomain = 'testfintech42';"
# Expected: settings JSON contains "industry": "fintech/payments"
```

### Risk: LOW — fire-and-forget with try/except. If task fails, tenant.settings
stays empty and onboarding wizard prompts manual selection.

---

## P5-05 — Glossary Self-Learning in Document Ontology Extraction

**Ticket:** P5-05
**Priority:** P2 (depends on P5-03)
**File:** `backend/app/services/business_ontology_service.py`
**Lines to read:** Lines 100–170 (extract_entities_from_document method)

### Why:
When the BOE extracts concepts from a new document, some concepts will have low
confidence (< 0.75) and won't match any term in the tenant's glossary or industry
vocabulary. These are candidates for the glossary. Instead of silently discarding them,
we surface them to the user via an amber banner on the document page.

### What to add — after _ingest_extraction_result call (around line 146 of business_ontology_service.py):
Read the file to confirm exact line, then insert after the `self.logger.info(...)` at
line 148:

```python
        # Phase 5 P5-05: Surface low-confidence unknown terms for glossary review
        try:
            self._surface_unknown_terms(
                db=db,
                tenant_id=tenant_id,
                entities=entities,
                document_id=document_id,
            )
        except Exception as gloss_err:
            self.logger.debug(f"Glossary surfacing failed (non-fatal): {gloss_err}")
```

Add the new method to BusinessOntologyService after `_ingest_extraction_result`:

```python
    def _surface_unknown_terms(
        self,
        db,
        tenant_id: int,
        entities: list,
        document_id: int,
    ) -> None:
        """
        Phase 5: Find low-confidence concepts not in glossary or industry vocab.
        Stores up to 10 in tenant.settings["pending_glossary_confirmations"].
        Creates a notification for the document owner.
        """
        from app import crud

        tenant = crud.tenant.get(db, id=tenant_id)
        if not tenant:
            return

        settings = dict(tenant.settings or {})
        glossary = settings.get("glossary", {}) or {}
        industry = settings.get("industry", "")

        # Load industry vocabulary to check against
        industry_vocab: set = set()
        try:
            import json, os
            ctx_path = os.path.join(
                os.path.dirname(__file__), "ai", "industry_context.json"
            )
            with open(ctx_path) as f:
                industry_data = json.load(f).get(industry, {})
                industry_vocab = set(k.lower() for k in industry_data.get("vocabulary", {}).keys())
        except Exception:
            pass

        known_terms = set(k.lower() for k in glossary.keys()) | industry_vocab

        # Find candidates: low-confidence entities not in any known vocab
        candidates = []
        for entity in entities:
            name = (entity.get("name", "") or "").strip()
            confidence = entity.get("confidence", 1.0)
            if not name or len(name) < 3:
                continue
            if confidence >= 0.75:
                continue
            if name.lower() in known_terms:
                continue
            candidates.append({
                "term": name,
                "suggested_definition": entity.get("context", ""),
                "source_document_id": document_id,
                "confidence": confidence,
            })
            if len(candidates) >= 10:
                break

        if not candidates:
            return

        # Store in tenant.settings (overwrite existing pending list)
        settings["pending_glossary_confirmations"] = candidates
        crud.tenant.update(db, db_obj=tenant, obj_in={"settings": settings})
        db.commit()

        self.logger.info(
            f"Surfaced {len(candidates)} unknown terms for tenant {tenant_id} "
            f"from document {document_id}"
        )

        # Notify document owner
        try:
            from app.services.notification_service import notify
            notify(
                db=db,
                tenant_id=tenant_id,
                user_id=None,  # broadcast to all tenant admins
                notification_type="glossary_review",
                title="New terms need your review",
                message=(
                    f"{len(candidates)} unknown terms were found in your document. "
                    "Define them to improve AI accuracy."
                ),
                resource_type="document",
                resource_id=document_id,
            )
        except Exception:
            pass
```

### New endpoints — add to backend/app/api/endpoints/documents.py:

```python
@router.get("/{document_id}/unknown-terms")
def get_unknown_terms(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    GET /api/v1/documents/{id}/unknown-terms

    Returns pending_glossary_confirmations from tenant.settings.
    Only returns terms that came from this specific document.
    """
    tenant = crud.tenant.get(db, id=tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    pending = (tenant.settings or {}).get("pending_glossary_confirmations", [])
    doc_terms = [t for t in pending if t.get("source_document_id") == document_id]
    return {"unknown_terms": doc_terms, "total": len(doc_terms)}


@router.post("/{document_id}/confirm-term")
def confirm_term(
    document_id: int,
    term: str,
    definition: str,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    POST /api/v1/documents/{id}/confirm-term

    Moves a term from pending_glossary_confirmations into the tenant glossary.
    Body params: term (str), definition (str).
    """
    tenant = crud.tenant.get(db, id=tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    settings = dict(tenant.settings or {})
    glossary = settings.get("glossary", {}) or {}
    pending = settings.get("pending_glossary_confirmations", [])

    # Add to glossary
    glossary[term] = definition
    settings["glossary"] = glossary

    # Remove from pending
    settings["pending_glossary_confirmations"] = [
        t for t in pending
        if not (t.get("term", "").lower() == term.lower()
                and t.get("source_document_id") == document_id)
    ]

    crud.tenant.update(db, db_obj=tenant, obj_in={"settings": settings})
    db.commit()

    return {
        "status": "confirmed",
        "term": term,
        "definition": definition,
        "glossary_size": len(glossary),
    }
```

### Test commands:
```bash
# Upload a document and let ontology extraction run
# Then check unknown terms endpoint
curl http://localhost:8000/api/v1/documents/1/unknown-terms \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"unknown_terms": [...], "total": N}

# Confirm a term
curl -X POST "http://localhost:8000/api/v1/documents/1/confirm-term?term=settlement&definition=Transfer+of+funds+to+merchant" \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"status": "confirmed", "term": "settlement", ...}
```

### Risk: MEDIUM — modifies tenant.settings in a new code path. The try/except wrapper
in the caller ensures ontology extraction never fails because of glossary surfacing.

---

## P5-06 — Glossary Confirmation UI on Document Page

**Ticket:** P5-06
**Priority:** P2 (depends on P5-05 endpoints being merged)
**File:** `frontend/app/dashboard/documents/[id]/page.tsx`

### Why:
The amber "unknown terms" banner surfaces glossary candidates where the user already
is — on the document detail page. Inline editing (type a definition, click save) gives
instant feedback without navigating away.

### What to add — new component + state in document detail page:
At the top of the file, add new state:
```tsx
const [unknownTerms, setUnknownTerms] = useState<UnknownTerm[]>([])
const [confirmingTerm, setConfirmingTerm] = useState<string | null>(null)
const [termDefinition, setTermDefinition] = useState("")

interface UnknownTerm {
  term: string
  suggested_definition: string
  source_document_id: number
  confidence: number
}
```

In the data fetch useEffect (wherever the page fetches document data), add:
```tsx
// Fetch unknown terms for glossary confirmation
try {
  const termsRes = await api.get(`/api/v1/documents/${id}/unknown-terms`)
  setUnknownTerms(termsRes.data.unknown_terms || [])
} catch {
  // Non-fatal — just don't show the banner
}
```

Add handler for term confirmation:
```tsx
const handleConfirmTerm = async (term: string) => {
  if (!termDefinition.trim()) return
  try {
    await api.post(`/api/v1/documents/${id}/confirm-term`, null, {
      params: { term, definition: termDefinition.trim() }
    })
    setUnknownTerms(prev => prev.filter(t => t.term !== term))
    setConfirmingTerm(null)
    setTermDefinition("")
  } catch (err) {
    console.error("Failed to confirm term:", err)
  }
}
```

Add the banner component inside the JSX (after the document title section):
```tsx
{unknownTerms.length > 0 && (
  <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
    <div className="flex items-start gap-3">
      <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
      <div className="flex-1">
        <h4 className="font-medium text-amber-900">
          {unknownTerms.length} unknown term{unknownTerms.length > 1 ? 's' : ''} found
        </h4>
        <p className="mt-1 text-sm text-amber-700">
          Define these terms to improve AI accuracy for future analyses.
        </p>
        <div className="mt-3 space-y-2">
          {unknownTerms.map((t) => (
            <div key={t.term} className="rounded bg-white border border-amber-200 p-3">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{t.term}</span>
                <span className="text-xs text-gray-400">
                  confidence: {(t.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {t.suggested_definition && (
                <p className="mt-1 text-xs text-gray-500 italic">
                  AI suggests: {t.suggested_definition}
                </p>
              )}
              {confirmingTerm === t.term ? (
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={termDefinition}
                    onChange={e => setTermDefinition(e.target.value)}
                    placeholder="Enter definition..."
                    className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                    onKeyDown={e => e.key === 'Enter' && handleConfirmTerm(t.term)}
                    autoFocus
                  />
                  <button
                    onClick={() => handleConfirmTerm(t.term)}
                    className="rounded bg-amber-600 px-3 py-1 text-xs text-white hover:bg-amber-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => { setConfirmingTerm(null); setTermDefinition("") }}
                    className="rounded border border-gray-300 px-3 py-1 text-xs hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setConfirmingTerm(t.term)
                    setTermDefinition(t.suggested_definition || "")
                  }}
                  className="mt-2 text-xs text-amber-600 hover:text-amber-800 underline"
                >
                  Add definition
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
)}
```

### Test commands:
```bash
# Navigate to /dashboard/documents/[id] for a document that had extraction run
# Expected: amber banner showing unknown terms
# Click "Add definition" → type a definition → press Enter or click Save
# Expected: term disappears from banner, check DB:
psql $DATABASE_URL -c "SELECT settings->'glossary' FROM tenants WHERE id = 1;"
# Expected: the confirmed term appears in the glossary JSON
```

### Risk: LOW — banner only renders if unknownTerms.length > 0.


---

## P5-07 — Onboarding Page

**Ticket:** P5-07
**Priority:** P2 (product polish — blocked on P5-04 industry detection)
**File:** `frontend/app/dashboard/onboarding/page.tsx` (NEW FILE)
**Parallelizable:** YES — pure frontend, no backend dependencies beyond existing APIs

### Why:
New tenants need a guided way to set their industry profile, review the auto-detected
classification, and seed their glossary. The page shows only when
`tenant.settings.onboarding_complete == false`. Three clear steps prevent cognitive
overload.

### What to create:
Create `frontend/app/dashboard/onboarding/page.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Building2, Globe, BookOpen, CheckCircle, ChevronRight, Loader2 } from "lucide-react";

const INDUSTRY_OPTIONS = [
  { value: "fintech/payments", label: "Fintech — Payments" },
  { value: "fintech/lending", label: "Fintech — Lending" },
  { value: "banking", label: "Banking" },
  { value: "healthcare", label: "Healthcare" },
  { value: "saas", label: "SaaS / Software" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "logistics", label: "Logistics" },
  { value: "devtools", label: "Developer Tools" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Company info
  const [companyName, setCompanyName] = useState("");
  const [companyWebsite, setCompanyWebsite] = useState("");

  // Step 2: Industry
  const [selectedIndustry, setSelectedIndustry] = useState("");
  const [detectedIndustry, setDetectedIndustry] = useState<string | null>(null);

  // Step 3: Glossary kickstart
  const [glossaryTerms, setGlossaryTerms] = useState<{ term: string; definition: string }[]>([
    { term: "", definition: "" },
  ]);

  useEffect(() => {
    // Load current tenant settings to pre-populate
    api.get("/api/v1/tenants/me/settings").then(res => {
      const settings = res.data?.settings || {};
      if (settings.onboarding_complete) {
        router.replace("/dashboard");
        return;
      }
      if (settings.industry) {
        setDetectedIndustry(settings.industry);
        setSelectedIndustry(settings.industry);
      }
    }).catch(() => {});
  }, []);

  const handleStep1Submit = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.patch("/api/v1/tenants/me/settings", {
        company_website: companyWebsite,
      });
      setStep(2);
    } catch (e: any) {
      setError(e.message || "Failed to save company info");
    } finally {
      setLoading(false);
    }
  };

  const handleStep2Submit = async () => {
    if (!selectedIndustry) {
      setError("Please select an industry");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.patch("/api/v1/tenants/me/settings", {
        industry: selectedIndustry,
      });
      setStep(3);
    } catch (e: any) {
      setError(e.message || "Failed to save industry");
    } finally {
      setLoading(false);
    }
  };

  const handleStep3Submit = async () => {
    setLoading(true);
    setError(null);
    try {
      // Save non-empty glossary terms
      const validTerms = glossaryTerms.filter(t => t.term.trim() && t.definition.trim());
      const glossary: Record<string, string> = {};
      validTerms.forEach(t => { glossary[t.term.trim()] = t.definition.trim(); });

      await api.patch("/api/v1/tenants/me/settings", {
        glossary,
        onboarding_complete: true,
      });

      router.push("/dashboard");
    } catch (e: any) {
      setError(e.message || "Failed to complete onboarding");
    } finally {
      setLoading(false);
    }
  };

  const addGlossaryRow = () => {
    setGlossaryTerms(prev => [...prev, { term: "", definition: "" }]);
  };

  const updateGlossaryRow = (index: number, field: "term" | "definition", value: string) => {
    setGlossaryTerms(prev => prev.map((t, i) => i === index ? { ...t, [field]: value } : t));
  };

  const STEPS = [
    { id: 1, icon: Building2, label: "Company" },
    { id: 2, icon: Globe, label: "Industry" },
    { id: 3, icon: BookOpen, label: "Glossary" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Welcome to DokyDoc</h1>
          <p className="mt-2 text-gray-500">
            Let's set up your workspace in 3 quick steps
          </p>
        </div>

        {/* Step indicator */}
        <div className="mb-8 flex justify-center gap-0">
          {STEPS.map((s, idx) => (
            <div key={s.id} className="flex items-center">
              <div className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                step === s.id
                  ? "bg-blue-600 text-white"
                  : step > s.id
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-400"
              }`}>
                {step > s.id ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  <s.icon className="h-4 w-4" />
                )}
                {s.label}
              </div>
              {idx < STEPS.length - 1 && (
                <ChevronRight className="mx-1 h-4 w-4 text-gray-300" />
              )}
            </div>
          ))}
        </div>

        {/* Step content card */}
        <div className="rounded-xl bg-white border border-gray-200 p-8 shadow-sm">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Your Company</h2>
                <p className="text-sm text-gray-500 mt-1">
                  We'll use your website to auto-detect your industry
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  placeholder="Acme Corporation"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Website <span className="text-gray-400">(optional)</span>
                </label>
                <input
                  type="url"
                  value={companyWebsite}
                  onChange={e => setCompanyWebsite(e.target.value)}
                  placeholder="https://acme.com"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-gray-400">
                  We'll analyze your website to suggest your industry automatically
                </p>
              </div>
              <button
                onClick={handleStep1Submit}
                disabled={loading || !companyName.trim()}
                className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Continue
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Your Industry</h2>
                {detectedIndustry ? (
                  <p className="text-sm text-blue-600 mt-1">
                    We detected your industry from your website. Confirm or change below.
                  </p>
                ) : (
                  <p className="text-sm text-gray-500 mt-1">
                    This helps DokyDoc inject relevant regulatory context into every AI analysis.
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {INDUSTRY_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedIndustry(opt.value)}
                    className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                      selectedIndustry === opt.value
                        ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                        : "border-gray-200 hover:border-gray-300 text-gray-700"
                    }`}
                  >
                    {detectedIndustry === opt.value && (
                      <span className="text-xs text-blue-400 block mb-1">Detected</span>
                    )}
                    {opt.label}
                  </button>
                ))}
              </div>
              <button
                onClick={handleStep2Submit}
                disabled={loading || !selectedIndustry}
                className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Continue
              </button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Company Glossary</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Define terms specific to your company. DokyDoc will use these in every
                  AI analysis. You can add more anytime.
                </p>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {glossaryTerms.map((t, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      type="text"
                      value={t.term}
                      onChange={e => updateGlossaryRow(i, "term", e.target.value)}
                      placeholder="Term"
                      className="w-1/3 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    />
                    <input
                      type="text"
                      value={t.definition}
                      onChange={e => updateGlossaryRow(i, "definition", e.target.value)}
                      placeholder="Definition..."
                      className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={addGlossaryRow}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                + Add another term
              </button>
              <div className="flex gap-3">
                <button
                  onClick={() => handleStep3Submit()}
                  disabled={loading}
                  className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Complete Setup
                </button>
                <button
                  onClick={() => handleStep3Submit()}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
                >
                  Skip for now
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Required backend endpoint for settings patch** — add to `tenants.py` if not present:
```python
@router.patch("/me/settings")
def update_tenant_settings(
    settings_update: dict,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """PATCH /api/v1/tenants/me/settings — Merge-update tenant.settings JSON."""
    tenant = crud.tenant.get(db, id=tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    current = dict(tenant.settings or {})
    current.update(settings_update)
    crud.tenant.update(db, db_obj=tenant, obj_in={"settings": current})
    db.commit()
    return {"status": "updated", "settings": current}
```

**Route guard in dashboard layout** — in `frontend/app/dashboard/layout.tsx`,
add a check after auth verification:
```tsx
// After auth check, check onboarding
if (tenantSettings && tenantSettings.onboarding_complete === false) {
  router.replace("/dashboard/onboarding");
  return null;
}
```

### Test commands:
```bash
# Register new tenant, set onboarding_complete = false
psql $DATABASE_URL -c "UPDATE tenants SET settings = '{\"onboarding_complete\": false}' WHERE id = 1;"
# Navigate to /dashboard — should redirect to /dashboard/onboarding
# Complete all 3 steps — should redirect back to /dashboard
# Check DB:
psql $DATABASE_URL -c "SELECT settings FROM tenants WHERE id = 1;"
# Expected: settings contains industry, glossary, onboarding_complete: true
```

### Risk: LOW — pure frontend. Route guard is additive.


---

## P5-08 — Wire Context into All Gemini Callers

**Ticket:** P5-08
**Priority:** P1 (this is the final wire-up — depends on P5-03)
**File:** `backend/app/services/ai/gemini.py`

### Why:
P5-03 added the context param to `get_prompt()`. P5-08 makes the callers actually
pass a context. Three Gemini methods are high-priority because they run on every
document: `call_gemini_for_typed_validation`, `call_gemini_for_atomization`, and
`call_gemini_for_enhanced_analysis`. Adding context to these three covers 90%+ of
Gemini spend.

### What to do — locate the three key caller methods in gemini.py:
First, read `backend/app/services/ai/gemini.py` and find the three methods listed.
Use:
```bash
grep -n "def call_gemini_for_typed_validation\|def call_gemini_for_atomization\|def call_gemini_for_enhanced_analysis" \
  backend/app/services/ai/gemini.py
```

For each method, apply this pattern:

**Pattern: Add db + tenant_id params, call build_prompt_context, pass to get_prompt**

#### For call_gemini_for_typed_validation:
Find current signature (example, verify exact line first):
```python
async def call_gemini_for_typed_validation(self, atom_type, atoms, code_analysis,
                                            tenant_id=None, user_id=None):
```

Change to:
```python
async def call_gemini_for_typed_validation(self, atom_type, atoms, code_analysis,
                                            tenant_id=None, user_id=None,
                                            db=None):
    # Phase 5: Build tenant context for prompt injection
    prompt_ctx = None
    if db is not None and tenant_id:
        try:
            from app.services.ai.prompt_context_builder import build_prompt_context
            prompt_ctx = build_prompt_context(db, tenant_id=tenant_id, example_type="validation")
        except Exception:
            pass  # Non-fatal — fall back to context-free prompt
```

Then in the body where `prompt_manager.get_prompt(PromptType.VALIDATION, ...)` is
called, change to:
```python
    prompt = prompt_manager.get_prompt(PromptType.VALIDATION, context=prompt_ctx, ...)
```

#### For call_gemini_for_atomization:
Apply the same pattern. Find the `get_prompt(PromptType.STRUCTURED_EXTRACTION, ...)` or
equivalent call and thread context through. The `example_type` to pass to
`build_prompt_context` should be `"atomization"`.

#### For call_gemini_for_enhanced_analysis (or equivalent entity extraction):
Apply the same pattern. The `example_type` should be `"entity_extraction"`.

### Caller update in validation_service.py (P4 developer coordination):
After P5-08 adds `db=` to the gemini method signatures, the calls in
`validation_service.py` (lines ~291–298) need to pass `db=db`:

```python
# BEFORE (current lines ~291–298):
                forward_tasks = [
                    gemini_service.call_gemini_for_typed_validation(
                        atom_type=atype,
                        atoms=atype_atoms,
                        code_analysis=code_analysis,
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    for atype, atype_atoms in atoms_by_type.items()
                ]

# AFTER — add db=db (Phase 5 wire-up):
                forward_tasks = [
                    gemini_service.call_gemini_for_typed_validation(
                        atom_type=atype,
                        atoms=atype_atoms,
                        code_analysis=code_analysis,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        db=db,   # Phase 5: passes DB session for context building
                    )
                    for atype, atype_atoms in atoms_by_type.items()
                ]
```

**COORDINATION NOTE:** This is the one place where Phase 4 and Phase 5 touch the
same file (`validation_service.py`). The Phase 4 developer owns the file. When
Phase 5 P5-08 is ready to merge, the Phase 4 developer makes the 1-line `db=db`
addition to the forward_tasks list comprehension. This should be a 30-second change.

### Test commands:
```bash
# Set industry on a test tenant
psql $DATABASE_URL -c "UPDATE tenants SET settings = '{\"industry\": \"fintech/payments\", \"glossary\": {\"settlement\": \"Transfer of funds\"}}' WHERE id = 1;"

# Trigger a validation scan and check if prompt context was injected
docker-compose logs backend | grep "Context-enriched prompt"
# Expected: "[Context-enriched prompt for type: validation (industry=fintech/payments, ...)]"
```

### Risk: MEDIUM — modifying gemini.py which is called by many paths. The `db=None`
default with `if db is not None` guard makes this safe for existing callers that
don't pass a DB session.

---

## P5-09 — Industry Profile Management Settings Card

**Ticket:** P5-09
**Priority:** P2 (settings management UX — depends on P5-03 endpoints)
**File:** `frontend/app/dashboard/admin/page.tsx` (add to existing admin/settings page)

### Why:
Tenant admins need a way to review and update their industry classification, glossary,
and few-shot statistics without going through the onboarding wizard again.

### What to add — new settings card in admin page:

Add state at top of admin page component:
```tsx
const [industryProfile, setIndustryProfile] = useState<IndustryProfile | null>(null)
const [editingIndustry, setEditingIndustry] = useState(false)
const [savingIndustry, setSavingIndustry] = useState(false)
const [selectedNewIndustry, setSelectedNewIndustry] = useState("")

interface IndustryProfile {
  industry: string
  sub_domain?: string
  glossary: Record<string, string>
  onboarding_complete: boolean
}
```

Add to data fetch:
```tsx
try {
  const res = await api.get("/api/v1/tenants/me/settings")
  setIndustryProfile({
    industry: res.data.settings?.industry || "",
    sub_domain: res.data.settings?.sub_domain || "",
    glossary: res.data.settings?.glossary || {},
    onboarding_complete: res.data.settings?.onboarding_complete ?? true,
  })
  setSelectedNewIndustry(res.data.settings?.industry || "")
} catch {}
```

Add the industry profile card in JSX:
```tsx
{/* Industry Profile Card */}
<div className="rounded-xl bg-white border border-gray-200 p-6 shadow-sm">
  <div className="flex items-center justify-between mb-4">
    <h3 className="font-semibold text-gray-900">Industry Profile</h3>
    {!editingIndustry && (
      <button
        onClick={() => setEditingIndustry(true)}
        className="text-sm text-blue-600 hover:text-blue-800"
      >
        Edit
      </button>
    )}
  </div>

  {industryProfile ? (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Industry
        </label>
        {editingIndustry ? (
          <select
            value={selectedNewIndustry}
            onChange={e => setSelectedNewIndustry(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">Select industry...</option>
            <option value="fintech/payments">Fintech — Payments</option>
            <option value="fintech/lending">Fintech — Lending</option>
            <option value="banking">Banking</option>
            <option value="healthcare">Healthcare</option>
            <option value="saas">SaaS / Software</option>
            <option value="ecommerce">E-commerce</option>
            <option value="logistics">Logistics</option>
            <option value="devtools">Developer Tools</option>
          </select>
        ) : (
          <p className="mt-1 text-sm font-medium text-gray-900">
            {industryProfile.industry || (
              <span className="text-gray-400 italic">Not set</span>
            )}
          </p>
        )}
      </div>

      <div className="flex gap-6">
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Glossary Terms
          </label>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {Object.keys(industryProfile.glossary || {}).length}
          </p>
        </div>
      </div>

      {editingIndustry && (
        <div className="flex gap-2 pt-2">
          <button
            onClick={async () => {
              setSavingIndustry(true)
              try {
                await api.patch("/api/v1/tenants/me/settings", {
                  industry: selectedNewIndustry,
                })
                setIndustryProfile(prev =>
                  prev ? { ...prev, industry: selectedNewIndustry } : prev
                )
                setEditingIndustry(false)
              } finally {
                setSavingIndustry(false)
              }
            }}
            disabled={savingIndustry}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {savingIndustry ? "Saving..." : "Save"}
          </button>
          <button
            onClick={() => setEditingIndustry(false)}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  ) : (
    <p className="text-sm text-gray-400">Loading industry profile...</p>
  )}
</div>
```

### Test commands:
```bash
# Navigate to /dashboard/admin (or equivalent settings page)
# Expected: "Industry Profile" card with current industry shown
# Click "Edit" → select new industry → Save
# Expected: industry updates in UI and DB
```

### Risk: LOW — read/write through existing settings endpoint.

---

## Phase 5 — Migration Summary

Only one migration for Phase 5:
```bash
cd /home/user/dokydoc/backend

# s15a1: GIN index on tenants.settings
alembic upgrade s15a1

# Or in one shot after all Phase 4+5 migrations are created:
alembic upgrade head
```

Full chain after both phases:
```
s11b1 → s12a1 → s14a1 → s14b1 → s15a1
```

---

## Phase 5 — Completion Checklist

Before marking Phase 5 done, every item below must be verified:

- [ ] `s15a1_tenant_settings_gin_index.py` migration created with `down_revision = 's14b1'`
- [ ] GIN index confirmed via `\di+ ix_tenants_settings_gin` in psql
- [ ] `backend/app/services/ai/industry_context.json` created with all 8 industries
- [ ] JSON validated: `python3 -c "import json; json.load(open(...))"` — no errors
- [ ] `backend/app/services/ai/prompt_context.py` created with PromptContext dataclass
- [ ] `PromptContext.render_full_preamble()` tested — returns non-empty string for non-empty context
- [ ] `backend/app/services/ai/prompt_context_builder.py` created
- [ ] `build_prompt_context()` tested against a real tenant — returns PromptContext
- [ ] `prompt_manager.get_prompt()` signature updated to accept `context=None` (line 1362)
- [ ] Backward compatibility confirmed: existing callers work unchanged
- [ ] Context injection confirmed: prompt with context contains "=== TENANT CONTEXT ==="
- [ ] `backend/app/tasks/tenant_tasks.py` created with `detect_tenant_industry` task
- [ ] `worker.py` updated to include `app.tasks.tenant_tasks`
- [ ] `tenants.py` registration endpoint dispatches `detect_tenant_industry.delay()`
- [ ] Tenant settings updated after registration when website URL provided
- [ ] `business_ontology_service.py` calls `_surface_unknown_terms()` after extraction
- [ ] GET `/api/v1/documents/{id}/unknown-terms` endpoint returns pending terms
- [ ] POST `/api/v1/documents/{id}/confirm-term` endpoint moves term to glossary
- [ ] Amber glossary banner renders on document detail page when unknown terms exist
- [ ] Clicking "Add definition" + Save removes term from banner and adds to glossary
- [ ] `frontend/app/dashboard/onboarding/page.tsx` created with 3-step wizard
- [ ] Onboarding page redirects to `/dashboard` on completion
- [ ] Dashboard layout guards redirect to `/dashboard/onboarding` when `onboarding_complete = false`
- [ ] `call_gemini_for_typed_validation`, `call_gemini_for_atomization`, `call_gemini_for_enhanced_analysis` accept `db=` param
- [ ] Logs show "Context-enriched prompt" for a tenant with industry set
- [ ] Industry profile card renders in admin/settings page
- [ ] Industry can be changed from settings card and persists to DB
- [ ] Phase 4 developer has added `db=db` to the `call_gemini_for_typed_validation` call in validation_service.py (P5-08 coordination step)

---

## Cross-Phase Coordination Points

The following items require explicit coordination between Phase 4 and Phase 5 developers.
Both developers must be available when these are merged:

### Coordination Point 1: P5-08 wire-up in validation_service.py

**Who:** Phase 4 developer makes the change. Phase 5 developer reviews.
**When:** After P5-08 (gemini.py) is merged.
**What:** Add `db=db` to `call_gemini_for_typed_validation` call in
`validation_service.py` lines ~291–298 (the forward_tasks list comprehension).
**Time estimate:** 5 minutes.
**Verification:** Run a validation scan and check logs for "Context-enriched prompt".

### Coordination Point 2: Migration order verification

Before deploying to any shared environment (staging, production), verify the full
chain is intact:
```bash
alembic history | head -8
# Expected output (newest first):
# s15a1 -> head, Add GIN index on tenants.settings
# s14b1 -> s15a1, Add last_validated_at and validation_verdict to concept_mappings
# s14a1 -> s14b1, Add atomized_at_upload flag to requirement_atoms
# s12a1 -> s14a1, Create training_examples table for data flywheel
```

If the chain is broken (wrong `down_revision`), fix before deploying.

### Coordination Point 3: Worker restart required after P5-04 merges

When `app.tasks.tenant_tasks` is added to `worker.py`, the Celery worker MUST be
restarted before the registration endpoint's `detect_tenant_industry.delay()` call
will work. Otherwise it throws `NotRegistered: detect_tenant_industry`.

```bash
docker-compose restart worker
# Verify task is registered:
docker-compose exec worker celery -A app.worker inspect registered | grep detect_tenant_industry
```

---

## Environment — No Manual .env Changes Required

Neither Phase 4 nor Phase 5 introduces new environment variables. All new features
are enabled by code and DB migrations only.

The `industry_context.json` file path is resolved relative to `__file__` in
`prompt_context_builder.py` — it is not configurable via env var (intentional: it's
a static library file, not deployment-specific configuration).

---

## Risk Summary

| Ticket | Risk | Mitigation |
|--------|------|-----------|
| P4-01 | LOW | try/except, async already in place |
| P4-02 | LOW | pure new file |
| P4-03 | MEDIUM | `boe_context=None` default preserves existing behavior |
| P4-04 | LOW | try/except, falls back to no-context scan |
| P4-05 | MEDIUM | db.rollback() in calibration block |
| P4-06 | LOW | pure static method |
| P4-07 | LOW | try/except, mapping trigger is optional |
| P4-08 | LOW | queues tasks, returns immediately |
| P4-09 | LOW | read-only endpoint, additive UI card |
| P5-01 | LOW | GIN index is CONCURRENTLY — no table lock |
| P5-02 | LOW | pure data file |
| P5-03 | MEDIUM | `context=None` default preserves backward compat |
| P5-04 | LOW | fire-and-forget task |
| P5-05 | MEDIUM | try/except in caller, settings mutation in try/except |
| P5-06 | LOW | banner is additive |
| P5-07 | LOW | route guard is additive |
| P5-08 | MEDIUM | `db=None` guard, no-op when not passed |
| P5-09 | LOW | read/patch settings endpoint |

---

## Appendix: Quick Reference — New Files Created

### Phase 4:
| File | Purpose |
|------|---------|
| `backend/alembic/versions/s14a1_atom_upload_flag.py` | Migration: atomized_at_upload column |
| `backend/alembic/versions/s14b1_concept_mapping_validation_fields.py` | Migration: last_validated_at + validation_verdict |
| `backend/app/services/boe_context.py` | BOEContext dataclass |

### Phase 5:
| File | Purpose |
|------|---------|
| `backend/alembic/versions/s15a1_tenant_settings_gin_index.py` | Migration: GIN index |
| `backend/app/services/ai/industry_context.json` | Industry knowledge library |
| `backend/app/services/ai/prompt_context.py` | PromptContext dataclass |
| `backend/app/services/ai/prompt_context_builder.py` | Context builder function |
| `backend/app/tasks/tenant_tasks.py` | detect_tenant_industry Celery task |
| `frontend/app/dashboard/onboarding/page.tsx` | 3-step onboarding wizard |

### Modified files summary:

**Phase 4 owns:**
- `backend/app/tasks/document_pipeline.py` — pre-atomization block
- `backend/app/services/validation_service.py` — BOE context integration + calibration
- `backend/app/services/code_analysis_service.py` — cross-graph mapping trigger
- `backend/app/api/endpoints/analysis_results.py` — run-full + boe-savings endpoints
- `backend/app/models/concept_mapping.py` — new columns
- `frontend/app/dashboard/analytics/page.tsx` — BOE savings card

**Phase 5 owns:**
- `backend/app/services/ai/prompt_manager.py` — context param addition only
- `backend/app/services/ai/gemini.py` — db param addition to 3 methods
- `backend/app/services/business_ontology_service.py` — unknown terms surfacing
- `backend/app/api/endpoints/documents.py` — unknown-terms + confirm-term endpoints
- `backend/app/api/endpoints/tenants.py` — dispatch detect_tenant_industry
- `backend/app/worker.py` — add tenant_tasks to include list
- `frontend/app/dashboard/documents/[id]/page.tsx` — amber glossary banner
- `frontend/app/dashboard/admin/page.tsx` — industry profile card

