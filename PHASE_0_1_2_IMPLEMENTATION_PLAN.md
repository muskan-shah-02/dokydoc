# DokyDoc — Phase 0, 1 & 2: Developer Implementation Plan
# Solution Architect Edition — Every file, every line, every step

---

## HOW TO READ THIS PLAN

Each task has:
- **Ticket ID** — reference in your sprint board (e.g. P0-01)
- **File** — exact file path relative to repo root
- **Lines** — exact lines to change (read the file first, verify before editing)
- **Why** — root cause / business reason
- **What to do** — step-by-step with exact code
- **Test** — how to verify it works
- **Risk** — what can break if done wrong

**Rules for all developers:**
1. Never edit a file without reading it first
2. Every DB change needs an Alembic migration — never `ALTER TABLE` by hand
3. Wrap new code in try/except where noted — these are non-breaking additions
4. Run `alembic upgrade head` after every migration before testing
5. All new endpoints need a tenant_id check — no exceptions

---

# PHASE 0 — Critical Bugs, Security & Performance Baseline

**Goal:** Fix everything that will silently hurt us under load or during a security audit.
**Can be parallelized:** P0-01 through P0-06 have zero dependencies on each other.
**Sprint estimate:** 3–4 days for 2 developers working in parallel.

---

## P0-01 — Remove 50MB Hard Upload Limit

**Ticket:** P0-01
**Priority:** P0 (blocks enterprise customers with large BRDs)
**File:** `backend/app/core/config.py`
**Lines:** 90–92

### Current code (line 90):
```python
MAX_FILE_SIZE: int = Field(default=50 * 1024 * 1024, env="MAX_FILE_SIZE")  # 50MB
```

### Why this is wrong:
Enterprise BRDs, SRS documents, and code archives can be 200MB+. The 50MB limit was
a placeholder that never got removed. We should warn, not block.

### What to change:

**Step 1 — Raise the config default to 2GB:**
In `backend/app/core/config.py`, line 90, change to:
```python
MAX_FILE_SIZE: int = Field(default=2 * 1024 * 1024 * 1024, env="MAX_FILE_SIZE")  # 2GB default, no hard cap
```

**Step 2 — Find upload endpoint and remove hard rejection:**
Read `backend/app/api/endpoints/documents.py`. Search for any `MAX_FILE_SIZE` check
that raises an HTTP 413 error. Replace rejection with a soft warning in the response:

```python
# BEFORE (remove this pattern wherever it appears):
if file.size > settings.MAX_FILE_SIZE:
    raise HTTPException(status_code=413, detail="File too large")

# AFTER (replace with soft warning):
file_size_warning = None
if file.size and file.size > 500 * 1024 * 1024:  # Warn above 500MB
    file_size_warning = f"Large file ({file.size // 1024 // 1024}MB) — analysis may take longer than usual"
```

Return `file_size_warning` in the upload response body so the frontend can display it.

**Step 3 — Update FastAPI max body size in main.py:**
Read `backend/main.py`. Find the line where `app = FastAPI(...)` is created.
After app creation, add:
```python
# Allow large uploads — no artificial cap
app.state.max_upload_size = None
```

Also check if there is any `uvicorn` config or `nginx` config in
`docker-compose.yml` or `nginx.conf` that has `client_max_body_size`. If found,
set to `client_max_body_size 0;` (nginx unlimited).

### Test:
```bash
# Create a 100MB dummy file and upload it — should succeed
dd if=/dev/zero of=/tmp/large_test.pdf bs=1M count=100
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/large_test.pdf" \
  -F "title=Large Test Doc"
# Expected: 200 OK with file_size_warning in response, NOT 413
```

### Risk: LOW — only removes a restriction, adds nothing new.

### Manual .env change required (production server):
The `.env` file is not committed to git. After deploying the code change, a developer
must manually update the production `.env`:

```bash
# On the production server, edit /home/user/dokydoc/backend/.env
# Change this line:
MAX_FILE_SIZE=52428800

# To this:
MAX_FILE_SIZE=2147483648

# Then restart the backend container to pick up the new value:
docker-compose restart backend
```

> **Current production state:** The production `.env` already has `MAX_FILE_SIZE=52428800`
> (50MB). Without this manual .env change, the code change alone will have no effect
> because `config.py` reads the env var at startup.

---

## P0-02 — Fix CORS Wildcard in Production

**Ticket:** P0-02
**Priority:** P0 (security — SOC2 blocker)
**File:** `backend/app/core/config.py`
**Lines:** 178–185

### Current code (lines 179–182):
```python
if settings.ENVIRONMENT == "production":
    settings.DEBUG = False
    settings.LOG_LEVEL = "WARNING"
    settings.CORS_ORIGINS = ["https://yourdomain.com"]  # Update with actual domain
```

### Why this is wrong:
`"https://yourdomain.com"` is a placeholder. In production, this either stays
wrong (blocks all CORS) or someone changes it to `["*"]` which allows any origin.
Both are bad. The value must come from an environment variable, not hardcoded.

### What to change:

**Step 1 — Remove the hardcoded override in config.py:**
Delete lines 179–185 entirely (the `if ENVIRONMENT == "production"` block at the bottom).
The `CORS_ORIGINS` setting already reads from env var — that is correct. The override
block below it is what causes the problem.

```python
# DELETE THIS ENTIRE BLOCK (lines 178-185):
if settings.ENVIRONMENT == "production":
    settings.DEBUG = False
    settings.LOG_LEVEL = "WARNING"
    settings.CORS_ORIGINS = ["https://yourdomain.com"]  # <-- DELETE
elif settings.ENVIRONMENT == "staging":
    settings.DEBUG = False
    settings.LOG_LEVEL = "INFO"
```

**Step 2 — Add a startup validator that rejects wildcard in production:**
In `backend/app/core/config.py`, add a new validator after the existing ones:

```python
@validator("CORS_ORIGINS")
def validate_cors_not_wildcard_in_production(cls, v, values):
    env = values.get("ENVIRONMENT", "development")
    if env == "production" and "*" in v:
        raise ValueError(
            "CORS_ORIGINS cannot contain '*' in production. "
            "Set CORS_ORIGINS env var to your actual frontend domain."
        )
    return v
```

**Step 3 — Update .env.example:**
Add to `.env.example` (or create if missing):
```
# REQUIRED in production — comma-separated list of allowed origins
CORS_ORIGINS=https://app.yourdomain.com,https://yourdomain.com
```

**Step 4 — Update docker-compose.yml:**
Ensure `CORS_ORIGINS` is listed as a required env var with no default `*` value.

### Test:
```bash
# In production env, set CORS_ORIGINS=* and start server
# Expected: server fails to start with ValueError about wildcard
ENVIRONMENT=production CORS_ORIGINS=* python -c "from app.core.config import settings"
# Expected output: ValueError: CORS_ORIGINS cannot contain '*' in production
```

### Risk: LOW — only adds validation. If CORS_ORIGINS env var is already correct, zero impact.

### Manual .env changes required (production server):
The `.env` file is not committed to git. Two manual changes are needed:

**Change 1 — Add www subdomain to CORS (currently missing):**
```bash
# Current value in production .env:
CORS_ORIGINS='["https://dokydoc.com"]'

# Change to (adds www subdomain):
CORS_ORIGINS='["https://dokydoc.com","https://www.dokydoc.com"]'
```

