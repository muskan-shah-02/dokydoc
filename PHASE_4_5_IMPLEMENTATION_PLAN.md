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

## P5-10 — Registration & Onboarding Gap Fixes (5 Critical Gaps)

**Owner:** Backend Dev 1 (items A, B, D) + Frontend Dev (items C, E)
**Estimate:** 1.5 days
**Priority:** P0 — Without these fixes, auto-detection never fires and the onboarding wizard never activates for any real user
**Depends on:** P5-04 (detection task), P5-07 (onboarding wizard), P5-09 (settings card)

---

### Root Cause Summary

A gap analysis across the registration → auto-detection → onboarding wizard user flow found 5 issues. Two are **showstoppers** that completely prevent the feature from working:

1. **GAP-1 (CRITICAL):** `company_website` input missing from the registration UI → auto-detection task never receives a URL → never dispatches → feature dead for all tenants
2. **GAP-2 (CRITICAL):** `onboarding_complete: false` only set as a side-effect of the detection task → if no website provided, `tenant.settings` is `{}` → dashboard guard checks `=== false` on an undefined value → never triggers → new tenants bypass onboarding entirely
3. **GAP-3 (HIGH):** Onboarding Step 2 loads `detectedIndustry` once on mount — Celery task hasn't finished yet → industry always shows as null → auto-detected pre-selection never works
4. **GAP-4 (HIGH):** `GET /api/v1/tenants/me/settings` endpoint not defined anywhere → P5-07 and P5-09 both crash on initial data load
5. **GAP-5 (MEDIUM):** `INDUSTRY_OPTIONS` array hardcoded separately in P5-07 and P5-09 → drift risk when new industries are added

---

### Fix A — Add `company_website` Field to Registration Form UI (GAP-1)

**File:** `frontend/app/auth/register/page.tsx` (or wherever the tenant signup form lives — search for the registration form component)

**Step 1 — Find the form:** Search the frontend codebase for the registration/signup form:
```bash
grep -r "register\|signup\|TenantCreate\|company_name" frontend/app --include="*.tsx" -l
```

**Step 2 — Add the field:** Inside the registration form, after the "Company Name" input and before the submit button, add:

```tsx
{/* Company Website — optional, used for auto industry detection */}
<div className="space-y-1.5">
  <label htmlFor="company_website"
    className="block text-sm font-medium text-gray-700">
    Company Website
    <span className="ml-1 text-xs text-gray-400 font-normal">(optional — helps us personalise your experience)</span>
  </label>
  <div className="relative">
    <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 text-sm">
      https://
    </span>
    <input
      id="company_website"
      type="url"
      value={companyWebsite}
      onChange={(e) => setCompanyWebsite(e.target.value)}
      placeholder="yourcompany.com"
      className="block w-full rounded-lg border border-gray-300 pl-16 pr-3 py-2.5
                 text-sm focus:border-indigo-500 focus:ring-indigo-500"
    />
  </div>
  <p className="text-xs text-gray-400">
    We'll automatically detect your industry to pre-configure your workspace.
  </p>
</div>
```

**Step 3 — Add state variable** at the top of the component:
```tsx
const [companyWebsite, setCompanyWebsite] = useState("");
```

**Step 4 — Include in form submission payload:**
```tsx
// In the registration submit handler, add company_website to the request body:
const payload = {
  email,
  password,
  company_name: companyName,
  company_website: companyWebsite.trim()
    ? (companyWebsite.startsWith("http") ? companyWebsite.trim() : `https://${companyWebsite.trim()}`)
    : undefined,
  // ... other existing fields
};
```

> **URL normalisation:** The `https://` prefix is prepended if missing so the Celery task always receives a valid URL. The `https://` label in the input is cosmetic — the user types `yourcompany.com`, the code sends `https://yourcompany.com`.

---

### Fix B — Set `onboarding_complete: false` at Tenant Creation (GAP-2)

**File:** `backend/app/api/endpoints/tenants.py`

Find the tenant registration handler (the `POST /register` or `POST /` endpoint that creates a new tenant). **Immediately after** the tenant record is committed to the DB — and **before** the optional `detect_tenant_industry.delay()` call — add:

```python
# ── P5-10 Fix B: Ensure onboarding_complete is always initialised ─────────
# Must be set unconditionally so the dashboard guard triggers even when
# company_website is absent and the auto-detection task is not dispatched.
_initial_settings = dict(tenant.settings or {})
_initial_settings["onboarding_complete"] = False
crud.tenant.update(db, db_obj=tenant, obj_in={"settings": _initial_settings})
db.commit()
# ─────────────────────────────────────────────────────────────────────────

# THEN: dispatch auto-detection (existing P5-04 logic):
company_website = getattr(tenant_in, "company_website", None)
if company_website:
    try:
        detect_tenant_industry.delay(tenant.id, company_website)
    except Exception:
        pass   # Never block registration
```

> **Order matters:** Set `onboarding_complete: false` FIRST, then dispatch the task. The task's `setdefault("onboarding_complete", False)` in P5-04 is now redundant (but harmless) — it will skip setting the key since it already exists. Remove the `setdefault` line from the task to keep the logic clean.

**Also update `TenantCreate` schema** to include `company_website` if not already present:

```python
# backend/app/schemas/tenant.py
class TenantCreate(BaseModel):
    name: str
    subdomain: str
    email: str                                   # admin email
    password: str
    company_website: Optional[str] = None        # ← ADD if missing
    # ... other existing fields
```

---

### Fix C — Poll for Auto-Detection Result in Onboarding Step 2 (GAP-3)

**File:** `frontend/app/dashboard/onboarding/page.tsx`

Add a polling `useEffect` that activates when the user enters Step 2 and `detectedIndustry` is still null. Polls every 3 seconds for up to 24 seconds, then gives up and lets the user select manually.

**Step 1 — Add polling state:**
```tsx
// Add alongside the existing state declarations:
const [isDetecting, setIsDetecting] = useState(false);
```

**Step 2 — Add polling effect** (add after the existing mount `useEffect`):
```tsx
useEffect(() => {
  // Only poll on Step 2, and only if no industry detected yet
  if (step !== 2 || detectedIndustry) return;

  setIsDetecting(true);
  let attempts = 0;
  const MAX_ATTEMPTS = 8;   // 8 × 3s = 24s max wait

  const poll = setInterval(async () => {
    attempts++;
    try {
      const res = await api.get("/api/v1/tenants/me/settings");
      const industry = res.data?.settings?.industry;
      if (industry) {
        setDetectedIndustry(industry);
        setSelectedIndustry(industry);
        setIsDetecting(false);
        clearInterval(poll);
      } else if (attempts >= MAX_ATTEMPTS) {
        setIsDetecting(false);   // Give up — show manual selection
        clearInterval(poll);
      }
    } catch {
      setIsDetecting(false);
      clearInterval(poll);
    }
  }, 3000);

  return () => {
    clearInterval(poll);
    setIsDetecting(false);
  };
}, [step, detectedIndustry]);
```

**Step 3 — Update Step 2 JSX** to show detection status:
```tsx
{/* Replace or augment the existing Step 2 industry selection section: */}

{/* Detection status banner */}
{isDetecting && (
  <div className="flex items-center gap-2 rounded-lg bg-indigo-50 border border-indigo-100
                  px-4 py-3 mb-4">
    <Loader2 className="h-4 w-4 animate-spin text-indigo-500 flex-shrink-0" />
    <div>
      <p className="text-sm font-medium text-indigo-700">
        Analysing your website...
      </p>
      <p className="text-xs text-indigo-500 mt-0.5">
        We're detecting your industry automatically. This takes up to 20 seconds.
      </p>
    </div>
  </div>
)}

{detectedIndustry && !isDetecting && (
  <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200
                  px-4 py-3 mb-4">
    <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
    <p className="text-sm text-green-700 font-medium">
      Industry auto-detected from your website
      <span className="ml-1 font-normal text-green-600">— you can change it below</span>
    </p>
  </div>
)}

{!detectedIndustry && !isDetecting && (
  <p className="text-sm text-gray-500 mb-4">
    We couldn't auto-detect your industry. Please select below.
  </p>
)}

{/* Industry selection — disable while detecting */}
<div className={`grid grid-cols-2 gap-3 ${isDetecting ? "opacity-50 pointer-events-none" : ""}`}>
  {INDUSTRY_OPTIONS.map((opt) => (
    <button
      key={opt.value}
      onClick={() => setSelectedIndustry(opt.value)}
      className={`rounded-lg border px-4 py-3 text-left text-sm transition-all ${
        selectedIndustry === opt.value
          ? "border-indigo-500 bg-indigo-50 text-indigo-700 font-medium"
          : "border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50"
      }`}
    >
      {opt.label}
      {opt.value === detectedIndustry && (
        <span className="ml-1.5 text-[10px] font-semibold text-green-600 uppercase tracking-wide">
          Detected
        </span>
      )}
    </button>
  ))}
</div>
```

---

### Fix D — Define `GET /api/v1/tenants/me/settings` Endpoint (GAP-4)

**File:** `backend/app/api/endpoints/tenants.py`

Add the `GET` endpoint **immediately before** the `PATCH /me/settings` endpoint (specified in P5-07). Both endpoints live in the same router:

```python
# GET /api/v1/tenants/me/settings
@router.get("/me/settings")
def get_tenant_settings(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """
    Return current tenant settings JSON.

    Used by:
    - Onboarding wizard (P5-07) to load pre-detected industry
    - Industry Profile card (P5-09) to populate the settings form
    - Dashboard layout guard to check onboarding_complete flag
    - Auto-detection polling (P5-10) to check if industry is ready

    Returns:
      { "settings": { ... }, "tenant_id": N }
    """
    tenant = crud.tenant.get(db, id=tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "settings": tenant.settings or {},
        "tenant_id": tenant_id,
    }


# PATCH /api/v1/tenants/me/settings  ← already in P5-07, place immediately after GET
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

> **Important:** Both routes must be registered in the same `router` object in `tenants.py`. No new router registration needed — they share the existing `/tenants` prefix.

---

### Fix E — Extract Shared `INDUSTRY_OPTIONS` Constant (GAP-5)

**New file:** `frontend/lib/constants/industry-options.ts`

```typescript
// frontend/lib/constants/industry-options.ts
/**
 * Canonical list of industry options used across:
 * - Onboarding wizard (P5-07)
 * - Industry Profile settings card (P5-09)
 * - Auto-detection Gemini prompt (P5-04 — backend Python mirrors this list)
 *
 * When adding a new industry: update this file AND the Python INDUSTRY_PROMPT
 * in backend/app/tasks/tenant_tasks.py.
 */
export const INDUSTRY_OPTIONS = [
  { value: "fintech/payments",  label: "Fintech — Payments" },
  { value: "fintech/lending",   label: "Fintech — Lending" },
  { value: "banking",           label: "Banking" },
  { value: "healthcare",        label: "Healthcare" },
  { value: "saas",              label: "SaaS / Software" },
  { value: "ecommerce",         label: "E-commerce" },
  { value: "logistics",         label: "Logistics" },
  { value: "devtools",          label: "Developer Tools" },
] as const;

export type IndustryValue = typeof INDUSTRY_OPTIONS[number]["value"];
export type IndustryOption = typeof INDUSTRY_OPTIONS[number];
```

**Update `frontend/app/dashboard/onboarding/page.tsx`:**
```tsx
// Remove the local INDUSTRY_OPTIONS array defined in P5-07
// Add import at top:
import { INDUSTRY_OPTIONS } from "@/lib/constants/industry-options";
```

**Update `frontend/app/dashboard/admin/page.tsx`:**
```tsx
// Replace the hardcoded <option> list in the settings card with:
import { INDUSTRY_OPTIONS } from "@/lib/constants/industry-options";

// In JSX:
<select value={selectedNewIndustry} onChange={...}>
  <option value="">Select industry...</option>
  {INDUSTRY_OPTIONS.map((opt) => (
    <option key={opt.value} value={opt.value}>{opt.label}</option>
  ))}
</select>
```

---

### P5-10 Verification Commands

```bash
# ── Fix A: Registration form captures website ──────────────────────────────
# 1. Open /register in the browser
# Expected: "Company Website (optional)" field visible below "Company Name"
# 2. Register with website = "stripe.com"
# Expected: payload sent includes company_website: "https://stripe.com"

# ── Fix B: onboarding_complete set at creation ─────────────────────────────
# Register a test tenant WITHOUT providing a website:
curl -X POST http://localhost:8000/api/v1/tenants/register \
  -H "Content-Type: application/json" \
  -d '{"name":"NoWebsiteCo","subdomain":"nowebsite99","email":"a@a.com","password":"pass"}'

# Check settings immediately:
psql $DATABASE_URL -c \
  "SELECT settings FROM tenants WHERE subdomain = 'nowebsite99';"
# Expected: {"onboarding_complete": false}   ← NOT empty {}

# ── Fix D: GET /me/settings works ─────────────────────────────────────────
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/tenants/me/settings | python3 -m json.tool
# Expected: { "settings": {"onboarding_complete": false, ...}, "tenant_id": N }

# ── Dashboard guard triggers ───────────────────────────────────────────────
# Log in as the no-website tenant → navigate to /dashboard
# Expected: browser redirects to /dashboard/onboarding

# ── Fix C: Auto-detection polling works ───────────────────────────────────
# Register WITH website = "stripe.com"
# Log in → navigate to /dashboard → redirected to /dashboard/onboarding
# Click "Next" to reach Step 2
# Expected: spinning "Analysing your website..." banner shown
# After 5–20 seconds:
# Expected: banner changes to green "Industry auto-detected from your website"
# Expected: "Fintech — Payments" card is pre-selected with "Detected" badge

# ── Fix E: Shared constant used in both pages ─────────────────────────────
grep -r "INDUSTRY_OPTIONS" frontend/ --include="*.ts" --include="*.tsx"
# Expected: only ONE definition (in lib/constants/industry-options.ts)
# Expected: imports in onboarding/page.tsx and admin/page.tsx
```

---

### P5-10 Developer Checklist

**Backend Dev 1:**
- [ ] **Fix B** — Add `onboarding_complete: false` write immediately after tenant record creation in registration handler (before `detect_tenant_industry.delay()`)
- [ ] **Fix B** — Add `company_website: Optional[str] = None` to `TenantCreate` schema if not already present
- [ ] **Fix B** — Remove now-redundant `setdefault("onboarding_complete", False)` from `detect_tenant_industry` Celery task
- [ ] **Fix D** — Add `GET /me/settings` endpoint to `tenants.py` immediately before the existing `PATCH /me/settings`
- [ ] **Fix D** — Write test: unauthenticated request → 401; authenticated request → 200 with `settings` dict
- [ ] **Fix D** — Write test: newly registered tenant → `settings.onboarding_complete === false`

**Frontend Dev:**
- [ ] **Fix A** — Find the registration/signup form component (search for company_name input)
- [ ] **Fix A** — Add `companyWebsite` state and "Company Website (optional)" URL input field
- [ ] **Fix A** — Add `https://` prefix normalisation before including in payload
- [ ] **Fix C** — Add `isDetecting` state to onboarding page
- [ ] **Fix C** — Add polling `useEffect` that fires on Step 2, polls `GET /me/settings` every 3s, max 8 attempts
- [ ] **Fix C** — Add "Analysing your website..." spinner banner (shown while `isDetecting`)
- [ ] **Fix C** — Add green "Auto-detected" success banner (shown after detection completes)
- [ ] **Fix C** — Add "Detected" badge inside the pre-selected industry card
- [ ] **Fix C** — Disable industry card grid while `isDetecting` (opacity + pointer-events-none)
- [ ] **Fix E** — Create `frontend/lib/constants/industry-options.ts` with shared `INDUSTRY_OPTIONS` array
- [ ] **Fix E** — Replace local `INDUSTRY_OPTIONS` array in `onboarding/page.tsx` with import
- [ ] **Fix E** — Replace hardcoded `<option>` list in `admin/page.tsx` settings card with import

---

### Files Modified by P5-10

| File | Change |
|------|--------|
| `backend/app/schemas/tenant.py` | Add `company_website: Optional[str] = None` to `TenantCreate` |
| `backend/app/api/endpoints/tenants.py` | Add `GET /me/settings`; add `onboarding_complete: false` write at registration; remove `setdefault` from task |
| `backend/app/tasks/tenant_tasks.py` | Remove `setdefault("onboarding_complete", False)` (now done at creation) |
| `frontend/app/auth/register/page.tsx` | Add `company_website` field + state + payload inclusion |
| `frontend/app/dashboard/onboarding/page.tsx` | Add `isDetecting` state + polling effect + Step 2 UX (banners, "Detected" badge, disabled state); replace local INDUSTRY_OPTIONS with import |
| `frontend/app/dashboard/admin/page.tsx` | Replace hardcoded industry `<option>` list with imported INDUSTRY_OPTIONS |
| `frontend/lib/constants/industry-options.ts` | **NEW** — shared INDUSTRY_OPTIONS constant + IndustryValue type |

---

## P5-11 — "Other" Industry Option + Custom Industry Input UI

**Owner:** Frontend Dev  
**Estimate:** 1 day  
**Priority:** P1 — Without this, every tenant outside the 8 known industries has zero domain context  
**Depends on:** P5-10 Fix E (INDUSTRY_OPTIONS shared constant), P5-12 (matcher API)

---

### Why

The fixed grid of 8 industry buttons covers only the industries DokyDoc launched with. Any tenant in insurance, real estate, education, media, government, telecom, or travel must currently pick the "closest" known industry — which degrades prompt quality. The "Other" option + live parent-matching gives them accurate classification without friction.

---

### Updated `frontend/lib/constants/industry-options.ts`

Extend the shared constant (from P5-10 Fix E) to include an "other" sentinel:

```typescript
export const INDUSTRY_OPTIONS = [
  { value: "fintech/payments",  label: "Fintech — Payments",  emoji: "💳" },
  { value: "fintech/lending",   label: "Fintech — Lending",   emoji: "🏦" },
  { value: "banking",           label: "Banking",             emoji: "🏛️" },
  { value: "healthcare",        label: "Healthcare",          emoji: "🏥" },
  { value: "saas",              label: "SaaS / Software",     emoji: "☁️" },
  { value: "ecommerce",         label: "E-commerce",          emoji: "🛒" },
  { value: "logistics",         label: "Logistics",           emoji: "🚚" },
  { value: "devtools",          label: "Developer Tools",     emoji: "🛠️" },
] as const;

// Sentinel value stored in tenant.settings.industry when user chooses "Other"
export const OTHER_INDUSTRY_SENTINEL = "other";

export type KnownIndustryValue = typeof INDUSTRY_OPTIONS[number]["value"];
export type IndustryValue = KnownIndustryValue | string;   // string = custom slug
export type IndustryOption = typeof INDUSTRY_OPTIONS[number];

export function isKnownIndustry(slug: string): slug is KnownIndustryValue {
  return INDUSTRY_OPTIONS.some((o) => o.value === slug);
}

export function getIndustryLabel(slug: string): string {
  const known = INDUSTRY_OPTIONS.find((o) => o.value === slug);
  if (known) return known.label;
  if (!slug || slug === OTHER_INDUSTRY_SENTINEL) return "Other";
  // Custom slug: capitalise and de-slug
  return slug.replace(/[/_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
```

---

### Updated Onboarding Step 2 (`frontend/app/dashboard/onboarding/page.tsx`)

**State additions:**
```tsx
const [isOther, setIsOther]           = useState(false);
const [customIndustry, setCustomIndustry] = useState("");
const [matchResult, setMatchResult]   = useState<IndustryMatchResult | null>(null);
const [isMatching, setIsMatching]     = useState(false);

interface IndustryMatchResult {
  slug: string;              // e.g. "banking/insurance"
  display_name: string;      // e.g. "Insurance & InsurTech"
  parent_slug: string | null; // e.g. "banking"
  parent_label: string | null; // e.g. "Banking"
  confidence: number;         // 0.0–1.0
  is_known_parent: boolean;
}
```

**Live matching — debounced call as user types:**
```tsx
useEffect(() => {
  if (!isOther || customIndustry.trim().length < 3) {
    setMatchResult(null);
    return;
  }
  setIsMatching(true);
  const timer = setTimeout(async () => {
    try {
      const res = await api.post("/api/v1/industries/match", {
        query: customIndustry.trim(),
      });
      setMatchResult(res.data);
    } catch {
      setMatchResult(null);
    } finally {
      setIsMatching(false);
    }
  }, 600);   // 600ms debounce — don't call on every keystroke
  return () => clearTimeout(timer);
}, [customIndustry, isOther]);
```

**Industry grid with "Other" card at the end:**
```tsx
{/* Known industry cards */}
<div className="grid grid-cols-2 gap-3">
  {INDUSTRY_OPTIONS.map((opt) => (
    <button
      key={opt.value}
      onClick={() => { setSelectedIndustry(opt.value); setIsOther(false); }}
      className={`rounded-xl border p-4 text-left transition-all ${
        selectedIndustry === opt.value && !isOther
          ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200"
          : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
      }`}
    >
      <span className="text-2xl">{opt.emoji}</span>
      <p className="mt-2 text-sm font-medium text-gray-800">{opt.label}</p>
      {opt.value === detectedIndustry && (
        <span className="mt-1 inline-block text-[10px] font-bold text-green-600 uppercase">
          Auto-detected ✓
        </span>
      )}
    </button>
  ))}

  {/* "Other" card — always last */}
  <button
    onClick={() => { setIsOther(true); setSelectedIndustry(""); }}
    className={`rounded-xl border p-4 text-left transition-all ${
      isOther
        ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200"
        : "border-gray-200 border-dashed hover:border-gray-300 hover:bg-gray-50"
    }`}
  >
    <span className="text-2xl">🏢</span>
    <p className="mt-2 text-sm font-medium text-gray-800">Other / Not listed</p>
    <p className="text-xs text-gray-400 mt-0.5">Tell us your industry</p>
  </button>
</div>

{/* Custom industry input — shown only when "Other" is selected */}
{isOther && (
  <div className="mt-4 space-y-3 rounded-xl border border-indigo-100 bg-indigo-50 p-4">
    <label className="block text-sm font-medium text-gray-700">
      Describe your industry
    </label>
    <input
      type="text"
      value={customIndustry}
      onChange={(e) => setCustomIndustry(e.target.value)}
      placeholder="e.g. Insurance, Real Estate, Education, Government Tech..."
      className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm
                 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      autoFocus
    />

    {/* Live matching feedback */}
    {isMatching && (
      <div className="flex items-center gap-2 text-xs text-indigo-600">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Finding the best match...
      </div>
    )}

    {matchResult && !isMatching && (
      <div className="rounded-lg border bg-white p-3 space-y-2">
        {matchResult.is_known_parent && matchResult.parent_label ? (
          <div className="flex items-start gap-2">
            <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-gray-800">
                Looks like a sub-industry of <strong>{matchResult.parent_label}</strong>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                You'll inherit {matchResult.parent_label} regulations and terminology,
                plus {matchResult.display_name}-specific context.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-gray-800">
                New industry: <strong>{matchResult.display_name}</strong>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                We'll generate a custom knowledge profile for your industry in the
                background. This takes about 30 seconds.
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <span className="text-xs text-gray-400">
            Classification: <code className="text-indigo-600">{matchResult.slug}</code>
          </span>
          {matchResult.confidence < 0.6 && (
            <span className="text-xs text-amber-600">
              (low confidence — you can edit if incorrect)
            </span>
          )}
        </div>
      </div>
    )}
  </div>
)}
```

**Updated Step 2 submit handler:**
```tsx
const handleStep2Submit = async () => {
  let finalSlug: string;
  let displayName: string;
  let parentSlug: string | null = null;

  if (isOther) {
    if (!customIndustry.trim()) {
      setError("Please describe your industry");
      return;
    }
    if (matchResult) {
      finalSlug = matchResult.slug;
      displayName = matchResult.display_name;
      parentSlug = matchResult.parent_slug;
    } else {
      // No match result yet (still typing) — use raw input as slug
      finalSlug = customIndustry.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
      displayName = customIndustry.trim();
    }
  } else {
    if (!selectedIndustry) {
      setError("Please select an industry");
      return;
    }
    finalSlug = selectedIndustry;
    displayName = getIndustryLabel(selectedIndustry);
  }

  setLoading(true);
  setError(null);
  try {
    await api.patch("/api/v1/tenants/me/settings", {
      industry: finalSlug,
      industry_display_name: displayName,
      parent_industry: parentSlug,
      industry_is_known: isKnownIndustry(finalSlug),
    });
    setStep(3);
  } catch (e: any) {
    setError(e.message || "Failed to save industry");
  } finally {
    setLoading(false);
  }
};
```

---

### Updated Industry Profile Settings Card (`frontend/app/dashboard/admin/page.tsx`)

Add the same "Other" option + custom input to the P5-09 settings card so admins can re-classify their industry post-onboarding. The card already has a `select` dropdown — replace it:

```tsx
// Replace the existing <select> in the P5-09 card with this:
{editingIndustry ? (
  <div className="space-y-3">
    {/* Known industry select */}
    <select
      value={isKnownIndustry(selectedNewIndustry) ? selectedNewIndustry : "other"}
      onChange={(e) => {
        if (e.target.value === "other") {
          setIsEditingOther(true);
          setSelectedNewIndustry("");
        } else {
          setIsEditingOther(false);
          setSelectedNewIndustry(e.target.value);
        }
      }}
      className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
    >
      <option value="">Select industry...</option>
      {INDUSTRY_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
      <option value="other">Other / Custom industry...</option>
    </select>

    {/* Custom input when "Other" selected */}
    {isEditingOther && (
      <input
        type="text"
        value={customIndustryEdit}
        onChange={(e) => setCustomIndustryEdit(e.target.value)}
        placeholder="e.g. Insurance, Real Estate, EdTech..."
        className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
                   focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
      />
    )}
  </div>
) : (
  <p className="mt-1 text-sm font-medium text-gray-900">
    {industryProfile?.industry
      ? getIndustryLabel(industryProfile.industry)
      : <span className="text-gray-400 italic">Not set</span>
    }
  </p>
)}
```

---

### Developer Checklist (P5-11)

- [ ] Add `emoji` field to `INDUSTRY_OPTIONS` in `industry-options.ts`
- [ ] Add `OTHER_INDUSTRY_SENTINEL`, `isKnownIndustry()`, `getIndustryLabel()` exports
- [ ] Add `isOther`, `customIndustry`, `matchResult`, `isMatching` state to onboarding page
- [ ] Implement debounced `POST /api/v1/industries/match` call (600ms)
- [ ] Render "Other" card as last item in grid
- [ ] Render custom input + live match result panel when `isOther` is true
- [ ] Update Step 2 submit handler to resolve final slug from `matchResult`
- [ ] Save `industry_display_name`, `parent_industry`, `industry_is_known` to settings
- [ ] Update admin settings card to include "Other / Custom" option in select
- [ ] Test: Known industry selected → `industry_is_known: true` saved
- [ ] Test: Custom industry typed → match result shown → slug saved correctly
- [ ] Test: Sub-industry detected → parent label shown in match result panel


---

## P5-12 — Industry Taxonomy & Sub-Industry Parent Matching Service

**Owner:** Backend Dev 1  
**Estimate:** 1.5 days  
**Priority:** P1 — Powers the live matching in P5-11 and feeds P5-13 generation  
**New files:** `backend/app/services/industry_matcher.py`, `backend/app/api/endpoints/industries.py`  
**Depends on:** P5-02 (industry_context.json exists)

---

### Why

When a user types "Property Insurance", the system needs to:
1. Detect that "insurance" maps to the parent industry "banking"
2. Suggest the slug `banking/insurance`
3. Inherit banking's regulations + vocabulary automatically
4. Only trigger full AI profile generation (P5-13) if NO known parent exists

This is pure deterministic matching — zero Gemini cost, runs in <10ms.

---

### Industry Taxonomy — Add to `industry_context.json`

**File:** `backend/app/services/ai/industry_context.json`

Add a top-level `"__taxonomy__"` key (double-underscore prefix prevents collision with real industry slugs). This maps keyword patterns → known parent slugs:

```json
{
  "__taxonomy__": {
    "parent_keywords": {
      "fintech": [
        "payment", "payments", "fintech", "financial technology", "money transfer",
        "remittance", "wallet", "neobank", "challenger bank", "open banking",
        "embedded finance", "buy now pay later", "bnpl", "crypto", "defi",
        "lending", "loan", "mortgage", "credit", "underwriting", "insurtech"
      ],
      "banking": [
        "bank", "banking", "insurance", "insurer", "insuretech", "insurtech",
        "wealth management", "asset management", "investment", "brokerage",
        "fund", "hedge fund", "treasury", "capital markets", "trading",
        "forex", "fx", "securities", "stock", "equity"
      ],
      "healthcare": [
        "health", "healthcare", "medical", "clinic", "hospital", "pharma",
        "pharmaceutical", "biotech", "life sciences", "mental health",
        "telemedicine", "telehealth", "dental", "vision", "wellness",
        "fitness", "nutrition", "care", "therapy", "therapeutics", "diagnostics",
        "medtech", "healthtech", "digital health", "patient"
      ],
      "saas": [
        "software", "saas", "platform", "cloud", "b2b", "enterprise software",
        "hr tech", "hrtech", "hr software", "payroll", "erp", "crm",
        "project management", "collaboration", "productivity", "workflow",
        "automation", "no-code", "low-code", "api", "developer platform",
        "data platform", "analytics platform", "bi tool", "business intelligence",
        "martech", "marketing technology", "adtech", "proptech"
      ],
      "ecommerce": [
        "ecommerce", "e-commerce", "retail", "marketplace", "shop", "store",
        "shopping", "consumer", "d2c", "direct to consumer", "subscription box",
        "fashion", "apparel", "beauty", "cosmetics", "food delivery",
        "grocery", "furniture", "electronics retail"
      ],
      "logistics": [
        "logistics", "supply chain", "shipping", "freight", "delivery",
        "courier", "warehouse", "fulfilment", "fulfillment", "transport",
        "trucking", "fleet", "last mile", "cold chain", "3pl", "4pl",
        "port", "customs", "import", "export", "trade"
      ],
      "devtools": [
        "developer tool", "devtool", "devops", "devsecops", "ci/cd",
        "monitoring", "observability", "security tool", "code review",
        "testing", "qa tool", "documentation", "api gateway", "sdk",
        "infrastructure", "cloud infrastructure", "kubernetes", "container"
      ]
    },
    "sub_industry_display_names": {
      "banking/insurance":         "Insurance & InsurTech",
      "banking/wealth":            "Wealth Management",
      "banking/investment":        "Investment & Capital Markets",
      "fintech/crypto":            "Crypto & DeFi",
      "fintech/bnpl":              "Buy Now Pay Later",
      "fintech/remittance":        "Remittance & Money Transfer",
      "healthcare/telemedicine":   "Telemedicine & Digital Health",
      "healthcare/pharma":         "Pharma & Life Sciences",
      "healthcare/mentalhealth":   "Mental Health Tech",
      "healthcare/dental":         "Dental & Vision",
      "saas/hrtech":               "HR Tech & Payroll",
      "saas/martech":              "MarTech & AdTech",
      "saas/proptech":             "PropTech & Real Estate Tech",
      "saas/edtech":               "EdTech & Learning Platforms",
      "ecommerce/fashion":         "Fashion & Apparel",
      "ecommerce/food":            "Food & Grocery Delivery",
      "logistics/freight":         "Freight & International Shipping"
    }
  },
  "fintech/payments": { ... },
  ...
}
```

---

### New Service: `backend/app/services/industry_matcher.py`

```python
# backend/app/services/industry_matcher.py
"""
IndustryMatcherService — deterministic parent-industry matching.

Takes a free-text industry description and returns:
  - slug: best-match slug (e.g. "banking/insurance")
  - parent_slug: known parent if found (e.g. "banking")
  - display_name: human name (e.g. "Insurance & InsurTech")
  - is_known_parent: True if parent exists in industry_context.json
  - confidence: float 0.0-1.0

Zero Gemini cost — pure keyword matching with token overlap scoring.
Runs in <10ms.
"""
import json
import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class IndustryMatchResult:
    slug: str
    parent_slug: Optional[str]
    display_name: str
    is_known_parent: bool
    confidence: float
    reasoning: str


_CONTEXT_PATH = os.path.join(os.path.dirname(__file__), "ai", "industry_context.json")
_taxonomy: dict = {}
_known_slugs: set = set()

try:
    with open(_CONTEXT_PATH, "r") as f:
        _data = json.load(f)
        _taxonomy = _data.get("__taxonomy__", {})
        _known_slugs = {k for k in _data if not k.startswith("__")}
except Exception:
    pass


class IndustryMatcherService:

    def match(self, query: str) -> IndustryMatchResult:
        """
        Match a free-text industry description to the best industry slug.

        Algorithm:
        1. Normalize query to lowercase tokens
        2. Score each known parent by keyword overlap
        3. If best score > 0.2: determine sub-industry slug
        4. Check taxonomy display_names for known sub-industry
        5. Return result with confidence score
        """
        if not query or not _taxonomy:
            return self._unknown(query)

        normalized = query.lower().strip()
        tokens = set(re.split(r"[\s\-/&,]+", normalized))

        # Step 1: Score each parent
        parent_keywords: dict = _taxonomy.get("parent_keywords", {})
        scores: dict[str, float] = {}

        for parent, keywords in parent_keywords.items():
            keyword_tokens_list = [
                set(re.split(r"[\s\-/&,]+", kw.lower())) for kw in keywords
            ]
            # Score = max overlap ratio across all keywords for this parent
            best = 0.0
            for kw_tokens in keyword_tokens_list:
                overlap = len(tokens & kw_tokens)
                union = len(tokens | kw_tokens)
                if union > 0:
                    ratio = overlap / union
                    if ratio > best:
                        best = ratio
                # Also check if full keyword is substring of query
                for kw in keywords:
                    if kw.lower() in normalized:
                        best = max(best, 0.8)  # Strong signal for substring match
            scores[parent] = best

        # Step 2: Find best parent
        best_parent = max(scores, key=scores.get) if scores else None
        best_score = scores.get(best_parent, 0.0) if best_parent else 0.0

        if best_score < 0.1:
            return self._unknown(query)

        # Step 3: Build sub-industry slug
        # Remove parent keywords from query to isolate the differentiator
        sub_keywords = parent_keywords.get(best_parent, [])
        residual = normalized
        for kw in sorted(sub_keywords, key=len, reverse=True):
            residual = residual.replace(kw.lower(), "").strip()

        # Normalize residual to slug component
        sub_slug = re.sub(r"[^a-z0-9]+", "_", residual.strip()).strip("_")[:30]

        if sub_slug:
            candidate_slug = f"{best_parent}/{sub_slug}"
        else:
            candidate_slug = best_parent

        # Step 4: Check taxonomy display_names for known sub-industry
        display_names: dict = _taxonomy.get("sub_industry_display_names", {})
        display_name = display_names.get(candidate_slug)

        if not display_name:
            # Generate display name from query
            display_name = query.strip().title()

        return IndustryMatchResult(
            slug=candidate_slug,
            parent_slug=best_parent if best_parent in _known_slugs else None,
            display_name=display_name,
            is_known_parent=best_parent in _known_slugs,
            confidence=round(min(best_score * 1.2, 1.0), 2),
            reasoning=f"Matched '{best_parent}' parent with score {best_score:.2f}",
        )

    def _unknown(self, query: str) -> IndustryMatchResult:
        """Return result for completely unknown industry with no parent match."""
        slug = re.sub(r"[^a-z0-9]+", "_", (query or "unknown").lower().strip())[:40].strip("_")
        return IndustryMatchResult(
            slug=slug,
            parent_slug=None,
            display_name=query.strip().title() if query else "Unknown",
            is_known_parent=False,
            confidence=0.0,
            reasoning="No keyword overlap with known parent industries",
        )


industry_matcher = IndustryMatcherService()
```

---

### New API Endpoint: `POST /api/v1/industries/match`

**New file:** `backend/app/api/endpoints/industries.py`

```python
# backend/app/api/endpoints/industries.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.api import deps
from app.services.industry_matcher import industry_matcher

router = APIRouter(prefix="/industries", tags=["Industries"])


class IndustryMatchRequest(BaseModel):
    query: str   # e.g. "Property Insurance" or "EdTech"


class IndustryMatchResponse(BaseModel):
    slug: str
    parent_slug: str | None
    display_name: str
    parent_label: str | None
    is_known_parent: bool
    confidence: float
    reasoning: str


@router.post("/match", response_model=IndustryMatchResponse)
def match_industry(
    body: IndustryMatchRequest,
    current_user=Depends(deps.get_current_active_user),
):
    """
    Match a free-text industry description to the best slug + parent.
    Used by the onboarding wizard and admin settings for custom industry input.
    Pure deterministic matching — zero AI cost, <10ms response time.
    """
    from app.services.ai.industry_context import _INDUSTRY_CONTEXT  # reuse loaded dict

    result = industry_matcher.match(body.query)

    # Resolve parent display label
    parent_label = None
    if result.parent_slug and result.parent_slug in _INDUSTRY_CONTEXT:
        # Get a friendly label from the known parent slug
        _PARENT_LABELS = {
            "fintech": "Fintech",
            "banking": "Banking",
            "healthcare": "Healthcare",
            "saas": "SaaS / Software",
            "ecommerce": "E-commerce",
            "logistics": "Logistics",
            "devtools": "Developer Tools",
        }
        parent_label = _PARENT_LABELS.get(result.parent_slug, result.parent_slug.title())

    return IndustryMatchResponse(
        slug=result.slug,
        parent_slug=result.parent_slug,
        display_name=result.display_name,
        parent_label=parent_label,
        is_known_parent=result.is_known_parent,
        confidence=result.confidence,
        reasoning=result.reasoning,
    )


@router.get("/known")
def list_known_industries(
    current_user=Depends(deps.get_current_active_user),
):
    """Return all known industry slugs. Useful for admin tooling."""
    from app.services.ai.industry_context import _INDUSTRY_CONTEXT
    return {
        "industries": [k for k in _INDUSTRY_CONTEXT if not k.startswith("__")]
    }
```

**Register in `backend/app/api/api.py`:**
```python
from app.api.endpoints import industries
api_router.include_router(industries.router, prefix="/api/v1")
```

---

### Update `PromptContextBuilder` to Use Parent Matching

**File:** `backend/app/services/ai/prompt_context_builder.py`

The existing Step 2 already does a basic parent lookup. Enhance it to also use the `IndustryMatcherService` for unknown slugs:

```python
# ── Step 2 (enhanced): Look up industry context library ──────────────────
if ctx.industry and _INDUSTRY_CONTEXT:
    industry_data = _INDUSTRY_CONTEXT.get(ctx.industry, {})

    if not industry_data:
        # Try known parent slug (e.g. "banking/insurance" → "banking")
        parts = ctx.industry.split("/")
        parent = parts[0]
        industry_data = _INDUSTRY_CONTEXT.get(parent, {})

        if industry_data:
            # Known parent found — enrich with sub-industry display name note
            sub_label = settings.get("industry_display_name", parts[1] if len(parts) > 1 else "")
            if sub_label and industry_data.get("prompt_injection"):
                industry_data = dict(industry_data)  # copy so we don't mutate module-level
                industry_data["prompt_injection"] = (
                    industry_data["prompt_injection"]
                    + f"

SUB-INDUSTRY NOTE: This tenant operates specifically in "
                    f"{sub_label} within the broader {parent.title()} sector."
                )

    # Step 2b: Check generated profiles DB (P5-13 adds this)
    # (placeholder — P5-13 adds the actual DB lookup here)

    ctx.regulatory = industry_data.get("regulatory", [])
    ctx.industry_vocabulary = industry_data.get("vocabulary", {})
    ctx.prompt_injection = industry_data.get("prompt_injection", "")
```

---

### Verification Commands

```bash
# 1. Taxonomy loaded:
python3 -c "
from app.services.industry_matcher import industry_matcher, _taxonomy
print('Taxonomy keys:', list(_taxonomy.keys()))
print('Parent count:', len(_taxonomy.get('parent_keywords', {})))
"
# Expected: Taxonomy keys: ['parent_keywords', 'sub_industry_display_names']

# 2. Match tests:
python3 -c "
from app.services.industry_matcher import industry_matcher
tests = [
    ('Property Insurance', 'banking'),
    ('EdTech learning platform', 'saas'),
    ('Telemedicine startup', 'healthcare'),
    ('Crypto exchange DeFi', 'fintech'),
    ('Restaurant supply chain', 'logistics'),
    ('totally unique niche', None),
]
for query, expected_parent in tests:
    result = industry_matcher.match(query)
    status = 'OK' if result.parent_slug == expected_parent else 'FAIL'
    print(f'{status}: "{query}" -> {result.slug} (parent={result.parent_slug}, conf={result.confidence})')
"

# 3. API endpoint:
curl -X POST http://localhost:8000/api/v1/industries/match \
  -H 'Authorization: Bearer \$TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"query": "Insurance & InsurTech"}' | python3 -m json.tool
# Expected: {"slug": "banking/insurance", "parent_slug": "banking", "is_known_parent": true, ...}
```

---

### Developer Checklist (P5-12)

- [ ] Add `"__taxonomy__"` block to `industry_context.json` (parent_keywords + sub_industry_display_names)
- [ ] Create `backend/app/services/industry_matcher.py` with `IndustryMatcherService` and `industry_matcher` singleton
- [ ] Create `backend/app/api/endpoints/industries.py` with `POST /match` and `GET /known`
- [ ] Register industries router in `backend/app/api/api.py`
- [ ] Update `PromptContextBuilder` Step 2 to add sub-industry note in `prompt_injection`
- [ ] Write unit tests for `IndustryMatcherService.match()` covering: exact known, sub-industry, no match
- [ ] Test `POST /industries/match` returns correct `parent_label` for known parents
- [ ] Verify sub-industry note appears in prompt injection for a tenant with `industry: "banking/insurance"`


---

## P5-13 — Dynamic Industry Profile Generation + DB Cache

**Owner:** Backend Dev 2  
**Estimate:** 2 days  
**Priority:** P1 — Without this, tenants with unknown industries get zero domain context in every Gemini call  
**New migration:** `backend/alembic/versions/s18a1_generated_industry_profiles.py`  
**New files:** `backend/app/models/generated_industry_profile.py`, `backend/app/crud/crud_generated_industry_profile.py`, `backend/app/tasks/industry_tasks.py`  
**Depends on:** P5-12 (matcher knows whether parent exists), P5-02 (industry_context.json structure known)

---

### Why

When a tenant's industry slug has no match in `industry_context.json` (e.g. `"real_estate"`, `"education"`, `"government"`), `PromptContextBuilder` currently returns empty context — every Gemini analysis runs with zero domain knowledge. This task generates a full industry profile via a single Gemini call and caches it in the DB, shared across all tenants with the same industry. The generation cost is paid once; every subsequent tenant with the same industry gets it for free.

---

### DB Migration: `s18a1_generated_industry_profiles`

**New file:** `backend/alembic/versions/s18a1_generated_industry_profiles.py`

```python
"""Add generated_industry_profiles table for dynamic industry context

Revision ID: s18a1
Revises: s15a1
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT

revision = 's18a1'
down_revision = 's15a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'generated_industry_profiles',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        # The slug this profile is for (e.g. "real_estate", "banking/insurance")
        sa.Column('industry_slug', sa.String(100), nullable=False, unique=True),
        # Parent slug if this is a sub-industry (e.g. "banking" for "banking/insurance")
        sa.Column('parent_slug', sa.String(100), nullable=True),
        # Human-readable name (e.g. "Insurance & InsurTech")
        sa.Column('display_name', sa.String(200), nullable=False),
        # Generated content
        sa.Column('regulatory', ARRAY(TEXT), server_default='{}', nullable=False),
        sa.Column('vocabulary', JSONB, server_default='{}', nullable=False),
        sa.Column('prompt_injection', sa.Text, nullable=True),
        # Metadata
        sa.Column('generation_model', sa.String(50), nullable=True),
        sa.Column('generation_prompt_version', sa.Integer, server_default='1', nullable=False),
        sa.Column('is_ai_generated', sa.Boolean, server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean, server_default='false', nullable=False),
        # How many tenants use this profile (for prioritising manual review)
        sa.Column('usage_count', sa.Integer, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gip_slug', 'generated_industry_profiles', ['industry_slug'], unique=True)
    op.create_index('ix_gip_parent', 'generated_industry_profiles', ['parent_slug'])
    op.create_index('ix_gip_usage', 'generated_industry_profiles', ['usage_count'])


def downgrade():
    op.drop_table('generated_industry_profiles')
```

---

### New Model: `backend/app/models/generated_industry_profile.py`

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Text, Boolean, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class GeneratedIndustryProfile(Base):
    __tablename__ = "generated_industry_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry_slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    parent_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    regulatory: Mapped[list] = mapped_column(ARRAY(Text), default=list, nullable=False)
    vocabulary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    prompt_injection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generation_model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    generation_prompt_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                   onupdate=datetime.utcnow)
```

**Register in `backend/app/models/__init__.py`:**
```python
from .generated_industry_profile import GeneratedIndustryProfile  # noqa
```

---

### New CRUD: `backend/app/crud/crud_generated_industry_profile.py`

```python
from sqlalchemy.orm import Session
from app.models.generated_industry_profile import GeneratedIndustryProfile


class CRUDGeneratedIndustryProfile:

    def get_by_slug(self, db: Session, *, slug: str) -> GeneratedIndustryProfile | None:
        return db.query(GeneratedIndustryProfile).filter_by(industry_slug=slug).first()

    def create(self, db: Session, *, slug: str, parent_slug: str | None,
                display_name: str, regulatory: list, vocabulary: dict,
                prompt_injection: str, model: str) -> GeneratedIndustryProfile:
        obj = GeneratedIndustryProfile(
            industry_slug=slug,
            parent_slug=parent_slug,
            display_name=display_name,
            regulatory=regulatory,
            vocabulary=vocabulary,
            prompt_injection=prompt_injection,
            generation_model=model,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def increment_usage(self, db: Session, *, slug: str) -> None:
        db.query(GeneratedIndustryProfile).filter_by(industry_slug=slug).update(
            {"usage_count": GeneratedIndustryProfile.usage_count + 1}
        )
        db.commit()

    def get_all_unverified(self, db: Session, *, min_usage: int = 2) -> list:
        """Return AI-generated profiles with enough usage to warrant manual review."""
        return (
            db.query(GeneratedIndustryProfile)
            .filter_by(is_verified=False, is_ai_generated=True)
            .filter(GeneratedIndustryProfile.usage_count >= min_usage)
            .order_by(GeneratedIndustryProfile.usage_count.desc())
            .all()
        )


crud_generated_industry_profile = CRUDGeneratedIndustryProfile()
```

---

### New Celery Task: `backend/app/tasks/industry_tasks.py`

```python
# backend/app/tasks/industry_tasks.py
"""
generate_industry_profile: On-demand Gemini profile generation for unknown industries.
Triggered when a tenant completes onboarding with a custom/unknown industry slug.
Result is shared across all tenants with the same slug.
"""
import asyncio
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("industry_tasks")

GENERATION_PROMPT_VERSION = 1

PROFILE_GENERATION_PROMPT = """
You are a domain expert. Generate a comprehensive industry knowledge profile for use
in AI-powered document analysis systems.

INDUSTRY: {display_name}
SLUG: {slug}
PARENT INDUSTRY (if applicable): {parent_display}

Generate a JSON response with EXACTLY this structure:
{{
  "regulatory": ["List of 3-6 key regulations, standards, or compliance frameworks"],
  "vocabulary": {{
    "term1": "clear definition relevant to this industry",
    "term2": "clear definition",
    ... (8-12 terms total)
  }},
  "prompt_injection": "A 2-4 sentence paragraph starting with 'REGULATORY CONTEXT:' or 'CONTEXT:' that summarises the most important compliance requirements and technical considerations for this industry. This text will be prepended to AI analysis prompts."
}}

Rules:
- regulatory: real, specific frameworks (e.g. "GDPR", "ISO 27001") not generic statements
- vocabulary: industry-specific jargon a developer must know to understand requirements
- prompt_injection: actionable guidance for document analysis AI, not marketing copy
- Respond ONLY with the JSON object, no explanation, no markdown code fences
"""


@celery_app.task(
    name="generate_industry_profile",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_industry_profile(
    self,
    slug: str,
    display_name: str,
    parent_slug: str | None = None,
):
    """
    Generate and store an industry profile for an unknown industry slug.
    Idempotent: if the slug already exists in the DB, increments usage_count only.
    """
    from app.db.session import SessionLocal
    from app.crud.crud_generated_industry_profile import crud_generated_industry_profile

    db = SessionLocal()
    try:
        # Idempotency check: if profile already exists, just increment usage
        existing = crud_generated_industry_profile.get_by_slug(db, slug=slug)
        if existing:
            crud_generated_industry_profile.increment_usage(db, slug=slug)
            logger.info(f"Profile already exists for '{slug}' — incremented usage")
            return {"status": "already_exists", "slug": slug}

        # Determine parent display name for prompt
        _PARENT_LABELS = {
            "fintech": "Fintech & Financial Technology",
            "banking": "Banking & Financial Services",
            "healthcare": "Healthcare & Life Sciences",
            "saas": "SaaS / Software",
            "ecommerce": "E-commerce & Retail",
            "logistics": "Logistics & Supply Chain",
            "devtools": "Developer Tools & Infrastructure",
        }
        parent_display = _PARENT_LABELS.get(parent_slug or "", "None")

        prompt = PROFILE_GENERATION_PROMPT.format(
            display_name=display_name,
            slug=slug,
            parent_display=parent_display,
        )

        # Call Gemini
        from app.services.ai.gemini import gemini_service
        import json as _json

        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(
                gemini_service.generate_content(prompt)
            )
        finally:
            loop.close()

        raw = (response.text or "").strip()
        # Strip markdown fences if Gemini wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        profile_data = _json.loads(raw)

        # Validate structure
        assert isinstance(profile_data.get("regulatory"), list), "regulatory must be list"
        assert isinstance(profile_data.get("vocabulary"), dict), "vocabulary must be dict"
        assert isinstance(profile_data.get("prompt_injection"), str), "prompt_injection must be str"

        # Store in DB
        profile = crud_generated_industry_profile.create(
            db=db,
            slug=slug,
            parent_slug=parent_slug,
            display_name=display_name,
            regulatory=profile_data["regulatory"],
            vocabulary=profile_data["vocabulary"],
            prompt_injection=profile_data["prompt_injection"],
            model="gemini-1.5-flash",
        )
        crud_generated_industry_profile.increment_usage(db, slug=slug)

        logger.info(
            f"Generated profile for '{slug}': "
            f"{len(profile_data['regulatory'])} regulations, "
            f"{len(profile_data['vocabulary'])} vocab terms"
        )
        return {
            "status": "generated",
            "slug": slug,
            "regulatory_count": len(profile_data["regulatory"]),
            "vocab_count": len(profile_data["vocabulary"]),
        }

    except Exception as exc:
        logger.error(f"Profile generation failed for '{slug}': {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()
```

**Register in `backend/app/worker.py`:**
```python
include=[
    ...
    "app.tasks.industry_tasks",   # ← ADD
]
```

---

### Trigger Generation from Onboarding Completion

**File:** `backend/app/api/endpoints/tenants.py` — in the `PATCH /me/settings` handler

After saving settings, if the industry is unknown (not in `industry_context.json`), dispatch the generation task:

```python
@router.patch("/me/settings")
def update_tenant_settings(settings_update: dict, ...):
    # ... existing merge-update logic ...

    # P5-13: Dispatch profile generation if unknown industry was saved
    new_industry = settings_update.get("industry")
    if new_industry:
        from app.services.ai.industry_context import _INDUSTRY_CONTEXT
        from app.services.industry_matcher import industry_matcher

        is_known = new_industry in _INDUSTRY_CONTEXT
        parent = new_industry.split("/")[0]
        parent_known = parent in _INDUSTRY_CONTEXT

        if not is_known and not parent_known:
            # Completely unknown industry — generate full profile
            display_name = settings_update.get("industry_display_name", new_industry.title())
            parent_slug = settings_update.get("parent_industry")
            try:
                from app.tasks.industry_tasks import generate_industry_profile
                generate_industry_profile.delay(
                    slug=new_industry,
                    display_name=display_name,
                    parent_slug=parent_slug,
                )
                logger.info(f"Dispatched profile generation for unknown industry '{new_industry}'")
            except Exception as e:
                logger.warning(f"Could not dispatch industry profile generation: {e}")

    return {"status": "updated", "settings": current}
```

---

### Update `PromptContextBuilder` — Tier 3 DB Lookup

**File:** `backend/app/services/ai/prompt_context_builder.py`

Complete the Step 2b placeholder from P5-12:

```python
# ── Step 2b: Check generated_industry_profiles DB ────────────────────────
if not industry_data and ctx.industry:
    try:
        from app.crud.crud_generated_industry_profile import crud_generated_industry_profile
        generated = crud_generated_industry_profile.get_by_slug(db, slug=ctx.industry)
        if generated:
            industry_data = {
                "regulatory": generated.regulatory or [],
                "vocabulary": generated.vocabulary or {},
                "prompt_injection": generated.prompt_injection or "",
            }
            logger.debug(
                f"Using AI-generated profile for industry '{ctx.industry}' "
                f"(verified={generated.is_verified})"
            )
    except Exception as db_err:
        logger.warning(f"Could not load generated profile: {db_err}")
```

This gives `PromptContextBuilder` a **4-tier resolution chain:**

```
Tier 1: industry_context.json exact match        → O(1) dict lookup
Tier 2: industry_context.json parent match       → O(1) + sub-industry note
Tier 3: generated_industry_profiles DB lookup    → 1 DB query, <5ms
Tier 4: Empty context (fallback)                  → generic prompt
```

---

### Verification Commands

```bash
# 1. Migration:
alembic upgrade s18a1
psql $DATABASE_URL -c "\d generated_industry_profiles"

# 2. Generate a profile manually:
python3 -c "
from app.tasks.industry_tasks import generate_industry_profile
result = generate_industry_profile('real_estate', 'Real Estate & PropTech', None)
print(result)
"
# Expected: {"status": "generated", "slug": "real_estate", ...}

# 3. Verify stored in DB:
psql $DATABASE_URL -c "SELECT industry_slug, display_name, array_length(regulatory,1) as regs, usage_count FROM generated_industry_profiles;"

# 4. Verify PromptContextBuilder uses generated profile:
python3 -c "
from app.db.session import SessionLocal
from app.services.ai.prompt_context_builder import build_prompt_context
db = SessionLocal()
# Assume tenant_id=1 has industry='real_estate' in settings
ctx = build_prompt_context(db, tenant_id=1)
print('Has prompt_injection:', bool(ctx.prompt_injection))
print('Regulatory count:', len(ctx.regulatory))
db.close()
"
# Expected: Has prompt_injection: True

# 5. Idempotency — run generate twice, check usage_count:
psql $DATABASE_URL -c "SELECT usage_count FROM generated_industry_profiles WHERE industry_slug='real_estate'"
# Expected: 2 (first run creates, second increments)

# 6. Full onboarding flow test:
# Register → set industry to "Government Tech" (unknown) → complete onboarding
# Wait 30s for Celery → check DB:
psql $DATABASE_URL -c "SELECT * FROM generated_industry_profiles WHERE industry_slug LIKE 'government%'"
```

---

### Developer Checklist (P5-13)

- [ ] Write `s18a1_generated_industry_profiles.py` migration (`down_revision = 's15a1'`)
- [ ] Run migration locally: `alembic upgrade s18a1`
- [ ] Create `backend/app/models/generated_industry_profile.py`
- [ ] Register model in `backend/app/models/__init__.py` and `backend/app/db/base.py`
- [ ] Create `backend/app/crud/crud_generated_industry_profile.py` (4 methods)
- [ ] Register CRUD in `backend/app/crud/__init__.py`
- [ ] Create `backend/app/tasks/industry_tasks.py` with `generate_industry_profile` Celery task
- [ ] Register `app.tasks.industry_tasks` in `backend/app/worker.py`
- [ ] Update `PATCH /me/settings` to dispatch generation task for unknown industries
- [ ] Update `PromptContextBuilder` Step 2b — add Tier 3 DB lookup
- [ ] Test: Complete onboarding with "Government Tech" → task dispatched → profile in DB after 30s
- [ ] Test: Second tenant with same slug → `usage_count` incremented, no duplicate generation
- [ ] Test: `PromptContextBuilder` returns non-empty context for tenant with `real_estate` industry


---

## P5-14 — Enhanced Auto-Detection Supporting Unknown Industries

**Owner:** Backend Dev 1  
**Estimate:** 1 day  
**Priority:** P1 — The current detection task rejects any industry outside the 8 known slugs  
**Modifies:** `backend/app/tasks/tenant_tasks.py` (the `detect_tenant_industry` task from P5-04)  
**Depends on:** P5-12 (taxonomy), P5-13 (generation task exists)

---

### Root Cause

The current `detect_tenant_industry` task (P5-04) hardcodes this validation:
```python
if detected_slug not in VALID_INDUSTRY_SLUGS:
    logger.warning(f"DETECT_INDUSTRY: invalid slug returned '{detected_slug}'")
    return   # ← SILENTLY DROPS the result
```

The Gemini prompt also constrains to `VALID_INDUSTRY_SLUGS`, so even if a company is clearly in insurance or real estate, Gemini is instructed to pick the "closest" of 8 known values — degrading accuracy. This task upgrades both the prompt and the handling logic.

---

### New Gemini Classification Prompt

**File:** `backend/app/tasks/tenant_tasks.py`

Replace the existing `classification_prompt` string with:

```python
KNOWN_SLUGS_STR = "\n".join(f"  - {s}" for s in sorted(VALID_INDUSTRY_SLUGS))

classification_prompt = f"""
Analyze the following website text and classify the company's industry.

KNOWN INDUSTRY SLUGS (use these if they match well):
{KNOWN_SLUGS_STR}

INSTRUCTIONS:
1. If the company fits a KNOWN SLUG well (confidence >= 0.7), return that slug.
2. If the company fits a SUB-DOMAIN of a known industry (e.g. insurance under banking),
   return "parent/sub" format: e.g. "banking/insurance", "healthcare/telemedicine",
   "saas/edtech", "fintech/crypto".
   The parent MUST be one of the known slugs above.
3. If the company is in a completely different industry not related to any known slug,
   return a new snake_case slug: e.g. "real_estate", "government", "education",
   "media", "telecom", "travel", "energy", "agriculture".

Return ONLY a valid JSON object, no explanation:
{{
  "industry_slug": "the best slug",
  "parent_slug": "parent if sub-industry, else null",
  "is_known": true or false,
  "display_name": "Human readable name e.g. Insurance & InsurTech",
  "confidence": 0.85,
  "reasoning": "one sentence explanation"
}}

WEBSITE TEXT:
{website_text}
"""
```

---

### Updated Step 4 — Handle Unknown Slugs

**File:** `backend/app/tasks/tenant_tasks.py`

Replace the existing Step 4 (slug validation) and Step 5 (settings update) with this enhanced version:

```python
        # ── Step 4: Parse Gemini JSON response ───────────────────────────────
        import json as _json
        raw = (response.text or "").strip()
        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            classification = _json.loads(raw)
        except _json.JSONDecodeError:
            # Fallback: old-style single slug response (backward compat)
            detected_slug = raw.lower().strip('"').strip("'")
            classification = {
                "industry_slug": detected_slug,
                "parent_slug": None,
                "is_known": detected_slug in VALID_INDUSTRY_SLUGS,
                "display_name": detected_slug.replace("_", " ").title(),
                "confidence": 0.5,
                "reasoning": "Legacy plain-text response",
            }

        detected_slug = classification.get("industry_slug", "").lower().strip()
        parent_slug = classification.get("parent_slug")
        is_known = classification.get("is_known", detected_slug in VALID_INDUSTRY_SLUGS)
        display_name = classification.get("display_name", detected_slug.replace("_", " ").title())
        confidence = float(classification.get("confidence", 0.5))

        # Validate slug format (snake_case or parent/sub)
        import re as _re
        if not _re.match(r"^[a-z][a-z0-9_/]{1,60}$", detected_slug):
            logger.warning(
                f"DETECT_INDUSTRY: malformed slug '{detected_slug}' for tenant {tenant_id}"
            )
            return

        # Low confidence: don't auto-set, let user choose in onboarding
        if confidence < 0.4:
            logger.info(
                f"DETECT_INDUSTRY: confidence {confidence} too low for tenant {tenant_id} "
                f"— leaving industry unset so user selects manually"
            )
            return

        # ── Step 5: Update tenant.settings ───────────────────────────────────
        tenant = crud.tenant.get(db, id=tenant_id)
        if not tenant:
            logger.error(f"DETECT_INDUSTRY: tenant {tenant_id} not found")
            return

        current_settings = dict(tenant.settings or {})

        # Only set if not already set by the user
        if not current_settings.get("industry"):
            current_settings["industry"] = detected_slug
            current_settings["industry_display_name"] = display_name
            current_settings["industry_is_known"] = is_known
            if parent_slug:
                current_settings["parent_industry"] = parent_slug

            crud.tenant.update(
                db, db_obj=tenant, obj_in={"settings": current_settings}
            )
            db.commit()
            logger.info(
                f"DETECT_INDUSTRY: set industry='{detected_slug}' "
                f"(known={is_known}, confidence={confidence}) for tenant {tenant_id}"
            )

            # ── Step 6: Trigger profile generation for unknown industry ───────
            if not is_known:
                # Check if parent is known (sub-industry case)
                parent_known = (parent_slug in VALID_INDUSTRY_SLUGS) if parent_slug else False
                if not parent_known:
                    # Completely unknown — generate full AI profile
                    try:
                        from app.tasks.industry_tasks import generate_industry_profile
                        generate_industry_profile.delay(
                            slug=detected_slug,
                            display_name=display_name,
                            parent_slug=parent_slug,
                        )
                        logger.info(
                            f"DETECT_INDUSTRY: dispatched profile generation "
                            f"for unknown industry '{detected_slug}'"
                        )
                    except Exception as task_err:
                        logger.warning(
                            f"DETECT_INDUSTRY: could not dispatch generation: {task_err}"
                        )
        else:
            logger.info(
                f"DETECT_INDUSTRY: tenant {tenant_id} already has industry set — skipping"
            )
```

---

### Updated `VALID_INDUSTRY_SLUGS` Constant

**File:** `backend/app/tasks/tenant_tasks.py`

The set is now used as a "known list" reference, not a whitelist that rejects unknowns:

```python
# Rename from VALID_INDUSTRY_SLUGS to KNOWN_INDUSTRY_SLUGS to signal intent change
KNOWN_INDUSTRY_SLUGS = {
    "fintech/payments",
    "fintech/lending",
    "banking",
    "healthcare",
    "saas",
    "ecommerce",
    "logistics",
    "devtools",
}
```

---

### What Changes in the Full Detection Flow

**Before (P5-04):**
```
website → Gemini → must be one of 8 slugs → if unknown: DROP and return
```

**After (P5-14):**
```
website → Gemini → JSON response with slug + confidence
    │
    ├── confidence < 0.4 → skip (let user choose manually)
    ├── is_known = true → save slug → done
    ├── is_known = false + parent_slug in known → save "banking/insurance" → done
    └── is_known = false + no known parent → save slug → dispatch generate_industry_profile task
                                                              ↓ (30s async)
                                                        GeneratedIndustryProfile in DB
                                                              ↓ (next analysis)
                                                        PromptContextBuilder uses generated profile
```

---

### Backward Compatibility

The detection task still handles the old plain-text response format via the `json.JSONDecodeError` fallback path. If for any reason Gemini returns a plain slug string instead of JSON, the existing behavior is preserved.

---

### Verification Commands

```bash
# 1. Test with an insurance company website:
python3 -c "
from app.tasks.tenant_tasks import detect_tenant_industry
# Call directly (not via .delay) for testing
detect_tenant_industry(
    tenant_id=999,
    website_url='https://lemonade.com'
)
"
psql \$DATABASE_URL -c "SELECT settings FROM tenants WHERE id=999;"
# Expected: settings contains industry='banking/insurance' or 'fintech/insurtech'

# 2. Test with an education company:
# Expected: industry='education' (unknown), generate_industry_profile task dispatched

# 3. Test low-confidence handling:
# A generic consulting firm website should NOT set industry (confidence < 0.4)
# Expected: settings.industry remains unset

# 4. Test JSON parse fallback:
# Simulate old plain-text Gemini response → should still work

# 5. After generate_industry_profile completes:
psql \$DATABASE_URL -c "
SELECT industry_slug, display_name, array_length(regulatory,1)
FROM generated_industry_profiles WHERE industry_slug='education';
"
```

---

### Developer Checklist (P5-14)

- [ ] Replace `classification_prompt` string in `detect_tenant_industry` with new JSON-response prompt
- [ ] Add `KNOWN_INDUSTRY_SLUGS` constant (rename from `VALID_INDUSTRY_SLUGS`)
- [ ] Replace Step 4 validation with JSON parse + structured handling
- [ ] Add confidence threshold check (skip if < 0.4)
- [ ] Save `industry_display_name`, `parent_industry`, `industry_is_known` to settings
- [ ] Add Step 6: dispatch `generate_industry_profile.delay()` for unknown industries without known parent
- [ ] Add `json.JSONDecodeError` fallback for backward compatibility with plain-text response
- [ ] Test: Lemonade / insurance company → slug contains "insurance" sub-industry
- [ ] Test: Education company → unknown industry → profile generation dispatched
- [ ] Test: Generic consulting website → low confidence → industry NOT set
- [ ] Test: Plain-text Gemini response → fallback path works → no crash

---

## P5-11 to P5-14 — Combined Gap Analysis Summary

### Three-Tier Industry Resolution (after all 4 tasks)

```
User registers with company_website = "lemonade.com"
        │
        ▼
detect_tenant_industry task (P5-14 enhanced)
        │
        ├── Gemini returns: { industry_slug: "banking/insurance", is_known: false,
        │                     parent_slug: "banking", confidence: 0.85 }
        │
        ├── parent "banking" IS known → save slug + dispatch generate delta profile
        │
        ▼
User reaches onboarding Step 2 (P5-11)
        │
        ├── Poll detects industry="banking/insurance" after 8s
        ├── Green banner: "Auto-detected from your website"
        ├── "Banking" card NOT selected (it's a sub-industry)
        ├── "Other" card IS selected with "Insurance & InsurTech" pre-filled
        └── "Looks like sub-industry of Banking" match result shown ✓
        │
        ▼
User completes onboarding
        │
        ▼
Next document analysis
        │
        ├── PromptContextBuilder Tier 1: "banking/insurance" not in JSON
        ├── PromptContextBuilder Tier 2: parent "banking" IS in JSON
        │   → inherits banking regulations + adds "Sub-industry: Insurance" note
        └── Full domain context injected ✓


User registers with company_website = "opendoor.com" (real estate)
        │
        ▼
detect_tenant_industry (P5-14)
        │
        ├── Gemini returns: { industry_slug: "real_estate", is_known: false,
        │                     parent_slug: null, confidence: 0.92 }
        │
        ├── No known parent → dispatch generate_industry_profile("real_estate", "Real Estate")
        │
        ▼
30s later: GeneratedIndustryProfile stored in DB
        │
        ▼
Next document analysis
        │
        └── PromptContextBuilder Tier 3: DB lookup → returns generated profile ✓
```

### New Files Introduced (P5-11 to P5-14)

| File | Task | Type |
|------|------|------|
| `frontend/lib/constants/industry-options.ts` | P5-11 | MODIFIED (extends P5-10) |
| `backend/app/services/industry_matcher.py` | P5-12 | NEW |
| `backend/app/api/endpoints/industries.py` | P5-12 | NEW |
| `backend/app/services/ai/industry_context.json` | P5-12 | MODIFIED (adds `__taxonomy__`) |
| `backend/alembic/versions/s18a1_generated_industry_profiles.py` | P5-13 | NEW |
| `backend/app/models/generated_industry_profile.py` | P5-13 | NEW |
| `backend/app/crud/crud_generated_industry_profile.py` | P5-13 | NEW |
| `backend/app/tasks/industry_tasks.py` | P5-13 | NEW |
| `backend/app/services/ai/prompt_context_builder.py` | P5-12 + P5-13 | MODIFIED |
| `backend/app/tasks/tenant_tasks.py` | P5-14 | MODIFIED |
| `backend/app/api/endpoints/tenants.py` | P5-13 | MODIFIED |
| `frontend/app/dashboard/onboarding/page.tsx` | P5-11 | MODIFIED |
| `frontend/app/dashboard/admin/page.tsx` | P5-11 | MODIFIED |


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


---

# PHASE 5B — Validation Accuracy, Transparency & Enterprise Workflow
**Priority: HIGH — directly determines product value proposition**
**Branch: claude/autodocs-multiple-sources-MbvDe**
**Depends on: Phase 4 (BOE-Aware Validation), Phase 5 (Dynamic Prompting)**
**Migration chain: s12a1 → s16a1 → s16b1 → s16c1 → s16d1 → s16e1**

## Strategic Context

Phase 4 makes validation faster. Phase 5 makes prompts smarter. Phase 5B makes the **output trustworthy**:

A CTO evaluating DokyDoc will ask:
1. "Can I trust these mismatch results?" → P5B-04 (False Positive Workflow) + P5B-05 (Evidence Transparency)
2. "What happens when we re-upload a changed BRD?" → P5B-01 (BRD Delta Diffing)
3. "Can I get a single compliance score?" → P5B-02 (Compliance Score)
4. "Does this push to Jira?" → P5B-03 (1-Click Jira)
5. "What happens when developers push new code?" → P5B-06 (Auto Re-validation)
6. "Which files cover which requirements?" → P5B-07 (Coverage Matrix)
7. "Are our regulatory requirements flagged separately?" → P5B-08 (Regulatory Tagging)
8. "How accurate is the AI per requirement type?" → P5B-09 (Prompt Strengthening)
9. "What states can a mismatch be in?" → P5B-10 (Status Lifecycle)
10. "Which BRD version caused this mismatch?" → P5B-11 (Version-Linked Mismatches)
11. "Can my BA sign off before we ship?" → P5B-12 (BA Sign-Off + Certificate)

Each task below is independently deployable and non-breaking. All changes are wrapped in try/except or additive-only.


---

## P5B-01 — BRD Delta Diffing (Atom-Level Version Comparison)

**Ticket ID:** P5B-01
**Priority:** P0 — Critical. Without this, re-uploading a BRD nukes all mismatches and starts from scratch. Teams lose their triage history.
**Complexity:** Medium
**Risk:** MEDIUM — touches atomization + mismatch CRUD + document pipeline

### Why This Exists

Current behavior when a user re-uploads a BRD (v2 after v1):
```
1. New DocumentVersion created (content_hash changes)
2. atomize_document() called — ALL atoms replaced (delete_by_document then bulk insert)
3. validate_single_link() called — crud.mismatch.remove_by_link() deletes ALL mismatches
4. Fresh validation runs on all atoms
5. Result: ALL triage history gone. Mismatches marked "won't fix" are resurrected.
```

What should happen:
```
1. New DocumentVersion created
2. Atom-level diff computed: ADDED / MODIFIED / UNCHANGED / DELETED
3. UNCHANGED atoms → skip re-validation (no Gemini cost)
4. DELETED atoms → auto-close their mismatches (requirement was removed from BRD)
5. ADDED atoms → run fresh validation (new requirement)
6. MODIFIED atoms → re-run validation only for those atoms (requirement changed)
7. Result: triage history preserved, cost reduced ~40-60%
```

### Current State

**File: `backend/app/models/requirement_atom.py` (line 34-55)**
`document_version` field stores the version string but there is NO field to link atoms from different versions of the same logical requirement. When v2 is uploaded, all v1 atoms are overwritten — there is no `previous_atom_id` or `content_hash` to detect "same requirement, minor wording change" vs "completely new requirement."

**File: `backend/app/crud/crud_requirement_atom.py` (line 51-57)**
`delete_by_document` deletes ALL atoms indiscriminately on re-atomization:
```python
# CURRENT — no diff awareness
def delete_by_document(self, db: Session, *, document_id: int) -> int:
    n = db.query(self.model).filter(
        self.model.document_id == document_id
    ).delete()
    db.commit()
    return n
```

**File: `backend/app/crud/crud_mismatch.py` (line 63-80)**
`remove_by_link` deletes ALL mismatches for a document-component pair:
```python
# CURRENT — no selective closure
def remove_by_link(self, db, *, document_id, code_component_id, tenant_id) -> int:
    num_deleted = db.query(self.model).filter(
        self.model.document_id == document_id,
        self.model.code_component_id == code_component_id,
        self.model.tenant_id == tenant_id
    ).delete()
    db.commit()
    return num_deleted
```

**File: `backend/app/services/validation_service.py` (line 252-260 approx)**
`run_validation` calls `remove_by_link` BEFORE `validate_single_link` — no way to recover history.

### What to Change

#### Step 1: Add `content_hash` + `previous_atom_id` to RequirementAtom model

**File: `backend/app/models/requirement_atom.py`**

```python
# BEFORE (line 54-55):
    document_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    document: Mapped["Document"] = relationship("Document")

# AFTER:
    document_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # P5B-01: content_hash enables change detection between versions
    # SHA-256 of normalized content (stripped whitespace, lowercase)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # P5B-01: links this atom to the equivalent atom in the previous version
    # NULL = new atom (no prior version), set = UNCHANGED or MODIFIED
    previous_atom_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("requirement_atoms.id", ondelete="SET NULL"), nullable=True
    )

    # P5B-01: change classification vs previous version
    # "new" = ADDED, "modified" = MODIFIED, "unchanged" = UNCHANGED
    # NULL = first version (no diff computed)
    delta_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    document: Mapped["Document"] = relationship("Document")
```

#### Step 2: New Alembic migration

**New file: `backend/alembic/versions/s16a1_atom_delta_fields.py`**

```python
"""
P5B-01: Add content_hash, previous_atom_id, delta_status to requirement_atoms.

Revision ID: s16a1
Revises: s12a1
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = 's16a1'
down_revision = 's12a1'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('requirement_atoms',
        sa.Column('content_hash', sa.String(64), nullable=True))
    op.add_column('requirement_atoms',
        sa.Column('previous_atom_id', sa.Integer,
                  sa.ForeignKey('requirement_atoms.id', ondelete='SET NULL'), nullable=True))
    op.add_column('requirement_atoms',
        sa.Column('delta_status', sa.String(20), nullable=True))

    # Index for fast lookup by hash (used in diff computation)
    op.create_index(
        'ix_requirement_atoms_content_hash',
        'requirement_atoms', ['content_hash'],
        postgresql_concurrently=True
    )
    # Index for delta queries (find all ADDED atoms for a re-run)
    op.create_index(
        'ix_requirement_atoms_delta_status',
        'requirement_atoms', ['document_id', 'delta_status'],
        postgresql_concurrently=True
    )

def downgrade():
    op.drop_index('ix_requirement_atoms_delta_status')
    op.drop_index('ix_requirement_atoms_content_hash')
    op.drop_column('requirement_atoms', 'delta_status')
    op.drop_column('requirement_atoms', 'previous_atom_id')
    op.drop_column('requirement_atoms', 'content_hash')
```

#### Step 3: New service — `AtomDiffService`

**New file: `backend/app/services/atom_diff_service.py`**

```python
"""
P5B-01: BRD Delta Diffing — atom-level comparison between document versions.

Computes ADDED / MODIFIED / UNCHANGED / DELETED for requirement atoms
when a document is re-uploaded. Enables:
  - Skipping re-validation for UNCHANGED atoms (cost savings)
  - Auto-closing mismatches for DELETED atoms (history preservation)
  - Targeted re-validation for ADDED + MODIFIED atoms only
"""
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session

from app.models.requirement_atom import RequirementAtom


def _normalize_content(text: str) -> str:
    """Normalize atom content for stable hashing. Strip whitespace, lowercase."""
    return " ".join(text.lower().strip().split())


def _hash_content(text: str) -> str:
    """SHA-256 of normalized content."""
    return hashlib.sha256(_normalize_content(text).encode()).hexdigest()


@dataclass
class AtomDelta:
    """Result of comparing one new atom against prior version atoms."""
    new_atom_content: str
    new_atom_type: str
    status: str  # "added" | "modified" | "unchanged"
    previous_atom_id: Optional[int] = None
    previous_content: Optional[str] = None
    content_hash: str = ""

    def __post_init__(self):
        self.content_hash = _hash_content(self.new_atom_content)


@dataclass
class DocumentAtomDiff:
    """Full diff result for a document re-atomization."""
    document_id: int
    previous_version: Optional[str]
    new_version: str
    added: list = field(default_factory=list)       # new atoms with no prior match
    modified: list = field(default_factory=list)     # atoms that changed content
    unchanged: list = field(default_factory=list)    # atoms with identical content hash
    deleted_atom_ids: list = field(default_factory=list)  # prior atom IDs not present in new version

    @property
    def needs_validation(self) -> list:
        """Atoms that require a Gemini validation pass."""
        return self.added + self.modified

    @property
    def total_prior_atoms(self) -> int:
        return len(self.modified) + len(self.unchanged) + len(self.deleted_atom_ids)


class AtomDiffService:
    """
    Computes atom-level diffs between document versions.
    Called by validation_service.py INSTEAD of delete_by_document when re-atomizing.
    """

    def compute_diff(
        self,
        db: Session,
        document_id: int,
        new_atoms_data: list[dict],
        new_version: str,
        tenant_id: int,
    ) -> DocumentAtomDiff:
        """
        Compare new atoms (from fresh Gemini atomization) against prior atoms in DB.

        Algorithm:
        1. Load all prior atoms for this document from DB
        2. Build hash → atom_id lookup for prior atoms
        3. For each new atom:
           a. Compute content hash
           b. If hash matches prior → UNCHANGED (carry forward previous_atom_id)
           c. If atom_type matches prior but content differs → MODIFIED
           d. If no match → ADDED
        4. Prior atoms not matched by any new atom → DELETED

        Matching strategy:
        - Primary: exact content hash match (hash equality)
        - Secondary: same atom_type + Levenshtein similarity > 0.75 (handles minor wording edits)
        """
        from app.crud.crud_requirement_atom import requirement_atom as crud_atom

        prior_atoms = crud_atom.get_by_document(db, document_id=document_id)
        prior_version = prior_atoms[0].document_version if prior_atoms else None

        diff = DocumentAtomDiff(
            document_id=document_id,
            previous_version=prior_version,
            new_version=new_version,
        )

        if not prior_atoms:
            # First upload — everything is ADDED
            for atom_data in new_atoms_data:
                diff.added.append(AtomDelta(
                    new_atom_content=atom_data["content"],
                    new_atom_type=atom_data.get("atom_type", "FUNCTIONAL_REQUIREMENT"),
                    status="added",
                ))
            return diff

        # Build lookup: hash → prior RequirementAtom
        prior_by_hash: dict[str, RequirementAtom] = {}
        prior_by_type: dict[str, list[RequirementAtom]] = {}
        for atom in prior_atoms:
            h = _hash_content(atom.content)
            prior_by_hash[h] = atom
            prior_by_type.setdefault(atom.atom_type, []).append(atom)

        matched_prior_ids: set[int] = set()

        for atom_data in new_atoms_data:
            content = atom_data["content"]
            atom_type = atom_data.get("atom_type", "FUNCTIONAL_REQUIREMENT")
            new_hash = _hash_content(content)

            # Try exact hash match first
            if new_hash in prior_by_hash:
                prior = prior_by_hash[new_hash]
                matched_prior_ids.add(prior.id)
                diff.unchanged.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="unchanged",
                    previous_atom_id=prior.id,
                    previous_content=prior.content,
                    content_hash=new_hash,
                ))
                continue

            # Try fuzzy match: same type, high similarity
            best_match = None
            best_score = 0.0
            for candidate in prior_by_type.get(atom_type, []):
                if candidate.id in matched_prior_ids:
                    continue
                score = _levenshtein_similarity(
                    _normalize_content(content),
                    _normalize_content(candidate.content)
                )
                if score > best_score:
                    best_score = score
                    best_match = candidate

            if best_match and best_score >= 0.75:
                matched_prior_ids.add(best_match.id)
                diff.modified.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="modified",
                    previous_atom_id=best_match.id,
                    previous_content=best_match.content,
                    content_hash=new_hash,
                ))
            else:
                diff.added.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="added",
                    content_hash=new_hash,
                ))

        # Prior atoms not matched → DELETED
        for atom in prior_atoms:
            if atom.id not in matched_prior_ids:
                diff.deleted_atom_ids.append(atom.id)

        return diff


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0-1.0). Uses SequenceMatcher for speed."""
    import difflib
    return difflib.SequenceMatcher(None, s1, s2).ratio()


# Singleton
atom_diff_service = AtomDiffService()
```

#### Step 4: Update `CRUDMismatch` — add `close_for_deleted_atoms`

**File: `backend/app/crud/crud_mismatch.py`**

Add this new method AFTER `remove_by_link` (after line 80):

```python
# AFTER — add after remove_by_link:
def close_for_deleted_atoms(
    self,
    db: Session,
    *,
    deleted_atom_ids: list[int],
    tenant_id: int,
    auto_close_reason: str = "requirement_deleted_from_brd"
) -> int:
    """
    P5B-01: Auto-close mismatches whose requirement atom was deleted from the BRD.
    Sets status to 'auto_closed' instead of deleting — preserves audit history.
    Returns count of mismatches closed.
    """
    if not deleted_atom_ids:
        return 0

    from datetime import datetime
    num_closed = db.query(self.model).filter(
        self.model.requirement_atom_id.in_(deleted_atom_ids),
        self.model.tenant_id == tenant_id,
        self.model.status.in_(["open", "in_progress"])  # P5B-10 statuses
    ).update(
        {
            "status": "auto_closed",
            "resolution_note": auto_close_reason,
            "updated_at": datetime.now(),
        },
        synchronize_session="fetch"
    )
    db.commit()
    return num_closed
```

#### Step 5: Update `ValidationService.atomize_document` to use diff

**File: `backend/app/services/validation_service.py`**

Find `atomize_document` method (line ~122) and update the atom storage section:

```python
# BEFORE (around line 185-210):
        # Wipe old atoms and replace with new ones
        crud.requirement_atom.delete_by_document(db, document_id=document.id)
        created_atoms = crud.requirement_atom.create_atoms_bulk(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            document_version=doc_version,
            atoms_data=raw_atoms,
        )
        logger.info(f"Stored {len(created_atoms)} RequirementAtoms for doc {document.id}")
        return created_atoms

# AFTER — diff-aware storage:
        # P5B-01: Compute atom-level diff instead of delete-all
        try:
            from app.services.atom_diff_service import atom_diff_service
            diff = atom_diff_service.compute_diff(
                db=db,
                document_id=document.id,
                new_atoms_data=raw_atoms,
                new_version=doc_version,
                tenant_id=tenant_id,
            )

            # Auto-close mismatches for deleted atoms (preserves history)
            if diff.deleted_atom_ids:
                n_closed = crud.mismatch.close_for_deleted_atoms(
                    db=db,
                    deleted_atom_ids=diff.deleted_atom_ids,
                    tenant_id=tenant_id,
                )
                logger.info(
                    f"Auto-closed {n_closed} mismatches for {len(diff.deleted_atom_ids)} "
                    f"deleted atoms in doc {document.id}"
                )

            # Delete old atoms (they will be replaced with diff-annotated versions)
            crud.requirement_atom.delete_by_document(db, document_id=document.id)

            # Rebuild atoms_data with delta annotations
            annotated_atoms = []
            for delta in diff.added + diff.modified + diff.unchanged:
                atom_data = next(
                    (a for a in raw_atoms if _normalize_content(a["content"]) ==
                     _normalize_content(delta.new_atom_content)),
                    None
                )
                if atom_data:
                    atom_data["_content_hash"] = delta.content_hash
                    atom_data["_previous_atom_id"] = delta.previous_atom_id
                    atom_data["_delta_status"] = delta.status
                    annotated_atoms.append(atom_data)

            created_atoms = crud.requirement_atom.create_atoms_bulk(
                db,
                tenant_id=tenant_id,
                document_id=document.id,
                document_version=doc_version,
                atoms_data=annotated_atoms,
            )

            logger.info(
                f"Doc {document.id} atom diff: {len(diff.added)} added, "
                f"{len(diff.modified)} modified, {len(diff.unchanged)} unchanged, "
                f"{len(diff.deleted_atom_ids)} deleted"
            )

            # Store diff summary on document for frontend display
            document.last_atom_diff = {
                "added": len(diff.added),
                "modified": len(diff.modified),
                "unchanged": len(diff.unchanged),
                "deleted": len(diff.deleted_atom_ids),
                "previous_version": diff.previous_version,
                "new_version": diff.new_version,
            }
            db.commit()

            return created_atoms

        except Exception as e:
            logger.warning(f"Atom diff failed (non-fatal), falling back to full re-atomize: {e}")
            # Fallback: original behavior
            crud.requirement_atom.delete_by_document(db, document_id=document.id)
            created_atoms = crud.requirement_atom.create_atoms_bulk(
                db, tenant_id=tenant_id, document_id=document.id,
                document_version=doc_version, atoms_data=raw_atoms,
            )
            return created_atoms
```

Also update `create_atoms_bulk` in `crud_requirement_atom.py` to accept and store the new fields:

**File: `backend/app/crud/crud_requirement_atom.py` (line 78-88)**

```python
# BEFORE:
            db_obj = RequirementAtom(
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=document_version,
                atom_id=atom.get("atom_id") or f"REQ-{i+1:03d}",
                atom_type=atom.get("atom_type", "FUNCTIONAL_REQUIREMENT"),
                content=atom.get("content", ""),
                criticality=atom.get("criticality", "standard"),
                created_at=now,
                updated_at=now,
            )

# AFTER (accepts P5B-01 delta fields via underscore-prefixed keys):
            db_obj = RequirementAtom(
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=document_version,
                atom_id=atom.get("atom_id") or f"REQ-{i+1:03d}",
                atom_type=atom.get("atom_type", "FUNCTIONAL_REQUIREMENT"),
                content=atom.get("content", ""),
                criticality=atom.get("criticality", "standard"),
                # P5B-01: delta annotation fields (present only after diff computation)
                content_hash=atom.get("_content_hash"),
                previous_atom_id=atom.get("_previous_atom_id"),
                delta_status=atom.get("_delta_status"),
                created_at=now,
                updated_at=now,
            )
```

#### Step 6: Update `validate_single_link` to skip UNCHANGED atoms

**File: `backend/app/services/validation_service.py`**

In `validate_single_link`, when loading atoms for validation, filter to only non-UNCHANGED atoms for re-runs:

```python
# In validate_single_link, after atoms = await self.atomize_document(...)
# Add this filter for re-validation runs (not first-time):

is_revalidation = (
    crud.mismatch.count_by_document_component(db, document_id, component_id, tenant_id) > 0
    or diff is not None
)

if is_revalidation:
    # Skip UNCHANGED atoms — their mismatches are still valid
    atoms_to_validate = [
        a for a in atoms
        if a.delta_status in (None, "added", "modified")
    ]
    logger.info(
        f"Re-validation: skipping {len(atoms) - len(atoms_to_validate)} unchanged atoms"
    )
else:
    atoms_to_validate = atoms
```

#### Step 7: Add `last_atom_diff` JSON column to documents

**File: `backend/app/models/document.py`**

Add after the existing `settings` or `status` field:
```python
# P5B-01: stores result of last atom diff computation for frontend display
from sqlalchemy.dialects.postgresql import JSONB
last_atom_diff: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
```

**New migration addition** — add to `s16a1` upgrade():
```python
op.add_column('documents',
    sa.Column('last_atom_diff', sa.dialects.postgresql.JSONB(), nullable=True))
```

#### Step 8: New API endpoint — `GET /documents/{id}/atom-diff`

**File: `backend/app/api/endpoints/documents.py`**

```python
@router.get("/{document_id}/atom-diff")
def get_atom_diff(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-01: Returns the last atom-level diff result for a document.
    Used by frontend to show "BRD Changed: 3 new requirements, 2 deleted" banner.
    """
    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": document_id,
        "last_atom_diff": document.last_atom_diff or {
            "message": "No diff available — document uploaded before P5B-01"
        }
    }
```

#### Frontend: Show diff banner on validation panel

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add after the document title header:
```tsx
{atomDiff && (atomDiff.added > 0 || atomDiff.modified > 0 || atomDiff.deleted > 0) && (
  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-center gap-3">
    <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
    <div className="text-sm text-amber-800">
      <span className="font-medium">BRD updated:</span>{' '}
      {atomDiff.added > 0 && <span className="text-green-700">{atomDiff.added} new requirements</span>}
      {atomDiff.added > 0 && atomDiff.modified > 0 && ', '}
      {atomDiff.modified > 0 && <span className="text-yellow-700">{atomDiff.modified} changed</span>}
      {(atomDiff.added > 0 || atomDiff.modified > 0) && atomDiff.deleted > 0 && ', '}
      {atomDiff.deleted > 0 && <span className="text-red-700">{atomDiff.deleted} removed</span>}
      {atomDiff.deleted > 0 && (
        <span className="text-gray-500 ml-1">
          (mismatches for removed requirements auto-closed)
        </span>
      )}
    </div>
  </div>
)}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16a1

# 2. Verify columns exist
psql -c "\d requirement_atoms" | grep "content_hash\|previous_atom_id\|delta_status"

# 3. Upload a BRD, note atom count
curl -X POST /api/v1/documents/ -F "file=@brd_v1.pdf"
# Note: document_id = X

# 4. Re-upload modified BRD
curl -X POST /api/v1/documents/{X}/re-upload -F "file=@brd_v2.pdf"

# 5. Check atom diff
curl /api/v1/documents/{X}/atom-diff
# Expect: { added: N, modified: M, unchanged: K, deleted: D }

# 6. Verify auto-closed mismatches
psql -c "SELECT status, resolution_note FROM mismatches WHERE status = 'auto_closed'"
# Expect: rows with resolution_note = 'requirement_deleted_from_brd'

# 7. Verify UNCHANGED atoms skipped in re-validation (check logs)
# Expect: "Re-validation: skipping N unchanged atoms"
```

### Risk Assessment
- **Fallback on error:** try/except wraps the entire diff computation — falls back to original behavior on any exception
- **Non-breaking for existing data:** `content_hash`, `previous_atom_id`, `delta_status` are all nullable — existing atoms unaffected
- **`auto_closed` status:** added to P5B-10 lifecycle; the `close_for_deleted_atoms` method only closes "open" or "in_progress" statuses — won't touch already-resolved or verified mismatches


---

## P5B-02 — Compliance Score (Single Weighted Percentage Per Project)

**Ticket ID:** P5B-02
**Priority:** P0 — The #1 metric a manager asks for. Without a single score, they can't track progress.
**Complexity:** Low-Medium
**Risk:** LOW — read-only computation, no side effects

### Why This Exists

A BA or CTO opening DokyDoc today sees a list of mismatches. There is no single answer to "how compliant are we?" — they have to count mismatches mentally. The product needs one headline number per document-repository combination:

```
Payment Service BRD vs payment_service repo
Documentation Compliance: 84%
  API Contracts:        91%  (10/11 covered)
  Business Rules:       78%  (7/9 covered)
  Data Constraints:     100% (5/5 covered)
  Security Reqs:        60%  (3/5 covered)  ← attention needed
  NFRs:                 80%  (4/5 covered)
```

The formula: `score = (atoms_without_critical_mismatch / total_atoms) × 100`
With weightings: SECURITY_REQUIREMENT atoms count 3×, BUSINESS_RULE 2×, others 1×.

### Current State

No compliance score endpoint exists. The validation panel shows raw mismatch lists.
`GET /api/v1/validation/{document_id}/summary` does not exist.

### What to Change

#### Step 1: New CRUD method on CRUDMismatch

**File: `backend/app/crud/crud_mismatch.py`**

Add after the last method (after line 116):

```python
def get_compliance_breakdown(
    self,
    db: Session,
    *,
    document_id: int,
    tenant_id: int,
    code_component_id: Optional[int] = None,
) -> dict:
    """
    P5B-02: Returns atom coverage breakdown by atom_type.
    Joins mismatches → requirement_atoms to compute per-type coverage.

    Returns dict:
    {
      "overall_score": 0.84,
      "weighted_score": 0.81,
      "by_type": {
        "API_CONTRACT": {"total": 11, "covered": 10, "score": 0.91},
        ...
      },
      "total_atoms": 35,
      "covered_atoms": 29,
      "open_critical_count": 2,
      "false_positive_excluded": 3,
    }
    """
    from app.models.requirement_atom import RequirementAtom
    from sqlalchemy import func, case

    # Atom type weights for weighted compliance score
    ATOM_WEIGHTS = {
        "SECURITY_REQUIREMENT": 3,
        "BUSINESS_RULE": 2,
        "API_CONTRACT": 2,
        "DATA_CONSTRAINT": 1,
        "FUNCTIONAL_REQUIREMENT": 1,
        "WORKFLOW_STEP": 1,
        "ERROR_SCENARIO": 1,
        "NFR": 1,
        "INTEGRATION_POINT": 1,
    }

    # Get all atoms for this document
    atoms_query = db.query(RequirementAtom).filter(
        RequirementAtom.document_id == document_id,
        RequirementAtom.tenant_id == tenant_id,
    )
    all_atoms = atoms_query.all()

    if not all_atoms:
        return {"overall_score": None, "message": "No atoms found — run validation first"}

    # Get open mismatches for this document (exclude false positives)
    mismatch_filter = [
        self.model.document_id == document_id,
        self.model.tenant_id == tenant_id,
        self.model.status.in_(["open", "in_progress"]),  # P5B-10 statuses
        self.model.status != "false_positive",             # P5B-04 exclusion
    ]
    if code_component_id:
        mismatch_filter.append(self.model.code_component_id == code_component_id)

    open_mismatches = db.query(self.model).filter(*mismatch_filter).all()

    # Map atom_id → has_critical_mismatch
    atoms_with_mismatch: set[int] = set()
    open_critical_count = 0
    for m in open_mismatches:
        if m.requirement_atom_id:
            atoms_with_mismatch.add(m.requirement_atom_id)
        if m.severity == "critical":
            open_critical_count += 1

    # Count false positives excluded
    fp_count = db.query(self.model).filter(
        self.model.document_id == document_id,
        self.model.tenant_id == tenant_id,
        self.model.status == "false_positive",
    ).count()

    # Compute per-type breakdown
    by_type = {}
    total_atoms = 0
    covered_atoms = 0
    weighted_total = 0
    weighted_covered = 0

    for atom_type, atoms_of_type in _group_by_type(all_atoms):
        type_total = len(atoms_of_type)
        type_covered = sum(1 for a in atoms_of_type if a.id not in atoms_with_mismatch)
        weight = ATOM_WEIGHTS.get(atom_type, 1)

        by_type[atom_type] = {
            "total": type_total,
            "covered": type_covered,
            "score": round(type_covered / type_total, 4) if type_total else 1.0,
            "weight": weight,
        }
        total_atoms += type_total
        covered_atoms += type_covered
        weighted_total += type_total * weight
        weighted_covered += type_covered * weight

    overall_score = round(covered_atoms / total_atoms, 4) if total_atoms else 1.0
    weighted_score = round(weighted_covered / weighted_total, 4) if weighted_total else 1.0

    return {
        "overall_score": overall_score,
        "weighted_score": weighted_score,
        "by_type": by_type,
        "total_atoms": total_atoms,
        "covered_atoms": covered_atoms,
        "open_critical_count": open_critical_count,
        "false_positive_excluded": fp_count,
    }


def _group_by_type(atoms) -> list:
    """Group RequirementAtom list by atom_type, returns [(type, [atoms])] sorted."""
    from collections import defaultdict
    groups = defaultdict(list)
    for a in atoms:
        groups[a.atom_type].append(a)
    return sorted(groups.items())
```

#### Step 2: New endpoint `GET /validation/{document_id}/compliance-score`

**File: `backend/app/api/endpoints/validation.py`**

Add after existing GET endpoints:

```python
@router.get("/{document_id}/compliance-score")
def get_compliance_score(
    document_id: int,
    code_component_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-02: Returns single compliance score for a document.
    Optional: filter to a specific code component for link-level score.

    Response:
    {
      "document_id": 42,
      "overall_score": 0.84,
      "weighted_score": 0.81,
      "percentage": 84,
      "grade": "B",
      "by_type": { "API_CONTRACT": { "total": 11, "covered": 10, "score": 0.91 } },
      "open_critical_count": 2,
      "false_positive_excluded": 3,
    }
    """
    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    breakdown = crud.mismatch.get_compliance_breakdown(
        db=db,
        document_id=document_id,
        tenant_id=tenant_id,
        code_component_id=code_component_id,
    )

    if breakdown.get("overall_score") is None:
        raise HTTPException(status_code=404, detail=breakdown.get("message"))

    score = breakdown["overall_score"]
    percentage = round(score * 100)

    # Letter grade
    if percentage >= 95: grade = "A"
    elif percentage >= 85: grade = "B"
    elif percentage >= 75: grade = "C"
    elif percentage >= 60: grade = "D"
    else: grade = "F"

    return {
        "document_id": document_id,
        **breakdown,
        "percentage": percentage,
        "grade": grade,
    }
```

#### Step 3: Frontend — Compliance Score Card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add compliance score card at the top of the validation panel, above the mismatch list:

```tsx
{complianceScore && (
  <div className="bg-white border rounded-xl p-5 mb-6 shadow-sm">
    <div className="flex items-center justify-between mb-4">
      <h3 className="font-semibold text-gray-700">Documentation Compliance</h3>
      <div className={`text-3xl font-bold ${
        complianceScore.percentage >= 85 ? 'text-green-600' :
        complianceScore.percentage >= 70 ? 'text-amber-500' : 'text-red-500'
      }`}>
        {complianceScore.percentage}%
        <span className="text-sm ml-1 font-normal text-gray-400">
          Grade {complianceScore.grade}
        </span>
      </div>
    </div>

    {/* Per-type breakdown */}
    <div className="space-y-2">
      {Object.entries(complianceScore.by_type).map(([type, data]) => (
        <div key={type} className="flex items-center gap-3">
          <span className="text-xs font-mono text-gray-500 w-40 flex-shrink-0">
            {type.replace(/_/g, ' ')}
          </span>
          <div className="flex-1 bg-gray-100 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${
                data.score >= 0.9 ? 'bg-green-500' :
                data.score >= 0.7 ? 'bg-amber-400' : 'bg-red-400'
              }`}
              style={{ width: `${data.score * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-600 w-16 text-right">
            {data.covered}/{data.total}
          </span>
        </div>
      ))}
    </div>

    {complianceScore.open_critical_count > 0 && (
      <p className="text-xs text-red-600 mt-3">
        ⚠ {complianceScore.open_critical_count} critical issue{complianceScore.open_critical_count > 1 ? 's' : ''} require immediate attention
      </p>
    )}
  </div>
)}
```

Fetch in `useEffect`:
```tsx
const fetchComplianceScore = async () => {
  const res = await fetch(`/api/v1/validation/${documentId}/compliance-score`, { headers: authHeaders })
  if (res.ok) setComplianceScore(await res.json())
}
```

### Test Commands

```bash
# 1. Run validation on a document first, then:
curl -H "Authorization: Bearer $TOKEN" \
  "/api/v1/validation/{document_id}/compliance-score"

# Expected response:
# { "percentage": 84, "grade": "B", "by_type": { "API_CONTRACT": { "score": 0.91 ... } } }

# 2. Verify weighted score differs from overall score
# weighted_score should be lower when SECURITY_REQUIREMENT atoms have mismatches
# (they have weight 3×)

# 3. Verify false positives are excluded from compliance denominator
# Mark a mismatch as false_positive, re-run score — false_positive_excluded should increment
```

### Risk Assessment
- **Pure read:** No writes — cannot corrupt data
- **No Gemini calls:** Purely DB query computation
- **Backward compatible:** endpoint is new, no existing endpoint modified
- **Performance:** Single complex query per request — add index on `(document_id, tenant_id, status)` in mismatches table (already exists from Phase 0)


---

## P5B-03 — 1-Click Jira Ticket From Mismatch

**Ticket ID:** P5B-03
**Priority:** P1 — Required for enterprise workflow adoption. Developers live in Jira, not DokyDoc.
**Complexity:** Low-Medium
**Risk:** LOW — new endpoint only; Jira API call is outbound only; no DB schema changes needed

### Why This Exists

A developer sees a mismatch: "PaymentService.refund() not implemented per BRD §4.2". They need to create a Jira ticket. Current workflow: copy mismatch title, switch to Jira, create ticket manually, paste description, set priority, link Epic, come back to DokyDoc and note the Jira key. That's 8 manual steps.

Target workflow: Click "Create Ticket" → Jira ticket created in 1 second → Jira key shown on mismatch card → Done.

### Current State

**Existing:**
- `GET /integrations/jira/projects` — lists Jira projects (uses `jira_sync_service.fetch_projects`)
- `JiraItem` model — stores synced items from Jira
- `IntegrationConfig` model — stores `access_token` + `base_url` per tenant
- `jira_sync_service` — has `fetch_projects`, `fetch_epics`, `fetch_sprints`

**Missing:**
- `POST /integrations/jira/create-issue` endpoint
- `create_issue` method on `jira_sync_service`
- Mismatch → Jira issue link tracking (which Jira key was created from which mismatch)

### What to Change

#### Step 1: Add `create_issue` to `JiraSyncService`

**File: `backend/app/services/jira_sync_service.py`**

Add after `fetch_sprints` method:

```python
async def create_issue(
    self,
    *,
    token: str,
    base_url: str,
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",      # Task | Bug | Story
    priority: str = "Medium",      # Highest | High | Medium | Low | Lowest
    labels: list[str] | None = None,
    epic_key: str | None = None,
    assignee_account_id: str | None = None,
) -> dict:
    """
    P5B-03: Creates a single Jira issue and returns the created issue dict.
    Returns: { "key": "PROJ-123", "id": "10001", "url": "https://..." }
    """
    import httpx

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }
                ]
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "labels": labels or ["dokydoc"],
        }
    }

    if epic_key:
        payload["fields"]["parent"] = {"key": epic_key}
    if assignee_account_id:
        payload["fields"]["assignee"] = {"accountId": assignee_account_id}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/rest/api/3/issue",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "key": data["key"],
        "id": data["id"],
        "url": f"{base_url.replace('https://api.atlassian.com/ex/jira/', 'https://')}/browse/{data['key']}"
    }
```

#### Step 2: Add `jira_issue_key` field to Mismatch model

**File: `backend/app/models/mismatch.py`**

Add after `user_notes` field (line 33):

```python
    # P5B-03: Jira issue key created from this mismatch (e.g. "PROJ-123")
    jira_issue_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    jira_issue_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

**New migration: `backend/alembic/versions/s16b1_mismatch_jira_fields.py`**

```python
"""
P5B-03: Add jira_issue_key and jira_issue_url to mismatches.

Revision ID: s16b1
Revises: s16a1
"""
from alembic import op
import sqlalchemy as sa

revision = 's16b1'
down_revision = 's16a1'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('mismatches',
        sa.Column('jira_issue_key', sa.String(50), nullable=True))
    op.add_column('mismatches',
        sa.Column('jira_issue_url', sa.String(500), nullable=True))
    op.create_index(
        'ix_mismatches_jira_issue_key',
        'mismatches', ['jira_issue_key'],
        postgresql_concurrently=True
    )

def downgrade():
    op.drop_index('ix_mismatches_jira_issue_key')
    op.drop_column('mismatches', 'jira_issue_url')
    op.drop_column('mismatches', 'jira_issue_key')
```

#### Step 3: New endpoint `POST /integrations/jira/create-issue`

**File: `backend/app/api/endpoints/integrations.py`**

Add after `trigger_jira_sync` endpoint (after line 516):

```python
@router.post("/jira/create-issue")
async def create_jira_issue_from_mismatch(
    mismatch_id: int = Body(...),
    project_key: str = Body(...),
    issue_type: str = Body("Task"),
    priority: str = Body("Medium"),
    epic_key: Optional[str] = Body(None),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    P5B-03: Creates a Jira issue from a mismatch in one click.

    Auto-populates:
    - Summary: "[DokyDoc] {mismatch_type}: {mismatch description truncated}"
    - Description: Full mismatch details (severity, atom content, code file)
    - Labels: ["dokydoc", mismatch_type.lower(), "validation"]
    - Priority: mapped from severity (critical→Highest, high→High, medium→Medium)

    Stores Jira key on mismatch record so duplicate prevention works.
    """
    config = crud_integration_config.get_by_provider(
        db, tenant_id=tenant_id, provider="jira"
    )
    if not config or not config.is_active or not config.access_token:
        raise HTTPException(status_code=404, detail="No active Jira integration found.")

    mismatch = crud.mismatch.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Mismatch not found.")

    if mismatch.jira_issue_key:
        raise HTTPException(
            status_code=409,
            detail=f"Jira issue already exists: {mismatch.jira_issue_key}"
        )

    # Map severity to Jira priority
    priority_map = {
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "info": "Lowest",
    }
    jira_priority = priority_map.get(mismatch.severity.lower(), priority)

    # Build summary (max 255 chars for Jira)
    summary = f"[DokyDoc] {mismatch.mismatch_type}: {mismatch.description[:180]}"

    # Build description with mismatch details
    description = (
        f"Detected by DokyDoc Validation Engine\n\n"
        f"Severity: {mismatch.severity.upper()}\n"
        f"Type: {mismatch.mismatch_type}\n"
        f"Direction: {'BRD requirement not in code' if mismatch.direction == 'forward' else 'Code not in BRD'}\n\n"
        f"Details:\n{mismatch.description}\n\n"
    )
    if mismatch.details:
        description += f"Technical details: {str(mismatch.details)[:500]}\n\n"
    description += f"View in DokyDoc: /dashboard/validation-panel?mismatch={mismatch.id}"

    from app.services.jira_sync_service import jira_sync_service
    try:
        result = await jira_sync_service.create_issue(
            token=config.access_token,
            base_url=config.base_url or "",
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=jira_priority,
            labels=["dokydoc", mismatch.mismatch_type.lower().replace("_", "-"), "validation"],
            epic_key=epic_key,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira API error: {str(e)}")

    # Store Jira key on mismatch
    from datetime import datetime
    db.query(models.Mismatch).filter(models.Mismatch.id == mismatch_id).update({
        "jira_issue_key": result["key"],
        "jira_issue_url": result["url"],
        "updated_at": datetime.now(),
    })
    db.commit()

    return {
        "jira_key": result["key"],
        "jira_url": result["url"],
        "mismatch_id": mismatch_id,
    }
```

#### Step 4: Frontend — "Create Ticket" button on mismatch card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Inside the mismatch card actions row (near the existing "Accept/Reject" buttons from Phase 1):

```tsx
{/* Jira integration button */}
{jiraConnected && (
  mismatch.jira_issue_key ? (
    <a
      href={mismatch.jira_issue_url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-200 flex items-center gap-1"
    >
      <JiraIcon className="h-3 w-3" />
      {mismatch.jira_issue_key}
    </a>
  ) : (
    <button
      onClick={() => handleCreateJiraTicket(mismatch.id)}
      disabled={creatingJira === mismatch.id}
      className="text-xs px-2 py-1 bg-gray-100 hover:bg-blue-50 hover:text-blue-700 text-gray-600 rounded border border-gray-200 flex items-center gap-1"
    >
      {creatingJira === mismatch.id ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <Plus className="h-3 w-3" />
      )}
      Create Ticket
    </button>
  )
)}
```

Handler:
```typescript
const handleCreateJiraTicket = async (mismatchId: number) => {
  setCreatingJira(mismatchId)
  try {
    const res = await fetch('/api/v1/integrations/jira/create-issue', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mismatch_id: mismatchId,
        project_key: selectedJiraProject,  // from user's saved preference
        issue_type: 'Task',
      })
    })
    const data = await res.json()
    if (res.ok) {
      // Update mismatch in local state
      setMismatches(prev => prev.map(m =>
        m.id === mismatchId
          ? { ...m, jira_issue_key: data.jira_key, jira_issue_url: data.jira_url }
          : m
      ))
      toast.success(`Created ${data.jira_key}`)
    } else if (res.status === 409) {
      toast.info(`Jira ticket already exists: ${data.detail}`)
    } else {
      toast.error('Failed to create Jira ticket')
    }
  } finally {
    setCreatingJira(null)
  }
}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16b1

# 2. Verify columns added
psql -c "\d mismatches" | grep "jira_issue"

# 3. Test create issue (requires active Jira integration)
curl -X POST /api/v1/integrations/jira/create-issue \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mismatch_id": 1, "project_key": "PROJ", "issue_type": "Task"}'
# Expected: { "jira_key": "PROJ-123", "jira_url": "https://..." }

# 4. Verify stored on mismatch
psql -c "SELECT jira_issue_key, jira_issue_url FROM mismatches WHERE id = 1"

# 5. Test duplicate prevention
# Call endpoint again for same mismatch
# Expected: 409 "Jira issue already exists: PROJ-123"
```

### Risk Assessment
- **No DB writes on Jira API failure:** HTTPException is raised before DB update
- **Duplicate prevention:** 409 check on `mismatch.jira_issue_key` prevents double-creation
- **Non-breaking:** New columns nullable, new endpoint only — nothing existing changed
- **SSRF protection:** `config.base_url` comes from admin-configured integration, not user input


---

## P5B-04 — False Positive Workflow (Mark, Reason, Dispute, Exclude From Score)

**Ticket ID:** P5B-04
**Priority:** P0 — Without this, teams lose trust in DokyDoc. Every tool that auto-detects issues MUST have a dispute mechanism.
**Complexity:** Low
**Risk:** LOW — status transition only; feeds Phase 1 training flywheel

### Why This Exists

The AI generates mismatches. Some will be wrong. If a developer can't say "this is a false positive and here's why," they will stop trusting ALL the mismatches — including the real ones. The false positive workflow:
1. Marks the mismatch with `status="false_positive"`
2. Requires a reason (free text, mandatory) — "The BRD says 'authentication required' which IS implemented via the JWT middleware, the AI didn't see the middleware"
3. Excludes false positives from the compliance score (P5B-02)
4. Captures as a TrainingExample with `human_label="rejected"` (Phase 1 flywheel)
5. Shows false positives in a separate filtered view so they're not lost

A BA can **dispute** a false positive decision: if developer marks as FP but BA disagrees, BA can re-open as "open" with their counter-reason.

### Current State

**File: `backend/app/models/mismatch.py` (line 30)**
`status: Mapped[str] = mapped_column(String, default="new", index=True, nullable=False)`
Only one real state: `"new"`. No `false_positive`, no `disputed`, no lifecycle.

**File: `backend/app/api/endpoints/validation.py`**
No endpoint to update mismatch status. Only creation endpoints exist.

**File: `backend/app/models/training_example.py`** (Phase 1)
`TrainingExample` exists with `human_label` field. False positive capture is planned but not wired to mismatch status changes.

### What to Change

#### Step 1: No new migration needed for P5B-04 itself
The status field already exists and stores strings. We add new valid values ("false_positive", "disputed") via application-layer enforcement only (P5B-10 will add a proper migration with a CHECK constraint later).

However, we DO need to add `resolution_note` to mismatches:

**File: `backend/app/models/mismatch.py`**

Add after `user_notes` field:

```python
    # P5B-04 / P5B-10: free-text reason for status transitions
    # Required when marking as false_positive; optional for resolved/verified
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # P5B-04: who last changed the status and when
    status_changed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

**Add to migration s16b1** (add to upgrade() of s16b1 since we're already modifying mismatches):
```python
# In s16b1 upgrade(), add:
op.add_column('mismatches',
    sa.Column('resolution_note', sa.Text(), nullable=True))
op.add_column('mismatches',
    sa.Column('status_changed_by_id', sa.Integer(),
              sa.ForeignKey('users.id'), nullable=True))
op.add_column('mismatches',
    sa.Column('status_changed_at', sa.DateTime(), nullable=True))
```

#### Step 2: Add `mark_false_positive` and `dispute_false_positive` to CRUDMismatch

**File: `backend/app/crud/crud_mismatch.py`**

```python
def mark_false_positive(
    self,
    db: Session,
    *,
    mismatch_id: int,
    tenant_id: int,
    reason: str,
    changed_by_user_id: int,
) -> "Mismatch":
    """
    P5B-04: Mark a mismatch as false positive.
    reason is REQUIRED — raises ValueError if empty.
    Captures TrainingExample with human_label='rejected'.
    """
    if not reason or not reason.strip():
        raise ValueError("A reason is required when marking a mismatch as false positive")

    mismatch = self.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise ValueError(f"Mismatch {mismatch_id} not found")

    from datetime import datetime
    mismatch.status = "false_positive"
    mismatch.resolution_note = reason.strip()
    mismatch.status_changed_by_id = changed_by_user_id
    mismatch.status_changed_at = datetime.now()
    db.commit()
    db.refresh(mismatch)

    # Capture training example (Phase 1 flywheel)
    try:
        from app.crud.crud_training_example import training_example as crud_te
        crud_te.create_from_mismatch(
            db=db,
            mismatch_id=mismatch_id,
            tenant_id=tenant_id,
            ai_output={"verdict": "mismatch", "confidence": mismatch.confidence},
            input_context={
                "mismatch_type": mismatch.mismatch_type,
                "description": mismatch.description,
                "human_label": "rejected",
                "rejection_reason": reason,
            }
        )
    except Exception:
        pass  # Never block status update due to training capture failure

    return mismatch


def dispute_false_positive(
    self,
    db: Session,
    *,
    mismatch_id: int,
    tenant_id: int,
    dispute_reason: str,
    changed_by_user_id: int,
) -> "Mismatch":
    """
    P5B-04: Re-open a false positive as disputed (BA disagrees with FP decision).
    Sets status to 'disputed' — shows in both FP view and open mismatch view.
    """
    if not dispute_reason or not dispute_reason.strip():
        raise ValueError("A dispute reason is required")

    mismatch = self.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise ValueError(f"Mismatch {mismatch_id} not found")

    if mismatch.status != "false_positive":
        raise ValueError("Can only dispute a mismatch that is marked as false positive")

    from datetime import datetime
    mismatch.status = "disputed"
    mismatch.resolution_note = (
        f"[DISPUTED by user {changed_by_user_id}]: {dispute_reason.strip()}\n"
        f"[Previous FP reason]: {mismatch.resolution_note or 'none'}"
    )
    mismatch.status_changed_by_id = changed_by_user_id
    mismatch.status_changed_at = datetime.now()
    db.commit()
    db.refresh(mismatch)
    return mismatch
```

#### Step 3: New endpoints

**File: `backend/app/api/endpoints/validation.py`**

```python
from pydantic import BaseModel

class MismatchFalsePositiveRequest(BaseModel):
    reason: str  # Required — min 10 characters

class MismatchDisputeRequest(BaseModel):
    dispute_reason: str


@router.post("/mismatches/{mismatch_id}/false-positive")
def mark_mismatch_false_positive(
    mismatch_id: int,
    body: MismatchFalsePositiveRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-04: Mark a mismatch as false positive with required reason.
    Excludes from compliance score. Captures training data.
    """
    if len(body.reason.strip()) < 10:
        raise HTTPException(status_code=422, detail="Reason must be at least 10 characters")
    try:
        mismatch = crud.mismatch.mark_false_positive(
            db=db,
            mismatch_id=mismatch_id,
            tenant_id=tenant_id,
            reason=body.reason,
            changed_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "false_positive", "mismatch_id": mismatch_id, "reason": mismatch.resolution_note}


@router.post("/mismatches/{mismatch_id}/dispute")
def dispute_false_positive(
    mismatch_id: int,
    body: MismatchDisputeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-04: Dispute a false positive decision. Re-opens as 'disputed'.
    Typically used by BA when developer incorrectly marked as FP.
    """
    try:
        mismatch = crud.mismatch.dispute_false_positive(
            db=db,
            mismatch_id=mismatch_id,
            tenant_id=tenant_id,
            dispute_reason=body.dispute_reason,
            changed_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "disputed", "mismatch_id": mismatch_id}
```

#### Step 4: Frontend — False Positive button on mismatch card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

In the mismatch card action buttons (next to "Accept/Reject" from Phase 1):

```tsx
{/* False Positive button */}
{mismatch.status !== 'false_positive' && mismatch.status !== 'resolved' && (
  <button
    onClick={() => setFalsePositiveMismatch(mismatch)}
    className="text-xs px-2 py-1 bg-gray-100 hover:bg-orange-50 hover:text-orange-700 text-gray-600 rounded border border-gray-200"
  >
    Not Real
  </button>
)}

{/* Show FP badge + dispute option */}
{mismatch.status === 'false_positive' && (
  <div className="flex items-center gap-1">
    <span className="text-xs px-2 py-1 bg-orange-100 text-orange-700 rounded">
      False Positive
    </span>
    <button
      onClick={() => handleDispute(mismatch.id)}
      className="text-xs text-gray-400 hover:text-red-500"
      title="Dispute this false positive decision"
    >
      Dispute
    </button>
  </div>
)}
```

False Positive modal:
```tsx
{falsePositiveMismatch && (
  <Modal
    title="Mark as False Positive"
    onClose={() => setFalsePositiveMismatch(null)}
  >
    <p className="text-sm text-gray-600 mb-3">
      Explain why this is NOT a real mismatch. This helps train DokyDoc to be more accurate.
    </p>
    <textarea
      value={fpReason}
      onChange={(e) => setFpReason(e.target.value)}
      placeholder="e.g. 'The authentication IS implemented via the JWT middleware in app/middleware/auth.py — the AI didn't see it because the file wasn't attached'"
      className="w-full text-sm border rounded p-2 h-24 resize-none"
      minLength={10}
    />
    <p className="text-xs text-gray-400 mt-1">{fpReason.length}/10 characters minimum</p>
    <div className="flex gap-2 mt-3">
      <button
        onClick={() => submitFalsePositive(falsePositiveMismatch.id, fpReason)}
        disabled={fpReason.length < 10}
        className="px-3 py-1.5 bg-orange-500 text-white rounded text-sm disabled:opacity-40"
      >
        Confirm False Positive
      </button>
      <button
        onClick={() => setFalsePositiveMismatch(null)}
        className="px-3 py-1.5 text-gray-600 text-sm"
      >
        Cancel
      </button>
    </div>
  </Modal>
)}
```

Also add a filter tab for false positives:
```tsx
<TabGroup>
  <Tab active={filter === 'open'} onClick={() => setFilter('open')}>
    Open ({openCount})
  </Tab>
  <Tab active={filter === 'false_positive'} onClick={() => setFilter('false_positive')}>
    False Positives ({fpCount})
  </Tab>
  <Tab active={filter === 'disputed'} onClick={() => setFilter('disputed')}>
    Disputed ({disputedCount})
  </Tab>
</TabGroup>
```

### Test Commands

```bash
# 1. Mark mismatch as false positive (requires reason)
curl -X POST /api/v1/validation/mismatches/1/false-positive \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Authentication IS implemented via JWT middleware"}'
# Expected: { "status": "false_positive", "mismatch_id": 1 }

# 2. Try without reason (should fail)
curl -X POST /api/v1/validation/mismatches/1/false-positive \
  -d '{"reason": "short"}'
# Expected: 422 "Reason must be at least 10 characters"

# 3. Verify excluded from compliance score
# GET /validation/{doc_id}/compliance-score
# false_positive_excluded should be 1

# 4. Dispute the FP decision
curl -X POST /api/v1/validation/mismatches/1/dispute \
  -d '{"dispute_reason": "The middleware is not enough, BRD requires explicit endpoint auth"}'
# Expected: { "status": "disputed" }

# 5. Verify training example captured
psql -c "SELECT human_label, input_context FROM training_examples ORDER BY id DESC LIMIT 1"
# Expected: human_label = 'rejected', input_context contains rejection_reason
```

### Risk Assessment
- **No schema migration needed for status** — status is a free-form String column, existing values unaffected
- **Training example capture is try/except guarded** — FP marking never fails due to training error
- **Reason validation both backend + frontend** — prevents useless "idk" reasons that don't train the model
- **Audit trail via `resolution_note` + `status_changed_at`** — full accountability


---

## P5B-05 — Mismatch Evidence Transparency (Show Exactly What AI Checked)

**Ticket ID:** P5B-05
**Priority:** P0 — Developers will reject mismatch findings they can't verify. Showing the evidence builds trust.
**Complexity:** Low
**Risk:** LOW — read-only; just surfacing data already stored in `mismatch.details` JSONB field

### Why This Exists

Current mismatch card shows: "API_CONTRACT: POST /payments missing rate limiting"

Developer's response: "But we DO have rate limiting! Show me where you looked."

Currently they can't. DokyDoc's validation engine sees `structured_analysis` from the code file and the atom content from the BRD — but this evidence is NOT shown to the user. It's buried in the `details` JSONB field or dropped entirely.

After P5B-05, every mismatch has an expandable "Evidence" panel:

```
[▼ Show Evidence]
  BRD Requirement (REQ-007):
    "API /payments/charge must enforce a rate limit of max 30 requests per minute per user"

  Code DokyDoc Analyzed (payment_service.py):
    api_contracts: [{ method: "POST", path: "/payments/charge", auth: "bearer_token" }]
    data_flows: ["request → rate_check → charge_processor → db_write"]
    internal_imports: ["from ratelimit import limits"]  ← This is the key field

  What AI Concluded:
    "rate_limit import found but no decorator applied to the endpoint function"
    Confidence: 0.78

  AI's Raw Reasoning:
    "The code imports ratelimit library but the @limits() decorator is not visible
     on the charge endpoint in structured_analysis.api_contracts[0]"
```

### Current State

**File: `backend/app/models/mismatch.py` (line 31)**
`details: Mapped[dict] = mapped_column(JSONB, nullable=True)` — JSONB field exists but is inconsistently populated. Some mismatches have `details={"verdict": "missing", "evidence": "..."}`, others have null.

**File: `backend/app/services/validation_service.py` (line 291-340)**
`call_gemini_for_typed_validation` returns a `mismatches` list. Each mismatch dict includes whatever Gemini returns — but `atom_content`, `code_analysis_snapshot`, and `confidence_reasoning` are NOT systematically stored in `details`.

### What to Change

#### Step 1: Ensure `details` JSONB is populated with evidence on mismatch creation

**File: `backend/app/services/ai/gemini.py`**

In `call_gemini_for_typed_validation`, the prompt already asks Gemini for `evidence` per mismatch. Ensure the prompt output schema includes `confidence_reasoning`:

Find the section where the prompt is built (around line 700-760) and ensure the JSON output schema includes:

```python
# The existing prompt already requests these fields per mismatch.
# Ensure these keys are explicitly in the schema section:
"""
Each mismatch in the array must have these fields:
{
  "atom_local_id": "REQ-001",       // which atom
  "mismatch_type": "...",           // type of gap
  "description": "...",             // human-readable description
  "severity": "critical|high|medium|low|info",
  "confidence": "high|medium|low",
  "evidence": "...",                // one sentence: what the AI found (or didn't find)
  "confidence_reasoning": "..."     // NEW: why AI is confident in this finding
}
"""
```

#### Step 2: Store richer evidence in `details` when creating mismatch

**File: `backend/app/services/validation_service.py`**

In the `create_with_link` call (line ~315-325), enrich the `obj_in` dict with evidence data:

```python
# BEFORE:
new_mismatch = crud.mismatch.create_with_link(
    db=db,
    obj_in={
        **m,
        "direction": "forward",
        "requirement_atom_id": db_atom_id,
    },
    link_id=link.id,
    owner_id=user_id,
    tenant_id=tenant_id,
)

# AFTER — enrich with evidence snapshot:
# Find the atom's full content for evidence
atom_content = next(
    (a.content for a in atoms if a.atom_id == m.get("atom_local_id", "")),
    None
)

# Extract relevant snippet from code_analysis for evidence
code_evidence_snapshot = _extract_evidence_snapshot(
    code_analysis=code_analysis,
    atom_type=atype,
    mismatch_description=m.get("description", ""),
)

new_mismatch = crud.mismatch.create_with_link(
    db=db,
    obj_in={
        **m,
        "direction": "forward",
        "requirement_atom_id": db_atom_id,
        # P5B-05: store evidence for transparency
        "details": {
            **(m.get("details") or {}),
            "evidence": m.get("evidence", ""),
            "confidence_reasoning": m.get("confidence_reasoning", ""),
            "atom_content": atom_content,
            "atom_type": atype,
            "code_evidence": code_evidence_snapshot,
            "validation_timestamp": datetime.now().isoformat(),
        }
    },
    link_id=link.id,
    owner_id=user_id,
    tenant_id=tenant_id,
)
```

**Helper function** (add to `validation_service.py`):

```python
def _extract_evidence_snapshot(
    code_analysis: dict,
    atom_type: str,
    mismatch_description: str,
) -> dict:
    """
    P5B-05: Extract the specific structured_analysis section most relevant
    to the atom_type being checked. Used to populate mismatch.details.code_evidence.
    Only stores the fields that matter for each atom type — not the full analysis.
    """
    if not code_analysis:
        return {}

    # Which structured_analysis fields matter per atom type
    RELEVANT_FIELDS_BY_TYPE = {
        "API_CONTRACT":           ["api_contracts", "auth_patterns"],
        "BUSINESS_RULE":          ["business_logic", "validation_rules", "functions"],
        "FUNCTIONAL_REQUIREMENT": ["purpose", "responsibilities", "functions"],
        "DATA_CONSTRAINT":        ["data_models", "validation_rules", "schemas"],
        "WORKFLOW_STEP":          ["data_flows", "functions", "component_interactions"],
        "ERROR_SCENARIO":         ["error_handling", "exceptions", "functions"],
        "SECURITY_REQUIREMENT":   ["auth_patterns", "security_controls", "dependencies"],
        "NFR":                    ["performance_notes", "caching_patterns", "async_patterns"],
        "INTEGRATION_POINT":      ["external_calls", "component_interactions", "webhooks"],
    }

    relevant = RELEVANT_FIELDS_BY_TYPE.get(atom_type, ["purpose", "responsibilities"])
    snapshot = {}
    for field in relevant:
        val = code_analysis.get(field)
        if val:
            # Truncate lists to avoid storing massive evidence blobs
            if isinstance(val, list):
                snapshot[field] = val[:5]  # Max 5 items
            elif isinstance(val, str):
                snapshot[field] = val[:500]  # Max 500 chars
            else:
                snapshot[field] = val
    return snapshot
```

#### Step 3: New endpoint `GET /validation/mismatches/{id}/evidence`

**File: `backend/app/api/endpoints/validation.py`**

```python
@router.get("/mismatches/{mismatch_id}/evidence")
def get_mismatch_evidence(
    mismatch_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-05: Returns the evidence DokyDoc used to detect this mismatch.
    Shows: BRD atom content, code analysis snapshot, AI reasoning.
    """
    mismatch = crud.mismatch.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    details = mismatch.details or {}

    # Load the requirement atom content
    atom_content = details.get("atom_content")
    if not atom_content and mismatch.requirement_atom_id:
        from app.models.requirement_atom import RequirementAtom
        atom = db.query(RequirementAtom).filter(
            RequirementAtom.id == mismatch.requirement_atom_id
        ).first()
        if atom:
            atom_content = atom.content

    return {
        "mismatch_id": mismatch_id,
        "mismatch_type": mismatch.mismatch_type,
        "severity": mismatch.severity,
        "evidence": {
            "brd_requirement": {
                "atom_id": details.get("atom_local_id"),
                "atom_type": details.get("atom_type", mismatch.mismatch_type),
                "content": atom_content or "Not available (pre-P5B-05 mismatch)",
            },
            "code_analyzed": {
                "snapshot": details.get("code_evidence", {}),
                "note": "Subset of structured_analysis relevant to this atom type"
            },
            "ai_conclusion": {
                "verdict": details.get("verdict", "mismatch"),
                "evidence_sentence": details.get("evidence", mismatch.description),
                "confidence": mismatch.confidence,
                "reasoning": details.get("confidence_reasoning", "Not available"),
                "validated_at": details.get("validation_timestamp"),
            }
        }
    }
```

#### Step 4: Frontend — Evidence expandable panel on mismatch card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add collapsible evidence section inside each mismatch card:

```tsx
const [expandedEvidence, setExpandedEvidence] = useState<number | null>(null)
const [evidenceData, setEvidenceData] = useState<Record<number, any>>({})

const loadEvidence = async (mismatchId: number) => {
  if (evidenceData[mismatchId]) {
    setExpandedEvidence(expandedEvidence === mismatchId ? null : mismatchId)
    return
  }
  const res = await fetch(`/api/v1/validation/mismatches/${mismatchId}/evidence`, { headers: authHeaders })
  if (res.ok) {
    setEvidenceData(prev => ({ ...prev, [mismatchId]: await res.json() }))
    setExpandedEvidence(mismatchId)
  }
}

// Inside mismatch card:
<button
  onClick={() => loadEvidence(mismatch.id)}
  className="text-xs text-blue-500 hover:underline flex items-center gap-1 mt-2"
>
  {expandedEvidence === mismatch.id ? (
    <><ChevronUp className="h-3 w-3" /> Hide Evidence</>
  ) : (
    <><ChevronDown className="h-3 w-3" /> Show Evidence</>
  )}
</button>

{expandedEvidence === mismatch.id && evidenceData[mismatch.id] && (
  <div className="mt-2 border-t pt-2 space-y-2 text-xs">
    <div className="bg-blue-50 rounded p-2">
      <p className="font-semibold text-blue-700 mb-1">
        BRD Requirement ({evidenceData[mismatch.id].evidence.brd_requirement.atom_type}):
      </p>
      <p className="text-gray-700 italic">
        "{evidenceData[mismatch.id].evidence.brd_requirement.content}"
      </p>
    </div>
    <div className="bg-gray-50 rounded p-2">
      <p className="font-semibold text-gray-600 mb-1">Code Analyzed:</p>
      <pre className="text-gray-600 whitespace-pre-wrap overflow-x-auto">
        {JSON.stringify(evidenceData[mismatch.id].evidence.code_analyzed.snapshot, null, 2)}
      </pre>
    </div>
    <div className="bg-amber-50 rounded p-2">
      <p className="font-semibold text-amber-700 mb-1">AI Conclusion:</p>
      <p className="text-gray-700">
        {evidenceData[mismatch.id].evidence.ai_conclusion.evidence_sentence}
      </p>
      {evidenceData[mismatch.id].evidence.ai_conclusion.reasoning && (
        <p className="text-gray-500 mt-1">
          Reasoning: {evidenceData[mismatch.id].evidence.ai_conclusion.reasoning}
        </p>
      )}
      <p className="text-gray-400 mt-1">
        Confidence: {evidenceData[mismatch.id].evidence.ai_conclusion.confidence}
      </p>
    </div>
  </div>
)}
```

### Test Commands

```bash
# 1. Run validation on a document
# 2. Check details field is populated
psql -c "SELECT id, details FROM mismatches ORDER BY id DESC LIMIT 1"
# Expected: details contains code_evidence, atom_content, evidence keys

# 3. Call evidence endpoint
curl /api/v1/validation/mismatches/1/evidence
# Expected: full structured evidence object

# 4. For old mismatches (pre-P5B-05): graceful degradation
# brd_requirement.content = "Not available (pre-P5B-05 mismatch)"
# reasoning = "Not available"
```

### Risk Assessment
- **No new columns needed** — uses existing `details` JSONB field
- **Backward compatible** — old mismatches get "Not available" for fields not previously stored
- **Lazy loading** — evidence loaded on demand (click), not on page load
- **Snapshot max size** — `_extract_evidence_snapshot` caps list fields at 5 items and strings at 500 chars — prevents bloated JSONB blobs


---

## P5B-06 — Webhook → Auto Re-validation → Smart Mismatch Auto-Close

**Ticket ID:** P5B-06
**Priority:** P1 — Without this, DokyDoc is a one-shot tool. Enterprise teams need continuous validation as code evolves.
**Complexity:** Medium-High
**Risk:** MEDIUM — modifies Celery task pipeline; all changes are additive and guarded

### Why This Exists

Current flow after developer pushes code to GitHub:
```
GitHub push → webhook → code re-analysis task (done)
```

Missing:
```
→ auto re-validation (are the mismatches now fixed?)
→ auto-close resolved mismatches (celebrate progress!)
→ reopen regressions (something broke)
→ notify team of changes
```

Without this, a developer fixes a critical mismatch, pushes code, and DokyDoc still shows it as OPEN. They have to manually re-run validation. That's broken.

### Current State

**File: `backend/app/api/endpoints/webhooks.py` (line ~310-325)**
After successful push, dispatches `webhook_triggered_analysis.delay(...)`. This re-analyzes changed code files but **does NOT trigger re-validation**.

**File: `backend/app/tasks/code_analysis_tasks.py`**
`webhook_triggered_analysis` task — completes when code analysis is done. Has no post-analysis hook to trigger validation.

**File: `backend/app/crud/crud_mismatch.py` (line 63-80)**
`remove_by_link` — deletes ALL mismatches on re-validation. This is the blunt-force approach we're replacing with smart compare-and-merge.

### What to Change

#### Step 1: New Celery task `auto_revalidate_after_analysis`

**New content in `backend/app/tasks/code_analysis_tasks.py`** (or a new file `backend/app/tasks/validation_tasks.py`):

```python
@celery_app.task(name="auto_revalidate_after_analysis", max_retries=2, bind=True)
def auto_revalidate_after_analysis(
    self,
    repo_id: int,
    tenant_id: int,
    changed_component_ids: list[int],
    commit_hash: str | None = None,
):
    """
    P5B-06: Triggered after code re-analysis to auto-run validation and smart-merge results.

    For each document linked to changed code components:
    1. Run validation ONLY for the changed components (not entire document)
    2. Compare new mismatches vs existing open mismatches
    3. Auto-close mismatches that no longer appear (developer fixed them)
    4. Keep existing mismatches that still appear (still broken)
    5. Add new mismatches that weren't there before (regressions)
    6. Send notification summary to document owners
    """
    from app.db.session import SessionLocal
    from app.services.validation_service import ValidationService
    from app.crud import crud_document_code_link, crud_mismatch, crud_notification

    db = SessionLocal()
    try:
        validation_svc = ValidationService()

        # Find all document-code links that involve the changed components
        affected_links = crud_document_code_link.get_by_component_ids(
            db=db,
            component_ids=changed_component_ids,
            tenant_id=tenant_id,
        )

        if not affected_links:
            return {"status": "no_affected_links", "repo_id": repo_id}

        results = {
            "auto_closed": 0,
            "still_open": 0,
            "new_mismatches": 0,
            "documents_revalidated": set(),
        }

        for link in affected_links:
            try:
                link_result = _revalidate_link_and_merge(
                    db=db,
                    link=link,
                    tenant_id=tenant_id,
                    validation_svc=validation_svc,
                    commit_hash=commit_hash,
                )
                results["auto_closed"] += link_result["closed"]
                results["still_open"] += link_result["still_open"]
                results["new_mismatches"] += link_result["new"]
                results["documents_revalidated"].add(link.document_id)

            except Exception as e:
                logger.warning(
                    f"Auto-revalidation failed for link {link.id}: {e}"
                )
                # Continue with other links — never stop batch for one failure

        # Send notification if anything changed
        total_changes = results["auto_closed"] + results["new_mismatches"]
        if total_changes > 0:
            _notify_validation_changes(
                db=db, tenant_id=tenant_id,
                results=results, commit_hash=commit_hash,
            )

        results["documents_revalidated"] = list(results["documents_revalidated"])
        return results

    finally:
        db.close()


def _revalidate_link_and_merge(
    db,
    link,
    tenant_id: int,
    validation_svc,
    commit_hash: str | None,
) -> dict:
    """
    Runs validation for ONE document-code link and merges results with existing mismatches.

    Strategy:
    1. Get existing open mismatches for this link (before re-validation)
    2. Run fresh validation (generates new mismatch set)
    3. Compare: new set vs old set using (atom_id + mismatch_type) as the key
    4. Matches in BOTH → still_open (keep as-is, update details if changed)
    5. In OLD only → auto_close (developer fixed it)
    6. In NEW only → add as new mismatch
    """
    import asyncio

    # 1. Get existing open mismatches
    existing_open = db.query(Mismatch).filter(
        Mismatch.document_id == link.document_id,
        Mismatch.code_component_id == link.code_component_id,
        Mismatch.tenant_id == tenant_id,
        Mismatch.status.in_(["open", "in_progress"]),
    ).all()

    # Key for matching: atom_id + mismatch_type (normalized)
    def mismatch_key(m_dict_or_obj) -> str:
        if isinstance(m_dict_or_obj, dict):
            return f"{m_dict_or_obj.get('requirement_atom_id','X')}::{m_dict_or_obj.get('mismatch_type','')}"
        return f"{m_dict_or_obj.requirement_atom_id}::{m_dict_or_obj.mismatch_type}"

    existing_keys = {mismatch_key(m): m for m in existing_open}

    # 2. Run fresh validation for this specific link
    # Get document and component
    document = db.query(Document).get(link.document_id)
    component = db.query(CodeComponent).get(link.code_component_id)

    if not document or not component:
        return {"closed": 0, "still_open": len(existing_open), "new": 0}

    # Run validation without destroying existing mismatches first
    new_mismatches_raw = asyncio.get_event_loop().run_until_complete(
        validation_svc.run_validation_for_link_preview(
            db=db,
            document=document,
            component=component,
            tenant_id=tenant_id,
        )
    )

    new_keys = {mismatch_key(m): m for m in new_mismatches_raw}

    # 3. Compare and merge
    closed_count = 0
    new_count = 0
    from datetime import datetime

    # Auto-close mismatches no longer detected
    for key, existing_m in existing_keys.items():
        if key not in new_keys:
            existing_m.status = "auto_closed"
            existing_m.resolution_note = (
                f"Auto-closed: not detected after code push"
                + (f" (commit {commit_hash[:8]})" if commit_hash else "")
            )
            existing_m.updated_at = datetime.now()
            # P5B-11: store commit hash that resolved it
            if hasattr(existing_m, 'resolved_commit_hash'):
                existing_m.resolved_commit_hash = commit_hash
            closed_count += 1

    # Add genuinely new mismatches
    for key, new_m_data in new_keys.items():
        if key not in existing_keys:
            try:
                crud.mismatch.create_with_link(
                    db=db,
                    obj_in={**new_m_data, "direction": "forward"},
                    link_id=link.id,
                    owner_id=1,  # system user — auto-validation
                    tenant_id=tenant_id,
                )
                new_count += 1
            except Exception:
                pass

    db.commit()

    return {
        "closed": closed_count,
        "still_open": len(existing_keys) - closed_count,
        "new": new_count,
    }


def _notify_validation_changes(db, tenant_id, results, commit_hash):
    """Send in-app notification summarizing what changed after code push."""
    try:
        from app.services.notification_service import notification_service
        n_docs = len(results["documents_revalidated"])
        message_parts = []
        if results["auto_closed"] > 0:
            message_parts.append(f"✅ {results['auto_closed']} mismatch(es) auto-closed (code fixed)")
        if results["new_mismatches"] > 0:
            message_parts.append(f"⚠️ {results['new_mismatches']} new mismatch(es) detected")

        if message_parts:
            notification_service.create(
                db,
                tenant_id=tenant_id,
                title="Validation updated after code push",
                body="\n".join(message_parts),
                notification_type="validation_auto_update",
                metadata={"commit_hash": commit_hash, "docs_affected": n_docs},
            )
    except Exception:
        pass  # Notification failure never blocks the task
```

#### Step 2: Hook auto-revalidate into `webhook_triggered_analysis`

**File: `backend/app/tasks/code_analysis_tasks.py`**

Find `webhook_triggered_analysis` task. After the analysis completes and components are updated, add:

```python
# At end of webhook_triggered_analysis, after code analysis complete:
# P5B-06: Trigger auto re-validation for changed components
try:
    changed_component_ids = [
        c.id for c in updated_components  # List of newly analyzed CodeComponent objects
    ]
    if changed_component_ids:
        auto_revalidate_after_analysis.apply_async(
            kwargs={
                "repo_id": repo_id,
                "tenant_id": tenant_id,
                "changed_component_ids": changed_component_ids,
                "commit_hash": commit_hash,
            },
            countdown=30,  # Wait 30s for analysis to fully settle before validating
        )
        logger.info(
            f"Webhook analysis done — queued auto-revalidation for "
            f"{len(changed_component_ids)} components"
        )
except Exception as e:
    logger.warning(f"Could not queue auto-revalidation (non-fatal): {e}")
```

#### Step 3: Add `get_by_component_ids` to `CRUDDocumentCodeLink`

**File: `backend/app/crud/crud_document_code_link.py`** (or equivalent CRUD file):

```python
def get_by_component_ids(
    self,
    db: Session,
    *,
    component_ids: list[int],
    tenant_id: int,
) -> list:
    """P5B-06: Find all document-code links for a list of component IDs."""
    if not component_ids:
        return []
    return db.query(self.model).filter(
        self.model.code_component_id.in_(component_ids),
        self.model.tenant_id == tenant_id,
    ).all()
```

#### Step 4: New migration for `resolved_commit_hash` on mismatches

Add to `s16b1` (or create `s16c1`):
```python
op.add_column('mismatches',
    sa.Column('resolved_commit_hash', sa.String(40), nullable=True))
op.add_column('mismatches',
    sa.Column('created_commit_hash', sa.String(40), nullable=True))
```

(These overlap with P5B-11 — merge into one migration.)

#### Step 5: Frontend — "Auto-Updated" badge on recently auto-closed mismatches

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

```tsx
{mismatch.status === 'auto_closed' && (
  <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full flex items-center gap-1">
    <CheckCircle className="h-3 w-3" />
    Auto-resolved after code push
  </span>
)}
```

### Test Commands

```bash
# 1. Create a mismatch manually via validation
# Note the mismatch ID

# 2. Simulate webhook push that fixes the code
# (In testing: directly call auto_revalidate_after_analysis)
python -c "
from app.tasks.code_analysis_tasks import auto_revalidate_after_analysis
auto_revalidate_after_analysis(
    repo_id=1, tenant_id=1,
    changed_component_ids=[5],
    commit_hash='abc123'
)
"

# 3. Verify mismatch auto-closed
psql -c "SELECT status, resolution_note FROM mismatches WHERE id = {id}"
# Expected: status='auto_closed', resolution_note contains 'abc123'

# 4. Test notification created
psql -c "SELECT title, body FROM notifications ORDER BY id DESC LIMIT 1"
```

### Risk Assessment
- **`countdown=30`**: Prevents validation running on mid-analysis state
- **Never deletes mismatches**: Only changes status to `auto_closed` — history preserved
- **Per-link errors don't stop batch**: try/except per link — 1 failure doesn't block 20 others
- **False positive protection**: `auto_closed` mismatches that were manually marked FP won't be re-opened (filter only `open` + `in_progress`)
- **`run_validation_for_link_preview` must be added**: This is a new non-destructive validation method that returns results without writing to DB first — implement alongside this task


---

## P5B-07 — Multi-File Coverage Matrix (BRD Rows × Code File Columns)

**Ticket ID:** P5B-07
**Priority:** P1 — Answers the manager question: "which code file covers which requirement?"
**Complexity:** Medium
**Risk:** LOW — read-only computation, new endpoint + frontend component only

### Why This Exists

When a BRD has 50 requirements and a repo has 20 files, a manager needs to see at a glance which files cover which requirements, and where the gaps are. The Coverage Matrix view shows exactly this:

```
                     payment_svc.py   auth.py   models.py   utils.py
REQ-001 API /charge     ✅ 100%        -          -           -
REQ-002 Auth required   ✅ 100%      ✅ 100%      -           -
REQ-003 Rate limit       ⚠️ 50%       -           -           -
REQ-004 DB schema        -            -         ✅ 100%       -
REQ-005 Audit log        ❌ 0%        -           -          ⚠️ 50%
```

Color code: green (≥90%), amber (50-89%), red (<50%), dash (not linked).

This is also the answer to "which files should I attach for better coverage?" — the matrix shows which requirements have no linked code file.

### Current State

No coverage matrix endpoint or view exists. Individual mismatches are shown per-document, but there is no matrix aggregation that joins `requirement_atoms → mismatches → code_components`.

### What to Change

#### Step 1: New endpoint `GET /validation/{document_id}/coverage-matrix`

**File: `backend/app/api/endpoints/validation.py`**

```python
@router.get("/{document_id}/coverage-matrix")
def get_coverage_matrix(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-07: Returns coverage matrix: atoms × code files.
    Each cell shows coverage score (0-100) and open mismatch count.

    Response:
    {
      "atoms": [{ id, atom_id, content, atom_type, criticality }],
      "components": [{ id, name, location, language }],
      "matrix": {
        "{atom_id}::{component_id}": {
          "coverage_score": 0.85,
          "open_mismatches": 1,
          "critical_mismatches": 0,
          "status": "partial"  // "covered" | "partial" | "missing" | "not_linked"
        }
      }
    }
    """
    from app.models.requirement_atom import RequirementAtom
    from app.models.code_component import CodeComponent
    from app.models.document_code_link import DocumentCodeLink

    # Load all atoms for this document
    atoms = db.query(RequirementAtom).filter(
        RequirementAtom.document_id == document_id,
        RequirementAtom.tenant_id == tenant_id,
    ).order_by(RequirementAtom.atom_id).all()

    if not atoms:
        raise HTTPException(status_code=404, detail="No atoms found. Run validation first.")

    # Load all linked code components
    links = db.query(DocumentCodeLink).filter(
        DocumentCodeLink.document_id == document_id,
        DocumentCodeLink.tenant_id == tenant_id,
    ).all()
    component_ids = [l.code_component_id for l in links]

    components = db.query(CodeComponent).filter(
        CodeComponent.id.in_(component_ids)
    ).all() if component_ids else []

    # Load all open mismatches for this document
    open_mismatches = db.query(Mismatch).filter(
        Mismatch.document_id == document_id,
        Mismatch.tenant_id == tenant_id,
        Mismatch.status.in_(["open", "in_progress"]),
        Mismatch.status != "false_positive",
    ).all()

    # Build matrix: key = "{atom_db_id}::{component_id}"
    matrix = {}

    # Initialize all cells as "not_linked"
    for atom in atoms:
        for comp in components:
            key = f"{atom.id}::{comp.id}"
            matrix[key] = {
                "coverage_score": None,
                "open_mismatches": 0,
                "critical_mismatches": 0,
                "status": "not_linked",
            }

    # Fill in mismatch counts
    for m in open_mismatches:
        if m.requirement_atom_id and m.code_component_id:
            key = f"{m.requirement_atom_id}::{m.code_component_id}"
            if key in matrix:
                matrix[key]["open_mismatches"] += 1
                if m.severity == "critical":
                    matrix[key]["critical_mismatches"] += 1

    # Determine status for each linked cell
    # A cell is "linked" if there is a DocumentCodeLink for that component
    linked_component_ids = set(component_ids)
    for atom in atoms:
        for comp in components:
            if comp.id not in linked_component_ids:
                continue
            key = f"{atom.id}::{comp.id}"
            cell = matrix[key]
            if cell["critical_mismatches"] > 0:
                cell["status"] = "missing"
                cell["coverage_score"] = 0.0
            elif cell["open_mismatches"] > 0:
                cell["status"] = "partial"
                cell["coverage_score"] = 0.5
            else:
                cell["status"] = "covered"
                cell["coverage_score"] = 1.0

    return {
        "document_id": document_id,
        "atoms": [
            {
                "id": a.id,
                "atom_id": a.atom_id,
                "content": a.content[:150],  # Truncate for matrix display
                "atom_type": a.atom_type,
                "criticality": a.criticality,
            }
            for a in atoms
        ],
        "components": [
            {
                "id": c.id,
                "name": c.name or c.location.split("/")[-1],
                "location": c.location,
                "language": c.language,
            }
            for c in components
        ],
        "matrix": matrix,
        "summary": {
            "total_atoms": len(atoms),
            "total_components": len(components),
            "covered_cells": sum(1 for v in matrix.values() if v["status"] == "covered"),
            "partial_cells": sum(1 for v in matrix.values() if v["status"] == "partial"),
            "missing_cells": sum(1 for v in matrix.values() if v["status"] == "missing"),
            "atoms_with_no_coverage": _count_uncovered_atoms(atoms, matrix),
        }
    }


def _count_uncovered_atoms(atoms, matrix) -> int:
    """Count atoms that have no 'covered' cell across any component."""
    count = 0
    for atom in atoms:
        has_coverage = any(
            matrix.get(f"{atom.id}::{k.split('::')[1]}", {}).get("status") == "covered"
            for k in matrix if k.startswith(f"{atom.id}::")
        )
        if not has_coverage:
            count += 1
    return count
```

#### Step 2: Frontend — Coverage Matrix Component

**New file: `frontend/components/validation/CoverageMatrix.tsx`**

```tsx
interface CoverageMatrixProps {
  documentId: number
}

export function CoverageMatrix({ documentId }: CoverageMatrixProps) {
  const [data, setData] = useState<MatrixData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/v1/validation/${documentId}/coverage-matrix`, { headers: authHeaders })
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [documentId])

  if (loading) return <Skeleton className="h-64" />
  if (!data) return null

  const getCellColor = (status: string) => {
    switch (status) {
      case 'covered':     return 'bg-green-100 text-green-800'
      case 'partial':     return 'bg-amber-100 text-amber-800'
      case 'missing':     return 'bg-red-100 text-red-800'
      case 'not_linked':  return 'bg-gray-50 text-gray-300'
      default:            return 'bg-gray-50'
    }
  }

  const getCellIcon = (status: string, cell: any) => {
    if (status === 'covered')    return '✅'
    if (status === 'partial')    return `⚠️ ${cell.open_mismatches}`
    if (status === 'missing')    return `❌ ${cell.critical_mismatches}`
    return '—'
  }

  return (
    <div className="overflow-x-auto">
      {/* Summary bar */}
      <div className="flex gap-4 mb-3 text-xs text-gray-500">
        <span>✅ {data.summary.covered_cells} covered</span>
        <span>⚠️ {data.summary.partial_cells} partial</span>
        <span>❌ {data.summary.missing_cells} missing</span>
        {data.summary.atoms_with_no_coverage > 0 && (
          <span className="text-amber-600 font-medium">
            ⚠ {data.summary.atoms_with_no_coverage} requirements have no linked code file
          </span>
        )}
      </div>

      <table className="text-xs border-collapse w-full">
        <thead>
          <tr>
            <th className="text-left p-2 border bg-gray-50 sticky left-0 z-10 min-w-[200px]">
              Requirement
            </th>
            {data.components.map(comp => (
              <th key={comp.id} className="p-2 border bg-gray-50 text-center max-w-[120px]">
                <div className="truncate" title={comp.location}>
                  {comp.name}
                </div>
                <div className="text-gray-400 font-normal truncate text-[10px]">
                  {comp.language}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.atoms.map(atom => (
            <tr key={atom.id} className="hover:bg-gray-50">
              <td className="p-2 border sticky left-0 bg-white max-w-[200px]">
                <div className="flex items-start gap-1">
                  <span className="text-gray-400 flex-shrink-0">{atom.atom_id}</span>
                  <span
                    className="truncate"
                    title={atom.content}
                  >
                    {atom.content}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {atom.atom_type.replace(/_/g, ' ')}
                  {atom.criticality === 'critical' && (
                    <span className="ml-1 text-red-500">• critical</span>
                  )}
                </div>
              </td>
              {data.components.map(comp => {
                const key = `${atom.id}::${comp.id}`
                const cell = data.matrix[key] || { status: 'not_linked' }
                return (
                  <td
                    key={comp.id}
                    className={`p-2 border text-center ${getCellColor(cell.status)}`}
                  >
                    {getCellIcon(cell.status, cell)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

#### Step 3: Add Coverage Matrix tab to validation panel

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add "Coverage Matrix" tab alongside the existing "Mismatches" tab:

```tsx
<TabGroup>
  <Tab active={view === 'mismatches'} onClick={() => setView('mismatches')}>
    Mismatches ({mismatchCount})
  </Tab>
  <Tab active={view === 'matrix'} onClick={() => setView('matrix')}>
    Coverage Matrix
  </Tab>
</TabGroup>

{view === 'matrix' && <CoverageMatrix documentId={documentId} />}
```

### Test Commands

```bash
# 1. Run validation on a document with multiple code components linked
# 2. Fetch matrix
curl /api/v1/validation/{document_id}/coverage-matrix
# Expected: atoms array, components array, matrix dict

# 3. Verify summary counts
# covered + partial + missing should equal total linked cells
# atoms_with_no_coverage should equal atoms that appear in no "covered" cell

# 4. Create a mismatch for atom 1 / component 2
# Re-fetch matrix → cell status should be "partial" or "missing"
```

### Risk Assessment
- **No writes** — pure read aggregation
- **Empty state** — 404 with clear message if no atoms (run validation first)
- **Performance** — 3 DB queries (atoms + components + mismatches) + in-memory join. Fast for typical BRD sizes (50-100 atoms × 10-20 files)
- **Matrix size limit** — for very large BRDs (500+ atoms), add `?limit=50&offset=0` pagination to atoms


---

## P5B-08 — Regulatory Compliance Tagging (RBI, PCI-DSS, HIPAA, GDPR)

**Ticket ID:** P5B-08
**Priority:** P1 — Enterprise clients in regulated industries (banking, healthcare) need to know WHICH mismatches are regulatory violations vs mere implementation gaps.
**Complexity:** Medium
**Risk:** LOW — additive fields on atoms and mismatches; no existing logic changed

### Why This Exists

A bank using DokyDoc has two types of mismatches:
1. "Pagination missing on /users list" — developer preference, can wait
2. "AES-256 encryption not applied to PII fields" — RBI mandate, must fix before audit

Without regulatory tagging, both look the same in the mismatch list. Auditors and compliance officers need to filter and report on the second type separately.

After P5B-08:
- SECURITY_REQUIREMENT atoms in a fintech BRD get tagged with `regulatory_frameworks: ["RBI", "PCI-DSS"]`
- Mismatches for these atoms get `severity="compliance_risk"` (new severity level)
- Compliance officer can filter: "Show only COMPLIANCE_RISK mismatches"
- Compliance score shows a separate "Regulatory Score" breakdown

The regulatory mapping uses the `tenant.settings.regulatory_context` set during onboarding (Phase 5 P5-04) and the `industry_context.json` library (Phase 5 P5-02).

### Current State

**File: `backend/app/models/requirement_atom.py`**
No `regulatory_tags` field. Atoms have `criticality` (critical/standard/informational) but no regulatory linkage.

**File: `backend/app/models/mismatch.py` (line 29)**
`severity: Mapped[str] = mapped_column(String, index=True, nullable=False)`
Valid values: "critical", "high", "medium", "low", "info" — no "compliance_risk" severity.

**File: `backend/app/services/ai/gemini.py` (line 562-590)**
Atomization prompt assigns `atom_type` but has no awareness of regulatory frameworks.

### What to Change

#### Step 1: Add `regulatory_tags` to RequirementAtom model

**File: `backend/app/models/requirement_atom.py`**

Add after `criticality` field:

```python
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy import String as SAString

    # P5B-08: regulatory framework tags for this requirement
    # e.g. ["PCI-DSS", "RBI", "GDPR"] — set during atomization based on tenant industry
    regulatory_tags: Mapped[Optional[list]] = mapped_column(
        ARRAY(SAString), nullable=True
    )
```

**New migration file: `backend/alembic/versions/s16c1_atom_regulatory_tags.py`**

```python
"""
P5B-08: Add regulatory_tags to requirement_atoms, compliance_risk severity to mismatches.

Revision ID: s16c1
Revises: s16b1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = 's16c1'
down_revision = 's16b1'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('requirement_atoms',
        sa.Column('regulatory_tags', ARRAY(sa.String()), nullable=True))

    # Index for fast regulatory tag queries (e.g. "all PCI-DSS atoms")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
        idx_requirement_atoms_regulatory_tags
        ON requirement_atoms USING GIN (regulatory_tags)
    """)

def downgrade():
    op.drop_index('idx_requirement_atoms_regulatory_tags')
    op.drop_column('requirement_atoms', 'regulatory_tags')
```

#### Step 2: Regulatory tag assignment in atomization prompt

**File: `backend/app/services/ai/gemini.py`**

In `call_gemini_for_atomization` method, inject tenant regulatory context into the prompt. Find the prompt assembly section (around line 556-595) and add:

```python
# BEFORE (current prompt excerpt around line 566):
"""
For each extracted requirement, return JSON with:
- atom_id: "REQ-001", "REQ-002" ...
- atom_type: one of [API_CONTRACT, BUSINESS_RULE, ...]
- content: exact original sentence
- criticality: "critical" | "standard" | "informational"
"""

# AFTER — add regulatory_tags field to output schema:
"""
For each extracted requirement, return JSON with:
- atom_id: "REQ-001", "REQ-002" ...
- atom_type: one of [API_CONTRACT, BUSINESS_RULE, ...]
- content: exact original sentence
- criticality: "critical" | "standard" | "informational"
- regulatory_tags: list of regulatory frameworks this requirement addresses.
  Use ONLY frameworks relevant to the current context: {regulatory_context_placeholder}
  Examples: ["PCI-DSS"] for payment card data, ["HIPAA"] for PHI, ["GDPR"] for EU personal data,
            ["RBI"] for Reserve Bank of India requirements, ["SOX"] for financial controls.
  Leave empty [] if no regulatory framework is clearly applicable.
"""
```

Pass the tenant's regulatory context into the prompt by updating `call_gemini_for_atomization` to accept a `regulatory_context` parameter:

```python
async def call_gemini_for_atomization(
    self,
    document_text: str,
    tenant_id: int = None,
    user_id: int = None,
    regulatory_context: list[str] | None = None,  # P5B-08: new param
) -> list:
    """..."""
    regulatory_hint = ""
    if regulatory_context:
        frameworks = ", ".join(regulatory_context)
        regulatory_hint = (
            f"\nThis document is from a {frameworks}-regulated industry. "
            f"Tag atoms that directly address {frameworks} compliance requirements "
            f"with the appropriate framework name(s) in the regulatory_tags field."
        )

    # Inject into prompt before the JSON schema section:
    prompt = f"""...(existing prompt start)...
{regulatory_hint}

For each extracted requirement, return JSON:
...(rest of schema)...
- regulatory_tags: [...]
"""
```

#### Step 3: Store `regulatory_tags` in `create_atoms_bulk`

**File: `backend/app/crud/crud_requirement_atom.py`**

In `create_atoms_bulk`, add `regulatory_tags` to the `RequirementAtom` constructor:

```python
# In the db_obj creation inside create_atoms_bulk:
db_obj = RequirementAtom(
    ...
    regulatory_tags=atom.get("regulatory_tags") or [],
    ...
)
```

#### Step 4: Validate `compliance_risk` severity on mismatch creation

**File: `backend/app/services/validation_service.py`**

When a mismatch is being created for an atom that has `regulatory_tags`, auto-upgrade severity to `compliance_risk` if it would be "high" or "critical":

```python
# In the mismatch creation section, after resolving db_atom_id:
# P5B-08: Check if atom has regulatory tags — upgrade severity
atom_obj = next((a for a in atoms if a.atom_id == m.get("atom_local_id", "")), None)
regulatory_tags = getattr(atom_obj, 'regulatory_tags', None) or []
if regulatory_tags and m.get("severity") in ("critical", "high"):
    m["severity"] = "compliance_risk"
    m_details = m.get("details") or {}
    m_details["regulatory_frameworks"] = regulatory_tags
    m["details"] = m_details
```

#### Step 5: New endpoint for regulatory compliance summary

**File: `backend/app/api/endpoints/validation.py`**

```python
@router.get("/{document_id}/regulatory-summary")
def get_regulatory_summary(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-08: Returns compliance status broken down by regulatory framework.
    Shows which frameworks have open violations vs are fully covered.

    Response:
    {
      "frameworks": {
        "PCI-DSS": {
          "total_atoms": 8,
          "covered": 6,
          "open_violations": 2,
          "score": 0.75
        },
        "RBI": { ... }
      },
      "overall_regulatory_score": 0.82,
      "compliance_risk_mismatches": 3
    }
    """
    from app.models.requirement_atom import RequirementAtom
    from sqlalchemy import text

    # Get all atoms with their regulatory tags
    atoms = db.query(RequirementAtom).filter(
        RequirementAtom.document_id == document_id,
        RequirementAtom.tenant_id == tenant_id,
        RequirementAtom.regulatory_tags.isnot(None),
    ).all()

    # Get compliance_risk mismatches for this document
    compliance_mismatches = db.query(Mismatch).filter(
        Mismatch.document_id == document_id,
        Mismatch.tenant_id == tenant_id,
        Mismatch.severity == "compliance_risk",
        Mismatch.status.in_(["open", "in_progress"]),
    ).all()

    # Build per-framework stats
    frameworks: dict[str, dict] = {}
    violated_atom_ids: set[int] = {
        m.requirement_atom_id for m in compliance_mismatches
        if m.requirement_atom_id
    }

    for atom in atoms:
        for framework in (atom.regulatory_tags or []):
            if framework not in frameworks:
                frameworks[framework] = {"total_atoms": 0, "covered": 0, "open_violations": 0}
            frameworks[framework]["total_atoms"] += 1
            if atom.id in violated_atom_ids:
                frameworks[framework]["open_violations"] += 1
            else:
                frameworks[framework]["covered"] += 1

    for fw, stats in frameworks.items():
        total = stats["total_atoms"]
        stats["score"] = round(stats["covered"] / total, 4) if total else 1.0

    overall = (
        sum(s["score"] for s in frameworks.values()) / len(frameworks)
        if frameworks else None
    )

    return {
        "document_id": document_id,
        "frameworks": frameworks,
        "overall_regulatory_score": round(overall, 4) if overall else None,
        "compliance_risk_mismatches": len(compliance_mismatches),
    }
```

#### Step 6: Frontend — Compliance Risk severity badge

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add "COMPLIANCE RISK" severity badge (distinct red-orange color):

```tsx
const SeverityBadge = ({ severity }: { severity: string }) => {
  const styles = {
    compliance_risk: 'bg-red-700 text-white border-red-800',  // NEW
    critical:        'bg-red-100 text-red-800 border-red-200',
    high:            'bg-orange-100 text-orange-800 border-orange-200',
    medium:          'bg-yellow-100 text-yellow-800 border-yellow-200',
    low:             'bg-blue-100 text-blue-800 border-blue-200',
    info:            'bg-gray-100 text-gray-600 border-gray-200',
  }
  const labels = {
    compliance_risk: '⚖ COMPLIANCE RISK',  // NEW
    critical: 'Critical',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    info: 'Info',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${styles[severity] || styles.info}`}>
      {labels[severity] || severity}
    </span>
  )
}
```

Also add regulatory tags display on mismatch card:
```tsx
{mismatch.details?.regulatory_frameworks?.length > 0 && (
  <div className="flex gap-1 mt-1">
    {mismatch.details.regulatory_frameworks.map((fw: string) => (
      <span key={fw} className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded border border-purple-200">
        {fw}
      </span>
    ))}
  </div>
)}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16c1

# 2. Verify column added
psql -c "\d requirement_atoms" | grep regulatory_tags

# 3. Upload a fintech BRD, run atomization with PCI-DSS context
# Check atoms have regulatory_tags
psql -c "SELECT atom_id, regulatory_tags FROM requirement_atoms WHERE document_id = X AND regulatory_tags IS NOT NULL"

# 4. Run validation — check mismatches for tagged atoms have compliance_risk severity
psql -c "SELECT severity, COUNT(*) FROM mismatches WHERE document_id = X GROUP BY severity"

# 5. Get regulatory summary
curl /api/v1/validation/{document_id}/regulatory-summary
# Expected: { "frameworks": { "PCI-DSS": { "score": 0.75, ... } } }
```

### Risk Assessment
- **Empty `regulatory_tags`** — defaults to `[]`, not null. GIN index handles empty arrays fine.
- **`compliance_risk` severity** — new value in string column, doesn't break existing queries
- **Only applies to atoms WITH regulatory_tags** — atoms without tags are unaffected, severity unchanged
- **No-op without Phase 5 industry detection** — if `tenant.settings.regulatory_context` is empty, `regulatory_context=[]` is passed to prompt → `regulatory_tags=[]` for all atoms → no change in behavior


---

## P5B-09 — Strengthen Per-Atom-Type Validation Prompt Instructions

**Ticket ID:** P5B-09
**Priority:** P0 — The quality of validation output is 80% determined by prompt quality. Current instructions are 1-2 sentences. They need to be 8-12 specific checks per type.
**Complexity:** Low (prompt engineering only, no DB changes)
**Risk:** LOW — only `_ATOM_TYPE_INSTRUCTIONS` dict in `gemini.py` changes; all other code untouched

### Why This Exists

Current instruction for NFR atoms (1 line):
```
"Non-functional requirements: check whether performance/scalability constraints are reflected
(pagination, caching, async, timeouts, retry). Flag: no pagination on list endpoints..."
```

This misses: rate limits (RPM/RPS numbers), SLA uptime targets, exact response time thresholds, database query time limits, concurrent user handling, etc.

A BRD saying "API must handle 1000 concurrent users" — the current prompt can't check this because it doesn't know to look in `structured_analysis.performance_notes` or check for async patterns, thread pool sizes, or load balancing config in `structured_analysis.architecture_notes`.

After P5B-09, each atom type instruction is 8-12 specific checks, grounded in what `structured_analysis` actually contains.

### Current State

**File: `backend/app/services/ai/gemini.py` (line 630-672)**

`_ATOM_TYPE_INSTRUCTIONS` dict — 9 entries, each 1-3 sentences.

### What to Change

**File: `backend/app/services/ai/gemini.py`**

Replace `_ATOM_TYPE_INSTRUCTIONS` dict completely:

```python
# BEFORE (line 630):
_ATOM_TYPE_INSTRUCTIONS = {
    "API_CONTRACT": (
        "API CONTRACTS: For each atom, check whether the code implements the specified "
        "HTTP endpoint with the correct method, path, authentication requirement, request "
        "parameters, and response shape. Flag: missing endpoints, wrong HTTP method, missing "
        "auth enforcement, wrong response structure, incorrect status codes."
    ),
    # ... 8 more single-paragraph entries
}

# AFTER — replace with expanded instructions:
_ATOM_TYPE_INSTRUCTIONS = {
    "API_CONTRACT": """API CONTRACTS — Check ALL of the following for each atom:
1. ENDPOINT EXISTS: Is the specified HTTP method + path present in api_contracts[]?
2. AUTH ENFORCEMENT: Does the endpoint require the stated authentication (bearer, API key, OAuth)?
   Check auth_patterns[] and api_contracts[].auth field.
3. REQUEST PARAMETERS: Are all required query params / path params / request body fields present?
   Check api_contracts[].parameters and data_models[].
4. RESPONSE SHAPE: Does the response schema match the BRD's specified fields and types?
   Check api_contracts[].response_schema.
5. HTTP STATUS CODES: Are the BRD-specified status codes (200, 201, 400, 404, 429, 500) returned?
   Check error_handling[] for 4xx/5xx patterns.
6. RATE LIMITING: If BRD specifies a rate limit (e.g. "30 req/min"), is a rate limiter
   applied to this endpoint? Check dependencies[] for ratelimit/slowapi/throttle libraries.
7. PAGINATION: If endpoint returns a collection and BRD specifies page size or cursor,
   is pagination implemented? Check api_contracts[].response_schema for page/cursor fields.
8. IDEMPOTENCY: If BRD requires idempotency keys (especially for payments/mutations),
   is the idempotency-key header handled?
Flag mismatches with: missing endpoint, wrong method, missing auth, missing param, wrong response type, no rate limit, no pagination, no idempotency.""",

    "BUSINESS_RULE": """BUSINESS RULES — Check ALL of the following for each atom:
1. CONDITION LOGIC: Is the stated condition (IF x THEN y, when A and B, only if C) coded?
   Look in business_logic[], validation_rules[], functions[].
2. THRESHOLD VALUES: Are exact thresholds (max 5 retries, minimum $10, age >= 18) present
   as constants or configuration? Check functions[].body_summary and validation_rules[].
3. CALCULATION FORMULA: If BRD specifies a formula (interest = principal × rate / 100),
   is it implemented exactly? Wrong formula = critical mismatch.
4. ELIGIBILITY CRITERIA: Are all eligibility conditions checked (e.g. KYC verified,
   account active, not blacklisted)? Check functions[] and external_calls[].
5. MUTUALLY EXCLUSIVE CONDITIONS: If BRD says conditions are mutually exclusive,
   is there an else/elif branch handling all cases?
6. DEFAULT BEHAVIOR: If BRD specifies default values (default currency = USD, default
   timeout = 30s), are they set as constants/defaults in the code?
7. EDGE CASES: Does code handle boundary values (e.g. amount = 0, list is empty,
   null input)? Look for None/null/empty checks in functions[].
8. AUDIT REQUIREMENT: If business rule must be logged for audit, is there a log/event
   write in the code path?
Flag: missing condition branch, wrong threshold, incorrect formula, missing eligibility check,
missing default, unhandled edge case, missing audit log.""",

    "FUNCTIONAL_REQUIREMENT": """FUNCTIONAL REQUIREMENTS — Check ALL of the following:
1. FEATURE EXISTS: Is the stated capability present in responsibilities[] or functions[]?
   A function named or described matching the requirement.
2. COMPLETE IMPLEMENTATION: Does the function do everything the BRD says,
   not just return a stub or placeholder?
3. TRIGGER/ENTRY POINT: Is the feature accessible from the correct entry point
   (API endpoint, event handler, scheduled job)?
4. DATA PERSISTENCE: If the BRD requirement involves saving data, is there a DB write
   in the code path? Check data_flows[] for storage step.
5. RETURN VALUE: Does the feature return the specified output (confirmation ID, 
   updated record, boolean, etc.)?
6. SIDE EFFECTS: If the BRD specifies side effects (send email, update cache, 
   emit event), are all side effects present in component_interactions[] or external_calls[]?
7. ROLE/PERMISSION: Is the feature accessible only to the stated user roles?
   Check auth_patterns[] and dependencies[].
8. CONFIGURATION: If BRD says feature is configurable (e.g. feature flag, env var),
   is it configured via settings/env, not hardcoded?
Flag: feature entirely missing, partial implementation (stub/TODO), wrong trigger,
missing DB write, missing side effect, wrong access control.""",

    "DATA_CONSTRAINT": """DATA CONSTRAINTS — Check ALL of the following:
1. FIELD EXISTS: Is the specified field present in data_models[] with correct name?
2. DATA TYPE: Is the field type correct (String vs Integer, DateTime vs Date)?
   Type mismatch = critical mismatch.
3. REQUIRED/NULLABLE: If BRD says field is required (non-null), is nullable=False set?
4. LENGTH LIMIT: If BRD specifies max/min length (max 255 chars, min 8 chars),
   is the constraint enforced in validation_rules[] or Pydantic schema?
5. RANGE CONSTRAINT: If BRD specifies numeric range (0-100, positive only),
   is it enforced as a validator?
6. REGEX PATTERN: If BRD specifies format (email, phone, UUID, ISO date),
   is regex validation applied?
7. UNIQUENESS: If BRD says field must be unique, is there a DB unique constraint?
   Check data_models[].constraints or migration for UniqueConstraint.
8. FOREIGN KEY RELATIONSHIP: If BRD specifies that a field references another entity,
   is a FK constraint present?
9. DEFAULT VALUE: If BRD specifies a default, is it set at DB level (server_default)
   or application level?
Flag: missing field, wrong type, missing null check, missing length limit,
missing range check, missing regex, missing unique constraint.""",

    "WORKFLOW_STEP": """WORKFLOW STEPS — Check ALL of the following:
1. ALL STEPS PRESENT: Are all specified steps in the BRD sequence present as
   discrete operations in data_flows[] or functions[]?
2. CORRECT ORDER: Do the steps occur in the BRD-specified sequence?
   Check data_flows[] order — any step out of order is a mismatch.
3. STEP TRIGGERS: Does each step trigger the next step correctly
   (not skipping or short-circuiting)?
4. ROLLBACK/COMPENSATION: If any step fails, is there a rollback of prior steps?
   Check error_handling[] for compensation transactions.
5. STATE TRANSITIONS: If workflow involves state changes (pending → active → closed),
   are all transitions present and guarded by precondition checks?
6. BLOCKING GATES: If workflow requires approval/review before proceeding,
   is there a gate check in the code?
7. TIMEOUT HANDLING: If BRD specifies step timeout (payment must complete in 30s),
   is there a timeout enforced?
8. CONCURRENT STEP SAFETY: If BRD says steps should not run concurrently for the
   same entity, is there a lock/mutex?
Flag: missing step, wrong order, no rollback on step N failure, missing state guard,
missing approval gate, no timeout.""",

    "ERROR_SCENARIO": """ERROR SCENARIOS — Check ALL of the following:
1. ERROR CASE HANDLED: Is the specific error condition (invalid input, timeout, 
   auth failure, not found) handled with a try/except or conditional?
   Check error_handling[] and functions[].
2. HTTP STATUS CODE: Does the error return the BRD-specified HTTP status code?
   (400 for validation, 401 for auth, 404 for not found, 422 for schema error,
   429 for rate limit, 500 for internal)
3. ERROR MESSAGE FORMAT: Is the error response in the BRD-specified format?
   (e.g. { "error": "...", "code": "...", "detail": "..." })
4. ERROR LOGGING: Is the error logged at the appropriate level (ERROR for 5xx,
   WARNING for 4xx)? Check functions[] for logger usage.
5. USER-FACING MESSAGE: Is the error message safe (no stack traces, no internal paths,
   no DB schema exposure in 5xx responses)?
6. RETRY HINT: If BRD says clients should retry on timeout, is Retry-After header
   or retry indication included in the error response?
7. PARTIAL FAILURE: If BRD specifies partial failure handling (batch operations where
   some items fail), is the partial success/failure response format implemented?
8. CIRCUIT BREAKER: If BRD specifies that external service failures should not cascade,
   is there a circuit breaker pattern in external_calls[]?
Flag: unhandled error case, wrong status code, wrong message format,
missing log, unsafe error message, missing retry hint.""",

    "SECURITY_REQUIREMENT": """SECURITY REQUIREMENTS — Check ALL of the following:
1. AUTHENTICATION: Is the stated auth mechanism implemented?
   (JWT: check auth_patterns[] for bearer/JWT; API key: check header validation;
   OAuth: check OAuth flow in external_calls[])
2. AUTHORIZATION/RBAC: Is the stated role/permission check present?
   Check auth_patterns[] for permission decorators/middleware.
3. INPUT SANITIZATION: If BRD specifies that input must be sanitized (SQL injection,
   XSS, command injection), is sanitization applied before DB/shell use?
4. DATA ENCRYPTION: If BRD requires encrypted storage (PII, PCI data),
   is encryption applied at application layer (field encryption) or DB layer?
   Check dependencies[] for encryption libraries.
5. SENSITIVE DATA MASKING: Are sensitive fields (password, card number, SSN) masked
   in logs and API responses? Check functions[] for masking logic.
6. SECURE COMMUNICATION: Are external calls using HTTPS only?
   Check external_calls[] for protocol.
7. CORS POLICY: If BRD specifies CORS restrictions, is CORS properly configured?
   Check dependencies[] and configuration notes.
8. SESSION MANAGEMENT: If BRD specifies session timeout or invalidation,
   is it implemented?
9. AUDIT LOGGING: If BRD requires audit trail for this operation, is there an
   audit log write in the code path?
Flag: missing auth, missing permission check, missing input sanitization,
missing encryption, data exposure in logs, HTTP instead of HTTPS, missing audit log.""",

    "NFR": """NON-FUNCTIONAL REQUIREMENTS — Check ALL of the following:
1. RESPONSE TIME: If BRD specifies max response time (< 200ms, < 2s),
   is there async processing, caching, or DB indexing to achieve it?
   Check caching_patterns[], async_patterns[].
2. THROUGHPUT/RATE LIMIT: If BRD specifies requests-per-minute or requests-per-second,
   is a rate limiter configured at the correct level (per user, per IP, global)?
3. PAGINATION: If BRD specifies max page size or cursor-based pagination,
   is it implemented with correct default and max limits?
4. CACHING: If BRD specifies that responses should be cached (TTL, cache-control),
   is caching implemented? Check caching_patterns[] and dependencies[].
5. DATABASE QUERY OPTIMIZATION: If BRD specifies query time limits, are indexes
   present for the queried fields? Check data_models[].indexes.
6. CONCURRENT USERS: If BRD specifies concurrent user capacity (handle 1000 simultaneous),
   is there connection pooling, async I/O, or horizontal scaling support?
7. RETRY POLICY: If BRD requires retry on transient failure (external API call),
   is exponential backoff implemented? Check external_calls[] for retry config.
8. GRACEFUL DEGRADATION: If BRD specifies that service must remain partially available
   under load, is there a fallback or circuit breaker?
9. MEMORY/RESOURCE LIMITS: If BRD specifies memory limits or file size limits,
   are they enforced (streaming large files, not loading full dataset into memory)?
10. MONITORING/ALERTING: If BRD specifies SLA monitoring, are metrics emitted?
    Check dependencies[] for prometheus/datadog/metrics libraries.
Flag: no async on slow operation, no rate limiter, no pagination, no cache,
no index for slow query, no retry policy, no resource limit enforcement.""",

    "INTEGRATION_POINT": """INTEGRATION POINTS — Check ALL of the following:
1. CALL EXISTS: Is the external service call present in external_calls[] or
   component_interactions[]? Matching service name/URL.
2. CORRECT TRIGGER: Does the integration fire at the BRD-specified trigger
   (on user registration, after payment, on schedule)?
   Check which function contains the call.
3. REQUEST FORMAT: Are the required fields sent to the external service?
   (e.g. Stripe requires amount, currency, customer_id)
4. RESPONSE HANDLING: Is the external service response parsed and acted upon?
   Check for response.json(), response.status_code checks.
5. FAILURE HANDLING: Is there a try/except around the external call?
   What happens if the service is unavailable? (Dead letter queue? Alert? Fallback?)
6. RETRY LOGIC: For critical integrations (payment processing, email), is there
   retry with exponential backoff?
7. TIMEOUT: Is there a timeout on the external call?
   (Hanging calls without timeout will exhaust thread pool)
8. IDEMPOTENCY: For payment or other financial integrations, is idempotency key
   sent to prevent duplicate transactions on retry?
9. WEBHOOK RECEIVER: If BRD specifies receiving webhooks from external service,
   is there a webhook endpoint and signature verification?
10. CREDENTIAL ROTATION: Are credentials stored as env vars/secrets (not hardcoded)?
    Check dependencies[] for secrets management.
Flag: missing call, wrong trigger timing, missing required fields, no failure handling,
no retry, no timeout, missing idempotency key, no signature verification.""",
}
```

### Test Commands

```bash
# No migration needed. Test by running validation:

# 1. Create a BRD with specific NFR: "API must handle 1000 concurrent users"
# 2. Link to a code component with no async patterns in structured_analysis
# 3. Run validation
# Expected: mismatch "NFR: no async/connection pooling for concurrency requirement"

# 2. Test API_CONTRACT rate limit detection:
# BRD: "POST /payments limited to 30 requests/minute"
# Code: no ratelimit dependency in structured_analysis
# Expected: mismatch "API_CONTRACT: rate limit not enforced"

# 3. Test SECURITY_REQUIREMENT audit log detection:
# BRD: "all fund transfers must be audit logged"
# Code: no audit log write in functions[]
# Expected: mismatch "SECURITY_REQUIREMENT: audit log missing for transfer operation"

# Verify prompt structure is correct:
python3 -c "
from app.services.ai.gemini import GeminiService
gs = GeminiService.__new__(GeminiService)
print(gs._ATOM_TYPE_INSTRUCTIONS['NFR'][:200])
"
```

### Risk Assessment
- **Zero DB changes** — prompt-only change
- **No existing logic changed** — `_ATOM_TYPE_INSTRUCTIONS` is used only as text injection into prompts
- **More specific instructions → more mismatches found** — this is the intended effect; brief regression testing recommended to ensure no false positives spike
- **Token cost increases slightly** — instructions are ~4× longer; adds ~500 tokens per validation call (~$0.0001 per call at Gemini Flash pricing). Negligible.


---

## P5B-10 — Mismatch Status Lifecycle (OPEN → IN_PROGRESS → RESOLVED → VERIFIED)

**Ticket ID:** P5B-10
**Priority:** P0 — Enterprise teams need workflow states beyond "open"/"resolved" to manage mismatch triage.
**Complexity:** Low-Medium
**Risk:** LOW — existing rows keep their current status; only new transitions added

### Why This Exists

Current mismatch statuses: `"new"` (only real state). This fails for team workflows:
- Developer acknowledges a mismatch but hasn't fixed it yet → needs `in_progress`
- Developer fixes it and marks resolved → needs `resolved`
- BA confirms the fix passes UAT → needs `verified`
- Mismatch turns out to be wrong AI output → needs `false_positive` (P5B-04)
- Code push auto-closes it → needs `auto_closed` (P5B-06)
- BA disputes a false positive decision → needs `disputed` (P5B-04)

Without proper lifecycle states, teams can't track velocity (how fast are mismatches being fixed?) or compliance (which mismatches have been verified by a human?).

### Valid Status Transitions

```
new → open                    (on creation — migrate "new" → "open")
open → in_progress            (developer acknowledges and starts work)
open → false_positive         (marked FP with reason — P5B-04)
open → auto_closed            (auto-closed by re-validation — P5B-06)
in_progress → resolved        (developer marks as fixed)
in_progress → false_positive  (realized it was a false positive mid-work)
resolved → verified           (BA confirms fix passes UAT)
resolved → open               (BA re-opens — fix didn't actually work)
verified → open               (regression discovered — extremely rare)
false_positive → disputed     (BA disputes FP decision — P5B-04)
disputed → open               (dispute upheld — mismatch is real)
disputed → false_positive     (dispute rejected — still FP)
auto_closed → open            (regression on later push — P5B-06)
```

### Current State

**File: `backend/app/models/mismatch.py` (line 30)**
`status: Mapped[str] = mapped_column(String, default="new", index=True, nullable=False)`

**File: `backend/app/crud/crud_mismatch.py`**
No `update_status` method exists.

**File: `backend/app/api/endpoints/validation.py`**
No PUT/PATCH endpoint for updating mismatch status.

### What to Change

#### Step 1: New Alembic migration — add CHECK constraint + default rename

**New file: `backend/alembic/versions/s16d1_mismatch_lifecycle.py`**

```python
"""
P5B-10: Add full mismatch status lifecycle with CHECK constraint.
Migrates existing "new" → "open" status.

Revision ID: s16d1
Revises: s16c1
"""
from alembic import op
import sqlalchemy as sa

revision = 's16d1'
down_revision = 's16c1'
branch_labels = None
depends_on = None

VALID_STATUSES = (
    'open', 'in_progress', 'resolved', 'verified',
    'false_positive', 'auto_closed', 'disputed'
)

def upgrade():
    # Migrate "new" → "open" (P5B-10: "new" is not a meaningful lifecycle state)
    op.execute("UPDATE mismatches SET status = 'open' WHERE status = 'new'")

    # Add CHECK constraint for valid statuses
    op.create_check_constraint(
        'ck_mismatches_valid_status',
        'mismatches',
        "status IN ('open', 'in_progress', 'resolved', 'verified', "
        "'false_positive', 'auto_closed', 'disputed')"
    )

    # Update default to 'open'
    op.alter_column('mismatches', 'status', server_default='open')

def downgrade():
    op.drop_constraint('ck_mismatches_valid_status', 'mismatches')
    op.alter_column('mismatches', 'status', server_default='new')
    op.execute("UPDATE mismatches SET status = 'new' WHERE status = 'open'")
```

#### Step 2: Add `update_status` to CRUDMismatch

**File: `backend/app/crud/crud_mismatch.py`**

```python
# Valid transitions map: current_status → allowed next statuses
VALID_TRANSITIONS = {
    "open":          {"in_progress", "false_positive", "auto_closed", "resolved"},
    "in_progress":   {"resolved", "false_positive", "open"},
    "resolved":      {"verified", "open"},
    "verified":      {"open"},
    "false_positive": {"disputed"},
    "disputed":      {"open", "false_positive"},
    "auto_closed":   {"open"},
}

def update_status(
    self,
    db: Session,
    *,
    mismatch_id: int,
    tenant_id: int,
    new_status: str,
    changed_by_user_id: int,
    note: Optional[str] = None,
) -> "Mismatch":
    """
    P5B-10: Update mismatch status with lifecycle validation.
    Raises ValueError if transition is invalid.
    """
    mismatch = self.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise ValueError(f"Mismatch {mismatch_id} not found")

    current = mismatch.status
    allowed = VALID_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {current} → {new_status}. "
            f"Allowed from '{current}': {sorted(allowed)}"
        )

    from datetime import datetime
    mismatch.status = new_status
    mismatch.status_changed_by_id = changed_by_user_id
    mismatch.status_changed_at = datetime.now()
    if note:
        mismatch.resolution_note = note
    db.commit()
    db.refresh(mismatch)
    return mismatch
```

#### Step 3: New endpoint `PATCH /validation/mismatches/{id}/status`

**File: `backend/app/api/endpoints/validation.py`**

```python
class MismatchStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

    @validator('status')
    def validate_status(cls, v):
        valid = {'open', 'in_progress', 'resolved', 'verified',
                 'false_positive', 'auto_closed', 'disputed'}
        if v not in valid:
            raise ValueError(f"status must be one of: {sorted(valid)}")
        return v


@router.patch("/mismatches/{mismatch_id}/status")
def update_mismatch_status(
    mismatch_id: int,
    body: MismatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-10: Update mismatch lifecycle status with transition validation.
    Returns the updated mismatch.
    """
    try:
        mismatch = crud.mismatch.update_status(
            db=db,
            mismatch_id=mismatch_id,
            tenant_id=tenant_id,
            new_status=body.status,
            changed_by_user_id=current_user.id,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "mismatch_id": mismatch_id,
        "old_status": mismatch.status,  # Note: already updated, this shows new
        "new_status": body.status,
        "changed_by": current_user.email,
        "changed_at": mismatch.status_changed_at.isoformat() if mismatch.status_changed_at else None,
    }
```

#### Step 4: Frontend — Status Lifecycle Dropdown on mismatch card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Replace the simple static badge with an interactive dropdown:

```tsx
const STATUS_TRANSITIONS = {
  open:          ['in_progress', 'false_positive', 'resolved'],
  in_progress:   ['resolved', 'open', 'false_positive'],
  resolved:      ['verified', 'open'],
  verified:      ['open'],
  false_positive: ['disputed'],
  disputed:      ['open', 'false_positive'],
  auto_closed:   ['open'],
}

const STATUS_LABELS = {
  open:           { label: 'Open',           color: 'bg-red-100 text-red-800' },
  in_progress:    { label: 'In Progress',    color: 'bg-blue-100 text-blue-800' },
  resolved:       { label: 'Resolved',       color: 'bg-amber-100 text-amber-800' },
  verified:       { label: 'Verified ✓',     color: 'bg-green-100 text-green-800' },
  false_positive: { label: 'False Positive', color: 'bg-orange-100 text-orange-800' },
  auto_closed:    { label: 'Auto-Closed ✓',  color: 'bg-gray-100 text-gray-600' },
  disputed:       { label: 'Disputed',       color: 'bg-purple-100 text-purple-800' },
}

// Status dropdown component:
const StatusDropdown = ({ mismatch, onUpdate }) => {
  const nextStatuses = STATUS_TRANSITIONS[mismatch.status] || []
  const current = STATUS_LABELS[mismatch.status] || { label: mismatch.status, color: 'bg-gray-100' }

  const updateStatus = async (newStatus: string) => {
    const res = await fetch(`/api/v1/validation/mismatches/${mismatch.id}/status`, {
      method: 'PATCH',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    })
    if (res.ok) onUpdate({ ...mismatch, status: newStatus })
  }

  return (
    <div className="relative group">
      <span className={`text-xs px-2 py-1 rounded cursor-pointer ${current.color}`}>
        {current.label} ▾
      </span>
      {nextStatuses.length > 0 && (
        <div className="absolute left-0 top-full mt-1 bg-white border rounded shadow-lg z-20 hidden group-hover:block min-w-[140px]">
          {nextStatuses.map(status => (
            <button
              key={status}
              onClick={() => updateStatus(status)}
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50"
            >
              → {STATUS_LABELS[status]?.label || status}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

Also add status filter tabs (update existing filter):
```tsx
// Summary counts by status
const statusCounts = mismatches.reduce((acc, m) => {
  acc[m.status] = (acc[m.status] || 0) + 1
  return acc
}, {} as Record<string, number>)
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16d1

# 2. Verify "new" migrated to "open"
psql -c "SELECT status, COUNT(*) FROM mismatches GROUP BY status"
# Expected: no rows with status="new"

# 3. Verify CHECK constraint works
psql -c "UPDATE mismatches SET status = 'invalid_status' WHERE id = 1"
# Expected: ERROR: violates check constraint

# 4. Valid transition test
curl -X PATCH /api/v1/validation/mismatches/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "note": "Developer assigned"}'
# Expected: 200

# 5. Invalid transition test
curl -X PATCH /api/v1/validation/mismatches/1/status \
  -d '{"status": "verified"}'
# Expected: 400 "Invalid transition: in_progress → verified"
```

### Risk Assessment
- **Data migration: "new" → "open"** — non-destructive, only changes existing values. Run `SELECT COUNT(*) FROM mismatches WHERE status = 'new'` before migration to verify.
- **CHECK constraint** — any code writing `status="new"` will break. Grep for `"new"` in mismatch creation code and update to `"open"` first.
- **Backward compatibility** — `default="open"` replaces `default="new"` — new mismatches created correctly going forward
- **Frontend graceful** — STATUS_LABELS has a fallback for unknown statuses


---

## P5B-11 — Version-Linked Mismatches (Document Version + Git Commit Hash)

**Ticket ID:** P5B-11
**Priority:** P1 — Audit trail and regression detection. "Which BRD version and git commit created this mismatch?"
**Complexity:** Low
**Risk:** LOW — additive nullable fields on mismatches; existing rows unaffected

### Why This Exists

An auditor asks: "This compliance mismatch was created 3 months ago. Which BRD version triggered it? Which git commit was current when it was found?"

A developer asks: "This mismatch appeared after today's commit. Which exact commit introduced the regression?"

Currently, mismatches have no version linkage. They're orphaned findings with no context.

After P5B-11:
- Every mismatch knows `document_version_id` (which BRD version triggered the finding)
- Every mismatch knows `created_commit_hash` (git commit hash at validation time)
- When a mismatch is auto-closed (P5B-06), `resolved_commit_hash` is recorded
- Timeline view: "Mismatch created at BRD v2 / commit abc123, resolved at commit def456"

### Current State

**File: `backend/app/models/mismatch.py`**
No `document_version_id` or `created_commit_hash` fields.

**File: `backend/app/services/validation_service.py`**
`validate_single_link` runs without knowing which document version is active or which commit triggered the validation.

**File: `backend/app/api/endpoints/webhooks.py`**
`webhook_triggered_analysis` receives `commit_hash` from GitHub push — this is NOT passed through to the validation that follows.

### What to Change

#### Step 1: New migration adding version/commit fields

**New file: `backend/alembic/versions/s16e1_mismatch_version_links.py`**

```python
"""
P5B-11: Add document_version_id and commit hash fields to mismatches.

Revision ID: s16e1
Revises: s16d1
"""
from alembic import op
import sqlalchemy as sa

revision = 's16e1'
down_revision = 's16d1'
branch_labels = None
depends_on = None

def upgrade():
    # Link to the document version that was active when mismatch was found
    op.add_column('mismatches',
        sa.Column('document_version_id', sa.Integer(),
                  sa.ForeignKey('document_versions.id', ondelete='SET NULL'),
                  nullable=True))

    # Git commit hash when mismatch was created
    op.add_column('mismatches',
        sa.Column('created_commit_hash', sa.String(40), nullable=True))

    # Git commit hash when mismatch was resolved/auto-closed (P5B-06)
    op.add_column('mismatches',
        sa.Column('resolved_commit_hash', sa.String(40), nullable=True))

    # Index for filtering mismatches by document version
    op.create_index(
        'ix_mismatches_document_version_id',
        'mismatches', ['document_version_id'],
        postgresql_concurrently=True
    )

    # Index for looking up mismatches created at a specific commit
    op.create_index(
        'ix_mismatches_created_commit_hash',
        'mismatches', ['created_commit_hash'],
        postgresql_concurrently=True
    )

def downgrade():
    op.drop_index('ix_mismatches_created_commit_hash')
    op.drop_index('ix_mismatches_document_version_id')
    op.drop_column('mismatches', 'resolved_commit_hash')
    op.drop_column('mismatches', 'created_commit_hash')
    op.drop_column('mismatches', 'document_version_id')
```

#### Step 2: Update Mismatch model

**File: `backend/app/models/mismatch.py`**

Add after `owner_id` field (line 46):

```python
    # P5B-11: Version-linked mismatches for audit trail
    document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    resolved_commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
```

#### Step 3: Pass version/commit context into validation

**File: `backend/app/services/validation_service.py`**

Update `run_validation` method signature to accept optional `commit_hash`:

```python
# BEFORE:
async def run_validation(
    self, db, *, tenant_id, user_id, document_id, repository_id=None, ...
):

# AFTER:
async def run_validation(
    self, db, *, tenant_id, user_id, document_id, repository_id=None,
    commit_hash: str | None = None,  # P5B-11: git commit that triggered this validation
    **kwargs,
):
    ...
    # When creating mismatches in create_with_link, pass commit_hash:
    new_mismatch = crud.mismatch.create_with_link(
        db=db,
        obj_in={
            **m,
            "direction": "forward",
            "requirement_atom_id": db_atom_id,
            "created_commit_hash": commit_hash,     # P5B-11
            "document_version_id": current_doc_version_id,  # P5B-11 (see below)
        },
        link_id=link.id,
        owner_id=user_id,
        tenant_id=tenant_id,
    )
```

Get `current_doc_version_id` from the document at validation time:

```python
# After loading document in validation_service.py:
from app.crud.crud_document_version import crud_document_version

latest_version = crud_document_version.get_by_document(
    db, document_id=document_id, tenant_id=tenant_id
)
current_doc_version_id = latest_version[0].id if latest_version else None
```

#### Step 4: Pass commit hash from webhook through to validation

**File: `backend/app/tasks/code_analysis_tasks.py`** (in `auto_revalidate_after_analysis`):

```python
# When creating mismatches in _revalidate_link_and_merge:
# The commit_hash parameter is already passed to this function (from P5B-06)
# Just pass it through to run_validation_for_link_preview:

link_result = _revalidate_link_and_merge(
    db=db, link=link, tenant_id=tenant_id,
    validation_svc=validation_svc,
    commit_hash=commit_hash,  # ← Already have this from webhook
)
```

And in `_revalidate_link_and_merge`:
```python
# When calling create_with_link for new mismatches:
crud.mismatch.create_with_link(
    db=db,
    obj_in={
        **new_m_data,
        "direction": "forward",
        "created_commit_hash": commit_hash,  # P5B-11
    },
    ...
)

# When auto-closing:
existing_m.resolved_commit_hash = commit_hash  # P5B-11
```

#### Step 5: New endpoint for mismatch version history

**File: `backend/app/api/endpoints/validation.py`**

```python
@router.get("/mismatches/{mismatch_id}/version-info")
def get_mismatch_version_info(
    mismatch_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-11: Returns version context for a mismatch.
    Shows: which BRD version + git commit created it, which commit resolved it.
    """
    mismatch = crud.mismatch.get(db, id=mismatch_id)
    if not mismatch or mismatch.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    doc_version = None
    if mismatch.document_version_id:
        from app.models.document_version import DocumentVersion
        dv = db.query(DocumentVersion).get(mismatch.document_version_id)
        if dv:
            doc_version = {
                "id": dv.id,
                "version_number": dv.version_number,
                "original_filename": dv.original_filename,
                "uploaded_at": dv.created_at.isoformat(),
            }

    return {
        "mismatch_id": mismatch_id,
        "created_at": mismatch.created_at.isoformat(),
        "document_version": doc_version or "Not tracked (pre-P5B-11 mismatch)",
        "created_commit": mismatch.created_commit_hash or "Not tracked",
        "resolved_commit": mismatch.resolved_commit_hash,
        "current_status": mismatch.status,
        "status_changed_at": (
            mismatch.status_changed_at.isoformat()
            if mismatch.status_changed_at else None
        ),
    }
```

#### Step 6: Frontend — Version info tooltip on mismatch card

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add a small info icon on mismatch card that shows version tooltip on hover:

```tsx
{(mismatch.created_commit_hash || mismatch.document_version_id) && (
  <div className="relative group ml-auto">
    <Info className="h-3.5 w-3.5 text-gray-300 hover:text-gray-500 cursor-help" />
    <div className="absolute right-0 bottom-full mb-1 bg-gray-900 text-white text-xs rounded p-2 min-w-[200px] hidden group-hover:block z-30">
      <div>Found at: BRD v{mismatch.document_version?.version_number || '?'}</div>
      {mismatch.created_commit_hash && (
        <div>Commit: {mismatch.created_commit_hash.slice(0, 8)}</div>
      )}
      {mismatch.resolved_commit_hash && (
        <div className="text-green-300">
          Fixed at: {mismatch.resolved_commit_hash.slice(0, 8)}
        </div>
      )}
    </div>
  </div>
)}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16e1

# 2. Verify columns added
psql -c "\d mismatches" | grep "version\|commit"

# 3. Run validation (manually or via webhook)
# Check document_version_id + created_commit_hash populated
psql -c "SELECT id, document_version_id, created_commit_hash FROM mismatches ORDER BY id DESC LIMIT 3"

# 4. Simulate code push (P5B-06 webhook)
# Auto-closed mismatches should have resolved_commit_hash set
psql -c "SELECT status, resolved_commit_hash FROM mismatches WHERE status = 'auto_closed'"

# 5. Get version info endpoint
curl /api/v1/validation/mismatches/1/version-info
```

### Risk Assessment
- **All new columns nullable** — existing mismatches unaffected (show "Not tracked")
- **Backward compatible** — `run_validation(commit_hash=None)` is the default; no callers break
- **`SET NULL` on delete** — if a document version is deleted, mismatch keeps `document_version_id=NULL` rather than cascade-deleting the mismatch
- **Performance** — `created_commit_hash` and `document_version_id` indexes enable fast commit-specific queries


---

## P5B-12 — BA Sign-Off Workflow + Compliance Certificate

**Ticket ID:** P5B-12
**Priority:** P1 — Required for regulated industry customers. "Can we prove this BRD was reviewed and signed off before the release?"
**Complexity:** Medium
**Risk:** LOW — new models/endpoints only; no existing functionality modified

### Why This Exists

Before a banking system ships to production, the BA must sign off that:
1. All requirements in BRD v3 have been validated against the code
2. All critical mismatches have been resolved or explicitly accepted with justification
3. A compliance certificate can be produced for the audit trail

Currently DokyDoc has no sign-off concept. After P5B-12:
- BA can perform sign-off for a specific BRD version against a specific repository
- Sign-off requires: all critical mismatches resolved OR explicitly acknowledged
- System generates a signed compliance certificate (JSON/PDF) with:
  - Tenant name, document title, document version
  - Date signed, signed by (name + role)
  - Compliance score at time of sign-off
  - List of open mismatches acknowledged as acceptable
  - SHA-256 tamper-evidence hash

### Current State

No sign-off model or endpoint exists.
`Approval` model exists (`backend/app/models/approval.py`) for general workflow approvals — but it's not wired to document validation sign-off.

### What to Change

#### Step 1: New model `BRDSignOff`

**New file: `backend/app/models/brd_sign_off.py`**

```python
"""
P5B-12: BRD Sign-Off — records a BA's formal sign-off of a document version.
Used for audit trail and compliance certificate generation.
"""
import hashlib
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base


class BRDSignOff(Base):
    __tablename__ = "brd_sign_offs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # What was signed off
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )

    # Who signed off
    signed_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    signed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # Sign-off details
    # Compliance score at time of sign-off (snapshot)
    compliance_score_at_signoff: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)

    # Summary of open mismatches at sign-off time
    open_mismatches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_mismatches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Explicitly acknowledged open mismatches (developer/BA accepts the risk)
    # List of mismatch IDs that are open but acknowledged as acceptable
    acknowledged_mismatch_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # BA notes (free text)
    sign_off_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Can only sign off if all critical mismatches are resolved OR acknowledged
    has_unresolved_critical: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Certificate fields
    certificate_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # SHA-256 of the certificate content for tamper detection

    # Relationships
    document = relationship("Document")
    signed_by = relationship("User")

    def generate_certificate_hash(self) -> str:
        """Generate a tamper-evident hash of the sign-off content."""
        content = {
            "tenant_id": self.tenant_id,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "signed_by_user_id": self.signed_by_user_id,
            "signed_at": self.signed_at.isoformat(),
            "compliance_score": self.compliance_score_at_signoff,
            "open_mismatches": self.open_mismatches_count,
            "critical_mismatches": self.critical_mismatches_count,
        }
        return hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
```

**New migration: `backend/alembic/versions/s16f1_brd_sign_offs.py`**

```python
"""
P5B-12: Create brd_sign_offs table.

Revision ID: s16f1
Revises: s16e1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 's16f1'
down_revision = 's16e1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'brd_sign_offs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(),
                  sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_version_id', sa.Integer(),
                  sa.ForeignKey('document_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('repository_id', sa.Integer(),
                  sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('signed_by_user_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('signed_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('compliance_score_at_signoff', sa.Float(), nullable=True),
        sa.Column('open_mismatches_count', sa.Integer(), default=0, nullable=False),
        sa.Column('critical_mismatches_count', sa.Integer(), default=0, nullable=False),
        sa.Column('acknowledged_mismatch_ids', JSONB(), nullable=True),
        sa.Column('sign_off_notes', sa.Text(), nullable=True),
        sa.Column('has_unresolved_critical', sa.Boolean(), default=False, nullable=False),
        sa.Column('certificate_hash', sa.String(64), nullable=True),
    )
    op.create_index('ix_brd_sign_offs_tenant_id', 'brd_sign_offs', ['tenant_id'])
    op.create_index('ix_brd_sign_offs_document_id', 'brd_sign_offs', ['document_id'])

def downgrade():
    op.drop_table('brd_sign_offs')
```

#### Step 2: Add `BRDSignOff` to models `__init__`

**File: `backend/app/models/__init__.py`**

```python
from .brd_sign_off import BRDSignOff  # P5B-12
```

#### Step 3: CRUD for BRDSignOff

**New file: `backend/app/crud/crud_brd_sign_off.py`**

```python
from sqlalchemy.orm import Session
from app.models.brd_sign_off import BRDSignOff


class CRUDBRDSignOff:

    def create_sign_off(
        self,
        db: Session,
        *,
        tenant_id: int,
        document_id: int,
        document_version_id: int | None,
        repository_id: int | None,
        signed_by_user_id: int,
        compliance_score: float | None,
        open_mismatches_count: int,
        critical_mismatches_count: int,
        acknowledged_mismatch_ids: list[int] | None,
        sign_off_notes: str | None,
        has_unresolved_critical: bool,
    ) -> BRDSignOff:
        from datetime import datetime
        sign_off = BRDSignOff(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=document_version_id,
            repository_id=repository_id,
            signed_by_user_id=signed_by_user_id,
            signed_at=datetime.now(),
            compliance_score_at_signoff=compliance_score,
            open_mismatches_count=open_mismatches_count,
            critical_mismatches_count=critical_mismatches_count,
            acknowledged_mismatch_ids=acknowledged_mismatch_ids or [],
            sign_off_notes=sign_off_notes,
            has_unresolved_critical=has_unresolved_critical,
        )
        # Generate certificate hash BEFORE committing
        sign_off.certificate_hash = sign_off.generate_certificate_hash()
        db.add(sign_off)
        db.commit()
        db.refresh(sign_off)
        return sign_off

    def get_by_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> list[BRDSignOff]:
        return db.query(BRDSignOff).filter(
            BRDSignOff.document_id == document_id,
            BRDSignOff.tenant_id == tenant_id,
        ).order_by(BRDSignOff.signed_at.desc()).all()

    def get_latest(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> BRDSignOff | None:
        return db.query(BRDSignOff).filter(
            BRDSignOff.document_id == document_id,
            BRDSignOff.tenant_id == tenant_id,
        ).order_by(BRDSignOff.signed_at.desc()).first()


crud_brd_sign_off = CRUDBRDSignOff()
```

#### Step 4: Sign-off endpoints

**File: `backend/app/api/endpoints/validation.py`**

```python
from pydantic import BaseModel
from typing import Optional

class SignOffRequest(BaseModel):
    repository_id: Optional[int] = None
    acknowledged_mismatch_ids: list[int] = []
    sign_off_notes: Optional[str] = None
    # BA must explicitly confirm they've reviewed open critical mismatches
    confirm_acknowledged_criticals: bool = False


@router.post("/{document_id}/sign-off")
def sign_off_document(
    document_id: int,
    body: SignOffRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-12: BA signs off on a document version after validation review.
    
    Pre-conditions:
    - All CRITICAL mismatches must be resolved OR in acknowledged_mismatch_ids
    - Only users with role business_analyst, admin, or owner can sign off
    
    Returns: sign-off record with certificate_hash.
    """
    # Role check — only BA/admin/owner can sign off
    if current_user.role not in ("business_analyst", "admin", "owner"):
        raise HTTPException(
            status_code=403,
            detail="Only Business Analysts, Admins, and Owners can sign off documents."
        )

    document = crud.document.get(db, id=document_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get compliance breakdown
    from app.crud.crud_mismatch import crud as mismatch_crud
    breakdown = mismatch_crud.mismatch.get_compliance_breakdown(
        db=db, document_id=document_id, tenant_id=tenant_id
    )

    compliance_score = breakdown.get("overall_score")

    # Count open mismatches
    open_mismatches = db.query(Mismatch).filter(
        Mismatch.document_id == document_id,
        Mismatch.tenant_id == tenant_id,
        Mismatch.status.in_(["open", "in_progress"]),
    ).all()

    critical_open = [m for m in open_mismatches if m.severity in ("critical", "compliance_risk")]
    unacknowledged_criticals = [
        m for m in critical_open
        if m.id not in body.acknowledged_mismatch_ids
    ]

    # Block sign-off if there are unacknowledged critical mismatches
    if unacknowledged_criticals and not body.confirm_acknowledged_criticals:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unresolved_critical_mismatches",
                "message": (
                    f"{len(unacknowledged_criticals)} critical/compliance-risk mismatch(es) "
                    f"are unresolved. Either resolve them or include their IDs in "
                    f"acknowledged_mismatch_ids and set confirm_acknowledged_criticals=true."
                ),
                "unresolved_ids": [m.id for m in unacknowledged_criticals],
            }
        )

    # Get latest document version
    from app.crud.crud_document_version import crud_document_version
    versions = crud_document_version.get_by_document(
        db, document_id=document_id, tenant_id=tenant_id
    )
    doc_version_id = versions[0].id if versions else None

    # Create sign-off record
    from app.crud.crud_brd_sign_off import crud_brd_sign_off
    sign_off = crud_brd_sign_off.create_sign_off(
        db=db,
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=doc_version_id,
        repository_id=body.repository_id,
        signed_by_user_id=current_user.id,
        compliance_score=compliance_score,
        open_mismatches_count=len(open_mismatches),
        critical_mismatches_count=len(critical_open),
        acknowledged_mismatch_ids=body.acknowledged_mismatch_ids,
        sign_off_notes=body.sign_off_notes,
        has_unresolved_critical=len(unacknowledged_criticals) > 0,
    )

    # Log audit event
    try:
        from app.services.audit_service import audit_service
        audit_service.log(
            db, tenant_id=tenant_id, actor_id=current_user.id,
            event_type="document.signed_off",
            resource_type="document", resource_id=document_id,
            metadata={
                "sign_off_id": sign_off.id,
                "compliance_score": compliance_score,
                "open_mismatches": len(open_mismatches),
            }
        )
    except Exception:
        pass

    return {
        "sign_off_id": sign_off.id,
        "document_id": document_id,
        "signed_by": current_user.email,
        "signed_at": sign_off.signed_at.isoformat(),
        "compliance_score": compliance_score,
        "open_mismatches": len(open_mismatches),
        "certificate_hash": sign_off.certificate_hash,
        "status": "signed_off",
    }


@router.get("/{document_id}/certificate")
def get_compliance_certificate(
    document_id: int,
    sign_off_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    P5B-12: Returns compliance certificate for a signed-off document.
    JSON format by default — can be used to generate PDF via frontend.
    """
    from app.crud.crud_brd_sign_off import crud_brd_sign_off

    if sign_off_id:
        sign_off = db.query(BRDSignOff).filter(
            BRDSignOff.id == sign_off_id,
            BRDSignOff.tenant_id == tenant_id,
        ).first()
    else:
        sign_off = crud_brd_sign_off.get_latest(
            db, document_id=document_id, tenant_id=tenant_id
        )

    if not sign_off:
        raise HTTPException(status_code=404, detail="No sign-off found for this document")

    document = crud.document.get(db, id=document_id)
    tenant = crud.tenant.get(db, id=tenant_id)

    # Load document version info
    doc_version = None
    if sign_off.document_version_id:
        from app.models.document_version import DocumentVersion
        dv = db.query(DocumentVersion).get(sign_off.document_version_id)
        if dv:
            doc_version = {
                "version_number": dv.version_number,
                "filename": dv.original_filename,
                "uploaded_at": dv.created_at.isoformat(),
            }

    # Load acknowledged mismatch details
    acknowledged_details = []
    if sign_off.acknowledged_mismatch_ids:
        ack_mismatches = db.query(Mismatch).filter(
            Mismatch.id.in_(sign_off.acknowledged_mismatch_ids)
        ).all()
        acknowledged_details = [
            {
                "id": m.id,
                "type": m.mismatch_type,
                "description": m.description[:200],
                "severity": m.severity,
            }
            for m in ack_mismatches
        ]

    certificate = {
        "certificate_type": "Documentation Compliance Sign-Off",
        "certificate_id": f"DOKYDOC-{sign_off.id:06d}",
        "tenant": {
            "name": tenant.name if tenant else "Unknown",
            "id": tenant_id,
        },
        "document": {
            "id": document_id,
            "title": document.title if document else "Unknown",
            "version": doc_version,
        },
        "validation_summary": {
            "compliance_score": sign_off.compliance_score_at_signoff,
            "compliance_percentage": (
                round(sign_off.compliance_score_at_signoff * 100)
                if sign_off.compliance_score_at_signoff else None
            ),
            "open_mismatches_at_signoff": sign_off.open_mismatches_count,
            "critical_mismatches_at_signoff": sign_off.critical_mismatches_count,
        },
        "acknowledged_risks": {
            "count": len(acknowledged_details),
            "mismatches": acknowledged_details,
            "sign_off_notes": sign_off.sign_off_notes,
        },
        "sign_off": {
            "signed_by_user_id": sign_off.signed_by_user_id,
            "signed_at": sign_off.signed_at.isoformat(),
            "sign_off_id": sign_off.id,
        },
        "tamper_evidence": {
            "certificate_hash": sign_off.certificate_hash,
            "hash_algorithm": "SHA-256",
            "note": "Recompute this hash to verify certificate authenticity",
        }
    }

    return certificate


@router.get("/{document_id}/sign-off-history")
def get_sign_off_history(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """P5B-12: List all sign-offs for a document, newest first."""
    from app.crud.crud_brd_sign_off import crud_brd_sign_off
    sign_offs = crud_brd_sign_off.get_by_document(
        db, document_id=document_id, tenant_id=tenant_id
    )
    return {
        "document_id": document_id,
        "sign_offs": [
            {
                "id": s.id,
                "signed_at": s.signed_at.isoformat(),
                "signed_by_user_id": s.signed_by_user_id,
                "compliance_score": s.compliance_score_at_signoff,
                "open_mismatches": s.open_mismatches_count,
                "certificate_hash": s.certificate_hash,
            }
            for s in sign_offs
        ]
    }
```

#### Step 5: Frontend — Sign-Off UI on validation panel

**File: `frontend/app/dashboard/validation-panel/page.tsx`**

Add sign-off section at bottom of validation panel (visible to BA/admin/owner roles):

```tsx
{canSignOff && (
  <div className="mt-6 border-t pt-4">
    <h3 className="font-semibold text-gray-700 mb-3">Sign Off This Document Version</h3>

    {latestSignOff ? (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center justify-between">
        <div>
          <div className="font-medium text-green-800 flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            Signed off by {latestSignOff.signed_by_email}
          </div>
          <div className="text-sm text-green-600 mt-1">
            {new Date(latestSignOff.signed_at).toLocaleString()} ·
            Compliance: {Math.round(latestSignOff.compliance_score * 100)}%
          </div>
        </div>
        <button
          onClick={downloadCertificate}
          className="text-sm px-3 py-1.5 border border-green-300 text-green-700 rounded hover:bg-green-100 flex items-center gap-1"
        >
          <Download className="h-3.5 w-3.5" />
          Certificate
        </button>
      </div>
    ) : (
      <div className="bg-gray-50 border rounded-lg p-4">
        {criticalOpenCount > 0 && (
          <div className="text-amber-700 text-sm mb-3">
            ⚠ {criticalOpenCount} critical mismatch(es) require resolution or acknowledgment before sign-off
          </div>
        )}
        <div className="flex items-center gap-3">
          <textarea
            value={signOffNotes}
            onChange={(e) => setSignOffNotes(e.target.value)}
            placeholder="Sign-off notes (optional)..."
            className="flex-1 text-sm border rounded p-2 h-16 resize-none"
          />
          <button
            onClick={handleSignOff}
            disabled={signingOff}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {signingOff ? 'Signing...' : 'Sign Off'}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Compliance score: {complianceScore?.percentage}% · Open mismatches: {openCount}
        </p>
      </div>
    )}
  </div>
)}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s16f1

# 2. Verify table created
psql -c "\d brd_sign_offs"

# 3. Test sign-off with no critical mismatches
curl -X POST /api/v1/validation/{document_id}/sign-off \
  -H "Authorization: Bearer $BA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sign_off_notes": "Reviewed and approved for release v1.2"}'
# Expected: { "sign_off_id": 1, "certificate_hash": "abc...", "status": "signed_off" }

# 4. Test sign-off with critical mismatches (should fail)
# Expected: 422 { "error": "unresolved_critical_mismatches", "unresolved_ids": [...] }

# 5. Test sign-off with acknowledged criticals
curl -X POST /api/v1/validation/{document_id}/sign-off \
  -d '{"acknowledged_mismatch_ids": [5, 7], "confirm_acknowledged_criticals": true,
       "sign_off_notes": "Mismatches 5 and 7 are accepted risk for MVP release"}'
# Expected: success with has_unresolved_critical=true

# 6. Download certificate
curl /api/v1/validation/{document_id}/certificate
# Expected: JSON certificate with certificate_hash

# 7. Verify certificate hash is tamper-evident
# Manually change one field in the certificate JSON
# Recompute SHA-256 → should not match certificate_hash
```

### Risk Assessment
- **Role check** — only BA/admin/owner can sign off; developers cannot self-approve their own work
- **Certificate hash** — SHA-256 of key fields; any field change breaks hash → detectable tampering
- **Blocking on unacknowledged criticals** — prevents accidental sign-off with critical gaps
- **No cascade deletes** — `SET NULL` on FK deletion prevents sign-off records from disappearing if document version is removed
- **Audit log** — every sign-off writes an audit event for compliance evidence


---

## Phase 5C — Workflow Completeness: End-to-End Actor Journeys

### Strategic Context

Phase 5B delivered validation accuracy and enterprise controls. Phase 5C completes the **end-to-end actor journeys** — every step a Business Analyst, Developer, QA Engineer, Tech Lead, and CTO needs to accomplish in DokyDoc without leaving the platform.

Nine capabilities are missing from the current plan to make the full workflow operational:

| Task | Capability | Primary Actor |
|------|-----------|---------------|
| P5C-01 | Smart File Suggestion Engine | BA / Developer |
| P5C-02 | Cross-Role Upload Request Notification | BA → Tech Lead |
| P5C-03 | Request Clarification Workflow | BA ↔ Developer |
| P5C-04 | UAT Checklist Auto-generation + QA Sign-off | BA / QA |
| P5C-05 | Auto-generated Test Suite Download | QA |
| P5C-06 | CI Test Result Webhook → Runtime Mismatch | QA / CI |
| P5C-07 | AI-Suggested Fix per Mismatch | Developer |
| P5C-08 | Compliance Score Trend / Time Series | Tech Lead |
| P5C-09 | Cross-Project Aggregate Compliance Dashboard | CTO |

### Migration Chain (Phase 5C)

```
s16f1  (Phase 5B baseline — brd_sign_offs)
  └── s17a1_file_suggestions          (P5C-01)
       └── s17b1_mismatch_clarifications  (P5C-03)
            └── s17c1_uat_checklist        (P5C-04)
                 └── s17d1_compliance_snapshots  (P5C-08)
                      └── s17e1_ci_webhook_config  (P5C-06)
```

---

## P5C-01 — Smart File Suggestion Engine

**Priority:** P0 — Core workflow blocker. Without this, the BA cannot guide the developer on what to upload, and atoms remain unvalidated.
**Complexity:** HIGH — Requires AI analysis of atom content to extract code identifiers.
**Risk:** MEDIUM — Gemini call is non-blocking; suggestions are advisory only.

### Why This Exists

**BA Step 4** of the workflow: after atomization, DokyDoc shows "47 atoms extracted. Missing coverage: Upload `payment_service.py` and `fd_service.py` to validate 14 of these atoms."

Currently, after atomization completes, the BA sees a list of atoms but **no guidance** on which code files to upload. The developer is asked to "upload some files" with no direction. This causes:
- Developers uploading the wrong files
- Atoms never getting validated because the right file was never uploaded
- BA-developer back-and-forth via Slack to figure out what to upload

The fix: after atomization, run a second Gemini pass that reads all atoms and extracts **code entity names** (service class names, file names, module names, function names) referenced in the atom content. Map these to likely file paths.

### DB Changes

**New table: `file_suggestions`**

**New migration: `backend/alembic/versions/s17a1_file_suggestions.py`**

```python
# backend/alembic/versions/s17a1_file_suggestions.py
"""Add file_suggestions table and atom testability field

Revision ID: s17a1
Revises: s16f1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = 's17a1'
down_revision = 's16f1'
branch_labels = None
depends_on = None


def upgrade():
    # 1. New table: file_suggestions
    op.create_table(
        'file_suggestions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer, sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        # Suggested filename or path (e.g. "payment_service.py")
        sa.Column('suggested_filename', sa.String(500), nullable=False),
        # Why this file was suggested — human-readable reason
        sa.Column('reason', sa.Text, nullable=False),
        # Which atoms reference this file (array of atom DB ids)
        sa.Column('atom_ids', ARRAY(sa.Integer), nullable=False, server_default='{}'),
        # How many atoms this file would cover
        sa.Column('atom_count', sa.Integer, nullable=False, default=0),
        # Whether the file has been uploaded already (FK to code_components)
        sa.Column('fulfilled_by_component_id', sa.Integer,
                  sa.ForeignKey('code_components.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_file_suggestions_document_id', 'file_suggestions', ['document_id'])

    # 2. Add testability field to requirement_atoms
    # Values: "static" (AI can validate), "runtime" (needs live test), "manual" (needs human UAT)
    op.add_column(
        'requirement_atoms',
        sa.Column('testability', sa.String(20), nullable=True)
    )
    # Add suggested_files summary JSONB to documents table
    op.add_column(
        'documents',
        sa.Column('file_suggestion_summary', JSONB, nullable=True)
    )


def downgrade():
    op.drop_column('documents', 'file_suggestion_summary')
    op.drop_column('requirement_atoms', 'testability')
    op.drop_table('file_suggestions')
```

### Backend — New Model `FileSuggestion`

**New file: `backend/app/models/file_suggestion.py`**

```python
# backend/app/models/file_suggestion.py
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base_class import Base


class FileSuggestion(Base):
    """
    AI-generated suggestion of which code files to upload to cover BRD atoms.
    Created after atomization completes. Marked fulfilled when the file is uploaded.
    """
    __tablename__ = "file_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    suggested_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    atom_ids: Mapped[list] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    atom_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulfilled_by_component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

**Add to `backend/app/models/__init__.py`:**

```python
from .file_suggestion import FileSuggestion  # noqa: F401
```

**Add to `backend/app/db/base.py`** (import all models):

```python
from app.models.file_suggestion import FileSuggestion  # noqa: F401
```

### Backend — Gemini Prompt for File Suggestion

**Add to `backend/app/services/ai/gemini.py`** (after existing `_ATOM_TYPE_INSTRUCTIONS`):

```python
_FILE_SUGGESTION_PROMPT = """
You are a code architecture assistant. Given a list of BRD requirement atoms,
identify which Python/TypeScript/Go source files a developer would need to upload
for automated validation of these requirements.

For each suggested file:
- Extract CLASS NAMES, SERVICE NAMES, FUNCTION NAMES, or MODULE NAMES mentioned in the atoms
- Map them to likely filenames using these conventions:
  * PaymentService → payment_service.py or paymentService.ts
  * fd_rate, fd_product → fd_service.py or fixed_deposit_service.py
  * "POST /api/v1/loans" → loan_router.py or loans.py
  * Database migration values → look for "migration" or "alembic" mentions

Return ONLY valid JSON with this exact structure:
{
  "suggestions": [
    {
      "filename": "payment_service.py",
      "reason": "Atoms REQ-004, REQ-007 reference PaymentService and payment processing logic",
      "atom_ids": ["REQ-004", "REQ-007"],
      "atom_count": 2,
      "confidence": "high"
    }
  ]
}

Rules:
- Maximum 8 file suggestions
- Only suggest files that would materially improve atom coverage
- If atom references a specific HTTP endpoint, suggest the router file
- confidence: "high" (filename explicitly mentioned), "medium" (class/service implied), "low" (indirect reference)
- Do NOT suggest config files, __init__.py, or test files
"""


async def call_gemini_for_file_suggestions(
    atoms: list[dict],
    model: str = "gemini-2.0-flash",
) -> list[dict]:
    """
    Analyze atom content to suggest which code files should be uploaded.
    Returns list of suggestion dicts matching _FILE_SUGGESTION_PROMPT schema.
    """
    import google.generativeai as genai
    from app.core.config import settings

    if not atoms:
        return []

    atom_summary = "\n".join(
        f"- [{a['atom_id']}] ({a['atom_type']}) {a['content']}"
        for a in atoms[:60]  # Cap at 60 atoms to stay within token limit
    )
    prompt = f"{_FILE_SUGGESTION_PROMPT}\n\nATOMS:\n{atom_summary}"

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model_client = genai.GenerativeModel(model)
    response = model_client.generate_content(
        prompt,
        generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
    )
    import json
    data = json.loads(response.text)
    return data.get("suggestions", [])
```

### Backend — Service: `FileSuggestionService`

**New file: `backend/app/services/file_suggestion_service.py`**

```python
# backend/app/services/file_suggestion_service.py
"""
FileSuggestionService — analyses atom content post-atomization to suggest
which code files a developer should upload for validation coverage.
"""
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.file_suggestion import FileSuggestion
from app.crud.crud_requirement_atom import requirement_atom as crud_atom

logger = get_logger("file_suggestion_service")


class FileSuggestionService:

    async def generate_and_store(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
    ) -> list[FileSuggestion]:
        """
        Called after atomization completes. Fetches all atoms for the document,
        calls Gemini to suggest files, stores results, returns list.
        """
        from app.services.ai.gemini import call_gemini_for_file_suggestions

        # Fetch atoms
        atoms = db.query(
            __import__('app.models.requirement_atom', fromlist=['RequirementAtom']).RequirementAtom
        ).filter_by(document_id=document_id, tenant_id=tenant_id).all()

        if not atoms:
            return []

        atom_dicts = [
            {"atom_id": a.atom_id, "atom_type": a.atom_type, "content": a.content}
            for a in atoms
        ]

        try:
            suggestions = await call_gemini_for_file_suggestions(atom_dicts)
        except Exception as e:
            logger.warning(f"File suggestion Gemini call failed: {e}")
            return []

        # Build atom_id→DB id map
        atom_id_to_db_id = {a.atom_id: a.id for a in atoms}

        # Delete existing suggestions for this document (re-atomization case)
        db.query(FileSuggestion).filter_by(document_id=document_id, tenant_id=tenant_id).delete()

        stored = []
        for s in suggestions:
            db_ids = [atom_id_to_db_id[aid] for aid in s.get("atom_ids", []) if aid in atom_id_to_db_id]
            obj = FileSuggestion(
                tenant_id=tenant_id,
                document_id=document_id,
                suggested_filename=s["filename"],
                reason=s["reason"],
                atom_ids=db_ids,
                atom_count=len(db_ids),
            )
            db.add(obj)
            stored.append(obj)

        db.commit()

        # Store summary JSON on the document itself for fast dashboard access
        from app.models.document import Document
        doc = db.get(Document, document_id)
        if doc:
            doc.file_suggestion_summary = {
                "total_suggestions": len(stored),
                "filenames": [s.suggested_filename for s in stored],
                "uncovered_atom_count": sum(s.atom_count for s in stored),
            }
            db.add(doc)
            db.commit()

        logger.info(f"Generated {len(stored)} file suggestions for document {document_id}")
        return stored


file_suggestion_service = FileSuggestionService()
```

### Backend — Trigger After Atomization

**In `backend/app/tasks/document_pipeline.py`**, after `atomize_document` succeeds and emits the `analysis_complete` notification (around line 150), add:

```python
# PHASE 5C: After atomization — suggest code files to upload
try:
    import asyncio
    from app.services.file_suggestion_service import file_suggestion_service
    asyncio.run(
        file_suggestion_service.generate_and_store(
            db=db,
            document_id=document.id,
            tenant_id=document.tenant_id,
        )
    )
except Exception as e:
    logger.warning(f"File suggestion generation failed (non-fatal): {e}")
```

### Backend — Mark Suggestion Fulfilled on Code Upload

**In `backend/app/tasks/code_analysis_tasks.py`**, after a new code component is created/linked, add:

```python
# PHASE 5C: Check if this upload fulfills any file suggestions
try:
    from app.models.file_suggestion import FileSuggestion
    filename = component.file_path.split("/")[-1]  # e.g. "payment_service.py"
    pending = db.query(FileSuggestion).filter(
        FileSuggestion.document_id == document_id,
        FileSuggestion.tenant_id == tenant_id,
        FileSuggestion.fulfilled_by_component_id == None,
        FileSuggestion.suggested_filename.ilike(f"%{filename}%"),
    ).all()
    for suggestion in pending:
        suggestion.fulfilled_by_component_id = component.id
    db.commit()
except Exception as e:
    logger.warning(f"File suggestion fulfillment mark failed (non-fatal): {e}")
```

### Backend — API Endpoint

**Add to `backend/app/api/endpoints/documents.py`:**

```python
# GET /documents/{document_id}/file-suggestions
@router.get("/{document_id}/file-suggestions")
def get_file_suggestions(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return AI-generated suggestions of which code files to upload
    to maximize validation coverage for this document's atoms.
    """
    from app.models.file_suggestion import FileSuggestion

    suggestions = db.query(FileSuggestion).filter(
        FileSuggestion.document_id == document_id,
        FileSuggestion.tenant_id == current_user.tenant_id,
    ).order_by(FileSuggestion.atom_count.desc()).all()

    return {
        "document_id": document_id,
        "suggestions": [
            {
                "id": s.id,
                "filename": s.suggested_filename,
                "reason": s.reason,
                "atom_count": s.atom_count,
                "is_fulfilled": s.fulfilled_by_component_id is not None,
                "fulfilled_by_component_id": s.fulfilled_by_component_id,
            }
            for s in suggestions
        ],
        "total_unfulfilled": sum(1 for s in suggestions if not s.fulfilled_by_component_id),
        "uncovered_atoms": sum(s.atom_count for s in suggestions if not s.fulfilled_by_component_id),
    }
```

### Frontend — File Suggestion Banner on Document Page

**In the document detail page** (wherever atom count is displayed), add a `FileSuggestionBanner` component:

**New file: `frontend/components/documents/FileSuggestionBanner.tsx`**

```tsx
// frontend/components/documents/FileSuggestionBanner.tsx
import { useState } from "react";
import { Upload, X, CheckCircle, AlertTriangle } from "lucide-react";
import { useSuggestions } from "@/hooks/useFileSuggestions";

interface Props {
  documentId: number;
  onRequestUpload: () => void;  // opens the upload modal
}

export function FileSuggestionBanner({ documentId, onRequestUpload }: Props) {
  const { suggestions, isLoading } = useSuggestions(documentId);
  const [dismissed, setDismissed] = useState(false);

  const unfulfilled = suggestions?.filter((s) => !s.is_fulfilled) ?? [];

  if (isLoading || dismissed || unfulfilled.length === 0) return null;

  const uncoveredAtoms = unfulfilled.reduce((sum, s) => sum + s.atom_count, 0);

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-amber-800">
              {uncoveredAtoms} atoms need code files to be validated
            </p>
            <p className="text-xs text-amber-700 mt-1">
              Upload these files to enable automated validation:
            </p>
            <ul className="mt-2 space-y-1">
              {unfulfilled.map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-xs text-amber-800">
                  <span className="font-mono bg-amber-100 px-1.5 py-0.5 rounded">
                    {s.filename}
                  </span>
                  <span className="text-amber-600">— {s.atom_count} atoms · {s.reason}</span>
                </li>
              ))}
            </ul>
            <button
              onClick={onRequestUpload}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-xs rounded-md hover:bg-amber-700 transition-colors"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload these files
            </button>
          </div>
        </div>
        <button onClick={() => setDismissed(true)} className="text-amber-400 hover:text-amber-600">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

**New hook: `frontend/hooks/useFileSuggestions.ts`**

```typescript
// frontend/hooks/useFileSuggestions.ts
import useSWR from "swr";
import { apiGet } from "@/lib/api";

export function useSuggestions(documentId: number) {
  const { data, isLoading, mutate } = useSWR(
    documentId ? `/documents/${documentId}/file-suggestions` : null,
    apiGet,
    { refreshInterval: 30_000 }  // poll every 30s to detect fulfillment
  );
  return { suggestions: data?.suggestions ?? [], isLoading, mutate };
}
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s17a1

# 2. Verify columns and table
psql -c "\d file_suggestions"
psql -c "\d requirement_atoms" | grep testability
psql -c "\d documents" | grep file_suggestion

# 3. Upload a BRD document and wait for atomization to complete
# Then check suggestions were generated:
psql -c "SELECT suggested_filename, atom_count, reason FROM file_suggestions WHERE document_id=1"

# 4. Test the API endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/documents/1/file-suggestions
# Expected: { "suggestions": [...], "total_unfulfilled": 3, "uncovered_atoms": 14 }

# 5. Upload one of the suggested files, then re-check:
# fulfilled_by_component_id should be set for that suggestion
psql -c "SELECT suggested_filename, fulfilled_by_component_id FROM file_suggestions WHERE document_id=1"
```

### Risk Assessment
- **Gemini call is async + non-blocking** — wrapped in try/except; atomization never fails because of this
- **Re-atomization safe** — old suggestions are deleted before new ones are written
- **Token limit** — capped at 60 atoms per Gemini call; large BRDs truncated with warning
- **Fulfillment match** — uses `ilike "%filename%"` which is fuzzy; unlikely to create false positives


---

## P5C-02 — Cross-Role Upload Request Notification (BA → Tech Lead)

**Priority:** P1 — Without this, the BA has no way to formally request developers to upload specific files.
**Complexity:** LOW — Uses the existing notification infrastructure.
**Risk:** LOW — Sends in-app notifications only; no external side effects.

### Why This Exists

**BA Step 5** of the workflow: "BA shares link with tech lead: 'Please upload these files'."

Currently, the BA must manually copy a URL and send it through Slack/email. DokyDoc has no built-in way for the BA to say "hey tech lead, these 3 files need uploading". The P5C-01 banner tells the BA what's needed — P5C-02 lets them act on it with one click.

The feature: a "Request Code Upload" button on the document page that opens a modal letting BA select target users (by role) and customize a message. On submit, in-app notifications are sent to those users with a direct link to the document and the list of suggested files.

### No New DB Changes

This uses the existing `notifications` table and `notification_service`. No migration needed.

The only model touch is adding a new `notification_type = "upload_request"` string — this is just a value, not a schema change.

### Backend — New Endpoint

**Add to `backend/app/api/endpoints/documents.py`:**

```python
from pydantic import BaseModel
from typing import List, Optional


class UploadRequestBody(BaseModel):
    user_ids: List[int]                    # specific user IDs to notify
    message: Optional[str] = None          # optional custom message from BA
    suggested_filenames: List[str] = []    # pre-filled from P5C-01 suggestions


@router.post("/{document_id}/request-uploads", status_code=202)
def request_code_uploads(
    document_id: int,
    body: UploadRequestBody,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    BA triggers: notify specified users that they need to upload code files
    for validation of this document. Uses existing notification_service.
    """
    from app.services.notification_service import notify
    from app.models.document import Document

    doc = db.get(Document, document_id)
    if not doc or doc.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    filenames_str = ", ".join(body.suggested_filenames) if body.suggested_filenames else "relevant code files"
    custom_msg = body.message or ""
    base_msg = (
        f"{current_user.full_name or current_user.email} has requested that you upload "
        f"{filenames_str} for BRD validation of '{doc.title}'."
    )
    full_message = f"{base_msg} {custom_msg}".strip()

    # Validate user_ids belong to same tenant
    from app.models.user import User
    valid_users = db.query(User).filter(
        User.id.in_(body.user_ids),
        User.tenant_id == current_user.tenant_id,
        User.is_active == True,
    ).all()
    valid_ids = {u.id for u in valid_users}

    notified = []
    for user_id in body.user_ids:
        if user_id not in valid_ids:
            continue
        notify(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            notification_type="upload_request",
            title=f"Code upload requested for '{doc.title}'",
            message=full_message,
            resource_type="document",
            resource_id=document_id,
            details={
                "requested_by_user_id": current_user.id,
                "requested_by_name": current_user.full_name or current_user.email,
                "suggested_filenames": body.suggested_filenames,
                "document_title": doc.title,
            },
        )
        notified.append(user_id)

    return {
        "notified_user_ids": notified,
        "message": f"Upload request sent to {len(notified)} user(s)",
    }


@router.get("/{document_id}/team-members")
def get_document_team_members(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return all active users in the tenant so the BA can select who to notify.
    Sorted by role (tech_lead first, then developer, then others).
    """
    from app.models.user import User

    users = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        User.is_active == True,
        User.id != current_user.id,  # exclude self
    ).all()

    def role_sort_key(u):
        roles = u.roles or []
        if "tech_lead" in roles: return 0
        if "developer" in roles: return 1
        return 2

    users.sort(key=role_sort_key)

    return {
        "team_members": [
            {
                "id": u.id,
                "name": u.full_name or u.email,
                "email": u.email,
                "roles": u.roles,
            }
            for u in users
        ]
    }
```

### Frontend — "Request Code Upload" Modal

**New file: `frontend/components/documents/RequestUploadModal.tsx`**

```tsx
// frontend/components/documents/RequestUploadModal.tsx
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { useTeamMembers } from "@/hooks/useTeamMembers";
import { apiPost } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onClose: () => void;
  documentId: number;
  suggestedFilenames: string[];
}

export function RequestUploadModal({ open, onClose, documentId, suggestedFilenames }: Props) {
  const { teamMembers } = useTeamMembers(documentId);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  const toggle = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSend = async () => {
    if (selectedIds.size === 0) return;
    setSending(true);
    try {
      await apiPost(`/documents/${documentId}/request-uploads`, {
        user_ids: Array.from(selectedIds),
        message,
        suggested_filenames: suggestedFilenames,
      });
      toast.success(`Upload request sent to ${selectedIds.size} team member(s)`);
      onClose();
    } catch {
      toast.error("Failed to send request");
    } finally {
      setSending(false);
    }
  };

  // Pre-select tech leads automatically
  useState(() => {
    const techLeadIds = teamMembers
      .filter((m) => m.roles?.includes("tech_lead"))
      .map((m) => m.id);
    setSelectedIds(new Set(techLeadIds));
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Request Code Upload</DialogTitle>
        </DialogHeader>

        {suggestedFilenames.length > 0 && (
          <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs">
            <p className="font-medium text-amber-800 mb-1">Files needed:</p>
            {suggestedFilenames.map((f) => (
              <code key={f} className="block text-amber-700">{f}</code>
            ))}
          </div>
        )}

        <div className="space-y-2 max-h-48 overflow-y-auto">
          <p className="text-xs font-medium text-gray-500">Select recipients:</p>
          {teamMembers.map((member) => (
            <label key={member.id} className="flex items-center gap-2 cursor-pointer py-1">
              <Checkbox
                checked={selectedIds.has(member.id)}
                onCheckedChange={() => toggle(member.id)}
              />
              <span className="text-sm">{member.name}</span>
              <span className="text-xs text-gray-400 ml-auto">
                {member.roles?.join(", ")}
              </span>
            </label>
          ))}
        </div>

        <Textarea
          placeholder="Optional: add a note for your team..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={2}
          className="text-sm"
        />

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} size="sm">Cancel</Button>
          <Button
            onClick={handleSend}
            disabled={selectedIds.size === 0 || sending}
            size="sm"
          >
            {sending ? "Sending..." : `Send to ${selectedIds.size} member(s)`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

**New hook: `frontend/hooks/useTeamMembers.ts`**

```typescript
// frontend/hooks/useTeamMembers.ts
import useSWR from "swr";
import { apiGet } from "@/lib/api";

export function useTeamMembers(documentId: number) {
  const { data, isLoading } = useSWR(
    documentId ? `/documents/${documentId}/team-members` : null,
    apiGet
  );
  return { teamMembers: data?.team_members ?? [], isLoading };
}
```

**Wire the modal into the document page** — in the document detail page component, add:

```tsx
// Where FileSuggestionBanner is rendered:
const [requestModalOpen, setRequestModalOpen] = useState(false);
const { suggestions } = useSuggestions(documentId);
const unfulfilledNames = suggestions.filter(s => !s.is_fulfilled).map(s => s.filename);

<FileSuggestionBanner
  documentId={documentId}
  onRequestUpload={() => setRequestModalOpen(true)}
/>

<RequestUploadModal
  open={requestModalOpen}
  onClose={() => setRequestModalOpen(false)}
  documentId={documentId}
  suggestedFilenames={unfulfilledNames}
/>
```

### Notification Display (Developer receives)

In the developer's notification bell, the `upload_request` type notification renders as:

```tsx
// In frontend/components/notifications/NotificationItem.tsx
// Add case for upload_request:
case "upload_request": {
  const { suggested_filenames, document_title, requested_by_name } = notification.details ?? {};
  return (
    <div className="text-sm">
      <span className="font-medium">{requested_by_name}</span> needs you to upload{" "}
      <span className="font-mono text-xs bg-gray-100 px-1">
        {suggested_filenames?.join(", ") || "code files"}
      </span>{" "}
      for validation of <span className="font-medium">'{document_title}'</span>.
      <a
        href={`/documents/${notification.resource_id}`}
        className="block mt-1 text-blue-600 text-xs hover:underline"
      >
        Open document →
      </a>
    </div>
  );
}
```

### Test Commands

```bash
# 1. As BA — get team members
curl -H "Authorization: Bearer $BA_TOKEN" \
  http://localhost:8000/api/v1/documents/1/team-members
# Expected: list of users with roles

# 2. Send upload request
curl -X POST -H "Authorization: Bearer $BA_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/documents/1/request-uploads \
  -d '{"user_ids": [3, 5], "suggested_filenames": ["payment_service.py", "fd_service.py"],
       "message": "Needed for sprint 12 validation"}'
# Expected: { "notified_user_ids": [3, 5], "message": "Upload request sent to 2 user(s)" }

# 3. Verify notifications created for those users
psql -c "SELECT user_id, notification_type, title FROM notifications ORDER BY id DESC LIMIT 3"
```

### Risk Assessment
- **Tenant isolation** — user_ids are validated against same tenant; cross-tenant notification impossible
- **Self-notification guard** — sender excluded from valid recipients
- **No new DB schema** — uses existing notifications table; zero migration risk
- **Non-blocking** — notification failures are caught silently by `notify()`


---

## P5C-03 — Request Clarification Workflow (BA ↔ Developer)

**Priority:** P1 — Covers BA Step 8 "ambiguous mismatch → notifies developer", which today has no mechanism.
**Complexity:** MEDIUM — Requires new table, two endpoints, notifications both directions.
**Risk:** LOW — New table, doesn't modify existing mismatch logic.

### Why This Exists

**BA Step 8:** "1 mismatch is ambiguous → click 'Request Clarification' → notifies developer."

Currently the BA has only two choices: Create Jira Ticket or Mark False Positive. When a mismatch is unclear — it might be a real bug, or it might be the AI misreading the code — there is no way to ask the developer "can you check this?". The BA must step outside DokyDoc (Slack, email) to get an answer, breaking the workflow.

The fix: a third mismatch action "Request Clarification" that opens a lightweight Q&A thread. The BA writes a question → developer is notified → developer writes an answer → BA is notified → BA can then act (Create Jira or Mark False Positive).

### DB Changes

**New table: `mismatch_clarifications`**

**New migration: `backend/alembic/versions/s17b1_mismatch_clarifications.py`**

```python
# backend/alembic/versions/s17b1_mismatch_clarifications.py
"""Add mismatch_clarifications table

Revision ID: s17b1
Revises: s17a1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = 's17b1'
down_revision = 's17a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mismatch_clarifications',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('mismatch_id', sa.Integer,
                  sa.ForeignKey('mismatches.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        # Who asked the question (BA)
        sa.Column('requested_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=False),
        # Who is expected to answer (developer/tech lead)
        sa.Column('assignee_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=True),
        # The question from BA
        sa.Column('question', sa.Text, nullable=False),
        # The answer from developer (null until answered)
        sa.Column('answer', sa.Text, nullable=True),
        # Lifecycle: open → answered → closed
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('answered_at', sa.DateTime, nullable=True),
        sa.Column('closed_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_mismatch_clarifications_mismatch_id', 'mismatch_clarifications', ['mismatch_id'])

    # Add CHECK constraint for status
    op.create_check_constraint(
        'ck_clarification_status',
        'mismatch_clarifications',
        "status IN ('open', 'answered', 'closed')"
    )


def downgrade():
    op.drop_table('mismatch_clarifications')
```

### Backend — New Model

**New file: `backend/app/models/mismatch_clarification.py`**

```python
# backend/app/models/mismatch_clarification.py
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .mismatch import Mismatch


class MismatchClarification(Base):
    """
    A clarification request attached to a mismatch.
    BA asks a question → developer answers → BA closes.
    """
    __tablename__ = "mismatch_clarifications"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'answered', 'closed')", name="ck_clarification_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mismatch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mismatches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by_user_id])
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_user_id])
```

**Add to `backend/app/models/__init__.py`:**

```python
from .mismatch_clarification import MismatchClarification  # noqa: F401
```

### Backend — CRUD

**New file: `backend/app/crud/crud_mismatch_clarification.py`**

```python
# backend/app/crud/crud_mismatch_clarification.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.mismatch_clarification import MismatchClarification


class CRUDMismatchClarification:

    def create(
        self,
        db: Session,
        *,
        tenant_id: int,
        mismatch_id: int,
        requested_by_user_id: int,
        assignee_user_id: int | None,
        question: str,
    ) -> MismatchClarification:
        if len(question.strip()) < 10:
            raise ValueError("Question must be at least 10 characters")
        obj = MismatchClarification(
            tenant_id=tenant_id,
            mismatch_id=mismatch_id,
            requested_by_user_id=requested_by_user_id,
            assignee_user_id=assignee_user_id,
            question=question.strip(),
            status="open",
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def answer(
        self,
        db: Session,
        *,
        clarification_id: int,
        tenant_id: int,
        answering_user_id: int,
        answer: str,
    ) -> MismatchClarification:
        obj = db.query(MismatchClarification).filter(
            MismatchClarification.id == clarification_id,
            MismatchClarification.tenant_id == tenant_id,
            MismatchClarification.status == "open",
        ).first()
        if not obj:
            raise ValueError("Clarification not found or already answered")
        if len(answer.strip()) < 5:
            raise ValueError("Answer must be at least 5 characters")
        obj.answer = answer.strip()
        obj.status = "answered"
        obj.answered_at = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def close(
        self,
        db: Session,
        *,
        clarification_id: int,
        tenant_id: int,
        closing_user_id: int,
    ) -> MismatchClarification:
        obj = db.query(MismatchClarification).filter(
            MismatchClarification.id == clarification_id,
            MismatchClarification.tenant_id == tenant_id,
        ).first()
        if not obj:
            raise ValueError("Clarification not found")
        obj.status = "closed"
        obj.closed_at = datetime.utcnow()
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_mismatch(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
    ) -> list[MismatchClarification]:
        return db.query(MismatchClarification).filter(
            MismatchClarification.mismatch_id == mismatch_id,
            MismatchClarification.tenant_id == tenant_id,
        ).order_by(MismatchClarification.created_at.asc()).all()


crud_mismatch_clarification = CRUDMismatchClarification()
```

### Backend — API Endpoints

**Add to `backend/app/api/endpoints/validation.py`:**

```python
from app.crud.crud_mismatch_clarification import crud_mismatch_clarification
from app.models.mismatch_clarification import MismatchClarification


class ClarificationRequest(BaseModel):
    question: str                          # min 10 chars
    assignee_user_id: Optional[int] = None  # developer/tech lead to notify


class ClarificationAnswer(BaseModel):
    answer: str                            # min 5 chars


# POST /validation/mismatches/{id}/clarification
@router.post("/mismatches/{mismatch_id}/clarification", status_code=201)
def request_clarification(
    mismatch_id: int,
    body: ClarificationRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    BA requests clarification from developer on an ambiguous mismatch.
    Creates a clarification record and notifies the assignee.
    """
    from app.services.notification_service import notify
    from app.models.mismatch import Mismatch

    mismatch = db.query(Mismatch).filter(
        Mismatch.id == mismatch_id,
        Mismatch.tenant_id == current_user.tenant_id,
    ).first()
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    try:
        clarification = crud_mismatch_clarification.create(
            db=db,
            tenant_id=current_user.tenant_id,
            mismatch_id=mismatch_id,
            requested_by_user_id=current_user.id,
            assignee_user_id=body.assignee_user_id,
            question=body.question,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Notify the assignee if specified; otherwise notify code component owner
    notify_user_id = body.assignee_user_id or mismatch.owner_id
    if notify_user_id:
        notify(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=notify_user_id,
            notification_type="clarification_requested",
            title=f"Clarification requested on mismatch #{mismatch_id}",
            message=(
                f"{current_user.full_name or current_user.email} has a question: "
                f"{body.question[:200]}"
            ),
            resource_type="mismatch",
            resource_id=mismatch_id,
            details={
                "clarification_id": clarification.id,
                "question": body.question,
                "requested_by": current_user.email,
            },
        )

    return {
        "clarification_id": clarification.id,
        "status": "open",
        "message": "Clarification request created and developer notified",
    }


# POST /validation/mismatches/{id}/clarification/{cid}/answer
@router.post("/mismatches/{mismatch_id}/clarification/{clarification_id}/answer")
def answer_clarification(
    mismatch_id: int,
    clarification_id: int,
    body: ClarificationAnswer,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Developer answers a clarification question. Notifies the BA who asked.
    """
    from app.services.notification_service import notify

    try:
        clarification = crud_mismatch_clarification.answer(
            db=db,
            clarification_id=clarification_id,
            tenant_id=current_user.tenant_id,
            answering_user_id=current_user.id,
            answer=body.answer,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Notify the BA who asked
    notify(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=clarification.requested_by_user_id,
        notification_type="clarification_answered",
        title=f"Clarification answered on mismatch #{mismatch_id}",
        message=(
            f"{current_user.full_name or current_user.email} answered: "
            f"{body.answer[:200]}"
        ),
        resource_type="mismatch",
        resource_id=mismatch_id,
        details={
            "clarification_id": clarification.id,
            "answer": body.answer,
            "answered_by": current_user.email,
        },
    )

    return {
        "clarification_id": clarification.id,
        "status": "answered",
        "answer": clarification.answer,
    }


# GET /validation/mismatches/{id}/clarifications
@router.get("/mismatches/{mismatch_id}/clarifications")
def get_clarifications(
    mismatch_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """Return all clarification threads for a mismatch."""
    items = crud_mismatch_clarification.get_by_mismatch(
        db=db,
        mismatch_id=mismatch_id,
        tenant_id=current_user.tenant_id,
    )
    return {
        "mismatch_id": mismatch_id,
        "clarifications": [
            {
                "id": c.id,
                "question": c.question,
                "answer": c.answer,
                "status": c.status,
                "requested_by_user_id": c.requested_by_user_id,
                "assignee_user_id": c.assignee_user_id,
                "created_at": c.created_at.isoformat(),
                "answered_at": c.answered_at.isoformat() if c.answered_at else None,
            }
            for c in items
        ],
    }
```

### Frontend — Clarification Panel on Mismatch Card

**New file: `frontend/components/validation/MismatchClarificationPanel.tsx`**

```tsx
// frontend/components/validation/MismatchClarificationPanel.tsx
import { useState } from "react";
import { MessageSquare, Send, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useClarifications } from "@/hooks/useClarifications";
import { apiPost } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  mismatchId: number;
  teamMembers: { id: number; name: string; roles: string[] }[];
}

export function MismatchClarificationPanel({ mismatchId, teamMembers }: Props) {
  const { clarifications, mutate } = useClarifications(mismatchId);
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [assigneeId, setAssigneeId] = useState<number | null>(null);
  const [sending, setSending] = useState(false);

  const handleAsk = async () => {
    if (question.trim().length < 10) {
      toast.error("Question must be at least 10 characters");
      return;
    }
    setSending(true);
    try {
      await apiPost(`/validation/mismatches/${mismatchId}/clarification`, {
        question,
        assignee_user_id: assigneeId,
      });
      toast.success("Clarification request sent");
      setQuestion("");
      setOpen(false);
      mutate();
    } catch {
      toast.error("Failed to send clarification request");
    } finally {
      setSending(false);
    }
  };

  const openCount = clarifications.filter((c) => c.status === "open").length;

  return (
    <div className="border-t pt-3 mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <MessageSquare className="h-4 w-4" />
        Request Clarification
        {openCount > 0 && (
          <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
            {openCount} open
          </span>
        )}
      </button>

      {/* Existing clarification threads */}
      {clarifications.map((c) => (
        <div key={c.id} className="mt-3 rounded-md border border-gray-200 p-3 text-xs space-y-2">
          <div className="flex items-start gap-2">
            <MessageSquare className="h-3.5 w-3.5 text-blue-500 mt-0.5" />
            <div>
              <span className="font-medium text-gray-700">Question: </span>
              <span className="text-gray-600">{c.question}</span>
            </div>
          </div>
          {c.answer ? (
            <div className="flex items-start gap-2 pl-4">
              <CheckCircle className="h-3.5 w-3.5 text-green-500 mt-0.5" />
              <div>
                <span className="font-medium text-gray-700">Answer: </span>
                <span className="text-gray-600">{c.answer}</span>
              </div>
            </div>
          ) : (
            <p className="pl-4 text-gray-400 italic">Awaiting developer response...</p>
          )}
          <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
            c.status === "answered" ? "bg-green-100 text-green-700" :
            c.status === "open" ? "bg-blue-100 text-blue-700" :
            "bg-gray-100 text-gray-500"
          }`}>
            {c.status}
          </span>
        </div>
      ))}

      {/* New question form */}
      {open && (
        <div className="mt-3 space-y-2">
          <select
            value={assigneeId ?? ""}
            onChange={(e) => setAssigneeId(e.target.value ? Number(e.target.value) : null)}
            className="w-full text-xs border rounded p-1.5"
          >
            <option value="">— Select developer to notify —</option>
            {teamMembers.map((m) => (
              <option key={m.id} value={m.id}>{m.name} ({m.roles?.join(", ")})</option>
            ))}
          </select>
          <Textarea
            placeholder="What do you need clarified? (min 10 chars)"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            className="text-xs"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAsk} disabled={sending}>
              <Send className="h-3.5 w-3.5 mr-1" />
              {sending ? "Sending..." : "Ask Developer"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**New hook: `frontend/hooks/useClarifications.ts`**

```typescript
// frontend/hooks/useClarifications.ts
import useSWR from "swr";
import { apiGet } from "@/lib/api";

export function useClarifications(mismatchId: number) {
  const { data, isLoading, mutate } = useSWR(
    mismatchId ? `/validation/mismatches/${mismatchId}/clarifications` : null,
    apiGet
  );
  return {
    clarifications: data?.clarifications ?? [],
    isLoading,
    mutate,
  };
}
```

**Wire into mismatch card** — in whatever component renders a mismatch card, add at the bottom alongside the False Positive and Create Jira buttons:

```tsx
<MismatchClarificationPanel
  mismatchId={mismatch.id}
  teamMembers={teamMembers}
/>
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s17b1

# 2. Verify table
psql -c "\d mismatch_clarifications"

# 3. Create clarification as BA
curl -X POST -H "Authorization: Bearer $BA_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/validation/mismatches/5/clarification \
  -d '{"question": "Is the FD rate calculated before or after tax?", "assignee_user_id": 3}'
# Expected: { "clarification_id": 1, "status": "open" }

# 4. Verify notification sent to developer
psql -c "SELECT notification_type, title, user_id FROM notifications ORDER BY id DESC LIMIT 1"

# 5. Developer answers
curl -X POST -H "Authorization: Bearer $DEV_TOKEN" \
  http://localhost:8000/api/v1/validation/mismatches/5/clarification/1/answer \
  -d '{"answer": "The rate is pre-tax; post-tax calculation is in the tax_service.py"}'
# Expected: { "status": "answered" }

# 6. Verify BA gets notified
psql -c "SELECT notification_type, user_id FROM notifications ORDER BY id DESC LIMIT 1"

# 7. Fetch all clarifications
curl -H "Authorization: Bearer $BA_TOKEN" \
  http://localhost:8000/api/v1/validation/mismatches/5/clarifications
```

### Risk Assessment
- **Cascade delete** — `ON DELETE CASCADE` on `mismatch_id` FK; clarifications auto-deleted if mismatch removed
- **Status CHECK constraint** — enforced at DB layer; prevents invalid status values
- **Minimum length validation** — question ≥10 chars, answer ≥5 chars enforced in CRUD
- **Assignee validation** — assignee_user_id is optional; defaults to mismatch owner_id if unset
- **Notification failure** — `notify()` is already wrapped in try/except; never blocks the main action


---

## P5C-04 — UAT Checklist Auto-generation + QA Sign-off

**Priority:** P1 — Covers BA Steps 11-12 and QA Steps 7-8. Without this, "manual UAT" has no tracking surface inside DokyDoc.
**Complexity:** MEDIUM — New table, classification logic in atomization prompt, new UI tab.
**Risk:** LOW — Additive; doesn't change validation engine.

### Why This Exists

**BA Step 11:** "Opens UAT checklist (auto-generated from atoms)."
**BA Step 12:** "Does UAT on the 9 behavioral requirements DokyDoc couldn't verify."
**QA Step 7:** "Focuses manual effort on behavioral tests, UX, edge cases (the 9 atoms DokyDoc couldn't auto-test)."
**QA Step 8:** "Signs off each manual check in DokyDoc UAT checklist."

DokyDoc can auto-validate API contracts, DB values, and business rules. But some requirements — user experience flows, behavioral edge cases, performance under real load — need a human. There is currently no way to:
1. Know WHICH atoms need manual testing
2. Track whether manual testing was done
3. Close the loop between QA sign-off and BRD compliance

The fix: atoms get a `testability` field (`static` / `runtime` / `manual`) assigned during atomization. A UAT checklist is auto-generated from `manual` atoms. QA or BA checks them off with notes. This data feeds into the compliance score.

### DB Changes

The `testability` column on `requirement_atoms` was already added in migration `s17a1` (P5C-01).

**New table: `uat_checklist_items`**

**New migration: `backend/alembic/versions/s17c1_uat_checklist.py`**

```python
# backend/alembic/versions/s17c1_uat_checklist.py
"""Add uat_checklist_items table

Revision ID: s17c1
Revises: s17b1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = 's17c1'
down_revision = 's17b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'uat_checklist_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        # The atom this checklist item tests
        sa.Column('atom_id', sa.Integer,
                  sa.ForeignKey('requirement_atoms.id', ondelete='CASCADE'),
                  nullable=False),
        # Who completed this manual check (null = not yet checked)
        sa.Column('checked_by_user_id', sa.Integer,
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('checked_at', sa.DateTime, nullable=True),
        # QA/BA notes about how they tested it and what they found
        sa.Column('notes', sa.Text, nullable=True),
        # Result: pass / fail / blocked
        sa.Column('result', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_uat_checklist_document_id', 'uat_checklist_items', ['document_id'])
    op.create_check_constraint(
        'ck_uat_result',
        'uat_checklist_items',
        "result IS NULL OR result IN ('pass', 'fail', 'blocked')"
    )


def downgrade():
    op.drop_table('uat_checklist_items')
```

### Backend — New Model

**New file: `backend/app/models/uat_checklist_item.py`**

```python
# backend/app/models/uat_checklist_item.py
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base


class UATChecklistItem(Base):
    """
    One manual UAT test item, linked to a 'manual' testability atom.
    Created automatically after atomization. QA/BA checks off with result + notes.
    """
    __tablename__ = "uat_checklist_items"
    __table_args__ = (
        CheckConstraint(
            "result IS NULL OR result IN ('pass', 'fail', 'blocked')",
            name="ck_uat_result"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_atoms.id", ondelete="CASCADE"), nullable=False
    )
    checked_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    atom: Mapped["RequirementAtom"] = relationship("RequirementAtom")
```

**Add to `backend/app/models/__init__.py`:**

```python
from .uat_checklist_item import UATChecklistItem  # noqa: F401
```

### Backend — Testability Classification in Atomization Prompt

**In `backend/app/services/ai/gemini.py`**, in `call_gemini_for_atomization`, the atomization JSON schema gains a new field:

**Current schema returned per atom:**
```json
{ "atom_id": "REQ-001", "atom_type": "...", "content": "...", "criticality": "..." }
```

**Updated schema (add `testability` field to the prompt instruction):**

```python
# In the atomization prompt, add this to the atom extraction instruction:
_ATOMIZATION_TESTABILITY_INSTRUCTION = """
For each atom, also set the "testability" field:
- "static": Can be verified by reading code (API contracts, DB values, calculations, field validations,
  class existence, method signatures, constants). DokyDoc can auto-validate these.
- "runtime": Requires executing the code (response time, memory usage, concurrent user load,
  retry behavior, timeout handling). Can be validated by automated integration/load tests.
- "manual": Requires human judgment (UX workflows, user experience quality, accessibility,
  visual design, business process correctness that depends on real-world context,
  edge cases with ambiguous expected output). DokyDoc CANNOT auto-validate these.

Classify conservatively: if in doubt whether static validation would catch it, classify as "manual".
"""
```

**In `create_atoms_bulk` in `backend/app/crud/crud_requirement_atom.py`**, accept `testability` underscore key:

```python
# Current line handles _atom_type, _criticality etc. Add:
atom_obj.testability = atom_data.get("_testability") or atom_data.get("testability") or "manual"
```

### Backend — Auto-create Checklist After Atomization

**In `backend/app/tasks/document_pipeline.py`**, after `file_suggestion_service.generate_and_store()` (P5C-01 hook), add:

```python
# PHASE 5C: Auto-create UAT checklist for manual-testability atoms
try:
    from app.models.requirement_atom import RequirementAtom
    from app.models.uat_checklist_item import UATChecklistItem

    # Delete stale checklist items for this document
    db.query(UATChecklistItem).filter_by(
        document_id=document.id,
        tenant_id=document.tenant_id,
    ).delete()

    manual_atoms = db.query(RequirementAtom).filter(
        RequirementAtom.document_id == document.id,
        RequirementAtom.tenant_id == document.tenant_id,
        RequirementAtom.testability == "manual",
    ).all()

    for atom in manual_atoms:
        db.add(UATChecklistItem(
            tenant_id=document.tenant_id,
            document_id=document.id,
            atom_id=atom.id,
        ))
    db.commit()
    logger.info(f"Created {len(manual_atoms)} UAT checklist items for document {document.id}")
except Exception as e:
    logger.warning(f"UAT checklist creation failed (non-fatal): {e}")
```

### Backend — API Endpoints

**Add to `backend/app/api/endpoints/validation.py`:**

```python
from app.models.uat_checklist_item import UATChecklistItem
from app.models.requirement_atom import RequirementAtom


class UATCheckBody(BaseModel):
    result: str               # "pass" | "fail" | "blocked"
    notes: Optional[str] = None


# GET /validation/{document_id}/uat-checklist
@router.get("/{document_id}/uat-checklist")
def get_uat_checklist(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return all UAT checklist items for a document (manual-testability atoms only).
    Shows which have been checked and which are still pending.
    """
    items = (
        db.query(UATChecklistItem, RequirementAtom)
        .join(RequirementAtom, UATChecklistItem.atom_id == RequirementAtom.id)
        .filter(
            UATChecklistItem.document_id == document_id,
            UATChecklistItem.tenant_id == current_user.tenant_id,
        )
        .all()
    )

    total = len(items)
    checked = sum(1 for item, _ in items if item.result is not None)
    passed = sum(1 for item, _ in items if item.result == "pass")
    failed = sum(1 for item, _ in items if item.result == "fail")

    return {
        "document_id": document_id,
        "summary": {
            "total": total,
            "checked": checked,
            "pending": total - checked,
            "passed": passed,
            "failed": failed,
            "completion_pct": round(checked / total * 100) if total > 0 else 0,
        },
        "items": [
            {
                "id": item.id,
                "atom_id": atom.atom_id,
                "atom_type": atom.atom_type,
                "content": atom.content,
                "criticality": atom.criticality,
                "result": item.result,
                "notes": item.notes,
                "checked_by_user_id": item.checked_by_user_id,
                "checked_at": item.checked_at.isoformat() if item.checked_at else None,
            }
            for item, atom in items
        ],
    }


# POST /validation/{document_id}/uat-checklist/{item_id}/check
@router.post("/{document_id}/uat-checklist/{item_id}/check")
def check_uat_item(
    document_id: int,
    item_id: int,
    body: UATCheckBody,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    BA or QA marks a UAT checklist item as pass/fail/blocked with notes.
    """
    if body.result not in ("pass", "fail", "blocked"):
        raise HTTPException(status_code=422, detail="result must be pass, fail, or blocked")

    item = db.query(UATChecklistItem).filter(
        UATChecklistItem.id == item_id,
        UATChecklistItem.document_id == document_id,
        UATChecklistItem.tenant_id == current_user.tenant_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="UAT checklist item not found")

    item.result = body.result
    item.notes = body.notes
    item.checked_by_user_id = current_user.id
    item.checked_at = datetime.utcnow()
    db.add(item)
    db.commit()

    return {
        "id": item_id,
        "result": body.result,
        "checked_at": item.checked_at.isoformat(),
        "message": f"UAT item marked as {body.result}",
    }
```

### Frontend — UAT Checklist Tab on Validation Panel

**New file: `frontend/components/validation/UATChecklist.tsx`**

```tsx
// frontend/components/validation/UATChecklist.tsx
import { useState } from "react";
import { CheckCircle, XCircle, MinusCircle, Clock } from "lucide-react";
import { useUATChecklist } from "@/hooks/useUATChecklist";
import { apiPost } from "@/lib/api";
import { toast } from "sonner";

const RESULT_CONFIG = {
  pass: { icon: CheckCircle, color: "text-green-600", bg: "bg-green-50", label: "Pass" },
  fail: { icon: XCircle, color: "text-red-600", bg: "bg-red-50", label: "Fail" },
  blocked: { icon: MinusCircle, color: "text-amber-600", bg: "bg-amber-50", label: "Blocked" },
};

interface Props {
  documentId: number;
}

export function UATChecklist({ documentId }: Props) {
  const { checklist, isLoading, mutate } = useUATChecklist(documentId);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});

  const handleCheck = async (itemId: number, result: "pass" | "fail" | "blocked") => {
    try {
      await apiPost(`/validation/${documentId}/uat-checklist/${itemId}/check`, {
        result,
        notes: notes[itemId] || null,
      });
      toast.success(`Marked as ${result}`);
      mutate();
    } catch {
      toast.error("Failed to update UAT item");
    }
  };

  if (isLoading) return <div className="text-sm text-gray-400 p-4">Loading UAT checklist...</div>;

  const { summary, items } = checklist;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total", value: summary?.total, color: "text-gray-700" },
          { label: "Pending", value: summary?.pending, color: "text-amber-600" },
          { label: "Passed", value: summary?.passed, color: "text-green-600" },
          { label: "Failed", value: summary?.failed, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="text-center rounded-lg border p-3">
            <div className={`text-2xl font-bold ${color}`}>{value ?? 0}</div>
            <div className="text-xs text-gray-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-500">
          <span>UAT Progress</span>
          <span>{summary?.completion_pct ?? 0}% complete</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all"
            style={{ width: `${summary?.completion_pct ?? 0}%` }}
          />
        </div>
      </div>

      {/* Checklist items */}
      <div className="space-y-2">
        {items?.map((item) => (
          <div
            key={item.id}
            className={`border rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-colors ${
              item.result ? RESULT_CONFIG[item.result as keyof typeof RESULT_CONFIG].bg : ""
            }`}
            onClick={() => setExpanded(expanded === item.id ? null : item.id)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2 min-w-0">
                {item.result ? (
                  (() => {
                    const cfg = RESULT_CONFIG[item.result as keyof typeof RESULT_CONFIG];
                    return <cfg.icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${cfg.color}`} />;
                  })()
                ) : (
                  <Clock className="h-4 w-4 mt-0.5 text-gray-400 flex-shrink-0" />
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-gray-500">{item.atom_id}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 rounded">{item.atom_type}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      item.criticality === "critical" ? "bg-red-100 text-red-700" :
                      item.criticality === "high" ? "bg-orange-100 text-orange-700" :
                      "bg-gray-100 text-gray-600"
                    }`}>
                      {item.criticality}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 mt-1 line-clamp-2">{item.content}</p>
                </div>
              </div>
            </div>

            {expanded === item.id && (
              <div className="mt-3 pt-3 border-t space-y-2" onClick={(e) => e.stopPropagation()}>
                <textarea
                  placeholder="Testing notes (optional)..."
                  value={notes[item.id] || item.notes || ""}
                  onChange={(e) => setNotes((prev) => ({ ...prev, [item.id]: e.target.value }))}
                  className="w-full text-xs border rounded p-2 h-16 resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleCheck(item.id, "pass")}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> Pass
                  </button>
                  <button
                    onClick={() => handleCheck(item.id, "fail")}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-red-600 text-white text-xs rounded hover:bg-red-700"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Fail
                  </button>
                  <button
                    onClick={() => handleCheck(item.id, "blocked")}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-amber-500 text-white text-xs rounded hover:bg-amber-600"
                  >
                    <MinusCircle className="h-3.5 w-3.5" /> Blocked
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**New hook: `frontend/hooks/useUATChecklist.ts`**

```typescript
// frontend/hooks/useUATChecklist.ts
import useSWR from "swr";
import { apiGet } from "@/lib/api";

export function useUATChecklist(documentId: number) {
  const { data, isLoading, mutate } = useSWR(
    documentId ? `/validation/${documentId}/uat-checklist` : null,
    apiGet
  );
  return { checklist: data ?? { summary: {}, items: [] }, isLoading, mutate };
}
```

**Wire UAT Checklist as a tab on the validation panel** — in the validation panel component, add:

```tsx
// In the tab list (alongside "Mismatches", "Coverage Matrix"):
<TabsTrigger value="uat">
  UAT Checklist
  {checklist.summary?.pending > 0 && (
    <span className="ml-1 px-1.5 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full">
      {checklist.summary.pending}
    </span>
  )}
</TabsTrigger>

// In the tab content:
<TabsContent value="uat">
  <UATChecklist documentId={documentId} />
</TabsContent>
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s17c1

# 2. Verify table
psql -c "\d uat_checklist_items"
psql -c "\d requirement_atoms" | grep testability

# 3. After uploading a BRD document, check testability was assigned
psql -c "SELECT atom_id, atom_type, testability FROM requirement_atoms WHERE document_id=1 LIMIT 10"

# 4. Check UAT checklist items were auto-created
psql -c "SELECT COUNT(*) FROM uat_checklist_items WHERE document_id=1"

# 5. Test API
curl -H "Authorization: Bearer $QA_TOKEN" \
  http://localhost:8000/api/v1/validation/1/uat-checklist
# Expected: { "summary": { "total": 9, "pending": 9, "passed": 0 }, "items": [...] }

# 6. Check off an item
curl -X POST -H "Authorization: Bearer $QA_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/validation/1/uat-checklist/3/check \
  -d '{"result": "pass", "notes": "Tested manually on staging, works correctly"}'
# Expected: { "result": "pass", "checked_at": "..." }

# 7. Verify completion percentage updated
curl -H "Authorization: Bearer $QA_TOKEN" \
  http://localhost:8000/api/v1/validation/1/uat-checklist | jq .summary
```

### Risk Assessment
- **Re-atomization safe** — checklist items are deleted + recreated on each atomization
- **Cascade delete** — `ON DELETE CASCADE` on both `document_id` and `atom_id` FKs
- **Result CHECK constraint** — enforced at DB layer (`pass / fail / blocked` only)
- **Testability default** — atoms without `testability` field default to `"manual"` (conservative)
- **Sign-off integration** — P5B-12 BA sign-off can optionally check if UAT checklist is 100% complete before allowing sign-off (extend the pre-check in P5B-12's sign-off endpoint)


---

## P5C-05 — Auto-generated Test Suite Download

**Priority:** P1 — Covers QA Steps 3-4: "Downloads generated test suite and drops into CI pipeline."
**Complexity:** HIGH — Gemini generates code (pytest files) rather than JSON; requires zip packaging.
**Risk:** MEDIUM — Generated tests are advisory; QA reviews before running. No production DB writes.

### Why This Exists

**QA Step 3:** "Downloads generated test suite: `test_fd_contract.py`, `test_fd_integration.py`, `test_fd_values.py`."
**QA Step 4:** "Drops test files into CI pipeline (GitHub Actions)."

Currently QA must write all tests by hand. Each BRD atom that is `testability = "static"` or `"runtime"` can have a pytest test generated from it automatically. This saves QA significant time for contract tests (does the endpoint exist? does it return the right status? does the field accept/reject edge case values?).

The feature: QA clicks "Generate Test Suite" on the validation panel → Gemini generates one pytest test function per atom → DokyDoc packages them into a `.zip` → QA downloads.

### No New DB Changes

No new table needed. Uses existing:
- `requirement_atoms` (with `testability` field from P5C-01/P5C-04)
- `documents` (for document context)

One JSONB field added to documents for caching generated tests:

```python
# Add to existing s17a1 migration OR add a column directly:
# documents.last_test_suite_generated_at  (DateTime, nullable)
# Store generated test content as a Celery task artifact; don't store in DB (too large)
```

No migration needed beyond s17a1's `testability` column. The test generation is stateless — triggered on demand, result returned as a file download.

### Backend — Gemini Prompt for Test Generation

**Add to `backend/app/services/ai/gemini.py`:**

```python
_TEST_GENERATION_PROMPT_TEMPLATE = """
You are a senior Python QA engineer. Generate a pytest test function for the following BRD requirement atom.

ATOM:
  ID: {atom_id}
  Type: {atom_type}
  Content: {content}
  Criticality: {criticality}
  Testability: {testability}

GUIDELINES BY ATOM TYPE:
- API_CONTRACT: Test the HTTP endpoint exists, returns correct status code, and validates response schema.
  Use httpx or requests. Mock authentication. Assert response fields.
- BUSINESS_RULE: Test the calculation/condition with valid and boundary inputs. Pure function tests.
  Include happy path, edge cases (min/max values), and invalid inputs.
- DATA_CONSTRAINT: Test field validation — valid values pass, invalid values fail (400 or validation error).
- FUNCTIONAL_REQUIREMENT: Test that the system capability exists and produces expected output.
- ERROR_SCENARIO: Test that the error case is handled correctly — verify error code and message.
- INTEGRATION_POINT: Test the integration call is made with correct parameters (use mocks/patches).
- SECURITY_REQUIREMENT: Test that unauthorized access returns 401/403. Test that sensitive data is not exposed.
- NFR: Test performance — use time.time() to assert operation completes within the SLA.
- WORKFLOW_STEP: Test that the workflow step transitions correctly (mock external dependencies).

RULES:
1. Generate EXACTLY ONE pytest function named test_{atom_id_snake}_{short_description}
2. Include clear ARRANGE/ACT/ASSERT comments
3. If HTTP endpoint test: use BASE_URL env var: BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
4. Include realistic test data based on the BRD content
5. Add a docstring quoting the original BRD requirement
6. For "runtime" testability: add a pytest.mark.integration marker
7. DO NOT import from the source code directly — test via HTTP or public interface
8. Keep the function under 50 lines

Return ONLY the Python code for the test function, no markdown fences.
"""


async def call_gemini_for_test_generation(
    atom: dict,
    model: str = "gemini-2.0-flash",
) -> str:
    """
    Generate a pytest test function for a single BRD atom.
    Returns raw Python code string.
    """
    import google.generativeai as genai
    from app.core.config import settings

    prompt = _TEST_GENERATION_PROMPT_TEMPLATE.format(
        atom_id=atom["atom_id"],
        atom_type=atom["atom_type"],
        content=atom["content"],
        criticality=atom.get("criticality", "standard"),
        testability=atom.get("testability", "static"),
    )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model_client = genai.GenerativeModel(model)
    response = model_client.generate_content(
        prompt,
        generation_config={"temperature": 0.2},
    )
    return response.text.strip()
```

### Backend — Test Suite Generation Service

**New file: `backend/app/services/test_suite_service.py`**

```python
# backend/app/services/test_suite_service.py
"""
TestSuiteService — generates downloadable pytest test files from BRD atoms.

Atoms classified as "static" or "runtime" testability get test functions.
Tests are grouped into files by atom_type and returned as an in-memory zip.
"""
import io
import zipfile
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.requirement_atom import RequirementAtom

logger = get_logger("test_suite_service")

# Group atom types into test files
_FILE_GROUPS = {
    "test_contracts.py": ["API_CONTRACT", "INTEGRATION_POINT"],
    "test_business_rules.py": ["BUSINESS_RULE", "DATA_CONSTRAINT"],
    "test_functional.py": ["FUNCTIONAL_REQUIREMENT", "WORKFLOW_STEP"],
    "test_security.py": ["SECURITY_REQUIREMENT"],
    "test_error_handling.py": ["ERROR_SCENARIO"],
    "test_nfr.py": ["NFR"],
}

_FILE_HEADER = '''"""
Auto-generated test suite by DokyDoc.
Document: {doc_title}
Generated: {generated_at}
WARNING: Review before running. These tests are AI-generated from BRD requirements.
"""
import os
import time
import pytest
import httpx

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")

HEADERS = {{"Authorization": f"Bearer {{AUTH_TOKEN}}"}}
'''


class TestSuiteService:

    async def generate_zip(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        doc_title: str,
    ) -> bytes:
        """
        Generate all test files and return as a zip bytes object.
        """
        from app.services.ai.gemini import call_gemini_for_test_generation
        from datetime import datetime

        atoms = db.query(RequirementAtom).filter(
            RequirementAtom.document_id == document_id,
            RequirementAtom.tenant_id == tenant_id,
            RequirementAtom.testability.in_(["static", "runtime"]),
        ).all()

        if not atoms:
            # Return a zip with a README explaining no testable atoms found
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("README.txt", "No auto-testable atoms found in this document.")
            return buf.getvalue()

        # Map atom_type → file group
        type_to_file = {}
        for filename, types in _FILE_GROUPS.items():
            for t in types:
                type_to_file[t] = filename

        # Generate test function for each atom
        file_contents: dict[str, list[str]] = {k: [] for k in _FILE_GROUPS}
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        for atom in atoms:
            target_file = type_to_file.get(atom.atom_type, "test_functional.py")
            try:
                test_code = await call_gemini_for_test_generation({
                    "atom_id": atom.atom_id,
                    "atom_type": atom.atom_type,
                    "content": atom.content,
                    "criticality": atom.criticality,
                    "testability": atom.testability or "static",
                })
                file_contents[target_file].append(f"\n\n{test_code}")
            except Exception as e:
                logger.warning(f"Test generation failed for atom {atom.atom_id}: {e}")
                # Write a placeholder test
                snake = atom.atom_id.lower().replace("-", "_")
                file_contents[target_file].append(
                    f'\n\n@pytest.mark.skip(reason="AI generation failed")\n'
                    f'def test_{snake}_placeholder():\n'
                    f'    """BRD requirement: {atom.content[:100]}..."""\n'
                    f'    pass\n'
                )

        # Build zip
        buf = io.BytesIO()
        header_fmt = _FILE_HEADER.format(doc_title=doc_title, generated_at=generated_at)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, functions in file_contents.items():
                if not functions:
                    continue
                content = header_fmt + "".join(functions)
                zf.writestr(f"dokydoc_tests/{filename}", content)

            # Add conftest.py and pytest.ini
            zf.writestr("dokydoc_tests/conftest.py", _CONFTEST)
            zf.writestr("pytest.ini", _PYTEST_INI)

        return buf.getvalue()


_CONFTEST = '''"""
Shared fixtures for DokyDoc auto-generated test suite.
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {AUTH_TOKEN}"}) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}
'''

_PYTEST_INI = """[pytest]
markers =
    integration: marks tests as integration tests (require running app)
    slow: marks tests as slow (performance tests)
testpaths = dokydoc_tests
"""

test_suite_service = TestSuiteService()
```

### Backend — Celery Task (Async Generation)

**Add to `backend/app/tasks/document_pipeline.py`** or create a new file `backend/app/tasks/test_generation_tasks.py`:

```python
# backend/app/tasks/test_generation_tasks.py
import asyncio
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("test_generation_tasks")


@celery_app.task(name="generate_test_suite", bind=True, max_retries=2)
def generate_test_suite(self, document_id: int, tenant_id: int, doc_title: str):
    """
    Celery task: generate test suite zip and store result path in Redis.
    Result stored under key: test_suite:{document_id}:{tenant_id}
    """
    import asyncio
    import tempfile
    import os
    from app.db.session import SessionLocal
    from app.services.test_suite_service import test_suite_service
    from app.core.redis import get_redis_client

    db = SessionLocal()
    try:
        zip_bytes = asyncio.run(
            test_suite_service.generate_zip(
                db=db,
                document_id=document_id,
                tenant_id=tenant_id,
                doc_title=doc_title,
            )
        )
        # Store in Redis with 1-hour TTL
        redis = get_redis_client()
        redis_key = f"test_suite:{document_id}:{tenant_id}"
        redis.set(redis_key, zip_bytes, ex=3600)
        logger.info(f"Test suite generated for document {document_id}, {len(zip_bytes)} bytes")
    except Exception as exc:
        logger.error(f"Test suite generation failed: {exc}")
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
```

### Backend — API Endpoints

**Add to `backend/app/api/endpoints/validation.py`:**

```python
from fastapi.responses import StreamingResponse
import io


# POST /validation/{document_id}/generate-tests  (async trigger)
@router.post("/{document_id}/generate-tests", status_code=202)
def trigger_test_suite_generation(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Trigger async test suite generation for a document.
    QA polls GET /download-tests until 200 is returned.
    """
    from app.models.document import Document
    from app.tasks.test_generation_tasks import generate_test_suite

    doc = db.get(Document, document_id)
    if not doc or doc.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")

    task = generate_test_suite.apply_async(
        args=[document_id, current_user.tenant_id, doc.title or "Untitled"]
    )
    return {"task_id": task.id, "status": "generating", "poll_url": f"/validation/{document_id}/download-tests"}


# GET /validation/{document_id}/download-tests
@router.get("/{document_id}/download-tests")
def download_test_suite(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Download the generated test suite zip. Returns 202 if still generating, 200 + zip if ready.
    """
    from app.core.redis import get_redis_client

    redis = get_redis_client()
    redis_key = f"test_suite:{document_id}:{current_user.tenant_id}"
    zip_bytes = redis.get(redis_key)

    if not zip_bytes:
        return JSONResponse(
            status_code=202,
            content={"status": "generating", "message": "Test suite is being generated. Try again in 30 seconds."},
        )

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=dokydoc_tests_doc{document_id}.zip"},
    )
```

### Frontend — "Generate Test Suite" Button on Validation Panel

**Add to the validation panel** (near UAT checklist tab or as a standalone button):

```tsx
// frontend/components/validation/TestSuiteDownload.tsx
import { useState } from "react";
import { Download, Loader2, FileCode } from "lucide-react";
import { apiPost, apiGetRaw } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  documentId: number;
}

export function TestSuiteDownload({ documentId }: Props) {
  const [status, setStatus] = useState<"idle" | "generating" | "ready">("idle");

  const handleGenerate = async () => {
    setStatus("generating");
    try {
      await apiPost(`/validation/${documentId}/generate-tests`, {});

      // Poll until ready (max 2 minutes)
      const startTime = Date.now();
      const poll = async () => {
        if (Date.now() - startTime > 120_000) {
          toast.error("Test suite generation timed out");
          setStatus("idle");
          return;
        }
        const resp = await apiGetRaw(`/validation/${documentId}/download-tests`);
        if (resp.status === 200) {
          // Trigger download
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `dokydoc_tests_doc${documentId}.zip`;
          a.click();
          URL.revokeObjectURL(url);
          setStatus("idle");
          toast.success("Test suite downloaded successfully");
        } else {
          // Still generating — retry in 5 seconds
          setTimeout(poll, 5000);
        }
      };
      await poll();
    } catch {
      toast.error("Failed to generate test suite");
      setStatus("idle");
    }
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed border-gray-300 bg-gray-50">
      <FileCode className="h-5 w-5 text-gray-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-700">Auto-generated Test Suite</p>
        <p className="text-xs text-gray-500">
          Pytest files generated from BRD atoms · Drop into CI pipeline
        </p>
      </div>
      <button
        onClick={handleGenerate}
        disabled={status === "generating"}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {status === "generating" ? (
          <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating...</>
        ) : (
          <><Download className="h-3.5 w-3.5" /> Download Tests</>
        )}
      </button>
    </div>
  );
}
```

### Test Commands

```bash
# 1. Verify testability column exists (from s17a1)
psql -c "SELECT atom_id, testability FROM requirement_atoms WHERE document_id=1 LIMIT 5"

# 2. Trigger test generation
curl -X POST -H "Authorization: Bearer $QA_TOKEN" \
  http://localhost:8000/api/v1/validation/1/generate-tests
# Expected: { "task_id": "...", "status": "generating" }

# 3. Poll for completion
curl -H "Authorization: Bearer $QA_TOKEN" \
  http://localhost:8000/api/v1/validation/1/download-tests
# Expected: initially 202, then 200 + zip file after Celery task completes

# 4. Inspect generated zip
# After download: unzip dokydoc_tests_doc1.zip -d /tmp/tests
# ls /tmp/tests/dokydoc_tests/
# Expected: test_contracts.py, test_business_rules.py, conftest.py, etc.

# 5. Run generated tests locally
# cd /tmp/tests && APP_BASE_URL=http://localhost:8000 pytest dokydoc_tests/ -v

# 6. Verify Redis key is set
redis-cli get test_suite:1:1 | wc -c  # should be > 0 bytes
```

### Risk Assessment
- **Generated code is advisory** — clearly labeled "AI-generated, review before running"; no auto-execution
- **Redis TTL 1 hour** — prevents stale test suites from being downloaded after BRD changes
- **Celery task + polling** — non-blocking; UI polls; no server-sent events needed
- **Atom cap** — if document has >100 testable atoms, Gemini calls are made per-atom; consider batching or limiting to top 50 by criticality for initial release
- **Import isolation** — generated tests only call via HTTP, never import source code directly; prevents import errors on QA machines


---

## P5C-06 — CI Test Result Webhook → Runtime Mismatch Auto-creation

**Priority:** P1 — Covers QA Step 6: "CI runs, test fails, DokyDoc receives result via webhook, auto-creates mismatch."
**Complexity:** HIGH — New webhook endpoint with secret-based auth, mismatch auto-creation, atom matching.
**Risk:** MEDIUM — New endpoint; doesn't touch existing validation engine.

### Why This Exists

**QA Step 6:** "Test failure → DokyDoc receives result via webhook → auto-creates mismatch: 'Runtime test failed: FD rate returns 6%'."

The existing GitHub webhook (P5B-06) triggers re-analysis on code push. But CI test results are different: a test runner (GitHub Actions, Jenkins, CircleCI) executes the auto-generated tests and sends failures back to DokyDoc. DokyDoc should create a new mismatch type `runtime_test_failure` when a test fails, linking it to the relevant BRD atom.

This closes the loop: DokyDoc generates tests (P5C-05) → CI runs them → failures come back → DokyDoc creates mismatches → developer fixes → mismatch auto-closes on next CI pass.

### DB Changes

**New table: `ci_webhook_configs`** — stores per-tenant CI webhook secret keys.

**New migration: `backend/alembic/versions/s17e1_ci_webhook_config.py`**

```python
# backend/alembic/versions/s17e1_ci_webhook_config.py
"""Add ci_webhook_configs table

Revision ID: s17e1
Revises: s17d1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = 's17e1'
down_revision = 's17d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ci_webhook_configs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer,
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        # HMAC-SHA256 secret for verifying webhook payloads
        sa.Column('webhook_secret', sa.String(64), nullable=False),
        # Which document this CI config applies to (optional; null = all docs in tenant)
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ci_webhook_tenant', 'ci_webhook_configs', ['tenant_id'])

    # Add mismatch_type value for runtime test failures
    # (mismatch_type is a plain String field, no ENUM to alter — no migration needed for value)


def downgrade():
    op.drop_table('ci_webhook_configs')
```

### Backend — New Model

**New file: `backend/app/models/ci_webhook_config.py`**

```python
# backend/app/models/ci_webhook_config.py
import secrets
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class CIWebhookConfig(Base):
    """
    Per-tenant CI webhook configuration.
    Stores the HMAC secret used to verify incoming CI test result payloads.
    """
    __tablename__ = "ci_webhook_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    webhook_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @staticmethod
    def generate_secret() -> str:
        return secrets.token_hex(32)  # 64 hex chars
```

**Add to `backend/app/models/__init__.py`:**

```python
from .ci_webhook_config import CIWebhookConfig  # noqa: F401
```

### Backend — Webhook Endpoint

**Add to `backend/app/api/endpoints/webhooks.py`:**

```python
import hmac
import hashlib
from typing import List, Optional
from pydantic import BaseModel
from fastapi import Request


class CITestResult(BaseModel):
    test_name: str                    # e.g. "test_req_004_fd_rate_calculation"
    status: str                       # "pass" | "fail" | "error"
    error_message: Optional[str] = None  # failure message if status is fail/error
    file_path: Optional[str] = None   # test file path within the zip
    atom_id_hint: Optional[str] = None  # e.g. "REQ-004" — used to link to atom
    duration_ms: Optional[float] = None


class CIWebhookPayload(BaseModel):
    document_id: int                  # which DokyDoc document these tests cover
    run_id: str                       # CI pipeline run ID (for deduplication)
    commit_sha: Optional[str] = None  # git commit that was tested
    test_results: List[CITestResult]


def _verify_ci_hmac(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-DokyDoc-Signature: sha256=<hmac> header."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    received = signature_header[7:]
    return hmac.compare_digest(expected, received)


@router.post("/ci/test-results", status_code=202)
async def receive_ci_test_results(
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """
    Receive CI pipeline test results and auto-create mismatches for failures.

    Authentication: HMAC-SHA256 signature in X-DokyDoc-Signature header.
    Tenant is identified by the document_id in the payload.

    GitHub Actions example:
      curl -X POST https://app.dokydoc.com/api/v1/webhooks/ci/test-results \\
        -H "X-DokyDoc-Signature: sha256=$(echo -n '$payload' | openssl dgst -sha256 -hmac '$SECRET')" \\
        -H "Content-Type: application/json" \\
        -d '{"document_id": 1, "run_id": "abc123", "test_results": [...]}'
    """
    from app.models.document import Document
    from app.models.ci_webhook_config import CIWebhookConfig
    from app.models.requirement_atom import RequirementAtom
    from app.models.mismatch import Mismatch
    from app.models.code_component import CodeComponent

    raw_body = await request.body()
    payload_data = await request.json()

    try:
        payload = CIWebhookPayload(**payload_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")

    # Look up document and tenant
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify HMAC signature
    config = db.query(CIWebhookConfig).filter_by(tenant_id=doc.tenant_id).first()
    if not config:
        raise HTTPException(status_code=401, detail="CI webhook not configured for this tenant")

    sig_header = request.headers.get("X-DokyDoc-Signature", "")
    if not _verify_ci_hmac(raw_body, sig_header, config.webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Process failures
    failures = [r for r in payload.test_results if r.status in ("fail", "error")]
    created_mismatch_ids = []

    for result in failures:
        # Try to match to an atom by atom_id_hint
        atom = None
        if result.atom_id_hint:
            atom = db.query(RequirementAtom).filter(
                RequirementAtom.document_id == payload.document_id,
                RequirementAtom.tenant_id == doc.tenant_id,
                RequirementAtom.atom_id == result.atom_id_hint,
            ).first()

        # Check for duplicate: same run_id + test_name
        existing = db.query(Mismatch).filter(
            Mismatch.document_id == payload.document_id,
            Mismatch.tenant_id == doc.tenant_id,
            Mismatch.details["ci_run_id"].astext == payload.run_id,
            Mismatch.details["test_name"].astext == result.test_name,
        ).first()
        if existing:
            continue

        # Find or create a synthetic "CI" code component
        ci_component = db.query(CodeComponent).filter_by(
            tenant_id=doc.tenant_id,
            file_path="__ci_pipeline__",
        ).first()
        if not ci_component:
            ci_component = CodeComponent(
                tenant_id=doc.tenant_id,
                file_path="__ci_pipeline__",
                component_name="CI Pipeline",
                language="pytest",
            )
            db.add(ci_component)
            db.flush()

        severity = "high" if (atom and atom.criticality in ("critical", "high")) else "medium"

        mismatch = Mismatch(
            tenant_id=doc.tenant_id,
            document_id=payload.document_id,
            code_component_id=ci_component.id,
            requirement_atom_id=atom.id if atom else None,
            owner_id=doc.owner_id,
            mismatch_type="runtime_test_failure",
            severity=severity,
            status="open",
            direction="forward",
            description=(
                f"CI test failed: {result.test_name}. "
                f"{result.error_message or 'No error message provided.'}"
            ),
            details={
                "ci_run_id": payload.run_id,
                "commit_sha": payload.commit_sha,
                "test_name": result.test_name,
                "test_file": result.file_path,
                "error_message": result.error_message,
                "duration_ms": result.duration_ms,
                "atom_id_hint": result.atom_id_hint,
            },
        )
        db.add(mismatch)
        db.flush()
        created_mismatch_ids.append(mismatch.id)

    # Auto-close previously-open runtime_test_failure mismatches for tests that now PASS
    passing_test_names = {r.test_name for r in payload.test_results if r.status == "pass"}
    if passing_test_names:
        stale = db.query(Mismatch).filter(
            Mismatch.document_id == payload.document_id,
            Mismatch.tenant_id == doc.tenant_id,
            Mismatch.mismatch_type == "runtime_test_failure",
            Mismatch.status == "open",
        ).all()
        for m in stale:
            if m.details and m.details.get("test_name") in passing_test_names:
                m.status = "auto_closed"
        db.flush()

    db.commit()

    return {
        "received": len(payload.test_results),
        "failures": len(failures),
        "mismatches_created": len(created_mismatch_ids),
        "mismatch_ids": created_mismatch_ids,
    }
```

### Backend — CI Webhook Setup Endpoints

**Add to `backend/app/api/endpoints/integrations.py`:**

```python
from app.models.ci_webhook_config import CIWebhookConfig


# POST /integrations/ci/setup  — generate webhook secret
@router.post("/ci/setup")
def setup_ci_webhook(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Generate or rotate the CI webhook secret for this tenant.
    Returns the secret to store as a CI environment variable.
    """
    config = db.query(CIWebhookConfig).filter_by(tenant_id=current_user.tenant_id).first()
    new_secret = CIWebhookConfig.generate_secret()

    if config:
        config.webhook_secret = new_secret
    else:
        config = CIWebhookConfig(
            tenant_id=current_user.tenant_id,
            webhook_secret=new_secret,
        )
        db.add(config)

    db.commit()

    return {
        "webhook_url": f"{settings.BACKEND_URL}/api/v1/webhooks/ci/test-results",
        "secret": new_secret,
        "env_var_name": "DOKYDOC_WEBHOOK_SECRET",
        "instructions": (
            "Add DOKYDOC_WEBHOOK_SECRET as a GitHub Actions secret. "
            "In your CI workflow, compute HMAC-SHA256 of the request body "
            "and send it in the X-DokyDoc-Signature header."
        ),
    }


# GET /integrations/ci/status
@router.get("/ci/status")
def get_ci_webhook_status(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """Check whether CI webhook is configured for this tenant."""
    config = db.query(CIWebhookConfig).filter_by(tenant_id=current_user.tenant_id).first()
    return {
        "configured": config is not None,
        "webhook_url": f"{settings.BACKEND_URL}/api/v1/webhooks/ci/test-results" if config else None,
        "created_at": config.created_at.isoformat() if config else None,
    }
```

### Frontend — CI Integration Setup Card

**New file: `frontend/components/settings/CIWebhookCard.tsx`**

```tsx
// frontend/components/settings/CIWebhookCard.tsx
import { useState } from "react";
import { Copy, RefreshCw, CheckCircle, Circle } from "lucide-react";
import { apiPost, apiGet } from "@/lib/api";
import useSWR from "swr";
import { toast } from "sonner";

export function CIWebhookCard() {
  const { data: status, mutate } = useSWR("/integrations/ci/status", apiGet);
  const [secret, setSecret] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const handleSetup = async () => {
    setGenerating(true);
    try {
      const result = await apiPost("/integrations/ci/setup", {});
      setSecret(result.secret);
      mutate();
      toast.success("CI webhook secret generated");
    } catch {
      toast.error("Failed to generate CI webhook");
    } finally {
      setGenerating(false);
    }
  };

  const copySecret = () => {
    if (secret) {
      navigator.clipboard.writeText(secret);
      toast.success("Secret copied to clipboard");
    }
  };

  return (
    <div className="rounded-lg border p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">CI Pipeline Integration</h3>
          <p className="text-sm text-gray-500 mt-1">
            Send test results from GitHub Actions / Jenkins to auto-create mismatches on failure.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {status?.configured ? (
            <><CheckCircle className="h-4 w-4 text-green-500" /><span className="text-green-600">Connected</span></>
          ) : (
            <><Circle className="h-4 w-4 text-gray-300" /><span className="text-gray-400">Not configured</span></>
          )}
        </div>
      </div>

      {secret && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3 space-y-2">
          <p className="text-xs font-medium text-amber-800">
            Save this secret now — it won't be shown again:
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-white border border-amber-200 px-2 py-1 rounded truncate">
              {secret}
            </code>
            <button onClick={copySecret} className="p-1 hover:bg-amber-100 rounded">
              <Copy className="h-4 w-4 text-amber-700" />
            </button>
          </div>
          <p className="text-xs text-amber-700">
            Add as <code className="font-mono">DOKYDOC_WEBHOOK_SECRET</code> in your CI environment.
          </p>
        </div>
      )}

      <div className="rounded-md bg-gray-50 border p-3 text-xs space-y-1">
        <p className="font-medium text-gray-700">Webhook URL:</p>
        <code className="text-gray-600 break-all">
          {status?.webhook_url || "https://app.dokydoc.com/api/v1/webhooks/ci/test-results"}
        </code>
      </div>

      <div className="rounded-md bg-gray-50 border p-3">
        <p className="text-xs font-medium text-gray-700 mb-2">GitHub Actions example:</p>
        <pre className="text-xs text-gray-600 overflow-x-auto">{`- name: Send results to DokyDoc
  run: |
    PAYLOAD=$(cat test_results.json)
    SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$DOKYDOC_WEBHOOK_SECRET" | cut -d' ' -f2)
    curl -X POST "$DOKYDOC_WEBHOOK_URL" \\
      -H "Content-Type: application/json" \\
      -H "X-DokyDoc-Signature: sha256=$SIG" \\
      -d "$PAYLOAD"`}</pre>
      </div>

      <button
        onClick={handleSetup}
        disabled={generating}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50 disabled:opacity-50"
      >
        <RefreshCw className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
        {status?.configured ? "Rotate Secret" : "Generate Webhook Secret"}
      </button>
    </div>
  );
}
```

**Wire into Settings page** — add `<CIWebhookCard />` in the integrations section of the Settings page alongside Jira, GitHub, and Confluence cards.

### Test Commands

```bash
# 1. Run migration
alembic upgrade s17e1

# 2. Verify table
psql -c "\d ci_webhook_configs"

# 3. Setup CI webhook
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/integrations/ci/setup
# Expected: { "webhook_url": "...", "secret": "abc123...", "env_var_name": "DOKYDOC_WEBHOOK_SECRET" }

# 4. Send a test result payload (manually compute HMAC)
SECRET="abc123..."
PAYLOAD='{"document_id":1,"run_id":"gh-run-999","commit_sha":"deadbeef","test_results":[{"test_name":"test_req_004_fd_rate","status":"fail","error_message":"AssertionError: expected 8.0 got 6.0","atom_id_hint":"REQ-004"}]}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)
curl -X POST http://localhost:8000/api/v1/webhooks/ci/test-results \
  -H "Content-Type: application/json" \
  -H "X-DokyDoc-Signature: sha256=$SIG" \
  -d "$PAYLOAD"
# Expected: { "received": 1, "failures": 1, "mismatches_created": 1 }

# 5. Verify mismatch created
psql -c "SELECT id, mismatch_type, description, status FROM mismatches ORDER BY id DESC LIMIT 1"

# 6. Send passing result for same test (should auto-close mismatch)
PAYLOAD='{"document_id":1,"run_id":"gh-run-1000","test_results":[{"test_name":"test_req_004_fd_rate","status":"pass"}]}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)
curl -X POST http://localhost:8000/api/v1/webhooks/ci/test-results ...
# Expected: mismatch status → auto_closed

# 7. Test invalid signature is rejected
curl -X POST http://localhost:8000/api/v1/webhooks/ci/test-results \
  -H "X-DokyDoc-Signature: sha256=badsig" \
  -d "$PAYLOAD"
# Expected: 401 Invalid webhook signature
```

### Risk Assessment
- **HMAC signature verification** — `hmac.compare_digest` prevents timing attacks; unsigned requests rejected with 401
- **Run ID deduplication** — same `run_id + test_name` combination never creates duplicate mismatches
- **Synthetic code component** — `__ci_pipeline__` component is created once per tenant; avoids FK violation for CI mismatches that have no real code file
- **Auto-close on pass** — when CI run passes a test, existing `open` mismatch for that test name is auto-closed
- **Tenant isolation** — `document_id` in payload is validated against document ownership; cannot inject mismatches for other tenants


---

## P5C-07 — AI-Suggested Fix per Mismatch

**Priority:** P2 — Developer Step 5: "Opens each mismatch — sees: BRD requirement | What code shows | Exact gap | **Suggested fix**."
**Complexity:** MEDIUM — Gemini call per mismatch, stored in existing `details` JSONB. No new table.
**Risk:** LOW — Suggestions are read-only and advisory. Stored lazily on first view.

### Why This Exists

**Developer Step 5** of the workflow: the mismatch card shows BRD requirement, what the code shows, and the exact gap (P5B-05 covers evidence transparency). The final column — **Suggested fix** — is missing. The developer must mentally compute "what do I need to change?" from the evidence alone.

The fix: when a developer opens a mismatch, DokyDoc calls Gemini with the mismatch description + BRD atom content + code evidence snapshot → receives a concise, actionable code fix suggestion (3-10 lines). Stored in `details.suggested_fix` so it's only computed once.

### No New DB Changes

`Mismatch.details` is already a JSONB field. The suggested fix is stored as:

```json
{
  "suggested_fix": {
    "summary": "Update FD_INTEREST_RATE constant from 0.06 to 0.08",
    "code_snippet": "# In fd_service.py, line 23:\nFD_INTEREST_RATE = 0.08  # Changed from 0.06 per BRD Section 4.2",
    "language": "python",
    "generated_at": "2026-04-07T10:30:00Z",
    "confidence": "high"
  }
}
```

No migration required.

### Backend — Gemini Prompt for Fix Suggestion

**Add to `backend/app/services/ai/gemini.py`:**

```python
_FIX_SUGGESTION_PROMPT = """
You are a senior software engineer helping fix a BRD compliance mismatch.

BRD REQUIREMENT:
{atom_content}

ATOM TYPE: {atom_type}
MISMATCH TYPE: {mismatch_type}
MISMATCH DESCRIPTION:
{mismatch_description}

CODE EVIDENCE (what the code currently shows):
{code_evidence}

Generate a CONCISE, ACTIONABLE fix suggestion for this developer.

Rules:
1. Focus on the MINIMAL code change needed to satisfy the BRD requirement
2. Provide a 1-line summary of what to change
3. Provide a 3-10 line code snippet showing the fix
4. Use the correct programming language based on the file extension in the evidence
5. Include a comment citing the BRD requirement (e.g. # BRD Section 4.2: FD rate must be 8%)
6. If you cannot determine the exact fix (e.g., UX requirement), say so clearly
7. Confidence: "high" if the fix is precise, "medium" if approximate, "low" if speculative

Return ONLY valid JSON:
{
  "summary": "One-line description of the fix",
  "code_snippet": "The actual code change (use markdown code formatting)",
  "language": "python|typescript|java|sql|etc",
  "confidence": "high|medium|low",
  "caveat": "Any important warning or consideration (optional)"
}
"""


async def call_gemini_for_fix_suggestion(
    atom_content: str,
    atom_type: str,
    mismatch_type: str,
    mismatch_description: str,
    code_evidence: str,
    model: str = "gemini-2.0-flash",
) -> dict:
    """
    Generate an AI fix suggestion for a mismatch.
    Returns dict with summary, code_snippet, language, confidence, caveat.
    """
    import google.generativeai as genai
    from app.core.config import settings
    import json

    prompt = _FIX_SUGGESTION_PROMPT.format(
        atom_content=atom_content[:1000],
        atom_type=atom_type,
        mismatch_type=mismatch_type,
        mismatch_description=mismatch_description[:500],
        code_evidence=code_evidence[:2000],
    )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model_client = genai.GenerativeModel(model)
    response = model_client.generate_content(
        prompt,
        generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
    )
    return json.loads(response.text)
```

### Backend — Service Function

**New file: `backend/app/services/fix_suggestion_service.py`**

```python
# backend/app/services/fix_suggestion_service.py
"""
FixSuggestionService — generates AI-powered code fix suggestions for mismatches.
Suggestions are stored lazily in mismatch.details["suggested_fix"] on first request.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.mismatch import Mismatch
from app.models.requirement_atom import RequirementAtom

logger = get_logger("fix_suggestion_service")


class FixSuggestionService:

    async def get_or_generate(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
    ) -> dict:
        """
        Return cached fix suggestion if available, otherwise generate and cache.
        Never raises — returns {"error": "..."} on failure.
        """
        mismatch = db.query(Mismatch).filter(
            Mismatch.id == mismatch_id,
            Mismatch.tenant_id == tenant_id,
        ).first()
        if not mismatch:
            return {"error": "Mismatch not found"}

        # Return cached if present
        existing = (mismatch.details or {}).get("suggested_fix")
        if existing:
            return existing

        # Build code evidence string from existing details
        details = mismatch.details or {}
        code_evidence_parts = []
        if details.get("code_evidence"):
            for ev in details["code_evidence"]:
                code_evidence_parts.append(
                    f"File: {ev.get('file_path', 'unknown')}\n"
                    f"Lines {ev.get('start_line', '?')}-{ev.get('end_line', '?')}:\n"
                    f"{ev.get('snippet', '')}"
                )
        code_evidence = "\n\n".join(code_evidence_parts) or "No code evidence available."

        # Get atom content
        atom_content = "No atom content available."
        atom_type = mismatch.mismatch_type
        if mismatch.requirement_atom_id:
            atom = db.get(RequirementAtom, mismatch.requirement_atom_id)
            if atom:
                atom_content = atom.content
                atom_type = atom.atom_type

        try:
            from app.services.ai.gemini import call_gemini_for_fix_suggestion
            fix = await call_gemini_for_fix_suggestion(
                atom_content=atom_content,
                atom_type=atom_type,
                mismatch_type=mismatch.mismatch_type,
                mismatch_description=mismatch.description,
                code_evidence=code_evidence,
            )
        except Exception as e:
            logger.warning(f"Fix suggestion generation failed for mismatch {mismatch_id}: {e}")
            fix = {
                "error": "Could not generate suggestion",
                "summary": "Manually review the BRD requirement against the code evidence above.",
                "confidence": "low",
            }

        # Cache in details
        fix["generated_at"] = datetime.utcnow().isoformat()
        updated_details = dict(mismatch.details or {})
        updated_details["suggested_fix"] = fix
        mismatch.details = updated_details
        db.add(mismatch)
        db.commit()

        return fix


fix_suggestion_service = FixSuggestionService()
```

### Backend — API Endpoint

**Add to `backend/app/api/endpoints/validation.py`:**

```python
# POST /validation/mismatches/{id}/suggest-fix
@router.post("/mismatches/{mismatch_id}/suggest-fix")
async def get_fix_suggestion(
    mismatch_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return AI-generated fix suggestion for a mismatch.
    Generates on first call and caches in mismatch.details['suggested_fix'].
    Returns cached result on subsequent calls (no Gemini cost).
    """
    from app.services.fix_suggestion_service import fix_suggestion_service
    import asyncio

    fix = await fix_suggestion_service.get_or_generate(
        db=db,
        mismatch_id=mismatch_id,
        tenant_id=current_user.tenant_id,
    )
    return {"mismatch_id": mismatch_id, "suggested_fix": fix}


# DELETE /validation/mismatches/{id}/suggest-fix  (force regenerate)
@router.delete("/mismatches/{mismatch_id}/suggest-fix", status_code=204)
def clear_fix_suggestion(
    mismatch_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """Clear cached fix suggestion to force regeneration on next request."""
    from app.models.mismatch import Mismatch

    mismatch = db.query(Mismatch).filter(
        Mismatch.id == mismatch_id,
        Mismatch.tenant_id == current_user.tenant_id,
    ).first()
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    updated = dict(mismatch.details or {})
    updated.pop("suggested_fix", None)
    mismatch.details = updated
    db.add(mismatch)
    db.commit()
```

### Frontend — Suggested Fix Panel on Mismatch Card

**New file: `frontend/components/validation/MismatchSuggestedFix.tsx`**

```tsx
// frontend/components/validation/MismatchSuggestedFix.tsx
import { useState } from "react";
import { Lightbulb, Copy, RefreshCw, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { apiPost, apiDelete } from "@/lib/api";
import { toast } from "sonner";

const CONFIDENCE_CONFIG = {
  high: { color: "text-green-600 bg-green-50", label: "High confidence" },
  medium: { color: "text-amber-600 bg-amber-50", label: "Medium confidence" },
  low: { color: "text-gray-500 bg-gray-50", label: "Low confidence" },
};

interface Fix {
  summary?: string;
  code_snippet?: string;
  language?: string;
  confidence?: "high" | "medium" | "low";
  caveat?: string;
  error?: string;
  generated_at?: string;
}

interface Props {
  mismatchId: number;
  existingFix?: Fix;         // pre-loaded from mismatch.details.suggested_fix
}

export function MismatchSuggestedFix({ mismatchId, existingFix }: Props) {
  const [open, setOpen] = useState(false);
  const [fix, setFix] = useState<Fix | null>(existingFix || null);
  const [loading, setLoading] = useState(false);

  const loadFix = async (forceRegenerate = false) => {
    if (forceRegenerate) {
      try {
        await apiDelete(`/validation/mismatches/${mismatchId}/suggest-fix`);
        setFix(null);
      } catch {}
    }
    setLoading(true);
    try {
      const data = await apiPost(`/validation/mismatches/${mismatchId}/suggest-fix`, {});
      setFix(data.suggested_fix);
    } catch {
      toast.error("Failed to generate fix suggestion");
    } finally {
      setLoading(false);
    }
  };

  const copySnippet = () => {
    if (fix?.code_snippet) {
      navigator.clipboard.writeText(fix.code_snippet);
      toast.success("Code copied to clipboard");
    }
  };

  return (
    <div className="border-t mt-3 pt-3">
      <button
        onClick={() => {
          setOpen(!open);
          if (!open && !fix) loadFix();
        }}
        className="flex items-center gap-2 text-sm text-amber-700 hover:text-amber-900"
      >
        <Lightbulb className="h-4 w-4" />
        <span>Suggested Fix</span>
        {open ? <ChevronUp className="h-3.5 w-3.5 ml-auto" /> : <ChevronDown className="h-3.5 w-3.5 ml-auto" />}
      </button>

      {open && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-amber-600">
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              Generating AI fix suggestion...
            </div>
          )}

          {fix && !loading && (
            <>
              {/* Summary */}
              {fix.summary && (
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-amber-900">{fix.summary}</p>
                    {fix.confidence && (
                      <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${
                        CONFIDENCE_CONFIG[fix.confidence]?.color || "text-gray-500 bg-gray-50"
                      }`}>
                        {CONFIDENCE_CONFIG[fix.confidence]?.label}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Code snippet */}
              {fix.code_snippet && (
                <div className="relative">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-amber-600">{fix.language}</span>
                    <button
                      onClick={copySnippet}
                      className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800"
                    >
                      <Copy className="h-3 w-3" /> Copy
                    </button>
                  </div>
                  <pre className="bg-white border border-amber-200 rounded p-2 text-xs overflow-x-auto whitespace-pre-wrap">
                    <code>{fix.code_snippet}</code>
                  </pre>
                </div>
              )}

              {/* Caveat */}
              {fix.caveat && (
                <div className="flex items-start gap-2 text-xs text-amber-700">
                  <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                  <span>{fix.caveat}</span>
                </div>
              )}

              {/* Error case */}
              {fix.error && (
                <p className="text-xs text-gray-500 italic">{fix.summary || fix.error}</p>
              )}

              {/* Regenerate */}
              <button
                onClick={() => loadFix(true)}
                className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800"
              >
                <RefreshCw className="h-3 w-3" /> Regenerate suggestion
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

**Wire into mismatch card** — in the mismatch card component, add below the evidence panel (P5B-05):

```tsx
<MismatchSuggestedFix
  mismatchId={mismatch.id}
  existingFix={mismatch.details?.suggested_fix}
/>
```

### Test Commands

```bash
# 1. No migration needed — uses existing mismatch.details JSONB

# 2. Fetch fix suggestion for a mismatch (generates on first call)
curl -X POST -H "Authorization: Bearer $DEV_TOKEN" \
  http://localhost:8000/api/v1/validation/mismatches/5/suggest-fix
# Expected: { "mismatch_id": 5, "suggested_fix": { "summary": "...", "code_snippet": "...", "confidence": "high" } }

# 3. Verify it was cached in the mismatch details
psql -c "SELECT details->'suggested_fix'->>'summary' FROM mismatches WHERE id=5"

# 4. Second call should return cached (no Gemini API call)
curl -X POST -H "Authorization: Bearer $DEV_TOKEN" \
  http://localhost:8000/api/v1/validation/mismatches/5/suggest-fix
# Same response, no Gemini cost

# 5. Force regenerate
curl -X DELETE -H "Authorization: Bearer $DEV_TOKEN" \
  http://localhost:8000/api/v1/validation/mismatches/5/suggest-fix
# Then POST again — fresh Gemini call

# 6. Test with a mismatch that has code evidence (P5B-05 populated details)
# The code_evidence in details should inform the fix suggestion
```

### Risk Assessment
- **Lazy generation** — Gemini is called only on first user request, not on mismatch creation; zero extra cost for mismatches that are never opened
- **Cached in JSONB** — subsequent loads are instant; no Gemini cost; persists until manually cleared
- **Failure graceful** — if Gemini fails, stores `{"error": "...", "summary": "Manually review..."}` so the card still renders something useful
- **Context limit** — atom content capped at 1000 chars, code evidence at 2000 chars; avoids token limit errors
- **Advisory only** — clearly labeled "AI suggestion"; developer is responsible for the actual fix


---

## P5C-08 — Compliance Score Trend / Time Series

**Priority:** P1 — Tech Lead Step 2: "Sees trend: Core Banking dropped from 89% to 79% this week."
**Complexity:** MEDIUM — New table, Celery beat snapshot task, recharts line chart.
**Risk:** LOW — Snapshot task is read-only and never blocks anything.

### Why This Exists

**Tech Lead Steps 1-3:**
- "Opens compliance dashboard daily — FD Product: 87%."
- "Sees trend: Core Banking dropped from 89% to 79% this week."
- "Drills in: 4 new high-severity mismatches from BRD v3.1 upload."

P5B-02 (compliance score) gives a single current percentage. There is no way to see whether things are getting better or worse over time. A Tech Lead needs to see trend direction — improving, degrading, or flat — to prioritize sprint work.

The fix: store a compliance score snapshot once per day per document. A Celery beat task runs nightly. Tech Lead sees a line chart over the last 30 days.

### DB Changes

**New table: `compliance_score_snapshots`**

**New migration: `backend/alembic/versions/s17d1_compliance_snapshots.py`**

```python
# backend/alembic/versions/s17d1_compliance_snapshots.py
"""Add compliance_score_snapshots table

Revision ID: s17d1
Revises: s17c1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = 's17d1'
down_revision = 's17c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'compliance_score_snapshots',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.Integer, nullable=False, index=True),
        sa.Column('document_id', sa.Integer,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        # Snapshot values
        sa.Column('score_percentage', sa.Float, nullable=False),
        sa.Column('total_atoms', sa.Integer, nullable=False, default=0),
        sa.Column('covered_atoms', sa.Integer, nullable=False, default=0),
        sa.Column('open_mismatches', sa.Integer, nullable=False, default=0),
        sa.Column('critical_mismatches', sa.Integer, nullable=False, default=0),
        # Timestamp of snapshot (date-level granularity, one per day)
        sa.Column('snapshot_date', sa.Date, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_compliance_snapshots_document_date',
                    'compliance_score_snapshots', ['document_id', 'snapshot_date'],
                    unique=True)  # One snapshot per document per day
    op.create_index('ix_compliance_snapshots_tenant',
                    'compliance_score_snapshots', ['tenant_id', 'snapshot_date'])


def downgrade():
    op.drop_table('compliance_score_snapshots')
```

### Backend — New Model

**New file: `backend/app/models/compliance_score_snapshot.py`**

```python
# backend/app/models/compliance_score_snapshot.py
from datetime import datetime, date
from sqlalchemy import Integer, Float, ForeignKey, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class ComplianceScoreSnapshot(Base):
    """
    Daily compliance score snapshot per document.
    Created by a nightly Celery beat task.
    Also triggered on-demand when validation scan completes.
    """
    __tablename__ = "compliance_score_snapshots"
    __table_args__ = (
        UniqueConstraint("document_id", "snapshot_date", name="uq_snapshot_document_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    total_atoms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    covered_atoms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_mismatches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_mismatches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

**Add to `backend/app/models/__init__.py`:**

```python
from .compliance_score_snapshot import ComplianceScoreSnapshot  # noqa: F401
```

### Backend — Snapshot Service

**New file: `backend/app/services/compliance_snapshot_service.py`**

```python
# backend/app/services/compliance_snapshot_service.py
"""
ComplianceSnapshotService — captures daily compliance score per document.
Reuses the existing compliance score calculation from P5B-02's CRUDMismatch.
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.logging import get_logger
from app.models.compliance_score_snapshot import ComplianceScoreSnapshot
from app.models.requirement_atom import RequirementAtom
from app.models.mismatch import Mismatch

logger = get_logger("compliance_snapshot_service")


class ComplianceSnapshotService:

    def capture_for_document(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        snapshot_date: date | None = None,
    ) -> ComplianceScoreSnapshot:
        """
        Take a compliance snapshot for one document.
        Uses UPSERT so re-running on the same day updates rather than duplicates.
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        # Calculate current score
        total_atoms = db.query(RequirementAtom).filter(
            RequirementAtom.document_id == document_id,
            RequirementAtom.tenant_id == tenant_id,
        ).count()

        # Atoms with at least one open/non-false-positive mismatch = not covered
        from sqlalchemy import func, distinct
        uncovered_atom_ids = db.query(distinct(Mismatch.requirement_atom_id)).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status.in_(["open", "in_progress"]),
            Mismatch.requirement_atom_id.isnot(None),
        ).all()
        uncovered_count = len(uncovered_atom_ids)
        covered = max(0, total_atoms - uncovered_count)
        score = round((covered / total_atoms * 100) if total_atoms > 0 else 100.0, 1)

        open_mismatches = db.query(Mismatch).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status == "open",
        ).count()

        critical_mismatches = db.query(Mismatch).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status == "open",
            Mismatch.severity.in_(["critical", "high"]),
        ).count()

        # UPSERT: insert or update on (document_id, snapshot_date)
        stmt = pg_insert(ComplianceScoreSnapshot).values(
            tenant_id=tenant_id,
            document_id=document_id,
            score_percentage=score,
            total_atoms=total_atoms,
            covered_atoms=covered,
            open_mismatches=open_mismatches,
            critical_mismatches=critical_mismatches,
            snapshot_date=snapshot_date,
            created_at=datetime.utcnow(),
        ).on_conflict_do_update(
            index_elements=["document_id", "snapshot_date"],
            set_={
                "score_percentage": score,
                "total_atoms": total_atoms,
                "covered_atoms": covered,
                "open_mismatches": open_mismatches,
                "critical_mismatches": critical_mismatches,
                "created_at": datetime.utcnow(),
            }
        )
        db.execute(stmt)
        db.commit()

        obj = db.query(ComplianceScoreSnapshot).filter_by(
            document_id=document_id, snapshot_date=snapshot_date
        ).first()
        return obj

    def capture_all_active_documents(self, db: Session) -> int:
        """
        Snapshot all documents that have atoms. Called by nightly Celery beat task.
        Returns count of documents snapshotted.
        """
        from app.models.document import Document
        from sqlalchemy import func

        # Documents that have atoms (active documents)
        active_doc_ids = db.query(
            RequirementAtom.document_id, RequirementAtom.tenant_id
        ).group_by(
            RequirementAtom.document_id, RequirementAtom.tenant_id
        ).all()

        count = 0
        for doc_id, tenant_id in active_doc_ids:
            try:
                self.capture_for_document(db=db, document_id=doc_id, tenant_id=tenant_id)
                count += 1
            except Exception as e:
                logger.warning(f"Snapshot failed for document {doc_id}: {e}")

        logger.info(f"Snapshotted {count} documents")
        return count


compliance_snapshot_service = ComplianceSnapshotService()
```

### Backend — Celery Beat Task (Nightly Snapshot)

**Add to `backend/app/tasks/document_pipeline.py`** or create `backend/app/tasks/analytics_tasks.py`:

```python
# backend/app/tasks/analytics_tasks.py
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("analytics_tasks")


@celery_app.task(name="nightly_compliance_snapshots")
def nightly_compliance_snapshots():
    """
    Celery beat task: run every night at midnight to snapshot compliance scores
    for all active documents. Configured in celery beat schedule.
    """
    from app.db.session import SessionLocal
    from app.services.compliance_snapshot_service import compliance_snapshot_service

    db = SessionLocal()
    try:
        count = compliance_snapshot_service.capture_all_active_documents(db)
        logger.info(f"Nightly snapshot completed: {count} documents")
        return {"status": "completed", "documents_snapshotted": count}
    except Exception as e:
        logger.error(f"Nightly snapshot task failed: {e}")
        raise
    finally:
        db.close()
```

**Add to Celery beat schedule** in `backend/app/core/celery_app.py`:

```python
# Add to beat_schedule dict:
"nightly-compliance-snapshots": {
    "task": "nightly_compliance_snapshots",
    "schedule": crontab(hour=0, minute=0),  # midnight UTC
    "options": {"expires": 3600},
},
```

**Also trigger a snapshot after each validation scan completes** — in `backend/app/services/validation_service.py` at the end of `run_validation_scan`:

```python
# PHASE 5C: Capture compliance snapshot after each scan
try:
    from app.services.compliance_snapshot_service import compliance_snapshot_service
    compliance_snapshot_service.capture_for_document(
        db=db, document_id=document_id, tenant_id=tenant_id
    )
except Exception as e:
    logger.warning(f"Post-scan compliance snapshot failed (non-fatal): {e}")
```

### Backend — API Endpoint

**Add to `backend/app/api/endpoints/validation.py`:**

```python
from app.models.compliance_score_snapshot import ComplianceScoreSnapshot
from datetime import date, timedelta


# GET /validation/{document_id}/compliance-trend
@router.get("/{document_id}/compliance-trend")
def get_compliance_trend(
    document_id: int,
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return compliance score snapshots for the last N days.
    Used to render the trend line chart on the validation dashboard.
    """
    since = date.today() - timedelta(days=days)

    snapshots = db.query(ComplianceScoreSnapshot).filter(
        ComplianceScoreSnapshot.document_id == document_id,
        ComplianceScoreSnapshot.tenant_id == current_user.tenant_id,
        ComplianceScoreSnapshot.snapshot_date >= since,
    ).order_by(ComplianceScoreSnapshot.snapshot_date.asc()).all()

    if not snapshots:
        return {
            "document_id": document_id,
            "days": days,
            "trend": [],
            "direction": "neutral",
            "change_pct": 0.0,
        }

    trend_data = [
        {
            "date": s.snapshot_date.isoformat(),
            "score": s.score_percentage,
            "total_atoms": s.total_atoms,
            "covered_atoms": s.covered_atoms,
            "open_mismatches": s.open_mismatches,
            "critical_mismatches": s.critical_mismatches,
        }
        for s in snapshots
    ]

    # Calculate direction: compare first and last snapshot
    first_score = snapshots[0].score_percentage
    last_score = snapshots[-1].score_percentage
    change = round(last_score - first_score, 1)

    direction = "improving" if change > 1 else "degrading" if change < -1 else "stable"

    return {
        "document_id": document_id,
        "days": days,
        "trend": trend_data,
        "direction": direction,
        "change_pct": change,
        "current_score": last_score,
        "baseline_score": first_score,
    }
```

### Frontend — Compliance Trend Chart

**New file: `frontend/components/validation/ComplianceTrendChart.tsx`**

```tsx
// frontend/components/validation/ComplianceTrendChart.tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import useSWR from "swr";
import { apiGet } from "@/lib/api";
import { useState } from "react";

interface Props {
  documentId: number;
}

const DIRECTION_CONFIG = {
  improving: { icon: TrendingUp, color: "text-green-600", bg: "bg-green-50 border-green-200" },
  degrading: { icon: TrendingDown, color: "text-red-600", bg: "bg-red-50 border-red-200" },
  stable: { icon: Minus, color: "text-gray-500", bg: "bg-gray-50 border-gray-200" },
  neutral: { icon: Minus, color: "text-gray-400", bg: "bg-gray-50 border-gray-100" },
};

export function ComplianceTrendChart({ documentId }: Props) {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useSWR(
    `/validation/${documentId}/compliance-trend?days=${days}`,
    apiGet,
    { refreshInterval: 300_000 }  // refresh every 5 min
  );

  if (isLoading) return <div className="h-48 flex items-center justify-center text-sm text-gray-400">Loading trend...</div>;
  if (!data?.trend?.length) return (
    <div className="h-20 flex items-center justify-center text-sm text-gray-400">
      No trend data yet. Run a validation scan to start tracking.
    </div>
  );

  const direction = data.direction || "neutral";
  const cfg = DIRECTION_CONFIG[direction as keyof typeof DIRECTION_CONFIG] || DIRECTION_CONFIG.neutral;
  const Icon = cfg.icon;

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  const chartData = data.trend.map((s: any) => ({
    ...s,
    date: formatDate(s.date),
  }));

  return (
    <div className="space-y-3">
      {/* Header: score + direction indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full border text-xs font-medium ${cfg.bg} ${cfg.color}`}>
            <Icon className="h-3.5 w-3.5" />
            {direction === "improving" && `+${Math.abs(data.change_pct)}% in ${days}d`}
            {direction === "degrading" && `-${Math.abs(data.change_pct)}% in ${days}d`}
            {direction === "stable" && `Stable (${data.change_pct > 0 ? "+" : ""}${data.change_pct}%)`}
            {direction === "neutral" && "No trend data"}
          </div>
          <span className="text-2xl font-bold text-gray-900">{data.current_score}%</span>
        </div>
        {/* Days selector */}
        <div className="flex gap-1">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2 py-0.5 text-xs rounded ${days === d ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Line chart */}
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
          <Tooltip
            formatter={(value: number) => [`${value}%`, "Compliance"]}
            labelStyle={{ fontSize: 11 }}
            contentStyle={{ fontSize: 11 }}
          />
          <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: "80%", fontSize: 10, fill: "#f59e0b" }} />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#3b82f6" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Supporting metrics row */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded border p-2">
          <div className="font-semibold text-gray-900">{data.trend[data.trend.length - 1]?.open_mismatches ?? 0}</div>
          <div className="text-gray-400">Open mismatches</div>
        </div>
        <div className="rounded border p-2">
          <div className="font-semibold text-red-600">{data.trend[data.trend.length - 1]?.critical_mismatches ?? 0}</div>
          <div className="text-gray-400">Critical/High</div>
        </div>
        <div className="rounded border p-2">
          <div className="font-semibold text-gray-900">{data.trend[data.trend.length - 1]?.total_atoms ?? 0}</div>
          <div className="text-gray-400">Total atoms</div>
        </div>
      </div>
    </div>
  );
}
```

**Wire into validation panel** — replace or augment the static compliance score display with:

```tsx
// In the compliance score section of the validation panel:
<ComplianceTrendChart documentId={documentId} />
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s17d1

# 2. Verify table with unique constraint
psql -c "\d compliance_score_snapshots"
psql -c "SELECT indexname FROM pg_indexes WHERE tablename='compliance_score_snapshots'"

# 3. Manually trigger a snapshot for document 1
# In Python shell:
from app.db.session import SessionLocal
from app.services.compliance_snapshot_service import compliance_snapshot_service
db = SessionLocal()
snap = compliance_snapshot_service.capture_for_document(db, document_id=1, tenant_id=1)
print(snap.score_percentage)

# 4. Verify in DB
psql -c "SELECT document_id, score_percentage, snapshot_date FROM compliance_score_snapshots"

# 5. Run the nightly task manually
celery -A app.core.celery_app call nightly_compliance_snapshots
# Expected: { "status": "completed", "documents_snapshotted": N }

# 6. Test trend API
curl -H "Authorization: Bearer $TECH_LEAD_TOKEN" \
  "http://localhost:8000/api/v1/validation/1/compliance-trend?days=30"
# Expected: { "trend": [...], "direction": "...", "change_pct": ..., "current_score": ... }

# 7. Verify upsert on same day (run snapshot twice — should not duplicate)
psql -c "SELECT COUNT(*) FROM compliance_score_snapshots WHERE document_id=1 AND snapshot_date=CURRENT_DATE"
# Expected: 1 (upsert, not insert)

# 8. Test recharts dependency installed
cd frontend && npm list recharts
```

### Risk Assessment
- **Unique constraint + UPSERT** — idempotent; running snapshot twice on the same day updates, not duplicates
- **Celery beat timing** — midnight UTC snapshot; documents created during the day get a snapshot within 24 hours at most; also triggered immediately after each scan
- **Large tenant performance** — `capture_all_active_documents` loops per document; for 1000+ docs, consider chunking with `try/except` per doc (already has that)
- **Recharts dependency** — already used in P4-09 cost savings widget; no new NPM dependency
- **Cascade delete** — `ON DELETE CASCADE` on document_id FK; snapshots auto-deleted with document


---

## P5C-09 — Cross-Project Aggregate Compliance Dashboard (CTO / VP Engineering)

**Priority:** P2 — CTO monthly view: "BRD Compliance Score: 91% across 14 active projects. QA time saved: ~18 hours."
**Complexity:** MEDIUM — Aggregate query across documents; new analytics page in frontend.
**Risk:** LOW — Read-only analytics endpoint. No writes to existing tables.

### Why This Exists

**CTO Monthly View:**
- "BRD Compliance Score: 91% across 14 active projects."
- "Open mismatches: 23 (8 High, 11 Medium, 4 Low)."
- "Regulatory risk: 2 HIPAA requirements unvalidated (file not uploaded)."
- "Gemini cost saved vs baseline: ₹12,400 this month." (P4-09 already covers this)
- "QA time saved: ~18 hours (based on atom count × baseline tester hours)."

P5B-02 gives a per-document compliance score. There is no cross-document aggregate view. A CTO needs to see all projects at once and spot which ones are lagging.

The fix: a new analytics endpoint that aggregates across all documents in the tenant, plus a frontend executive dashboard page. QA time saved is calculated as `testable_atoms × baseline_tester_hours_per_atom` (configurable in tenant settings, default 0.5 hours).

### No New DB Changes

This task only reads existing tables:
- `compliance_score_snapshots` (P5C-08) — for per-document latest score
- `requirement_atoms` — for atom counts and regulatory tags
- `mismatches` — for open/severity breakdown
- `documents` — for document metadata
- `file_suggestions` (P5C-01) — for unvalidated regulatory atoms

No new migration required.

One optional tenant setting addition (stored in existing `tenant.settings` JSONB, no schema change):

```json
{
  "qa_baseline_hours_per_atom": 0.5
}
```

### Backend — Aggregate Analytics Endpoint

**Add to `backend/app/api/endpoints/analysis_results.py`** (or create a new `analytics.py` router):

```python
# Add to backend/app/api/endpoints/analytics.py (new file)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.api import deps

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/compliance-overview")
def get_compliance_overview(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    CTO/VP dashboard: aggregate compliance across all documents in the tenant.

    Returns:
    - Overall compliance percentage (weighted by atom count)
    - Per-document breakdown
    - Mismatch severity breakdown
    - Regulatory risk summary (atoms with regulatory tags but no linked file)
    - QA time saved estimate
    """
    from app.models.document import Document
    from app.models.requirement_atom import RequirementAtom
    from app.models.mismatch import Mismatch
    from app.models.compliance_score_snapshot import ComplianceScoreSnapshot
    from app.models.file_suggestion import FileSuggestion
    from app.models.tenant import Tenant
    from datetime import date

    tenant_id = current_user.tenant_id

    # 1. All active documents (have atoms)
    docs_with_atoms = db.query(
        RequirementAtom.document_id,
        func.count(RequirementAtom.id).label("atom_count"),
    ).filter(
        RequirementAtom.tenant_id == tenant_id,
    ).group_by(RequirementAtom.document_id).all()

    doc_ids = [r.document_id for r in docs_with_atoms]
    atom_count_by_doc = {r.document_id: r.atom_count for r in docs_with_atoms}

    if not doc_ids:
        return {
            "tenant_id": tenant_id,
            "total_documents": 0,
            "overall_compliance_pct": 100.0,
            "projects": [],
            "mismatch_breakdown": {},
            "regulatory_risk": {},
            "qa_time_saved_hours": 0.0,
        }

    # 2. Latest compliance score snapshot per document
    from sqlalchemy import distinct
    latest_snapshots_subq = db.query(
        ComplianceScoreSnapshot.document_id,
        func.max(ComplianceScoreSnapshot.snapshot_date).label("latest_date"),
    ).filter(
        ComplianceScoreSnapshot.tenant_id == tenant_id,
        ComplianceScoreSnapshot.document_id.in_(doc_ids),
    ).group_by(ComplianceScoreSnapshot.document_id).subquery()

    latest_snapshots = db.query(ComplianceScoreSnapshot).join(
        latest_snapshots_subq,
        (ComplianceScoreSnapshot.document_id == latest_snapshots_subq.c.document_id) &
        (ComplianceScoreSnapshot.snapshot_date == latest_snapshots_subq.c.latest_date),
    ).all()

    score_by_doc = {s.document_id: s for s in latest_snapshots}

    # 3. Document metadata
    docs = db.query(Document).filter(
        Document.id.in_(doc_ids),
        Document.tenant_id == tenant_id,
    ).all()
    doc_meta = {d.id: d for d in docs}

    # 4. Overall mismatch breakdown
    mismatch_summary = db.query(
        Mismatch.severity,
        func.count(Mismatch.id).label("count"),
    ).filter(
        Mismatch.tenant_id == tenant_id,
        Mismatch.document_id.in_(doc_ids),
        Mismatch.status.in_(["open", "in_progress"]),
    ).group_by(Mismatch.severity).all()

    mismatch_breakdown = {r.severity: r.count for r in mismatch_summary}
    total_open_mismatches = sum(mismatch_breakdown.values())

    # 5. Regulatory risk — atoms with regulatory tags but no linked code file
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy import String, cast
    # Find atoms with regulatory_tags set but corresponding file suggestion unfulfilled
    unvalidated_regulatory = db.execute(
        """
        SELECT ra.regulatory_tags, COUNT(*) as cnt
        FROM requirement_atoms ra
        WHERE ra.tenant_id = :tenant_id
          AND ra.document_id = ANY(:doc_ids)
          AND ra.regulatory_tags IS NOT NULL
          AND array_length(ra.regulatory_tags, 1) > 0
          AND NOT EXISTS (
            SELECT 1 FROM mismatches m
            WHERE m.requirement_atom_id = ra.id
              AND m.status NOT IN ('false_positive', 'auto_closed')
          )
        GROUP BY ra.regulatory_tags
        """,
        {"tenant_id": tenant_id, "doc_ids": doc_ids}
    ).fetchall()

    # Simplified: count unvalidated atoms by regulatory tag
    regulatory_risk = {}
    for row in unvalidated_regulatory:
        tags = row[0] or []
        for tag in tags:
            regulatory_risk[tag] = regulatory_risk.get(tag, 0) + row[1]

    # 6. QA time saved
    # Atoms with testability="static" or "runtime" = auto-tested = QA time saved
    auto_testable_count = db.query(func.count(RequirementAtom.id)).filter(
        RequirementAtom.tenant_id == tenant_id,
        RequirementAtom.document_id.in_(doc_ids),
        RequirementAtom.testability.in_(["static", "runtime"]),
    ).scalar() or 0

    # QA baseline hours per atom from tenant settings (default 0.5 hours)
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    tenant_settings = tenant.settings if tenant and hasattr(tenant, 'settings') and tenant.settings else {}
    baseline_hours = float(tenant_settings.get("qa_baseline_hours_per_atom", 0.5))
    qa_time_saved = round(auto_testable_count * baseline_hours, 1)

    # 7. Weighted overall compliance (weighted by atom count)
    total_atoms = sum(atom_count_by_doc.values())
    weighted_score_sum = 0.0
    for doc_id in doc_ids:
        snap = score_by_doc.get(doc_id)
        score = snap.score_percentage if snap else 100.0
        weighted_score_sum += score * atom_count_by_doc[doc_id]
    overall_compliance = round(weighted_score_sum / total_atoms, 1) if total_atoms > 0 else 100.0

    # 8. Per-project list
    projects = []
    for doc_id in doc_ids:
        snap = score_by_doc.get(doc_id)
        doc = doc_meta.get(doc_id)
        projects.append({
            "document_id": doc_id,
            "title": doc.title if doc else f"Document {doc_id}",
            "atom_count": atom_count_by_doc[doc_id],
            "compliance_score": snap.score_percentage if snap else None,
            "open_mismatches": snap.open_mismatches if snap else 0,
            "critical_mismatches": snap.critical_mismatches if snap else 0,
            "last_snapshot_date": snap.snapshot_date.isoformat() if snap else None,
        })

    # Sort: lowest compliance first (most urgent)
    projects.sort(key=lambda p: p["compliance_score"] or 100.0)

    return {
        "tenant_id": tenant_id,
        "total_documents": len(doc_ids),
        "total_atoms": total_atoms,
        "overall_compliance_pct": overall_compliance,
        "total_open_mismatches": total_open_mismatches,
        "mismatch_breakdown": mismatch_breakdown,
        "regulatory_risk": regulatory_risk,
        "qa_time_saved_hours": qa_time_saved,
        "auto_testable_atoms": auto_testable_count,
        "qa_baseline_hours_per_atom": baseline_hours,
        "projects": projects,
        "generated_at": date.today().isoformat(),
    }
```

**Register router in `backend/app/api/api.py`:**

```python
from app.api.endpoints import analytics
api_router.include_router(analytics.router)
```

### Frontend — Executive Compliance Dashboard Page

**New file: `frontend/pages/analytics/compliance.tsx`** (or `frontend/app/analytics/compliance/page.tsx` for Next.js app router):

```tsx
// frontend/pages/analytics/compliance.tsx
import { Building2, TrendingUp, TrendingDown, AlertTriangle, Clock, Shield } from "lucide-react";
import useSWR from "swr";
import { apiGet } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function ComplianceDashboard() {
  const { data, isLoading } = useSWR("/analytics/compliance-overview", apiGet, {
    refreshInterval: 300_000,  // refresh every 5 min
  });

  if (isLoading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading compliance data...</div>;

  const {
    total_documents, overall_compliance_pct, total_open_mismatches,
    mismatch_breakdown, regulatory_risk, qa_time_saved_hours,
    auto_testable_atoms, projects = [],
  } = data ?? {};

  const getScoreColor = (score: number) =>
    score >= 90 ? "text-green-600" : score >= 75 ? "text-amber-600" : "text-red-600";
  const getScoreBg = (score: number) =>
    score >= 90 ? "bg-green-50 border-green-200" : score >= 75 ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200";

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Compliance Overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Across {total_documents} active projects · Last updated today
        </p>
      </div>

      {/* Top KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overall compliance */}
        <div className={`rounded-xl border p-5 space-y-1 ${getScoreBg(overall_compliance_pct)}`}>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Overall Compliance</p>
          <p className={`text-4xl font-bold ${getScoreColor(overall_compliance_pct)}`}>
            {overall_compliance_pct}%
          </p>
          <p className="text-xs text-gray-500">Weighted across {total_documents} projects</p>
        </div>

        {/* Open mismatches */}
        <div className="rounded-xl border bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Open Mismatches</p>
          <p className="text-4xl font-bold text-gray-900">{total_open_mismatches}</p>
          <div className="flex gap-2 text-xs">
            <span className="text-red-600 font-medium">{mismatch_breakdown?.critical || 0} Critical</span>
            <span className="text-amber-600">{mismatch_breakdown?.high || 0} High</span>
            <span className="text-gray-400">{mismatch_breakdown?.medium || 0} Med</span>
          </div>
        </div>

        {/* QA time saved */}
        <div className="rounded-xl border bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">QA Time Saved</p>
          <p className="text-4xl font-bold text-blue-600">{qa_time_saved_hours}h</p>
          <p className="text-xs text-gray-500">
            {auto_testable_atoms} atoms auto-tested · 0.5h baseline each
          </p>
        </div>

        {/* Regulatory risk */}
        <div className="rounded-xl border bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Regulatory Risk</p>
          <p className="text-4xl font-bold text-amber-600">
            {Object.values(regulatory_risk || {}).reduce((a: number, b: any) => a + (b as number), 0)}
          </p>
          <div className="flex flex-wrap gap-1 mt-1">
            {Object.entries(regulatory_risk || {}).map(([tag, count]) => (
              <span key={tag} className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                {tag}: {count as number}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Per-project compliance bar chart */}
      <div className="rounded-xl border bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Compliance by Project</h2>
        <ResponsiveContainer width="100%" height={Math.max(200, projects.length * 40)}>
          <BarChart
            data={projects.slice(0, 15)}  // Show top 15 lowest compliance first
            layout="vertical"
            margin={{ left: 20, right: 40, top: 0, bottom: 0 }}
          >
            <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
            <YAxis
              dataKey="title"
              type="category"
              width={180}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => v.length > 25 ? `${v.slice(0, 22)}...` : v}
            />
            <Tooltip
              formatter={(value: number) => [`${value}%`, "Compliance"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="compliance_score" radius={[0, 4, 4, 0]}>
              {projects.slice(0, 15).map((p: any) => (
                <Cell
                  key={p.document_id}
                  fill={
                    (p.compliance_score || 0) >= 90 ? "#22c55e" :
                    (p.compliance_score || 0) >= 75 ? "#f59e0b" : "#ef4444"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Project detail table */}
      <div className="rounded-xl border bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Project</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Score</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Atoms</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Open</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Critical</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Last Update</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {projects.map((p: any) => (
              <tr key={p.document_id} className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => window.location.href = `/documents/${p.document_id}`}>
                <td className="px-4 py-3 font-medium text-gray-900">{p.title}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`font-bold ${getScoreColor(p.compliance_score || 0)}`}>
                    {p.compliance_score != null ? `${p.compliance_score}%` : "—"}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-gray-600">{p.atom_count}</td>
                <td className="px-4 py-3 text-center">
                  <span className={p.open_mismatches > 0 ? "text-amber-600 font-medium" : "text-gray-400"}>
                    {p.open_mismatches}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={p.critical_mismatches > 0 ? "text-red-600 font-bold" : "text-gray-400"}>
                    {p.critical_mismatches}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-gray-400 text-xs">
                  {p.last_snapshot_date || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

**Wire into sidebar navigation** — add a "Compliance Dashboard" link in the sidebar under Analytics:

```tsx
// In the sidebar nav items array:
{
  label: "Compliance Dashboard",
  href: "/analytics/compliance",
  icon: Shield,
  roles: ["cto", "vp_engineering", "admin", "tech_lead"],
}
```

**Tenant Settings — QA Baseline Hours Configurability**

In the settings page (where P5-09 Industry Profile is), add a QA calibration field:

```tsx
// In frontend/pages/settings/index.tsx, inside tenant settings form:
<div className="space-y-1">
  <label className="text-sm font-medium text-gray-700">
    QA Baseline Hours per Atom
  </label>
  <p className="text-xs text-gray-500">
    Estimated hours a QA engineer spends testing one requirement manually.
    Used to calculate QA time saved on the compliance dashboard. Default: 0.5 hours.
  </p>
  <input
    type="number"
    step="0.1"
    min="0.1"
    max="8"
    value={settings.qa_baseline_hours_per_atom ?? 0.5}
    onChange={(e) => updateSetting("qa_baseline_hours_per_atom", parseFloat(e.target.value))}
    className="w-24 text-sm border rounded px-2 py-1"
  />
</div>
```

### Test Commands

```bash
# 1. No migration needed (pure read)
# Verify tables used exist
psql -c "\d compliance_score_snapshots"
psql -c "\d requirement_atoms" | grep testability
psql -c "\d mismatches" | grep severity

# 2. Seed some snapshots (or trigger validation scans on multiple documents)
# Then test the aggregate endpoint:
curl -H "Authorization: Bearer $CTO_TOKEN" \
  http://localhost:8000/api/v1/analytics/compliance-overview
# Expected:
# {
#   "total_documents": 14,
#   "overall_compliance_pct": 91.2,
#   "total_open_mismatches": 23,
#   "mismatch_breakdown": {"high": 8, "medium": 11, "low": 4},
#   "regulatory_risk": {"HIPAA": 2, "PCI-DSS": 1},
#   "qa_time_saved_hours": 18.5,
#   "projects": [...]
# }

# 3. Test with no snapshots yet (graceful fallback)
# compliance_score should be null for documents without snapshots

# 4. Verify QA baseline from tenant settings
psql -c "SELECT settings->'qa_baseline_hours_per_atom' FROM tenants WHERE id=1"

# 5. Update baseline via settings endpoint and re-check
curl -X PATCH -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"settings": {"qa_baseline_hours_per_atom": 0.75}}' \
  http://localhost:8000/api/v1/tenants/settings
curl http://localhost:8000/api/v1/analytics/compliance-overview | jq .qa_time_saved_hours
# Should reflect new 0.75 * atom_count value

# 6. Verify recharts BarChart renders without console errors
# Open /analytics/compliance in browser → check devtools for errors
```

### Risk Assessment
- **Read-only endpoint** — aggregates from existing tables; no writes; safe to call frequently
- **Weighted compliance** — weighted by atom count (not simple average); large documents don't get diluted by small ones
- **Missing snapshots** — documents without snapshots show `compliance_score: null` and `open_mismatches: 0`; handled gracefully in the UI with "—"
- **Regulatory risk query** — raw SQL for the regulatory cross-join; consider moving to ORM query if maintenance is a concern
- **Role guard** — sidebar link only shows for `cto / vp_engineering / admin / tech_lead` roles; endpoint itself has no role check (tenant_id isolation is sufficient for data safety)
- **QA time metric is an estimate** — clearly labeled as estimate; not shown to external auditors; configurable baseline makes it honest

---

## Phase 5C — Migration Dependency Chain

```
s16f1  (Phase 5B baseline — brd_sign_offs)
  └── s17a1  file_suggestions + requirement_atoms.testability + documents.file_suggestion_summary
       └── s17b1  mismatch_clarifications
            └── s17c1  uat_checklist_items
                 └── s17d1  compliance_score_snapshots
                      └── s17e1  ci_webhook_configs
```

Run all at once:
```bash
alembic upgrade s17e1
```

Or step by step:
```bash
alembic upgrade s17a1  # P5C-01: file suggestions + testability
alembic upgrade s17b1  # P5C-03: clarifications
alembic upgrade s17c1  # P5C-04: UAT checklist
alembic upgrade s17d1  # P5C-08: compliance snapshots
alembic upgrade s17e1  # P5C-06: CI webhook config
```

## Phase 5C — New Files Summary

| File | Task | Purpose |
|------|------|---------|
| `backend/alembic/versions/s17a1_file_suggestions.py` | P5C-01 | Migration: file_suggestions table + testability field |
| `backend/alembic/versions/s17b1_mismatch_clarifications.py` | P5C-03 | Migration: mismatch_clarifications table |
| `backend/alembic/versions/s17c1_uat_checklist.py` | P5C-04 | Migration: uat_checklist_items table |
| `backend/alembic/versions/s17d1_compliance_snapshots.py` | P5C-08 | Migration: compliance_score_snapshots table |
| `backend/alembic/versions/s17e1_ci_webhook_config.py` | P5C-06 | Migration: ci_webhook_configs table |
| `backend/app/models/file_suggestion.py` | P5C-01 | FileSuggestion ORM model |
| `backend/app/models/mismatch_clarification.py` | P5C-03 | MismatchClarification ORM model |
| `backend/app/models/uat_checklist_item.py` | P5C-04 | UATChecklistItem ORM model |
| `backend/app/models/compliance_score_snapshot.py` | P5C-08 | ComplianceScoreSnapshot ORM model |
| `backend/app/models/ci_webhook_config.py` | P5C-06 | CIWebhookConfig ORM model |
| `backend/app/services/file_suggestion_service.py` | P5C-01 | AI file suggestion generation + storage |
| `backend/app/services/test_suite_service.py` | P5C-05 | Pytest test file generation + zip packaging |
| `backend/app/services/fix_suggestion_service.py` | P5C-07 | AI fix suggestion + lazy cache in details |
| `backend/app/services/compliance_snapshot_service.py` | P5C-08 | Daily snapshot service + upsert logic |
| `backend/app/crud/crud_mismatch_clarification.py` | P5C-03 | CRUD: create, answer, close, get_by_mismatch |
| `backend/app/tasks/test_generation_tasks.py` | P5C-05 | Celery task: async test suite generation |
| `backend/app/tasks/analytics_tasks.py` | P5C-08 | Celery beat: nightly compliance snapshots |
| `backend/app/api/endpoints/analytics.py` | P5C-09 | Analytics router: compliance-overview endpoint |
| `frontend/components/documents/FileSuggestionBanner.tsx` | P5C-01 | Banner showing files needed + atom count |
| `frontend/components/documents/RequestUploadModal.tsx` | P5C-02 | Modal: select team members + send notification |
| `frontend/components/validation/MismatchClarificationPanel.tsx` | P5C-03 | Q&A thread on mismatch card |
| `frontend/components/validation/UATChecklist.tsx` | P5C-04 | UAT checklist tab with pass/fail/blocked |
| `frontend/components/validation/TestSuiteDownload.tsx` | P5C-05 | Download button + polling logic |
| `frontend/components/settings/CIWebhookCard.tsx` | P5C-06 | CI webhook setup + secret display |
| `frontend/components/validation/MismatchSuggestedFix.tsx` | P5C-07 | Expandable fix suggestion panel |
| `frontend/components/validation/ComplianceTrendChart.tsx` | P5C-08 | Recharts line chart for compliance trend |
| `frontend/pages/analytics/compliance.tsx` | P5C-09 | CTO executive compliance dashboard page |
| `frontend/hooks/useFileSuggestions.ts` | P5C-01 | SWR hook for file suggestions |
| `frontend/hooks/useTeamMembers.ts` | P5C-02 | SWR hook for team members list |
| `frontend/hooks/useClarifications.ts` | P5C-03 | SWR hook for mismatch clarifications |
| `frontend/hooks/useUATChecklist.ts` | P5C-04 | SWR hook for UAT checklist |

## Phase 5C — Completion Checklist

### Database (5 migrations)
- [ ] `s17a1` — `file_suggestions` table + `requirement_atoms.testability` + `documents.file_suggestion_summary`
- [ ] `s17b1` — `mismatch_clarifications` table with status CHECK constraint
- [ ] `s17c1` — `uat_checklist_items` table with result CHECK constraint
- [ ] `s17d1` — `compliance_score_snapshots` table with unique constraint on (document_id, snapshot_date)
- [ ] `s17e1` — `ci_webhook_configs` table with per-tenant HMAC secret

### Backend Services
- [ ] `FileSuggestionService.generate_and_store()` triggered after atomization
- [ ] `TestSuiteService.generate_zip()` packages pytest files as a zip
- [ ] `FixSuggestionService.get_or_generate()` lazy-generates and caches AI fix
- [ ] `ComplianceSnapshotService.capture_for_document()` + `capture_all_active_documents()`

### Backend Tasks
- [ ] `nightly_compliance_snapshots` Celery beat task registered at midnight UTC
- [ ] `generate_test_suite` Celery task with Redis result storage (1h TTL)

### Backend Endpoints
- [ ] `GET /documents/{id}/file-suggestions`
- [ ] `GET /documents/{id}/team-members`
- [ ] `POST /documents/{id}/request-uploads`
- [ ] `POST /validation/mismatches/{id}/clarification`
- [ ] `POST /validation/mismatches/{id}/clarification/{cid}/answer`
- [ ] `GET /validation/mismatches/{id}/clarifications`
- [ ] `GET /validation/{document_id}/uat-checklist`
- [ ] `POST /validation/{document_id}/uat-checklist/{item_id}/check`
- [ ] `POST /validation/{document_id}/generate-tests`
- [ ] `GET /validation/{document_id}/download-tests`
- [ ] `POST /validation/mismatches/{id}/suggest-fix`
- [ ] `DELETE /validation/mismatches/{id}/suggest-fix`
- [ ] `GET /validation/{document_id}/compliance-trend`
- [ ] `POST /webhooks/ci/test-results`
- [ ] `POST /integrations/ci/setup`
- [ ] `GET /integrations/ci/status`
- [ ] `GET /analytics/compliance-overview`

### Frontend Components
- [ ] `FileSuggestionBanner` on document detail page
- [ ] `RequestUploadModal` wired to banner's "Request Upload" button
- [ ] `MismatchClarificationPanel` on each mismatch card
- [ ] `UATChecklist` tab on validation panel
- [ ] `TestSuiteDownload` button on validation panel
- [ ] `CIWebhookCard` in settings integrations section
- [ ] `MismatchSuggestedFix` on each mismatch card
- [ ] `ComplianceTrendChart` replacing static score on validation panel
- [ ] Compliance Dashboard page at `/analytics/compliance`
- [ ] Sidebar nav link for CTO/Tech Lead roles

### Notifications wired
- [ ] `upload_request` — when BA requests code upload (P5C-02)
- [ ] `clarification_requested` — when BA asks developer a question (P5C-03)
- [ ] `clarification_answered` — when developer answers (P5C-03)


---

## KNOWN IMPLEMENTATION BUGS — Fix Before Execution

> These bugs were identified during a solution architect review of the full plan against the live
> codebase. Each one will cause a runtime error or silent failure if not patched before the
> affected task is coded. Assign one developer to fix these as the FIRST action before any
> Phase 5C code is written.

---

### BUG-01 — `Document.title` Field Does Not Exist

**Severity:** HIGH — Runtime `AttributeError` on first use
**Affects:** P5C-05 (`TestSuiteService`), P5C-09 (`compliance_overview` endpoint), P5B-12 (certificate generation)
**Discovery:** The `Document` model (`backend/app/models/document.py`) has no `title` column. The only name field is `filename`.

**Everywhere in P5C/P5B-12 code that reads:**
```python
doc.title
doc.title or "Untitled"
"document_title": doc.title
```

**Replace with:**
```python
doc.filename
doc.filename or "Untitled"
"document_title": doc.filename
```

**If a human-readable title separate from the filename is needed long-term,** add it in the same migration that first needs it (s17a1). Add to s17a1 upgrade():
```python
op.add_column('documents', sa.Column('title', sa.String(512), nullable=True))
```
And add to Document model:
```python
title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
```
Then render as: `doc.title or doc.filename`

**Resolution:** Patch all plan code snippets now OR add the column in s17a1. Decide before starting P5C.

---

### BUG-02 — `User.full_name` Field Does Not Exist

**Severity:** HIGH — `None` silently replaces expected display name in all notifications
**Affects:** P5C-02 (`request-uploads` endpoint), P5C-03 (clarification notifications), P5B-04 (false positive audit trail), P5B-12 (certificate `signed_by`)
**Discovery:** The `User` model (`backend/app/models/user.py`) only has `email`, `hashed_password`, `is_active`, `is_superuser`, `roles`. There is no `full_name` field.

**Every plan snippet that writes:**
```python
current_user.full_name or current_user.email
```
evaluates as `None or current_user.email` → always returns `current_user.email`. This means notifications always say the email address, never a name. Functionally this works but looks unprofessional.

**Short-term fix (no migration — P5C is unblocked immediately):**
```python
# Replace in all P5C/P5B notification code:
current_user.full_name or current_user.email
# With:
current_user.email   # clean, no None risk
```

**Long-term fix (optional, add to s17a1 migration):**
```python
# In s17a1 upgrade():
op.add_column('users', sa.Column('full_name', sa.String(255), nullable=True))

# In User model:
full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```
Then `current_user.full_name or current_user.email` works as intended.

**Resolution:** Either patch all snippets to use `current_user.email` directly, OR add the column in s17a1. The second option is better UX.

---

### BUG-03 — `from app.core.redis import get_redis_client` — Module Does Not Exist

**Severity:** HIGH — `ImportError` on Celery task startup, crashes the entire worker
**Affects:** P5C-05 (`test_generation_tasks.py` Celery task)
**Discovery:** `backend/app/core/` contains only: `config.py`, `exceptions.py`, `logging.py`, `permissions.py`, `security.py`. There is no `redis.py`. Redis is only accessible through `CacheService` in `backend/app/services/cache_service.py`.

**The plan writes:**
```python
from app.core.redis import get_redis_client
redis = get_redis_client()
redis.set(redis_key, zip_bytes, ex=3600)
```

**Fix option A — Use CacheService (recommended, already tested):**
```python
from app.services.cache_service import CacheService
cache = CacheService()
# CacheService.set() stores JSON — but zip_bytes is binary, so encode:
import base64
cache.set(redis_key, base64.b64encode(zip_bytes).decode(), ttl=3600)
# On retrieval:
raw = cache.get(redis_key)
zip_bytes = base64.b64decode(raw) if raw else None
```

**Fix option B — Create the missing module (clean, reusable):**

**New file: `backend/app/core/redis.py`**
```python
# backend/app/core/redis.py
"""Thin wrapper around redis-py. Exposes a singleton get_redis_client() function.
Use for raw bytes storage (e.g. zip files). Use CacheService for JSON key-value cache."""
import redis as redis_lib
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("core.redis")
_client = None


def get_redis_client() -> redis_lib.Redis:
    global _client
    if _client is None:
        try:
            _client = redis_lib.from_url(settings.REDIS_URL, decode_responses=False)
            _client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            raise
    return _client
```

**Resolution:** Create `backend/app/core/redis.py` as the first file created in P5C-05 sprint. The developer must not start `test_generation_tasks.py` before this file exists.

---

### BUG-04 — `asyncio.run()` Inside Celery Workers Is Unsafe

**Severity:** HIGH — Crashes Celery workers using gevent/eventlet or Python 3.12+
**Affects:** P5C-01 (`document_pipeline.py` hook for file suggestion), P5C-05 (`generate_test_suite` Celery task), P4-07 (BOE notification inside code analysis task)

**The plan writes in Celery task bodies:**
```python
asyncio.run(
    file_suggestion_service.generate_and_store(db=db, ...)
)
```

**Why this breaks:**
1. `asyncio.run()` creates a **new event loop** and blocks the calling thread
2. If the Celery worker uses gevent or eventlet (event loop already running), `asyncio.run()` raises `RuntimeError: This event loop is already running`
3. In Python 3.12+, `asyncio.run()` in certain contexts emits deprecation warnings and can deadlock
4. The existing pattern in `code_analysis_tasks.py` uses synchronous calls only — no `asyncio.run()`

**Fix — Use the safe pattern already established in the codebase:**

For services that need to call async functions from sync Celery tasks:

**Option A — Make the service method synchronous (preferred):**
```python
# In FileSuggestionService, add a sync wrapper:
def generate_and_store_sync(self, db, *, document_id, tenant_id):
    """Synchronous wrapper for use in Celery tasks."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            self.generate_and_store(db=db, document_id=document_id, tenant_id=tenant_id)
        )
    finally:
        loop.close()
        asyncio.set_event_loop(None)
```

**Option B — Refactor the service to be synchronous from the start:**
Since `call_gemini_for_file_suggestions` is the only async call inside `generate_and_store`, and the Gemini client supports sync calls, the entire service can be written synchronously. The plan uses `async def` unnecessarily for these services.

**Rule going forward for ALL P5B and P5C services called from Celery:**
- If a service is ONLY called from Celery tasks → write it as `def` (synchronous)
- If a service is ONLY called from FastAPI endpoints → `async def` is fine
- If called from both → provide a `_sync` wrapper using the `new_event_loop` pattern above

**Resolution:** Before any P5C service is coded, decide synchronous vs async. The safer default is synchronous — FastAPI can call sync services fine; the reverse is what breaks.

---

### BUG-05 — Mismatch Model Multi-Ticket Edit Conflict (Data Integrity Risk)

**Severity:** MEDIUM — Not a runtime crash but causes model/migration desync if not managed
**Affects:** P5B-03, P5B-04, P5B-10, P5B-11 — all four tickets modify `backend/app/models/mismatch.py`
**Discovery:** The plan adds fields to `Mismatch` across 4 separate tickets in 4 separate migrations:
- P5B-03 adds `jira_issue_key`, `jira_issue_url` → migration s16b1
- P5B-04 adds `resolution_note`, `status_changed_by_id`, `status_changed_at` → also s16b1
- P5B-10 migrates `status` default + adds CHECK constraint → migration s16d1
- P5B-11 adds `document_version_id`, `created_commit_hash`, `resolved_commit_hash` → migration s16e1

**The risk:** If a developer implements P5B-03's model changes (adds `jira_issue_key` to `mismatch.py`) and pushes that model file, then another developer doing P5B-10 also edits `mismatch.py` to add the CHECK constraint — they will have a merge conflict. Worse: if P5B-10's CHECK constraint `status IN ('open', 'in_progress', ...)` is applied to the model **before** s16d1 migration runs (which renames `"new"` → `"open"`), existing rows with `status="new"` will fail the CHECK.

**Fix — Single-owner rule + staged model updates:**

**Rule:** ONE developer owns `backend/app/models/mismatch.py` for the entire Phase 5B sprint. No PR that touches this file is merged without that developer's explicit review.

**Staged approach:**
```
Step 1: Write ALL migrations first (s16a1 through s16f1) in sequence, test on empty DB
Step 2: Apply ALL migrations to staging DB: alembic upgrade s16f1
Step 3: Run data migration: UPDATE mismatches SET status='open' WHERE status='new'
Step 4: ONLY THEN update mismatch.py with all new fields + CHECK constraint in one PR
Step 5: Deploy model change
```

**The model file edit sequence must be:**
```python
# ALL of these fields added in ONE commit to mismatch.py:
jira_issue_key: Mapped[Optional[str]]       # P5B-03
jira_issue_url: Mapped[Optional[str]]       # P5B-03
resolution_note: Mapped[Optional[str]]      # P5B-04
status_changed_by_id: Mapped[Optional[int]] # P5B-04
status_changed_at: Mapped[Optional[datetime]] # P5B-04
document_version_id: Mapped[Optional[int]]  # P5B-11
created_commit_hash: Mapped[Optional[str]]  # P5B-11
resolved_commit_hash: Mapped[Optional[str]] # P5B-11
# AND the CHECK constraint on status — ONLY after s16d1 migration confirms all rows have valid status
```

**Resolution:** Create a `mismatch.py` ownership rule in team standup before Phase 5B starts.

---

## Bug Fix Sprint Checklist

These are pre-conditions for Phase 5C to execute cleanly. Mark all done before the P5C sprint starts:

- [ ] **BUG-01** — `doc.title` → either replace with `doc.filename` everywhere OR add `title` column to `documents` in s17a1
- [ ] **BUG-02** — `user.full_name` → either replace with `user.email` everywhere OR add `full_name` column to `users` in s17a1
- [ ] **BUG-03** — Create `backend/app/core/redis.py` with `get_redis_client()` before starting P5C-05
- [ ] **BUG-04** — Review all async service methods called from Celery tasks; add `_sync` wrappers or refactor to sync
- [ ] **BUG-05** — Assign single developer to own `mismatch.py`; agree on staged migration + model update sequence before Phase 5B starts


---

# PHASE 3 — Request Data Flow Diagrams (Premium Visual Intelligence)

## Solution Architect Preamble

**What this phase builds:** When a developer opens any code file in DokyDoc today, they see raw JSON and a knowledge graph. A BA sees nothing useful. A CTO sees nothing at all. Phase 3 changes this by adding a **visual swimlane diagram** that shows the exact journey of a request through the codebase:

```
POST /register → validate(UserCreateSchema) → AuthService.register()
  → UserCRUD.create() → users table (id, email, password_hash)
  → EmailService.send_welcome() → SendGrid API
```

**Why it costs zero extra Gemini money:** All data already exists in `CodeComponent.structured_analysis` (JSONB) from Sprint 3. The `DataFlowService` is a **deterministic parser** — it reads existing JSON and derives edges algorithmically. Four new optional fields added to the prompt (P3.1) only enrich NEW files analyzed going forward; existing records work immediately.

**Who benefits:**
- **Developer** — sees who calls them and who they call; navigates entire request trace by clicking nodes
- **BA** — "Business View" mode shows human labels in swimlanes, no function names; understands system behavior without reading code
- **CXO/Tech Lead** — executive diagram of system flow per feature for architecture reviews
- **QA** — sees all data entry/exit points for a request; generates test boundary list

**Premium gate:** Free tier sees a blurred preview with an upsell card. Pro and Enterprise see the full interactive diagram.

---

## Developer Ownership (Phase 3)

| File | Owner |
|------|-------|
| `backend/app/services/ai/prompt_manager.py` | **BE-P3** (coordinate with Phase 5 developer — same file) |
| `backend/app/models/code_data_flow_edge.py` | BE-P3 (new file) |
| `backend/app/crud/crud_code_data_flow_edge.py` | BE-P3 (new file) |
| `backend/app/services/data_flow_service.py` | BE-P3 (new file) |
| `backend/app/tasks/data_flow_tasks.py` | BE-P3 (new file) |
| `backend/app/api/endpoints/code_components.py` | BE-P3 (additive only — new endpoints appended) |
| `backend/app/api/endpoints/repositories.py` | BE-P3 (additive only — one endpoint appended) |
| `backend/app/schemas/code_component.py` | BE-P3 (additive — new schemas appended) |
| `backend/alembic/versions/s13a1_code_data_flow_edges.py` | BE-P3 (new file) |
| `frontend/components/data-flow/DataFlowDiagram.tsx` | FE-P3 (new file) |
| `frontend/components/data-flow/RequestTracePanel.tsx` | FE-P3 (new file) |
| `frontend/components/data-flow/EdgeListPanel.tsx` | FE-P3 (new file) |
| `frontend/components/data-flow/PremiumGateCard.tsx` | FE-P3 (new file) |
| `frontend/app/dashboard/code/[id]/page.tsx` | FE-P3 (additive — new tab only) |
| `frontend/hooks/useDataFlow.ts` | FE-P3 (new file) |

**Rule:** BE-P3 developer must coordinate with Phase 5 developer before touching `prompt_manager.py`. Both changes (P3.1 output schema + P5-03 input prefix injection) must be reviewed together to avoid git conflicts. Recommended: Phase 5 developer makes their change first (P5-03), then BE-P3 developer rebases on top and adds P3.1 fields.

**Phase 3 can run fully in parallel with Phase 5B.** No shared files.

**Sprint estimate:** 6–7 days for 1 backend + 1 frontend developer working in parallel.

---

## Migration Chain (Phase 3)

```
s12a1 (training_examples — existing baseline)
  └── s13a1 (code_data_flow_edges — Phase 3)
       └── s14a1 (concept_mapping fields — Phase 4, separate chain)
```

Phase 3 migration is independent. Can be deployed before or after Phase 4/5.

---

## P3.1 — Enhance ENHANCED_SEMANTIC_ANALYSIS Prompt (Additive Fields)

**Priority:** P1 — Must happen before any new code analysis runs; enriches future analyses
**Complexity:** LOW — Additive prompt change; backward compatible
**Risk:** LOW — Old `structured_analysis` records remain valid; new fields are OPTIONAL

### Why This Exists

The current `ENHANCED_SEMANTIC_ANALYSIS` prompt (lines 752–930 of `prompt_manager.py`) extracts 7 sections: `business_rules`, `api_contracts`, `data_model_relationships`, `security_patterns`, `component_interactions`, `data_flows`, `components`. These sections contain the raw material for data flow diagrams, but 4 pieces of structured metadata are missing that make deterministic graph building significantly more accurate:

1. **`file_role`** — normalized enum (ENDPOINT/SERVICE/SCHEMA/MODEL/CRUD/etc.) is more stable than the 17-value `file_type` string
2. **`backed_by_model`** — for schema files: which DB table + which columns map to which schema fields
3. **`model_definition`** — for model files: exact column names, types, and constraints
4. **`outbound_calls`** — for service/CRUD files: structured list of what external modules/functions are called

Without these fields, the `DataFlowService` falls back to parsing free-text `component_interactions` which is messy. With them, graph building is deterministic and accurate.

### Current State

**File:** `backend/app/services/ai/prompt_manager.py`
**Lines 885–895** (the CRITICAL section at the bottom of the prompt, before `CODE TO ANALYZE:`):

```python
CRITICAL:
- For business_rules: Extract ACTUAL rules from code logic, not just comments
- For api_contracts: Include ALL endpoints with their full contract
- For data_model_relationships: Include FK constraints and cascade behavior
- For security_patterns: Note GAPS as well as implemented patterns
- For component_interactions: Extract ALL function-to-function calls...
- For data_flows: Trace how data enters, transforms, and exits...
- If a section is not applicable to this file type, return an empty array []

CODE TO ANALYZE:
```

**Lines 905–916** (expected_schema properties):
```python
"properties": {
    "language_info": {"type": "object"},
    "business_rules": {"type": "array"},
    "api_contracts": {"type": "array"},
    "data_model_relationships": {"type": "array"},
    "security_patterns": {"type": "array"},
    "component_interactions": {"type": "array"},
    "data_flows": {"type": "array"},
    "components": {"type": "array"},
    ...
}
```

### What to Change

**Step 1 — Add 4 new optional sections to the prompt body (insert BEFORE the existing CRITICAL block):**

In `prompt_manager.py`, find the line that reads `"8. **STANDARD ANALYSIS**"` (or the last numbered analysis instruction). Add after item 7 (`DATA FLOWS`):

```python
"""
8. **FILE ROLE** — Classify this file into exactly one normalized role:
   - "ENDPOINT": HTTP handler/router file (FastAPI router, Express handler, Django view)
   - "SERVICE": Business logic service class (AuthService, PaymentService, etc.)
   - "SCHEMA": Data validation/serialization schema (Pydantic, Zod, Marshmallow)
   - "MODEL": Database model/entity (SQLAlchemy, TypeORM, Prisma model)
   - "CRUD": Database access layer (CRUD class, Repository pattern)
   - "MIDDLEWARE": Request/response interceptor, authentication decorator
   - "UTILITY": Helper functions, shared utilities, constants
   - "CONFIG": Configuration, environment settings, constants
   - "TEST": Test file
   - "MIGRATION": Database migration file
   Return as a single string under "file_role".

9. **MODEL DEFINITION** — ONLY for MODEL/MIGRATION files:
   Extract the DB table name and ALL columns with types.
   Return as "model_definition": { "table_name": "...", "columns": [...] }
   Skip entirely (omit the key) for non-MODEL files.

10. **SCHEMA MAPPING** — ONLY for SCHEMA files:
    Map each schema field to the underlying DB column if discernible.
    Return as "backed_by_model": { "table_name": "...", "model_class": "...", "fields": [...] }
    Skip entirely (omit the key) for non-SCHEMA files.

11. **OUTBOUND CALLS** — ONLY for ENDPOINT/SERVICE/CRUD files:
    List every call this file makes to an external module, service, or DB.
    For each call: { "caller_function": "...", "target_module": "...",
                     "target_function": "...", "data_in": "...", "data_out": "..." }
    "target_module" must be the import path (e.g. "services.auth_service", "crud.users")
    so it can be matched to other CodeComponent records.
    Skip entirely (omit the key) for SCHEMA/MODEL/CONFIG/TEST files.
"""
```

**Step 2 — Update the STRICT RESPONSE FORMAT JSON block** (inside the prompt string, add 4 new optional keys after `"data_flows"`):

```python
        "file_role": "ENDPOINT|SERVICE|SCHEMA|MODEL|CRUD|MIDDLEWARE|UTILITY|CONFIG|TEST|MIGRATION",
        "model_definition": {
            "table_name": "users",
            "columns": [
                {"name": "id", "type": "Integer", "primary_key": true, "nullable": false, "indexed": true},
                {"name": "email", "type": "String", "nullable": false, "indexed": true}
            ]
        },
        "backed_by_model": {
            "table_name": "users",
            "model_class": "User",
            "fields": [
                {"schema_field": "email", "model_column": "email", "type": "EmailStr"},
                {"schema_field": "id", "model_column": "id", "type": "int"}
            ]
        },
        "outbound_calls": [
            {
                "caller_function": "create_user",
                "target_module": "services/auth_service",
                "target_function": "AuthService.register",
                "data_in": "UserCreateRequest",
                "data_out": "User"
            }
        ]
```

**Step 3 — Update the CRITICAL block** to add guidance for the new fields:

```python
- For file_role: Classify into exactly one value from the enum above; prefer specificity
- For model_definition: Only for MODEL files — extract ALL columns, not just a sample
- For backed_by_model: Only for SCHEMA files — trace field names back to DB columns
- For outbound_calls: Only for ENDPOINT/SERVICE/CRUD files — include ALL cross-module calls;
  use the actual import path for target_module so it can be resolved to other files
- ALL FOUR NEW FIELDS ARE OPTIONAL — omit entirely if not applicable to this file type
```

**Step 4 — Update `expected_schema`** in the same prompt definition dict:

```python
# Add inside "properties" of structured_analysis:
"file_role": {"type": "string"},
"model_definition": {"type": "object"},
"backed_by_model": {"type": "object"},
"outbound_calls": {"type": "array"},
```

### Test Commands

```bash
# 1. Verify prompt was updated (no syntax error):
python -c "from app.services.ai.prompt_manager import prompt_manager; print('OK')"

# 2. Re-analyze one file and check new fields appear:
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/code-components/{id}/retry
# Wait for analysis to complete, then:
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/code-components/{id} | jq '.structured_analysis.file_role'
# Expected: "SERVICE" or "ENDPOINT" etc.

# 3. Verify old records still load (backward compat):
psql -c "SELECT id, structured_analysis->>'file_role' FROM code_components LIMIT 10"
# Old records: NULL (field absent) — that's fine, DataFlowService handles this
```

### Risk Assessment
- **Pure additive** — existing `structured_analysis` records are untouched; null fields handled by DataFlowService fallback
- **No migration** — no DB schema change; `structured_analysis` is already a JSONB column
- **Coordinate with P5-03** — both changes touch `prompt_manager.py`; resolve in same PR or rebase


---

## P3.2 — New DB Model: `CodeDataFlowEdge`

**Priority:** P0 — All other Phase 3 tasks depend on this table existing
**Complexity:** LOW — New model, clean migration
**Risk:** LOW — New table; no existing table modified

### Why This Exists

The `DataFlowService` needs to persist the edges it derives from `structured_analysis`. Edges must be stored (not computed on every request) because:
1. Request trace BFS traverses multiple components — needs fast edge lookup by `source_component_id`
2. Edges need to survive re-deployment (cannot be recomputed from `structured_analysis` in an API request without Gemini cost)
3. Enables the admin backfill task to incrementally build edges without re-running AI

### DB Migration

**New file: `backend/alembic/versions/s13a1_code_data_flow_edges.py`**

```python
# backend/alembic/versions/s13a1_code_data_flow_edges.py
"""Add code_data_flow_edges table for Phase 3 Data Flow Diagrams

Revision ID: s13a1
Revises: s12a1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = 's13a1'
down_revision = 's12a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'code_data_flow_edges',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer, nullable=False),
        sa.Column('repository_id', sa.Integer,
                  sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True),
        # The file that INITIATES the flow (always present)
        sa.Column('source_component_id', sa.Integer,
                  sa.ForeignKey('code_components.id', ondelete='CASCADE'), nullable=False),
        # The file that RECEIVES the flow (null = external system like SendGrid, Redis)
        sa.Column('target_component_id', sa.Integer,
                  sa.ForeignKey('code_components.id', ondelete='SET NULL'), nullable=True),
        # Edge classification
        sa.Column('edge_type', sa.String(30), nullable=False),
        # "HTTP_TRIGGER" | "SERVICE_CALL" | "SCHEMA_VALIDATION" |
        # "DB_READ" | "DB_WRITE" | "EXTERNAL_API" | "CACHE_READ" |
        # "CACHE_WRITE" | "EVENT_PUBLISH" | "EVENT_CONSUME"
        # Function-level details
        sa.Column('source_function', sa.String(200), nullable=True),
        sa.Column('target_function', sa.String(200), nullable=True),
        # Data descriptions
        sa.Column('data_in_description', sa.Text, nullable=True),   # "UserCreateRequest (email, password)"
        sa.Column('data_out_description', sa.Text, nullable=True),  # "User object with id"
        # Human-readable label for Business View mode
        sa.Column('human_label', sa.String(500), nullable=True),    # "Saves registration data"
        # For edges where target_component_id is NULL (external systems)
        sa.Column('external_target_name', sa.String(200), nullable=True),  # "SendGrid", "Redis", "S3"
        # Position in the flow (for ordered swimlane rendering)
        sa.Column('step_index', sa.Integer, nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # Indexes for fast BFS traversal
    op.create_index('ix_cdf_source', 'code_data_flow_edges', ['source_component_id'])
    op.create_index('ix_cdf_target', 'code_data_flow_edges', ['target_component_id'])
    op.create_index('ix_cdf_tenant', 'code_data_flow_edges', ['tenant_id'])
    op.create_index('ix_cdf_repo', 'code_data_flow_edges', ['repository_id'])
    op.create_index('ix_cdf_source_type', 'code_data_flow_edges', ['source_component_id', 'edge_type'])

    # CHECK constraint on edge_type
    op.create_check_constraint(
        'ck_cdf_edge_type',
        'code_data_flow_edges',
        "edge_type IN ('HTTP_TRIGGER','SERVICE_CALL','SCHEMA_VALIDATION','DB_READ','DB_WRITE',"
        "'EXTERNAL_API','CACHE_READ','CACHE_WRITE','EVENT_PUBLISH','EVENT_CONSUME')"
    )


def downgrade():
    op.drop_table('code_data_flow_edges')
```

### New Model

**New file: `backend/app/models/code_data_flow_edge.py`**

```python
# backend/app/models/code_data_flow_edge.py
"""
CodeDataFlowEdge — stores one directed edge in the request data flow graph.

source_component_id → target_component_id (or external_target_name if target is NULL)

Edge types:
  HTTP_TRIGGER      — User/client calls an HTTP endpoint
  SERVICE_CALL      — One service calls another service's method
  SCHEMA_VALIDATION — Service validates input/output against a schema
  DB_READ           — Component reads from a database table
  DB_WRITE          — Component writes to a database table
  EXTERNAL_API      — Component calls an external API (SendGrid, Stripe, etc.)
  CACHE_READ        — Component reads from Redis/Memcached
  CACHE_WRITE       — Component writes to Redis/Memcached
  EVENT_PUBLISH     — Component publishes an event/message (Kafka, RabbitMQ, Celery)
  EVENT_CONSUME     — Component consumes an event/message
"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

if TYPE_CHECKING:
    from .code_component import CodeComponent


VALID_EDGE_TYPES = {
    "HTTP_TRIGGER", "SERVICE_CALL", "SCHEMA_VALIDATION",
    "DB_READ", "DB_WRITE", "EXTERNAL_API",
    "CACHE_READ", "CACHE_WRITE", "EVENT_PUBLISH", "EVENT_CONSUME",
}

# Human-readable label templates per edge type
EDGE_LABEL_TEMPLATES = {
    "HTTP_TRIGGER": "User calls {method} {path}",
    "SERVICE_CALL": "{source} invokes {target}",
    "SCHEMA_VALIDATION": "Validates data using {target}",
    "DB_READ": "Reads from {table}",
    "DB_WRITE": "Saves to {table}",
    "EXTERNAL_API": "Calls external: {name}",
    "CACHE_READ": "Reads cache: {key}",
    "CACHE_WRITE": "Writes cache: {key}",
    "EVENT_PUBLISH": "Publishes event: {topic}",
    "EVENT_CONSUME": "Consumes event: {topic}",
}

# Swimlane assignment per file_role
SWIMLANE_MAP = {
    "ENDPOINT": "API Layer",
    "MIDDLEWARE": "API Layer",
    "SERVICE": "Business Logic",
    "SCHEMA": "Validation",
    "CRUD": "Data Access",
    "MODEL": "Database",
    "UTILITY": "Utilities",
    "CONFIG": "Configuration",
    None: "External Services",   # target_component_id is None → external
}


class CodeDataFlowEdge(Base):
    __tablename__ = "code_data_flow_edges"
    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('HTTP_TRIGGER','SERVICE_CALL','SCHEMA_VALIDATION','DB_READ',"
            "'DB_WRITE','EXTERNAL_API','CACHE_READ','CACHE_WRITE','EVENT_PUBLISH','EVENT_CONSUME')",
            name="ck_cdf_edge_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    repository_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_component_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_components.id", ondelete="SET NULL"), nullable=True, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_function: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    target_function: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    data_in_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_out_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    human_label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_target_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    source_component: Mapped["CodeComponent"] = relationship(
        "CodeComponent", foreign_keys=[source_component_id]
    )
    target_component: Mapped[Optional["CodeComponent"]] = relationship(
        "CodeComponent", foreign_keys=[target_component_id]
    )
```

**Add to `backend/app/models/__init__.py`:**
```python
from .code_data_flow_edge import CodeDataFlowEdge  # noqa: F401
```

**Add to `backend/app/db/base.py`:**
```python
from app.models.code_data_flow_edge import CodeDataFlowEdge  # noqa: F401
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s13a1

# 2. Verify table + indexes + CHECK constraint
psql -c "\d code_data_flow_edges"
psql -c "SELECT indexname FROM pg_indexes WHERE tablename='code_data_flow_edges'"

# 3. Verify CHECK constraint works
psql -c "INSERT INTO code_data_flow_edges (tenant_id, source_component_id, edge_type) VALUES (1, 1, 'INVALID_TYPE')"
# Expected: ERROR: new row violates check constraint "ck_cdf_edge_type"
```

### Risk Assessment
- **CASCADE on source** — if a CodeComponent is deleted, its edges auto-delete; graph stays clean
- **SET NULL on target** — if a target component is deleted, edge remains with `target_component_id=NULL`; renders as external node in diagram
- **No FK on repository_id for standalone components** — some CodeComponents have no repository (standalone upload); `repository_id` is nullable


---

## P3.3 — CRUD: `CRUDCodeDataFlowEdge`

**Priority:** P0 — Required by DataFlowService and API endpoints
**Complexity:** LOW — Standard CRUD pattern matching existing cruds

### New File: `backend/app/crud/crud_code_data_flow_edge.py`

```python
# backend/app/crud/crud_code_data_flow_edge.py
"""
CRUD operations for CodeDataFlowEdge.
Optimised for graph traversal: get_by_source, get_by_target, get_egocentric.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.code_data_flow_edge import CodeDataFlowEdge
from app.core.logging import get_logger

logger = get_logger("crud_code_data_flow_edge")


class CRUDCodeDataFlowEdge:

    def get_by_source(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> list[CodeDataFlowEdge]:
        """
        Return all outgoing edges from this component.
        Used to build the 'Calls' panel and traverse BFS forward.
        """
        return db.query(CodeDataFlowEdge).filter(
            CodeDataFlowEdge.source_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).order_by(CodeDataFlowEdge.step_index.asc().nullslast()).all()

    def get_by_target(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> list[CodeDataFlowEdge]:
        """
        Return all incoming edges to this component.
        Used to build the 'Called By' panel.
        """
        return db.query(CodeDataFlowEdge).filter(
            CodeDataFlowEdge.target_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).all()

    def get_egocentric(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> list[CodeDataFlowEdge]:
        """
        Return all edges where this component is source OR target.
        Used for the 'This File Only' data flow view.
        """
        return db.query(CodeDataFlowEdge).filter(
            or_(
                CodeDataFlowEdge.source_component_id == component_id,
                CodeDataFlowEdge.target_component_id == component_id,
            ),
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).order_by(CodeDataFlowEdge.step_index.asc().nullslast()).all()

    def get_subgraph(
        self,
        db: Session,
        *,
        component_ids: list[int],
        tenant_id: int,
    ) -> list[CodeDataFlowEdge]:
        """
        Return all edges where BOTH source and target are in component_ids.
        Used to build the subgraph for BFS result rendering.
        """
        from sqlalchemy import and_
        return db.query(CodeDataFlowEdge).filter(
            CodeDataFlowEdge.tenant_id == tenant_id,
            or_(
                CodeDataFlowEdge.source_component_id.in_(component_ids),
                CodeDataFlowEdge.target_component_id.in_(component_ids),
            ),
        ).all()

    def get_by_repository(
        self,
        db: Session,
        *,
        repository_id: int,
        tenant_id: int,
    ) -> list[CodeDataFlowEdge]:
        """Return all edges in a repository. Used by backfill and overview."""
        return db.query(CodeDataFlowEdge).filter(
            CodeDataFlowEdge.repository_id == repository_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).all()

    def delete_by_component(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> int:
        """
        Delete all edges where this component is the SOURCE.
        Called before rebuilding edges for a re-analyzed component.
        Returns count deleted.
        """
        count = db.query(CodeDataFlowEdge).filter(
            CodeDataFlowEdge.source_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.commit()
        return count

    def bulk_create(
        self,
        db: Session,
        *,
        edges: list[dict],
    ) -> int:
        """
        Batch insert edges. Returns count created.

        Each dict in edges must have:
          tenant_id, source_component_id, edge_type
        Optional: target_component_id, repository_id, source_function,
                  target_function, data_in_description, data_out_description,
                  human_label, external_target_name, step_index
        """
        if not edges:
            return 0
        db_objs = [CodeDataFlowEdge(**e) for e in edges]
        db.add_all(db_objs)
        db.commit()
        return len(db_objs)

    def count_by_repository(
        self,
        db: Session,
        *,
        repository_id: int,
        tenant_id: int,
    ) -> dict:
        """Return edge type breakdown for a repository. Used in analytics."""
        from sqlalchemy import func
        rows = db.query(
            CodeDataFlowEdge.edge_type,
            func.count(CodeDataFlowEdge.id).label("count"),
        ).filter(
            CodeDataFlowEdge.repository_id == repository_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        ).group_by(CodeDataFlowEdge.edge_type).all()
        return {r.edge_type: r.count for r in rows}


crud_code_data_flow_edge = CRUDCodeDataFlowEdge()
```

**Add to `backend/app/crud/__init__.py`:**
```python
from .crud_code_data_flow_edge import crud_code_data_flow_edge  # noqa: F401
```


---

## P3.4 — New Service: `DataFlowService`

**Priority:** P0 — Core Phase 3 logic. Everything else depends on this.
**Complexity:** HIGH — BFS traversal, Mermaid rendering, fallback parsing
**Risk:** MEDIUM — Must handle malformed `structured_analysis` gracefully

### New File: `backend/app/services/data_flow_service.py`

```python
# backend/app/services/data_flow_service.py
"""
DataFlowService — derives request data flow graphs from existing structured_analysis JSON.

ZERO extra Gemini cost: all data comes from CodeComponent.structured_analysis (already stored).
The service is fully synchronous — safe to call from Celery tasks.

Three main methods:
  build_flow_for_component()  — extract + store edges for one component (idempotent)
  get_request_trace()         — BFS from a starting component (returns nodes + edges)
  render_mermaid()            — generate Mermaid flowchart syntax from nodes + edges
"""
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.code_data_flow_edge import (
    CodeDataFlowEdge, VALID_EDGE_TYPES, EDGE_LABEL_TEMPLATES, SWIMLANE_MAP
)
from app.crud.crud_code_data_flow_edge import crud_code_data_flow_edge

logger = get_logger("data_flow_service")

# Mapping from structured_analysis.language_info.file_type to normalized file_role
_FILE_TYPE_TO_ROLE = {
    "Controller": "ENDPOINT", "Route": "ENDPOINT", "Router": "ENDPOINT",
    "Handler": "ENDPOINT", "View": "ENDPOINT",
    "Service": "SERVICE",
    "Schema": "SCHEMA", "Serializer": "SCHEMA", "Validator": "SCHEMA",
    "Model": "MODEL", "Entity": "MODEL", "Migration": "MIGRATION",
    "Repository": "CRUD", "CRUD": "CRUD", "DAO": "CRUD",
    "Middleware": "MIDDLEWARE", "Interceptor": "MIDDLEWARE",
    "Utility": "UTILITY", "Helper": "UTILITY", "Lib": "UTILITY",
    "Config": "CONFIG", "Settings": "CONFIG", "Constants": "CONFIG",
    "Test": "TEST",
}


class DataFlowService:

    # ─────────────────────────────────────────────
    # Method 1: Build and store edges for one file
    # ─────────────────────────────────────────────
    def build_flow_for_component(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
    ) -> dict:
        """
        Deterministically parse structured_analysis for one CodeComponent and
        store the resulting edges. Idempotent: old edges deleted before insert.

        Returns: { "edges_created": int, "file_role": str }
        """
        from app.models.code_component import CodeComponent

        component = db.get(CodeComponent, component_id)
        if not component or not component.structured_analysis:
            logger.warning(f"Component {component_id} has no structured_analysis — skip")
            return {"edges_created": 0, "file_role": "UNKNOWN"}

        sa = component.structured_analysis
        file_role = self._resolve_file_role(sa)

        edges = []

        # ENDPOINT: HTTP trigger edges from api_contracts
        if file_role == "ENDPOINT":
            for contract in sa.get("api_contracts", []):
                method = contract.get("method", "")
                path = contract.get("path", "")
                if method and path:
                    edges.append({
                        "tenant_id": tenant_id,
                        "repository_id": component.repository_id,
                        "source_component_id": component_id,
                        "target_component_id": None,
                        "edge_type": "HTTP_TRIGGER",
                        "source_function": None,
                        "target_function": None,
                        "data_in_description": contract.get("request_schema", ""),
                        "data_out_description": contract.get("response_schema", ""),
                        "human_label": f"Receives {method} {path}",
                        "external_target_name": "HTTP Client",
                        "step_index": 0,
                    })

        # OUTBOUND CALLS (new P3.1 field — most accurate)
        for i, call in enumerate(sa.get("outbound_calls", []), start=1):
            target_id = self._resolve_component_id(
                db=db,
                target_module=call.get("target_module", ""),
                repository_id=component.repository_id,
                tenant_id=tenant_id,
            )
            edges.append({
                "tenant_id": tenant_id,
                "repository_id": component.repository_id,
                "source_component_id": component_id,
                "target_component_id": target_id,
                "edge_type": "SERVICE_CALL",
                "source_function": call.get("caller_function"),
                "target_function": call.get("target_function"),
                "data_in_description": call.get("data_in"),
                "data_out_description": call.get("data_out"),
                "human_label": self._build_human_label(
                    "SERVICE_CALL",
                    source=call.get("caller_function", ""),
                    target=call.get("target_function", ""),
                ),
                "external_target_name": call.get("target_module") if not target_id else None,
                "step_index": i,
            })

        # COMPONENT INTERACTIONS fallback (Sprint 3 field — less structured)
        if not sa.get("outbound_calls") and sa.get("component_interactions"):
            for i, interaction in enumerate(sa.get("component_interactions", []), start=1):
                target_id = self._resolve_component_id(
                    db=db,
                    target_module=interaction.get("target", ""),
                    repository_id=component.repository_id,
                    tenant_id=tenant_id,
                )
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": component.repository_id,
                    "source_component_id": component_id,
                    "target_component_id": target_id,
                    "edge_type": "SERVICE_CALL",
                    "source_function": interaction.get("source"),
                    "target_function": interaction.get("target"),
                    "data_in_description": interaction.get("data_passed"),
                    "data_out_description": None,
                    "human_label": interaction.get("description", ""),
                    "external_target_name": interaction.get("target") if not target_id else None,
                    "step_index": i,
                })

        # DATA FLOWS → DB edges (look for DB/database keywords in destination)
        for flow in sa.get("data_flows", []):
            dest = (flow.get("destination") or "").lower()
            if any(kw in dest for kw in ("db", "database", "table", "postgresql", "mysql")):
                edge_type = "DB_WRITE" if any(
                    kw in dest for kw in ("insert", "save", "write", "create", "update")
                ) else "DB_READ"
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": component.repository_id,
                    "source_component_id": component_id,
                    "target_component_id": None,
                    "edge_type": edge_type,
                    "source_function": None,
                    "target_function": None,
                    "data_in_description": flow.get("source"),
                    "data_out_description": flow.get("destination"),
                    "human_label": self._build_human_label(
                        edge_type, table=flow.get("destination", "database")
                    ),
                    "external_target_name": flow.get("destination"),
                    "step_index": None,
                })

            # EXTERNAL API edges
            elif any(kw in dest for kw in ("external", "api", "sendgrid", "stripe", "twilio", "s3", "sns", "sqs")):
                edges.append({
                    "tenant_id": tenant_id,
                    "repository_id": component.repository_id,
                    "source_component_id": component_id,
                    "target_component_id": None,
                    "edge_type": "EXTERNAL_API",
                    "source_function": None,
                    "target_function": None,
                    "data_in_description": flow.get("source"),
                    "data_out_description": flow.get("destination"),
                    "human_label": self._build_human_label(
                        "EXTERNAL_API", name=flow.get("destination", "External Service")
                    ),
                    "external_target_name": flow.get("destination"),
                    "step_index": None,
                })

        # SCHEMA: backed_by_model → SCHEMA_VALIDATION edge back to source
        if file_role == "SCHEMA" and sa.get("backed_by_model"):
            bm = sa["backed_by_model"]
            edges.append({
                "tenant_id": tenant_id,
                "repository_id": component.repository_id,
                "source_component_id": component_id,
                "target_component_id": None,
                "edge_type": "SCHEMA_VALIDATION",
                "human_label": self._build_human_label(
                    "SCHEMA_VALIDATION",
                    target=bm.get("model_class", "Model"),
                ),
                "external_target_name": bm.get("table_name"),
                "step_index": None,
            })

        # Delete old edges and insert new ones (idempotent rebuild)
        crud_code_data_flow_edge.delete_by_component(
            db=db, component_id=component_id, tenant_id=tenant_id
        )
        created = crud_code_data_flow_edge.bulk_create(db=db, edges=edges)

        logger.info(f"Built {created} edges for component {component_id} (role={file_role})")
        return {"edges_created": created, "file_role": file_role}

    # ─────────────────────────────────────────────
    # Method 2: BFS request trace from an endpoint
    # ─────────────────────────────────────────────
    def get_request_trace(
        self,
        db: Session,
        *,
        component_id: int,
        tenant_id: int,
        max_depth: int = 5,
    ) -> dict:
        """
        BFS traversal from a starting component through all SERVICE_CALL edges.
        Returns all nodes + edges for Mermaid rendering.

        Returns:
        {
          nodes: [{ component_id, name, location, file_role, model_columns?, schema_fields? }],
          edges: [CodeDataFlowEdge as dict],
          mermaid_technical: str,
          mermaid_simple: str,
        }
        """
        from app.models.code_component import CodeComponent
        from collections import deque

        visited_ids = set()
        all_edges = []
        queue = deque([(component_id, 0)])
        node_info = {}

        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited_ids or depth > max_depth:
                continue
            visited_ids.add(current_id)

            # Load node metadata
            comp = db.get(CodeComponent, current_id)
            if comp:
                sa = comp.structured_analysis or {}
                node_info[current_id] = {
                    "component_id": current_id,
                    "name": comp.name,
                    "location": comp.location,
                    "file_role": self._resolve_file_role(sa),
                    "model_columns": sa.get("model_definition", {}).get("columns"),
                    "schema_fields": sa.get("backed_by_model", {}).get("fields"),
                    "summary": comp.summary,
                }

            # Get outgoing edges from this node
            edges_out = crud_code_data_flow_edge.get_by_source(
                db=db, component_id=current_id, tenant_id=tenant_id
            )
            for edge in edges_out:
                all_edges.append(edge)
                if edge.target_component_id and edge.target_component_id not in visited_ids:
                    queue.append((edge.target_component_id, depth + 1))
                elif edge.target_component_id is None and edge.external_target_name:
                    # External node — add as virtual node with negative ID
                    ext_key = f"EXT_{edge.external_target_name}"
                    if ext_key not in node_info:
                        node_info[ext_key] = {
                            "component_id": None,
                            "name": edge.external_target_name,
                            "location": None,
                            "file_role": None,
                            "is_external": True,
                        }

        nodes = list(node_info.values())
        edges_as_dicts = [
            {
                "id": e.id,
                "source_component_id": e.source_component_id,
                "target_component_id": e.target_component_id,
                "edge_type": e.edge_type,
                "source_function": e.source_function,
                "target_function": e.target_function,
                "data_in_description": e.data_in_description,
                "data_out_description": e.data_out_description,
                "human_label": e.human_label,
                "external_target_name": e.external_target_name,
                "step_index": e.step_index,
            }
            for e in all_edges
        ]

        return {
            "nodes": nodes,
            "edges": edges_as_dicts,
            "mermaid_technical": self.render_mermaid(nodes, all_edges, mode="technical"),
            "mermaid_simple": self.render_mermaid(nodes, all_edges, mode="simple"),
        }

    # ─────────────────────────────────────────────
    # Method 3: Mermaid renderer (technical + business)
    # ─────────────────────────────────────────────
    def render_mermaid(self, nodes: list[dict], edges: list, mode: str = "technical") -> str:
        """
        Convert graph nodes+edges into Mermaid flowchart LR syntax.

        mode="technical" — shows function names, types, column lists
        mode="simple"    — shows human labels only, no code identifiers
        """
        lines = ["flowchart LR"]

        # Group nodes by swimlane
        swimlanes: dict[str, list] = {}
        for node in nodes:
            lane = SWIMLANE_MAP.get(node.get("file_role"), "External Services")
            swimlanes.setdefault(lane, []).append(node)

        # Swimlane order
        lane_order = [
            "API Layer", "Business Logic", "Validation",
            "Data Access", "Database", "External Services",
            "Utilities", "Configuration",
        ]

        node_id_map = {}  # component_id → mermaid node id (e.g. "n1")
        n = 0
        for lane in lane_order:
            if lane not in swimlanes:
                continue
            safe_lane = lane.replace(" ", "_")
            lines.append(f'  subgraph {safe_lane}["{lane}"]')
            for node in swimlanes[lane]:
                nid = f"n{n}"
                n += 1
                cid = node.get("component_id") or node.get("name", f"ext{n}")
                node_id_map[cid] = nid

                if mode == "technical":
                    label = self._make_technical_label(node)
                else:
                    label = self._make_simple_label(node)

                # Choose node shape by role
                role = node.get("file_role")
                if role == "ENDPOINT":
                    lines.append(f'    {nid}["{label}"]')
                elif role == "MODEL" or role is None:
                    lines.append(f'    {nid}[("{label}")]')  # cylinder shape
                elif node.get("is_external"):
                    lines.append(f'    {nid}{{"{label}"}}')  # diamond shape
                else:
                    lines.append(f'    {nid}["{label}"]')

                # Click directive (only for internal nodes with component_id)
                if node.get("component_id"):
                    lines.append(f'    click {nid} call dokydocClick("{node["component_id"]}")')

            lines.append("  end")

        # Edges
        for edge in edges:
            src_id = edge.source_component_id if hasattr(edge, "source_component_id") else edge.get("source_component_id")
            tgt_id = edge.target_component_id if hasattr(edge, "target_component_id") else edge.get("target_component_id")
            ext_name = edge.external_target_name if hasattr(edge, "external_target_name") else edge.get("external_target_name")

            src_node = node_id_map.get(src_id)
            tgt_node = node_id_map.get(tgt_id) if tgt_id else node_id_map.get(ext_name)

            if not src_node or not tgt_node:
                continue

            if mode == "technical":
                fn = edge.source_function if hasattr(edge, "source_function") else edge.get("source_function")
                label = f"{fn or edge.edge_type if hasattr(edge,'edge_type') else edge.get('edge_type','→')}"
            else:
                label = edge.human_label if hasattr(edge, "human_label") else edge.get("human_label", "→")

            label = (label or "→").replace('"', "'")
            lines.append(f'  {src_node} -->|"{label}"| {tgt_node}')

        return "\n".join(lines)

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────
    def _resolve_file_role(self, structured_analysis: dict) -> str:
        """Normalize file role from structured_analysis dict."""
        # P3.1 new field — most accurate
        if structured_analysis.get("file_role"):
            return structured_analysis["file_role"]
        # Fallback to language_info.file_type mapping
        lang = structured_analysis.get("language_info", {})
        file_type = lang.get("file_type", "")
        return _FILE_TYPE_TO_ROLE.get(file_type, "UTILITY")

    def _resolve_component_id(
        self,
        db: Session,
        *,
        target_module: str,
        repository_id: int | None,
        tenant_id: int,
    ) -> int | None:
        """
        Try to match target_module path to an existing CodeComponent.location.
        Returns component_id if found, None if external.
        """
        if not target_module or not repository_id:
            return None
        from app.models.code_component import CodeComponent
        # Normalize path: "services/auth_service" → match on location containing "auth_service"
        search_term = target_module.replace(".", "/").split("/")[-1]
        match = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repository_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.location.ilike(f"%{search_term}%"),
        ).first()
        return match.id if match else None

    def _build_human_label(self, edge_type: str, **kwargs) -> str:
        template = EDGE_LABEL_TEMPLATES.get(edge_type, "→")
        try:
            return template.format(**kwargs)
        except KeyError:
            return edge_type

    def _make_technical_label(self, node: dict) -> str:
        name = node.get("name", "Unknown")
        role = node.get("file_role", "")
        fn_list = ""
        if node.get("model_columns"):
            cols = node["model_columns"][:4]
            fn_list = "\\n" + " · ".join(c.get("name", "") for c in cols)
        location = node.get("location", "").split("/")[-1] if node.get("location") else ""
        return f"{name}\\n{location}{fn_list}".strip("\\n")

    def _make_simple_label(self, node: dict) -> str:
        name = node.get("name", "Unknown")
        role = node.get("file_role", "")
        role_emoji = {
            "ENDPOINT": "🌐", "SERVICE": "⚙️", "SCHEMA": "✅",
            "MODEL": "🗄️", "CRUD": "📋", "EXTERNAL_API": "🔌",
        }.get(role, "")
        return f"{role_emoji} {name}".strip()


data_flow_service = DataFlowService()
```


---

## P3.5 — Hook DataFlowService into Analysis Pipeline

**Priority:** P1 — Without this, new analyses never build edges
**Complexity:** LOW — 8-line addition to existing service
**Risk:** LOW — Fully wrapped in try/except; never breaks existing analysis

### Current State

**File:** `backend/app/services/code_analysis_service.py`

After the ontology extraction call (the last step in the file analysis pipeline, look for `build_graph_from_code_component` or the `# Step 6` comment), the pipeline completes without triggering edge building.

### What to Add

Find the successful completion section of `_run_enhanced_analysis_for_component()` (the method that runs after Gemini returns structured_analysis). Insert AFTER the ontology extraction step:

```python
# ─── Step 7: Build data flow edges (Phase 3 — premium only, zero AI cost) ───
try:
    from app.models.tenant import Tenant
    from app.crud import crud as crud_main
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if tenant and tenant.tier in ("professional", "enterprise"):
        from app.services.data_flow_service import data_flow_service
        result = data_flow_service.build_flow_for_component(
            db=db,
            component_id=component.id,
            tenant_id=tenant_id,
        )
        self.logger.info(
            f"Data flow edges built: {result['edges_created']} edges "
            f"(role={result['file_role']}) for component {component.id}"
        )
except Exception as e:
    self.logger.warning(
        f"Data flow edge build failed (non-fatal) for component {component.id}: {e}"
    )
# ─────────────────────────────────────────────────────────────────────────────
```

**Important:** The free-tier check (`tenant.tier in ("professional", "enterprise")`) means free-tier analyses never build edges. When a tenant upgrades, the backfill task (P3.6) populates all existing components.

### Risk Assessment
- `data_flow_service.build_flow_for_component()` is synchronous — no async issues
- try/except wraps the entire block — a bug in DataFlowService cannot break code analysis
- `tenant.tier` lookup is a single indexed query — negligible latency

---

## P3.6 — Backfill Celery Task

**Priority:** P2 — Required for tenant tier upgrades and post-prompt-update rebuilds
**Complexity:** LOW — Simple Celery task following existing patterns

### New File: `backend/app/tasks/data_flow_tasks.py`

```python
# backend/app/tasks/data_flow_tasks.py
"""
Data flow edge backfill and rebuild tasks.

backfill_data_flow_edges: Builds edges for all analyzed components in a repo.
  Called when: (a) tenant upgrades free→pro, (b) P3.1 prompt is deployed and
  existing analyses should be enriched.

rebuild_component_data_flow: Rebuild edges for a single component.
  Called when: user clicks "Rebuild diagram" in the UI (P3.8).
"""
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger("data_flow_tasks")


@celery_app.task(name="backfill_data_flow_edges", bind=True, max_retries=2)
def backfill_data_flow_edges(self, repository_id: int, tenant_id: int):
    """
    Build data flow edges for all completed components in a repository.
    Per-component errors do not stop the batch.
    Returns: { "success": int, "failed": int, "total": int }
    """
    from app.db.session import SessionLocal
    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service

    db = SessionLocal()
    results = {"success": 0, "failed": 0, "total": 0}
    try:
        components = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repository_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        ).all()

        results["total"] = len(components)
        logger.info(f"Backfilling {len(components)} components for repo {repository_id}")

        for component in components:
            try:
                data_flow_service.build_flow_for_component(
                    db=db,
                    component_id=component.id,
                    tenant_id=tenant_id,
                )
                results["success"] += 1
            except Exception as e:
                logger.warning(f"Backfill failed for component {component.id}: {e}")
                results["failed"] += 1

        logger.info(f"Backfill complete: {results}")
        return results
    except Exception as exc:
        logger.error(f"Backfill task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(name="rebuild_component_data_flow", bind=True, max_retries=1)
def rebuild_component_data_flow(self, component_id: int, tenant_id: int):
    """
    Rebuild data flow edges for a single component.
    Triggered by user clicking "Rebuild diagram" in the UI.
    """
    from app.db.session import SessionLocal
    from app.services.data_flow_service import data_flow_service

    db = SessionLocal()
    try:
        result = data_flow_service.build_flow_for_component(
            db=db, component_id=component_id, tenant_id=tenant_id
        )
        return result
    except Exception as exc:
        logger.error(f"Component {component_id} rebuild failed: {exc}")
        raise self.retry(exc=exc, countdown=15)
    finally:
        db.close()
```

**Register in `backend/app/worker.py`** (add to include list):
```python
include=[
    "app.tasks",
    "app.tasks.ontology_tasks",
    "app.tasks.code_analysis_tasks",
    "app.tasks.data_flow_tasks",    # ← ADD THIS
]
```

---

## P3.7 — New API Endpoints

**Priority:** P0 — Frontend cannot work without these
**Complexity:** MEDIUM — 4 new endpoints + 4 new Pydantic schemas

### Step 1: New Schemas

**Add to `backend/app/schemas/code_component.py`** (append at end):

```python
# ─── Phase 3: Data Flow Response Schemas ───

class DataFlowNodeSchema(BaseModel):
    component_id: Optional[int] = None
    name: str
    location: Optional[str] = None
    file_role: Optional[str] = None
    summary: Optional[str] = None
    model_columns: Optional[list] = None
    schema_fields: Optional[list] = None
    is_external: bool = False

    model_config = ConfigDict(from_attributes=True)


class DataFlowEdgeSchema(BaseModel):
    id: Optional[int] = None
    source_component_id: int
    target_component_id: Optional[int] = None
    edge_type: str
    source_function: Optional[str] = None
    target_function: Optional[str] = None
    data_in_description: Optional[str] = None
    data_out_description: Optional[str] = None
    human_label: Optional[str] = None
    external_target_name: Optional[str] = None
    step_index: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EgocentricFlowResponse(BaseModel):
    component_id: int
    file_role: str
    edges_in: list[DataFlowEdgeSchema]
    edges_out: list[DataFlowEdgeSchema]
    mermaid_technical: str
    mermaid_simple: str
    total_edges: int

    model_config = ConfigDict(from_attributes=True)


class RequestTraceResponse(BaseModel):
    start_component_id: int
    depth: int
    nodes: list[DataFlowNodeSchema]
    edges: list[DataFlowEdgeSchema]
    mermaid_technical: str
    mermaid_simple: str
    total_nodes: int
    total_edges: int

    model_config = ConfigDict(from_attributes=True)
```

**Add to `backend/app/schemas/__init__.py`:**
```python
from .code_component import (
    ...,  # existing
    DataFlowNodeSchema,
    DataFlowEdgeSchema,
    EgocentricFlowResponse,
    RequestTraceResponse,
)
```

### Step 2: New Endpoints

**Add to `backend/app/api/endpoints/code_components.py`** (append after existing `/{id}/retry` route):

```python
from app.schemas.code_component import EgocentricFlowResponse, RequestTraceResponse
from app.models.code_data_flow_edge import SWIMLANE_MAP


def _check_premium(tenant_id: int, db: Session) -> None:
    """Raise 403 if tenant is on free tier."""
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant or tenant.tier == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "premium_required",
                "message": "Data Flow Diagrams are available on Professional and Enterprise plans.",
                "upgrade_url": "/settings/billing",
            }
        )


# GET /code-components/{id}/data-flow
@router.get("/{id}/data-flow", response_model=EgocentricFlowResponse)
def get_component_data_flow(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Return egocentric data flow for a single file — all edges in + out.
    Premium gate: 403 for free tier tenants.

    Used by: "This File Only" view in the Data Flow tab.
    """
    _check_premium(current_user.tenant_id, db)

    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service
    from app.crud.crud_code_data_flow_edge import crud_code_data_flow_edge

    comp = db.get(CodeComponent, id)
    if not comp or comp.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Component not found")

    edges_in = crud_code_data_flow_edge.get_by_target(
        db=db, component_id=id, tenant_id=current_user.tenant_id
    )
    edges_out = crud_code_data_flow_edge.get_by_source(
        db=db, component_id=id, tenant_id=current_user.tenant_id
    )
    all_edges = edges_in + edges_out

    sa = comp.structured_analysis or {}
    file_role = data_flow_service._resolve_file_role(sa)

    # Build simple node list for this file only
    node_self = [{
        "component_id": id,
        "name": comp.name,
        "location": comp.location,
        "file_role": file_role,
        "summary": comp.summary,
    }]

    return EgocentricFlowResponse(
        component_id=id,
        file_role=file_role,
        edges_in=edges_in,
        edges_out=edges_out,
        mermaid_technical=data_flow_service.render_mermaid(node_self, all_edges, "technical"),
        mermaid_simple=data_flow_service.render_mermaid(node_self, all_edges, "simple"),
        total_edges=len(all_edges),
    )


# GET /code-components/{id}/request-trace
@router.get("/{id}/request-trace", response_model=RequestTraceResponse)
def get_request_trace(
    id: int,
    depth: int = Query(default=5, ge=1, le=8),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    BFS request trace from this component (max depth=8, default=5).
    Premium gate: 403 for free tier tenants.

    Used by: "Full Request Trace" view in the Data Flow tab.
    """
    _check_premium(current_user.tenant_id, db)

    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service

    comp = db.get(CodeComponent, id)
    if not comp or comp.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Component not found")

    trace = data_flow_service.get_request_trace(
        db=db,
        component_id=id,
        tenant_id=current_user.tenant_id,
        max_depth=depth,
    )

    return RequestTraceResponse(
        start_component_id=id,
        depth=depth,
        nodes=trace["nodes"],
        edges=trace["edges"],
        mermaid_technical=trace["mermaid_technical"],
        mermaid_simple=trace["mermaid_simple"],
        total_nodes=len(trace["nodes"]),
        total_edges=len(trace["edges"]),
    )


# POST /code-components/{id}/data-flow/rebuild
@router.post("/{id}/data-flow/rebuild", status_code=202)
def rebuild_data_flow(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Trigger async rebuild of data flow edges for a single component.
    Premium gate: 403 for free tier.
    Used by: "Rebuild diagram" button in the UI after re-analysis.
    """
    _check_premium(current_user.tenant_id, db)

    from app.models.code_component import CodeComponent
    from app.tasks.data_flow_tasks import rebuild_component_data_flow

    comp = db.get(CodeComponent, id)
    if not comp or comp.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Component not found")

    task = rebuild_component_data_flow.apply_async(
        args=[id, current_user.tenant_id]
    )
    return {"task_id": task.id, "component_id": id, "status": "rebuilding"}
```

**Add to `backend/app/api/endpoints/repositories.py`** (append at end):

```python
# POST /repositories/{id}/backfill-data-flow
@router.post("/{id}/backfill-data-flow", status_code=202)
def backfill_repository_data_flow(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user),
):
    """
    Trigger backfill of all data flow edges for a repository.
    Admin or repo owner only. Used after tier upgrade or prompt update.
    """
    from app.models.repository import Repository
    from app.models.code_component import CodeComponent
    from sqlalchemy import func
    from app.tasks.data_flow_tasks import backfill_data_flow_edges

    repo = db.get(Repository, id)
    if not repo or repo.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Count eligible components
    component_count = db.query(func.count(CodeComponent.id)).filter(
        CodeComponent.repository_id == id,
        CodeComponent.tenant_id == current_user.tenant_id,
        CodeComponent.analysis_status == "completed",
    ).scalar()

    task = backfill_data_flow_edges.apply_async(
        args=[id, current_user.tenant_id]
    )
    return {
        "task_id": task.id,
        "repository_id": id,
        "component_count": component_count,
        "status": "backfilling",
        "message": f"Building data flow edges for {component_count} components",
    }
```

### Test Commands

```bash
# 1. Run migration
alembic upgrade s13a1

# 2. Trigger backfill for a repo (pro tenant)
curl -X POST -H "Authorization: Bearer $PRO_TOKEN" \
  http://localhost:8000/api/v1/repositories/1/backfill-data-flow
# Expected: { "task_id": "...", "component_count": 15, "status": "backfilling" }

# 3. Check edges were created
psql -c "SELECT edge_type, COUNT(*) FROM code_data_flow_edges GROUP BY edge_type"

# 4. Get egocentric data flow for a service file
curl -H "Authorization: Bearer $PRO_TOKEN" \
  http://localhost:8000/api/v1/code-components/5/data-flow
# Expected: { "file_role": "SERVICE", "edges_in": [...], "edges_out": [...], "mermaid_technical": "..." }

# 5. Get request trace from an endpoint
curl -H "Authorization: Bearer $PRO_TOKEN" \
  "http://localhost:8000/api/v1/code-components/3/request-trace?depth=4"
# Expected: { "nodes": [...], "edges": [...], "mermaid_technical": "flowchart LR\n..." }

# 6. Verify premium gate blocks free tier
curl -H "Authorization: Bearer $FREE_TOKEN" \
  http://localhost:8000/api/v1/code-components/3/request-trace
# Expected: 403 { "error": "premium_required", "upgrade_url": "/settings/billing" }

# 7. Test rebuild single component
curl -X POST -H "Authorization: Bearer $PRO_TOKEN" \
  http://localhost:8000/api/v1/code-components/5/data-flow/rebuild
# Expected: 202 { "task_id": "...", "status": "rebuilding" }
```


---

## P3.8 — Frontend: "Data Flow" Tab — High-End UI/UX

**Priority:** P0 — This is the user-facing deliverable; everything else supports it
**Complexity:** HIGH — Interactive diagram, two view modes, edge list panels, premium gate
**Risk:** LOW — Additive to existing tab bar; existing tabs untouched

### UX Design Principles

1. **Role-aware defaults:** Developer lands on "Technical" mode by default. BA/PM lands on "Business" mode by default (detected from `current_user.roles`).
2. **Zero-loading on tab switch:** Data is fetched when the tab activates, not before. A skeleton loader appears immediately.
3. **Diagram is clickable navigation:** Every node in the diagram is a link. Clicking a service node navigates to that file's detail page — developer never has to leave the flow.
4. **Two views in one tab:** "Full Trace" (BFS from this file) and "This File Only" (egocentric). Toggle at the top. Default: Full Trace for ENDPOINTs, This File for everything else.
5. **Evidence panels below the diagram:** After the diagram, show structured edge lists ("Calls", "Called By") with full function names, data types, and step descriptions.
6. **Premium gate is not a wall:** Free tier sees a teaser diagram (static, blurred placeholder) with a clear upsell card. Never a blank screen.

---

### New Files

**New file: `frontend/hooks/useDataFlow.ts`**

```typescript
// frontend/hooks/useDataFlow.ts
import useSWR from "swr";
import { apiGet } from "@/lib/api";

export type FlowMode = "technical" | "simple";
export type FlowView = "trace" | "file";

export function useRequestTrace(componentId: number, depth = 5, enabled = true) {
  return useSWR(
    enabled && componentId
      ? `/code-components/${componentId}/request-trace?depth=${depth}`
      : null,
    apiGet,
    { revalidateOnFocus: false }
  );
}

export function useEgocentricFlow(componentId: number, enabled = true) {
  return useSWR(
    enabled && componentId ? `/code-components/${componentId}/data-flow` : null,
    apiGet,
    { revalidateOnFocus: false }
  );
}
```

---

**New file: `frontend/components/data-flow/PremiumGateCard.tsx`**

```tsx
// frontend/components/data-flow/PremiumGateCard.tsx
"use client";
import { Sparkles, Lock, ArrowRight } from "lucide-react";
import Link from "next/link";

const EXAMPLE_NODES = [
  { x: 80, y: 60, w: 120, label: "POST /register" },
  { x: 260, y: 30, w: 120, label: "AuthService" },
  { x: 260, y: 100, w: 120, label: "UserCreateSchema" },
  { x: 440, y: 60, w: 120, label: "UserCRUD" },
  { x: 620, y: 40, w: 100, label: "users table" },
  { x: 620, y: 90, w: 100, label: "SendGrid API" },
];

export function PremiumGateCard() {
  return (
    <div className="relative overflow-hidden rounded-xl border border-gray-200 bg-white">
      {/* Blurred SVG teaser diagram */}
      <div className="blur-sm select-none pointer-events-none p-6 opacity-60 h-52">
        <svg width="100%" height="100%" viewBox="0 0 760 160" className="w-full">
          {/* Draw fake nodes */}
          {EXAMPLE_NODES.map((n, i) => (
            <g key={i}>
              <rect x={n.x} y={n.y} width={n.w} height={36} rx={6}
                fill={i === 0 ? "#e0e7ff" : i === 4 || i === 5 ? "#fef9c3" : "#f0fdf4"}
                stroke="#c7d2fe" strokeWidth={1.5} />
              <text x={n.x + n.w / 2} y={n.y + 22} textAnchor="middle"
                fontSize={11} fill="#374151" fontFamily="monospace">
                {n.label}
              </text>
            </g>
          ))}
          {/* Arrows between nodes */}
          {[
            [200, 78, 260, 48], [200, 78, 260, 118], [380, 48, 440, 78],
            [380, 118, 440, 78], [560, 78, 620, 58], [560, 78, 620, 108],
          ].map(([x1, y1, x2, y2], i) => (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="#6366f1" strokeWidth={1.5} markerEnd="url(#arr)" />
          ))}
          <defs>
            <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="#6366f1" />
            </marker>
          </defs>
        </svg>
      </div>

      {/* Overlay upsell card */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4
                      bg-white/70 backdrop-blur-[2px]">
        <div className="flex items-center gap-2 rounded-full bg-indigo-100 px-4 py-2">
          <Sparkles className="h-4 w-4 text-indigo-600" />
          <span className="text-sm font-semibold text-indigo-700">Professional Feature</span>
        </div>
        <div className="text-center space-y-1">
          <h3 className="text-lg font-bold text-gray-900">Request Data Flow Diagrams</h3>
          <p className="text-sm text-gray-500 max-w-sm">
            See exactly how data flows through your entire codebase — from HTTP call to database.
            Click any node to navigate to that file.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link href="/dashboard/settings?tab=billing"
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5
                       text-sm font-semibold text-white hover:bg-indigo-700 transition-colors">
            Upgrade to Pro
            <ArrowRight className="h-4 w-4" />
          </Link>
          <button className="inline-flex items-center gap-2 rounded-lg border px-5 py-2.5
                             text-sm text-gray-600 hover:bg-gray-50 transition-colors">
            <Lock className="h-4 w-4" />
            See what's included
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

**New file: `frontend/components/data-flow/EdgeListPanel.tsx`**

```tsx
// frontend/components/data-flow/EdgeListPanel.tsx
"use client";
import { ArrowUpRight, ArrowDownLeft, Database, Globe, Server, CheckSquare, Zap } from "lucide-react";
import Link from "next/link";

const EDGE_TYPE_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  HTTP_TRIGGER:      { icon: Globe,       color: "text-blue-600 bg-blue-50",   label: "HTTP" },
  SERVICE_CALL:      { icon: Server,      color: "text-purple-600 bg-purple-50", label: "Call" },
  SCHEMA_VALIDATION: { icon: CheckSquare, color: "text-green-600 bg-green-50",  label: "Schema" },
  DB_READ:           { icon: Database,    color: "text-amber-600 bg-amber-50",  label: "DB Read" },
  DB_WRITE:          { icon: Database,    color: "text-red-600 bg-red-50",      label: "DB Write" },
  EXTERNAL_API:      { icon: Globe,       color: "text-teal-600 bg-teal-50",    label: "External" },
  CACHE_READ:        { icon: Zap,         color: "text-yellow-600 bg-yellow-50", label: "Cache Read" },
  CACHE_WRITE:       { icon: Zap,         color: "text-orange-600 bg-orange-50", label: "Cache Write" },
  EVENT_PUBLISH:     { icon: Zap,         color: "text-pink-600 bg-pink-50",    label: "Publish" },
  EVENT_CONSUME:     { icon: Zap,         color: "text-violet-600 bg-violet-50", label: "Consume" },
};

interface Edge {
  id?: number;
  edge_type: string;
  source_function?: string;
  target_function?: string;
  data_in_description?: string;
  data_out_description?: string;
  human_label?: string;
  external_target_name?: string;
  target_component_id?: number;
  source_component_id?: number;
  step_index?: number;
}

interface Node {
  component_id?: number;
  name: string;
  file_role?: string;
}

interface Props {
  edgesOut: Edge[];
  edgesIn: Edge[];
  nodes: Node[];
}

export function EdgeListPanel({ edgesOut, edgesIn, nodes }: Props) {
  const nodeMap = new Map(nodes.map((n) => [n.component_id, n]));

  const renderEdge = (edge: Edge, direction: "out" | "in") => {
    const cfg = EDGE_TYPE_CONFIG[edge.edge_type] || { icon: Server, color: "text-gray-500 bg-gray-50", label: edge.edge_type };
    const Icon = cfg.icon;
    const connectedId = direction === "out" ? edge.target_component_id : edge.source_component_id;
    const connectedNode = nodeMap.get(connectedId ?? -1);
    const connectedName = connectedNode?.name ?? edge.external_target_name ?? "External";

    return (
      <div key={edge.id ?? Math.random()} className="flex items-start gap-3 py-2.5 border-b last:border-0">
        {/* Direction + type badge */}
        <div className="flex flex-col items-center gap-1 flex-shrink-0 w-14">
          {direction === "out"
            ? <ArrowUpRight className="h-3.5 w-3.5 text-purple-500" />
            : <ArrowDownLeft className="h-3.5 w-3.5 text-blue-500" />}
          <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${cfg.color}`}>
            {cfg.label}
          </span>
        </div>

        {/* Edge details */}
        <div className="flex-1 min-w-0 space-y-0.5">
          <div className="flex items-center gap-2">
            {edge.source_function && direction === "out" && (
              <code className="text-xs text-gray-700 font-mono truncate">
                {edge.source_function}
              </code>
            )}
            <span className="text-xs text-gray-400">→</span>
            {connectedId ? (
              <Link href={`/dashboard/code/${connectedId}`}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium truncate hover:underline">
                {connectedName}
              </Link>
            ) : (
              <span className="text-xs text-teal-600 font-medium">{connectedName}</span>
            )}
            {edge.target_function && (
              <code className="text-xs text-gray-500 font-mono truncate">
                .{edge.target_function}
              </code>
            )}
          </div>

          {edge.human_label && (
            <p className="text-xs text-gray-500">{edge.human_label}</p>
          )}

          {(edge.data_in_description || edge.data_out_description) && (
            <div className="flex gap-2 text-[10px] text-gray-400 font-mono">
              {edge.data_in_description && <span>in: {edge.data_in_description}</span>}
              {edge.data_out_description && <span>out: {edge.data_out_description}</span>}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
      {/* Outgoing calls */}
      <div className="rounded-lg border bg-white overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-purple-50">
          <ArrowUpRight className="h-4 w-4 text-purple-600" />
          <span className="text-sm font-semibold text-purple-700">
            Calls ({edgesOut.length})
          </span>
        </div>
        <div className="px-3 divide-y divide-gray-100 max-h-64 overflow-y-auto">
          {edgesOut.length === 0
            ? <p className="text-xs text-gray-400 py-4 text-center">No outgoing calls</p>
            : edgesOut.map((e) => renderEdge(e, "out"))}
        </div>
      </div>

      {/* Incoming calls */}
      <div className="rounded-lg border bg-white overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-blue-50">
          <ArrowDownLeft className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-blue-700">
            Called By ({edgesIn.length})
          </span>
        </div>
        <div className="px-3 divide-y divide-gray-100 max-h-64 overflow-y-auto">
          {edgesIn.length === 0
            ? <p className="text-xs text-gray-400 py-4 text-center">Not called by any tracked file</p>
            : edgesIn.map((e) => renderEdge(e, "in"))}
        </div>
      </div>
    </div>
  );
}
```

---

**New file: `frontend/components/data-flow/DataFlowDiagram.tsx`**

```tsx
// frontend/components/data-flow/DataFlowDiagram.tsx
"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  GitBranch, Layers, Code2, RefreshCw, ZoomIn, ZoomOut,
  ChevronDown, Loader2, AlertCircle, Info
} from "lucide-react";
import { MermaidDiagram } from "@/components/ontology/MermaidDiagram";
import { EdgeListPanel } from "./EdgeListPanel";
import { PremiumGateCard } from "./PremiumGateCard";
import { useRequestTrace, useEgocentricFlow, type FlowMode, type FlowView } from "@/hooks/useDataFlow";
import { apiPost } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  componentId: number;
  fileRole?: string;           // passed from parent page (from structured_analysis)
  userRoles?: string[];        // to default mode by role
}

const ROLE_DESCRIPTIONS: Record<string, string> = {
  ENDPOINT: "HTTP handler — shows the full request journey from this API endpoint",
  SERVICE:  "Business logic — shows what this service calls and what calls it",
  SCHEMA:   "Data schema — shows what validates against this schema",
  MODEL:    "Database model — shows what reads/writes this table",
  CRUD:     "Data layer — shows what services use this CRUD layer",
  UTILITY:  "Utility — shows what this helper is used by",
};

export function DataFlowDiagram({ componentId, fileRole, userRoles = [] }: Props) {
  const router = useRouter();

  // Default view: ENDPOINT → trace, everything else → file
  const [flowView, setFlowView] = useState<FlowView>(
    fileRole === "ENDPOINT" ? "trace" : "file"
  );
  // Default mode: BA/PM → simple, everyone else → technical
  const [flowMode, setFlowMode] = useState<FlowMode>(
    userRoles.some((r) => ["business_analyst", "product_manager", "cxo"].includes(r))
      ? "simple" : "technical"
  );
  const [traceDepth, setTraceDepth] = useState(5);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [isPremiumGated, setIsPremiumGated] = useState(false);

  // Fetch based on view
  const traceResult = useRequestTrace(componentId, traceDepth, flowView === "trace");
  const egoResult = useEgocentricFlow(componentId, flowView === "file");

  const isLoading = flowView === "trace" ? traceResult.isLoading : egoResult.isLoading;
  const error = flowView === "trace" ? traceResult.error : egoResult.error;
  const data = flowView === "trace" ? traceResult.data : egoResult.data;

  // Detect premium gate from 403 response
  useEffect(() => {
    if (error?.status === 403) setIsPremiumGated(true);
  }, [error]);

  const mermaid = data
    ? (flowMode === "technical" ? data.mermaid_technical : data.mermaid_simple)
    : "";

  const handleRebuild = async () => {
    setIsRebuilding(true);
    try {
      await apiPost(`/code-components/${componentId}/data-flow/rebuild`, {});
      toast.success("Diagram rebuilding — refresh in a few seconds");
      setTimeout(() => {
        traceResult.mutate?.();
        egoResult.mutate?.();
      }, 3000);
    } catch {
      toast.error("Rebuild failed");
    } finally {
      setIsRebuilding(false);
    }
  };

  const handleNodeClick = (nodeId: string) => {
    const numId = parseInt(nodeId, 10);
    if (!isNaN(numId)) {
      router.push(`/dashboard/code/${numId}`);
    }
  };

  if (isPremiumGated) return <PremiumGateCard />;

  return (
    <div className="space-y-4">
      {/* ── Controls row ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap">

        {/* View toggle (This File / Full Trace) */}
        <div className="inline-flex rounded-lg border bg-gray-50 p-0.5">
          {([
            { value: "file",  label: "This File",    icon: Code2 },
            { value: "trace", label: "Full Trace",   icon: Layers },
          ] as const).map(({ value, label, icon: Icon }) => (
            <button key={value} onClick={() => setFlowView(value)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-all ${
                flowView === value
                  ? "bg-white shadow-sm font-semibold text-indigo-700 border border-gray-200"
                  : "text-gray-500 hover:text-gray-700"
              }`}>
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Mode toggle (Technical / Business) */}
        <div className="inline-flex rounded-lg border bg-gray-50 p-0.5">
          {([
            { value: "technical", label: "Technical" },
            { value: "simple",    label: "Business" },
          ] as const).map(({ value, label }) => (
            <button key={value} onClick={() => setFlowMode(value)}
              className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                flowMode === value
                  ? "bg-white shadow-sm font-semibold text-gray-800 border border-gray-200"
                  : "text-gray-500 hover:text-gray-700"
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* Trace depth (only in trace mode) */}
        {flowView === "trace" && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Depth:</span>
            <div className="inline-flex rounded-md border overflow-hidden">
              {[3, 5, 8].map((d) => (
                <button key={d} onClick={() => setTraceDepth(d)}
                  className={`px-2.5 py-1 text-xs transition-colors ${
                    traceDepth === d
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-gray-600 hover:bg-gray-50"
                  }`}>
                  {d}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Rebuild button */}
        <button onClick={handleRebuild} disabled={isRebuilding}
          className="ml-auto flex items-center gap-1.5 text-xs text-gray-400
                     hover:text-gray-600 disabled:opacity-50 transition-colors">
          <RefreshCw className={`h-3.5 w-3.5 ${isRebuilding ? "animate-spin" : ""}`} />
          {isRebuilding ? "Rebuilding..." : "Rebuild"}
        </button>
      </div>

      {/* ── File role description (contextual hint) ── */}
      {fileRole && ROLE_DESCRIPTIONS[fileRole] && (
        <div className="flex items-center gap-2 rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2">
          <Info className="h-3.5 w-3.5 text-indigo-500 flex-shrink-0" />
          <p className="text-xs text-indigo-700">{ROLE_DESCRIPTIONS[fileRole]}</p>
        </div>
      )}

      {/* ── Diagram area ── */}
      {isLoading ? (
        <div className="h-72 flex items-center justify-center rounded-xl border bg-gray-50">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
            <p className="text-sm text-gray-500">Building data flow diagram...</p>
          </div>
        </div>
      ) : error && error?.status !== 403 ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700">Could not load data flow</p>
            <p className="text-xs text-red-500 mt-0.5">
              {error?.message || "The diagram may not be built yet. Try rebuilding."}
            </p>
          </div>
        </div>
      ) : data && mermaid ? (
        <div className="rounded-xl border bg-white overflow-hidden shadow-sm">
          {/* Stats bar */}
          <div className="flex items-center gap-4 px-4 py-2 border-b bg-gray-50 text-xs text-gray-500">
            <span><b className="text-gray-700">{data.total_nodes ?? 1}</b> components</span>
            <span><b className="text-gray-700">{data.total_edges ?? 0}</b> connections</span>
            {flowView === "trace" && (
              <span><b className="text-gray-700">{data.depth}</b> levels deep</span>
            )}
            <span className="ml-auto text-gray-400 italic">Click any node to navigate →</span>
          </div>
          <div className="p-2">
            <MermaidDiagram
              syntax={mermaid}
              height="480px"
              onNodeClick={handleNodeClick}
            />
          </div>
        </div>
      ) : (
        <div className="h-48 flex items-center justify-center rounded-xl border border-dashed bg-gray-50">
          <div className="text-center space-y-2">
            <GitBranch className="h-8 w-8 text-gray-300 mx-auto" />
            <p className="text-sm text-gray-400">No flow data yet</p>
            <button onClick={handleRebuild}
              className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline">
              Click to build diagram
            </button>
          </div>
        </div>
      )}

      {/* ── Edge list panels (evidence section) ── */}
      {data && (
        <EdgeListPanel
          edgesOut={data.edges_out ?? data.edges?.filter((e: any) => e.source_component_id === componentId) ?? []}
          edgesIn={data.edges_in ?? data.edges?.filter((e: any) => e.target_component_id === componentId) ?? []}
          nodes={data.nodes ?? []}
        />
      )}
    </div>
  );
}
```

---

### Wire Into `frontend/app/dashboard/code/[id]/page.tsx`

**Step 1 — Import:**

```tsx
// Add at top of file with other imports:
import { DataFlowDiagram } from "@/components/data-flow/DataFlowDiagram";
import { GitBranch } from "lucide-react";
```

**Step 2 — Add tab trigger** (inside `<TabsList>`, after the last existing `<TabsTrigger>`):

```tsx
<TabsTrigger
  value="dataflow"
  className="data-[state=active]:bg-indigo-50 data-[state=active]:text-indigo-700 h-10 px-6"
>
  <GitBranch className="h-4 w-4 mr-1.5" />
  Data Flow
</TabsTrigger>
```

**Step 3 — Add tab content** (after the last `</TabsContent>`, before closing `</Tabs>`):

```tsx
<TabsContent value="dataflow" className="space-y-4">
  <div className="rounded-xl border bg-white p-5">
    <div className="mb-4">
      <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-indigo-600" />
        Request Data Flow
      </h2>
      <p className="text-sm text-gray-500 mt-1">
        Visualise how requests and data flow through this file and its connected components.
      </p>
    </div>
    <DataFlowDiagram
      componentId={Number(id)}
      fileRole={component?.structured_analysis?.file_role}
      userRoles={currentUser?.roles}
    />
  </div>
</TabsContent>
```

**Step 4 — Pass `onValueChange` to trigger lazy fetch:** The existing `onValueChange` handler on the `<Tabs>` component already handles tab activation. No additional change needed — `DataFlowDiagram` uses SWR with `enabled` flags tied to the view toggle, so data is fetched lazily.


---

## P3.9 — Admin Backfill, Verification & Phase 3 Completion Checklist

**Owner:** Backend Lead  
**Estimate:** 1 day  
**Depends on:** P3.1–P3.8 merged  

---

### P3.9.1 — Admin Backfill Endpoint (already in P3.7, hardened here)

The endpoint was registered in `backend/app/api/endpoints/repositories.py` under P3.7. This section hardens it with proper response schema, permission check, and component count.

**File:** `backend/app/api/endpoints/repositories.py`

Ensure the endpoint reads as follows (replace the stub from P3.7):

```python
from app.tasks.data_flow_tasks import backfill_data_flow_edges

@router.post(
    "/{repository_id}/backfill-data-flow",
    status_code=202,
    summary="Trigger data-flow edge backfill for all components in a repository",
    tags=["Repositories"],
)
def trigger_data_flow_backfill(
    repository_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    Dispatches a background Celery task that builds CodeDataFlowEdge rows
    for every already-analysed component in the repository.

    Auth: must be repository owner OR a tenant admin.
    Response: 202 Accepted with task_id and component_count.
    """
    # Ownership / admin guard
    repo = crud.repository.get(db, id=repository_id)
    if not repo or repo.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != current_user.id and current_user.role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Must be repo owner or tenant admin")

    # Count components that have completed analysis (so we give an accurate ETA)
    component_count = (
        db.query(CodeComponent)
        .filter(
            CodeComponent.repository_id == repository_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "complete",
        )
        .count()
    )

    if component_count == 0:
        raise HTTPException(
            status_code=422,
            detail="No analysed components found. Run code analysis first.",
        )

    # Dispatch Celery task
    task = backfill_data_flow_edges.delay(
        repository_id=repository_id,
        tenant_id=tenant_id,
    )

    return {
        "task_id": task.id,
        "component_count": component_count,
        "message": (
            f"Backfill started for {component_count} components. "
            "Check task status at GET /api/v1/tasks/{task_id}/status"
        ),
    }
```

**Required imports** (add if not already present):

```python
from app.models.code_component import CodeComponent
from app.tasks.data_flow_tasks import backfill_data_flow_edges
```

---

### P3.9.2 — Register `data_flow_tasks` in Celery Worker

**File:** `backend/app/worker.py`

Find the `include=` list passed to `celery_app` and add the new task module:

```python
celery_app = Celery(
    "dokydoc",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks",
        "app.tasks.ontology_tasks",
        "app.tasks.code_analysis_tasks",
        "app.tasks.data_flow_tasks",   # ← ADD THIS LINE
    ],
)
```

---

### P3.9.3 — Hook Data Flow Build into Code Analysis Pipeline

**File:** `backend/app/services/code_analysis_service.py`

After the step that calls ontology extraction (search for the call to `_extract_ontology_from_analysis` or `build_graph_from_code_component`), add the non-breaking data flow step:

```python
# ── Step 7: Build data-flow edges (pro/enterprise only, zero extra AI cost) ──
try:
    tenant = crud.tenant.get(db=db, id=tenant_id)
    _is_premium = getattr(tenant, "tier", "free") in ("pro", "enterprise")
    if _is_premium:
        from app.services.data_flow_service import DataFlowService
        DataFlowService().build_flow_for_component(
            db=db,
            component_id=component.id,
            tenant_id=tenant_id,
        )
        self.logger.info(
            f"Data-flow edges built for component {component.id}"
        )
except Exception as _dfe:
    # NEVER let data-flow extraction break existing analysis pipeline
    self.logger.warning(
        f"Data-flow extraction failed for component {component.id} "
        f"(non-fatal): {_dfe}"
    )
```

> **Important:** This block must be inside the per-component analysis completion section, wrapped in its own `try/except`. The rest of the pipeline must continue even if this raises.

---

### P3.9.4 — Verification Commands

Run these commands **in order** after deploying Phase 3. Each command must pass before moving to the next.

#### Step 1 — Migration Applied
```bash
cd backend
alembic current
# Expected: s13a1 (head)

alembic check
# Expected: "No new upgrade operations detected."
```

#### Step 2 — Table Created
```sql
-- Connect to DB and run:
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'code_data_flow_edges'
ORDER BY ordinal_position;

-- Expected columns (13 total):
-- id, tenant_id, repository_id, source_component_id, target_component_id,
-- source_function, target_function, edge_type, data_in_description,
-- data_out_description, human_label, external_target_name,
-- step_index, created_at
```

#### Step 3 — CHECK Constraint on edge_type
```sql
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name LIKE '%edge_type%';
-- Expected: one row with all valid edge type values
```

#### Step 4 — Indexes Created
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'code_data_flow_edges';
-- Expected: ix_cdf_source, ix_cdf_target, ix_cdf_tenant, ix_cdf_repo, ix_cdf_source_type
```

#### Step 5 — Model Importable
```bash
cd backend
python -c "from app.models.code_data_flow_edge import CodeDataFlowEdge; print('OK')"
python -c "from app.crud.crud_code_data_flow_edge import CRUDCodeDataFlowEdge; print('OK')"
python -c "from app.services.data_flow_service import DataFlowService; print('OK')"
python -c "from app.tasks.data_flow_tasks import backfill_data_flow_edges; print('OK')"
```

#### Step 6 — API Endpoints Registered
```bash
# Start backend locally (dev mode)
uvicorn app.main:app --reload &

# Check endpoints exist:
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
spec = json.load(sys.stdin)
paths = list(spec['paths'].keys())
required = [
    '/api/v1/code-components/{id}/data-flow',
    '/api/v1/code-components/{id}/request-trace',
    '/api/v1/code-components/{id}/data-flow/rebuild',
    '/api/v1/repositories/{repository_id}/backfill-data-flow',
]
for p in required:
    if p in paths:
        print(f'✓ {p}')
    else:
        print(f'✗ MISSING: {p}')
"
```

#### Step 7 — End-to-End Flow Build
```bash
# Pick a component that has completed analysis
# Replace {TOKEN} and {COMPONENT_ID} with real values

# 1. Trigger rebuild for single component
curl -X POST http://localhost:8000/api/v1/code-components/{COMPONENT_ID}/data-flow/rebuild \
  -H "Authorization: Bearer {TOKEN}" \
  | python3 -m json.tool
# Expected: {"task_id": "...", "message": "Rebuild started"}

# Wait 5s for Celery to process, then:

# 2. Fetch egocentric flow
curl http://localhost:8000/api/v1/code-components/{COMPONENT_ID}/data-flow \
  -H "Authorization: Bearer {TOKEN}" \
  | python3 -m json.tool
# Expected: {"file_role": "...", "edges_out": [...], "edges_in": [...],
#            "mermaid_technical": "flowchart LR...", "mermaid_simple": "flowchart LR..."}

# 3. Fetch request trace
curl "http://localhost:8000/api/v1/code-components/{COMPONENT_ID}/request-trace?depth=3" \
  -H "Authorization: Bearer {TOKEN}" \
  | python3 -m json.tool
# Expected: {"nodes": [...], "edges": [...], "mermaid_technical": "...", "mermaid_simple": "..."}
```

#### Step 8 — Mermaid Syntax Valid
```bash
# Grab mermaid_technical from request trace above, then validate:
# Paste into https://mermaid.live — should render without errors
# OR use mermaid CLI:
npm install -g @mermaid-js/mermaid-cli
echo "$(curl -s .../request-trace | jq -r '.mermaid_technical')" | mmdc -i /dev/stdin -o /tmp/diagram.svg
# Expected: /tmp/diagram.svg created, non-zero file size
```

#### Step 9 — Premium Gate Works
```bash
# With a FREE tier tenant token:
curl http://localhost:8000/api/v1/code-components/{COMPONENT_ID}/data-flow \
  -H "Authorization: Bearer {FREE_TIER_TOKEN}" \
  | python3 -m json.tool
# Expected: HTTP 403
# {
#   "detail": {
#     "error": "premium_required",
#     "feature": "data_flow_diagrams",
#     "upgrade_url": "/dashboard/settings?tab=billing"
#   }
# }
```

#### Step 10 — Backfill Task Runs
```bash
# Trigger repo-level backfill
curl -X POST http://localhost:8000/api/v1/repositories/{REPO_ID}/backfill-data-flow \
  -H "Authorization: Bearer {TOKEN}" \
  | python3 -m json.tool
# Expected: {"task_id": "...", "component_count": N, "message": "Backfill started for N components..."}

# After completion check DB:
psql $DATABASE_URL -c "
SELECT edge_type, COUNT(*) as count
FROM code_data_flow_edges
WHERE repository_id = {REPO_ID}
GROUP BY edge_type
ORDER BY count DESC;
"
# Expected: rows for various edge_types (HTTP_TRIGGER, SERVICE_CALL, DB_READ, etc.)
```

#### Step 11 — Frontend Tab Renders
```
1. Open Chrome DevTools → Network tab
2. Navigate to /dashboard/code/{COMPONENT_ID}
3. Click the "Data Flow" tab
4. Verify Network shows:
   - GET /api/v1/code-components/{id}/request-trace → 200
   - Response contains mermaid_technical and mermaid_simple strings
5. Verify Mermaid diagram renders (no "Diagram render error" shown)
6. Click a node in the diagram → verify browser navigates to /dashboard/code/{other_id}
7. Toggle "Business View" → verify diagram re-renders with simpler labels
8. Toggle "This File Only" → verify GET /data-flow endpoint called instead
```

#### Step 12 — Premium Gate in UI (Free Tier)
```
1. Log in as a free-tier tenant user
2. Navigate to any code component
3. Click "Data Flow" tab
4. Verify: blurred SVG preview is shown (not the real diagram)
5. Verify: "Upgrade to Pro" button visible and links to /dashboard/settings?tab=billing
6. Verify: no API call is made to /data-flow or /request-trace (check Network tab)
```

---

### P3.9.5 — Phase 3 New Files Summary

| File | Type | Description |
|------|------|-------------|
| `backend/app/models/code_data_flow_edge.py` | NEW | `CodeDataFlowEdge` SQLAlchemy model |
| `backend/alembic/versions/s13a1_code_data_flow_edges.py` | NEW | DB migration: `code_data_flow_edges` table |
| `backend/app/crud/crud_code_data_flow_edge.py` | NEW | CRUD: get_by_source, get_by_target, get_egocentric, bulk_create, etc. |
| `backend/app/services/data_flow_service.py` | NEW | DataFlowService: build_flow, get_request_trace, render_mermaid |
| `backend/app/tasks/data_flow_tasks.py` | NEW | Celery tasks: backfill_data_flow_edges, rebuild_component_data_flow |
| `backend/app/schemas/code_component.py` | MODIFIED | +DataFlowNodeSchema, DataFlowEdgeSchema, EgocentricFlowResponse, RequestTraceResponse |
| `backend/app/api/endpoints/code_components.py` | MODIFIED | +3 endpoints: /data-flow, /request-trace, /data-flow/rebuild |
| `backend/app/api/endpoints/repositories.py` | MODIFIED | +1 endpoint: /backfill-data-flow |
| `backend/app/models/__init__.py` | MODIFIED | +`from .code_data_flow_edge import CodeDataFlowEdge` |
| `backend/app/crud/__init__.py` | MODIFIED | +`from .crud_code_data_flow_edge import code_data_flow_edge` |
| `backend/app/worker.py` | MODIFIED | +`app.tasks.data_flow_tasks` in include list |
| `backend/app/services/code_analysis_service.py` | MODIFIED | +Step 7: data-flow edge build hook (try/except guarded) |
| `frontend/hooks/useDataFlow.ts` | NEW | SWR hooks: useRequestTrace, useEgocentricFlow |
| `frontend/components/data-flow/PremiumGateCard.tsx` | NEW | Blurred SVG teaser + upsell overlay |
| `frontend/components/data-flow/EdgeListPanel.tsx` | NEW | "Calls" and "Called By" evidence panels |
| `frontend/components/data-flow/DataFlowDiagram.tsx` | NEW | Main Data Flow tab component (orchestrates all above) |
| `frontend/app/dashboard/code/[id]/page.tsx` | MODIFIED | +Data Flow tab trigger and content |

---

### P3.9.6 — Migration Chain Checkpoint

After Phase 3 is merged, the Alembic migration chain must be:

```
s12a1_training_examples          ← Phase 1 (data flywheel)
    ↓ down_revision
s13a1_code_data_flow_edges       ← Phase 3 (THIS phase)
    ↓ down_revision
s14a1_atom_upload_flag           ← Phase 4 (4-engine integration)
    ↓ down_revision
s14b1_concept_mapping_validation_fields
    ↓ down_revision
s14c1_analysis_run_efficiency_fields
    ↓ down_revision
s15a1_tenant_industry_settings   ← Phase 5 (dynamic prompting)
    ↓ down_revision
s16a1_... (Phase 5B mismatches)
...
```

**Verify before merging:**
```bash
alembic history --verbose | head -20
# s13a1 must appear immediately after s12a1
# s14a1 must list down_revision = 's13a1'
```

---

### P3.9.7 — Developer Checklist (Phase 3)

> Copy this checklist into your project tracking tool (Jira/Linear/GitHub Projects) and assign tasks before sprint begins.

#### DB / Backend (assign to: Backend Dev 1)
- [ ] **P3.2-DB** — Create `backend/app/models/code_data_flow_edge.py` with all fields, CHECK constraint, EDGE_LABEL_TEMPLATES, SWIMLANE_MAP
- [ ] **P3.2-MIG** — Write `backend/alembic/versions/s13a1_code_data_flow_edges.py` with all indexes, set `down_revision='s12a1'`
- [ ] **P3.2-REG** — Add `from .code_data_flow_edge import CodeDataFlowEdge` to `backend/app/models/__init__.py`
- [ ] **P3.2-VER** — Run `alembic upgrade s13a1` locally, run all verification commands in P3.9.4 Steps 1–4
- [ ] **P3.3-CRUD** — Write `backend/app/crud/crud_code_data_flow_edge.py` with 8 methods
- [ ] **P3.3-REG** — Add `from .crud_code_data_flow_edge import code_data_flow_edge` to `backend/app/crud/__init__.py`

#### Service Layer (assign to: Backend Dev 2)
- [ ] **P3.4-SVC** — Write `backend/app/services/data_flow_service.py` (DataFlowService with 3 public methods + all private helpers)
- [ ] **P3.1-PROMPT** — Edit `backend/app/services/ai/prompt_manager.py`: add `file_role`, `backed_by_model`, `model_definition`, `outbound_calls` fields to ENHANCED_SEMANTIC_ANALYSIS prompt (additive only — never remove existing fields)
- [ ] **P3.5-HOOK** — Edit `backend/app/services/code_analysis_service.py`: add Step 7 data-flow hook (copy snippet from P3.9.3 exactly)
- [ ] **P3.6-TASK** — Write `backend/app/tasks/data_flow_tasks.py` with 2 Celery tasks
- [ ] **P3.6-REG** — Add `app.tasks.data_flow_tasks` to include list in `backend/app/worker.py`

#### API Layer (assign to: Backend Dev 1 or 2)
- [ ] **P3.7-SCH** — Add 4 new Pydantic schemas to `backend/app/schemas/code_component.py`
- [ ] **P3.7-EP1** — Add `GET /{id}/data-flow` endpoint to `backend/app/api/endpoints/code_components.py`
- [ ] **P3.7-EP2** — Add `GET /{id}/request-trace` endpoint
- [ ] **P3.7-EP3** — Add `POST /{id}/data-flow/rebuild` endpoint
- [ ] **P3.7-EP4** — Add `POST /{repository_id}/backfill-data-flow` to `backend/app/api/endpoints/repositories.py` (harden existing stub from P3.9.1)
- [ ] **P3.7-VER** — Run all API verification commands in P3.9.4 Steps 5–10

#### Frontend (assign to: Frontend Dev)
- [ ] **P3.8-HOOK** — Write `frontend/hooks/useDataFlow.ts` with useRequestTrace + useEgocentricFlow (SWR-based)
- [ ] **P3.8-GATE** — Write `frontend/components/data-flow/PremiumGateCard.tsx` (blurred SVG + upsell)
- [ ] **P3.8-EDGE** — Write `frontend/components/data-flow/EdgeListPanel.tsx` (Calls + Called By panels)
- [ ] **P3.8-MAIN** — Write `frontend/components/data-flow/DataFlowDiagram.tsx` (main orchestrator)
- [ ] **P3.8-WIRE** — Modify `frontend/app/dashboard/code/[id]/page.tsx`: add import, TabsTrigger, TabsContent
- [ ] **P3.8-VER** — Manual QA using verification steps in P3.9.4 Steps 11–12

#### QA Sign-Off (assign to: QA Engineer)
- [ ] **QA-E2E** — Run all 12 verification steps in P3.9.4
- [ ] **QA-MERMAID** — Validate generated Mermaid syntax at mermaid.live for 5 different component types (endpoint, service, schema, model, CRUD)
- [ ] **QA-CLICK** — Verify node click navigation works for each swimlane category
- [ ] **QA-MODES** — Verify technical ↔ business toggle re-renders with correct labels
- [ ] **QA-VIEWS** — Verify trace ↔ file-only toggle calls correct API endpoint
- [ ] **QA-DEPTH** — Verify depth selector (3/5/8) passes correct `?depth=N` param
- [ ] **QA-FREE** — Verify free-tier users see blurred gate and no API calls made
- [ ] **QA-PREMIUM** — Verify pro-tier users see full diagram with all controls
- [ ] **QA-MOBILE** — Verify diagram and controls are usable on 375px mobile viewport
- [ ] **QA-REBUILD** — Click "Rebuild" button → verify task dispatched → diagram refreshes after 3s polling
- [ ] **QA-NONBREAK** — Verify existing tabs (Analysis, Graph, Domains, System, Branches, Synthesis) still load correctly after adding Data Flow tab
- [ ] **QA-PIPELINE** — Analyze a fresh code component (one not analyzed before) → verify data-flow edges appear in DB automatically (Step 7 hook)

---

### P3.9.8 — What Does NOT Change in Phase 3

The following existing code is **untouched** by Phase 3. Developers must not modify these:

| Component | Reason |
|-----------|--------|
| `OntologyConcept` / `OntologyRelationship` tables | Not touched — data flow is a separate edge store |
| `_extract_ontology_from_analysis()` in `business_ontology_service.py` | Completely separate from data flow extraction |
| All existing validation endpoints | Unchanged |
| All existing ontology endpoints | Unchanged |
| `structured_analysis` JSON schema in existing records | New fields are additive and optional |
| `MermaidDiagram.tsx` component | Used as-is — no modifications needed |
| All existing `code_components` endpoints | New endpoints are additional, not replacing existing |
| Existing Celery task queue configuration | Only adding a new include module, not changing queue settings |

---

### P3.9.9 — Rollback Plan

If Phase 3 causes a production issue:

**Backend rollback (zero data loss):**
```bash
# 1. Revert worker.py to remove data_flow_tasks from include list
# 2. Revert code_analysis_service.py Step 7 hook
# 3. Revert code_components.py (remove 3 new endpoints)
# 4. Revert repositories.py (remove backfill endpoint)
# 5. Roll back migration:
alembic downgrade s12a1
# This drops code_data_flow_edges table — acceptable because it's new data only
```

**Frontend rollback:**
```bash
# Remove DataFlowDiagram tab from code/[id]/page.tsx
# Delete data-flow component directory
# No user data is affected
```

**Data safety:** The `code_data_flow_edges` table contains only derived data (computed from `structured_analysis`). Dropping it during rollback causes zero business data loss — it can be rebuilt at any time via the backfill endpoint.

---

## Phase 3 — Sprint Placement & Integration Points

### When to Execute Phase 3

Phase 3 should be executed as a **parallel track in Sprint 6**, alongside Phase 12 (Performance). It has no dependency on Phase 4 or 5, and Phase 3's prompt additions (P3.1 new fields) are a prerequisite for new code analyses from Phase 4 onwards.

```
Sprint 4 (Weeks 7-8):   Phase 4 (4-Engine Integration)
Sprint 5 (Weeks 9-10):  Phase 5 (Dynamic Prompting) + Phase 11 (Auto-Docs)
Sprint 6 (Weeks 11-12): Phase 3 (Data Flow Diagrams) ← HERE
                         Phase 12 (Performance) ← parallel
```

**Why Sprint 6?**  
1. Phase 3 benefits from Phase 4's BOEContext data (richer structured_analysis) — not hard-required but improves diagram quality
2. Phase 5 adds industry context to the analysis prompt — same time prompt is enhanced for data flow fields (P3.1 bundled)  
3. Phase 12 adds DB indexes including `code_data_flow_edges` indexes — cleanest if done together

**P3.1 Prompt Enhancement — Bundle with Phase 5:**  
The 4 new JSON output fields (`file_role`, `backed_by_model`, `model_definition`, `outbound_calls`) in the ENHANCED_SEMANTIC_ANALYSIS prompt (P3.1) should be added **in the same PR** as Phase 5's dynamic prompting changes to `prompt_manager.py`. This avoids two PRs touching the same file and simplifies review.

---

## Phase 3 — Summary for Product & Stakeholders

**What it delivers:**

> **"For every API endpoint, service, or data model in your codebase — DokyDoc shows you exactly how data flows through it, from the entry point all the way to the database and external services. Click any node to jump directly to that file's analysis. Share the diagram with your BA or PM using 'Business View' — they'll understand the system without reading code."**

**Business Value:**
- **Zero extra AI cost** — 100% deterministic, built from existing `structured_analysis` data
- **Premium gate** — creates a natural upgrade path from free → pro for existing users
- **Non-breaking** — wrapped in try/except, no existing features affected
- **Clickable navigation** — deepens engagement with code analysis pages
- **Two modes** — Technical for developers, Business for BAs/PMs/CTOs

**Metrics to track post-launch:**
- Data Flow tab activation rate (% of code component page views that click the tab)
- Free → pro conversion rate for users who hit the premium gate
- Diagram render error rate (track via `setError` in MermaidDiagram)
- Rebuild button click rate (signal that auto-build is not working well)
- Node click-through rate (are users navigating via the diagram?)


---

## P3.10 — Mermaid Click Callback Fix (`window.dokydocClick` + `securityLevel: 'loose'`)

**Owner:** Frontend Dev  
**Estimate:** 0.5 day  
**Severity:** CRITICAL — Node click navigation is completely broken without this  
**Covers:** GAP-1  
**Depends on:** P3.8 (DataFlowDiagram.tsx exists)

---

### Root Cause

Mermaid's `click n1 call dokydocClick("123")` directive works by invoking a **global JavaScript function** named `dokydocClick` on `window`. Two problems in the current plan:

1. `handleNodeClick` is a React closure inside `DataFlowDiagram.tsx` — it is **never exposed** on `window`, so Mermaid has nothing to call.
2. Mermaid's default `securityLevel: 'strict'` **silently ignores all click directives** regardless of step 1. This must be changed to `'loose'`.

Without both fixes, every node in every generated diagram is permanently non-clickable.

---

### Fix A — Register Global Click Handler in `DataFlowDiagram.tsx`

**File:** `frontend/components/data-flow/DataFlowDiagram.tsx`

Find the `handleNodeClick` function (already defined in P3.8) and add a `useEffect` **immediately after** it:

```tsx
// EXISTING (from P3.8):
const handleNodeClick = (nodeId: string) => {
  const numId = parseInt(nodeId, 10);
  if (!isNaN(numId)) {
    router.push(`/dashboard/code/${numId}`);
  }
};

// ADD THIS immediately after:
useEffect(() => {
  // Expose handler as global so Mermaid's `click n1 call dokydocClick("id")` works
  (window as any).dokydocClick = (id: string) => {
    const numId = parseInt(id, 10);
    if (!isNaN(numId)) {
      router.push(`/dashboard/code/${numId}`);
    }
  };
  // Clean up when component unmounts (e.g. user navigates away)
  return () => {
    delete (window as any).dokydocClick;
  };
}, [router]);
```

> **Why the cleanup matters:** Without it, navigating from one component page to another leaves a stale `window.dokydocClick` pointing to the old router instance, which could navigate to wrong pages.

---

### Fix B — Set `securityLevel: 'loose'` in `MermaidDiagram.tsx`

**File:** `frontend/components/ontology/MermaidDiagram.tsx`

Find the Mermaid initialization call (search for `mermaid.initialize` or `mermaid.init`). Add `securityLevel: 'loose'` to the config object:

```ts
// BEFORE (current state — securityLevel defaults to 'strict'):
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  // ... other existing config
});

// AFTER:
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",   // ← ADD THIS LINE
  // ... other existing config
});
```

> **Security note:** `securityLevel: 'loose'` allows Mermaid to invoke named global functions via click directives. This is safe here because:
> - The `dokydocClick` function only calls `router.push()` — it cannot execute arbitrary code
> - The Mermaid syntax itself is generated server-side by DokyDoc, not from user input
> - The function is cleaned up on unmount

---

### Fix C — Verify `onNodeClick` Prop Still Works (Non-Regression)

The existing `MermaidDiagram.tsx` `onNodeClick` prop is used by other diagrams (ontology graph, domain map). Confirm that setting `securityLevel: 'loose'` does NOT break those existing click handlers.

**Test:**
1. Navigate to a component's "Graph" or "Domains" tab (existing tab that uses `MermaidDiagram` with `onNodeClick`)
2. Verify node clicks still work as before
3. Navigate to "Data Flow" tab → verify `dokydocClick` fires on node click → browser navigates to component page

---

### Fix D — Harden `render_mermaid()` node ID format (Backend)

**File:** `backend/app/services/data_flow_service.py`

The current `click` directive format is:
```python
lines.append(f'    click {nid} call dokydocClick("{node["component_id"]}")')
```

The `nid` is a sequential counter (`n0`, `n1`, etc.) while `node["component_id"]` is the actual DB id. The `dokydocClick` receives the **DB id** as a string argument — this is correct. But add a safety guard to ensure we never emit a click directive for external nodes (which have `component_id = None`):

```python
# BEFORE (current — could emit click for external nodes):
if node.get("component_id"):
    lines.append(f'    click {nid} call dokydocClick("{node["component_id"]}")')

# AFTER (same — already has the guard — just confirm this line exists exactly as-is):
if node.get("component_id"):   # Only internal nodes with real DB ids get click handlers
    lines.append(f'    click {nid} call dokydocClick("{node["component_id"]}")')
```

This is already correct in P3.4 — just a confirmation checklist item.

---

### Verification Commands

```bash
# 1. Backend — ensure render_mermaid output contains click directives:
python3 -c "
from app.services.data_flow_service import DataFlowService
svc = DataFlowService()
nodes = [{'component_id': 42, 'name': 'TestService', 'file_role': 'SERVICE'}]
edges = []
result = svc.render_mermaid(nodes, edges, 'technical')
print(result)
assert 'click n0 call dokydocClick' in result, 'click directive missing'
print('OK')
"
```

```
# 2. Frontend — manual browser test:
# a. Open any pro-tier component → Data Flow tab
# b. Open browser DevTools → Console
# c. Type: window.dokydocClick
# Expected: function (not undefined)
# d. Click a node in the diagram
# Expected: browser navigates to /dashboard/code/{id}
```

```
# 3. Non-regression — ontology/graph tabs:
# a. Navigate to component → "Graph" tab (existing MermaidDiagram usage)
# b. Click any node
# Expected: existing behavior unchanged
```

---

### Developer Checklist

- [ ] Add `useEffect` to register `window.dokydocClick` in `DataFlowDiagram.tsx`
- [ ] Add cleanup `return () => delete (window as any).dokydocClick` in the same effect
- [ ] Add `securityLevel: "loose"` to `mermaid.initialize()` in `MermaidDiagram.tsx`
- [ ] Test non-regression on all existing diagram tabs (Graph, Domains, System)
- [ ] Test node click navigation in Data Flow tab (Technical mode + Business mode)
- [ ] Test that unmount cleanup works: navigate away → verify `window.dokydocClick` is `undefined`


---

## P3.11 — CACHE & EVENT Edge Extraction in DataFlowService

**Owner:** Backend Dev 2  
**Estimate:** 1 day  
**Severity:** CRITICAL — Diagram is structurally incomplete for any system using Redis, Celery, Kafka  
**Covers:** GAP-3  
**Depends on:** P3.4 (DataFlowService exists), P3.1 (outbound_calls prompt field)

---

### Root Cause

`DataFlowService.build_flow_for_component()` defines 10 edge types but generates only 5 of them. The 4 edge types below are in the DB CHECK constraint and in the EdgeListPanel UI but are never created:

| Edge Type | Represents | Typical Code Pattern |
|-----------|------------|---------------------|
| `CACHE_READ` | Redis GET / Memcached get / cache.get() | `await redis.get(key)`, `cache.get("user:123")` |
| `CACHE_WRITE` | Redis SET / cache.set() / cache.delete() | `await redis.set(key, value)`, `cache.delete(key)` |
| `EVENT_PUBLISH` | Celery task.delay() / Kafka produce / SQS send | `send_email.delay(user_id)`, `producer.send(topic, msg)` |
| `EVENT_CONSUME` | Celery @task decorator / Kafka consumer / SQS poll | `@celery_app.task`, `@app.task(name=...)` |

---

### What to Add in `DataFlowService.build_flow_for_component()`

**File:** `backend/app/services/data_flow_service.py`

Add these two new detection blocks inside `build_flow_for_component()`, **after the existing EXTERNAL_API block** and **before the SCHEMA block**:

```python
# ── CACHE edges: detect Redis / Memcached / cache interactions ──────────────
_CACHE_READ_KEYWORDS = {"redis.get", "cache.get", "get_cache", "cache_get",
                        "memcache.get", "client.get", "hget", "lrange",
                        "smembers", "zrange", "getex"}
_CACHE_WRITE_KEYWORDS = {"redis.set", "cache.set", "set_cache", "cache_set",
                         "memcache.set", "client.set", "hset", "lpush",
                         "rpush", "sadd", "zadd", "setex", "cache.delete",
                         "redis.delete", "cache_invalidate"}
_CACHE_SERVICE_KEYWORDS = {"redis", "cache", "memcache", "memcached",
                           "cacheservice", "redisclient"}

for i, interaction in enumerate(sa.get("component_interactions", []), start=1):
    target = (interaction.get("target") or "").lower()
    description = (interaction.get("description") or "").lower()
    combined = f"{target} {description}"

    # Determine if this is a cache interaction
    is_cache_target = any(kw in combined for kw in _CACHE_SERVICE_KEYWORDS)
    if not is_cache_target:
        continue

    # Determine READ vs WRITE
    is_read = any(kw in combined for kw in _CACHE_READ_KEYWORDS)
    is_write = any(kw in combined for kw in _CACHE_WRITE_KEYWORDS)
    if not is_read and not is_write:
        # Default: if we see cache target but can't determine direction, use CACHE_READ
        is_read = True

    edge_type = "CACHE_READ" if is_read else "CACHE_WRITE"
    cache_target = interaction.get("target", "Redis")

    edges.append({
        "tenant_id": tenant_id,
        "repository_id": component.repository_id,
        "source_component_id": component_id,
        "target_component_id": None,   # Cache is always external
        "edge_type": edge_type,
        "source_function": interaction.get("source"),
        "target_function": None,
        "data_in_description": interaction.get("data_passed"),
        "data_out_description": None,
        "human_label": self._build_human_label(
            edge_type,
            key=interaction.get("data_passed") or cache_target,
        ),
        "external_target_name": cache_target,
        "step_index": None,
    })

# ── EVENT edges: detect Celery / Kafka / RabbitMQ / SQS / SNS ───────────────
_EVENT_PUBLISH_KEYWORDS = {".delay(", ".apply_async(", "producer.send",
                           "publish(", "sns.publish", "sqs.send_message",
                           "rabbitmq.publish", "channel.publish",
                           "task.apply_async", "celery_app.send_task"}
_EVENT_CONSUME_KEYWORDS = {"@celery_app.task", "@app.task", "@shared_task",
                           "@task(", "consumer.poll", "consumer.consume",
                           "subscribe(", "sqs.receive_message",
                           "channel.consume", "@dramatiq.actor"}
_EVENT_SERVICE_KEYWORDS = {"celery", "kafka", "rabbitmq", "sqs", "sns",
                           "redis queue", "dramatiq", "rq.", "huey",
                           "event", "message queue", "broker"}

# Check component_interactions for event patterns
for i, interaction in enumerate(sa.get("component_interactions", []), start=1):
    target = (interaction.get("target") or "").lower()
    description = (interaction.get("description") or "").lower()
    source_fn = (interaction.get("source") or "").lower()
    combined = f"{target} {description} {source_fn}"

    is_event_target = any(kw in combined for kw in _EVENT_SERVICE_KEYWORDS)
    if not is_event_target:
        continue

    is_publish = any(kw in combined for kw in _EVENT_PUBLISH_KEYWORDS)
    is_consume = any(kw in combined for kw in _EVENT_CONSUME_KEYWORDS)
    if not is_publish and not is_consume:
        # Default: producer pattern if it's a service calling, consumer if it's a task decorator
        is_publish = True

    edge_type = "EVENT_PUBLISH" if is_publish else "EVENT_CONSUME"
    event_name = interaction.get("data_passed") or interaction.get("target", "event")

    edges.append({
        "tenant_id": tenant_id,
        "repository_id": component.repository_id,
        "source_component_id": component_id,
        "target_component_id": None,
        "edge_type": edge_type,
        "source_function": interaction.get("source"),
        "target_function": None,
        "data_in_description": interaction.get("data_passed"),
        "data_out_description": None,
        "human_label": self._build_human_label(
            edge_type,
            topic=event_name,
        ),
        "external_target_name": interaction.get("target", "Message Queue"),
        "step_index": None,
    })

# Also check outbound_calls for event patterns (P3.1 new field)
for i, call in enumerate(sa.get("outbound_calls", []), start=1):
    target_module = (call.get("target_module") or "").lower()
    target_fn = (call.get("target_function") or "").lower()
    combined_call = f"{target_module} {target_fn}"

    # Cache via outbound_calls
    if any(kw in combined_call for kw in _CACHE_SERVICE_KEYWORDS):
        is_read = any(kw in combined_call for kw in {"get", "read", "fetch", "hget", "lrange"})
        edge_type = "CACHE_READ" if is_read else "CACHE_WRITE"
        edges.append({
            "tenant_id": tenant_id,
            "repository_id": component.repository_id,
            "source_component_id": component_id,
            "target_component_id": None,
            "edge_type": edge_type,
            "source_function": call.get("caller_function"),
            "target_function": call.get("target_function"),
            "data_in_description": call.get("data_in"),
            "data_out_description": call.get("data_out"),
            "human_label": self._build_human_label(
                edge_type,
                key=call.get("data_in") or call.get("target_function", "key"),
            ),
            "external_target_name": "Redis" if "redis" in combined_call else "Cache",
            "step_index": i,
        })

    # Events via outbound_calls
    elif any(kw in combined_call for kw in _EVENT_SERVICE_KEYWORDS):
        is_pub = any(kw in combined_call for kw in {"delay", "apply_async", "send", "publish"})
        edge_type = "EVENT_PUBLISH" if is_pub else "EVENT_CONSUME"
        edges.append({
            "tenant_id": tenant_id,
            "repository_id": component.repository_id,
            "source_component_id": component_id,
            "target_component_id": None,
            "edge_type": edge_type,
            "source_function": call.get("caller_function"),
            "target_function": call.get("target_function"),
            "data_in_description": call.get("data_in"),
            "data_out_description": call.get("data_out"),
            "human_label": self._build_human_label(
                edge_type,
                topic=call.get("target_function") or call.get("data_in") or "task",
            ),
            "external_target_name": call.get("target_module", "Message Queue"),
            "step_index": i,
        })
```

> **Placement note:** Insert both blocks **after** the existing `EXTERNAL_API` detection block (the `elif any(kw in dest for kw in ("external", "api", "sendgrid", ...)):` block) and **before** the `SCHEMA: backed_by_model` block. The new blocks process `component_interactions` independently from the existing `data_flows` loop.

---

### Add Module-Level Keyword Sets (at top of file)

Add these constants **at the top of `data_flow_service.py`** (after the `_FILE_TYPE_TO_ROLE` dict):

```python
# Cache keyword sets (used in build_flow_for_component)
_CACHE_READ_KEYWORDS = frozenset({
    "redis.get", "cache.get", "get_cache", "cache_get", "memcache.get",
    "client.get", "hget", "lrange", "smembers", "zrange", "getex",
})
_CACHE_WRITE_KEYWORDS = frozenset({
    "redis.set", "cache.set", "set_cache", "cache_set", "memcache.set",
    "client.set", "hset", "lpush", "rpush", "sadd", "zadd", "setex",
    "cache.delete", "redis.delete", "cache_invalidate",
})
_CACHE_SERVICE_KEYWORDS = frozenset({
    "redis", "cache", "memcache", "memcached", "cacheservice", "redisclient",
})

# Event/queue keyword sets
_EVENT_PUBLISH_KEYWORDS = frozenset({
    ".delay(", ".apply_async(", "producer.send", "publish(",
    "sns.publish", "sqs.send_message", "rabbitmq.publish",
    "channel.publish", "task.apply_async", "celery_app.send_task",
})
_EVENT_CONSUME_KEYWORDS = frozenset({
    "@celery_app.task", "@app.task", "@shared_task", "@task(",
    "consumer.poll", "consumer.consume", "subscribe(",
    "sqs.receive_message", "channel.consume", "@dramatiq.actor",
})
_EVENT_SERVICE_KEYWORDS = frozenset({
    "celery", "kafka", "rabbitmq", "sqs", "sns", "dramatiq", "rq.",
    "huey", "event", "message queue", "broker",
})
```

> **Why `frozenset`:** Membership checks on frozensets are O(1) vs O(n) for lists. These sets are checked per-edge in a loop — performance matters for components with many interactions.

---

### Deduplication Guard

When a component has both `outbound_calls` AND `component_interactions` present (P3.1 new field + old field), it is possible to generate duplicate edges. Add a deduplication step **before** the `crud_code_data_flow_edge.bulk_create()` call:

```python
# Deduplicate edges: same source + edge_type + external_target is one edge
seen = set()
deduped_edges = []
for e in edges:
    key = (
        e["source_component_id"],
        e.get("target_component_id"),
        e["edge_type"],
        e.get("external_target_name") or "",
        e.get("source_function") or "",
    )
    if key not in seen:
        seen.add(key)
        deduped_edges.append(e)
edges = deduped_edges

# Delete old edges and insert new ones (idempotent rebuild)
crud_code_data_flow_edge.delete_by_component(
    db=db, component_id=component_id, tenant_id=tenant_id
)
created = crud_code_data_flow_edge.bulk_create(db=db, edges=deduped_edges)
```

---

### Verification Commands

```bash
# 1. Analyze a file that uses Redis (e.g. a service that calls cache.get / cache.set)
# Trigger rebuild for that component, then check DB:
psql $DATABASE_URL -c "
SELECT edge_type, source_function, external_target_name, human_label
FROM code_data_flow_edges
WHERE source_component_id = {COMPONENT_ID}
ORDER BY edge_type;
"
# Expected: CACHE_READ and/or CACHE_WRITE rows present

# 2. Analyze a service that calls a Celery task (.delay())
# Expected: EVENT_PUBLISH row with external_target_name = task module name

# 3. Analyze a Celery task file (@celery_app.task decorated)
# Expected: EVENT_CONSUME row

# 4. Verify no duplicate edges:
psql $DATABASE_URL -c "
SELECT source_component_id, edge_type, external_target_name, COUNT(*)
FROM code_data_flow_edges
GROUP BY source_component_id, edge_type, external_target_name
HAVING COUNT(*) > 1;
"
# Expected: 0 rows (no duplicates)

# 5. Verify CACHE/EVENT edges show in EdgeListPanel:
# Navigate to a cache-using component → Data Flow tab
# Scroll to "Calls" panel
# Expected: CACHE_READ/WRITE entries with yellow/orange badge
```

---

### Developer Checklist

- [ ] Add `_CACHE_*` and `_EVENT_*` keyword frozensets as module-level constants at top of `data_flow_service.py`
- [ ] Add CACHE edge extraction block (from `component_interactions` + `outbound_calls`)
- [ ] Add EVENT edge extraction block (from `component_interactions` + `outbound_calls`)
- [ ] Add deduplication guard before `bulk_create()`
- [ ] Test with a real Redis-using service component
- [ ] Test with a real Celery task file
- [ ] Verify no duplicate edges created when both `outbound_calls` and `component_interactions` present
- [ ] Verify all 10 edge types appear in the EdgeListPanel for a complex component


---

## P3.12 — Task Status Polling & Backfill Progress UI

**Owner:** Backend Dev 1 (API) + Frontend Dev (UI)  
**Estimate:** 1.5 days  
**Severity:** HIGH — Rebuild appears to do nothing when Celery is under load; backfill has zero visibility  
**Covers:** GAP-5, GAP-8  
**Depends on:** P3.6 (Celery tasks), P3.7 (rebuild endpoint), P3.8 (DataFlowDiagram)

---

### Root Cause

The rebuild flow uses a hardcoded 3-second wait before re-fetching:
```ts
setTimeout(() => { traceResult.mutate?.(); egoResult.mutate?.(); }, 3000);
```
If Celery is processing other jobs, the task might take 10–60 seconds. The diagram stays stale and the user has no feedback.

The backfill endpoint returns `{ task_id, component_count }` but there is no UI to show progress, no way to know when it completes, and no indication of how many components succeeded vs failed.

---

### Part A — Task Status API Endpoint (Backend)

**File:** `backend/app/api/endpoints/tasks.py` (new file)

```python
# backend/app/api/endpoints/tasks.py
"""
Generic Celery task status endpoint.
Returns task state, result, and metadata from the Celery result backend.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}/status")
def get_task_status(
    task_id: str,
    current_user=Depends(deps.get_current_active_user),
):
    """
    Poll Celery task status by task_id.

    Returns:
      - state: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY"
      - result: task return value (if SUCCESS), error message (if FAILURE)
      - progress: optional progress dict for tasks that emit intermediate updates
    """
    from app.core.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "state": result.state,
        "result": None,
        "error": None,
    }

    if result.state == "SUCCESS":
        response["result"] = result.result   # e.g. {"success": 72, "failed": 15, "total": 87}
    elif result.state == "FAILURE":
        response["error"] = str(result.result)
    elif result.state in ("PENDING", "STARTED", "RETRY"):
        # Some tasks emit progress via result.info
        if isinstance(result.info, dict):
            response["progress"] = result.info

    return response
```

**Register in `backend/app/api/api.py`:**
```python
from app.api.endpoints import tasks
api_router.include_router(tasks.router, prefix="/api/v1")
```

> **Note:** This endpoint intentionally does NOT restrict by tenant — task_id is an opaque UUID, not guessable. Any authenticated user who has the task_id (received from the API response) can poll it.

---

### Part B — Emit Progress from Backfill Task (Backend)

**File:** `backend/app/tasks/data_flow_tasks.py`

Update `backfill_data_flow_edges` to emit progress updates via `self.update_state()`:

```python
@celery_app.task(name="backfill_data_flow_edges", bind=True, max_retries=2)
def backfill_data_flow_edges(self, repository_id: int, tenant_id: int):
    from app.db.session import SessionLocal
    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service

    db = SessionLocal()
    results = {"success": 0, "failed": 0, "total": 0}
    try:
        components = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repository_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",   # canonical value — see P3.15
            CodeComponent.structured_analysis.isnot(None),
        ).all()

        results["total"] = len(components)
        logger.info(f"Backfilling {len(components)} components for repo {repository_id}")

        for idx, component in enumerate(components, start=1):
            # ── Emit progress so frontend can poll ──────────────────────
            self.update_state(
                state="STARTED",
                meta={
                    "current": idx,
                    "total": results["total"],
                    "success": results["success"],
                    "failed": results["failed"],
                    "current_component": component.name,
                },
            )
            # ────────────────────────────────────────────────────────────
            try:
                data_flow_service.build_flow_for_component(
                    db=db, component_id=component.id, tenant_id=tenant_id,
                )
                results["success"] += 1
            except Exception as e:
                logger.warning(f"Backfill failed for component {component.id}: {e}")
                results["failed"] += 1

        logger.info(f"Backfill complete: {results}")
        return results
    except Exception as exc:
        logger.error(f"Backfill task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
```

---

### Part C — Smart Polling in `DataFlowDiagram.tsx` (Frontend)

**File:** `frontend/components/data-flow/DataFlowDiagram.tsx`

Replace the hardcoded 3-second timeout with real polling:

```tsx
// BEFORE (P3.8 original — race condition):
const handleRebuild = async () => {
  setIsRebuilding(true);
  try {
    await apiPost(`/code-components/${componentId}/data-flow/rebuild`, {});
    toast.success("Diagram rebuilding — refresh in a few seconds");
    setTimeout(() => {
      traceResult.mutate?.();
      egoResult.mutate?.();
    }, 3000);
  } catch {
    toast.error("Rebuild failed");
  } finally {
    setIsRebuilding(false);
  }
};

// AFTER (P3.12 — real polling):
const handleRebuild = async () => {
  setIsRebuilding(true);
  try {
    const { task_id } = await apiPost(
      `/code-components/${componentId}/data-flow/rebuild`, {}
    );
    toast.info("Rebuilding diagram...");

    // Poll task status until terminal state
    let attempts = 0;
    const maxAttempts = 20;   // 20 × 2s = 40s max wait
    const poll = setInterval(async () => {
      attempts++;
      try {
        const status = await apiGet(`/tasks/${task_id}/status`);
        if (status.state === "SUCCESS") {
          clearInterval(poll);
          setIsRebuilding(false);
          toast.success("Diagram updated");
          traceResult.mutate?.();
          egoResult.mutate?.();
        } else if (status.state === "FAILURE") {
          clearInterval(poll);
          setIsRebuilding(false);
          toast.error(`Rebuild failed: ${status.error}`);
        } else if (attempts >= maxAttempts) {
          clearInterval(poll);
          setIsRebuilding(false);
          toast.warning("Rebuild is taking longer than expected — try refreshing");
        }
      } catch {
        clearInterval(poll);
        setIsRebuilding(false);
      }
    }, 2000);   // Poll every 2 seconds
  } catch {
    toast.error("Could not start rebuild");
    setIsRebuilding(false);
  }
};
```

---

### Part D — Backfill Progress Card (Frontend)

**New file:** `frontend/components/data-flow/BackfillProgressCard.tsx`

This component is shown in the repository settings or overview page when a backfill is in progress. It is NOT shown in the Data Flow tab (which is per-component).

```tsx
// frontend/components/data-flow/BackfillProgressCard.tsx
"use client";
import { useEffect, useState } from "react";
import { Loader2, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import { apiGet } from "@/lib/api";

interface Props {
  taskId: string;
  totalComponents: number;
  onComplete?: (result: { success: number; failed: number; total: number }) => void;
}

export function BackfillProgressCard({ taskId, totalComponents, onComplete }: Props) {
  const [state, setState] = useState<"polling" | "success" | "failed">("polling");
  const [progress, setProgress] = useState({ current: 0, success: 0, failed: 0 });
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const status = await apiGet(`/tasks/${taskId}/status`);
        if (status.state === "STARTED" && status.progress) {
          setProgress({
            current: status.progress.current ?? 0,
            success: status.progress.success ?? 0,
            failed: status.progress.failed ?? 0,
          });
        } else if (status.state === "SUCCESS") {
          clearInterval(interval);
          setState("success");
          setResult(status.result);
          onComplete?.(status.result);
        } else if (status.state === "FAILURE") {
          clearInterval(interval);
          setState("failed");
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [taskId, onComplete]);

  const pct = totalComponents > 0
    ? Math.round((progress.current / totalComponents) * 100)
    : 0;

  return (
    <div className="rounded-xl border bg-white p-4 space-y-3">
      <div className="flex items-center gap-2">
        {state === "polling" && <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />}
        {state === "success" && <CheckCircle className="h-4 w-4 text-green-500" />}
        {state === "failed" && <XCircle className="h-4 w-4 text-red-500" />}
        <span className="text-sm font-medium text-gray-800">
          {state === "polling" && "Building data flow diagrams..."}
          {state === "success" && "Backfill complete"}
          {state === "failed" && "Backfill failed"}
        </span>
      </div>

      {state === "polling" && (
        <>
          {/* Progress bar */}
          <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>{progress.current} / {totalComponents} components</span>
            <span>
              {progress.success > 0 && <span className="text-green-600">{progress.success} done</span>}
              {progress.failed > 0 && <span className="text-red-500 ml-2">{progress.failed} failed</span>}
            </span>
          </div>
        </>
      )}

      {state === "success" && result && (
        <div className="flex gap-4 text-xs">
          <span className="text-green-600 font-medium">{result.success} succeeded</span>
          {result.failed > 0 && (
            <span className="text-red-500 font-medium">{result.failed} failed</span>
          )}
          <span className="text-gray-400">{result.total} total</span>
        </div>
      )}
    </div>
  );
}
```

**Where to use it:** In `frontend/app/dashboard/repositories/[id]/page.tsx` (or equivalent repo detail page). After triggering backfill, store `task_id` + `component_count` in local state and render `<BackfillProgressCard>`.

---

### Verification Commands

```bash
# 1. API — trigger rebuild and poll status:
TASK=$(curl -sX POST .../code-components/5/data-flow/rebuild \
  -H "Authorization: Bearer $TOKEN" | jq -r '.task_id')
echo "Task: $TASK"

# Poll until SUCCESS:
for i in $(seq 1 10); do
  STATUS=$(curl -s .../tasks/$TASK/status -H "Authorization: Bearer $TOKEN")
  echo "Attempt $i: $(echo $STATUS | jq -r '.state')"
  [ "$(echo $STATUS | jq -r '.state')" = "SUCCESS" ] && break
  sleep 2
done

# 2. Backfill progress:
BTASK=$(curl -sX POST .../repositories/1/backfill-data-flow \
  -H "Authorization: Bearer $TOKEN" | jq -r '.task_id')

# Poll and see intermediate STARTED states with progress:
curl -s .../tasks/$BTASK/status -H "Authorization: Bearer $TOKEN" | jq '.progress'
# Expected during processing: {"current": 15, "total": 87, "success": 14, "failed": 1, ...}
```

---

### Developer Checklist

**Backend (Dev 1):**
- [ ] Create `backend/app/api/endpoints/tasks.py` with `GET /{task_id}/status`
- [ ] Register tasks router in `backend/app/api/api.py`
- [ ] Add `self.update_state(state="STARTED", meta={...})` calls to `backfill_data_flow_edges` Celery task

**Frontend (Frontend Dev):**
- [ ] Replace 3-second `setTimeout` in `handleRebuild` with interval polling logic
- [ ] Create `frontend/components/data-flow/BackfillProgressCard.tsx`
- [ ] Integrate `BackfillProgressCard` into repository overview/settings page


---

## P3.13 — User Role & Tenant Tier in Frontend Context

**Owner:** Backend Dev 1 (API) + Frontend Dev (context store)  
**Estimate:** 1 day  
**Severity:** CRITICAL + HIGH — Role-aware diagram defaults broken; free tier shows loading flash before gate  
**Covers:** GAP-2, GAP-6  
**Depends on:** Existing `/auth/me` endpoint, existing user context store

---

### Root Cause 1 — `currentUser?.roles` (plural array) Does Not Exist

The backend `User` model has `role: str` (a single string like `"admin"`, `"member"`, `"viewer"`). The frontend `DataFlowDiagram` component receives:
```tsx
userRoles={currentUser?.roles}   // always undefined
```
This makes `userRoles.some(r => ["business_analyst", ...].includes(r))` always return `false`. BAs always land on "Technical" mode.

### Root Cause 2 — Tenant Tier Not in User Context

The frontend has no knowledge of `tenant.tier` until it makes an API call and receives a 403. Free tier users see a loading skeleton before the premium gate appears — jarring UX.

---

### Fix A — Expose `role` and `tenant_tier` from `/auth/me` (Backend)

**File:** `backend/app/api/endpoints/auth.py` (or wherever `GET /auth/me` is defined)

Find the response schema for `/auth/me` and add `tenant_tier`:

```python
# Find the existing UserMeResponse or similar schema in backend/app/schemas/user.py
# ADD these two fields:

class UserMeResponse(BaseModel):
    id: int
    email: str
    role: str                    # existing field — "admin" | "member" | "viewer" etc.
    tenant_id: int
    tenant_tier: str             # ← ADD: "free" | "pro" | "enterprise"
    # ... other existing fields
    
    model_config = ConfigDict(from_attributes=True)
```

**In the `/auth/me` endpoint handler**, populate `tenant_tier`:

```python
@router.get("/me", response_model=UserMeResponse)
def get_current_user_info(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    from app.models.tenant import Tenant
    tenant = db.get(Tenant, current_user.tenant_id)
    return {
        **current_user.__dict__,
        "tenant_tier": getattr(tenant, "tier", "free"),
    }
```

> **Note:** If `Tenant` model does not yet have a `tier` field (it may be added in Phase 5), return `"free"` as a safe default. The premium gate will show for all users until the tier field exists, which is the safe direction.

---

### Fix B — Add `tenant_tier` and Role Helpers to Frontend User Context

**File:** `frontend/lib/types/user.ts` (or wherever the `User` type is defined)

```ts
// Find the existing User type and add tenant_tier:
export interface CurrentUser {
  id: number;
  email: string;
  role: string;          // existing — "admin" | "member" | "viewer"
  tenant_id: number;
  tenant_tier: "free" | "pro" | "enterprise";   // ← ADD
  // ... other existing fields
}

// ADD these helper functions (or add to existing user utils):
export function isProOrEnterprise(user: CurrentUser | null | undefined): boolean {
  return user?.tenant_tier === "pro" || user?.tenant_tier === "enterprise";
}

export function getDataFlowMode(user: CurrentUser | null | undefined): "technical" | "simple" {
  // Business Analyst and PM roles default to simple (Business) view
  const businessRoles = ["business_analyst", "product_manager", "ba", "pm", "cxo", "vp"];
  const role = (user?.role ?? "").toLowerCase();
  return businessRoles.some((r) => role.includes(r)) ? "simple" : "technical";
}
```

---

### Fix C — Update `DataFlowDiagram.tsx` to Use Correct Props

**File:** `frontend/components/data-flow/DataFlowDiagram.tsx`

Update the `Props` interface and prop handling:

```tsx
// BEFORE (P3.8 original):
interface Props {
  componentId: number;
  fileRole?: string;
  userRoles?: string[];   // ← This was wrong — User model has role (singular)
}

// AFTER:
interface Props {
  componentId: number;
  fileRole?: string;
  userRole?: string;         // singular string from currentUser.role
  tenantTier?: string;       // "free" | "pro" | "enterprise"
}
```

Update the default state derivation:

```tsx
// BEFORE (P3.8 original — always false because userRoles is undefined):
const [flowMode, setFlowMode] = useState<FlowMode>(
  userRoles?.some((r) => ["business_analyst", "product_manager", "cxo"].includes(r))
    ? "simple" : "technical"
);

// AFTER:
const [flowMode, setFlowMode] = useState<FlowMode>(() => {
  const role = (userRole ?? "").toLowerCase();
  const businessRoles = ["business_analyst", "product_manager", "ba", "pm", "cxo", "vp"];
  return businessRoles.some((r) => role.includes(r)) ? "simple" : "technical";
});
```

Update premium gate logic — show gate immediately without API roundtrip:

```tsx
// BEFORE (P3.8 original — only detects gate after 403 response):
const [isPremiumGated, setIsPremiumGated] = useState(false);

useEffect(() => {
  if (error?.status === 403) setIsPremiumGated(true);
}, [error]);

// AFTER — detect immediately from tenantTier prop:
const isPremiumGated = tenantTier === "free";
// (Keep the error detection as a fallback for missing prop scenarios)
useEffect(() => {
  if (error?.status === 403 && !isPremiumGated) {
    // This shouldn't happen if tenantTier is correctly passed,
    // but keep as a safety fallback
    console.warn("Premium gate: 403 received but tenantTier was not 'free'");
  }
}, [error, isPremiumGated]);
```

> **Result:** Free tier users see `PremiumGateCard` **instantly** on tab activation — no loading spinner, no API call, no 403 round-trip.

---

### Fix D — Update Wire-In in `code/[id]/page.tsx`

**File:** `frontend/app/dashboard/code/[id]/page.tsx`

Update the DataFlowDiagram usage (replaces the step from P3.8):

```tsx
// BEFORE (P3.8 — wrong prop):
<DataFlowDiagram
  componentId={Number(id)}
  fileRole={component?.structured_analysis?.file_role}
  userRoles={currentUser?.roles}          // ← wrong: was always undefined
/>

// AFTER:
<DataFlowDiagram
  componentId={Number(id)}
  fileRole={component?.structured_analysis?.file_role}
  userRole={currentUser?.role}            // ← correct: singular string
  tenantTier={currentUser?.tenant_tier}   // ← new: instant gate detection
/>
```

---

### Fix E — Update PremiumGateCard Upgrade Link

The link in `PremiumGateCard.tsx` currently points to:
```tsx
href="/dashboard/settings?tab=billing"
```

Ensure this is the correct path in the actual application. If the billing settings are at a different route, update it here. This is the canonical upgrade path for all premium gates in the app — keep it consistent.

---

### Verification Commands

```bash
# 1. Backend — verify tenant_tier in /auth/me response:
curl -H "Authorization: Bearer $FREE_TOKEN" \
  http://localhost:8000/api/v1/auth/me | jq '.tenant_tier'
# Expected: "free"

curl -H "Authorization: Bearer $PRO_TOKEN" \
  http://localhost:8000/api/v1/auth/me | jq '.tenant_tier'
# Expected: "pro"
```

```
# 2. Frontend — free tier instant gate:
# a. Log in as free tier user
# b. Navigate to any code component
# c. Click "Data Flow" tab
# d. Open Network tab in DevTools
# Expected: NO request to /data-flow or /request-trace (gate shows immediately)
# Expected: PremiumGateCard visible immediately (no loading spinner)
```

```
# 3. Frontend — role-aware mode default:
# a. Log in as a user whose role is "business_analyst" (or configure a test user)
# b. Navigate to any code component (pro tier tenant)
# c. Click "Data Flow" tab
# Expected: "Business" mode button is active by default (not "Technical")
```

---

### Developer Checklist

**Backend (Dev 1):**
- [ ] Add `tenant_tier: str` to `UserMeResponse` schema
- [ ] Update `/auth/me` handler to query Tenant and include `tier` (default `"free"` if tenant has no tier field yet)
- [ ] Write test: `GET /auth/me` for free tenant returns `tenant_tier: "free"`
- [ ] Write test: `GET /auth/me` for pro tenant returns `tenant_tier: "pro"`

**Frontend (Frontend Dev):**
- [ ] Add `tenant_tier` to `CurrentUser` type definition
- [ ] Add `isProOrEnterprise()` and `getDataFlowMode()` helper functions
- [ ] Update `DataFlowDiagram.tsx` Props: change `userRoles?: string[]` → `userRole?: string` + `tenantTier?: string`
- [ ] Replace `isPremiumGated` state with direct `tenantTier === "free"` check
- [ ] Update `useState(flowMode)` initialization to use `userRole` (singular)
- [ ] Update wire-in in `code/[id]/page.tsx`: pass `userRole` and `tenantTier`
- [ ] Verify: free tier user sees gate instantly on tab click (no loading flash)
- [ ] Verify: BA-role pro user defaults to Business mode
- [ ] Verify: Developer-role pro user defaults to Technical mode


---

## P3.14 — Egocentric View: Fix Missing Incoming Edge Source Nodes

**Owner:** Backend Dev 2  
**Estimate:** 0.5 day  
**Severity:** CRITICAL — "This File Only" Mermaid diagram renders no incoming edges  
**Covers:** GAP-4  
**Depends on:** P3.7 (egocentric endpoint), P3.3 (CRUD methods)

---

### Root Cause

The `GET /code-components/{id}/data-flow` endpoint (egocentric view) builds a node list with **only the current component**:

```python
# P3.7 current code — only one node:
node_self = [{
    "component_id": id,
    "name": comp.name,
    "location": comp.location,
    "file_role": file_role,
    "summary": comp.summary,
}]
return EgocentricFlowResponse(
    mermaid_technical=data_flow_service.render_mermaid(node_self, all_edges, "technical"),
    ...
)
```

`edges_in` are edges FROM other components TO this one. In `render_mermaid()`:
```python
src_node = node_id_map.get(src_id)   # src_id = other component's ID, NOT in node_self
# → src_node is None → `continue` → edge SKIPPED entirely
```

Result: The Mermaid diagram in "This File Only" mode renders zero incoming edges — the "Called By" section exists only in the EdgeListPanel text list, not in the visual diagram.

---

### Fix — Enrich Egocentric Node List

**File:** `backend/app/api/endpoints/code_components.py`

Replace the egocentric endpoint's node building section:

```python
# GET /code-components/{id}/data-flow
@router.get("/{id}/data-flow", response_model=EgocentricFlowResponse)
def get_component_data_flow(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
):
    _check_premium(current_user.tenant_id, db)

    from app.models.code_component import CodeComponent
    from app.services.data_flow_service import data_flow_service
    from app.crud.crud_code_data_flow_edge import crud_code_data_flow_edge

    comp = db.get(CodeComponent, id)
    if not comp or comp.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Component not found")

    # Use the efficient get_egocentric method (single query — fixes GAP-11)
    edges_in, edges_out = crud_code_data_flow_edge.get_egocentric(
        db=db, component_id=id, tenant_id=current_user.tenant_id
    )
    all_edges = edges_in + edges_out

    sa = comp.structured_analysis or {}
    file_role = data_flow_service._resolve_file_role(sa)

    # ── Build complete node list ──────────────────────────────────────────────
    # Start with the focal component
    nodes = [{
        "component_id": id,
        "name": comp.name,
        "location": comp.location,
        "file_role": file_role,
        "summary": comp.summary,
        "model_columns": sa.get("model_definition", {}).get("columns"),
        "schema_fields": sa.get("backed_by_model", {}).get("fields"),
    }]

    # Add source nodes from edges_in (the callers of this component)
    seen_ids = {id}
    for edge in edges_in:
        src_id = edge.source_component_id
        if src_id and src_id not in seen_ids:
            seen_ids.add(src_id)
            src_comp = db.get(CodeComponent, src_id)
            if src_comp and src_comp.tenant_id == current_user.tenant_id:
                src_sa = src_comp.structured_analysis or {}
                nodes.append({
                    "component_id": src_id,
                    "name": src_comp.name,
                    "location": src_comp.location,
                    "file_role": data_flow_service._resolve_file_role(src_sa),
                    "summary": src_comp.summary,
                })

    # Add target nodes from edges_out (the callees of this component)
    for edge in edges_out:
        tgt_id = edge.target_component_id
        if tgt_id and tgt_id not in seen_ids:
            seen_ids.add(tgt_id)
            tgt_comp = db.get(CodeComponent, tgt_id)
            if tgt_comp and tgt_comp.tenant_id == current_user.tenant_id:
                tgt_sa = tgt_comp.structured_analysis or {}
                nodes.append({
                    "component_id": tgt_id,
                    "name": tgt_comp.name,
                    "location": tgt_comp.location,
                    "file_role": data_flow_service._resolve_file_role(tgt_sa),
                    "summary": tgt_comp.summary,
                })
        elif not tgt_id and edge.external_target_name:
            # External node (no DB record)
            ext_name = edge.external_target_name
            if ext_name not in seen_ids:
                seen_ids.add(ext_name)
                nodes.append({
                    "component_id": None,
                    "name": ext_name,
                    "location": None,
                    "file_role": None,
                    "is_external": True,
                })
    # ─────────────────────────────────────────────────────────────────────────

    # Also compute edges_built_at for GAP-10 (see P3.15)
    from sqlalchemy import func as sql_func
    from app.models.code_data_flow_edge import CodeDataFlowEdge as EdgeModel
    edges_built_at_row = db.query(sql_func.max(EdgeModel.created_at)).filter(
        EdgeModel.source_component_id == id,
        EdgeModel.tenant_id == current_user.tenant_id,
    ).scalar()

    return EgocentricFlowResponse(
        component_id=id,
        file_role=file_role,
        edges_in=edges_in,
        edges_out=edges_out,
        mermaid_technical=data_flow_service.render_mermaid(nodes, all_edges, "technical"),
        mermaid_simple=data_flow_service.render_mermaid(nodes, all_edges, "simple"),
        total_edges=len(all_edges),
        edges_built_at=edges_built_at_row,   # None if never built (see P3.15)
    )
```

---

### Update `EgocentricFlowResponse` Schema

**File:** `backend/app/schemas/code_component.py`

Add `edges_built_at` and `nodes` to the schema (the `nodes` field enables the frontend to show rich data even in egocentric mode):

```python
class EgocentricFlowResponse(BaseModel):
    component_id: int
    file_role: str
    edges_in: list[DataFlowEdgeSchema]
    edges_out: list[DataFlowEdgeSchema]
    nodes: list[DataFlowNodeSchema]           # ← ADD: all relevant nodes for this view
    mermaid_technical: str
    mermaid_simple: str
    total_edges: int
    edges_built_at: Optional[datetime] = None  # ← ADD: None = never built

    model_config = ConfigDict(from_attributes=True)
```

---

### Update `get_egocentric` in CRUD

**File:** `backend/app/crud/crud_code_data_flow_edge.py`

The `get_egocentric` method was defined in P3.3 but not detailed. Implement it as a single query returning both directions:

```python
def get_egocentric(
    self,
    db: Session,
    *,
    component_id: int,
    tenant_id: int,
) -> tuple[list[CodeDataFlowEdge], list[CodeDataFlowEdge]]:
    """
    Return (edges_in, edges_out) for a component in two separate lists.
    Single method call vs two separate get_by_source/get_by_target calls.
    Edges are sorted by step_index ASC NULLS LAST (see P3.15).
    """
    edges_out = (
        db.query(CodeDataFlowEdge)
        .filter(
            CodeDataFlowEdge.source_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        )
        .order_by(
            CodeDataFlowEdge.step_index.asc().nullslast()
        )
        .all()
    )
    edges_in = (
        db.query(CodeDataFlowEdge)
        .filter(
            CodeDataFlowEdge.target_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        )
        .order_by(
            CodeDataFlowEdge.step_index.asc().nullslast()
        )
        .all()
    )
    return edges_in, edges_out
```

---

### Verification Commands

```bash
# 1. For a component that IS called by other components (e.g. a UserCRUD called by UserService):
curl -H "Authorization: Bearer $PRO_TOKEN" \
  http://localhost:8000/api/v1/code-components/{CRUD_COMPONENT_ID}/data-flow \
  | python3 -m json.tool

# Expected:
# - "edges_in" array is non-empty
# - "nodes" array contains BOTH the CRUD component AND the calling service component(s)
# - "mermaid_technical" string contains node IDs for both the CRUD and the calling service
# - "total_edges" = len(edges_in) + len(edges_out)
```

```
# 2. Browser test:
# a. Open a CRUD file's Data Flow tab → "This File Only" view
# b. Verify the Mermaid diagram shows INCOMING arrows (not just outgoing)
# c. Verify nodes from calling services appear as box shapes in the correct swimlane
# d. Click on a calling service node → verify navigation to that component page
```

---

### Developer Checklist

- [ ] Implement `get_egocentric()` in `CRUDCodeDataFlowEdge` (returns tuple of edges_in, edges_out, ordered by step_index)
- [ ] Update egocentric endpoint to use `get_egocentric()` instead of separate calls
- [ ] Add incoming edge source nodes to the node list (with tenant isolation check)
- [ ] Add outgoing edge target nodes to the node list (with tenant isolation check)
- [ ] Add external node handling (null target_component_id)
- [ ] Add `edges_built_at` query to egocentric endpoint
- [ ] Add `nodes` and `edges_built_at` fields to `EgocentricFlowResponse` schema
- [ ] Test: CRUD file shows callers in diagram
- [ ] Test: MODEL file shows writers and readers in diagram
- [ ] Test: ENDPOINT file shows downstream services in diagram


---

## P3.15 — Edge Quality Omnibus Fix

**Owner:** Backend Dev 1 (items A, B, E) + Backend Dev 2 (items C, D) + Frontend Dev (item F)  
**Estimate:** 1 day  
**Severity:** HIGH + MEDIUM — Multiple quality and consistency issues that degrade diagram accuracy  
**Covers:** GAP-7, GAP-9, GAP-10, GAP-11, GAP-13  
**Depends on:** P3.3 (CRUD), P3.4 (DataFlowService), P3.7 (API schemas), P3.14 (EgocentricFlowResponse updated)

---

### Fix A — Canonical `analysis_status` Value Audit (GAP-7)

**Problem:** P3.6 uses `"completed"` and P3.9.1 uses `"complete"` — one is wrong and will silently return 0 components.

**Action:**
```bash
# 1. Check the actual values in your DB right now:
psql $DATABASE_URL -c "
SELECT DISTINCT analysis_status, COUNT(*)
FROM code_components
GROUP BY analysis_status
ORDER BY count DESC;
"
```

**If result shows `"completed"` (with 'd'):**
- Keep P3.6 as-is (`analysis_status == "completed"`)
- Fix P3.9.1 endpoint: change `analysis_status == "complete"` → `"completed"`
- Fix P3.5 hook: verify it uses the same value

**If result shows `"complete"` (without 'd'):**
- Keep P3.9.1 as-is (`analysis_status == "complete"`)
- Fix P3.6 task: change `analysis_status == "completed"` → `"complete"`

**Whichever value is correct — standardize it as a module-level constant:**

```python
# Add to backend/app/models/code_component.py or backend/app/constants.py
ANALYSIS_STATUS_COMPLETE = "completed"   # or "complete" — pick ONE based on audit above

# Then use it everywhere:
# P3.5 hook:
if component.analysis_status == ANALYSIS_STATUS_COMPLETE:
# P3.6 task:
CodeComponent.analysis_status == ANALYSIS_STATUS_COMPLETE,
# P3.9.1 endpoint:
CodeComponent.analysis_status == ANALYSIS_STATUS_COMPLETE,
```

> **This is a 5-minute fix with potentially massive impact** — if the wrong value is used, Tech Lead's backfill triggers on 0 components silently. Always audit before assuming.

---

### Fix B — Order Edges by `step_index` in CRUD Queries (GAP-9)

**Problem:** `render_mermaid()` processes edges in DB insertion order. Edges should flow logically (step 1 → step 2 → step 3).

**File:** `backend/app/crud/crud_code_data_flow_edge.py`

Add `ORDER BY step_index ASC NULLS LAST` to all edge query methods:

```python
def get_by_source(
    self, db: Session, *, component_id: int, tenant_id: int
) -> list[CodeDataFlowEdge]:
    return (
        db.query(CodeDataFlowEdge)
        .filter(
            CodeDataFlowEdge.source_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        )
        .order_by(CodeDataFlowEdge.step_index.asc().nullslast())  # ← ADD
        .all()
    )

def get_by_target(
    self, db: Session, *, component_id: int, tenant_id: int
) -> list[CodeDataFlowEdge]:
    return (
        db.query(CodeDataFlowEdge)
        .filter(
            CodeDataFlowEdge.target_component_id == component_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        )
        .order_by(CodeDataFlowEdge.step_index.asc().nullslast())  # ← ADD
        .all()
    )

def get_by_repository(
    self, db: Session, *, repository_id: int, tenant_id: int
) -> list[CodeDataFlowEdge]:
    return (
        db.query(CodeDataFlowEdge)
        .filter(
            CodeDataFlowEdge.repository_id == repository_id,
            CodeDataFlowEdge.tenant_id == tenant_id,
        )
        .order_by(
            CodeDataFlowEdge.source_component_id,
            CodeDataFlowEdge.step_index.asc().nullslast()   # ← ADD
        )
        .all()
    )
```

Also sort in `render_mermaid()` as a safety net (in case edges arrive from non-CRUD sources):

```python
def render_mermaid(self, nodes: list[dict], edges: list, mode: str = "technical") -> str:
    lines = ["flowchart LR"]

    # Sort edges by step_index (None values go last)
    sorted_edges = sorted(
        edges,
        key=lambda e: (
            getattr(e, "step_index", None) if hasattr(e, "step_index")
            else e.get("step_index"),
        ) or 9999
    )
    # ... rest of method uses sorted_edges instead of edges
```

---

### Fix C — "Not Built Yet" vs "Genuinely 0 Edges" Distinction (GAP-10)

**File:** `backend/app/schemas/code_component.py`

`edges_built_at` was added to `EgocentricFlowResponse` in P3.14. Also add it to `RequestTraceResponse`:

```python
class RequestTraceResponse(BaseModel):
    start_component_id: int
    depth: int
    nodes: list[DataFlowNodeSchema]
    edges: list[DataFlowEdgeSchema]
    mermaid_technical: str
    mermaid_simple: str
    total_nodes: int
    total_edges: int
    edges_built_at: Optional[datetime] = None  # ← ADD

    model_config = ConfigDict(from_attributes=True)
```

**File:** `backend/app/api/endpoints/code_components.py`

In the request-trace endpoint, query and include `edges_built_at`:

```python
@router.get("/{id}/request-trace", response_model=RequestTraceResponse)
def get_request_trace(id: int, depth: int = Query(default=5, ge=1, le=8), ...):
    # ... existing BFS trace logic ...

    # Add edges_built_at
    from sqlalchemy import func as sql_func
    from app.models.code_data_flow_edge import CodeDataFlowEdge as EdgeModel
    edges_built_at_row = db.query(sql_func.max(EdgeModel.created_at)).filter(
        EdgeModel.source_component_id == id,
        EdgeModel.tenant_id == current_user.tenant_id,
    ).scalar()

    return RequestTraceResponse(
        start_component_id=id,
        depth=depth,
        nodes=trace["nodes"],
        edges=trace["edges"],
        mermaid_technical=trace["mermaid_technical"],
        mermaid_simple=trace["mermaid_simple"],
        total_nodes=len(trace["nodes"]),
        total_edges=len(trace["edges"]),
        edges_built_at=edges_built_at_row,   # ← ADD
    )
```

**File:** `frontend/components/data-flow/DataFlowDiagram.tsx`

Use `edges_built_at` to show the correct empty state message:

```tsx
// In the empty state section (where total_edges === 0):
// BEFORE (same message for both states):
<div className="h-48 flex items-center justify-center rounded-xl border border-dashed bg-gray-50">
  <div className="text-center space-y-2">
    <GitBranch className="h-8 w-8 text-gray-300 mx-auto" />
    <p className="text-sm text-gray-400">No flow data yet</p>
    <button onClick={handleRebuild} ...>Click to build diagram</button>
  </div>
</div>

// AFTER (differentiated messages):
const wasBuilt = !!data?.edges_built_at;
const hasEdges = (data?.total_edges ?? 0) > 0;

// Empty state:
{!hasEdges && (
  <div className="h-48 flex items-center justify-center rounded-xl border border-dashed bg-gray-50">
    <div className="text-center space-y-2">
      <GitBranch className="h-8 w-8 text-gray-300 mx-auto" />
      {wasBuilt ? (
        // Was built but has 0 edges — this file genuinely has no tracked connections
        <>
          <p className="text-sm text-gray-400">No connections found</p>
          <p className="text-xs text-gray-400">
            This file makes no trackable outbound calls.
            <br />
            <span className="text-gray-300">
              Last checked: {new Date(data.edges_built_at).toLocaleDateString()}
            </span>
          </p>
        </>
      ) : (
        // Never built — offer to build
        <>
          <p className="text-sm text-gray-400">Diagram not generated yet</p>
          <button onClick={handleRebuild}
            className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline">
            Generate data flow diagram
          </button>
        </>
      )}
    </div>
  </div>
)}
```

---

### Fix D — Add `created_at` to `DataFlowEdgeSchema` (GAP-13)

**File:** `backend/app/schemas/code_component.py`

```python
class DataFlowEdgeSchema(BaseModel):
    id: Optional[int] = None
    source_component_id: int
    target_component_id: Optional[int] = None
    edge_type: str
    source_function: Optional[str] = None
    target_function: Optional[str] = None
    data_in_description: Optional[str] = None
    data_out_description: Optional[str] = None
    human_label: Optional[str] = None
    external_target_name: Optional[str] = None
    step_index: Optional[int] = None
    created_at: Optional[datetime] = None      # ← ADD (allows "last built X ago" display)

    model_config = ConfigDict(from_attributes=True)
```

---

### Fix E — Align Backfill Auth Check (GAP-12)

**Problem:** Two different auth checks for the same concept of "admin or repo owner":
- P3.9.1: `current_user.role not in ("admin", "owner")`
- P3.7 stub: `repo.owner_id != current_user.id` (no admin check)

**Action:** Standardize to one helper function:

```python
# Add to backend/app/api/deps.py or backend/app/api/endpoints/repositories.py:

def _assert_repo_admin(repo, current_user) -> None:
    """
    Raise 403 unless the current user is:
    - The repository owner, OR
    - A tenant admin (role = "admin")
    
    Audit the actual User.role values in your system and update the
    admin_roles set below to match.
    """
    _ADMIN_ROLES = {"admin"}   # add "owner" if that's a valid role value in your system
    is_owner = repo.owner_id == current_user.id
    is_admin = current_user.role in _ADMIN_ROLES
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=403,
            detail="Must be repository owner or tenant admin",
        )

# Use in both backfill endpoints (P3.9.1 and P3.7 stub):
_assert_repo_admin(repo, current_user)
```

---

### Fix F — "Last Built" Timestamp in UI (GAP-13)

**File:** `frontend/components/data-flow/DataFlowDiagram.tsx`

Add "Last built" display in the stats bar (the gray bar above the diagram):

```tsx
// In the stats bar section (already in P3.8):
<div className="flex items-center gap-4 px-4 py-2 border-b bg-gray-50 text-xs text-gray-500">
  <span><b className="text-gray-700">{data.total_nodes ?? 1}</b> components</span>
  <span><b className="text-gray-700">{data.total_edges ?? 0}</b> connections</span>
  {flowView === "trace" && (
    <span><b className="text-gray-700">{data.depth}</b> levels deep</span>
  )}
  {/* ADD: Last built timestamp */}
  {data.edges_built_at && (
    <span className="text-gray-400">
      Built {formatRelativeTime(data.edges_built_at)}
    </span>
  )}
  <span className="ml-auto text-gray-400 italic">Click any node to navigate →</span>
</div>
```

Add the `formatRelativeTime` helper (or use `date-fns`):
```tsx
function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

---

### P3.15 Verification Commands

```bash
# A — Canonical analysis_status:
psql $DATABASE_URL -c "SELECT DISTINCT analysis_status FROM code_components"
# Record the value, update ANALYSIS_STATUS_COMPLETE constant

# B — step_index ordering:
psql $DATABASE_URL -c "
SELECT id, edge_type, step_index
FROM code_data_flow_edges
WHERE source_component_id = {ID}
ORDER BY step_index ASC NULLS LAST;
"
# Verify edges returned in logical step order

# C — edges_built_at in API response:
curl -H "Authorization: Bearer $TOKEN" \
  .../code-components/{ID}/data-flow | jq '.edges_built_at'
# Expect: ISO timestamp string OR null (never built)

# D — created_at in edge schema:
curl -H "Authorization: Bearer $TOKEN" \
  .../code-components/{ID}/data-flow | jq '.edges_out[0].created_at'
# Expect: ISO timestamp string
```

---

### P3.15 Developer Checklist

**Backend Dev 1:**
- [ ] **Fix A** — Run SQL audit, determine canonical `analysis_status` value, add `ANALYSIS_STATUS_COMPLETE` constant, update P3.6 task + P3.9.1 endpoint + P3.5 hook to use it
- [ ] **Fix B** — Add `ORDER BY step_index ASC NULLS LAST` to `get_by_source()`, `get_by_target()`, `get_by_repository()` in CRUD
- [ ] **Fix E** — Create `_assert_repo_admin()` helper, replace inline auth checks in both backfill endpoints

**Backend Dev 2:**
- [ ] **Fix B** — Add edge sort by step_index in `render_mermaid()` (safety net)
- [ ] **Fix C** — Add `edges_built_at` field to `RequestTraceResponse` schema and populate in request-trace endpoint
- [ ] **Fix D** — Add `created_at: Optional[datetime]` to `DataFlowEdgeSchema`

**Frontend Dev:**
- [ ] **Fix C** — Differentiate "never built" vs "genuinely 0 edges" empty states using `edges_built_at`
- [ ] **Fix F** — Add "Built X ago" display in the diagram stats bar

---

## Phase 3 Gap-Fix Summary (P3.10–P3.15)

| Task | Gaps Fixed | Files Modified |
|------|-----------|----------------|
| P3.10 | GAP-1 (Mermaid click) | `DataFlowDiagram.tsx`, `MermaidDiagram.tsx` |
| P3.11 | GAP-3 (CACHE/EVENT edges) | `data_flow_service.py` |
| P3.12 | GAP-5, GAP-8 (task polling, backfill progress) | `tasks.py` (new), `data_flow_tasks.py`, `DataFlowDiagram.tsx`, `BackfillProgressCard.tsx` (new) |
| P3.13 | GAP-2, GAP-6 (role, tier context) | `/auth/me` schema, `CurrentUser` type, `DataFlowDiagram.tsx`, `code/[id]/page.tsx` |
| P3.14 | GAP-4, GAP-11 (egocentric nodes, get_egocentric usage) | `code_components.py` endpoint, `crud_code_data_flow_edge.py`, `EgocentricFlowResponse` schema |
| P3.15 | GAP-7, GAP-9, GAP-10, GAP-12, GAP-13 | `constants.py`, CRUD queries, `RequestTraceResponse`, `DataFlowEdgeSchema`, `DataFlowDiagram.tsx` |

**Total new files from gap-fix tasks:**
- `backend/app/api/endpoints/tasks.py` (P3.12)
- `frontend/components/data-flow/BackfillProgressCard.tsx` (P3.12)

**Total modified files from gap-fix tasks:**
- `backend/app/services/data_flow_service.py` (P3.11, P3.15B)
- `backend/app/tasks/data_flow_tasks.py` (P3.12B)
- `backend/app/api/endpoints/code_components.py` (P3.14, P3.15C)
- `backend/app/api/endpoints/repositories.py` (P3.15E)
- `backend/app/api/api.py` (P3.12A — register tasks router)
- `backend/app/crud/crud_code_data_flow_edge.py` (P3.14, P3.15B)
- `backend/app/schemas/code_component.py` (P3.14, P3.15C, P3.15D)
- `backend/app/models/code_component.py` or `constants.py` (P3.15A)
- `frontend/components/data-flow/DataFlowDiagram.tsx` (P3.10, P3.12C, P3.13C, P3.15C, P3.15F)
- `frontend/components/ontology/MermaidDiagram.tsx` (P3.10B)
- `frontend/app/dashboard/code/[id]/page.tsx` (P3.13D)
- `frontend/lib/types/user.ts` (P3.13B)
- `backend/app/api/endpoints/auth.py` + user schema (P3.13A)

