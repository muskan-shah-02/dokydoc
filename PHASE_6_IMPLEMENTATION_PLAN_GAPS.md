# DokyDoc — Phase 6 Gap Completion: Implementation Plan
# Only the MISSING pieces. ~65% of Phase 6 is already built.

---

## HOW TO USE THIS PLAN

- 4 gaps to close: Approval SLA, Audit Checksum, Initiative Health, Multi-Repo Analysis
- Each gap is independent — can be coded in any order
- All changes are non-breaking (new columns, new endpoints, new files)
- Migration chain: `s9d1` (latest) → `s6g1` → `s6g2` → `s6g3`
- Estimated total: ~5-7 days for 1 developer

---

## GAP 1 — Approval SLA Tracking & Escalation

**Problem:** Approvals can sit forever. No deadline, no escalation, no visibility into SLA breaches. Enterprise customers (banks, hospitals) require SLA enforcement on approval workflows.

**What exists:** Full 3-level approval system with role-based checks, auto-approve for low-risk items, frontend UI with tabs.

**What's missing:** SLA deadline on each approval, Celery task to escalate overdue ones, tenant-configurable SLA hours.

### Step 1 — Add SLA fields to Approval model

**File:** `backend/app/models/approval.py`
**After line 71** (`resolved_at` field), add:

```python
    # Phase 6 Gap: SLA tracking
    sla_hours = Column(Integer, nullable=True)  # Hours allowed before escalation
    sla_deadline = Column(DateTime, nullable=True)  # Computed: created_at + sla_hours
    escalated = Column(Boolean, default=False, nullable=False)
    escalated_at = Column(DateTime, nullable=True)
    escalated_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
```

### Step 2 — Migration

**New file:** `backend/alembic/versions/s6g1_approval_sla_fields.py`

```python
"""Add SLA tracking fields to approvals

Revision ID: s6g1
Revises: s9d1
Create Date: 2026-04-09
"""
import sqlalchemy as sa
from alembic import op

revision = "s6g1"
down_revision = "s9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approvals", sa.Column("sla_hours", sa.Integer(), nullable=True))
    op.add_column("approvals", sa.Column("sla_deadline", sa.DateTime(), nullable=True))
    op.add_column("approvals", sa.Column("escalated", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("approvals", sa.Column("escalated_at", sa.DateTime(), nullable=True))
    op.add_column("approvals", sa.Column("escalated_to_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_approval_escalated_to", "approvals", "users", ["escalated_to_id"], ["id"])
    op.create_index("ix_approvals_sla_deadline", "approvals", ["sla_deadline"], postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index("ix_approvals_sla_deadline", table_name="approvals")
    op.drop_constraint("fk_approval_escalated_to", "approvals", type_="foreignkey")
    op.drop_column("approvals", "escalated_to_id")
    op.drop_column("approvals", "escalated_at")
    op.drop_column("approvals", "escalated")
    op.drop_column("approvals", "sla_deadline")
    op.drop_column("approvals", "sla_hours")
```

### Step 3 — Update approval_service.py to set SLA on creation

**File:** `backend/app/services/approval_service.py`
**In `request_approval()` method (around line 60-70)**, after the approval is created, compute SLA:

```python
# After: approval = crud.approval.create(db, ...)
# Add:
tenant = crud.tenant.get(db, id=tenant_id)
default_sla = (tenant.settings or {}).get("approval_sla_hours", 48)  # Default 48h
sla_hours = default_sla

if approval.approval_level >= 3:
    sla_hours = default_sla * 2  # Executive approvals get double time

approval.sla_hours = sla_hours
approval.sla_deadline = approval.created_at + timedelta(hours=sla_hours)
db.commit()
```

Add import at top: `from datetime import timedelta`

### Step 4 — Celery escalation task

**New file:** `backend/app/tasks/approval_tasks.py`

