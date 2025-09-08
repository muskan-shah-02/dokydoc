"""
Initiative Asset Model

Join table that associates initiatives with documents and code repositories.
This enables cross-system validation and governance.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class InitiativeAsset(Base):
    __tablename__ = "initiative_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    initiative_id: Mapped[int] = mapped_column(Integer, ForeignKey("initiatives.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "DOCUMENT" or "REPOSITORY"
    asset_id: Mapped[int] = mapped_column(Integer, nullable=False)  # ID of the document or repository
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    initiative = relationship("Initiative", back_populates="assets")

    def __repr__(self):
        return f"<InitiativeAsset(id={self.id}, initiative_id={self.initiative_id}, type='{self.asset_type}', asset_id={self.asset_id})>"