**Change 2 — Add ALLOWED_HOSTS (currently missing entirely from .env):**
```bash
# Add this new line to production .env:
ALLOWED_HOSTS=dokydoc.com,www.dokydoc.com,localhost
```

After both changes, restart the backend:
```bash
docker-compose restart backend
```

> **Note:** The `config.py` code change in this task adds the *validation* logic.
> The .env change provides the *values* that validation checks. Both are required.

---

## P0-03 — Fix ACCESS_TOKEN_EXPIRE_MINUTES (8 hours is too long)

**Ticket:** P0-03
**Priority:** P0 (security)
**File:** `backend/app/core/config.py`
**Line:** 36

### Current code:
```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 8 hours
```

### Current production state:
> The production `.env` already has `ACCESS_TOKEN_EXPIRE_MINUTES=30` which correctly
> overrides the 480-minute default. **Production is already safe.** This task fixes
> the dangerous `default=480` in `config.py` so that staging, local dev, and any
> environment *without* the `.env` override also gets a safe default (60 min).
> Priority is MEDIUM — not urgent for production, but a trap for other environments.

### Why the default is wrong:
8-hour tokens mean a stolen token gives an attacker 8 hours of access. Industry
standard is 15–60 minutes for access tokens. We already have refresh token support
(`REFRESH_TOKEN_EXPIRE_DAYS = 7`).

### What to change:

**Step 1 — Change default in config.py line 36:**
```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 1 hour
```

**Step 2 — Verify frontend handles 401 and calls refresh token:**
Read `frontend/` for any axios/fetch interceptor. There must be a 401 interceptor
that calls `POST /api/refresh-token` when a request fails with 401. If it doesn't
exist, create `frontend/lib/api-client.ts` with:

```typescript
// Add response interceptor to handle token expiry
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        const refreshToken = localStorage.getItem('refresh_token')
        const res = await axios.post('/api/refresh-token', { refresh_token: refreshToken })
        localStorage.setItem('access_token', res.data.access_token)
        originalRequest.headers['Authorization'] = `Bearer ${res.data.access_token}`
        return apiClient(originalRequest)
      } catch {
        // Refresh failed — redirect to login
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
```

### Test:
```bash
# Login and get token, note expiry in JWT payload
TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -d "username=test@test.com&password=password" | jq -r .access_token)
# Decode JWT and check exp field
echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
# exp should be ~3600 seconds from now (1 hour), not 28800 (8 hours)
```

### Risk: MEDIUM — if frontend has no refresh token interceptor, users will be logged out hourly. Do Step 2 first.

---

## P0-04 — Add Missing Database Indexes

**Ticket:** P0-04
**Priority:** P0 (performance — will OOM at 50+ tenants)
**New file:** `backend/alembic/versions/s11a1_performance_indexes.py`

### Why:
Several high-frequency query patterns hit full table scans. These become
critical at scale. The `CONCURRENTLY` keyword means zero downtime during migration.

### What to create:

Create new file `backend/alembic/versions/s11a1_performance_indexes.py`:

```python
"""Add critical performance indexes

Revision ID: s11a1
Revises: s10a1
Create Date: 2026-04-05
"""
from alembic import op

revision = 's11a1'
down_revision = 's10a1'  # Points to requirement_atoms migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mismatches — validation panel loads these constantly
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mismatches_tenant_doc_status
        ON mismatches (tenant_id, document_id, status);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mismatches_tenant_severity_open
        ON mismatches (tenant_id, severity)
        WHERE status = 'new';
    """)

    # Requirement atoms — 9-pass validation scans these in every run
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requirement_atoms_document_type
        ON requirement_atoms (document_id, atom_type);
    """)

    # Ontology graph — most expensive endpoint
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_concepts_tenant_type
        ON ontology_concepts (tenant_id, concept_type);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_relationships_tenant_source
        ON ontology_relationships (tenant_id, source_concept_id);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ontology_relationships_tenant_target
        ON ontology_relationships (tenant_id, target_concept_id);
    """)

    # Audit logs — compliance time-range queries
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_tenant_created
        ON audit_logs (tenant_id, created_at DESC);
    """)

    # Concept mappings — used in every mapping run
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_concept_mappings_tenant_doc
        ON concept_mappings (tenant_id, document_concept_id);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_concept_mappings_tenant_code
        ON concept_mappings (tenant_id, code_concept_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_mismatches_tenant_doc_status;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_mismatches_tenant_severity_open;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_requirement_atoms_document_type;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_concepts_tenant_type;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_relationships_tenant_source;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_ontology_relationships_tenant_target;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_audit_logs_tenant_created;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_concept_mappings_tenant_doc;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_concept_mappings_tenant_code;")
```

**IMPORTANT:** Check `down_revision` — it must match the `revision` of the latest
migration in your chain. Run `alembic heads` to find the current head, then set
`down_revision` accordingly. Do not guess.

### How to run:
```bash
cd backend
alembic upgrade head
# Verify with:
psql $DATABASE_URL -c "\d mismatches" | grep idx
```

### Test:
```bash
# After migration, verify index exists
psql $DATABASE_URL -c "
  SELECT indexname FROM pg_indexes
  WHERE tablename = 'mismatches'
  AND indexname LIKE 'idx_%';
"
# Should list all 9 new indexes
```

### Risk: LOW — `CONCURRENTLY` means no table lock. Safe on live database.

---

## P0-05 — Celery Task Idempotency Guard

**Ticket:** P0-05
**Priority:** P0 (data integrity)
**File:** `backend/app/services/business_ontology_service.py`

### Why:
If a Celery worker crashes mid-task and retries, `extract_ontology_entities` can
create duplicate OntologyConcept rows. There is no unique constraint at the DB level.

### What to change:

**Step 1 — Read the file first:**
```bash
grep -n "get_or_create\|UniqueConstraint\|concept_type\|name" \
  backend/app/services/business_ontology_service.py | head -30
```

**Step 2 — Add unique constraint via migration:**
Create `backend/alembic/versions/s11b1_ontology_unique_constraint.py`:

```python
"""Add unique constraint on ontology_concepts name+tenant+source_type

Revision ID: s11b1
Revises: s11a1
Create Date: 2026-04-05
"""
from alembic import op

revision = 's11b1'
down_revision = 's11a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First, remove any existing duplicates (keep the one with highest id)
    op.execute("""
        DELETE FROM ontology_concepts
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM ontology_concepts
            GROUP BY name, tenant_id, source_type
        );
    """)
    # Now add the unique constraint
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ontology_concept_name_tenant_source
        ON ontology_concepts (name, tenant_id, source_type);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ontology_concept_name_tenant_source;")
```

**Step 3 — Update `get_or_create` pattern in ontology service:**
Find where `OntologyConcept` is created (grep for `OntologyConcept(` or
`crud.ontology_concept.create`). Wrap in an upsert pattern:

```python
# BEFORE (creates duplicates on retry):
concept = crud.ontology_concept.create(db=db, obj_in=concept_data)

# AFTER (idempotent — safe to call multiple times):
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(OntologyConcept).values(**concept_data)
stmt = stmt.on_conflict_do_update(
    constraint="uq_ontology_concept_name_tenant_source",
    set_={"updated_at": func.now(), "confidence_score": stmt.excluded.confidence_score}
)
db.execute(stmt)
db.commit()
```