```python
"""
Phase 6 Gap: Approval SLA escalation task.
Runs hourly via Celery beat. Finds overdue approvals and escalates.
"""
import logging
from datetime import datetime

from app.db.session import SessionLocal
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="check_approval_slas", bind=True, max_retries=1)
def check_approval_slas(self):
    """
    Finds pending approvals where sla_deadline < now() and escalated = False.
    For each: marks escalated, notifies next-level approver.
    """
    db = SessionLocal()
    try:
        from app import crud
        from app.services.audit_service import log_audit

        now = datetime.utcnow()

        # Query overdue, non-escalated approvals
        overdue = (
            db.query(crud.approval.model)
            .filter(
                crud.approval.model.status == "pending",
                crud.approval.model.escalated == False,
                crud.approval.model.sla_deadline.isnot(None),
                crud.approval.model.sla_deadline < now,
            )
            .all()
        )

        escalated_count = 0
        for approval in overdue:
            try:
                approval.escalated = True
                approval.escalated_at = now

                # Find next-level approver (CXO for level 1-2, admin for level 3)
                escalate_to = _find_escalation_target(db, approval)
                if escalate_to:
                    approval.escalated_to_id = escalate_to.id

                    # Send notification
                    from app.services.notification_service import create_notification
                    create_notification(
                        db,
                        tenant_id=approval.tenant_id,
                        user_id=escalate_to.id,
                        title=f"Overdue approval: {approval.entity_name or approval.entity_type}",
                        message=f"Approval #{approval.id} has breached its {approval.sla_hours}h SLA.",
                        notification_type="approval_escalation",
                        link=f"/dashboard/approvals",
                    )

                log_audit(
                    db,
                    tenant_id=approval.tenant_id,
                    action="update",
                    resource_type="approval",
                    resource_id=approval.id,
                    description=f"Approval escalated after {approval.sla_hours}h SLA breach",
                    status="warning",
                )

                escalated_count += 1
            except Exception as e:
                logger.warning(f"Failed to escalate approval {approval.id}: {e}")

        db.commit()
        logger.info(f"SLA check complete: {escalated_count}/{len(overdue)} approvals escalated")
        return {"overdue": len(overdue), "escalated": escalated_count}

    except Exception as e:
        logger.error(f"SLA check task failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _find_escalation_target(db, approval):
    """Find the best user to escalate to based on approval level."""
    from app import crud

    # Get users with CXO or ADMIN role in same tenant
    users = crud.user.get_multi_by_tenant(db, tenant_id=approval.tenant_id)
    for user in users:
        roles = user.roles or []
        if "CXO" in roles and user.id != approval.requested_by_id:
            return user
    for user in users:
        roles = user.roles or []
        if "ADMIN" in roles and user.id != approval.requested_by_id:
            return user
    return None
```

### Step 5 — Register task in worker.py

**File:** `backend/app/worker.py`
**Line 11-16**, add to the include list:

```python
include=[
    "app.tasks",
    "app.tasks.ontology_tasks",
    "app.tasks.code_analysis_tasks",
    "app.tasks.embedding_tasks",
    "app.tasks.approval_tasks",  # Phase 6 Gap: SLA escalation
]
```

### Step 6 — Add Celery beat schedule

**File:** `backend/app/worker.py`
**After the include list**, add beat schedule (if not exists, create it):

```python
celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "check-approval-slas": {
        "task": "check_approval_slas",
        "schedule": 3600.0,  # Every hour
    },
}
```

### Step 7 — Update approval schema for SLA fields

**File:** `backend/app/schemas/approval.py`
**Add to `ApprovalResponse`:**

```python
    sla_hours: Optional[int] = None
    sla_deadline: Optional[datetime] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None
```

### Verification
1. Create approval → check `sla_deadline` is set (created_at + 48h default)
2. Set tenant `approval_sla_hours` to 1 → create approval → deadline is 1h from now
3. Run `check_approval_slas` manually → overdue approvals get `escalated=True`
4. Verify notification created for escalation target
5. Verify audit log entry for escalation

---

## GAP 2 — Audit Log Tamper-Evidence (Checksum Hash Chain)

**Problem:** Current audit logs can be silently modified or deleted by anyone with DB access. SOC 2 auditors and regulated industry customers require proof that logs haven't been tampered with. A hash chain makes any modification detectable.

