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

    def get(self, db: Session, id: Any, *, tenant_id: Optional[int] = None) -> Optional[ModelType]:
        """
        Get a single record by ID, optionally filtered by tenant_id.

        Args:
            db: Database session
            id: Record ID
            tenant_id: Optional tenant ID for multi-tenancy isolation (Sprint 1: BE-MULTI-01)
        """
        query = db.query(self.model).filter(self.model.id == id)

        # Apply tenant filter if model supports multi-tenancy and tenant_id is provided
        if tenant_id is not None and self._has_tenant_id():
            query = query.filter(self.model.tenant_id == tenant_id)

        return query.first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[int] = None
    ) -> List[ModelType]:
        """
        Get multiple records with pagination, optionally filtered by tenant_id.

        Args:
            db: Database session
            skip: Number of records to skip (pagination offset)
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenancy isolation (Sprint 1: BE-MULTI-01)
        """
        query = db.query(self.model)

        # Apply tenant filter if model supports multi-tenancy and tenant_id is provided
        if tenant_id is not None and self._has_tenant_id():
            query = query.filter(self.model.tenant_id == tenant_id)

        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
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


    def remove(self, db: Session, *, id: int) -> ModelType:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj
    
    def get_multi_by_ids(
        self,
        db: Session,
        *,
        ids: List[int],
        tenant_id: Optional[int] = None
    ) -> List[ModelType]:
        """
        Get multiple records by IDs, optionally filtered by tenant_id.

        Args:
            db: Database session
            ids: List of record IDs to fetch
            tenant_id: Optional tenant ID for multi-tenancy isolation (Sprint 1: BE-MULTI-01)
        """
        query = db.query(self.model).filter(self.model.id.in_(ids))

        # Apply tenant filter if model supports multi-tenancy and tenant_id is provided
        if tenant_id is not None and self._has_tenant_id():
            query = query.filter(self.model.tenant_id == tenant_id)

        return query.all()
    
    