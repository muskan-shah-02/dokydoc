# Phase 5B — User Journey: Validation Accuracy, Transparency & Enterprise Workflow

## Overview

Phase 5B adds 12 enterprise-grade capabilities to the Validation Panel. The journey follows a **Business Analyst (BA)** who uploads a BRD, runs validation, triages mismatches, and formally signs off on compliance.

---

## Act 1 — Re-uploading a BRD (P5B-01: Atom Diff)

### What the user does
The BA uploads a revised BRD (v2) for a document already validated in the system.

### Frontend
An **amber banner** appears at the top of the Validation Panel:
```
⚠ BRD Updated — 3 atoms added · 2 modified · 1 deleted   [×]
```
The banner is dismissable. It only appears when `last_atom_diff` on the document is non-null.

### Backend — `AtomDiffService` (`atom_diff_service.py`)
1. Loads all prior `RequirementAtom` rows for the document.
2. For each new atom from Gemini atomization:
   - **Exact SHA-256 hash match** → status = `unchanged` (skip re-validation, saving ~40-60% Gemini cost)
   - **Same atom_type + Levenshtein similarity ≥ 0.75** → status = `modified`
   - **No match** → status = `added`
3. Prior atoms with no new counterpart → `deleted` (their open mismatches are auto-closed).
4. Diff summary stored on `documents.last_atom_diff` (JSONB).

### Database — Migration `s16a1`
| Table | New Columns |
|---|---|
| `requirement_atoms` | `content_hash VARCHAR(64)`, `previous_atom_id INT` (self-FK), `delta_status VARCHAR(20)`, `regulatory_tags TEXT[]` |
| `documents` | `last_atom_diff JSONB` |

Indexes: `ix_requirement_atoms_content_hash`, `ix_requirement_atoms_delta_status`, `ix_requirement_atoms_regulatory_tags` (GIN).

---

## Act 2 — Viewing the Compliance Score (P5B-02)

### What the user does
The BA opens the Validation Panel for a document. At the top, a **score card** shows the overall compliance health.

### Frontend
```
┌─────────────────────────────────────┐
│  Compliance Score       [B] 87%     │
│  ─────────────────────────────────  │
│  Security Requirements  ██████░  3× │
│  Business Rules         ████░░░  2× │
│  API Contracts          ███████  2× │
│  Functional Req         █████░░  1× │
└─────────────────────────────────────┘
```
Grade badges: **A** (≥95%) · **B** (≥85%) · **C** (≥75%) · **D** (≥60%) · **F** (<60%).  
Per-type progress bars show weight multipliers (3×, 2×, 1×) so the BA understands why one category dominates the score.

### Backend — `GET /{document_id}/compliance-score`
- Calls `crud.mismatch.get_compliance_breakdown()` which applies weighted scoring:
  - `SECURITY_REQUIREMENT` = 3× weight
  - `BUSINESS_RULE` = 2×, `API_CONTRACT` = 2×
  - All others = 1×
- Returns `overall_score`, `percentage`, `grade`, and per-type breakdown.

---

## Act 3 — Triaging a Mismatch (P5B-10: Status Lifecycle)

### What the user does
The BA sees a list of mismatches. Each has a **clickable status badge** showing valid next states.

### Frontend — Status Dropdown
```
[open ▾]  →  in_progress
              resolved
              false_positive
```
Valid transitions enforced in UI via `VALID_TRANSITIONS` map:
- `open` → `in_progress`, `resolved`, `false_positive`
- `in_progress` → `resolved`, `false_positive`
- `resolved` → `verified`
- `verified` → (terminal)
- `false_positive` → `disputed`

### Backend — `PATCH /mismatches/{id}/status`
- Validates transition server-side (returns HTTP 400 on illegal move).
- Records `status_changed_by_id` (FK to users) and `status_changed_at` timestamp.
- Optional `note` stored in `resolution_note`.

### Database — Migration `s16b1`
| Table | New Columns |
|---|---|
| `mismatches` | `resolution_note TEXT`, `status_changed_by_id INT` (FK→users), `status_changed_at DATETIME` |