**What exists:** Full audit logging (middleware + service), analytics, anomaly detection, compliance reports, export.

**What's missing:** Each log entry should contain a SHA-256 hash of itself + the previous entry's hash, forming an unbreakable chain. Plus: retention policy field and legal hold flag.

### Step 1 — Add checksum fields to AuditLog model

**File:** `backend/app/models/audit_log.py`
**After line 71** (`created_at` field), add:

```python
    # Phase 6 Gap: Tamper-evidence hash chain
    entry_hash = Column(String(64), nullable=True, index=True)      # SHA-256 of this entry
    previous_hash = Column(String(64), nullable=True)                # Hash of previous entry

    # Phase 6 Gap: Retention policy
    retained_until = Column(DateTime, nullable=True)                 # Legal hold — cannot delete before this date
```

### Step 2 — Migration

**New file:** `backend/alembic/versions/s6g2_audit_checksum_chain.py`

```python
"""Add hash chain and retention fields to audit_logs

Revision ID: s6g2
Revises: s6g1
Create Date: 2026-04-09
"""
import sqlalchemy as sa
from alembic import op

revision = "s6g2"
down_revision = "s6g1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("entry_hash", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("retained_until", sa.DateTime(), nullable=True))
    op.create_index("ix_audit_logs_entry_hash", "audit_logs", ["entry_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entry_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "retained_until")
    op.drop_column("audit_logs", "previous_hash")
    op.drop_column("audit_logs", "entry_hash")
```

### Step 3 — Hash computation helper

**File:** `backend/app/services/audit_service.py`
**Add at top of file:**

```python
import hashlib
import json
```

**Add new function before `log_audit()`:**

```python
def _compute_entry_hash(
    tenant_id: int,
    action: str,
    resource_type: str,
    user_id: int | None,
    description: str,
    created_at: str,
    previous_hash: str | None,
) -> str:
    """
    SHA-256 hash of entry fields + previous entry's hash.
    Forms an append-only hash chain. Any deletion or modification
    of a prior entry breaks the chain (detectable by verify endpoint).
    """
    payload = json.dumps({
        "tenant_id": tenant_id,
        "action": action,
        "resource_type": resource_type,
        "user_id": user_id,
        "description": description,
        "created_at": created_at,
        "previous_hash": previous_hash or "GENESIS",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

### Step 4 — Update log_audit() to compute and store hash

**File:** `backend/app/services/audit_service.py`
**Inside `log_audit()`, after the audit entry is created but before `db.commit()`**, add:

```python
    # Phase 6 Gap: Compute hash chain
    try:
        # Get the most recent entry's hash for this tenant
        from app.models.audit_log import AuditLog
        prev_entry = (
            db.query(AuditLog.entry_hash)
            .filter(AuditLog.tenant_id == tenant_id, AuditLog.entry_hash.isnot(None))
            .order_by(AuditLog.id.desc())
            .first()
        )
        previous_hash = prev_entry.entry_hash if prev_entry else None

        entry_hash = _compute_entry_hash(
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            user_id=getattr(user, "id", None) if user else None,
            description=description,
            created_at=audit_entry.created_at.isoformat() if audit_entry.created_at else "",
            previous_hash=previous_hash,
        )
        audit_entry.entry_hash = entry_hash
        audit_entry.previous_hash = previous_hash
    except Exception:
        pass  # Never let hash computation break audit logging
