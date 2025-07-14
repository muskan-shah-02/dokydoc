# This is the content for your NEW file at:
# backend/app/models/analysis_result.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base_class import Base

class AnalysisResult(Base):
    """
    Database model for storing the results of various AI analyses
    performed on a document.
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    
    # The type of analysis performed, e.g., "summary", "functional_requirements"
    analysis_type = Column(String, index=True, nullable=False)
    
    # The structured result from the AI, stored as a JSON object.
    # Using JSONB is efficient for querying in PostgreSQL.
    result_data = Column(JSONB)
    
    # The timestamp when the analysis was completed.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Foreign key to link this analysis result back to the original document.
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    # Creates a relationship to the Document model.
    document = relationship("Document")
