"""
SPRINT 3: Business Ontology Engine API Endpoints
SPRINT 4: Concept Mapping API (Two-Graph Architecture)

Provides CRUD for concepts, relationships, graph visualization,
and cross-graph concept mapping between document & code layers.
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
from app.schemas.concept_mapping import (
    ConceptMappingCreate, ConceptMappingUpdate, ConceptMappingResponse,
    ConceptMappingWithConcepts,
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
    initiative_id: Optional[int] = Query(None, description="Filter by project/initiative"),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List ontology concepts, optionally filtered by type and/or project."""
    if initiative_id:
        concepts = crud.ontology_concept.get_by_initiative(
            db=db, initiative_id=initiative_id, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
        if concept_type:
            concepts = [c for c in concepts if c.concept_type == concept_type]
        return concepts
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
    """Manually create a new ontology concept, optionally scoped to a project."""
    return crud.ontology_concept.get_or_create(
        db=db, name=obj_in.name, concept_type=obj_in.concept_type,
        tenant_id=tenant_id, description=obj_in.description,
        confidence_score=obj_in.confidence_score,
        initiative_id=obj_in.initiative_id
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
    initiative_id: Optional[int] = Query(None, description="Filter by project/initiative"),
) -> Any:
    """
    Get the ontology graph for the tenant, optionally scoped to a project.
    Returns nodes (concepts) and edges (relationships) for frontend visualization.
    """
    concepts = crud.ontology_concept.get_all_active(
        db=db, tenant_id=tenant_id, initiative_id=initiative_id
    )
    concept_ids = {c.id for c in concepts}

    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)
    # Filter relationships to only include edges between visible concepts
    filtered_rels = [
        r for r in relationships
        if r.source_concept_id in concept_ids and r.target_concept_id in concept_ids
    ]

    nodes = [
        OntologyGraphNode(
            id=c.id, name=c.name, concept_type=c.concept_type,
            source_type=c.source_type, initiative_id=c.initiative_id,
            confidence_score=c.confidence_score
        ) for c in concepts
    ]
    edges = [
        OntologyGraphEdge(
            id=r.id, source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score
        ) for r in filtered_rels
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
    initiative_id: Optional[int] = Query(None, description="Filter by project/initiative"),
) -> Any:
    """Get ontology statistics, optionally scoped to a project."""
    total_concepts = crud.ontology_concept.count_by_tenant(
        db=db, tenant_id=tenant_id, initiative_id=initiative_id
    )
    # For relationships, filter by counting edges between project-scoped concepts
    if initiative_id:
        concepts = crud.ontology_concept.get_all_active(
            db=db, tenant_id=tenant_id, initiative_id=initiative_id
        )
        concept_ids = {c.id for c in concepts}
        all_rels = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)
        total_rels = sum(
            1 for r in all_rels
            if r.source_concept_id in concept_ids and r.target_concept_id in concept_ids
        )
        concept_types = list({c.concept_type for c in concepts})
    else:
        total_rels = crud.ontology_relationship.count_by_tenant(db=db, tenant_id=tenant_id)
        concept_types = crud.ontology_concept.get_concept_types(db=db, tenant_id=tenant_id)

    return {
        "total_concepts": total_concepts,
        "total_relationships": total_rels,
        "concept_types": concept_types,
    }


