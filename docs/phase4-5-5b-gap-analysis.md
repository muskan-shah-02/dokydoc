# Phase 4 / 5 / 5B — Architectural Gap Analysis
> Solution Architect review · Branch: `claude/review-codebase-6g1Dg` · Date: 2026-04-16

## Severity Legend
🔴 Critical — blocks functionality or is a security/data-loss issue  
🟠 High — causes incorrect behaviour under normal use  
🟡 Medium — degrades UX or performance under load  
🔵 Low — tech debt or future risk

---

## BACKEND GAPS

### ARC-BE-01 🟠 — Coverage Matrix: O(N²) linear scan inside double loop
**File:** `backend/app/api/endpoints/validation.py:494`

```python
link_exists = any(l.code_component_id == comp.id for l in links)
```
This runs inside `for atom in atoms: for comp in components:` — an O(atoms × components) loop calling `any()` over `links` each iteration. With 50 atoms × 20 components × 20 links = **20 000 comparisons per request**.

**Fix:** Build a `linked_component_ids = {l.code_component_id for l in links}` set before the loop and replace `any(...)` with `comp.id in linked_component_ids`.

---

### ARC-BE-02 🟠 — Sign-off history response missing `certificate_id` field
**File:** `backend/app/api/endpoints/validation.py:786–804`

The `GET /{doc_id}/sign-off-history` response serialises each record but **omits `certificate_id`**:
```python
# history response has: id, signed_at, certificate_hash ...
# MISSING:             certificate_id = f"DOKYDOC-{s.id:06d}"
```
The frontend (`validation-panel/page.tsx:1679`) renders `signOffHistory[0].certificate_id ?? "—"` — this will always show `"—"` because the field is never returned.

**Fix:** Add `"certificate_id": f"DOKYDOC-{s.id:06d}"` to the history serialiser.

---

### ARC-BE-03 🟠 — `confidence` stored as String, compared as Float
**File:** `backend/app/models/mismatch.py:35`, `gemini.py:845`

Gemini returns `"confidence": "High"` (string). The `Mismatch.confidence` column is `String`. But `BOEContext._calibrate_confidence` and the compliance score card perform numeric comparisons (`>= 0.92`). These two usages are permanently mismatched — the model stores `"High"` but the BOE code expects `0.95`.

**Fix:** Either (a) store confidence as `Float` and convert Gemini's `High/Medium/Low` to `0.9/0.6/0.3` at ingestion time, or (b) add an explicit `HIGH_MAP = {"High": 0.9, "Medium": 0.6, "Low": 0.3}` wherever numeric comparison happens.

---

### ARC-BE-04 🟡 — `GET /validation/report/{initiative_id}` hard-caps at 500 mismatches
**File:** `backend/app/api/endpoints/validation.py:234`

```python
mismatches = crud.mismatch.get_multi_by_owner(..., skip=0, limit=500)
```
A tenant with >500 mismatches silently produces an incomplete compliance report with no indication of truncation. This affects the `requirement_coverage` calculation.

**Fix:** Either paginate the export or add `"truncated": len(mismatches) == 500` to the response body.

---

### ARC-BE-05 🟡 — Missing composite DB index on `(tenant_id, document_id, status)`
**File:** `backend/app/models/mismatch.py` — `__table_args__` absent

The hot query path (`get_multi_by_owner`, coverage matrix, compliance score, sign-off) all filter on `tenant_id + document_id + status`. Each column has a single-column index but no composite index. At scale (100K mismatches) these queries will require three separate index scans instead of one.

**Fix:** Add to `Mismatch` model:
```python
__table_args__ = (
    Index("ix_mismatches_tenant_doc_status", "tenant_id", "document_id", "status"),
)
```
Add in a new migration.

---

### ARC-BE-06 🟡 — `get_compliance_breakdown` fetches atoms with unbounded `.all()`
**File:** `backend/app/crud/crud_mismatch.py` (compliance breakdown method)

All `RequirementAtom` rows for a document are loaded with no LIMIT to compute weighted scores. For a large BRD atomized into 200+ atoms this materialises hundreds of ORM objects unnecessarily. The count and type breakdown can be computed with a single `GROUP BY` aggregate query.

**Fix:** Replace the atom fetch with a SQL aggregate:
```sql
SELECT atom_type, COUNT(*) FROM requirement_atoms
WHERE document_id=:doc_id AND tenant_id=:tid GROUP BY atom_type
```

---

### ARC-BE-07 🔵 — `atom_diff_service.py` uses content prefix as dedup key (collision risk)
**File:** `backend/app/services/validation_service.py:293–295`

```python
key = delta.new_atom_content[:80]
```
Two atoms with identical first 80 characters but different tails will be treated as the same atom. While rare in practice, requirements like `"The system shall validate all user inputs for SQL injection in module A"` and `"...module B"` would collide.

**Fix:** Use `delta.content_hash` (already computed SHA-256) as the dedup key instead of the content prefix.

---

### ARC-BE-08 🔵 — `detect_tenant_industry` fires but nothing triggers it post-registration
**File:** `backend/app/tasks/tenant_tasks.py:56`

