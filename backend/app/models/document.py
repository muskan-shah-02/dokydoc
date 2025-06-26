# This is the content for your NEW file at:
# backend/app/models/document.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class Document(Base):
    """
    Database model for storing document metadata.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    
    # The original name of the file uploaded by the user
    filename = Column(String, index=True, nullable=False)
    
    # The type of document, e.g., "BRD", "SRS", "Technical Spec"
    document_type = Column(String, nullable=False)
    
    # The version string provided by the user, e.g., "v1.0", "v2.3"
    version = Column(String, nullable=False)
    
    # The path on the server's storage where the actual file is located
    # e.g., /app/uploads/e9a8f7b6-c5d4-4e32-a1b1-f2d3e4c5d6e7.pdf
    storage_path = Column(String, nullable=False, unique=True)
    
    # The timestamp when the document record was created
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Foreign key to link this document to the user who uploaded it
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Creates a relationship, allowing you to access the user object
    # from a document object, e.g., my_document.owner.email
    owner = relationship("User")

