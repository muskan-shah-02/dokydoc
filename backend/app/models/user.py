from typing import List
from datetime import datetime
from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # This line adds the 'roles' column to the database model
    roles: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    
    # Documents owned by this user
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="owner")
    
    # Initiatives owned by this user
    initiatives: Mapped[List["Initiative"]] = relationship("Initiative", back_populates="owner")
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)