The Celery task exists and works, but there is no call-site that dispatches it when a new tenant registers and provides `company_website`. The trigger must exist in the tenant registration endpoint or a post-create hook — if it's missing there, the task never fires.

**Action:** Verify `POST /tenants` (or equivalent registration flow) calls `detect_tenant_industry.delay(tenant_id, website_url)` when `company_website` is provided.

---

## FRONTEND GAPS

### ARC-FE-01 🟠 — `fetchEvidence` silently swallows errors (empty catch blocks)
**File:** `frontend/app/dashboard/validation-panel/page.tsx:334, 349, 363, 379`

Multiple fetch handlers catch exceptions and do nothing:
```typescript
} catch {}   // evidence, coverage, atom diff, compliance
```
When the API is down or returns 4xx, the panel shows nothing — no toast, no inline error, no retry prompt. The user sees a spinner or blank area with no explanation.

**Fix:** Replace silent `catch {}` with `catch (e) { console.error(e); /* show inline error state */ }` or a shared `notifyError()` call.

---

### ARC-FE-02 🟠 — Sign-off history `certificate_id` always renders `"—"`
**File:** `frontend/app/dashboard/validation-panel/page.tsx:1679`

```typescript
cert {signOffHistory[0].certificate_id ?? "—"}
```
The backend history endpoint doesn't return `certificate_id` (see ARC-BE-02). This field always evaluates to `undefined ?? "—"` = `"—"`. The history panel never shows the actual certificate reference.

**Fix:** Fixed by ARC-BE-02 backend change. No frontend change needed once backend returns the field.

---

### ARC-FE-03 🟡 — No optimistic UI for status dropdown transitions
**File:** `frontend/app/dashboard/validation-panel/page.tsx:420–440`

`handleStatusUpdate` sets `statusUpdating` (shows a spinner) then awaits the API. If the API takes 2–3s, the dropdown stays open with the old status. On failure, `setError()` is called but the dropdown badge doesn't revert — the UI shows the new status even though the server rejected it.

**Fix:** Capture the old status, apply the new one optimistically, then revert on error:
```typescript
const previousStatus = mismatch.status;
// update local state immediately
// on catch: restore previousStatus
```

---

### ARC-FE-04 🟡 — Coverage matrix tab has no loading state
**File:** `frontend/app/dashboard/validation-panel/page.tsx:357`

`fetchCoverageMatrix` sets `setCoverageMatrix(null)` before the fetch, but the tab render doesn't distinguish between `null (never loaded)` and `null (loading)`. The tab shows blank content with no spinner while the matrix loads.

**Fix:** Add a `coverageMatrixLoading: boolean` state, set to `true` before fetch and `false` after, and render a `<Loader2>` skeleton while loading.

---

### ARC-FE-05 🟡 — Poll loop in validation scan has no maximum retry count guard
**File:** `frontend/app/dashboard/validation-panel/page.tsx:550–588`

The `pollForResults` inner async loop polls every 3s. There is no maximum iteration count — if the backend scan hangs permanently, the poll loop runs forever until the user navigates away, leaking memory and causing unnecessary API calls.

**Fix:** Add `let attempts = 0; const MAX = 40;` and break the loop when `attempts++ > MAX`, then show a "Scan is taking longer than expected" message.

---

### ARC-FE-06 🔵 — `focusedDocId` compliance data not cleared on document switch
**File:** `frontend/app/dashboard/validation-panel/page.tsx:194–196`

When the user clicks a different document row, `focusedDocId` changes. `fetchComplianceData` is re-called, but `complianceData`, `atomDiffSummary`, and `coverageMatrix` are **not reset to `null`** before the new fetch completes. For 1–2 seconds the panel shows the previous document's score card under the new document's mismatch list.

**Fix:** At the start of any document-switch handler, reset all doc-scoped state:
```typescript
setComplianceData(null); setAtomDiffSummary(null); setCoverageMatrix(null);
```

---

## DATABASE GAPS

### ARC-DB-01 🟠 — `brd_sign_offs` has no unique constraint on concurrent sign-offs
**File:** `backend/alembic/versions/s16f1_brd_sign_offs.py`

Nothing prevents two BA users from both clicking "Generate Certificate" at the same time, creating two `BRDSignOff` rows for the same document at nearly identical timestamps. Each gets a different `certificate_hash`, leaving the audit trail ambiguous about which is canonical.

**Fix:** Add a partial unique index in a new migration:
```sql
CREATE UNIQUE INDEX uq_brd_sign_off_active
ON brd_sign_offs (document_id, tenant_id)
WHERE has_unresolved_critical = FALSE;
```
Or enforce via application-level `SELECT FOR UPDATE` before insert.

---

### ARC-DB-02 🟡 — Missing index on `mismatches.document_id`
**File:** `backend/app/models/mismatch.py:47`

`document_id` has a FK but **no explicit index**. The coverage matrix query, compliance score, and sign-off all filter by `document_id`. SQLAlchemy's `ForeignKey` does not automatically create an index in PostgreSQL.

**Fix:** Add `index=True` to the `document_id` column mapping, or add `op.create_index` in the next migration.

