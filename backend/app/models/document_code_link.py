# This is the content for your NEW file at:
# backend/app/models/document_code_link.py

from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from app.db.base_class import Base

class DocumentCodeLink(Base):
    """
    Database model for the association table linking Documents and CodeComponents.
    Each row represents a single link between one document and one code component.
    """
    __tablename__ = "document_code_links"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id = Column(Integer, ForeignKey("code_components.id"), nullable=False)

    # Add a unique constraint to ensure that the same document cannot be
    # linked to the same code component more than once.
    __table_args__ = (
        UniqueConstraint('document_id', 'code_component_id', name='_document_code_uc'),
    )

