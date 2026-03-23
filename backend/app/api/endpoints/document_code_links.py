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
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all code components linked to a specific document.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = links_endpoints.logger
    logger.info(f"Fetching linked components for document {document_id} (tenant_id={tenant_id})")

    # Verify document exists in tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {document_id} not found in tenant {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Get all the links for this document
    links = crud.document_code_link.get_multi_by_document(db=db, document_id=document_id, tenant_id=tenant_id)

    # For each link, fetch the full CodeComponent object
    linked_components = [
        crud.code_component.get(db=db, id=link.code_component_id, tenant_id=tenant_id) for link in links
    ]

    # Filter out any components that might be None (if they were deleted)
    valid_components = [comp for comp in linked_components if comp is not None]

    logger.info(f"Retrieved {len(valid_components)} linked components for document {document_id} (tenant_id={tenant_id})")
    return valid_components


@router.post("/", response_model=schemas.DocumentCodeLink)
def create_link(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    link_in: schemas.DocumentCodeLinkCreate,
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new link between a document and a code component.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document/component not in tenant to avoid leaking existence.
    """
    logger = links_endpoints.logger
    logger.info(f"Creating link between document {link_in.document_id} and code component {link_in.code_component_id} (tenant_id={tenant_id})")

    # Verify the document exists in tenant
    document = crud.document.get(db=db, id=link_in.document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {link_in.document_id} not found in tenant {tenant_id} for linking")
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify the code component exists in tenant
    code_component = crud.code_component.get(db=db, id=link_in.code_component_id, tenant_id=tenant_id)
    if not code_component:
        logger.warning(f"Code component {link_in.code_component_id} not found in tenant {tenant_id} for linking")
        raise HTTPException(status_code=404, detail="Code component not found")

    # The create function from CRUDBase will handle the creation
    link = crud.document_code_link.create(db=db, obj_in=link_in, tenant_id=tenant_id)

    logger.info(f"Successfully created link {link.id} between document {link_in.document_id} and code component {link_in.code_component_id} (tenant_id={tenant_id})")
    return link


@router.delete("/")
def delete_link(
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    link_in: schemas.DocumentCodeLinkCreate, # Use the same schema for identification
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete a link between a document and a code component.

    SPRINT 2: Now filtered by tenant_id. Uses "Schrödinger's Document" pattern -
    returns 404 (not 403) when document not in tenant to avoid leaking existence.
    """
    logger = links_endpoints.logger
    logger.info(f"Deleting link between document {link_in.document_id} and code component {link_in.code_component_id} (tenant_id={tenant_id})")

    # Verify document exists in tenant before allowing deletion
    document = crud.document.get(db=db, id=link_in.document_id, tenant_id=tenant_id)
    if not document:
        logger.warning(f"Document {link_in.document_id} not found in tenant {tenant_id} for link deletion")
        raise HTTPException(status_code=404, detail="Document not found")

    crud.document_code_link.remove_link(
        db=db,
        document_id=link_in.document_id,
        code_component_id=link_in.code_component_id,
        tenant_id=tenant_id
    )

    logger.info(f"Successfully deleted link between document {link_in.document_id} and code component {link_in.code_component_id} (tenant_id={tenant_id})")
    return {"msg": "Link removed successfully"}

