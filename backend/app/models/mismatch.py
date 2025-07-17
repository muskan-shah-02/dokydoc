# This is the content for your NEW file at:
# backend/app/models/mismatch.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class Mismatch(Base):
    """
    Database model for storing detected mismatches between documents and code.
    """
    __tablename__ = "mismatches"

    id = Column(Integer, primary_key=True, index=True)
    
    # The type of mismatch, e.g., "version", "semantic", "structural"
    mismatch_type = Column(String, index=True, nullable=False)
    
    # A detailed description of the mismatch
    description = Column(Text, nullable=False)
    
    # The status of the mismatch, e.g., "new", "acknowledged", "resolved"
    status = Column(String, default="new", index=True)
    
    # The timestamp when the mismatch was first detected
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Foreign keys to link the mismatch to the specific items involved
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id = Column(Integer, ForeignKey("code_components.id"), nullable=False)
    
    # Relationships to easily access the linked objects
    document = relationship("Document")
    code_component = relationship("CodeComponent")