Data migration: existing `status='new'` rows updated to `status='open'`.

---

## Act 4 — Investigating Evidence (P5B-05)

### What the user does
The BA clicks **"Show Evidence"** on a mismatch to see exactly *why* the AI flagged it.

### Frontend — Expandable Evidence Panel
```
▼ Show Evidence
  BRD Requirement
  ─────────────────────────────────────────────────
  "The system shall encrypt all PII data at rest..."
  [SECURITY_REQUIREMENT]  Tags: GDPR, PCI-DSS

  Code Analyzed
  ─────────────────────────────────────────────────
  user_service.py → save_user()
  ┌─────────────────────────────────────────┐
  │  db.save(user_data)  # no encryption   │
  └─────────────────────────────────────────┘

  AI Reasoning
  ─────────────────────────────────────────────────
  Confidence: High · "No AES/RSA call found..."
```

### Backend — `GET /mismatches/{id}/evidence`
Returns three structured blocks:
1. `brd_requirement` — atom content, type, regulatory_tags from `details` JSONB
2. `code_analyzed` — code snapshot, component name
3. `ai_conclusion` — mismatch_type, description, severity, confidence, evidence text, confidence_reasoning

### How Gemini populates this (P5B-09)
Gemini validation prompt now requests **8-12 specific checks per atom type** for all 9 atom types, and outputs:
```json
{
  "evidence": "No encryption call found in save_user()",
  "confidence_reasoning": "AES/RSA/Fernet absent from entire module"
}
```
Both fields stored in `mismatch.details` JSONB.

---

## Act 5 — Regulatory Tagging (P5B-08)

### What the user does
The BA notices some atoms are tagged `[GDPR]` `[PCI-DSS]`. These map to elevated severity automatically.

### Backend — Atomization Extension
Gemini atomization prompt now asks for `regulatory_tags` per atom:
```json
{
  "atom_type": "SECURITY_REQUIREMENT",
  "content": "Encrypt PII at rest",
  "regulatory_tags": ["GDPR", "PCI-DSS"]
}
```
When a tagged security atom has a mismatch, severity is automatically elevated to `compliance_risk`.

### Database
`regulatory_tags TEXT[]` column on `requirement_atoms` with a **GIN index** for efficient array containment queries (`@>` operator).

---

## Act 6 — Marking a False Positive (P5B-04)

### What the user does
The BA disagrees with a mismatch — clicks **"Not Real"** and submits a reason.

### Frontend — False Positive Modal
```
┌─────────────────────────────────────────────────────┐
│  Mark as False Positive                             │
│                                                     │
│  Why is this not a real issue?                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ This check does not apply to read-only...   │   │
│  └─────────────────────────────────────────────┘   │
│  Minimum 10 characters required                     │
│                                [Cancel] [Confirm]   │
└─────────────────────────────────────────────────────┘
```
The "Not Real" button only appears on mismatches that are NOT already `false_positive`.

### Backend — `POST /mismatches/{id}/false-positive`
- Validates reason ≥ 10 chars (HTTP 400 otherwise).
- Sets `status = 'false_positive'`, stores reason in `resolution_note`.
- Creates a `TrainingExample` record to feed the AI data flywheel.

If another team member disagrees: `POST /mismatches/{id}/dispute` → status = `disputed`.

---

## Act 7 — Pushing to Jira (P5B-03)

### What the user does
For unresolved critical mismatches, the BA clicks a **"Create Jira Issue"** button. A ticket is created in the team's Jira project.

### Backend — `POST /integrations/jira/create-issue`
- Uses Atlassian REST API v3 with ADF body format.
- Maps DokuDoc severity to Jira priority: `critical` → `Highest`, `warning` → `Medium`, `info` → `Low`.
- Idempotent: if `mismatch.jira_issue_key` already set, returns existing key without duplicate creation.
- Stores `jira_issue_key` and `jira_issue_url` on the mismatch record.

### Database — Migration `s16b1`
| Column | Type | Purpose |
|---|---|---|
| `jira_issue_key` | VARCHAR(50) | e.g. `PROJ-142` |
| `jira_issue_url` | VARCHAR(500) | deep link to Jira |

