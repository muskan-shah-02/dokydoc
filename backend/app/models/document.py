# This is the final, updated content for your file at:
# backend/app/models/document.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class Document(Base):
    """
    Database model for storing document metadata and content.
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
    storage_path = Column(String, nullable=False, unique=True)

    # The size of the file in kilobytes
    file_size_kb = Column(Integer, nullable=True)

    # The full text content extracted from the document by our parsing service.
    content = Column(Text, nullable=True)
    
    # A status field to track background parsing
    status = Column(String, default="processing") # e.g., "processing", "completed", "failed"
    
    # Add this line to your Document model after the status field
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    
    # The timestamp when the document record was created
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Foreign key to link this document to the user who uploaded it
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Creates a relationship, allowing you to access the user object
    # from a document object, e.g., my_document.owner.email
    owner = relationship("User")
