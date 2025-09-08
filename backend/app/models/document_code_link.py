from datetime import datetime
from sqlalchemy import Integer, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base

class DocumentCodeLink(Base):
    """
    Database model for the association table linking Documents and CodeComponents.
    Each row represents a single link between one document and one code component.
    """
    __tablename__ = "document_code_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id: Mapped[int] = mapped_column(Integer, ForeignKey("code_components.id"), nullable=False)

    # Add a unique constraint to ensure that the same document cannot be
    # linked to the same code component more than once.
    __table_args__ = (
        UniqueConstraint('document_id', 'code_component_id', name='_document_code_uc'),
    )
    
    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