---

## Act 8 — Auto Re-validation (P5B-06)

### What the user does
The developer pushes a code fix. The BA doesn't need to manually re-trigger validation.

### Backend — Celery Task
A Celery task fires **30 seconds after** a code component is re-analyzed:
1. Finds all mismatches linked to that component with status `open` or `in_progress`.
2. Marks them `in_progress` (signals re-check is pending).
3. Triggers a focused re-validation only for atoms linked to those mismatches.

This keeps the mismatch list fresh without the BA needing to click "Run Scan" again.

---

## Act 9 — Coverage Matrix (P5B-07)

### What the user does
The BA switches to the **"Coverage Matrix"** tab (4th tab in the Validation Panel) to see which BRD atoms are covered by which code components.

### Frontend — Matrix Grid
```
              auth.py   user_svc.py   payment.py
─────────────────────────────────────────────────
Encrypt PII     ✓           ✗             ~
Login Flow      ✓           ✓             ·
Payment Limit   ·           ·             ✓
```
Legend: `✓` covered · `~` partial (open mismatches) · `✗` missing (critical) · `·` not linked.

Summary pills show total covered / partial / missing cells.

### Backend — `GET /{document_id}/coverage-matrix`
Returns:
```json
{
  "atoms": [{ "id": 1, "atom_type": "SECURITY_REQUIREMENT", "content": "..." }],
  "components": [{ "id": 10, "name": "auth.py" }],
  "matrix": {
    "1::10": { "coverage_score": 1.0, "open_mismatches": 0, "status": "covered" },
    "1::11": { "coverage_score": 0.0, "open_mismatches": 2, "status": "missing" }
  },
  "summary": { "covered": 4, "partial": 1, "missing": 2, "total_cells": 9 }
}
```

---

## Act 10 — Version-Linked Mismatches (P5B-11)

### What the user does
The BA hovers on a mismatch to see **when it was created** (which BRD version, which git commit).

### Backend — `GET /mismatches/{id}/version-info`
Returns:
```json
{
  "document_version": { "version_number": "v2.1", "uploaded_at": "2026-04-10" },
  "created_commit": "a3f9c12...",
  "resolved_commit": null
}
```

### Database — Migration `s16b1`
| Column | Type |
|---|---|
| `document_version_id` | INT FK → `document_versions.id` |
| `created_commit_hash` | VARCHAR(40) |
| `resolved_commit_hash` | VARCHAR(40) |

---

## Act 11 — BA Sign-Off & Compliance Certificate (P5B-12)

### What the user does
After reviewing all mismatches, the BA clicks **"Generate Certificate"** to formally sign off.

### Frontend — Sign-Off Panel
```
┌──────────────────────────────────────────────────┐
│  BA Sign-Off                                     │
│                                                  │
│  Notes (optional)                                │
│  ┌────────────────────────────────────────────┐  │
│  │ Reviewed all critical items. PCI-DSS...    │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  Compliance Snapshot                             │
│  Score: 87% · Open: 2 · Critical: 0             │
│                                                  │
│  [Generate Certificate]                          │
│                                                  │
│  Certificate ID: DOKYDOC-000001                  │
│  Hash: a3f9c12d8b...                             │
└──────────────────────────────────────────────────┘
```

### Backend — `POST /{document_id}/sign-off`
1. Checks for unresolved critical mismatches.
2. Blocks sign-off unless each critical mismatch is in `acknowledged_mismatch_ids` OR `confirm_acknowledged_criticals=true`.
3. Creates a `BRDSignOff` record capturing a compliance snapshot.
4. Generates a **SHA-256 `certificate_hash`** from:
   - sign_off id, tenant_id, document_id, signed_by_user_id, signed_at, compliance_score, open_count, critical_count, acknowledged_ids
5. Returns certificate reference: `DOKYDOC-000001`.

