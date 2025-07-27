# This is the updated content for your file at:
# backend/app/models/mismatch.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base_class import Base

class Mismatch(Base):
    """
    Database model for storing validation mismatches.
    """
    __tablename__ = "mismatches"

    id = Column(Integer, primary_key=True, index=True)

    mismatch_type = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, index=True, nullable=False)
    status = Column(String, default="new", index=True, nullable=False)
    details = Column(JSONB, nullable=True)

    # --- NEW COLUMNS TO ADD ---
    
    # The AI's confidence in this mismatch finding (e.g., "High", "Medium", "Low")
    confidence = Column(String, nullable=True)
    
    # A field for users to add notes or context to a mismatch
    user_notes = Column(Text, nullable=True)
    
    # --- END OF NEW COLUMNS ---

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    code_component_id = Column(Integer, ForeignKey("code_components.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")
    document = relationship("Document")
    code_component = relationship("CodeComponent")