### Test:
```bash
# Trigger the same ontology extraction twice for the same document
# Expected: second run updates existing concepts, does NOT create duplicates
psql $DATABASE_URL -c "
  SELECT name, tenant_id, COUNT(*) as cnt
  FROM ontology_concepts
  GROUP BY name, tenant_id
  HAVING COUNT(*) > 1;
"
# Expected: 0 rows returned
```

### Risk: MEDIUM — the DELETE in the migration removes real data (duplicates). Run in staging first. Verify the duplicate removal query on your data before applying to production.

---

## P0-06 — Frontend Error Boundary for Mermaid

**Ticket:** P0-06
**Priority:** P0 (UX — Mermaid JS errors crash the entire page)
**File:** `frontend/components/ontology/MermaidDiagram.tsx`

### Why:
If Mermaid receives invalid syntax (e.g. a concept name with special characters),
it throws a JS exception that propagates up and crashes the entire React tree,
showing a blank white page to the user.

### What to change:

**Step 1 — Read the file:**
```bash
cat frontend/components/ontology/MermaidDiagram.tsx
```

**Step 2 — Create an ErrorBoundary component:**
Create new file `frontend/components/ui/ErrorBoundary.tsx`:

```tsx
'use client'
import React from 'react'

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="border border-red-200 bg-red-50 rounded-lg p-4 text-sm">
          <p className="font-medium text-red-700">Diagram rendering failed</p>
          <p className="text-red-500 mt-1 text-xs font-mono">
            {this.state.error?.message}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
```

**Step 3 — Wrap MermaidDiagram in ErrorBoundary:**
In every file that renders `<MermaidDiagram />`, wrap it:

```tsx
// Find files using MermaidDiagram:
// frontend/app/dashboard/brain/page.tsx
// frontend/app/dashboard/code/[id]/page.tsx
// Any other page that imports MermaidDiagram

import { ErrorBoundary } from '@/components/ui/ErrorBoundary'

// Replace:
<MermaidDiagram syntax={...} />

// With:
<ErrorBoundary>
  <MermaidDiagram syntax={...} />
</ErrorBoundary>
```

**Step 4 — Sanitize concept names before injecting into Mermaid syntax:**
In `frontend/components/ontology/MermaidDiagram.tsx`, find where node labels are
built and add a sanitizer:

```typescript
// Add this helper function at the top of the file:
function sanitizeMermaidLabel(label: string): string {
  // Remove chars that break Mermaid syntax or could inject JS
  return label
    .replace(/["\[\](){}|<>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80) // Hard cap to prevent huge nodes
}

// Then use it wherever node labels are constructed:
// BEFORE: node.name
// AFTER:  sanitizeMermaidLabel(node.name)
```

### Test:
1. Create an ontology concept with name `Test"Concept[broken]` (special chars)
2. Navigate to brain/ontology graph page
3. Expected: Page does NOT crash — shows "Diagram rendering failed" card
4. Click "Try again" — diagram attempts re-render

### Risk: LOW — purely additive, wraps existing component.

---

## P0-07 — Fix Duplicate REDIS_URL in .env

**Ticket:** P0-07
**Priority:** P0 (silent connection bug — may cause intermittent auth failures)
**Type:** Manual .env fix only — no code change required
**Estimated time:** 5 minutes

### Problem:
The production `.env` file defines `REDIS_URL` **twice**:
- First definition (line ~43): `REDIS_URL=redis://redis:6379` — **no password, wrong**
- Second definition (line ~55): `REDIS_URL=redis://:2ffdf08ed9b64853578245256adbda20@redis:6379` — **with password, correct**

Python's `python-dotenv` and most env parsers use the **last** definition when a key appears twice. This means the correct (password) value is currently winning — but this is fragile and confusing. If anyone reorders the file, the broken value silently takes over and Redis connections fail (Celery tasks stop, rate limiting breaks, session caching fails).

### Fix (manual, on production server):
```bash
# Edit /home/user/dokydoc/backend/.env
# DELETE the first REDIS_URL line (the one WITHOUT the password):
# REDIS_URL=redis://redis:6379   ← DELETE THIS LINE

# Keep only the correct line:
REDIS_URL=redis://:2ffdf08ed9b64853578245256adbda20@redis:6379

# Restart affected services:
docker-compose restart backend celery
```

### Verify:
```bash
# After restart, verify Redis is reachable from backend:
docker-compose exec backend python -c "
from app.core.config import settings
print('REDIS_URL:', settings.REDIS_URL)
import redis
r = redis.from_url(settings.REDIS_URL)
print('PING:', r.ping())  # Should print: PING: True
"
```

### Risk: ZERO — removing a duplicate wrong value, keeping the correct one.

---

## P0 COMPLETION CHECKLIST

Before marking Phase 0 done, verify:

```
[ ] P0-01: Upload a 100MB file — no 413 error, file_size_warning in response
[ ] P0-01: .env updated: MAX_FILE_SIZE=2147483648 on production server
[ ] P0-02: Start server with ENVIRONMENT=production CORS_ORIGINS=* — server refuses to start
[ ] P0-02: .env updated: www.dokydoc.com added to CORS_ORIGINS on production server
[ ] P0-02: .env updated: ALLOWED_HOSTS line added to production .env
[ ] P0-03: config.py default is now 60 min (staging/dev environments use safe default)
[ ] P0-03: (Production already correct via .env — no .env change needed for P0-03)
[ ] P0-04: Run "SELECT indexname FROM pg_indexes WHERE tablename='mismatches'" — 9 new indexes present
[ ] P0-05: Run ontology extraction twice — zero duplicate concepts in DB
[ ] P0-06: Render a Mermaid diagram with a broken concept name — no page crash
[ ] P0-07: Only ONE REDIS_URL line in production .env — the one with the password
[ ] All existing tests still pass: cd backend && python -m pytest tests/ -v
```

---

---

# PHASE 1 — Data Flywheel & Training Infrastructure

**Goal:** Capture every AI judgment + human correction so we can fine-tune models later.
**This data can NEVER be recovered retroactively — capture must start NOW.**
**Can be parallelized:** P1-01 through P1-04 are DB/backend only. P1-05 is frontend only.
**Sprint estimate:** 4–5 days for 2 developers.

---

## P1-01 — Create TrainingExample Model & Migration

**Ticket:** P1-01
**Priority:** P1 (data — every day without this loses training signal)
**New file:** `backend/app/models/training_example.py`

### Why:
When a developer clicks "Correct" or "Wrong" on a mismatch card, that signal is
worth gold for future LLM fine-tuning. Without this table, the signal is lost forever.

### Step 1 — Create the model:

Create `backend/app/models/training_example.py`:

