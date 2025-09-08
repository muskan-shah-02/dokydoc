"""
Initiative Model

Represents a business initiative or project that spans multiple documents and code repositories.
This is the governance layer that ties everything together.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Initiative(Base):
    __tablename__ = "initiatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")  # ACTIVE, COMPLETED, CANCELLED
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="initiatives")
    assets = relationship("InitiativeAsset", back_populates="initiative", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Initiative(id={self.id}, name='{self.name}', status='{self.status}')>"
