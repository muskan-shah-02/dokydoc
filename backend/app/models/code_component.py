# This is the content for your NEW file at:
# backend/app/models/code_component.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class CodeComponent(Base):
    """
    Database model for storing code component metadata.
    This represents a reference to a piece of code, like a file,
    class, function, or entire repository.
    """
    __tablename__ = "code_components"

    id = Column(Integer, primary_key=True, index=True)
    
    # A user-friendly name for the component
    name = Column(String, index=True, nullable=False)
    
    # The type of component, e.g., "Repository", "File", "Class", "Function"
    component_type = Column(String, nullable=False)

    # A URL or path to the code, e.g., a GitHub URL or a file path
    location = Column(String, nullable=False)
    
    # The version of the code component, e.g., a git commit hash or a version tag
    version = Column(String, nullable=False)
    
    # The timestamp when the code component was registered in the system
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Foreign key to link this component to the user who registered it
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Creates a relationship to the User model
    owner = relationship("User")

