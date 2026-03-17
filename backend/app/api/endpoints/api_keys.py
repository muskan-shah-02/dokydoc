"""
API Key Management Endpoints
Sprint 8: Programmatic access via API keys.

  POST   /api-keys/          — Create a new API key
  GET    /api-keys/          — List my API keys
  DELETE /api-keys/{id}      — Revoke an API key
"""
from typing import Any
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.db.session import get_db
from app.crud.crud_api_key import crud_api_key
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyListResponse, ApiKeyResponse
from app.core.logging import get_logger

logger = get_logger("api.api_keys")

router = APIRouter()


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=201)
def create_api_key(
    payload: ApiKeyCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new API key. The raw key is shown only once — store it securely.
    """
    obj, raw_key = crud_api_key.create(
        db,
        name=payload.name,
        user_id=current_user.id,
        tenant_id=tenant_id,
        expires_days=payload.expires_days,
    )
    return ApiKeyCreatedResponse(
        id=obj.id,
        tenant_id=obj.tenant_id,
        user_id=obj.user_id,
        name=obj.name,
        key_prefix=obj.key_prefix,
        is_active=obj.is_active,
        expires_at=obj.expires_at,
        last_used_at=obj.last_used_at,
        request_count=obj.request_count,
        created_at=obj.created_at,
        raw_key=raw_key,
    )


@router.get("/", response_model=ApiKeyListResponse)
def list_api_keys(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List all API keys belonging to the current user."""
    keys = crud_api_key.get_for_user(db, user_id=current_user.id, tenant_id=tenant_id)
    return {"api_keys": keys, "total": len(keys)}


@router.delete("/{key_id}", status_code=200)
def revoke_api_key(
    key_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Revoke (deactivate) an API key. This cannot be undone."""
    obj = crud_api_key.revoke(
        db, key_id=key_id, user_id=current_user.id, tenant_id=tenant_id
    )
    if not obj:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked", "id": key_id}
