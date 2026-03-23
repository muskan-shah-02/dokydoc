from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.base_class import Base
from fastapi.encoders import jsonable_encoder

ModelType = TypeVar("ModelType", bound=Base) # type: ignore
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def _has_tenant_id(self) -> bool:
        """Check if model has tenant_id column for multi-tenancy support."""
        return hasattr(self.model, 'tenant_id')

    def get(self, db: Session, id: Any, *, tenant_id: int) -> Optional[ModelType]:
        """
        Get a single record by ID, filtered by tenant_id.

        SPRINT 2: tenant_id is now REQUIRED (not optional) for data isolation.

        Args:
            db: Database session
            id: Record ID
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Raises:
            ValueError: If tenant_id is not provided or model doesn't support multi-tenancy
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError(
                f"tenant_id is REQUIRED for {self.model.__name__}.get() - "
                "this is a critical security requirement for data isolation"
            )

        # Validate model supports multi-tenancy
        if not self._has_tenant_id():
            raise ValueError(
                f"Model {self.model.__name__} does not support multi-tenancy (missing tenant_id column)"
            )

        # Build query with MANDATORY tenant filter
        return db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        ).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        tenant_id: int
    ) -> List[ModelType]:
        """
        Get multiple records with pagination, filtered by tenant_id.

        SPRINT 2: tenant_id is now REQUIRED (not optional) for data isolation.

        Args:
            db: Database session
            skip: Number of records to skip (pagination offset)
            limit: Maximum number of records to return
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Raises:
            ValueError: If tenant_id is not provided or model doesn't support multi-tenancy
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError(
                f"tenant_id is REQUIRED for {self.model.__name__}.get_multi() - "
                "this is a critical security requirement for data isolation"
            )

        # Validate model supports multi-tenancy
        if not self._has_tenant_id():
            raise ValueError(
                f"Model {self.model.__name__} does not support multi-tenancy (missing tenant_id column)"
            )

        # Build query with MANDATORY tenant filter
        return db.query(self.model).filter(
            self.model.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType, tenant_id: int) -> ModelType:
        """
        Create a new record with tenant_id automatically injected.

        SPRINT 2: tenant_id is now REQUIRED and automatically assigned to the record.

        Args:
            db: Database session
            obj_in: Pydantic schema with create data
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Raises:
            ValueError: If tenant_id is not provided or model doesn't support multi-tenancy

        Returns:
            Created database object
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError(
                f"tenant_id is REQUIRED for {self.model.__name__}.create() - "
                "this is a critical security requirement for data isolation"
            )

        # Validate model supports multi-tenancy
        if not self._has_tenant_id():
            raise ValueError(
                f"Model {self.model.__name__} does not support multi-tenancy (missing tenant_id column)"
            )

        # Convert Pydantic model to dict
        obj_in_data = obj_in.model_dump()

        # CRITICAL: Force tenant_id to prevent tenant hijacking
        # Even if obj_in contains tenant_id, we override it with the authenticated tenant
        obj_in_data["tenant_id"] = tenant_id

        # Create database object
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
           self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        --- THIS IS THE CORRECTED UPDATE METHOD ---
        It directly updates the model attributes without using unsafe set operations,
        making it safe to use with JSON/dict fields.
        """
        # Use jsonable_encoder to handle complex types like datetimes
        obj_data = jsonable_encoder(db_obj)
        
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # For Pydantic models, dump to a dict, excluding unset values
            update_data = obj_in.model_dump(exclude_unset=True)
        
        # Iterate directly and set attributes
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
                
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


    def remove(self, db: Session, *, id: int, tenant_id: int) -> Optional[ModelType]:
        """
        Remove a record by ID, filtered by tenant_id.

        SPRINT 2: tenant_id is now REQUIRED to prevent cross-tenant deletion.

        Args:
            db: Database session
            id: Record ID to delete
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Raises:
            ValueError: If tenant_id is not provided or model doesn't support multi-tenancy

        Returns:
            Deleted database object, or None if not found
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError(
                f"tenant_id is REQUIRED for {self.model.__name__}.remove() - "
                "this is a critical security requirement for data isolation"
            )

        # Validate model supports multi-tenancy
        if not self._has_tenant_id():
            raise ValueError(
                f"Model {self.model.__name__} does not support multi-tenancy (missing tenant_id column)"
            )

        # Find object with tenant filter (prevents cross-tenant deletion)
        obj = db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        ).first()

        if obj:
            db.delete(obj)
            db.commit()

        return obj
    
    def get_multi_by_ids(
        self,
        db: Session,
        *,
        ids: List[int],
        tenant_id: int
    ) -> List[ModelType]:
        """
        Get multiple records by IDs, filtered by tenant_id.

        SPRINT 2: tenant_id is now REQUIRED (not optional) for data isolation.

        Args:
            db: Database session
            ids: List of record IDs to fetch
            tenant_id: REQUIRED tenant ID for multi-tenancy isolation

        Raises:
            ValueError: If tenant_id is not provided or model doesn't support multi-tenancy
        """
        # CRITICAL VALIDATION: Ensure tenant_id is provided
        if not tenant_id:
            raise ValueError(
                f"tenant_id is REQUIRED for {self.model.__name__}.get_multi_by_ids() - "
                "this is a critical security requirement for data isolation"
            )

        # Validate model supports multi-tenancy
        if not self._has_tenant_id():
            raise ValueError(
                f"Model {self.model.__name__} does not support multi-tenancy (missing tenant_id column)"
            )

        # Build query with MANDATORY tenant filter
        return db.query(self.model).filter(
            self.model.id.in_(ids),
            self.model.tenant_id == tenant_id
        ).all()
    
    