```python
"""
TrainingExample — Captures AI judgment + human correction for LLM fine-tuning.

Every mismatch created by the validation engine is captured here automatically.
Human feedback (accept/reject/edit) is recorded when developers review mismatches.
This table is the foundation of the data flywheel.
"""
from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base


class TrainingExample(Base):
    __tablename__ = "training_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # What type of AI judgment was this?
    # "mismatch_judgment" = validation engine decided there was a mismatch
    # "mapping_judgment"  = mapping engine decided two concepts are related
    # "chat_response"     = chat assistant answered a question
    example_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # FK to the source row (no DB-level FK — intentionally flexible)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(50), nullable=False)
    # Values: "mismatches", "concept_mappings", "chat_messages"

    # What the AI saw (full prompt context — stored for replay)
    input_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example: { "atom_content": "...", "atom_type": "FUNCTIONAL", "code_context": "..." }

    # What the AI output (the actual judgment)
    ai_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example: { "verdict": "MISMATCH", "confidence": 0.87, "reasoning": "..." }

    # What the human said (filled in when developer clicks accept/reject/edit)
    human_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    # Values: "accepted" (AI was right), "rejected" (AI was wrong), "edited" (AI was partially right)

    human_correction: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Only set when human_label = "edited". Contains the corrected answer.
    # Example: { "correct_verdict": "PARTIAL_MATCH", "notes": "This is actually documented in section 3" }

    # Who labeled it and when
    labeled_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    labeled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Export tracking (for fine-tuning jobs)
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    export_batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<TrainingExample(id={self.id}, type={self.example_type}, "
            f"label={self.human_label})>"
        )
```

### Step 2 — Register in models/__init__.py:

Open `backend/app/models/__init__.py` and add at the end:
```python
from .training_example import TrainingExample  # Phase 1: Data Flywheel
```

### Step 3 — Create the Alembic migration:

Create `backend/alembic/versions/s12a1_training_examples.py`:

```python
"""Add training_examples table for data flywheel

Revision ID: s12a1
Revises: s11b1
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 's12a1'
down_revision = 's11b1'  # After the performance indexes migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'training_examples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('example_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('source_table', sa.String(50), nullable=False),
        sa.Column('input_context', JSONB(), nullable=False),
        sa.Column('ai_output', JSONB(), nullable=False),
        sa.Column('human_label', sa.String(20), nullable=True),
        sa.Column('human_correction', JSONB(), nullable=True),
        sa.Column('labeled_by_user_id', sa.Integer(), nullable=True),
        sa.Column('labeled_at', sa.DateTime(), nullable=True),
        sa.Column('is_exported', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('export_batch_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['labeled_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Indexes for common query patterns
    op.create_index('idx_training_examples_tenant_type',
                    'training_examples', ['tenant_id', 'example_type'])
    op.create_index('idx_training_examples_unlabeled',
                    'training_examples', ['tenant_id', 'example_type'],
                    postgresql_where=sa.text("human_label IS NULL"))
    op.create_index('idx_training_examples_source',
                    'training_examples', ['source_table', 'source_id'])


def downgrade() -> None:
    op.drop_index('idx_training_examples_source')
    op.drop_index('idx_training_examples_unlabeled')
    op.drop_index('idx_training_examples_tenant_type')
    op.drop_table('training_examples')
```

### Run:
```bash
cd backend && alembic upgrade head
# Verify:
psql $DATABASE_URL -c "\d training_examples"
```

---

## P1-02 — Create CRUD for TrainingExample

**Ticket:** P1-02
**Depends:** P1-01 (model must exist first)
**New file:** `backend/app/crud/crud_training_example.py`

### Create the file:

```python
"""CRUD operations for TrainingExample (data flywheel)."""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.training_example import TrainingExample


class CRUDTrainingExample:

    def create_from_mismatch(
        self,
        db: Session,
        *,
        tenant_id: int,
        mismatch_id: int,
        ai_output: dict,
        input_context: dict,
    ) -> TrainingExample:
        """
        Auto-capture a training example when a mismatch is created.
        Called by validation_service.py. Never raises — wrapped in try/except by caller.
        """
        example = TrainingExample(
            tenant_id=tenant_id,
            example_type="mismatch_judgment",
            source_id=mismatch_id,
            source_table="mismatches",
            input_context=input_context,
            ai_output=ai_output,
        )
        db.add(example)
        db.commit()
        db.refresh(example)
        return example

    def create_from_mapping(
        self,
        db: Session,
        *,
        tenant_id: int,
        mapping_id: int,
        ai_output: dict,
        input_context: dict,
    ) -> TrainingExample:
        """Auto-capture when a concept mapping is AI-validated (Tier 3)."""
        example = TrainingExample(
            tenant_id=tenant_id,
            example_type="mapping_judgment",
            source_id=mapping_id,
            source_table="concept_mappings",
            input_context=input_context,
            ai_output=ai_output,
        )
        db.add(example)
        db.commit()
        db.refresh(example)
        return example

    def record_human_label(
        self,
        db: Session,
        *,
        source_table: str,
        source_id: int,
        tenant_id: int,
        label: str,  # "accepted", "rejected", "edited"
        correction: Optional[dict] = None,
        user_id: Optional[int] = None,
    ) -> Optional[TrainingExample]:
        """
        Record a human's feedback on an AI judgment.
        Called when developer clicks Accept/Reject/Edit on a mismatch card.
        Returns None if no matching TrainingExample found (non-fatal).
        """
        example = (
            db.query(TrainingExample)
            .filter(
                TrainingExample.source_table == source_table,
                TrainingExample.source_id == source_id,
                TrainingExample.tenant_id == tenant_id,
            )
            .first()
        )
        if not example:
            return None

        example.human_label = label
        example.human_correction = correction
        example.labeled_by_user_id = user_id
        example.labeled_at = datetime.utcnow()
        db.commit()
        db.refresh(example)
        return example

    def get_unlabeled(
        self,
        db: Session,
        *,
        tenant_id: int,
        example_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[TrainingExample]:
        """Get examples awaiting human review — for the labeling queue UI."""
        q = db.query(TrainingExample).filter(
            TrainingExample.tenant_id == tenant_id,
            TrainingExample.human_label.is_(None),
        )
        if example_type:
            q = q.filter(TrainingExample.example_type == example_type)
        return q.order_by(TrainingExample.created_at.desc()).limit(limit).all()

    def get_label_stats(self, db: Session, *, tenant_id: int) -> dict:
        """
        Returns counts for the analytics dashboard:
        { total, labeled, unlabeled, by_label: {accepted, rejected, edited} }
        """
        from sqlalchemy import func, case

        result = db.query(
            func.count(TrainingExample.id).label("total"),
            func.sum(
                case((TrainingExample.human_label.isnot(None), 1), else_=0)
            ).label("labeled"),
            func.sum(
                case((TrainingExample.human_label == "accepted", 1), else_=0)
            ).label("accepted"),
            func.sum(
                case((TrainingExample.human_label == "rejected", 1), else_=0)
            ).label("rejected"),
            func.sum(
                case((TrainingExample.human_label == "edited", 1), else_=0)
            ).label("edited"),
        ).filter(TrainingExample.tenant_id == tenant_id).first()

        total = result.total or 0
        labeled = result.labeled or 0
        return {
            "total": total,
            "labeled": labeled,
            "unlabeled": total - labeled,
            "by_label": {
                "accepted": result.accepted or 0,
                "rejected": result.rejected or 0,
                "edited": result.edited or 0,
            },
        }

    def get_export_batch(
        self,
        db: Session,
        *,
        tenant_id: int,
        example_type: Optional[str] = None,
        require_label: bool = True,
        limit: int = 1000,
    ) -> List[TrainingExample]:
        """Get examples ready for export to a training dataset."""
        q = db.query(TrainingExample).filter(
            TrainingExample.tenant_id == tenant_id,
            TrainingExample.is_exported.is_(False),
        )
        if require_label:
            q = q.filter(TrainingExample.human_label.isnot(None))
        if example_type:
            q = q.filter(TrainingExample.example_type == example_type)
        return q.order_by(TrainingExample.created_at.asc()).limit(limit).all()


training_example = CRUDTrainingExample()
```

