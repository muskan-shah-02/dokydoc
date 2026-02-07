"""
SPRINT 3: Initiative (Governance) API Endpoints

Initiatives group documents and code repositories into projects,
enabling cross-system validation and traceability.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app import crud, models
from app.api import deps
from app.db.session import get_db
from app.schemas.initiative import (
    InitiativeCreate, InitiativeUpdate, InitiativeResponse,
    InitiativeWithAssets, InitiativeAssetCreate, InitiativeAssetResponse
)
from app.core.logging import get_logger

logger = get_logger("api.initiatives")

router = APIRouter()


# ============================================================
# INITIATIVE CRUD
# ============================================================

@router.get("/", response_model=List[InitiativeResponse])
def list_initiatives(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all initiatives for the current tenant."""
    if initiative_status:
        return crud.initiative.get_by_status(
            db=db, status=initiative_status, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    return crud.initiative.get_multi(
        db=db, tenant_id=tenant_id, skip=skip, limit=limit
    )


@router.get("/{initiative_id}", response_model=InitiativeWithAssets)
def get_initiative(
    initiative_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single initiative with all linked assets."""
    initiative = crud.initiative.get_with_assets(
        db=db, id=initiative_id, tenant_id=tenant_id
    )
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")
    return initiative


@router.post("/", response_model=InitiativeResponse, status_code=status.HTTP_201_CREATED)
def create_initiative(
    *,
    obj_in: InitiativeCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Create a new initiative."""
    logger.info(f"Creating initiative '{obj_in.name}' for tenant {tenant_id}")
    return crud.initiative.create_with_owner(
        db=db, obj_in=obj_in, owner_id=current_user.id, tenant_id=tenant_id
    )


@router.put("/{initiative_id}", response_model=InitiativeResponse)
def update_initiative(
    initiative_id: int,
    *,
    obj_in: InitiativeUpdate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Update an initiative."""
    initiative = crud.initiative.get(db=db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")
    return crud.initiative.update(db=db, db_obj=initiative, obj_in=obj_in)


@router.delete("/{initiative_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_initiative(
    initiative_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Delete an initiative and all its asset links."""
    initiative = crud.initiative.get(db=db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")
    crud.initiative.remove(db=db, id=initiative_id, tenant_id=tenant_id)


# ============================================================
# INITIATIVE ASSET LINKING
# ============================================================

@router.get("/{initiative_id}/assets", response_model=List[InitiativeAssetResponse])
def list_initiative_assets(
    initiative_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List all assets linked to an initiative."""
    # Verify initiative exists
    initiative = crud.initiative.get(db=db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    return crud.initiative_asset.get_by_initiative(
        db=db, initiative_id=initiative_id, tenant_id=tenant_id
    )


@router.post("/{initiative_id}/assets", response_model=InitiativeAssetResponse, status_code=status.HTTP_201_CREATED)
def add_asset_to_initiative(
    initiative_id: int,
    *,
    asset_type: str = Query(..., pattern="^(DOCUMENT|REPOSITORY)$"),
    asset_id: int = Query(...),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Link a document or repository to an initiative."""
    # Verify initiative exists
    initiative = crud.initiative.get(db=db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify the asset exists in the tenant
    if asset_type == "DOCUMENT":
        asset = crud.document.get(db=db, id=asset_id, tenant_id=tenant_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Document not found")
    elif asset_type == "REPOSITORY":
        asset = crud.code_component.get(db=db, id=asset_id, tenant_id=tenant_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Code component not found")

    asset_in = InitiativeAssetCreate(
        initiative_id=initiative_id,
        asset_type=asset_type,
        asset_id=asset_id
    )
    return crud.initiative_asset.create_asset(
        db=db, obj_in=asset_in, tenant_id=tenant_id
    )


@router.delete("/{initiative_id}/assets/{asset_link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_asset_from_initiative(
    initiative_id: int,
    asset_link_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Remove (soft-delete) an asset link from an initiative."""
    initiative = crud.initiative.get(db=db, id=initiative_id, tenant_id=tenant_id)
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    result = crud.initiative_asset.deactivate_asset(
        db=db, id=asset_link_id, tenant_id=tenant_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Asset link not found")
