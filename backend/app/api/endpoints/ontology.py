"""
SPRINT 3: Business Ontology Engine API Endpoints

Provides CRUD for concepts, relationships, and graph visualization.
All endpoints are tenant-scoped via get_tenant_id dependency.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.db.session import get_db
from app.schemas.ontology import (
    OntologyConceptCreate, OntologyConceptUpdate, OntologyConceptResponse,
    OntologyConceptWithRelationships,
    OntologyRelationshipCreate, OntologyRelationshipUpdate, OntologyRelationshipResponse,
    OntologyGraphResponse, OntologyGraphNode, OntologyGraphEdge
)
from app.core.logging import get_logger

logger = get_logger("api.ontology")

router = APIRouter()


# ============================================================
# CONCEPT ENDPOINTS
# ============================================================

@router.get("/concepts", response_model=List[OntologyConceptResponse])
def list_concepts(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    concept_type: Optional[str] = Query(None, description="Filter by concept type"),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all ontology concepts for the current tenant, optionally filtered by type."""
    if concept_type:
        return crud.ontology_concept.get_by_type(
            db=db, concept_type=concept_type, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    return crud.ontology_concept.get_multi(
        db=db, tenant_id=tenant_id, skip=skip, limit=limit
    )


@router.get("/concepts/types", response_model=List[str])
def list_concept_types(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get all distinct concept types for the tenant."""
    return crud.ontology_concept.get_concept_types(db=db, tenant_id=tenant_id)


@router.get("/concepts/search", response_model=List[OntologyConceptResponse])
def search_concepts(
    q: str = Query(..., min_length=1, description="Search query"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    limit: int = 20,
) -> Any:
    """Search concepts by name (case-insensitive partial match)."""
    return crud.ontology_concept.search_by_name(
        db=db, query=q, tenant_id=tenant_id, limit=limit
    )


@router.get("/concepts/{concept_id}", response_model=OntologyConceptWithRelationships)
def get_concept(
    concept_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single concept with all its relationships."""
    concept = crud.ontology_concept.get_with_relationships(
        db=db, id=concept_id, tenant_id=tenant_id
    )
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept


@router.post("/concepts", response_model=OntologyConceptResponse, status_code=status.HTTP_201_CREATED)
def create_concept(
    *,
    obj_in: OntologyConceptCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Manually create a new ontology concept."""
    return crud.ontology_concept.get_or_create(
        db=db, name=obj_in.name, concept_type=obj_in.concept_type,
        tenant_id=tenant_id, description=obj_in.description,
        confidence_score=obj_in.confidence_score
    )


@router.put("/concepts/{concept_id}", response_model=OntologyConceptResponse)
def update_concept(
    concept_id: int,
    *,
    obj_in: OntologyConceptUpdate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Update an ontology concept."""
    concept = crud.ontology_concept.get(db=db, id=concept_id, tenant_id=tenant_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return crud.ontology_concept.update(db=db, db_obj=concept, obj_in=obj_in)


@router.delete("/concepts/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_concept(
    concept_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Delete a concept and all its relationships."""
    concept = crud.ontology_concept.get(db=db, id=concept_id, tenant_id=tenant_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    # Cascade: delete relationships first
    crud.ontology_relationship.delete_by_concept(
        db=db, concept_id=concept_id, tenant_id=tenant_id
    )
    crud.ontology_concept.remove(db=db, id=concept_id, tenant_id=tenant_id)


# ============================================================
# RELATIONSHIP ENDPOINTS
# ============================================================

@router.get("/relationships", response_model=List[OntologyRelationshipResponse])
def list_relationships(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all ontology relationships for the tenant."""
    if relationship_type:
        return crud.ontology_relationship.get_by_type(
            db=db, relationship_type=relationship_type, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    return crud.ontology_relationship.get_multi(
        db=db, tenant_id=tenant_id, skip=skip, limit=limit
    )


@router.post("/relationships", response_model=OntologyRelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship(
    *,
    obj_in: OntologyRelationshipCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Create a relationship between two concepts."""
    # Validate both concepts exist in tenant
    source = crud.ontology_concept.get(db=db, id=obj_in.source_concept_id, tenant_id=tenant_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source concept not found")
    target = crud.ontology_concept.get(db=db, id=obj_in.target_concept_id, tenant_id=tenant_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target concept not found")
    if obj_in.source_concept_id == obj_in.target_concept_id:
        raise HTTPException(status_code=400, detail="Cannot create self-referencing relationship")

    return crud.ontology_relationship.create_if_not_exists(
        db=db, source_concept_id=obj_in.source_concept_id,
        target_concept_id=obj_in.target_concept_id,
        relationship_type=obj_in.relationship_type,
        tenant_id=tenant_id, description=obj_in.description,
        confidence_score=obj_in.confidence_score
    )


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Delete a specific relationship."""
    rel = crud.ontology_relationship.get(db=db, id=relationship_id, tenant_id=tenant_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    crud.ontology_relationship.remove(db=db, id=relationship_id, tenant_id=tenant_id)


# ============================================================
# GRAPH ENDPOINT (for visualization)
# ============================================================

@router.get("/graph", response_model=OntologyGraphResponse)
def get_graph(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the full ontology graph for the tenant.
    Returns nodes (concepts) and edges (relationships) for frontend visualization.
    """
    concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)

    nodes = [
        OntologyGraphNode(
            id=c.id, name=c.name, concept_type=c.concept_type,
            confidence_score=c.confidence_score
        ) for c in concepts
    ]
    edges = [
        OntologyGraphEdge(
            id=r.id, source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score
        ) for r in relationships
    ]

    return OntologyGraphResponse(
        nodes=nodes, edges=edges,
        total_nodes=len(nodes), total_edges=len(edges)
    )


# ============================================================
# STATS + DOCUMENT ONTOLOGY STATUS
# ============================================================

@router.get("/stats")
def get_ontology_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get ontology statistics for the tenant."""
    return {
        "total_concepts": crud.ontology_concept.count_by_tenant(db=db, tenant_id=tenant_id),
        "total_relationships": crud.ontology_relationship.count_by_tenant(db=db, tenant_id=tenant_id),
        "concept_types": crud.ontology_concept.get_concept_types(db=db, tenant_id=tenant_id),
    }


@router.post("/synonyms/detect", status_code=status.HTTP_202_ACCEPTED)
def trigger_synonym_detection(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks = None,
) -> Any:
    """Trigger synonym detection across all concepts for the tenant."""
    from app.services.business_ontology_service import business_ontology_service
    import asyncio

    async def _run_detection():
        return await business_ontology_service.detect_synonyms(db=db, tenant_id=tenant_id)

    background_tasks.add_task(asyncio.run, _run_detection())
    return {"message": "Synonym detection started"}