### Register in crud/__init__.py:
Open `backend/app/crud/__init__.py` and add at the end:
```python
# Phase 1: Data Flywheel
from .crud_training_example import training_example
```

---

## P1-03 — Auto-Capture in Validation Service

**Ticket:** P1-03
**Depends:** P1-02 (CRUD must exist)
**File:** `backend/app/services/validation_service.py`

### Why:
Every mismatch created by the validation engine must auto-capture a TrainingExample.
The developer does not need to do anything — capture is automatic.

### What to add:

**Step 1 — Read validation_service.py fully:**
```bash
grep -n "crud.mismatch\|create_with\|Mismatch\|mismatch" \
  backend/app/services/validation_service.py | head -30
```

Find the exact line where `crud.mismatch.create` or `crud.mismatch.create_with_link`
is called. It will look something like:
```python
new_mismatch = crud.mismatch.create_with_link(db=db, ...)
```

**Step 2 — After that line, add the capture block:**

```python
# --- PHASE 1: Data Flywheel capture (non-blocking) ---
try:
    crud.training_example.create_from_mismatch(
        db=db,
        tenant_id=tenant_id,
        mismatch_id=new_mismatch.id,
        ai_output={
            "verdict": pass_result.get("verdict"),
            "confidence": pass_result.get("confidence"),
            "reasoning": pass_result.get("reasoning", ""),
            "pass_name": pass_name,
        },
        input_context={
            "atom_content": atom.content,
            "atom_type": atom.atom_type,
            "atom_id": atom.id,
            "document_id": document_id,
            "component_id": component_id,
            "code_context": pass_result.get("code_context", ""),
        },
    )
except Exception as _te:
    # CRITICAL: NEVER let training capture block validation
    self.logger.warning(f"Training capture failed (non-fatal): {_te}")
# --- END Data Flywheel capture ---
```

**Important:** The variable names (`pass_result`, `pass_name`, `atom`, `new_mismatch`)
must match what already exists in the function. Read the actual code first and adjust
variable names accordingly.

---

## P1-04 — Auto-Capture in Mapping Service (Tier 3)

**Ticket:** P1-04
**Depends:** P1-02 (CRUD must exist)
**File:** `backend/app/services/mapping_service.py`

### Why:
Tier 3 AI validation is the most expensive and error-prone step. Capturing these
judgments lets us reduce AI calls over time as we learn which pairs are always correct.

### What to add:

**Step 1 — Find where Tier 3 creates a mapping:**
```bash
grep -n "ai_validated\|create_mapping\|relationship_type\|Tier 3" \
  backend/app/services/mapping_service.py
```

Find the line after `crud.concept_mapping.create_mapping(...)` inside the
`_validate_ambiguous_pairs` method. It will look like:
```python
crud.concept_mapping.create_mapping(
    db=db,
    document_concept_id=...,
    code_concept_id=...,
    mapping_method="ai_validated",
    ...
)
```

**Step 2 — After the mapping creation, add capture:**
```python
# --- PHASE 1: Data Flywheel capture for AI mapping judgment (non-blocking) ---
try:
    # Get the mapping we just created to get its ID
    new_mapping = crud.concept_mapping.get_latest(
        db=db, doc_concept_id=doc_concept.id, code_concept_id=code_concept.id
    )
    if new_mapping:
        crud.training_example.create_from_mapping(
            db=db,
            tenant_id=tenant_id,
            mapping_id=new_mapping.id,
            ai_output={
                "relationship_type": ai_relationship_type,
                "confidence": ai_confidence,
                "verdict": "mapped" if ai_relationship_type != "unrelated" else "unmapped",
            },
            input_context={
                "doc_concept_name": doc_concept.name,
                "code_concept_name": code_concept.name,
                "doc_concept_type": doc_concept.concept_type,
                "code_concept_type": code_concept.concept_type,
                "fuzzy_score_before_ai": round(pair_score, 3),
            },
        )
except Exception as _te:
    self.logger.warning(f"Training capture (mapping) failed (non-fatal): {_te}")
# --- END Data Flywheel capture ---
```

---

## P1-05 — Accept/Reject/Edit UI on Mismatch Cards

**Ticket:** P1-05
**Depends:** P1-06 (feedback endpoint must exist before UI calls it)
**File:** `frontend/app/dashboard/validation-panel/page.tsx`

### Step 1 — Read the file:
```bash
cat frontend/app/dashboard/validation-panel/page.tsx | head -100
```
Find where each mismatch card is rendered. It will look like a `.map()` over mismatches.

### Step 2 — Add feedback state per mismatch:
At the top of the component, add:
```typescript
const [feedback, setFeedback] = useState<Record<number, 'accepted' | 'rejected' | 'edited'>>({})
const [editingMismatch, setEditingMismatch] = useState<number | null>(null)
const [editNote, setEditNote] = useState('')
```

### Step 3 — Add the feedback API call:
```typescript
const recordFeedback = async (
  mismatchId: number,
  label: 'accepted' | 'rejected' | 'edited',
  correction?: string
) => {
  try {
    await fetch(`/api/v1/validation/mismatches/${mismatchId}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ label, correction }),
    })
    setFeedback(prev => ({ ...prev, [mismatchId]: label }))
  } catch (err) {
    console.error('Feedback failed:', err)
    // Non-fatal — don't show error to user
  }
}
```

### Step 4 — Add the 3 buttons inside each mismatch card:

Find the JSX for each mismatch card and add at the bottom of the card:
```tsx
{/* Phase 1: Training feedback buttons */}
<div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
  {feedback[mismatch.id] ? (
    <span className="text-xs text-gray-400">
      {feedback[mismatch.id] === 'accepted' && '✓ Marked correct'}
      {feedback[mismatch.id] === 'rejected' && '✗ Marked wrong'}
      {feedback[mismatch.id] === 'edited' && '✎ Correction saved'}
    </span>
  ) : (
    <>
      <span className="text-xs text-gray-400 mr-1">Was this correct?</span>
      <button
        onClick={() => recordFeedback(mismatch.id, 'accepted')}
        className="text-xs px-2 py-1 bg-green-50 hover:bg-green-100 text-green-700 rounded border border-green-200"
      >
        ✓ Yes
      </button>
      <button
        onClick={() => recordFeedback(mismatch.id, 'rejected')}
        className="text-xs px-2 py-1 bg-red-50 hover:bg-red-100 text-red-700 rounded border border-red-200"
      >
        ✗ No
      </button>
      <button
        onClick={() => setEditingMismatch(mismatch.id)}
        className="text-xs px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-700 rounded border border-amber-200"
      >
        ✎ Correct it
      </button>
    </>
  )}
</div>

