"""
Phase 6: Compliance Library API endpoints.

Endpoints:
  GET  /compliance/library                 — list all frameworks (system + own custom)
  POST /compliance/library                 — create tenant-custom framework
  GET  /tenants/me/compliance              — get tenant's active framework selections
  PUT  /tenants/me/compliance              — replace full selection set
  POST /tenants/me/compliance/{fid}        — add single framework
  DELETE /tenants/me/compliance/{fid}      — remove single framework
"""
from datetime import datetime
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.compliance_framework import ComplianceFramework, TenantComplianceSelection

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class ComplianceFrameworkOut(BaseModel):
    id: int
    code: str
    name: str
    category: str
    geography: Optional[str]
    description: Optional[str]
    applicable_industries: Optional[List[str]]
    is_system: bool
    is_selected: bool = False  # populated per-tenant in responses

    class Config:
        from_attributes = True


class ComplianceSelectionOut(BaseModel):
    framework: ComplianceFrameworkOut
    notes: Optional[str]
    selected_at: datetime

    class Config:
        from_attributes = True


class CreateCustomFrameworkRequest(BaseModel):
    code: str
    name: str
    category: str
    geography: Optional[str] = None
    description: Optional[str] = None
    applicable_industries: Optional[List[str]] = None


class UpdateSelectionsRequest(BaseModel):
    framework_ids: List[int]