@router.get("/document/{document_id}/status")
def get_document_ontology_status(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get ontology enrichment status for a specific document.
    Frontend uses this to show a subtle badge like "12 entities extracted"
    after the async ontology task completes.
    """
    # Verify document belongs to tenant
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Count concepts that reference this document (via source_document_id on OntologyConcept)
    # For now, return tenant-level stats + a flag indicating enrichment has run
    total_concepts = crud.ontology_concept.count_by_tenant(db=db, tenant_id=tenant_id)
    total_relationships = crud.ontology_relationship.count_by_tenant(db=db, tenant_id=tenant_id)

    return {
        "document_id": document_id,
        "enrichment_complete": total_concepts > 0,
        "total_concepts": total_concepts,
        "total_relationships": total_relationships,
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


# ============================================================
# FILTERED GRAPH ENDPOINTS (SPRINT 4 — Two-Graph UI)
# ============================================================

@router.get("/graph/document", response_model=OntologyGraphResponse)
def get_document_graph(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Filter by project/initiative"),
) -> Any:
    """Get only the document-layer concepts and their relationships, optionally scoped to a project."""
    concepts = crud.ontology_concept.get_all_active(
        db=db, tenant_id=tenant_id, initiative_id=initiative_id
    )
    doc_concepts = [c for c in concepts if c.source_type in ("document", "both")]
    doc_ids = {c.id for c in doc_concepts}

    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)
    doc_relationships = [
        r for r in relationships
        if r.source_concept_id in doc_ids and r.target_concept_id in doc_ids
    ]

    nodes = [
        OntologyGraphNode(
            id=c.id, name=c.name, concept_type=c.concept_type,
            source_type=c.source_type, initiative_id=c.initiative_id,
            confidence_score=c.confidence_score
        ) for c in doc_concepts
    ]
    edges = [
        OntologyGraphEdge(
            id=r.id, source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score
        ) for r in doc_relationships
    ]

    return OntologyGraphResponse(nodes=nodes, edges=edges, total_nodes=len(nodes), total_edges=len(edges))


@router.get("/graph/code", response_model=OntologyGraphResponse)
def get_code_graph(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Filter by project/initiative"),
) -> Any:
    """Get only the code-layer concepts and their relationships, optionally scoped to a project."""
    concepts = crud.ontology_concept.get_all_active(
        db=db, tenant_id=tenant_id, initiative_id=initiative_id
    )
    code_concepts = [c for c in concepts if c.source_type in ("code", "both")]
    code_ids = {c.id for c in code_concepts}

    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)
    code_relationships = [
        r for r in relationships
        if r.source_concept_id in code_ids and r.target_concept_id in code_ids
    ]

    nodes = [
        OntologyGraphNode(
            id=c.id, name=c.name, concept_type=c.concept_type,
            source_type=c.source_type, initiative_id=c.initiative_id,
            confidence_score=c.confidence_score
        ) for c in code_concepts
    ]
    edges = [
        OntologyGraphEdge(
            id=r.id, source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score
        ) for r in code_relationships
    ]

    return OntologyGraphResponse(nodes=nodes, edges=edges, total_nodes=len(nodes), total_edges=len(edges))


# ============================================================
# CONCEPT MAPPING ENDPOINTS (SPRINT 4 — Cross-Graph)
# ============================================================

@router.get("/mappings")
def list_mappings(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: candidate, confirmed, rejected"),
    skip: int = 0,
    limit: int = 200,
) -> Any:
    """List concept mappings with optional status filter. Returns enriched mapping data."""
    if status_filter:
        mappings = crud.concept_mapping.get_by_status(
            db=db, status=status_filter, tenant_id=tenant_id, skip=skip, limit=limit
        )
    else:
        mappings = crud.concept_mapping.get_multi(db=db, tenant_id=tenant_id, skip=skip, limit=limit)

    # Enrich with concept names
    result = []
    for m in mappings:
        doc_concept = crud.ontology_concept.get(db=db, id=m.document_concept_id, tenant_id=tenant_id)
        code_concept = crud.ontology_concept.get(db=db, id=m.code_concept_id, tenant_id=tenant_id)
        result.append({
            "id": m.id,
            "tenant_id": m.tenant_id,
            "document_concept_id": m.document_concept_id,
            "code_concept_id": m.code_concept_id,
            "mapping_method": m.mapping_method,
            "confidence_score": m.confidence_score,
            "status": m.status,
            "relationship_type": m.relationship_type,
            "ai_reasoning": m.ai_reasoning,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "document_concept_name": doc_concept.name if doc_concept else "Unknown",
            "document_concept_type": doc_concept.concept_type if doc_concept else "Unknown",
            "code_concept_name": code_concept.name if code_concept else "Unknown",
            "code_concept_type": code_concept.concept_type if code_concept else "Unknown",
        })
    return result


@router.post("/mappings/run", status_code=status.HTTP_202_ACCEPTED)
def trigger_mapping_run(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks = None,
) -> Any:
    """
    Trigger the 3-tier algorithmic mapping pipeline.
    Runs in background: Exact match → Fuzzy match → AI validation.
    """
    from app.services.mapping_service import mapping_service

    def _run_mapping():
        return mapping_service.run_full_mapping(db=db, tenant_id=tenant_id)

    background_tasks.add_task(_run_mapping)
    return {"message": "Cross-graph mapping started", "tiers": ["exact", "fuzzy", "ai_validation"]}


@router.get("/mappings/mismatches")
def get_mismatches(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get gap analysis: document concepts with no code match,
    code concepts with no document match, and contradictions.
    """
    from app.services.mapping_service import mapping_service
    return mapping_service.get_mismatches(db=db, tenant_id=tenant_id)


@router.get("/mappings/stats")
def get_mapping_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get mapping statistics."""
    all_concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    doc_count = sum(1 for c in all_concepts if c.source_type in ("document", "both"))
    code_count = sum(1 for c in all_concepts if c.source_type in ("code", "both"))
    total_mappings = crud.concept_mapping.count_by_tenant(db=db, tenant_id=tenant_id)
    confirmed = len(crud.concept_mapping.get_confirmed(db=db, tenant_id=tenant_id))
    contradictions = len(crud.concept_mapping.get_contradictions(db=db, tenant_id=tenant_id))

    # Count candidates
    candidates = len(crud.concept_mapping.get_by_status(db=db, status="candidate", tenant_id=tenant_id))

    return {
        "document_concepts": doc_count,
        "code_concepts": code_count,
        "total_mappings": total_mappings,
        "confirmed_mappings": confirmed,
        "candidate_mappings": candidates,
        "contradictions": contradictions,
    }


@router.put("/mappings/{mapping_id}/confirm")
def confirm_mapping(
    mapping_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Confirm a candidate mapping."""
    result = crud.concept_mapping.confirm_mapping(db=db, mapping_id=mapping_id, tenant_id=tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "confirmed", "mapping_id": mapping_id}


@router.put("/mappings/{mapping_id}/reject")
def reject_mapping(
    mapping_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Reject a candidate mapping."""
    result = crud.concept_mapping.reject_mapping(db=db, mapping_id=mapping_id, tenant_id=tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "rejected", "mapping_id": mapping_id}


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping(
    mapping_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> None:
    """Delete a specific mapping."""
    mapping = crud.concept_mapping.get(db=db, id=mapping_id, tenant_id=tenant_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    crud.concept_mapping.remove(db=db, id=mapping_id, tenant_id=tenant_id)


@router.post("/extract-code-concepts", status_code=status.HTTP_202_ACCEPTED)
def extract_code_concepts(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks = None,
) -> Any:
    """
    Extract ontology concepts from ALL completed code components.
    This is a backfill endpoint — extracts concepts from existing structured_analysis
    without making additional AI calls. Creates code-layer concepts for the BOE.
    """
    from app.services.code_analysis_service import code_analysis_service
    from app.models.code_component import CodeComponent

    # Get all completed components with structured_analysis
    components = db.query(CodeComponent).filter(
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.analysis_status == "completed",
        CodeComponent.structured_analysis.isnot(None),
    ).all()

    if not components:
        return {"message": "No completed code components found", "concepts_extracted": 0}

    total_concepts = 0
    for comp in components:
        try:
            code_analysis_service._extract_ontology_from_analysis(
                db=db,
                structured_analysis=comp.structured_analysis,
                component_name=comp.name,
                tenant_id=tenant_id,
            )
            total_concepts += 1
        except Exception as e:
            pass  # Non-fatal, continue with other components

    db.commit()

    return {
        "message": f"Code concepts extracted from {total_concepts} components",
        "components_processed": total_concepts,
        "total_components": len(components),
    }


# ============================================================
# CROSS-PROJECT MAPPING ENDPOINTS (SPRINT 4 Phase 3)
# ============================================================

@router.post("/cross-project/run", status_code=status.HTTP_202_ACCEPTED)
def trigger_cross_project_mapping(
    *,
    initiative_a_id: int = Query(..., description="First project ID"),
    initiative_b_id: int = Query(..., description="Second project ID"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks = None,
) -> Any:
    """
    Trigger 3-tier cross-project mapping between two projects.
    Runs in background: exact → fuzzy → AI validation.
    """
    if initiative_a_id == initiative_b_id:
        raise HTTPException(status_code=400, detail="Cannot map a project to itself")

    from app.services.cross_project_mapping_service import cross_project_mapping_service

    def _run():
        return cross_project_mapping_service.run_cross_project_mapping(
            db=db, initiative_a_id=initiative_a_id,
            initiative_b_id=initiative_b_id, tenant_id=tenant_id
        )

    background_tasks.add_task(_run)
    return {
        "message": "Cross-project mapping started",
        "initiative_a_id": initiative_a_id,
        "initiative_b_id": initiative_b_id,
    }


@router.get("/cross-project/mappings")
def list_cross_project_mappings(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Filter by project"),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 200,
) -> Any:
    """List cross-project mappings with enriched concept/project names."""
    if status_filter:
        mappings = crud.cross_project_mapping.get_by_status(
            db=db, status=status_filter, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    elif initiative_id:
        mappings = crud.cross_project_mapping.get_by_initiative(
            db=db, initiative_id=initiative_id, tenant_id=tenant_id,
            skip=skip, limit=limit
        )
    else:
        mappings = crud.cross_project_mapping.get_all_for_tenant(
            db=db, tenant_id=tenant_id, skip=skip, limit=limit
        )

    result = []
    for m in mappings:
        concept_a = crud.ontology_concept.get(db=db, id=m.concept_a_id, tenant_id=tenant_id)
        concept_b = crud.ontology_concept.get(db=db, id=m.concept_b_id, tenant_id=tenant_id)
        init_a = crud.initiative.get(db=db, id=m.initiative_a_id, tenant_id=tenant_id)
        init_b = crud.initiative.get(db=db, id=m.initiative_b_id, tenant_id=tenant_id)
        result.append({
            "id": m.id,
            "tenant_id": m.tenant_id,
            "concept_a_id": m.concept_a_id,
            "concept_b_id": m.concept_b_id,
            "initiative_a_id": m.initiative_a_id,
            "initiative_b_id": m.initiative_b_id,
            "mapping_method": m.mapping_method,
            "confidence_score": m.confidence_score,
            "status": m.status,
            "relationship_type": m.relationship_type,
            "ai_reasoning": m.ai_reasoning,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "concept_a_name": concept_a.name if concept_a else "Unknown",
            "concept_a_type": concept_a.concept_type if concept_a else "Unknown",
            "concept_b_name": concept_b.name if concept_b else "Unknown",
            "concept_b_type": concept_b.concept_type if concept_b else "Unknown",
            "initiative_a_name": init_a.name if init_a else "Unknown",
            "initiative_b_name": init_b.name if init_b else "Unknown",
        })
    return result


@router.put("/cross-project/mappings/{mapping_id}/confirm")
def confirm_cross_project_mapping(
    mapping_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Confirm a candidate cross-project mapping."""
    result = crud.cross_project_mapping.confirm_mapping(
        db=db, mapping_id=mapping_id, tenant_id=tenant_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "confirmed", "mapping_id": mapping_id}


@router.put("/cross-project/mappings/{mapping_id}/reject")
def reject_cross_project_mapping(
    mapping_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Reject a candidate cross-project mapping."""
    result = crud.cross_project_mapping.reject_mapping(
        db=db, mapping_id=mapping_id, tenant_id=tenant_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "rejected", "mapping_id": mapping_id}


@router.get("/cross-project/stats")
def get_cross_project_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get cross-project mapping statistics."""
    all_mappings = crud.cross_project_mapping.get_all_for_tenant(
        db=db, tenant_id=tenant_id
    )
    confirmed = sum(1 for m in all_mappings if m.status == "confirmed")
    candidates = sum(1 for m in all_mappings if m.status == "candidate")
    # Count unique project pairs
    pairs = set()
    for m in all_mappings:
        pair = tuple(sorted([m.initiative_a_id, m.initiative_b_id]))
        pairs.add(pair)

    return {
        "total_mappings": len(all_mappings),
        "confirmed_mappings": confirmed,
        "candidate_mappings": candidates,
        "project_pairs": len(pairs),
    }


# ============================================================
# META-GRAPH ENDPOINT (SPRINT 4 Phase 3 — Org-Wide View)
# ============================================================

@router.get("/graph/meta", response_model=None)
def get_meta_graph(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Org-wide meta-graph: all concepts clustered by project,
    with both intra-project edges and cross-project edges.
    """
    # Get all concepts with their project assignments
    concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)
    cross_mappings = crud.cross_project_mapping.get_all_for_tenant(
        db=db, tenant_id=tenant_id
    )

    # Build nodes with project cluster info
    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "concept_type": c.concept_type,
            "source_type": c.source_type,
            "initiative_id": c.initiative_id,
            "confidence_score": c.confidence_score,
        }
        for c in concepts
    ]

    # Intra-project edges (from OntologyRelationship)
    intra_edges = [
        {
            "id": r.id,
            "source_concept_id": r.source_concept_id,
            "target_concept_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "confidence_score": r.confidence_score,
            "edge_type": "intra_project",
        }
        for r in relationships
    ]

    # Cross-project edges (from CrossProjectMapping)
    cross_edges = [
        {
            "id": m.id + 100000,  # Offset to avoid ID collision with intra edges
            "source_concept_id": m.concept_a_id,
            "target_concept_id": m.concept_b_id,
            "relationship_type": m.relationship_type,
            "confidence_score": m.confidence_score,
            "edge_type": "cross_project",
            "status": m.status,
            "mapping_method": m.mapping_method,
            "initiative_a_id": m.initiative_a_id,
            "initiative_b_id": m.initiative_b_id,
        }
        for m in cross_mappings
        if m.status != "rejected"
    ]

    # Get project names for clustering
    projects = crud.initiative.get_multi(db=db, tenant_id=tenant_id)
    project_map = {p.id: p.name for p in projects}

    return {
        "nodes": nodes,
        "intra_edges": intra_edges,
        "cross_edges": cross_edges,
        "total_nodes": len(nodes),
        "total_intra_edges": len(intra_edges),
        "total_cross_edges": len(cross_edges),
        "projects": [
            {"id": p.id, "name": p.name}
            for p in projects
        ],
    }
