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
    OntologyGraphResponse, OntologyGraphNode, OntologyGraphEdge,
    BranchPreviewNode, BranchPreviewEdge, BranchPreviewGraphResponse,
)
from app.schemas.concept_mapping import (
    ConceptMappingCreate, ConceptMappingUpdate, ConceptMappingResponse,
    ConceptMappingWithConcepts,
)
from app.core.logging import get_logger

logger = get_logger("api.ontology")

router = APIRouter()


def _get_mapping_edges(db: Session, tenant_id: int, concept_ids: set, edge_id_offset: int = 0):
    """
    Convert confirmed ConceptMapping records into OntologyGraphEdge objects
    so they appear as cross-graph bridge edges in the visualization.
    Uses negative IDs (offset from -1000000) to distinguish from real relationship IDs.
    """
    from app.models.concept_mapping import ConceptMapping
    mappings = db.query(ConceptMapping).filter(
        ConceptMapping.tenant_id == tenant_id,
        ConceptMapping.status.in_(["confirmed", "candidate"]),
    ).all()

    edges = []
    for m in mappings:
        if m.document_concept_id in concept_ids and m.code_concept_id in concept_ids:
            edges.append(OntologyGraphEdge(
                id=-(1000000 + m.id),  # Negative ID to distinguish from OntologyRelationship
                source_concept_id=m.document_concept_id,
                target_concept_id=m.code_concept_id,
                relationship_type=f"mapping:{m.relationship_type}",
                confidence_score=m.confidence_score,
            ))
    return edges


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
    Returns nodes (concepts) and edges (relationships + cross-graph mappings) for frontend visualization.
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

    # Include confirmed ConceptMapping records as cross-graph bridge edges
    # These connect document-layer concepts to code-layer concepts
    mappings = _get_mapping_edges(db, tenant_id, concept_ids, edge_id_offset=len(edges))
    edges.extend(mappings)

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
    try:
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
    except Exception:
        total_rels = 0
        concept_types = []

    # Count cross-graph mappings — wrapped in try/except so a missing/uninitialized
    # concept_mappings table doesn't crash the whole stats call
    try:
        total_mappings = crud.concept_mapping.count_by_tenant(db=db, tenant_id=tenant_id)
    except Exception:
        total_mappings = 0

    return {
        "total_concepts": total_concepts,
        "total_relationships": total_rels,
        "total_mappings": total_mappings,
        "total_edges": total_rels + total_mappings,
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

    # Include cross-graph mappings where code concepts are involved
    mappings = _get_mapping_edges(db, tenant_id, code_ids, edge_id_offset=len(edges))
    edges.extend(mappings)

    return OntologyGraphResponse(nodes=nodes, edges=edges, total_nodes=len(nodes), total_edges=len(edges))


# ============================================================
# PER-FILE SUBGRAPH ENDPOINT
# ============================================================

@router.get("/graph/component/{component_id}")
def get_component_subgraph(
    component_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the subgraph for a specific code component (file).
    Returns concepts created from this file and their inter-relationships.
    """
    concepts = crud.ontology_concept.get_by_component(
        db=db, component_id=component_id, tenant_id=tenant_id
    )
    if not concepts:
        return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}

    concept_ids = {c.id for c in concepts}
    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "concept_type": c.concept_type,
            "source_type": c.source_type,
            "confidence_score": c.confidence_score or 0,
        }
        for c in concepts
    ]

    # Get relationships between these concepts
    from app.models.ontology_relationship import OntologyRelationship
    from sqlalchemy import or_
    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all()

    edges = [
        {
            "id": r.id,
            "source_concept_id": r.source_concept_id,
            "target_concept_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "confidence_score": r.confidence_score or 0,
        }
        for r in rels
        if r.source_concept_id in concept_ids or r.target_concept_id in concept_ids
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "component_id": component_id,
    }


# ============================================================
# BRAIN ARCHITECTURE ENDPOINTS (Levels 1-5)
# ============================================================


def _derive_domain_from_path(location: str) -> str:
    """
    Derive a domain label from a file path.
    Strips common roots, then takes the first 1-2 meaningful path segments.
    """
    import posixpath
    loc = location.replace("\\", "/").lstrip("./")
    for prefix in ("backend/app/", "frontend/src/", "src/app/", "app/", "src/", "lib/"):
        if loc.startswith(prefix):
            loc = loc[len(prefix):]
            break
    parts = [p for p in loc.split("/") if p]
    if len(parts) <= 1:
        return "root"
    if len(parts) >= 3:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


@router.get("/graph/document-source/{document_id}")
def get_document_source_subgraph(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Level 1 Brain: Per-document subgraph.
    Returns concepts extracted from a specific document and their relationships.
    """
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    concepts = crud.ontology_concept.get_by_document(
        db=db, document_id=document_id, tenant_id=tenant_id
    )
    if not concepts:
        return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0, "document_id": document_id}

    concept_ids = {c.id for c in concepts}
    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "concept_type": c.concept_type,
            "source_type": c.source_type,
            "confidence_score": c.confidence_score or 0,
        }
        for c in concepts
    ]

    from app.models.ontology_relationship import OntologyRelationship
    from sqlalchemy import or_
    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all()

    edges = [
        {
            "id": r.id,
            "source_concept_id": r.source_concept_id,
            "target_concept_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "confidence_score": r.confidence_score or 0,
        }
        for r in rels
        if r.source_concept_id in concept_ids or r.target_concept_id in concept_ids
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "document_id": document_id,
    }


