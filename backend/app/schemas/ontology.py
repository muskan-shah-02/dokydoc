from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal
from datetime import datetime


# --- Ontology Concept Schemas ---

class OntologyConceptBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    concept_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class OntologyConceptCreate(OntologyConceptBase):
    source_type: Literal["document", "code"] = "document"
    initiative_id: Optional[int] = None


class OntologyConceptUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    concept_type: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class OntologyConceptResponse(OntologyConceptBase):
    id: int
    source_type: str = "document"  # "document", "code", or "both"
    initiative_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Ontology Relationship Schemas ---

class OntologyRelationshipBase(BaseModel):
    source_concept_id: int
    target_concept_id: int
    relationship_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class OntologyRelationshipCreate(OntologyRelationshipBase):
    pass


class OntologyRelationshipUpdate(BaseModel):
    relationship_type: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class OntologyRelationshipResponse(OntologyRelationshipBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    source_concept: Optional[OntologyConceptResponse] = None
    target_concept: Optional[OntologyConceptResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- Concept with full relationships ---

class OntologyConceptWithRelationships(OntologyConceptResponse):
    outgoing_relationships: List[OntologyRelationshipResponse] = []
    incoming_relationships: List[OntologyRelationshipResponse] = []


# --- Graph response for visualization ---

class OntologyGraphNode(BaseModel):
    id: int
    name: str
    concept_type: str
    source_type: str = "document"
    initiative_id: Optional[int] = None
    confidence_score: Optional[float] = None
    # Artifact navigation fields — populated by subgraph endpoints
    source_component_id: Optional[int] = None      # FK to code_components.id
    source_document_id: Optional[int] = None       # FK to documents.id
    source_artifact_name: Optional[str] = None     # Human-readable name (filename/doc title)
    source_artifact_location: Optional[str] = None # File path for code components
    is_home: Optional[bool] = None                 # True = from the focal artifact; False = neighbor

    model_config = ConfigDict(from_attributes=True)


class OntologyGraphEdge(BaseModel):
    id: int
    source_concept_id: int
    target_concept_id: int
    relationship_type: str
    confidence_score: Optional[float] = None
    description: Optional[str] = None             # Edge label / reasoning

    model_config = ConfigDict(from_attributes=True)


class OntologyGraphResponse(BaseModel):
    nodes: List[OntologyGraphNode]
    edges: List[OntologyGraphEdge]
    total_nodes: int
    total_edges: int


class EgocentricGraphResponse(OntologyGraphResponse):
    """
    Egocentric (ego-network) graph centered on a single artifact.
    Home nodes = concepts extracted FROM the focal artifact.
    Neighbor nodes = concepts from OTHER artifacts that home concepts link to/from.
    """
    focal_component_id: Optional[int] = None
    focal_document_id: Optional[int] = None
    focal_artifact_name: Optional[str] = None
    home_node_count: int = 0
    neighbor_node_count: int = 0
    # List of distinct artifact summaries that connect to this one
    connected_artifacts: List[dict] = []


# --- Branch Preview Schemas (Sprint 4 Phase 4) ---

class BranchPreviewNode(OntologyGraphNode):
    diff_status: str = "unchanged"  # "unchanged", "added", "modified", "removed"


class BranchPreviewEdge(OntologyGraphEdge):
    diff_status: str = "unchanged"  # "unchanged", "added", "modified", "removed"


class BranchPreviewGraphResponse(BaseModel):
    nodes: List[BranchPreviewNode]
    edges: List[BranchPreviewEdge]
    total_nodes: int
    total_edges: int
    branch: str
    commit_hash: str
    changed_files: List[str] = []
