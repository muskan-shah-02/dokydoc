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

    # Count cross-graph mappings
    total_mappings = crud.concept_mapping.count_by_tenant(db=db, tenant_id=tenant_id)

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
