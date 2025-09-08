# This is the final, updated content for your file at:
# backend/app/api/endpoints/document_code_links.py

from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.core.logging import LoggerMixin
from app.core.exceptions import NotFoundException, ValidationException

class DocumentCodeLinksEndpoints(LoggerMixin):
    """Document code links endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
links_endpoints = DocumentCodeLinksEndpoints()

router = APIRouter()


@router.get("/document/{document_id}", response_model=List[schemas.CodeComponent])
def get_linked_components_for_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components linked to a specific document.
    """
    logger = links_endpoints.logger
    logger.info(f"Fetching linked components for document {document_id}")
    
    # First, verify the user owns the document they are querying
    document = crud.document.get(db=db, id=document_id)
    if not document:
        logger.warning(f"Document {document_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to access links for document {document_id} owned by {document.owner_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this document.",
        )
        
    # Get all the links for this document
    links = crud.document_code_link.get_multi_by_document(db=db, document_id=document_id)
    
    # For each link, fetch the full CodeComponent object
    linked_components = [
        crud.code_component.get(db=db, id=link.code_component_id) for link in links
    ]
    
    # Filter out any components that might be None (if they were deleted)
    valid_components = [comp for comp in linked_components if comp is not None]
    
    logger.info(f"Retrieved {len(valid_components)} linked components for document {document_id}")
    return valid_components


@router.post("/", response_model=schemas.DocumentCodeLink)
def create_link(
    *,
    db: Session = Depends(deps.get_db),
    link_in: schemas.DocumentCodeLinkCreate,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new link between a document and a code component.
    """
    logger = links_endpoints.logger
    logger.info(f"Creating link between document {link_in.document_id} and code component {link_in.code_component_id}")
    
    # Verify the user owns the document and the code component
    document = crud.document.get(db=db, id=link_in.document_id)
    if not document:
        logger.warning(f"Document {link_in.document_id} not found for linking")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to link document {link_in.document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to link this document")

    code_component = crud.code_component.get(db=db, id=link_in.code_component_id)
    if not code_component:
        logger.warning(f"Code component {link_in.code_component_id} not found for linking")
        raise HTTPException(status_code=404, detail="Code component not found")
    
    if code_component.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to link code component {link_in.code_component_id} owned by {code_component.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to link this code component")

    # The create function from CRUDBase will handle the creation
    link = crud.document_code_link.create(db=db, obj_in=link_in)
    
    logger.info(f"Successfully created link {link.id} between document {link_in.document_id} and code component {link_in.code_component_id}")
    return link


@router.delete("/")
def delete_link(
    *,
    db: Session = Depends(deps.get_db),
    link_in: schemas.DocumentCodeLinkCreate, # Use the same schema for identification
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete a link between a document and a code component.
    """
    logger = links_endpoints.logger
    logger.info(f"Deleting link between document {link_in.document_id} and code component {link_in.code_component_id}")
    
    # Verify user ownership of the document before allowing deletion
    document = crud.document.get(db=db, id=link_in.document_id)
    if not document:
        logger.warning(f"Document {link_in.document_id} not found for link deletion")
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to delete link for document {link_in.document_id} owned by {document.owner_id}")
        raise HTTPException(status_code=403, detail="Not authorized to modify this document's links")

    crud.document_code_link.remove_link(
        db=db, 
        document_id=link_in.document_id, 
        code_component_id=link_in.code_component_id
    )
    
    logger.info(f"Successfully deleted link between document {link_in.document_id} and code component {link_in.code_component_id}")
    return {"msg": "Link removed successfully"}

