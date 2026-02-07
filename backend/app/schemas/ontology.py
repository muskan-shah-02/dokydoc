from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


# --- Ontology Concept Schemas ---

class OntologyConceptBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    concept_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class OntologyConceptCreate(OntologyConceptBase):
    pass


class OntologyConceptUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    concept_type: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class OntologyConceptResponse(OntologyConceptBase):
    id: int
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
    confidence_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class OntologyGraphEdge(BaseModel):
    id: int
    source_concept_id: int
    target_concept_id: int
    relationship_type: str
    confidence_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class OntologyGraphResponse(BaseModel):
    nodes: List[OntologyGraphNode]
    edges: List[OntologyGraphEdge]
    total_nodes: int
    total_edges: int
