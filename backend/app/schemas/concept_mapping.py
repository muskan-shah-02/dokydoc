"""
ConceptMapping Schemas — Cross-Graph Mapping API contracts
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal
from datetime import datetime


class ConceptMappingBase(BaseModel):
    document_concept_id: int
    code_concept_id: int
    relationship_type: str = Field(default="implements", max_length=50)


class ConceptMappingCreate(ConceptMappingBase):
    mapping_method: Literal["exact", "fuzzy", "ai_validated"] = "exact"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["candidate", "confirmed", "rejected"] = "candidate"
    ai_reasoning: Optional[str] = None


class ConceptMappingUpdate(BaseModel):
    status: Optional[Literal["candidate", "confirmed", "rejected"]] = None
    relationship_type: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_reasoning: Optional[str] = None


class ConceptMappingResponse(ConceptMappingBase):
    id: int
    tenant_id: int
    mapping_method: str
    confidence_score: float
    status: str
    ai_reasoning: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConceptMappingWithConcepts(ConceptMappingResponse):
    """Extended response that includes the concept details."""
    document_concept_name: Optional[str] = None
    document_concept_type: Optional[str] = None
    code_concept_name: Optional[str] = None
    code_concept_type: Optional[str] = None


class MappingRunResult(BaseModel):
    """Result of running the 3-tier mapping algorithm."""
    exact_matches: int = 0
    fuzzy_matches: int = 0
    ai_validated: int = 0
    total_mappings: int = 0
    total_gaps: int = 0        # document concepts with no code match
    total_undocumented: int = 0  # code concepts with no document match
    ai_cost_inr: float = 0.0


class MismatchSummary(BaseModel):
    """Gaps and undocumented features detected by graph comparison."""
    gaps: List[dict] = []          # doc concepts with no code mapping
    undocumented: List[dict] = []  # code concepts with no doc mapping
    contradictions: List[dict] = []  # mappings where relationship_type == "contradicts"
