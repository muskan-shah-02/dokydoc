"""
CRUD operations for ApiKey model.
Sprint 8: API Key Authentication.
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.api_key import ApiKey


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class CRUDApiKey:

    PREFIX = "dk_live_"

    def create(
        self,
        db: Session,
        *,
        name: str,
        user_id: int,
        tenant_id: int,
        expires_days: Optional[int] = None,
    ) -> tuple[ApiKey, str]:
        """
        Create a new API key. Returns (ApiKey, raw_key).
        The raw_key is shown to the user once; store the hash only.
        """
        token = secrets.token_urlsafe(32)
        raw_key = f"{self.PREFIX}{token}"
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:12]

        expires_at = (
            datetime.utcnow() + timedelta(days=expires_days) if expires_days else None
        )

        obj = ApiKey(
            name=name,
            user_id=user_id,
            tenant_id=tenant_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            is_active=True,
            expires_at=expires_at,
            request_count=0,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj, raw_key

    def get_by_raw_key(self, db: Session, raw_key: str) -> Optional[ApiKey]:
        """Look up an API key by its raw (unhashed) value."""
        key_hash = _hash_key(raw_key)
        return db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

    def get_for_user(self, db: Session, *, user_id: int, tenant_id: int) -> list[ApiKey]:
        """List all API keys for a specific user in a tenant."""
        return (
            db.query(ApiKey)
            .filter(ApiKey.user_id == user_id, ApiKey.tenant_id == tenant_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    def get_by_id(
        self, db: Session, *, key_id: int, user_id: int, tenant_id: int
    ) -> Optional[ApiKey]:
        return db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == user_id,
            ApiKey.tenant_id == tenant_id,
        ).first()

    def revoke(
        self, db: Session, *, key_id: int, user_id: int, tenant_id: int
    ) -> Optional[ApiKey]:
        """Deactivate (revoke) an API key."""
        obj = self.get_by_id(db, key_id=key_id, user_id=user_id, tenant_id=tenant_id)
        if obj:
            obj.is_active = False
            obj.revoked_at = datetime.utcnow()
            db.commit()
            db.refresh(obj)
        return obj

    def record_usage(self, db: Session, api_key: ApiKey) -> None:
        """Update last_used_at and increment request_count (fire-and-forget)."""
        api_key.last_used_at = datetime.utcnow()
        api_key.request_count = (api_key.request_count or 0) + 1
        db.commit()

    def is_valid(self, api_key: ApiKey) -> bool:
        """Check the key is active and not expired."""
        if not api_key.is_active:
            return False
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return False
        return True


crud_api_key = CRUDApiKey()