```

### Step 5 — Chain integrity verification endpoint

**File:** `backend/app/api/endpoints/audit.py`
**Add new endpoint:**

```python
@router.get("/verify-integrity")
def verify_audit_integrity(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(require_permission(Permission.AUDIT_EXPORT)),
):
    """
    Walks the hash chain and verifies every entry.
    Returns: { valid: bool, total_checked: int, broken_at_id: int | None }
    """
    from app.models.audit_log import AuditLog
    from app.services.audit_service import _compute_entry_hash

    entries = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id, AuditLog.entry_hash.isnot(None))
        .order_by(AuditLog.id.asc())
        .all()
    )

    if not entries:
        return {"valid": True, "total_checked": 0, "broken_at_id": None}

    for i, entry in enumerate(entries):
        expected_previous = entries[i - 1].entry_hash if i > 0 else None

        # Verify previous_hash pointer
        if entry.previous_hash != expected_previous:
            return {"valid": False, "total_checked": i + 1, "broken_at_id": entry.id,
                    "reason": "previous_hash mismatch"}

        # Recompute and verify entry_hash
        recomputed = _compute_entry_hash(
            tenant_id=entry.tenant_id,
            action=entry.action,
            resource_type=entry.resource_type,
            user_id=entry.user_id,
            description=entry.description,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
            previous_hash=entry.previous_hash,
        )
        if recomputed != entry.entry_hash:
            return {"valid": False, "total_checked": i + 1, "broken_at_id": entry.id,
                    "reason": "entry_hash recomputation mismatch"}

    return {"valid": True, "total_checked": len(entries), "broken_at_id": None}
```

### Step 6 — Legal hold endpoint

**File:** `backend/app/api/endpoints/audit.py`
**Add:**

```python
@router.post("/legal-hold")
def set_legal_hold(
    start_date: datetime,
    end_date: datetime,
    retained_until: datetime,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(require_permission(Permission.AUDIT_EXPORT)),
):
    """
    Marks audit log entries within a date range as legally held.
    Held entries cannot be deleted by any retention policy cleanup.
    Used during litigation, regulatory investigation, or SOC 2 audit.
    """
    from app.models.audit_log import AuditLog

    count = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date,
        )
        .update({"retained_until": retained_until})
    )
    db.commit()
    return {"held_entries": count, "retained_until": retained_until.isoformat()}
```

### Verification
1. Create 5 audit entries → each has `entry_hash` and `previous_hash` set
2. `GET /audit/verify-integrity` → `{"valid": true, "total_checked": 5}`
3. Manually UPDATE one entry's description via SQL → re-run verify → `{"valid": false, "broken_at_id": X}`
4. `POST /audit/legal-hold` for a date range → entries have `retained_until` set

---

## GAP 3 — Initiative Health Score & Cross-Asset Reporting

**Problem:** Initiatives exist but there's no way to see "how healthy is this initiative?" CXOs need a single number + breakdown to track progress across all documents and repos in an initiative.

**What exists:** Initiative CRUD, asset linking (documents + repos), endpoints for list/create/update/delete/assets.

**What's missing:** Health score computation, validation summary across all assets, BOE gap report.

### Step 1 — Add health fields to Initiative model

**File:** `backend/app/models/initiative.py`
**After line 24** (`updated_at`), add:

```python
    # Phase 6 Gap: Health scoring
    health_score = Column(Float, nullable=True)                # 0.0 - 100.0
    health_status = Column(String(20), nullable=True)          # healthy / warning / critical
    health_computed_at = Column(DateTime(timezone=True), nullable=True)
    target_completion_date = Column(Date, nullable=True)
```

Add import at top: `from sqlalchemy import Date`

### Step 2 — Migration

**New file:** `backend/alembic/versions/s6g3_initiative_health_fields.py`

```python
"""Add health score fields to initiatives

Revision ID: s6g3
Revises: s6g2
Create Date: 2026-04-09
"""
import sqlalchemy as sa
from alembic import op