### Database — Migration `s16f1`
```sql
CREATE TABLE brd_sign_offs (
  id                          SERIAL PRIMARY KEY,
  tenant_id                   INT NOT NULL,
  document_id                 INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  document_version_id         INT REFERENCES document_versions(id) ON DELETE SET NULL,
  repository_id               INT REFERENCES repositories(id) ON DELETE SET NULL,
  signed_by_user_id           INT NOT NULL REFERENCES users(id),
  signed_at                   TIMESTAMP NOT NULL,
  compliance_score_at_signoff FLOAT,
  open_mismatches_count       INT DEFAULT 0,
  critical_mismatches_count   INT DEFAULT 0,
  acknowledged_mismatch_ids   JSONB,
  sign_off_notes              TEXT,
  has_unresolved_critical     BOOLEAN DEFAULT FALSE,
  certificate_hash            VARCHAR(64),
  created_at                  TIMESTAMP NOT NULL
);
```

Sign-off history viewable at `GET /{document_id}/sign-off-history`.

---

## Complete Data Flow Diagram

```
User uploads BRD (v2)
        │
        ▼
  AtomDiffService.compute_diff()
  ├── SHA-256 hash match → UNCHANGED (skip Gemini)
  ├── Levenshtein ≥0.75 → MODIFIED
  └── No match → ADDED
        │
        ▼
  Gemini Atomization (P5B-08/09)
  └── Extracts regulatory_tags per atom
  └── 8-12 specific checks per atom type
        │
        ▼
  Gemini Validation → Mismatches created
  └── evidence + confidence_reasoning stored in details JSONB
  └── document_version_id + created_commit_hash stamped
        │
        ▼
  Validation Panel renders:
  ├── Amber diff banner (if re-upload)
  ├── Compliance score card (weighted, A-F grade)
  ├── Mismatch list with:
  │   ├── Status dropdown (lifecycle transitions)
  │   ├── "Show Evidence" expandable panel
  │   ├── "Not Real" button → false positive modal
  │   └── Regulatory tags ([GDPR], [PCI-DSS])
  ├── Coverage Matrix tab (atoms × components grid)
  └── Sign-Off panel → Certificate hash
        │
        ▼
  Celery auto re-validation (30s after code change)
  └── Affected mismatches → in_progress
  └── Focused re-scan → mismatches updated
```

---

## API Endpoints Added (Phase 5B)

| Method | Path | Ticket | Purpose |
|---|---|---|---|
| `GET` | `/{doc_id}/compliance-score` | P5B-02 | Weighted score + grade |
| `POST` | `/mismatches/{id}/false-positive` | P5B-04 | Mark false positive |
| `POST` | `/mismatches/{id}/dispute` | P5B-04 | Dispute a false positive |
| `GET` | `/mismatches/{id}/evidence` | P5B-05 | BRD+code+AI evidence |
| `GET` | `/{doc_id}/coverage-matrix` | P5B-07 | Atoms × components grid |
| `PATCH` | `/mismatches/{id}/status` | P5B-10 | Lifecycle transition |
| `GET` | `/mismatches/{id}/version-info` | P5B-11 | BRD version + git commit |
| `POST` | `/{doc_id}/sign-off` | P5B-12 | BA sign-off + certificate |
| `GET` | `/{doc_id}/certificate` | P5B-12 | Fetch certificate |
| `GET` | `/{doc_id}/sign-off-history` | P5B-12 | All sign-offs for doc |
| `POST` | `/integrations/jira/create-issue` | P5B-03 | Push mismatch to Jira |

---

## Database Migrations Summary

| Migration | Ticket(s) | Key Changes |
|---|---|---|
| `s16a1` | P5B-01, P5B-08 | `content_hash`, `delta_status`, `previous_atom_id`, `regulatory_tags` on `requirement_atoms`; `last_atom_diff` on `documents` |
| `s16b1` | P5B-03, P5B-04, P5B-10, P5B-11 | `resolution_note`, `status_changed_by_id/at`, `jira_issue_key/url`, `document_version_id`, `created/resolved_commit_hash` on `mismatches`; status `'new'→'open'` data migration |
| `s16f1` | P5B-12 | `brd_sign_offs` table with `certificate_hash` |