{/* Correction input (shown when Edit is clicked) */}
{editingMismatch === mismatch.id && (
  <div className="mt-2 flex gap-2">
    <input
      value={editNote}
      onChange={(e) => setEditNote(e.target.value)}
      placeholder="What is the correct interpretation?"
      className="flex-1 text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
      autoFocus
    />
    <button
      onClick={() => {
        recordFeedback(mismatch.id, 'edited', editNote)
        setEditingMismatch(null)
        setEditNote('')
      }}
      className="text-xs px-2 py-1 bg-blue-600 text-white rounded"
    >
      Save
    </button>
    <button
      onClick={() => { setEditingMismatch(null); setEditNote('') }}
      className="text-xs px-2 py-1 text-gray-500 hover:text-gray-700"
    >
      Cancel
    </button>
  </div>
)}
```

---

## P1-06 — Feedback API Endpoint

**Ticket:** P1-06
**Depends:** P1-02 (CRUD must exist)
**File:** `backend/app/api/endpoints/validation.py`

### Read the file first:
```bash
cat backend/app/api/endpoints/validation.py
```

### Add this endpoint after the existing `read_mismatches` endpoint:

```python
class MismatchFeedbackRequest(BaseModel):
    label: str          # "accepted", "rejected", "edited"
    correction: Optional[str] = None