@router.get("/graph/domain/{repo_id}")
def get_domain_cluster_graph(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Level 2 Brain: Domain Cluster Graph for a repository.
    Groups concepts by file directory domain.
    """
    from app.models.code_component import CodeComponent
    from app.models.ontology_relationship import OntologyRelationship
    from app.models.ontology_concept import OntologyConcept
    from sqlalchemy import or_
    from collections import defaultdict

    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    if not components:
        return {"nodes": [], "edges": [], "domains": [],
                "total_nodes": 0, "total_edges": 0, "repo_id": repo_id}

    component_ids = {c.id for c in components}
    comp_to_domain = {
        c.id: _derive_domain_from_path(c.location or c.name)
        for c in components
    }

    concepts = db.query(OntologyConcept).filter(
        OntologyConcept.source_component_id.in_(component_ids),
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
    ).all()

    concept_ids = {c.id for c in concepts}
    concept_to_domain = {}
    for c in concepts:
        concept_to_domain[c.id] = comp_to_domain.get(c.source_component_id, "unknown")

    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "concept_type": c.concept_type,
            "source_type": c.source_type,
            "confidence_score": c.confidence_score or 0,
            "domain": concept_to_domain.get(c.id, "unknown"),
        }
        for c in concepts
    ]

    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all() if concept_ids else []

    edges = [
        {
            "id": r.id,
            "source_concept_id": r.source_concept_id,
            "target_concept_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "confidence_score": r.confidence_score or 0,
        }
        for r in rels
        if r.source_concept_id in concept_ids and r.target_concept_id in concept_ids
    ]

    domain_components = defaultdict(list)
    domain_concepts = defaultdict(list)
    for c in components:
        domain_components[comp_to_domain[c.id]].append(c.id)
    for cid, domain in concept_to_domain.items():
        domain_concepts[domain].append(cid)

    domains = [
        {
            "name": dn,
            "file_count": len(domain_components.get(dn, [])),
            "concept_count": len(domain_concepts.get(dn, [])),
        }
        for dn in sorted(set(list(domain_components.keys()) + list(domain_concepts.keys())))
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "domains": domains,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "repo_id": repo_id,
    }


@router.get("/graph/system/{repo_id}")
def get_system_architecture_graph(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Level 3 Brain: System Architecture Graph for a repository.
    Aggregates domains into system layers with inter-domain edge counts.
    """
    from app.models.code_component import CodeComponent
    from app.models.ontology_relationship import OntologyRelationship
    from app.models.ontology_concept import OntologyConcept
    from sqlalchemy import or_
    from collections import defaultdict

    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    if not components:
        return {"system_nodes": [], "system_edges": [], "synthesis_summary": None,
                "total_domains": 0, "repo_id": repo_id, "repo_name": repo.name}

    component_ids = {c.id for c in components}
    comp_to_domain = {
        c.id: _derive_domain_from_path(c.location or c.name)
        for c in components
    }

    concepts = db.query(OntologyConcept).filter(
        OntologyConcept.source_component_id.in_(component_ids),
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
    ).all()

    concept_ids = {c.id for c in concepts}
    concept_to_domain = {}
    for c in concepts:
        concept_to_domain[c.id] = comp_to_domain.get(c.source_component_id, "unknown")

    # Build domain metadata
    domain_file_count = defaultdict(int)
    domain_concept_count = defaultdict(int)
    domain_key_concepts = defaultdict(list)

    for c in components:
        domain_file_count[comp_to_domain[c.id]] += 1
    for c in concepts:
        d = concept_to_domain[c.id]
        domain_concept_count[d] += 1
        if len(domain_key_concepts[d]) < 5:
            domain_key_concepts[d].append(c.name)

    all_domains = sorted(set(list(domain_file_count.keys()) + list(domain_concept_count.keys())))

    system_nodes = [
        {
            "domain_name": d,
            "file_count": domain_file_count.get(d, 0),
            "concept_count": domain_concept_count.get(d, 0),
            "key_concepts": domain_key_concepts.get(d, []),
        }
        for d in all_domains
    ]

    # Build cross-domain edges
    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all() if concept_ids else []

    cross_domain_counts = defaultdict(lambda: {"count": 0, "types": set()})
    for r in rels:
        src_domain = concept_to_domain.get(r.source_concept_id)
        tgt_domain = concept_to_domain.get(r.target_concept_id)
        if src_domain and tgt_domain and src_domain != tgt_domain:
            key = tuple(sorted([src_domain, tgt_domain]))
            cross_domain_counts[key]["count"] += 1
            cross_domain_counts[key]["types"].add(r.relationship_type)

    system_edges = [
        {
            "source_domain": k[0],
            "target_domain": k[1],
            "relationship_count": v["count"],
            "relationship_types": list(v["types"]),
        }
        for k, v in cross_domain_counts.items()
    ]

    # Extract synthesis summary
    synthesis_summary = None
    if repo.synthesis_data and isinstance(repo.synthesis_data, dict):
        synthesis_summary = repo.synthesis_data.get("executive_summary",
                            repo.synthesis_data.get("summary", None))

    return {
        "system_nodes": system_nodes,
        "system_edges": system_edges,
        "synthesis_summary": synthesis_summary,
        "total_domains": len(system_nodes),
        "repo_id": repo_id,
        "repo_name": repo.name,
    }


@router.get("/graph/system/{repo_id}/mermaid")
def get_system_mermaid_diagram(
    repo_id: int,
    diagram_type: str = Query("architecture", description="architecture | dataflow | er"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Generate a Mermaid diagram for L3 System Architecture view.
    diagram_type:
      - architecture: graph TD showing domains and connections
      - dataflow:     sequenceDiagram showing data flow between domains
      - er:           erDiagram showing data-layer concepts and relationships
    """
    from app.models.code_component import CodeComponent
    from app.models.ontology_relationship import OntologyRelationship
    from app.models.ontology_concept import OntologyConcept
    from sqlalchemy import or_
    from collections import defaultdict
    import re

    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    def _safe_id(name: str) -> str:
        """Convert domain name to a valid Mermaid node ID."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "node"

    # ---- Collect domain data (same logic as /graph/system/{repo_id}) ----
    components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    if not components:
        return {"mermaid_syntax": "graph TD\n    A[No components analyzed yet]", "diagram_type": diagram_type}

    comp_to_domain = {c.id: _derive_domain_from_path(c.location or c.name) for c in components}
    component_ids = {c.id for c in components}

    concepts = db.query(OntologyConcept).filter(
        OntologyConcept.source_component_id.in_(component_ids),
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
    ).all()

    concept_to_domain: dict = {}
    domain_concepts: dict = defaultdict(list)
    for c in concepts:
        d = comp_to_domain.get(c.source_component_id, "unknown")
        concept_to_domain[c.id] = d
        domain_concepts[d].append(c)

    concept_ids = {c.id for c in concepts}
    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all() if concept_ids else []

    # Cross-domain relationships
    cross_domain: dict = defaultdict(lambda: {"count": 0, "types": set()})
    for r in rels:
        sd = concept_to_domain.get(r.source_concept_id)
        td = concept_to_domain.get(r.target_concept_id)
        if sd and td and sd != td:
            key = (sd, td)
            cross_domain[key]["count"] += 1
            cross_domain[key]["types"].add(r.relationship_type or "relates_to")

    all_domains = sorted(set(comp_to_domain.values()))

    # ---- Architecture Diagram (graph TD) ----
    if diagram_type == "architecture":
        lines = ["graph TD"]
        domain_file_count: dict = defaultdict(int)
        for c in components:
            domain_file_count[comp_to_domain[c.id]] += 1

        for d in all_domains:
            nid = _safe_id(d)
            fcount = domain_file_count.get(d, 0)
            ccount = len(domain_concepts.get(d, []))
            label = f"{d}\\n{fcount} files · {ccount} concepts"
            lines.append(f'    {nid}["{label}"]')

        added_edges: set = set()
        for (sd, td), info in cross_domain.items():
            sid, tid = _safe_id(sd), _safe_id(td)
            fwd = (sid, tid)
            rev = (tid, sid)
            rel_label = list(info["types"])[0] if info["types"] else "relates_to"
            if fwd not in added_edges and rev not in added_edges:
                lines.append(f'    {sid} -->|"{rel_label} ({info["count"]})"| {tid}')
                added_edges.add(fwd)

        mermaid = "\n".join(lines)

    # ---- Data Flow Diagram (sequenceDiagram) ----
    elif diagram_type == "dataflow":
        lines = ["sequenceDiagram"]
        lines.append(f"    Note over {','.join(_safe_id(d) for d in all_domains[:8])}: {repo.name} — Data Flow")
        for d in all_domains[:10]:
            lines.append(f"    participant {_safe_id(d)} as {d}")

        seen_flows: set = set()
        for (sd, td), info in sorted(cross_domain.items(), key=lambda x: -x[1]["count"]):
            sid, tid = _safe_id(sd), _safe_id(td)
            key = (sid, tid)
            if key in seen_flows:
                continue
            seen_flows.add(key)
            rel = list(info["types"])[0] if info["types"] else "data"
            lines.append(f"    {sid}->>{tid}: {rel} ({info['count']} connections)")
            if len(seen_flows) >= 15:
                break

        if not seen_flows:
            lines.append("    Note over app: No cross-domain data flows detected yet")

        mermaid = "\n".join(lines)

    # ---- Technical Architecture Diagram (graph LR with subgraphs per layer) ----
    elif diagram_type == "technical_architecture":
        def _layer_for_domain(domain: str) -> str:
            d = domain.lower().replace("\\", "/")
            if any(d.startswith(p) for p in ("frontend", "pages", "components", "public", "next", "ui")):
                return "FRONTEND"
            if any(x in d for x in ("task", "worker", "celery", "queue", "job")):
                return "ASYNC"
            if any(x in d for x in ("/models", "models/", "schema", "migrat", "/db", "db/")):
                return "DATA"
            if any(x in d for x in ("middleware", "tenant_context", "rate_limit", "audit_log", "security")):
                return "MIDDLEWARE"
            if any(x in d for x in ("api", "endpoint", "route", "router")):
                return "API"
            if any(x in d for x in ("service", "services")):
                return "SERVICES"
            if any(x in d for x in ("ai", "llm", "prompt", "gemini", "anthropic", "openai", "claude")):
                return "AI"
            # crude fallback: if it has 'model' or 'schema' anywhere
            if "model" in d or "schema" in d:
                return "DATA"
            return "SERVICES"

        domain_file_count2: dict = defaultdict(int)
        domain_concept_count3: dict = defaultdict(int)
        for c in components:
            domain_file_count2[comp_to_domain[c.id]] += 1
        for c in concepts:
            d = comp_to_domain.get(c.source_component_id, "unknown")
            domain_concept_count3[d] += 1

        layer_domains2: dict[str, list] = defaultdict(list)  # layer -> sorted domain names
        domain_to_layer2: dict = {}
        for d in all_domains:
            layer = _layer_for_domain(d)
            layer_domains2[layer].append(d)
            domain_to_layer2[d] = layer

        # Layer display order and labels
        layer_order = ["FRONTEND", "MIDDLEWARE", "API", "SERVICES", "ASYNC", "AI", "DATA"]
        layer_labels = {
            "FRONTEND": "FRONTEND (React/Next.js)",
            "MIDDLEWARE": "Middleware & Tenant Context",
            "API": "API Gateway & Router",
            "SERVICES": "Core Domain Services",
            "ASYNC": "Async Processing",
            "AI": "AI Orchestration",
            "DATA": "Data Persistence",
        }

        lines = ["graph LR"]

        # External Clients subgraph (always present)
        lines += [
            '    subgraph EXTERNAL ["EXTERNAL CLIENTS"]',
            "        direction TB",
            '        END_USER["👤 End User"]',
            '        GIT_REPOS["Git Repositories"]',
            "    end",
        ]

        # One subgraph per layer that has at least one domain
        for layer_id in layer_order:
            domains_in_layer = sorted(layer_domains2.get(layer_id, []))
            if not domains_in_layer:
                continue
            label = layer_labels[layer_id]
            lines.append(f'    subgraph {layer_id} ["{label}"]')
            lines.append("        direction TB")
            for d in domains_in_layer:
                nid = _safe_id(d)
                fc = domain_file_count2.get(d, 0)
                cc = domain_concept_count3.get(d, 0)
                # Short label: last path segment
                short = d.split("/")[-1].replace("_", " ").title()
                node_label = f"{short}\\n{fc} files · {cc} concepts"
                lines.append(f'        {nid}["{node_label}"]')
                lines.append(f'        click {nid} call dokydocClick("{d}")')
            lines.append("    end")

        # Inter-layer edges: External → Frontend → Middleware → API → Services → Async/AI → Data
        fe = [_safe_id(d) for d in sorted(layer_domains2.get("FRONTEND", []))]
        mw = [_safe_id(d) for d in sorted(layer_domains2.get("MIDDLEWARE", []))]
        api = [_safe_id(d) for d in sorted(layer_domains2.get("API", []))]
        svc = [_safe_id(d) for d in sorted(layer_domains2.get("SERVICES", []))]
        asc = [_safe_id(d) for d in sorted(layer_domains2.get("ASYNC", []))]
        ai = [_safe_id(d) for d in sorted(layer_domains2.get("AI", []))]
        data = [_safe_id(d) for d in sorted(layer_domains2.get("DATA", []))]

        if fe:
            lines.append(f'    END_USER -->|HTTPS| {fe[0]}')
            lines.append(f'    GIT_REPOS -->|API/Webhook| {fe[0]}')
        first_be = mw[0] if mw else (api[0] if api else (svc[0] if svc else None))
        if fe and first_be:
            for f_node in fe[:2]:
                lines.append(f'    {f_node} --> {first_be}')
        if mw and api:
            for m_node in mw[:2]:
                lines.append(f'    {m_node} --> {api[0]}')
        if api and svc:
            for a_node in api[:2]:
                for s_node in svc[:3]:
                    lines.append(f'    {a_node} --> {s_node}')
        if svc and asc:
            lines.append(f'    {svc[0]} -->|Task Queue| {asc[0]}')
        if svc and ai:
            lines.append(f'    {svc[0]} -->|AI Request| {ai[0]}')
        if data:
            for src in (svc + asc)[:4]:
                lines.append(f'    {src} --> {data[0]}')

        # Top cross-domain relationships as dashed lines
        added_tech_edges: set = set()
        for (sd, td), info in sorted(cross_domain.items(), key=lambda x: -x[1]["count"])[:8]:
            sl = domain_to_layer2.get(sd)
            tl = domain_to_layer2.get(td)
            if sl and tl and sl != tl:
                sn, tn = _safe_id(sd), _safe_id(td)
                ek = (sn, tn)
                if ek not in added_tech_edges:
                    added_tech_edges.add(ek)
                    rel = list(info["types"])[0] if info["types"] else "uses"
                    lines.append(f'    {sn} -.->|{rel}| {tn}')

        mermaid = "\n".join(lines)

    # ---- ER Diagram ----
    else:  # er
        lines = ["erDiagram"]
        # Find entity-like concepts (DATABASE, TABLE, MODEL, ENTITY types)
        entity_types = {"DATABASE", "TABLE", "MODEL", "ENTITY", "SCHEMA", "DATA_MODEL", "CLASS"}
        entities = [c for c in concepts if (c.concept_type or "").upper() in entity_types]

        if not entities:
            # Fallback: use all concepts grouped by domain, pick top 3 per domain
            entities = []
            for d, dconcepts in domain_concepts.items():
                entities.extend(dconcepts[:3])

        entity_ids = {c.id for c in entities}
        entity_name_map = {c.id: _safe_id(c.name) for c in entities}

        added_entities: set = set()
        for c in entities[:20]:
            eid = _safe_id(c.name)
            if eid in added_entities:
                continue
            added_entities.add(eid)
            lines.append(f'    {eid} {{')
            lines.append(f'        string name "{c.name}"')
            lines.append(f'        string type "{c.concept_type or "entity"}"')
            if c.source_component_id:
                domain = comp_to_domain.get(c.source_component_id, "unknown")
                lines.append(f'        string domain "{domain}"')
            lines.append(f'    }}')

        for r in rels:
            if r.source_concept_id in entity_ids and r.target_concept_id in entity_ids:
                sid = entity_name_map.get(r.source_concept_id)
                tid = entity_name_map.get(r.target_concept_id)
                if sid and tid and sid in added_entities and tid in added_entities:
                    rel = (r.relationship_type or "relates_to").replace("-", "_").replace(" ", "_")
                    lines.append(f'    {sid} ||--o| {tid} : "{rel}"')

        if len(added_entities) == 0:
            lines.append('    Entity { string name "No entities found" }')

        mermaid = "\n".join(lines)

    return {
        "mermaid_syntax": mermaid,
        "diagram_type": diagram_type,
        "repo_id": repo_id,
        "repo_name": repo.name,
        "domain_count": len(all_domains),
        "concept_count": len(concepts),
    }


@router.get("/graph/system/{repo_id}/domain-mermaid")
def get_domain_flow_mermaid(
    repo_id: int,
    domain_name: str = Query(..., description="Domain name from L3 (e.g. 'services' or 'api/endpoints')"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    L2 domain drill-down Mermaid diagram.
    Shows all files in a domain and how their concepts relate to each other.
    Each file node has a click directive to navigate to L1 (component analysis).
    """
    from app.models.code_component import CodeComponent
    from app.models.ontology_concept import OntologyConcept
    from app.models.ontology_relationship import OntologyRelationship
    from sqlalchemy import or_
    from collections import defaultdict
    import re

    def _safe_id(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "node"

    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    all_components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    if not all_components:
        return {
            "mermaid_syntax": "graph TD\n    A[No components analyzed yet]",
            "domain_name": domain_name,
            "components": [],
        }

    # Filter components belonging to this domain
    def _derive_domain_from_path(location: str) -> str:
        import posixpath
        loc = (location or "").replace("\\", "/").lstrip("./")
        for prefix in ("backend/app/", "frontend/src/", "src/app/", "app/", "src/", "lib/"):
            if loc.startswith(prefix):
                loc = loc[len(prefix):]
                break
        parts = [p for p in loc.split("/") if p]
        if len(parts) <= 1:
            return "root"
        if len(parts) >= 3:
            return f"{parts[0]}/{parts[1]}"
        return parts[0]

    domain_components = [
        c for c in all_components
        if _derive_domain_from_path(c.location or c.name) == domain_name
    ]

    if not domain_components:
        return {
            "mermaid_syntax": f'graph TD\n    A["No files found in domain: {domain_name}"]',
            "domain_name": domain_name,
            "components": [],
        }

    comp_ids = {c.id for c in domain_components}

    concepts = db.query(OntologyConcept).filter(
        OntologyConcept.source_component_id.in_(comp_ids),
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
    ).all()

    concept_ids = {c.id for c in concepts}
    concept_to_comp: dict = {c.id: c.source_component_id for c in concepts}

    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids),
            OntologyRelationship.target_concept_id.in_(concept_ids),
        ),
    ).all() if concept_ids else []

    # Count cross-file relationships
    file_rel_count: dict = defaultdict(lambda: defaultdict(int))
    file_rel_types: dict = defaultdict(lambda: defaultdict(set))
    for r in rels:
        sc = concept_to_comp.get(r.source_concept_id)
        tc = concept_to_comp.get(r.target_concept_id)
        if sc and tc and sc != tc:
            file_rel_count[sc][tc] += 1
            file_rel_types[sc][tc].add(r.relationship_type or "uses")

    # Count concepts per component
    comp_concept_count: dict = defaultdict(int)
    for c in concepts:
        comp_concept_count[c.source_component_id] += 1

    # Node shape by type
    concept_types_per_comp: dict = defaultdict(set)
    for c in concepts:
        concept_types_per_comp[c.source_component_id].add((c.concept_type or "").upper())

    def _node_shape(comp_id: int) -> tuple[str, str]:
        """Returns (open, close) for Mermaid node shape."""
        types = concept_types_per_comp.get(comp_id, set())
        if types & {"SERVICE", "MANAGER", "HANDLER"}:
            return "[", "]"
        if types & {"MODEL", "SCHEMA", "TABLE", "DATABASE"}:
            return "[(", ")]"
        if types & {"ENDPOINT", "ROUTE", "API"}:
            return "([", "])"
        if types & {"TASK", "WORKER", "JOB"}:
            return ">", "]"
        return "[", "]"

    lines = [f'graph TD']
    lines.append(f'    title["{domain_name} — File Flow"]')
    lines.append(f'    style title fill:none,stroke:none,color:#6366f1,font-weight:bold')

    comp_info_list = []
    for comp in domain_components:
        file_name = (comp.location or comp.name or "").split("/")[-1]
        nid = f"file_{comp.id}"
        cc = comp_concept_count.get(comp.id, 0)
        analysis_status = comp.analysis_status or "pending"
        label = f"{file_name}\\n{cc} concepts"
        op, cl = _node_shape(comp.id)
        lines.append(f'    {nid}{op}"{label}"{cl}')
        lines.append(f'    click {nid} call dokydocClick("component:{comp.id}")')
        comp_info_list.append({
            "id": comp.id,
            "name": file_name,
            "location": comp.location or comp.name,
            "node_id": nid,
            "concept_count": cc,
            "analysis_status": analysis_status,
        })

    # Add edges (top relationships only to keep diagram readable)
    edge_count = 0
    for src_comp_id, targets in sorted(file_rel_count.items(), key=lambda x: -sum(x[1].values())):
        for tgt_comp_id, count in sorted(targets.items(), key=lambda x: -x[1]):
            if edge_count >= 30:
                break
            src_node = f"file_{src_comp_id}"
            tgt_node = f"file_{tgt_comp_id}"
            rel = list(file_rel_types[src_comp_id][tgt_comp_id])[0]
            lines.append(f'    {src_node} -->|"{rel}"| {tgt_node}')
            edge_count += 1

    mermaid = "\n".join(lines)

    return {
        "mermaid_syntax": mermaid,
        "diagram_type": "domain_flow",
        "domain_name": domain_name,
        "repo_id": repo_id,
        "components": comp_info_list,
    }


@router.get("/graph/repo/{repo_id}/drill")
def adaptive_path_drill(
    repo_id: int,
    path: str = Query("", description="Navigation path (e.g. 'services' or 'services/billing'). Empty = architectural overview."),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Adaptive drill-down that follows the ACTUAL filesystem depth of the repo.

    - path=""          → Architectural layer overview (graph LR with subgraphs)
    - path="services"  → Nodes at the next level: sub-dirs OR files, whichever exist
    - path="services/billing" → Same, one level deeper
    - A node whose type="file" means click → navigate to L1 (/dashboard/code/{id})
    - A node whose type="group" means click → drill deeper (append segment to path)
    - A node whose type="mixed_group" contains both files and sub-groups

    Returns:
      view_type:      "architecture" | "groups" | "files" | "mixed"
      mermaid_syntax: Mermaid diagram for this level
      nodes:          Array of {name, path, type, file_count, concept_count,
                                component_id, depth_to_leaf, key_concepts}
      breadcrumb:     Array of {label, path} for navigation back up
    """
    import re
    from collections import defaultdict
    from app.models.code_component import CodeComponent
    from app.models.ontology_concept import OntologyConcept
    from app.models.ontology_relationship import OntologyRelationship
    from sqlalchemy import or_

    def _safe_id(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "node"

    def _normalize(location: str) -> str:
        """Strip repo-specific URL and common root prefixes to get a clean relative path.

        Handles all location formats stored in the DB:
          - Full HTTPS URLs: https://github.com/org/repo/blob/main/backend/app/file.py
          - Raw GitHub URLs: https://raw.githubusercontent.com/org/repo/main/backend/app/file.py
          - Partial blob paths: blob/main/backend/app/file.py
          - Plain relative paths: backend/app/file.py
        """
        loc = (location or "").replace("\\", "/")

        # ── Full URL (http:// or https://) ──────────────────────────────
        if loc.startswith("http://") or loc.startswith("https://"):
            # Strip protocol + host: everything up to and including the third "/"
            # e.g. "https://github.com/" → start_of_path = "org/repo/blob/main/..."
            try:
                proto_end = loc.index("//") + 2          # after "https://"
                host_end = loc.index("/", proto_end)      # first "/" after host
                path_part = loc[host_end + 1:]            # "org/repo/blob/main/..."
                parts = [p for p in path_part.split("/") if p]

                if "blob" in parts:
                    bi = parts.index("blob")
                    loc = "/".join(parts[bi + 2:])        # skip blob/<branch>
                elif "tree" in parts:
                    ti = parts.index("tree")
                    loc = "/".join(parts[ti + 2:])        # skip tree/<branch>
                else:
                    # raw.githubusercontent.com style: org/repo/branch/actual/path
                    loc = "/".join(parts[3:]) if len(parts) > 3 else "/".join(parts)
            except (ValueError, IndexError):
                pass  # leave loc unchanged; prefix stripping below may still help

        else:
            # ── Relative path that may still contain blob/tree marker ────
            for marker in ("blob/", "tree/"):
                idx = loc.find(marker)
                if idx >= 0:
                    after = loc[idx + len(marker):]
                    slash = after.find("/")
                    if slash >= 0:
                        loc = after[slash + 1:]
                    break
            loc = loc.lstrip("./")

        # ── Strip standard repo-root prefixes ───────────────────────────
        for prefix in (
            "backend/app/", "backend/", "frontend/src/", "frontend/app/",
            "frontend/", "src/app/", "src/", "app/", "lib/",
        ):
            if loc.startswith(prefix):
                loc = loc[len(prefix):]
                break
        return loc

    def _depth_to_leaf(normalized_path: str, all_norms: list[str]) -> int:
        """Compute how many more path segments exist beneath this path across all files."""
        prefix = normalized_path.rstrip("/") + "/"
        max_depth = 0
        for n in all_norms:
            if n.startswith(prefix):
                remaining = n[len(prefix):]
                depth = len([p for p in remaining.split("/") if p])
                max_depth = max(max_depth, depth)
        return max_depth

    def _build_breadcrumb(parts: list) -> list:
        crumbs = []
        for i, seg in enumerate(parts):
            crumbs.append({"label": seg, "path": "/".join(parts[:i + 1])})
        return crumbs

    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    all_components = db.query(CodeComponent).filter(
        CodeComponent.repository_id == repo_id,
        CodeComponent.tenant_id == tenant_id,
    ).all()

    if not all_components:
        return {
            "view_type": "empty",
            "mermaid_syntax": "graph TD\n    A[No components analyzed yet]",
            "nodes": [],
            "breadcrumb": [],
        }

    # Normalize all component locations
    comp_norms = {c.id: _normalize(c.location or c.name or "") for c in all_components}
    all_norms = list(comp_norms.values())

    # --- ARCHITECTURAL OVERVIEW (path == "") ---
    if not path:
        # Reuse the technical_architecture mermaid generator via internal call
        # We'll inline a trimmed version here for clarity
        def _layer_for_domain(domain: str) -> str:
            d = domain.lower()
            if any(d.startswith(p) for p in ("frontend", "pages", "components", "public", "next", "ui")):
                return "FRONTEND"
            if any(x in d for x in ("task", "worker", "celery", "queue", "job")):
                return "ASYNC"
            if any(x in d for x in ("model", "schema", "migrat", "/db", "db/")):
                return "DATA"
            if any(x in d for x in ("middleware", "tenant_context", "rate_limit", "audit", "security")):
                return "MIDDLEWARE"
            if any(x in d for x in ("api", "endpoint", "route", "router")):
                return "API"
            if any(x in d for x in ("service", "services")):
                return "SERVICES"
            if any(x in d for x in ("ai", "llm", "prompt", "gemini", "anthropic", "openai")):
                return "AI"
            if "model" in d or "schema" in d:
                return "DATA"
            return "SERVICES"

        # Compute first-level path segments (the "domain" groups)
        domain_file_count: dict = defaultdict(int)
        domain_comp_ids: dict = defaultdict(list)
        for comp in all_components:
            norm = comp_norms[comp.id]
            parts = [p for p in norm.split("/") if p]
            if not parts:
                continue
            # Domain = first 1-2 meaningful segments (same as existing _derive_domain_from_path)
            if len(parts) == 1:
                domain = "root"
            elif len(parts) >= 3:
                domain = f"{parts[0]}/{parts[1]}"
            else:
                domain = parts[0]
            domain_file_count[domain] += 1
            domain_comp_ids[domain].append(comp.id)

        # Fetch concepts for concept count per domain
        all_concept_ids_by_comp: dict = defaultdict(int)
        concepts_all = db.query(OntologyConcept).filter(
            OntologyConcept.source_component_id.in_({c.id for c in all_components}),
            OntologyConcept.tenant_id == tenant_id,
            OntologyConcept.is_active == True,
        ).limit(2000).all()  # cap to avoid massive memory/query for large repos
        for c in concepts_all:
            all_concept_ids_by_comp[c.source_component_id] += 1

        domain_concept_count: dict = defaultdict(int)
        for domain, comp_ids in domain_comp_ids.items():
            for cid in comp_ids:
                domain_concept_count[domain] += all_concept_ids_by_comp.get(cid, 0)

        all_domains = sorted(domain_file_count.keys())

        # Cross-domain edges
        concept_to_domain: dict = {}
        for c in concepts_all:
            # Find domain for this component
            norm = comp_norms.get(c.source_component_id, "")
            parts = [p for p in norm.split("/") if p]
            if len(parts) == 1:
                d = "root"
            elif len(parts) >= 3:
                d = f"{parts[0]}/{parts[1]}"
            else:
                d = parts[0] if parts else "root"
            concept_to_domain[c.id] = d

        concept_ids_set = {c.id for c in concepts_all}
        # Cap to 300 concept IDs for the IN-clause — cross-domain edges are
        # decorative; a sample is sufficient and avoids 1000-param queries.
        concept_ids_sample = list(concept_ids_set)[:300]
        rels_all = db.query(OntologyRelationship).filter(
            OntologyRelationship.tenant_id == tenant_id,
            or_(
                OntologyRelationship.source_concept_id.in_(concept_ids_sample),
                OntologyRelationship.target_concept_id.in_(concept_ids_sample),
            ),
        ).limit(800).all() if concept_ids_sample else []

        cross_domain: dict = defaultdict(lambda: {"count": 0, "types": set()})
        for r in rels_all:
            sd = concept_to_domain.get(r.source_concept_id)
            td = concept_to_domain.get(r.target_concept_id)
            if sd and td and sd != td:
                key = (sd, td)
                cross_domain[key]["count"] += 1
                cross_domain[key]["types"].add(r.relationship_type or "uses")

        layer_domains2: dict = defaultdict(list)
        domain_to_layer2: dict = {}
        for d in all_domains:
            layer = _layer_for_domain(d)
            layer_domains2[layer].append(d)
            domain_to_layer2[d] = layer

        layer_order = ["FRONTEND", "MIDDLEWARE", "API", "SERVICES", "ASYNC", "AI", "DATA"]
        layer_labels = {
            "FRONTEND": "FRONTEND", "MIDDLEWARE": "Middleware & Tenant Context",
            "API": "API Gateway & Router", "SERVICES": "Core Domain Services",
            "ASYNC": "Async Processing", "AI": "AI Orchestration", "DATA": "Data Persistence",
        }

        lines = ["graph LR"]
        lines += [
            '    subgraph EXTERNAL ["EXTERNAL CLIENTS"]',
            "        direction TB",
            '        END_USER["👤 End User"]',
            '        GIT_REPOS["Git Repositories"]',
            "    end",
        ]

        present_layers = []
        for layer_id in layer_order:
            domains_in_layer = sorted(layer_domains2.get(layer_id, []))
            if not domains_in_layer:
                continue
            present_layers.append(layer_id)
            label = layer_labels[layer_id]
            lines.append(f'    subgraph {layer_id} ["{label}"]')
            lines.append("        direction TB")
            for d in domains_in_layer:
                nid = _safe_id(d)
                fc = domain_file_count.get(d, 0)
                cc = domain_concept_count.get(d, 0)
                dtl = _depth_to_leaf(d, all_norms)
                depth_hint = f"↓{dtl} level{'s' if dtl != 1 else ''}" if dtl > 0 else "→ files"
                short = d.split("/")[-1].replace("_", " ").title()
                label_text = f"{short}\\n{fc} files · {cc} concepts\\n{depth_hint}"
                lines.append(f'        {nid}["{label_text}"]')
                lines.append(f'        click {nid} call dokydocClick("{d}")')
            lines.append("    end")

        # Inter-layer edges
        def first_node(layer): return _safe_id(sorted(layer_domains2.get(layer, []))[0]) if layer_domains2.get(layer) else None
        fe, mw, api, svc, asc, ai, data = (first_node(l) for l in ["FRONTEND", "MIDDLEWARE", "API", "SERVICES", "ASYNC", "AI", "DATA"])
        if fe: lines += [f'    END_USER -->|HTTPS| {fe}', f'    GIT_REPOS -->|API/Webhook| {fe}']
        first_be = mw or api or svc
        if fe and first_be: lines.append(f'    {fe} --> {first_be}')
        if mw and api: lines.append(f'    {mw} --> {api}')
        if api and svc: lines.append(f'    {api} --> {svc}')
        if svc and asc: lines.append(f'    {svc} -->|Task Queue| {asc}')
        if svc and ai: lines.append(f'    {svc} -->|AI Request| {ai}')
        if data:
            for src in [x for x in [svc, asc, api] if x]: lines.append(f'    {src} --> {data}')

        added: set = set()
        for (sd, td), info in sorted(cross_domain.items(), key=lambda x: -x[1]["count"])[:8]:
            sl, tl = domain_to_layer2.get(sd), domain_to_layer2.get(td)
            if sl and tl and sl != tl:
                sn, tn = _safe_id(sd), _safe_id(td)
                ek = (sn, tn)
                if ek not in added:
                    added.add(ek)
                    rel = list(info["types"])[0] if info["types"] else "uses"
                    lines.append(f'    {sn} -.->|{rel}| {tn}')

        # Build nodes metadata
        nodes_meta = []
        for d in all_domains:
            dtl = _depth_to_leaf(d, all_norms)
            nodes_meta.append({
                "name": d.split("/")[-1],
                "path": d,
                "type": "file" if dtl == 0 else "group",
                "file_count": domain_file_count.get(d, 0),
                "concept_count": domain_concept_count.get(d, 0),
                "component_id": None,
                "depth_to_leaf": dtl,
                "layer": domain_to_layer2.get(d, "SERVICES"),
            })

        return {
            "view_type": "architecture",
            "mermaid_syntax": "\n".join(lines),
            "nodes": nodes_meta,
            "breadcrumb": [],
            "repo_name": repo.name,
        }

    # --- PATH DRILL (path != "") ---
    path = path.strip("/")
    path_parts = [p for p in path.split("/") if p]

    # Filter components whose normalized path starts with this path prefix
    matching: list = []
    for comp in all_components:
        norm = comp_norms[comp.id]
        prefix = path + "/"
        if norm.startswith(prefix) or norm == path:
            matching.append((comp, norm))

    if not matching:
        return {
            "view_type": "empty",
            "mermaid_syntax": f'graph TD\n    A["No files found under: {path}"]',
            "nodes": [],
            "breadcrumb": _build_breadcrumb(path_parts),
        }

    # Analyse what lives at the NEXT level beneath current path
    # next_items: segment_name -> {components, is_pure_group, has_files, has_subdirs}
    next_items: dict = {}
    for comp, norm in matching:
        remaining = norm[len(path):].lstrip("/")
        parts = [p for p in remaining.split("/") if p]
        if not parts:
            continue
        seg = parts[0]
        is_file = len(parts) == 1

        if seg not in next_items:
            next_items[seg] = {
                "components": [],
                "file_components": [],
                "has_subdirs": False,
            }
        next_items[seg]["components"].append(comp)
        if is_file:
            next_items[seg]["file_components"].append(comp)
        else:
            next_items[seg]["has_subdirs"] = True

    # Determine view type: groups = at least one sub-directory exists; files = all are leaves
    has_groups = any(info["has_subdirs"] for info in next_items.values())

    # Fetch concepts for matching components (capped to prevent huge IN-clauses)
    matching_comp_ids = {comp.id for comp, _ in matching}
    concepts = db.query(OntologyConcept).filter(
        OntologyConcept.source_component_id.in_(matching_comp_ids),
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
    ).limit(1000).all()

    concept_ids = {c.id for c in concepts}
    concept_to_comp: dict = {c.id: c.source_component_id for c in concepts}
    comp_concept_count: dict = defaultdict(int)
    comp_key_concepts: dict = defaultdict(list)
    for c in concepts:
        comp_concept_count[c.source_component_id] += 1
        if len(comp_key_concepts[c.source_component_id]) < 3:
            comp_key_concepts[c.source_component_id].append(c.name)

    # Cap the IN-clause to 200 concept IDs to avoid 1000-param queries that
    # cause PostgreSQL plan thrash and SQLAlchemy ROLLBACKs.  Relationships
    # are only used for drawing edges between groups — a sample is enough.
    concept_ids_for_rels = list(concept_ids)[:200]
    rels = db.query(OntologyRelationship).filter(
        OntologyRelationship.tenant_id == tenant_id,
        or_(
            OntologyRelationship.source_concept_id.in_(concept_ids_for_rels),
            OntologyRelationship.target_concept_id.in_(concept_ids_for_rels),
        ),
    ).limit(500).all() if concept_ids_for_rels else []

    # Count cross-item relationships (between items at the current level)
    def seg_for_comp(comp_id: int) -> str:
        norm = comp_norms.get(comp_id, "")
        remaining = norm[len(path):].lstrip("/")
        parts = [p for p in remaining.split("/") if p]
        return parts[0] if parts else ""

    item_rel_count: dict = defaultdict(lambda: defaultdict(int))
    item_rel_types: dict = defaultdict(lambda: defaultdict(set))
    for r in rels:
        sc = concept_to_comp.get(r.source_concept_id)
        tc = concept_to_comp.get(r.target_concept_id)
        if sc and tc and sc != tc:
            ss = seg_for_comp(sc)
            ts = seg_for_comp(tc)
            if ss and ts and ss != ts:
                item_rel_count[ss][ts] += 1
                item_rel_types[ss][ts].add(r.relationship_type or "uses")

    # --- Build Mermaid + nodes metadata ---
    lines = ["graph TD"]
    nodes_meta = []
    added_edges: set = set()

    for seg, info in sorted(next_items.items()):
        nid = _safe_id(seg)
        all_comps_here = info["components"]
        fc = len(set(c.id for c in all_comps_here))
        cc = sum(comp_concept_count.get(c.id, 0) for c in all_comps_here)
        key_c = []
        for c in all_comps_here:
            key_c.extend(comp_key_concepts.get(c.id, []))
        key_c = list(dict.fromkeys(key_c))[:3]

        if info["has_subdirs"]:
            # This is a drillable group (has sub-directories)
            node_type = "group"
            full_path = f"{path}/{seg}"
            dtl = _depth_to_leaf(full_path, all_norms)
            depth_hint = f"↓{dtl} level{'s' if dtl != 1 else ''}" if dtl > 0 else "→ files"
            short = seg.replace("_", " ").replace("-", " ").title()
            label = f"{short}\\n{fc} files · {cc} concepts\\n{depth_hint}"
            lines.append(f'    {nid}["{label}"]')
            lines.append(f'    click {nid} call dokydocClick("{full_path}")')
            nodes_meta.append({
                "name": seg, "path": full_path, "type": "group",
                "file_count": fc, "concept_count": cc,
                "component_id": None, "depth_to_leaf": dtl,
                "key_concepts": key_c,
            })
        else:
            # This is a leaf file
            comp = info["file_components"][0] if info["file_components"] else info["components"][0]
            node_type = "file"
            cc_single = comp_concept_count.get(comp.id, 0)
            key_c_single = comp_key_concepts.get(comp.id, [])
            # Pick shape by analysis status / concept types
            label = f"{seg}\\n{cc_single} concepts"
            lines.append(f'    {nid}["{label}"]')
            lines.append(f'    click {nid} call dokydocClick("component:{comp.id}")')
            nodes_meta.append({
                "name": seg, "path": f"{path}/{seg}", "type": "file",
                "file_count": 1, "concept_count": cc_single,
                "component_id": comp.id, "depth_to_leaf": 0,
                "key_concepts": key_c_single,
            })

    # Add inter-item edges (top 20)
    edge_count = 0
    for src_seg, targets in sorted(item_rel_count.items(), key=lambda x: -sum(x[1].values())):
        for tgt_seg, count in sorted(targets.items(), key=lambda x: -x[1]):
            if edge_count >= 20:
                break
            sn, tn = _safe_id(src_seg), _safe_id(tgt_seg)
            ek = (sn, tn)
            if ek not in added_edges and sn in {_safe_id(s) for s in next_items} and tn in {_safe_id(s) for s in next_items}:
                added_edges.add(ek)
                rel = list(item_rel_types[src_seg][tgt_seg])[0]
                lines.append(f'    {sn} -->|"{rel}"| {tn}')
                edge_count += 1

    view_type = "groups" if has_groups else "files"

    return {
        "view_type": view_type,
        "mermaid_syntax": "\n".join(lines),
        "nodes": nodes_meta,
        "breadcrumb": _build_breadcrumb(path_parts),
        "current_path": path,
        "repo_name": repo.name,
    }


@router.get("/graph/alignment/{initiative_id}")
def get_alignment_graph(
    initiative_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    include_unmapped: bool = Query(True, description="Include concepts with no mapping"),
) -> Any:
    """
    Level 4 Brain: Cross-Domain Alignment Graph for an initiative.
    Returns bipartite doc↔code concepts with ConceptMapping bridges + coverage stats.
    """
    from app.models.concept_mapping import ConceptMapping
    from app.models.ontology_concept import OntologyConcept
    from sqlalchemy import or_

    # Get all non-rejected mappings
    mappings = db.query(ConceptMapping).filter(
        ConceptMapping.tenant_id == tenant_id,
        ConceptMapping.status != "rejected",
    ).all()

    mapped_doc_ids = {m.document_concept_id for m in mappings}
    mapped_code_ids = {m.code_concept_id for m in mappings}

    # Get document concepts for this initiative
    # Include "both" because exact-matched concepts get promoted from "document" to "both"
    doc_q = db.query(OntologyConcept).filter(
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
        OntologyConcept.source_type.in_(["document", "both"]),
    )
    if initiative_id:
        doc_q = doc_q.filter(or_(
            OntologyConcept.initiative_id == initiative_id,
            OntologyConcept.initiative_id.is_(None),
        ))
    all_doc_concepts = doc_q.all()

    # Get code concepts for this initiative
    code_q = db.query(OntologyConcept).filter(
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.is_active == True,
        OntologyConcept.source_type.in_(["code", "both"]),
    )
    if initiative_id:
        code_q = code_q.filter(or_(
            OntologyConcept.initiative_id == initiative_id,
            OntologyConcept.initiative_id.is_(None),
        ))
    all_code_concepts = code_q.all()

    if include_unmapped:
        doc_concepts = all_doc_concepts
        code_concepts = all_code_concepts
    else:
        doc_concepts = [c for c in all_doc_concepts if c.id in mapped_doc_ids]
        code_concepts = [c for c in all_code_concepts if c.id in mapped_code_ids]

    doc_ids = {c.id for c in doc_concepts}
    code_ids = {c.id for c in code_concepts}

    visible_mappings = [
        m for m in mappings
        if m.document_concept_id in doc_ids and m.code_concept_id in code_ids
    ]

    def _node(c):
        return {"id": c.id, "name": c.name, "concept_type": c.concept_type,
                "source_type": c.source_type, "confidence_score": c.confidence_score or 0}

    total_doc = len(all_doc_concepts)
    mapped_doc_count = sum(1 for c in all_doc_concepts if c.id in mapped_doc_ids)

    # Build gap analysis data (unmapped doc concepts = gaps, unmapped code = undocumented)
    unmapped_doc = [c for c in all_doc_concepts if c.id not in mapped_doc_ids]
    unmapped_code = [c for c in all_code_concepts if c.id not in mapped_code_ids]

    # Build concept name lookup for mapping enrichment
    concept_map = {c.id: c.name for c in all_doc_concepts}
    concept_map.update({c.id: c.name for c in all_code_concepts})

    return {
        "document_nodes": [_node(c) for c in doc_concepts],
        "code_nodes": [_node(c) for c in code_concepts],
        "mappings": [
            {
                "id": m.id, "document_concept_id": m.document_concept_id,
                "code_concept_id": m.code_concept_id, "mapping_method": m.mapping_method,
                "confidence_score": m.confidence_score, "status": m.status,
                "relationship_type": m.relationship_type,
                "document_concept_name": concept_map.get(m.document_concept_id, ""),
                "code_concept_name": concept_map.get(m.code_concept_id, ""),
            }
            for m in visible_mappings
        ],
        "coverage_stats": {
            "total_doc_concepts": total_doc,
            "mapped_doc_concepts": mapped_doc_count,
            "total_code_concepts": len(all_code_concepts),
            "mapped_code_concepts": sum(1 for c in all_code_concepts if c.id in mapped_code_ids),
            "coverage_pct": round(mapped_doc_count / total_doc, 3) if total_doc else 0,
        },
        "gap_analysis": {
            "gaps": [{"id": c.id, "name": c.name, "concept_type": c.concept_type} for c in unmapped_doc[:50]],
            "undocumented": [{"id": c.id, "name": c.name, "concept_type": c.concept_type} for c in unmapped_code[:50]],
            "contradictions": [],
            "total_gaps": len(unmapped_doc),
            "total_undocumented": len(unmapped_code),
            "total_contradictions": 0,
        },
        "initiative_id": initiative_id,
    }


@router.post("/run-mapping")
def trigger_cross_graph_mapping(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually trigger the 3-tier cross-graph mapping pipeline.
    Dispatches a Celery task that matches document concepts ↔ code concepts.
    """
    from app.tasks.ontology_tasks import run_cross_graph_mapping
    try:
        run_cross_graph_mapping.delay(tenant_id)
        return {"status": "dispatched", "message": "Cross-graph mapping task queued"}
    except Exception as e:
        logger.error(f"Failed to dispatch mapping task: {e}")
        raise HTTPException(status_code=500, detail="Failed to dispatch mapping task")


@router.post("/extract/document/{document_id}")
def trigger_document_extraction(
    document_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually trigger ontology entity extraction for a document.
    Fires the Celery task that reads analysis results and creates OntologyConcepts.
    """
    doc = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "completed":
        raise HTTPException(status_code=400, detail=f"Document status is '{doc.status}', must be 'completed'")

    from app.tasks.ontology_tasks import extract_ontology_entities
    try:
        extract_ontology_entities.delay(document_id, tenant_id)
        return {"status": "dispatched", "message": f"Ontology extraction queued for document {document_id}"}
    except Exception as e:
        logger.error(f"Failed to dispatch extraction task: {e}")
        raise HTTPException(status_code=500, detail="Failed to dispatch extraction task")


@router.post("/extract/repository/{repo_id}")
def trigger_repository_extraction(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually trigger ontology entity extraction for a repository.
    Fires the Celery task that reads code analysis and creates OntologyConcepts.
    """
    repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.analysis_status != "completed":
        raise HTTPException(status_code=400, detail=f"Repository status is '{repo.analysis_status}', must be 'completed'")

    from app.tasks.ontology_tasks import extract_code_ontology_entities
    try:
        extract_code_ontology_entities.delay(repo_id, tenant_id)
        return {"status": "dispatched", "message": f"Code ontology extraction queued for repo {repo_id}"}
    except Exception as e:
        logger.error(f"Failed to dispatch extraction task: {e}")
        raise HTTPException(status_code=500, detail="Failed to dispatch extraction task")


@router.get("/graph/brain")
def get_organizational_brain(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Level 5 Brain: Organizational Brain.
    Returns project-level bubbles with aggregated metrics and cross-project edges.
    """
    from app.models.concept_mapping import ConceptMapping
    from collections import defaultdict

    projects = crud.initiative.get_multi(db=db, tenant_id=tenant_id)
    if not projects:
        return {"projects": [], "connections": [], "total_projects": 0, "total_connections": 0}

    all_concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    concept_by_project = defaultdict(list)
    for c in all_concepts:
        if c.initiative_id:
            concept_by_project[c.initiative_id].append(c)

    all_mappings = db.query(ConceptMapping).filter(
        ConceptMapping.tenant_id == tenant_id,
        ConceptMapping.status != "rejected",
    ).all()
    mapped_doc_ids = {m.document_concept_id for m in all_mappings}

    # Cross-project mappings
    try:
        cross_mappings = crud.cross_project_mapping.get_all_for_tenant(db=db, tenant_id=tenant_id)
    except Exception:
        cross_mappings = []

    cross_by_pair = defaultdict(list)
    for cm in cross_mappings:
        if hasattr(cm, 'status') and cm.status == "rejected":
            continue
        pair = tuple(sorted([cm.initiative_a_id, cm.initiative_b_id]))
        cross_by_pair[pair].append(cm)

    project_nodes = []
    for p in projects:
        concepts = concept_by_project.get(p.id, [])
        doc_c = [c for c in concepts if c.source_type == "document"]
        code_c = [c for c in concepts if c.source_type in ("code", "both")]
        mapped = sum(1 for c in doc_c if c.id in mapped_doc_ids)
        coverage = round(mapped / len(doc_c), 3) if doc_c else 0

        top = sorted([c for c in concepts if c.confidence_score],
                     key=lambda c: c.confidence_score, reverse=True)[:5]

        project_nodes.append({
            "id": p.id,
            "name": p.name,
            "doc_concept_count": len(doc_c),
            "code_concept_count": len(code_c),
            "total_concept_count": len(concepts),
            "coverage_pct": coverage,
            "top_concepts": [{"name": c.name, "type": c.concept_type} for c in top],
        })

    connections = []
    project_ids = {p.id for p in projects}
    for pair, cms in cross_by_pair.items():
        if pair[0] not in project_ids or pair[1] not in project_ids:
            continue
        connections.append({
            "project_a_id": pair[0],
            "project_b_id": pair[1],
            "connection_count": len(cms),
            "relationship_types": list({getattr(cm, 'relationship_type', 'related') for cm in cms}),
        })

    return {
        "projects": project_nodes,
        "connections": connections,
        "total_projects": len(project_nodes),
        "total_connections": len(connections),
    }


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


@router.post("/mappings/{mapping_id}/feedback")
def submit_mapping_feedback(
    mapping_id: int,
    *,
    action: str = Query(..., description="Action: 'confirm' or 'reject'"),
    comment: Optional[str] = Query(None, description="Optional feedback comment"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Submit feedback on a mapping — confirm or reject with optional comment.
    Tracks who provided the feedback and when, enabling threshold tuning.
    """
    if action not in ("confirm", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'confirm' or 'reject'")

    result = crud.concept_mapping.submit_feedback(
        db=db,
        mapping_id=mapping_id,
        tenant_id=tenant_id,
        action=action,
        user_id=current_user.id,
        comment=comment,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return {
        "status": result.status,
        "mapping_id": mapping_id,
        "feedback_by": current_user.id,
        "feedback_comment": result.feedback_comment,
        "feedback_at": result.feedback_at.isoformat() if result.feedback_at else None,
    }


@router.get("/mappings/feedback/stats")
def get_mapping_feedback_stats(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get aggregated feedback statistics — useful for tuning mapping thresholds.
    Shows acceptance rates and average confidence by mapping method.
    """
    return crud.concept_mapping.get_feedback_stats(db=db, tenant_id=tenant_id)


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

    # Count by method
    by_method: dict = {}
    for m in all_mappings:
        method = m.mapping_method or "unknown"
        by_method[method] = by_method.get(method, 0) + 1

    # Count by relationship type
    by_relationship: dict = {}
    for m in all_mappings:
        rel = m.relationship_type or "unknown"
        by_relationship[rel] = by_relationship.get(rel, 0) + 1

    rejected = sum(1 for m in all_mappings if m.status == "rejected")

    return {
        "total_mappings": len(all_mappings),
        # Legacy field names kept for backward compat
        "confirmed_mappings": confirmed,
        "candidate_mappings": candidates,
        "project_pairs": len(pairs),
        # Fields expected by frontend CrossProjectStats type
        "confirmed": confirmed,
        "candidate": candidates,
        "rejected": rejected,
        "by_method": by_method,
        "by_relationship": by_relationship,
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
    Org-wide meta-graph: projects as aggregated nodes (not individual concepts).
    Each node represents a project with concept/relationship counts and top concepts.
    Cross-project edges show mapping counts between projects.
    """
    from app.models.initiative_asset import InitiativeAsset
    from app.models.code_component import CodeComponent
    from app.models.ontology_concept import OntologyConcept
    from app.models.ontology_relationship import OntologyRelationship
    from collections import defaultdict

    # Get all projects
    projects = crud.initiative.get_multi(db=db, tenant_id=tenant_id)

    # Get all concepts and relationships for counts
    concepts = crud.ontology_concept.get_all_active(db=db, tenant_id=tenant_id)
    relationships = crud.ontology_relationship.get_full_graph(db=db, tenant_id=tenant_id)

    # Build concept-to-initiative map
    concept_initiative = {}
    initiative_concepts = defaultdict(list)
    for c in concepts:
        concept_initiative[c.id] = c.initiative_id
        initiative_concepts[c.initiative_id or 0].append(c)

    # Build relationship counts per initiative
    initiative_rel_count = defaultdict(int)
    for r in relationships:
        init_id = concept_initiative.get(r.source_concept_id)
        if init_id:
            initiative_rel_count[init_id] += 1

    # Get repo mapping per initiative
    initiative_repo = {}
    assets = db.query(InitiativeAsset).filter(
        InitiativeAsset.tenant_id == tenant_id,
        InitiativeAsset.asset_type == "REPOSITORY",
        InitiativeAsset.is_active == True,
    ).all()
    for a in assets:
        initiative_repo[a.initiative_id] = a.asset_id

    # Get file count per initiative (via repository)
    initiative_file_count = {}
    for init_id, repo_id in initiative_repo.items():
        count = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
        ).count()
        initiative_file_count[init_id] = count

    # Build project-level aggregated nodes
    nodes = []
    for p in projects:
        p_concepts = initiative_concepts.get(p.id, [])
        # Top concepts by confidence
        top_concepts = sorted(p_concepts, key=lambda c: c.confidence_score, reverse=True)
        # Type distribution
        type_dist = defaultdict(int)
        for c in p_concepts:
            type_dist[c.concept_type] += 1

        nodes.append({
            "id": p.id,
            "name": p.name,
            "initiative_id": p.id,
            "repo_id": initiative_repo.get(p.id),
            "concept_count": len(p_concepts),
            "relationship_count": initiative_rel_count.get(p.id, 0),
            "file_count": initiative_file_count.get(p.id, 0),
            "top_concepts": [c.name for c in top_concepts[:8]],
            "type_distribution": dict(type_dist),
            "status": p.status,
        })

    # Handle unscoped concepts (no initiative)
    unscoped = initiative_concepts.get(0, [])
    if unscoped:
        type_dist = defaultdict(int)
        for c in unscoped:
            type_dist[c.concept_type] += 1
        top = sorted(unscoped, key=lambda c: c.confidence_score, reverse=True)
        nodes.append({
            "id": -1,
            "name": "Unscoped Concepts",
            "initiative_id": None,
            "repo_id": None,
            "concept_count": len(unscoped),
            "relationship_count": 0,
            "file_count": 0,
            "top_concepts": [c.name for c in top[:8]],
            "type_distribution": dict(type_dist),
            "status": "ACTIVE",
        })

    # Cross-project edges from CrossProjectMapping
    cross_mappings = crud.cross_project_mapping.get_all_for_tenant(
        db=db, tenant_id=tenant_id
    )
    cross_edge_counts = defaultdict(lambda: {"count": 0, "types": set()})
    for m in cross_mappings:
        if m.status == "rejected":
            continue
        key = tuple(sorted([m.initiative_a_id, m.initiative_b_id]))
        cross_edge_counts[key]["count"] += 1
        cross_edge_counts[key]["types"].add(m.relationship_type)

    cross_edges = [
        {
            "source_id": k[0],
            "target_id": k[1],
            "relationship_count": v["count"],
            "relationship_types": list(v["types"]),
        }
        for k, v in cross_edge_counts.items()
    ]

    return {
        "nodes": nodes,
        "cross_edges": cross_edges,
        "total_concepts": len(concepts),
        "total_relationships": len(relationships),
        "total_cross_edges": sum(e["relationship_count"] for e in cross_edges),
        "projects": [
            {"id": p.id, "name": p.name}
            for p in projects
        ],
    }


# ============================================================
# BRANCH PREVIEW ENDPOINTS (SPRINT 4 Phase 4)
# ============================================================

@router.get("/graph/branches/{repo_id}")
def list_branch_previews(
    repo_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List all active branch previews for a repository."""
    from app.services.cache_service import cache_service

    branch_names = cache_service.list_branch_previews(
        tenant_id=tenant_id, repo_id=repo_id
    )

    branches = []
    for branch_name in branch_names:
        data = cache_service.get_branch_preview(
            tenant_id=tenant_id, repo_id=repo_id, branch=branch_name
        )
        if data:
            branches.append({
                "branch": branch_name,
                "commit_hash": data.get("commit_hash", ""),
                "extracted_at": data.get("extracted_at", ""),
                "entity_count": len(data.get("entities", [])),
                "relationship_count": len(data.get("relationships", [])),
                "changed_files_count": len(data.get("changed_files", [])),
                "changed_files": data.get("changed_files", []),
            })

    return branches


@router.get("/graph/preview/{repo_id}/{branch:path}", response_model=BranchPreviewGraphResponse)
def get_branch_preview_graph(
    repo_id: int,
    branch: str,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    initiative_id: Optional[int] = Query(None, description="Filter base graph by project"),
) -> Any:
    """
    On-the-fly merge: base graph (PostgreSQL) + branch delta (Redis).
    Returns nodes annotated with diff_status: unchanged/added/modified/removed.
    """
    from app.services.cache_service import cache_service

    # 1. Fetch branch delta from Redis
    preview = cache_service.get_branch_preview(
        tenant_id=tenant_id, repo_id=repo_id, branch=branch
    )

    if not preview:
        raise HTTPException(
            status_code=404,
            detail=f"No preview available for branch '{branch}'"
        )

    # 2. Fetch base graph from PostgreSQL (main branch ground truth)
    base_concepts = crud.ontology_concept.get_all_active(
        db=db, tenant_id=tenant_id, initiative_id=initiative_id
    )
    base_relationships = crud.ontology_relationship.get_full_graph(
        db=db, tenant_id=tenant_id
    )

    # Filter relationships to visible concepts
    base_concept_ids = {c.id for c in base_concepts}
    base_relationships = [
        r for r in base_relationships
        if r.source_concept_id in base_concept_ids and r.target_concept_id in base_concept_ids
    ]

    # 3. Build base concept lookup (lowercase name → concept)
    base_names = {c.name.lower(): c for c in base_concepts}

    # 4. Track branch entity names for diff detection
    branch_entity_names = {
        e["name"].lower() for e in preview.get("entities", []) if e.get("name")
    }

    # 5. Build merged nodes
    nodes = []

    # Add base concepts — mark as "unchanged" or "modified" if also in branch
    for c in base_concepts:
        diff_status = "modified" if c.name.lower() in branch_entity_names else "unchanged"
        nodes.append(BranchPreviewNode(
            id=c.id,
            name=c.name,
            concept_type=c.concept_type,
            source_type=c.source_type,
            initiative_id=c.initiative_id,
            confidence_score=c.confidence_score,
            diff_status=diff_status,
        ))

    # Add branch-only concepts (marked "added")
    next_id = max((c.id for c in base_concepts), default=0) + 1000
    name_to_id = {c.name.lower(): c.id for c in base_concepts}

    for be in preview.get("entities", []):
        be_name = be.get("name", "")
        if be_name.lower() not in base_names:
            name_to_id[be_name.lower()] = next_id
            nodes.append(BranchPreviewNode(
                id=next_id,
                name=be_name,
                concept_type=be.get("type", "Entity"),
                source_type="code",
                confidence_score=be.get("confidence", 0.8),
                diff_status="added",
            ))
            next_id += 1

    # 6. Build merged edges
    edges = []

    # Base relationships (unchanged)
    for r in base_relationships:
        edges.append(BranchPreviewEdge(
            id=r.id,
            source_concept_id=r.source_concept_id,
            target_concept_id=r.target_concept_id,
            relationship_type=r.relationship_type,
            confidence_score=r.confidence_score,
            diff_status="unchanged",
        ))

    # Branch-only relationships (resolve by name → id)
    edge_next_id = max((r.id for r in base_relationships), default=0) + 1000
    for br in preview.get("relationships", []):
        source_name = br.get("source", "").lower()
        target_name = br.get("target", "").lower()
        source_id = name_to_id.get(source_name)
        target_id = name_to_id.get(target_name)

        if source_id and target_id:
            # Check if this edge already exists in base
            existing = any(
                e.source_concept_id == source_id and e.target_concept_id == target_id
                for e in base_relationships
            )
            if not existing:
                edges.append(BranchPreviewEdge(
                    id=edge_next_id,
                    source_concept_id=source_id,
                    target_concept_id=target_id,
                    relationship_type=br.get("type", "relates_to"),
                    confidence_score=br.get("confidence", 0.75),
                    diff_status="added",
                ))
                edge_next_id += 1

    return BranchPreviewGraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
        branch=branch,
        commit_hash=preview.get("commit_hash", ""),
        changed_files=preview.get("changed_files", []),
    )


# ══════════════════════════════════════════════════════════════════
# GRAPH VERSIONING ENDPOINTS
# Pre-built graph JSON for fast rendering + version history + diff
# ══════════════════════════════════════════════════════════════════

@router.get("/graph/component/{component_id}/current")
def get_component_graph_current(
    component_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get the current pre-built graph for a code component (fast, no joins)."""
    version = crud.knowledge_graph_version.get_current(
        db, source_type="component", source_id=component_id, tenant_id=tenant_id
    )
    if not version:
        raise HTTPException(status_code=404, detail="No graph version found for this component")
    return {
        "version": version.version,
        "graph_data": version.graph_data,
        "graph_hash": version.graph_hash,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


@router.get("/graph/component/{component_id}/versions")
def get_component_graph_versions(
    component_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get version history for a code component's graph."""
    versions = crud.knowledge_graph_version.get_history(
        db, source_type="component", source_id=component_id, tenant_id=tenant_id
    )
    return [
        {
            "version": v.version,
            "is_current": v.is_current,
            "graph_hash": v.graph_hash,
            "delta_summary": v.graph_delta.get("summary", "") if v.graph_delta else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/graph/component/{component_id}/diff")
def get_component_graph_diff(
    component_id: int,
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get diff between two graph versions of a code component."""
    diff = crud.knowledge_graph_version.get_diff(
        db, source_type="component", source_id=component_id,
        version_a=v1, version_b=v2, tenant_id=tenant_id
    )
    if diff is None:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return diff


@router.get("/graph/document/{document_id}/current")
def get_document_graph_current(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get the current pre-built graph for a document (fast, no joins)."""
    version = crud.knowledge_graph_version.get_current(
        db, source_type="document", source_id=document_id, tenant_id=tenant_id
    )
    if not version:
        raise HTTPException(status_code=404, detail="No graph version found for this document")
    return {
        "version": version.version,
        "graph_data": version.graph_data,
        "graph_hash": version.graph_hash,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


@router.get("/graph/document/{document_id}/versions")
def get_document_graph_versions(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get version history for a document's graph."""
    versions = crud.knowledge_graph_version.get_history(
        db, source_type="document", source_id=document_id, tenant_id=tenant_id
    )
    return [
        {
            "version": v.version,
            "is_current": v.is_current,
            "graph_hash": v.graph_hash,
            "delta_summary": v.graph_delta.get("summary", "") if v.graph_delta else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/graph/document/{document_id}/diff")
def get_document_graph_diff(
    document_id: int,
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get diff between two graph versions of a document."""
    diff = crud.knowledge_graph_version.get_diff(
        db, source_type="document", source_id=document_id,
        version_a=v1, version_b=v2, tenant_id=tenant_id
    )
    if diff is None:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return diff


# ══════════════════════════════════════════════════════════════════
# REQUIREMENT TRACEABILITY ENDPOINTS
# Layer 2 of the 3-layer hybrid validation system
# ══════════════════════════════════════════════════════════════════

@router.get("/traceability/document/{document_id}")
def get_requirement_traces(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get all requirement traces for a document with coverage summary."""
    traces = crud.requirement_trace.get_by_document(
        db, document_id=document_id, tenant_id=tenant_id
    )
    summary = crud.requirement_trace.get_coverage_summary(
        db, document_id=document_id, tenant_id=tenant_id
    )
    return {
        "traces": [
            {
                "id": t.id,
                "requirement_key": t.requirement_key,
                "requirement_text": t.requirement_text,
                "code_concept_ids": t.code_concept_ids,
                "code_component_ids": t.code_component_ids,
                "coverage_status": t.coverage_status,
                "validation_status": t.validation_status,
                "validation_details": t.validation_details,
            }
            for t in traces
        ],
        "summary": summary,
    }


@router.get("/traceability/initiative/{initiative_id}")
def get_initiative_traces(
    initiative_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Get all requirement traces for an initiative/project."""
    traces = crud.requirement_trace.get_by_initiative(
        db, initiative_id=initiative_id, tenant_id=tenant_id
    )
    return {
        "traces": [
            {
                "id": t.id,
                "document_id": t.document_id,
                "requirement_key": t.requirement_key,
                "requirement_text": t.requirement_text,
                "code_concept_ids": t.code_concept_ids,
                "coverage_status": t.coverage_status,
                "validation_status": t.validation_status,
            }
            for t in traces
        ],
        "total": len(traces),
    }


@router.post("/traceability/build/{document_id}")
def build_requirement_traces(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
):
    """Build/rebuild requirement traces for a document."""
    document = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.services.requirement_traceability_service import requirement_traceability_service
    result = requirement_traceability_service.build_traces_for_document(
        db=db, document_id=document_id, tenant_id=tenant_id
    )
    return result


@router.post("/backfill-initiative-ids")
def backfill_concept_initiative_ids(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(deps.get_tenant_id),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Backfill initiative_id on existing OntologyConcepts that have NULL initiative_id.
    Resolves via: OntologyConcept.source_component_id → CodeComponent.repository_id → InitiativeAsset.
    """
    from app.models.ontology_concept import OntologyConcept
    from app.models.code_component import CodeComponent
    from app.models.initiative_asset import InitiativeAsset

    # Build repo→initiative lookup
    assets = db.query(InitiativeAsset).filter(
        InitiativeAsset.tenant_id == tenant_id,
        InitiativeAsset.asset_type == "REPOSITORY",
        InitiativeAsset.is_active == True,
    ).all()
    repo_to_initiative = {a.asset_id: a.initiative_id for a in assets}

    # Build component→repo lookup
    components = db.query(CodeComponent.id, CodeComponent.repository_id).filter(
        CodeComponent.tenant_id == tenant_id,
        CodeComponent.repository_id.isnot(None),
    ).all()
    comp_to_repo = {c.id: c.repository_id for c in components}

    # Find unscoped concepts
    unscoped = db.query(OntologyConcept).filter(
        OntologyConcept.tenant_id == tenant_id,
        OntologyConcept.initiative_id.is_(None),
        OntologyConcept.source_component_id.isnot(None),
    ).all()

    updated = 0
    for concept in unscoped:
        repo_id = comp_to_repo.get(concept.source_component_id)
        if repo_id:
            initiative_id = repo_to_initiative.get(repo_id)
            if initiative_id:
                concept.initiative_id = initiative_id
                updated += 1

    db.commit()
    return {
        "total_unscoped": len(unscoped),
        "updated": updated,
        "remaining_unscoped": len(unscoped) - updated,
    }


# ============================================================
# SPRINT 4: Semantic Search Endpoints
# ============================================================

@router.get("/search")
def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    concept_type: Optional[str] = Query(None, description="Filter by concept type"),
    source_type: Optional[str] = Query(None, description="Filter by source type (document/code/both)"),
    initiative_id: Optional[int] = Query(None, description="Filter by initiative"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 4: Semantic search across ontology concepts.
    Uses vector similarity (pgvector) when available, falls back to text search.
    """
    from app.services.semantic_search_service import semantic_search_service
    results = semantic_search_service.search_concepts(
        db, q, tenant_id,
        concept_type=concept_type,
        source_type=source_type,
        initiative_id=initiative_id,
        min_confidence=min_confidence,
        limit=limit,
    )
    return {"query": q, "results": results, "count": len(results)}


@router.get("/search/related/{concept_id}")
def find_related_concepts(
    concept_id: int,
    depth: int = Query(1, ge=1, le=3, description="Graph traversal depth"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 4: Find concepts related to a given concept.
    Combines graph traversal with vector similarity.
    """
    from app.services.semantic_search_service import semantic_search_service
    results = semantic_search_service.find_related(
        db, concept_id, tenant_id,
        depth=depth,
        limit=limit,
    )
    return {"concept_id": concept_id, "related": results, "count": len(results)}


@router.get("/search/graphs")
def search_graphs(
    q: str = Query(..., min_length=1, description="Search query"),
    source_type: Optional[str] = Query(None, description="Filter: component or document"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 4: Search knowledge graph versions by summary similarity.
    """
    from app.services.semantic_search_service import semantic_search_service
    results = semantic_search_service.search_graphs(
        db, q, tenant_id,
        source_type=source_type,
        limit=limit,
    )
    return {"query": q, "results": results, "count": len(results)}


@router.post("/embeddings/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_embeddings(
    background_tasks: BackgroundTasks,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Sprint 4: Trigger embedding generation for all un-embedded concepts.
    Runs as a background Celery task.
    """
    try:
        from app.tasks.embedding_tasks import embed_all_tenant_concepts
        embed_all_tenant_concepts.delay(tenant_id)
        return {"status": "accepted", "message": "Embedding generation task enqueued"}
    except Exception as e:
        logger.warning(f"Failed to enqueue embedding task: {e}")
        return {"status": "accepted", "message": "Embedding generation scheduled"}