revision = "s6g3"
down_revision = "s6g2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("initiatives", sa.Column("health_score", sa.Float(), nullable=True))
    op.add_column("initiatives", sa.Column("health_status", sa.String(20), nullable=True))
    op.add_column("initiatives", sa.Column("health_computed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("initiatives", sa.Column("target_completion_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("initiatives", "target_completion_date")
    op.drop_column("initiatives", "health_computed_at")
    op.drop_column("initiatives", "health_status")
    op.drop_column("initiatives", "health_score")
```

### Step 3 — Initiative Health Service

**New file:** `backend/app/services/initiative_health_service.py`

```python
"""
Phase 6 Gap: Initiative Health Score Computation.

Composite score from 5 dimensions:
- Validation coverage (30%) — % of linked docs with completed validation
- Mismatch resolution (30%) — % of mismatches resolved across all assets
- Document completion (20%) — % of linked docs in "completed" status
- Code analysis coverage (10%) — % of linked repos fully analyzed
- Approval backlog (10%) — penalize if pending approvals > 5

Score: 0.0 - 100.0
Status: healthy (>= 70), warning (40-69), critical (< 40)
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

WEIGHTS = {
    "validation": 0.30,
    "mismatches": 0.30,
    "documents": 0.20,
    "code_analysis": 0.10,
    "approvals": 0.10,
}


def compute_health_score(db: Session, initiative_id: int, tenant_id: int) -> dict:
    """
    Computes health score for an initiative. Returns:
    {
        "health_score": 72.5,
        "health_status": "healthy",
        "breakdown": { "validation": 80.0, "mismatches": 65.0, ... },
        "stats": { "total_docs": 3, "total_repos": 2, ... }
    }
    """
    from app import crud
    from app.models.initiative_asset import InitiativeAsset

    # Load all active assets
    assets = crud.initiative_asset.get_by_initiative(db, initiative_id=initiative_id, tenant_id=tenant_id)
    doc_ids = [a.asset_id for a in assets if a.asset_type == "DOCUMENT"]
    repo_ids = [a.asset_id for a in assets if a.asset_type == "REPOSITORY"]

    if not doc_ids and not repo_ids:
        return {"health_score": 0.0, "health_status": "critical",
                "breakdown": {k: 0.0 for k in WEIGHTS}, "stats": {}}

    # 1. Validation coverage: how many docs have at least 1 completed validation?
    validated_count = 0
    for doc_id in doc_ids:
        try:
            runs = crud.analysis_result.get_multi(db, tenant_id=tenant_id)
            # Check if any mismatch or analysis_run references this doc
            from app.models.mismatch import Mismatch
            has_validation = db.query(Mismatch).filter(
                Mismatch.document_id == doc_id, Mismatch.tenant_id == tenant_id
            ).first()
            if has_validation:
                validated_count += 1
        except Exception:
            pass
    validation_score = (validated_count / len(doc_ids) * 100) if doc_ids else 0

    # 2. Mismatch resolution rate
    from app.models.mismatch import Mismatch
    total_mismatches = 0
    resolved_mismatches = 0
    for doc_id in doc_ids:
        try:
            all_m = db.query(Mismatch).filter(
                Mismatch.document_id == doc_id, Mismatch.tenant_id == tenant_id
            ).count()
            resolved_m = db.query(Mismatch).filter(
                Mismatch.document_id == doc_id, Mismatch.tenant_id == tenant_id,
                Mismatch.status == "resolved",
            ).count()
            total_mismatches += all_m
            resolved_mismatches += resolved_m
        except Exception:
            pass
    mismatch_score = (resolved_mismatches / total_mismatches * 100) if total_mismatches > 0 else 100

    # 3. Document completion: % in "completed" status
    completed_docs = 0
    for doc_id in doc_ids:
        try:
            doc = crud.document.get(db, id=doc_id, tenant_id=tenant_id)
            if doc and doc.status in ("completed", "published"):
                completed_docs += 1
        except Exception:
            pass
    doc_score = (completed_docs / len(doc_ids) * 100) if doc_ids else 0

    # 4. Code analysis coverage: % of repos fully analyzed
    analyzed_repos = 0
    for repo_id in repo_ids:
        try:
            repo = crud.repository.get(db, id=repo_id, tenant_id=tenant_id)
            if repo and repo.status in ("analyzed", "completed"):
                analyzed_repos += 1
        except Exception:
            pass
    code_score = (analyzed_repos / len(repo_ids) * 100) if repo_ids else 0

    # 5. Approval backlog: penalize if > 5 pending
    from app.models.approval import Approval
    pending_approvals = db.query(Approval).filter(
        Approval.tenant_id == tenant_id, Approval.status == "pending"
    ).count()
    approval_score = max(0, 100 - (pending_approvals * 10))  # -10 per pending, floor 0

    # Composite
    breakdown = {
        "validation": round(validation_score, 1),
        "mismatches": round(mismatch_score, 1),
        "documents": round(doc_score, 1),
        "code_analysis": round(code_score, 1),
        "approvals": round(approval_score, 1),
    }

    health_score = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)
    health_score = round(health_score, 1)

    if health_score >= 70:
        health_status = "healthy"
    elif health_score >= 40:
        health_status = "warning"
    else:
        health_status = "critical"

    stats = {
        "total_docs": len(doc_ids),
        "total_repos": len(repo_ids),
        "validated_docs": validated_count,
        "total_mismatches": total_mismatches,
        "resolved_mismatches": resolved_mismatches,
        "open_mismatches": total_mismatches - resolved_mismatches,
        "completed_docs": completed_docs,
        "analyzed_repos": analyzed_repos,
        "pending_approvals": pending_approvals,
    }

    return {
        "health_score": health_score,
        "health_status": health_status,
        "breakdown": breakdown,
        "stats": stats,
    }


def update_initiative_health(db: Session, initiative_id: int, tenant_id: int) -> None:
    """Computes and persists health score on the initiative record."""
    result = compute_health_score(db, initiative_id, tenant_id)

    initiative = crud.initiative.get(db, id=initiative_id, tenant_id=tenant_id)
    if initiative:
        initiative.health_score = result["health_score"]
        initiative.health_status = result["health_status"]
        initiative.health_computed_at = datetime.utcnow()
        db.commit()

    from app import crud
```

### Step 4 — New initiative endpoints

**File:** `backend/app/api/endpoints/initiatives.py`
**Add these endpoints after the existing ones (after line 186):**

```python
@router.get("/{initiative_id}/health")
def get_initiative_health(
    initiative_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(get_current_user),
):
    """
    Returns composite health score with breakdown by dimension.
    Recomputes live — not cached (cheap: DB queries only, no AI calls).
    """
    from app.services.initiative_health_service import compute_health_score

    initiative = crud.initiative.get(db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(404, "Initiative not found")

    return compute_health_score(db, initiative_id, tenant_id)


@router.get("/{initiative_id}/validation-summary")
def get_initiative_validation_summary(
    initiative_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(get_current_user),
):
    """
    Aggregates validation results across ALL documents linked to this initiative.
    Returns: mismatch counts by severity, by type, top unresolved issues.
    """
    from app.models.mismatch import Mismatch

    assets = crud.initiative_asset.get_by_initiative(db, initiative_id=initiative_id, tenant_id=tenant_id)
    doc_ids = [a.asset_id for a in assets if a.asset_type == "DOCUMENT"]

    if not doc_ids:
        return {"total": 0, "by_severity": {}, "by_type": {}, "top_issues": []}

    mismatches = (
        db.query(Mismatch)
        .filter(Mismatch.document_id.in_(doc_ids), Mismatch.tenant_id == tenant_id)
        .all()
    )

    by_severity = {}
    by_type = {}
    open_issues = []

    for m in mismatches:
        sev = m.severity or "unknown"
        by_severity[sev] = by_severity.get(sev, 0) + 1

        mtype = m.mismatch_type or "unknown"
        by_type[mtype] = by_type.get(mtype, 0) + 1

        if m.status != "resolved":
            open_issues.append({
                "id": m.id,
                "title": m.title,
                "severity": m.severity,
                "type": m.mismatch_type,
                "document_id": m.document_id,
                "status": m.status,
            })

    # Sort open issues: critical first
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    open_issues.sort(key=lambda x: severity_order.get(x.get("severity", ""), 99))

    return {
        "total": len(mismatches),
        "open": len(open_issues),
        "resolved": len(mismatches) - len(open_issues),
        "by_severity": by_severity,
        "by_type": by_type,
        "top_issues": open_issues[:20],
    }


@router.get("/{initiative_id}/gap-report")
def get_initiative_gap_report(
    initiative_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(get_current_user),
):
    """
    Shows BOE gaps across all initiative assets:
    - Document concepts with no code match (missing implementations)
    - Code concepts with no document match (undocumented features)
    """
    from app.models.ontology_concept import OntologyConcept
    from app.models.concept_mapping import ConceptMapping  # if exists
    from app import crud

    assets = crud.initiative_asset.get_by_initiative(db, initiative_id=initiative_id, tenant_id=tenant_id)
    doc_ids = [a.asset_id for a in assets if a.asset_type == "DOCUMENT"]
    repo_ids = [a.asset_id for a in assets if a.asset_type == "REPOSITORY"]

    # Get all doc-sourced and code-sourced concepts for this tenant
    doc_concepts = (
        db.query(OntologyConcept)
        .filter(OntologyConcept.tenant_id == tenant_id, OntologyConcept.source_type == "document")
        .all()
    )
    code_concepts = (
        db.query(OntologyConcept)
        .filter(OntologyConcept.tenant_id == tenant_id, OntologyConcept.source_type == "code")
        .all()
    )

    # Get all confirmed mappings
    confirmed_mappings = crud.concept_mapping.get_confirmed(db, tenant_id=tenant_id)
    mapped_doc_names = {m.document_concept.name.lower() for m in confirmed_mappings if m.document_concept}
    mapped_code_names = {m.code_concept.name.lower() for m in confirmed_mappings if m.code_concept}

    # Gaps
    doc_only = [
        {"name": c.name, "description": c.description, "concept_id": c.id}
        for c in doc_concepts
        if c.name and c.name.lower() not in mapped_doc_names
    ]
    code_only = [
        {"name": c.name, "description": c.description, "concept_id": c.id}
        for c in code_concepts
        if c.name and c.name.lower() not in mapped_code_names
    ]

    return {
        "initiative_id": initiative_id,
        "total_doc_concepts": len(doc_concepts),
        "total_code_concepts": len(code_concepts),
        "confirmed_mappings": len(confirmed_mappings),
        "document_only_gaps": doc_only[:50],      # Missing implementations
        "code_only_gaps": code_only[:50],          # Undocumented features
        "coverage_pct": round(
            len(confirmed_mappings) / max(len(doc_concepts), 1) * 100, 1
        ),
    }
```

### Step 5 — Update initiative schema

**File:** `backend/app/schemas/initiative.py`
**Add to `InitiativeResponse` and `InitiativeWithAssets`:**

```python
    health_score: Optional[float] = None
    health_status: Optional[str] = None
    health_computed_at: Optional[datetime] = None
    target_completion_date: Optional[date] = None
```

**Add to `InitiativeUpdate`:**

```python
    target_completion_date: Optional[date] = None
```

### Verification
1. Link 2 docs + 1 repo to initiative → `GET /initiatives/{id}/health` → returns score with breakdown
2. Score reflects real data: if 0 mismatches resolved, mismatch dimension = 0%
3. `GET /initiatives/{id}/validation-summary` → shows mismatches grouped by severity
4. `GET /initiatives/{id}/gap-report` → shows unmatched doc concepts and unmatched code concepts

---

## GAP 4 — Multi-Repository Analysis Within Initiatives

**Problem:** A single BRD often spans 2-3 microservices. Currently there's no way to run cross-repo analysis to find shared concepts, data ownership conflicts, or interface mismatches between repos within the same initiative.

**What exists:** Initiative asset linking (repos can be linked). Cross-project mapping exists between tenants (`cross_project_mapping_service.py`) but NOT within a tenant across repos.

**What's missing:** An endpoint that triggers BOE cross-graph mapping across all repos in an initiative and returns a unified view.

### Step 1 — New endpoint for cross-repo analysis

**File:** `backend/app/api/endpoints/initiatives.py`
**Add:**

```python
@router.post("/{initiative_id}/cross-repo-analysis")
def trigger_cross_repo_analysis(
    initiative_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user=Depends(get_current_user),
):
    """
    Runs BOE cross-graph mapping across ALL repos linked to this initiative.
    Detects:
    - Shared concepts (same entity name in 2+ repos)
    - Interface contracts (one repo calls another's API)
    - Data ownership conflicts (2 repos write to same logical entity)
    Returns results synchronously (DB queries + existing mapping, no new AI calls).
    """
    from app.models.ontology_concept import OntologyConcept
    from app.models.code_component import CodeComponent

    assets = crud.initiative_asset.get_by_initiative(db, initiative_id=initiative_id, tenant_id=tenant_id)
    repo_ids = [a.asset_id for a in assets if a.asset_type == "REPOSITORY"]

    if len(repo_ids) < 2:
        return {"message": "Need at least 2 repositories for cross-repo analysis", "repos": len(repo_ids)}

    # Collect concepts per repo
    repo_concepts = {}
    for repo_id in repo_ids:
        repo = crud.repository.get(db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            continue

        # Get code components for this repo
        components = (
            db.query(CodeComponent)
            .filter(CodeComponent.repository_id == repo_id, CodeComponent.tenant_id == tenant_id)
            .all()
        )
        component_ids = [c.id for c in components]

        # Get concepts sourced from these components
        concepts = (
            db.query(OntologyConcept)
            .filter(
                OntologyConcept.tenant_id == tenant_id,
                OntologyConcept.source_type == "code",
                OntologyConcept.source_component_id.in_(component_ids),
            )
            .all()
        ) if component_ids else []

        repo_concepts[repo_id] = {
            "repo_name": repo.name,
            "concept_names": {c.name.lower(): c for c in concepts if c.name},
            "component_count": len(components),
        }

    # Find shared concepts (same name in 2+ repos)
    all_concept_names = {}
    for repo_id, data in repo_concepts.items():
        for name in data["concept_names"]:
            if name not in all_concept_names:
                all_concept_names[name] = []
            all_concept_names[name].append(data["repo_name"])

    shared_concepts = [
        {"concept_name": name, "found_in_repos": repos, "repo_count": len(repos)}
        for name, repos in all_concept_names.items()
        if len(repos) >= 2
    ]
    shared_concepts.sort(key=lambda x: x["repo_count"], reverse=True)

    # Find unique-to-repo concepts
    unique_concepts = {}
    for repo_id, data in repo_concepts.items():
        unique = [
            name for name in data["concept_names"]
            if len(all_concept_names.get(name, [])) == 1
        ]
        unique_concepts[data["repo_name"]] = unique

    # Update initiative health after cross-repo analysis
    from app.services.initiative_health_service import update_initiative_health
    try:
        update_initiative_health(db, initiative_id, tenant_id)
    except Exception:
        pass

    return {
        "initiative_id": initiative_id,
        "repos_analyzed": len(repo_concepts),
        "total_concepts_across_repos": len(all_concept_names),
        "shared_concepts": shared_concepts[:30],
        "shared_concept_count": len(shared_concepts),
        "unique_per_repo": {k: len(v) for k, v in unique_concepts.items()},
        "potential_conflicts": [
            s for s in shared_concepts
            if s["repo_count"] >= 2
        ][:10],
    }
```

### Verification
1. Link 2+ repos to an initiative → `POST /initiatives/{id}/cross-repo-analysis`
2. Response shows shared concepts found across repos
3. Unique-per-repo counts make sense (concepts in only 1 repo)
4. Initiative health_score gets updated after analysis

---

## Summary — All 4 Gaps

| Gap | Files Changed | New Files | Migration |
|-----|---------------|-----------|-----------|
| 1. Approval SLA | `approval.py`, `approval_service.py`, `schemas/approval.py`, `worker.py` | `tasks/approval_tasks.py` | `s6g1` |
| 2. Audit Checksum | `audit_log.py`, `audit_service.py`, `endpoints/audit.py` | — | `s6g2` |
| 3. Initiative Health | `initiative.py`, `schemas/initiative.py`, `endpoints/initiatives.py` | `services/initiative_health_service.py` | `s6g3` |
| 4. Multi-Repo Analysis | `endpoints/initiatives.py` | — | — |

**Migration chain:** `s9d1` → `s6g1` → `s6g2` → `s6g3`

**Total new files:** 2 (`approval_tasks.py`, `initiative_health_service.py`)
**Total modified files:** ~10
**Estimated effort:** 5-7 days for 1 developer

### Run After Implementation
```bash
cd /home/user/dokydoc/backend
alembic upgrade head
pytest tests/ -x
```

