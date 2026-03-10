"""
Field Encryption — SQLAlchemy event-based transparent encryption/decryption.
Sprint 6: Data Encryption at Rest.

Registers SQLAlchemy event listeners to automatically encrypt sensitive fields
on write and decrypt on read. Configured via ENCRYPTION_KEY environment variable.

Usage:
    from app.services.field_encryption import register_encryption_listeners
    register_encryption_listeners()  # Call once during app startup
"""
from sqlalchemy import event
from app.services.encryption_service import encrypt, decrypt, is_encryption_configured
from app.core.logging import get_logger

logger = get_logger("field_encryption")

# Map of Model -> list of field names to encrypt
ENCRYPTED_FIELDS = {}


def register_encrypted_model(model_class, field_names: list):
    """Register a model and its fields for transparent encryption."""
    ENCRYPTED_FIELDS[model_class] = field_names


def register_encryption_listeners():
    """
    Register SQLAlchemy event listeners for all encrypted models.
    Call this once during application startup.
    """
    if not is_encryption_configured():
        logger.info("ENCRYPTION_KEY not set — field encryption disabled")
        return

    # Import models and register their encrypted fields
    from app.models.document import Document
    register_encrypted_model(Document, ["raw_text"])

    for model_class, fields in ENCRYPTED_FIELDS.items():
        _register_model_listeners(model_class, fields)

    logger.info(
        f"Field encryption enabled for {len(ENCRYPTED_FIELDS)} model(s): "
        f"{[m.__tablename__ for m in ENCRYPTED_FIELDS]}"
    )


def _register_model_listeners(model_class, field_names: list):
    """Register before_insert / before_update / load listeners for a model."""

    @event.listens_for(model_class, "before_insert")
    def encrypt_on_insert(mapper, connection, target):
        for field in field_names:
            value = getattr(target, field, None)
            if value and isinstance(value, str):
                setattr(target, field, encrypt(value))

    @event.listens_for(model_class, "before_update")
    def encrypt_on_update(mapper, connection, target):
        for field in field_names:
            value = getattr(target, field, None)
            if value and isinstance(value, str):
                setattr(target, field, encrypt(value))

    @event.listens_for(model_class, "load")
    def decrypt_on_load(target, context):
        for field in field_names:
            value = getattr(target, field, None)
            if value and isinstance(value, str):
                setattr(target, field, decrypt(value))