class AddFrameworkRequest(BaseModel):
    notes: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _framework_to_out(fw: ComplianceFramework, selected_ids: set) -> Dict[str, Any]:
    return {
        "id": fw.id,
        "code": fw.code,
        "name": fw.name,
        "category": fw.category,
        "geography": fw.geography,
        "description": fw.description,
        "applicable_industries": fw.applicable_industries or [],
        "is_system": fw.is_system,
        "is_selected": fw.id in selected_ids,
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/library")
def list_compliance_library(
    industry: Optional[str] = Query(None, description="Filter by industry slug"),
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Search by code or name keyword"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Return all compliance frameworks visible to this tenant:
    system-wide ones + their own custom ones.
    Each framework carries `is_selected` flag.
    """
    tenant_id = current_user.tenant_id

    # Load tenant's current selections
    selections = db.query(TenantComplianceSelection).filter(
        TenantComplianceSelection.tenant_id == tenant_id
    ).all()
    selected_ids = {s.framework_id for s in selections}

    # Query: system frameworks + tenant-custom
    query = db.query(ComplianceFramework).filter(
        (ComplianceFramework.is_system == True) |
        (ComplianceFramework.tenant_id == tenant_id)
    )

    if industry:
        # JSONB contains operator: applicable_industries @> '["slug"]'
        query = query.filter(
            ComplianceFramework.applicable_industries.contains([industry])
        )
    if category:
        query = query.filter(ComplianceFramework.category.ilike(f"%{category}%"))
    if q:
        query = query.filter(
            (ComplianceFramework.code.ilike(f"%{q}%")) |
            (ComplianceFramework.name.ilike(f"%{q}%"))
        )

    frameworks = query.order_by(ComplianceFramework.category, ComplianceFramework.name).all()

    return {
        "frameworks": [_framework_to_out(fw, selected_ids) for fw in frameworks],
        "total": len(frameworks),
        "selected_count": len(selected_ids),
    }


@router.post("/library", status_code=201)
def create_custom_framework(
    payload: CreateCustomFrameworkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a tenant-custom compliance framework."""
    tenant_id = current_user.tenant_id

    # Check for duplicate code within this tenant
    existing = db.query(ComplianceFramework).filter(
        ComplianceFramework.code == payload.code.upper(),
        ComplianceFramework.tenant_id == tenant_id,
    ).first()
    if existing:
        raise HTTPException(400, detail=f"Framework code '{payload.code}' already exists.")

    fw = ComplianceFramework(
        code=payload.code.upper(),
        name=payload.name,
        category=payload.category,
        geography=payload.geography,
        description=payload.description,
        applicable_industries=payload.applicable_industries or [],
        is_system=False,
        tenant_id=tenant_id,
        created_at=datetime.utcnow(),
    )
    db.add(fw)
    db.commit()
    db.refresh(fw)
    return _framework_to_out(fw, set())


@router.get("/tenants/me/compliance")
def get_tenant_compliance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return tenant's active compliance framework selections."""
    tenant_id = current_user.tenant_id
    selections = (
        db.query(TenantComplianceSelection)
        .filter(TenantComplianceSelection.tenant_id == tenant_id)
        .all()
    )
    return {
        "tenant_id": tenant_id,
        "selections": [
            {
                "id": s.id,
                "framework_id": s.framework_id,
                "code": s.framework.code,
                "name": s.framework.name,
                "category": s.framework.category,
                "geography": s.framework.geography,
                "notes": s.notes,
                "selected_at": s.selected_at.isoformat(),
            }
            for s in selections
        ],
    }


@router.put("/tenants/me/compliance")
def set_tenant_compliance(
    payload: UpdateSelectionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Replace the tenant's full compliance selection.
    Existing selections not in the new list are removed.
    """
    tenant_id = current_user.tenant_id

    # Validate all framework IDs exist and are visible to this tenant
    for fid in payload.framework_ids:
        fw = db.query(ComplianceFramework).filter(
            ComplianceFramework.id == fid,
            (ComplianceFramework.is_system == True) | (ComplianceFramework.tenant_id == tenant_id)
        ).first()
        if not fw:
            raise HTTPException(404, detail=f"Framework {fid} not found.")

    # Delete existing selections
    db.query(TenantComplianceSelection).filter(
        TenantComplianceSelection.tenant_id == tenant_id
    ).delete(synchronize_session=False)

    # Insert new selections
    now = datetime.utcnow()
    for fid in payload.framework_ids:
        db.add(TenantComplianceSelection(
            tenant_id=tenant_id,
            framework_id=fid,
            selected_at=now,
        ))

    db.commit()

    # Also update tenant.settings with compliance_codes for fast Gemini context
    _sync_compliance_to_settings(db, tenant_id)

    return {"tenant_id": tenant_id, "selected_count": len(payload.framework_ids)}


@router.post("/tenants/me/compliance/{framework_id}", status_code=201)
def add_compliance(
    framework_id: int,
    payload: AddFrameworkRequest = AddFrameworkRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a single compliance framework to the tenant's selection."""
    tenant_id = current_user.tenant_id

    fw = db.query(ComplianceFramework).filter(
        ComplianceFramework.id == framework_id,
        (ComplianceFramework.is_system == True) | (ComplianceFramework.tenant_id == tenant_id)
    ).first()
    if not fw:
        raise HTTPException(404, detail="Framework not found.")

    existing = db.query(TenantComplianceSelection).filter(
        TenantComplianceSelection.tenant_id == tenant_id,
        TenantComplianceSelection.framework_id == framework_id,
    ).first()
    if existing:
        return {"message": "Already selected", "framework_id": framework_id}

    db.add(TenantComplianceSelection(
        tenant_id=tenant_id,
        framework_id=framework_id,
        notes=payload.notes,
        selected_at=datetime.utcnow(),
    ))
    db.commit()
    _sync_compliance_to_settings(db, tenant_id)
    return {"message": "Added", "framework_id": framework_id, "code": fw.code}


@router.delete("/tenants/me/compliance/{framework_id}")
def remove_compliance(
    framework_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a single compliance framework from the tenant's selection."""
    tenant_id = current_user.tenant_id
    deleted = db.query(TenantComplianceSelection).filter(
        TenantComplianceSelection.tenant_id == tenant_id,
        TenantComplianceSelection.framework_id == framework_id,
    ).delete(synchronize_session=False)
    db.commit()
    if deleted:
        _sync_compliance_to_settings(db, tenant_id)
    return {"message": "Removed", "framework_id": framework_id}


# ─── Internal helper ──────────────────────────────────────────────────────────

def _sync_compliance_to_settings(db: Session, tenant_id: int):
    """
    Write selected compliance framework codes into tenant.settings['compliance_frameworks']
    so Gemini prompt_context can read them without a JOIN.
    Also invalidates the compressed_context cache.
    """
    try:
        from app.models.tenant import Tenant
        from sqlalchemy import text

        selections = db.query(TenantComplianceSelection).filter(
            TenantComplianceSelection.tenant_id == tenant_id
        ).all()
        codes = [s.framework.code for s in selections]

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            settings = dict(tenant.settings or {})
            settings["compliance_frameworks"] = codes
            # Invalidate compressed context cache so next Gemini call rebuilds it
            settings.pop("compressed_context", None)
            db.execute(
                text("UPDATE tenants SET settings = :s WHERE id = :id"),
                {"s": __import__("json").dumps(settings), "id": tenant_id}
            )
            db.commit()
    except Exception:
        pass  # Non-critical — next prompt rebuild will re-sync