---

### ARC-DB-03 🟡 — `regulatory_tags` GIN index unused (no query uses `@>` operator)
**File:** `backend/alembic/versions/s16a1_atom_delta_fields.py:47–51`

The GIN index on `requirement_atoms.regulatory_tags` was created but no SQLAlchemy query currently filters by this array (only inserts and reads from `details` JSONB use it). When filtering queries are eventually added, developers unfamiliar with PostgreSQL will likely use `.in_()` or string `.contains()`, which bypasses the GIN index entirely.

**Fix (preventive):** Add a helper in `crud_requirement_atom.py`:
```python
from sqlalchemy.dialects.postgresql import array as pg_array
def get_by_regulatory_tag(self, db, tag: str, tenant_id: int):
    return db.query(RequirementAtom).filter(
        RequirementAtom.regulatory_tags.contains([tag]),  # uses GIN @>
        RequirementAtom.tenant_id == tenant_id,
    ).all()
```
And document that `.contains([tag])` is the only GIN-compatible operator.

---

### ARC-DB-04 🔵 — `documents.last_atom_diff` JSONB never read by any endpoint
**File:** `backend/alembic/versions/s16a1_atom_delta_fields.py:54`

`last_atom_diff` is written by `validation_service.atomize_document()` but no API endpoint reads it. The frontend fetches diff data from a different path. Confirm the field is actually consumed; if not, the write is dead code creating unnecessary JSONB storage overhead.

---

## FRONTEND-BACKEND CONTRACT MISMATCHES

| # | Frontend expects | Backend returns | Endpoint |
|---|---|---|---|
| CM-01 | `certificate_id` in sign-off history | Field absent | `GET /{doc_id}/sign-off-history` |
| CM-02 | `confidence` as `"High"/"Medium"/"Low"` string | Same string (matches) | `GET /mismatches` |
| CM-03 | `signOffResult.message` field | Not in POST response | `POST /{doc_id}/sign-off` |
| CM-04 | Coverage matrix tab triggers on `focusedDocId` | Endpoint requires explicit doc select | UX only — no contract gap |

---

## Summary Table

| Gap ID | Layer | Severity | Description |
|---|---|---|---|
| ARC-BE-01 | Backend | 🟠 High | O(N²) `any()` scan inside coverage matrix double loop |
| ARC-BE-02 | Backend | 🟠 High | `certificate_id` missing from sign-off history response |
| ARC-BE-03 | Backend | 🟠 High | `confidence` stored as String but compared as Float in BOE |
| ARC-BE-04 | Backend | 🟡 Medium | Validation report hard-capped at 500 mismatches silently |
| ARC-BE-05 | Backend/DB | 🟡 Medium | Missing composite index `(tenant_id, document_id, status)` on mismatches |
| ARC-BE-06 | Backend | 🟡 Medium | Compliance breakdown fetches all atoms; should use SQL GROUP BY |
| ARC-BE-07 | Backend | 🔵 Low | Content prefix collision risk in atom dedup (use SHA-256 hash instead) |
| ARC-BE-08 | Backend | 🔵 Low | `detect_tenant_industry` task may not be dispatched at registration |
| ARC-FE-01 | Frontend | 🟠 High | Silent `catch {}` blocks hide all evidence/coverage/diff fetch errors |
| ARC-FE-02 | Frontend | 🟠 High | `certificate_id` always shows `"—"` in history panel (see CM-01) |
| ARC-FE-03 | Frontend | 🟡 Medium | Status dropdown shows wrong state on API error (no revert) |
| ARC-FE-04 | Frontend | 🟡 Medium | Coverage matrix tab has no loading skeleton |
| ARC-FE-05 | Frontend | 🟡 Medium | Poll loop has no maximum iteration guard — can run forever |
| ARC-FE-06 | Frontend | 🔵 Low | Stale compliance data shown for ~2s after document switch |
| ARC-DB-01 | DB | 🟠 High | No unique constraint prevents duplicate sign-offs for same document |
| ARC-DB-02 | DB | 🟡 Medium | `mismatches.document_id` FK has no index |
| ARC-DB-03 | DB | 🟡 Medium | GIN index on `regulatory_tags` will be bypassed when queries are added |
| ARC-DB-04 | DB | 🔵 Low | `documents.last_atom_diff` written but never read by any endpoint |

---

## Priority Order for Phase 5C Pre-flight

Fix these before Phase 5C development begins:

1. **ARC-BE-02 + ARC-FE-02** (certificate_id contract) — 10-min backend fix, zero risk
2. **ARC-BE-01** (O(N²) coverage matrix) — 5-min set-based fix, big perf gain
3. **ARC-FE-01** (silent catch blocks) — protects all P5B evidence features from silent failures
4. **ARC-DB-01** (duplicate sign-offs) — add partial unique index, required for audit integrity
5. **ARC-DB-02** (missing document_id index) — one-line migration, prevents full table scans
6. **ARC-BE-03** (confidence type mismatch) — needs data migration, plan carefully
7. **ARC-FE-05** (poll loop runaway) — easy guard, prevents memory leaks in long sessions