@router.post("/mismatches/{mismatch_id}/feedback", status_code=200)
def record_mismatch_feedback(
    mismatch_id: int,
    feedback: MismatchFeedbackRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Record human feedback on a mismatch (was the AI correct?).
    Phase 1: Data Flywheel — feeds training_examples table.
    """
    # Validate label value
    valid_labels = {"accepted", "rejected", "edited"}
    if feedback.label not in valid_labels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{feedback.label}'. Must be one of: {valid_labels}"
        )

    # Verify mismatch belongs to this tenant (security check)
    mismatch = crud.mismatch.get(db=db, id=mismatch_id, tenant_id=tenant_id)
    if not mismatch:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    # Record in training_examples table
    correction_dict = None
    if feedback.label == "edited" and feedback.correction:
        correction_dict = {"correct_interpretation": feedback.correction}

    result = crud.training_example.record_human_label(
        db=db,
        source_table="mismatches",
        source_id=mismatch_id,
        tenant_id=tenant_id,
        label=feedback.label,
        correction=correction_dict,
        user_id=current_user.id,
    )

    return {
        "success": True,
        "mismatch_id": mismatch_id,
        "label": feedback.label,
        "training_example_updated": result is not None,
    }
```

**Note:** You need `from pydantic import BaseModel` at the top if not already imported.
Check line 1–10 of the file and add if missing.

---

## P1 COMPLETION CHECKLIST

```
[ ] P1-01: "SELECT COUNT(*) FROM training_examples" returns 0 (table exists, empty)
[ ] P1-02: "from app.crud import training_example" works without ImportError
[ ] P1-03: Run a validation scan → "SELECT COUNT(*) FROM training_examples" > 0
[ ] P1-04: Trigger a mapping run → training_examples has rows with example_type='mapping_judgment'
[ ] P1-05: Mismatch card in UI shows ✓ Yes / ✗ No / ✎ Correct it buttons
[ ] P1-06: POST /api/v1/validation/mismatches/1/feedback with {"label":"accepted"} returns 200
[ ] P1-06: After clicking "Yes" on a mismatch → SELECT human_label FROM training_examples WHERE source_id=X returns 'accepted'
[ ] Non-regression: All existing validation tests still pass
```

---

---

# PHASE 2 — Mapping Intelligence Upgrade (Cosine Similarity)

**Goal:** Use the 768-dim embeddings already stored on OntologyConcept to improve
concept matching. Currently ignored. Fix is ~30 lines of code. Zero new AI calls.
**Sprint estimate:** 1–2 days for 1 developer.
**Can be parallelized:** YES — independent of Phase 0 and Phase 1.

---

## P2-01 — Verify Embeddings Are Being Stored

**Ticket:** P2-01 (investigation — do this before writing any code)
**File:** `backend/app/services/embedding_service.py`

### Step 1 — Check if embedding_vector column exists on ontology_concepts:
```bash
psql $DATABASE_URL -c "
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name = 'ontology_concepts'
  AND column_name LIKE '%embed%';
"
```

If no rows returned: the column doesn't exist yet. Run:
```bash
cd backend && alembic upgrade head
# Check if s4c1_pgvector_embeddings.py migration runs
```

### Step 2 — Check embedding coverage:
```bash
psql $DATABASE_URL -c "
  SELECT
    COUNT(*) as total,
    COUNT(embedding_vector) as with_embedding,
    ROUND(COUNT(embedding_vector)::numeric / NULLIF(COUNT(*),0) * 100, 1) as pct_covered
  FROM ontology_concepts
  WHERE tenant_id = 1;
"
```

**If coverage < 50%:** Run the embedding backfill before implementing cosine matching.
The backfill command (read `embedding_service.py` to find the right function):
```bash
# Trigger backfill for all un-embedded concepts
# This may already exist as a Celery task or admin endpoint
```

**If coverage >= 50%:** Proceed to P2-02.

---

## P2-02 — Add Cosine Similarity Function to MappingService

**Ticket:** P2-02
**Depends:** P2-01 (embeddings must exist)
**File:** `backend/app/services/mapping_service.py`

### Current state (lines 70–76):
```python
def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0 to 1.0)."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (_levenshtein_distance(s1, s2) / max_len)
```

### Step 1 — Add cosine similarity function AFTER line 76:

Open `backend/app/services/mapping_service.py`.
After the `_levenshtein_similarity` function (after line 76), insert:

```python
def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """
    Cosine similarity between two embedding vectors. Returns 0.0–1.0.
    Returns 0.0 if either vector is None or empty (safe fallback).

    Used in Tier 2 matching to catch semantic synonyms that Levenshtein misses.
    Example: "User Account" vs "Customer Profile" → cosine ~0.91, Levenshtein ~0.31
    """
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) != len(vec_b):
        return 0.0
    try:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = sum(a * a for a in vec_a) ** 0.5
        mag_b = sum(b * b for b in vec_b) ** 0.5
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (mag_a * mag_b)))
    except (TypeError, ZeroDivisionError):
        return 0.0
```

### Step 2 — Add cosine threshold constant to MappingService class:

In the `MappingService` class (line ~83–87), add a new threshold:

```python
class MappingService(LoggerMixin):
    # Thresholds (defaults — can be tuned from feedback data)
    FUZZY_HIGH_CONFIDENCE = 0.50
    FUZZY_MEDIUM_CONFIDENCE = 0.25
    LEVENSHTEIN_THRESHOLD = 0.70
    AI_VALIDATION_THRESHOLD = 0.25
    COSINE_HIGH_CONFIDENCE = 0.85   # ADD THIS LINE — cosine >= 0.85 → auto-confirm, skip AI
    COSINE_MEDIUM_CONFIDENCE = 0.70 # ADD THIS LINE — cosine 0.70–0.85 → high confidence fuzzy
```

---

## P2-03 — Wire Cosine Similarity into Tier 2 Matching Loop

**Ticket:** P2-03
**Depends:** P2-02 (function must exist)
**File:** `backend/app/services/mapping_service.py`
**Lines:** 231–289 (the Tier 2 fuzzy matching loop)

### Current Tier 2 inner loop (lines ~241–260):
```python
for cc in unmapped_codes:
    if cc.id in mapped_code_ids:
        continue

    cc_tokens = _tokenize(cc.name)
    cc_norm = _normalize(cc.name)

    # Token overlap score
    if dc_tokens and cc_tokens:
        overlap = len(dc_tokens & cc_tokens)
        union = len(dc_tokens | cc_tokens)
        token_score = overlap / union if union > 0 else 0.0
    else:
        token_score = 0.0

    # Levenshtein similarity
    lev_score = _levenshtein_similarity(dc_norm, cc_norm)

    # Combined score (weighted)
    combined = max(token_score, lev_score)

    if combined > best_score:
        best_score = combined
        best_match = cc
```

### Replace the inner loop with the cosine-enhanced version:

Find this exact block (starting at `for cc in unmapped_codes:` and ending at
`best_match = cc`) and replace with:

```python
for cc in unmapped_codes:
    if cc.id in mapped_code_ids:
        continue

    cc_tokens = _tokenize(cc.name)
    cc_norm = _normalize(cc.name)

    # Token overlap score (FREE)
    if dc_tokens and cc_tokens:
        overlap = len(dc_tokens & cc_tokens)
        union = len(dc_tokens | cc_tokens)
        token_score = overlap / union if union > 0 else 0.0
    else:
        token_score = 0.0

    # Levenshtein similarity (FREE)
    lev_score = _levenshtein_similarity(dc_norm, cc_norm)

    # PHASE 2: Cosine similarity from stored embeddings (FREE — already computed)
    cos_score = 0.0
    if hasattr(dc, 'embedding_vector') and hasattr(cc, 'embedding_vector'):
        cos_score = _cosine_similarity(dc.embedding_vector, cc.embedding_vector)

    # Composite score: cosine is most reliable for semantics
    # If cosine is available (>0), weight it heavily
    if cos_score > 0:
        combined = max(token_score, lev_score, cos_score)
        # Boost: if cosine alone is very high, trust it
        if cos_score >= self.COSINE_HIGH_CONFIDENCE:
            combined = cos_score  # Override everything — high-confidence semantic match
    else:
        # Fallback: no embeddings available, use original logic
        combined = max(token_score, lev_score)

    if combined > best_score:
        best_score = combined
        best_match = cc
```

### Also update the mapping method label to include cosine info:

Find the section after the loop where `crud.concept_mapping.create_mapping` is called
(around line 265). Update `mapping_method` to record which signal won:

```python
# Determine which signal drove the match (for debugging and training data)
if best_match:
    if hasattr(dc, 'embedding_vector') and hasattr(best_match, 'embedding_vector'):
        final_cos = _cosine_similarity(dc.embedding_vector, best_match.embedding_vector)
    else:
        final_cos = 0.0
    mapping_method = "cosine_fuzzy" if final_cos >= self.COSINE_MEDIUM_CONFIDENCE else "fuzzy"
else:
    mapping_method = "fuzzy"

crud.concept_mapping.create_mapping(
    db=db,
    document_concept_id=dc.id,
    code_concept_id=best_match.id,
    mapping_method=mapping_method,   # Was "fuzzy", now "cosine_fuzzy" when applicable
    confidence_score=round(best_score, 3),
    ...
)
```

---

## P2-04 — Embedding Coverage Check Before Mapping Run

**Ticket:** P2-04
**Depends:** P2-02
**File:** `backend/app/services/mapping_service.py`
**Location:** Beginning of `run_full_mapping()` method

### Add a coverage check at the start of run_full_mapping:

Find `def run_full_mapping(` and add this block right after the
`doc_concepts = crud.ontology_concept.get_by_source_type(...)` call:

```python
# PHASE 2: Check embedding coverage — log warning if low
total_concepts = len(doc_concepts) + len(code_concepts)
embedded_concepts = sum(
    1 for c in doc_concepts + code_concepts
    if hasattr(c, 'embedding_vector') and c.embedding_vector
)
coverage_pct = (embedded_concepts / total_concepts * 100) if total_concepts > 0 else 0

if coverage_pct < 30:
    self.logger.warning(
        f"Low embedding coverage for tenant {tenant_id}: "
        f"{embedded_concepts}/{total_concepts} concepts embedded ({coverage_pct:.0f}%). "
        f"Cosine similarity will be skipped for un-embedded concepts. "
        f"Run embedding backfill to improve mapping accuracy."
    )
elif coverage_pct >= 80:
    self.logger.info(
        f"Good embedding coverage: {coverage_pct:.0f}% — cosine similarity active"
    )
```

---

## P2-05 — Add Embedding Backfill Celery Task

**Ticket:** P2-05
**Depends:** P2-01 (must know which concepts need embeddings)
**File:** `backend/app/tasks/ontology_tasks.py`

### Read the file first:
```bash
cat backend/app/tasks/ontology_tasks.py
```

### Add the backfill task at the end of the file:

```python
@celery_app.task(name="backfill_embeddings", bind=True, max_retries=2)
def backfill_embeddings(self, tenant_id: int):
    """
    Generate embeddings for all OntologyConcepts that don't have one yet.
    Safe to run multiple times (idempotent).
    Triggered automatically if embedding coverage < 50% during mapping run.

    Phase 2: Required for cosine similarity matching to work.
    """
    from app.services.embedding_service import embedding_service
    from app.models.ontology_concept import OntologyConcept
    from app.db.session import SessionLocal

    logger.info(f"Starting embedding backfill for tenant {tenant_id}")

    with SessionLocal() as db:
        # Get all concepts without embeddings for this tenant
        concepts = (
            db.query(OntologyConcept)
            .filter(
                OntologyConcept.tenant_id == tenant_id,
                OntologyConcept.is_active == True,
            )
            .all()
        )

        # Filter to un-embedded (check the actual column name in your DB)
        un_embedded = [c for c in concepts if not getattr(c, 'embedding_vector', None)]
        total = len(un_embedded)

        if total == 0:
            logger.info(f"All concepts already embedded for tenant {tenant_id}")
            return {"status": "already_complete", "embedded": 0}

        logger.info(f"Embedding {total} concepts for tenant {tenant_id}")
        success = 0
        failed = 0

        # Process in batches of 20 to respect rate limits
        batch_size = 20
        for i in range(0, total, batch_size):
            batch = un_embedded[i:i + batch_size]
            for concept in batch:
                try:
                    embedding_service.generate_and_store(db=db, concept=concept)
                    success += 1
                except Exception as e:
                    logger.warning(f"Embedding failed for concept {concept.id}: {e}")
                    failed += 1

        logger.info(
            f"Embedding backfill complete for tenant {tenant_id}: "
            f"{success} success, {failed} failed"
        )
        return {"status": "complete", "embedded": success, "failed": failed}
```

**Important:** Check how `embedding_service.generate_and_store` works in your actual
`embedding_service.py` — the method name may differ. Read the file:
```bash
grep -n "def generate\|def embed\|def store" backend/app/services/embedding_service.py
```
Adjust the method call to match what exists.

### Register the task:

Open `backend/app/worker.py`. Add the new task module to `include`:
```python
celery_app = Celery(
    "dokydoc_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks",
        "app.tasks.ontology_tasks",
        "app.tasks.code_analysis_tasks",
        # No change needed if backfill_embeddings is in ontology_tasks.py
    ]
)
```

### Add admin trigger endpoint:

Open `backend/app/api/endpoints/ontology.py`. Add at the end:

```python
@router.post("/backfill-embeddings", status_code=202)
def trigger_embedding_backfill(
    tenant_id: int = Depends(deps.get_tenant_id),
    current_user: models.User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Trigger background embedding generation for all un-embedded concepts.
    Phase 2: Required before cosine similarity kicks in.
    """
    from app.tasks.ontology_tasks import backfill_embeddings
    task = backfill_embeddings.delay(tenant_id=tenant_id)
    return {"task_id": task.id, "status": "queued",
            "message": "Embedding backfill started. Cosine matching will improve once complete."}
```

---

## P2-06 — Update Threshold Calibration to Include Cosine

**Ticket:** P2-06
**Depends:** P2-03
**File:** `backend/app/services/mapping_service.py`
**Location:** `calibrate_thresholds()` method (lines ~93–140)

### What to add:

Find `calibrate_thresholds` and add cosine threshold calibration. After the existing
`ai_stats` calibration block, add:

```python
# PHASE 2: Calibrate cosine thresholds based on training feedback
cosine_stats = stats.get("by_method", {}).get("cosine_fuzzy", {})
if cosine_stats and cosine_stats.get("total", 0) >= 10:
    acceptance_rate = cosine_stats.get("confirmed", 0) / cosine_stats["total"]
    if acceptance_rate < 0.5:
        # Cosine matches are being rejected — raise the bar
        old_cosine = self.COSINE_HIGH_CONFIDENCE
        self.COSINE_HIGH_CONFIDENCE = min(0.95, old_cosine + 0.03)
        adjustments["cosine_high_confidence"] = {
            "old": old_cosine,
            "new": self.COSINE_HIGH_CONFIDENCE,
            "reason": f"Cosine acceptance rate low ({acceptance_rate:.0%})"
        }
    elif acceptance_rate > 0.9:
        # Cosine matches are almost always correct — lower the bar
        old_cosine = self.COSINE_HIGH_CONFIDENCE
        self.COSINE_HIGH_CONFIDENCE = max(0.75, old_cosine - 0.02)
        adjustments["cosine_high_confidence"] = {
            "old": old_cosine,
            "new": self.COSINE_HIGH_CONFIDENCE,
            "reason": f"Cosine acceptance rate high ({acceptance_rate:.0%})"
        }
```

Also update the `current_thresholds` return value to include cosine:
```python
return {
    "feedback_stats": stats,
    "adjustments": adjustments,
    "current_thresholds": {
        "fuzzy_high_confidence": self.FUZZY_HIGH_CONFIDENCE,
        "fuzzy_medium_confidence": self.FUZZY_MEDIUM_CONFIDENCE,
        "levenshtein_threshold": self.LEVENSHTEIN_THRESHOLD,
        "cosine_high_confidence": self.COSINE_HIGH_CONFIDENCE,    # ADD
        "cosine_medium_confidence": self.COSINE_MEDIUM_CONFIDENCE, # ADD
    },
}
```

---

## P2 COMPLETION CHECKLIST

```
[ ] P2-01: Embedding coverage check — at least some concepts have embedding_vector non-null
[ ] P2-01: Run "SELECT COUNT(*) FROM ontology_concepts WHERE embedding_vector IS NOT NULL"
[ ] P2-02: _cosine_similarity([], []) returns 0.0 (empty vector safe)
[ ] P2-02: _cosine_similarity([1,0,0], [1,0,0]) returns 1.0 (identical vectors)
[ ] P2-02: _cosine_similarity([1,0,0], [0,1,0]) returns 0.0 (orthogonal vectors)
[ ] P2-03: Run a full mapping → logs show "cosine similarity active" (if coverage >= 80%)
[ ] P2-03: Check concept_mappings table — some rows have mapping_method='cosine_fuzzy'
[ ] P2-04: For a tenant with 0 embeddings, logs show coverage warning message
[ ] P2-05: POST /api/v1/ontology/backfill-embeddings → returns 202 with task_id
[ ] P2-05: After backfill task completes, re-run coverage check — count increases
[ ] P2-05: Run mapping again after backfill — more cosine_fuzzy matches than before
[ ] Regression: "Payment" concept still maps to "PaymentProcessor" correctly
[ ] Regression: All existing concept mappings are unchanged (new logic is additive)
```

---

# APPENDIX — Developer Setup & Common Commands

## Running migrations:
```bash
cd backend
alembic upgrade head          # Apply all pending migrations
alembic current               # See current revision
alembic heads                 # See all head revisions
alembic history --verbose     # See full migration history
```

## Checking the migration chain:
Before creating any new migration, verify the chain:
```bash
alembic heads
# Should output exactly ONE head revision
# If multiple heads, you need a merge migration first:
# alembic merge heads -m "merge"
```

## Running tests:
```bash
cd backend
python -m pytest tests/ -v                         # All tests
python -m pytest tests/test_validation.py -v       # Specific file
python -m pytest tests/ -k "test_mismatch" -v      # By name pattern
```

## Checking for cross-tenant leaks (run after every PR):
```bash
psql $DATABASE_URL -c "
  SELECT 'mismatches' as tbl, COUNT(*) FROM mismatches WHERE tenant_id IS NULL
  UNION ALL
  SELECT 'ontology_concepts', COUNT(*) FROM ontology_concepts WHERE tenant_id IS NULL
  UNION ALL
  SELECT 'training_examples', COUNT(*) FROM training_examples WHERE tenant_id IS NULL;
"
# All counts should be 0
```

## Verifying training flywheel is capturing:
```bash
# After running a validation scan:
psql $DATABASE_URL -c "
  SELECT example_type, human_label, COUNT(*)
  FROM training_examples
  GROUP BY example_type, human_label
  ORDER BY example_type, human_label;
"
```

## Checking cosine similarity is active:
```bash
psql $DATABASE_URL -c "
  SELECT mapping_method, COUNT(*), ROUND(AVG(confidence_score)::numeric, 3) as avg_confidence
  FROM concept_mappings
  GROUP BY mapping_method
  ORDER BY COUNT(*) DESC;
"
# Should show rows for: exact, fuzzy, cosine_fuzzy, ai_validated
```

---

## DEPENDENCY ORDER (for sprint planning)

```
P0-01  ─── no deps ─── can start day 1
P0-02  ─── no deps ─── can start day 1
P0-03  ─── no deps ─── can start day 1
P0-04  ─── no deps ─── can start day 1 (run before P0-05)
P0-05  ─── needs P0-04 (migration must run first)
P0-06  ─── no deps ─── can start day 1

P1-01  ─── no deps ─── can start day 1 (parallel with Phase 0)
P1-02  ─── needs P1-01
P1-03  ─── needs P1-02
P1-04  ─── needs P1-02
P1-05  ─── needs P1-06 (UI calls the endpoint)
P1-06  ─── needs P1-02

P2-01  ─── no deps ─── investigation task, start immediately
P2-02  ─── needs P2-01 outcome
P2-03  ─── needs P2-02
P2-04  ─── needs P2-02
P2-05  ─── needs P2-01 outcome
P2-06  ─── needs P2-03
```

## RECOMMENDED PARALLEL ASSIGNMENT

```
Developer A (Backend focus):
  Day 1: P0-04 (indexes), P0-05 (idempotency)
  Day 2: P1-01 (model), P1-02 (CRUD)
  Day 3: P1-03 (validation capture), P1-04 (mapping capture)
  Day 4: P1-06 (feedback endpoint)
  Day 5: P2-01 investigation, P2-02, P2-03

Developer B (Full-stack):
  Day 1: P0-01 (file size), P0-02 (CORS), P0-03 (JWT)
  Day 2: P0-06 (error boundary)
  Day 3: P1-05 (feedback UI)
  Day 4: P2-05 (backfill task + endpoint)
  Day 5: P2-04 (coverage check), P2-06 (threshold calibration)
```

Total wall time: ~5 working days with 2 developers.
