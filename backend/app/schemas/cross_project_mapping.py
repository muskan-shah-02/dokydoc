"""
CrossProjectMapping Schemas — Cross-Project Mapping API contracts
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal
from datetime import datetime


class CrossProjectMappingBase(BaseModel):
    concept_a_id: int
    concept_b_id: int
    initiative_a_id: int
    initiative_b_id: int
    relationship_type: str = Field(default="shares_concept", max_length=50)


class CrossProjectMappingCreate(CrossProjectMappingBase):
    mapping_method: Literal["exact", "fuzzy", "ai_validated"] = "exact"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["candidate", "confirmed", "rejected"] = "candidate"
    ai_reasoning: Optional[str] = None


class CrossProjectMappingUpdate(BaseModel):
    status: Optional[Literal["candidate", "confirmed", "rejected"]] = None
    relationship_type: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_reasoning: Optional[str] = None


class CrossProjectMappingResponse(CrossProjectMappingBase):
    id: int
    tenant_id: int
    mapping_method: str
    confidence_score: float
    status: str
    ai_reasoning: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CrossProjectMappingWithConcepts(CrossProjectMappingResponse):
    """Extended response with concept and project names."""
    concept_a_name: Optional[str] = None
    concept_a_type: Optional[str] = None
    concept_b_name: Optional[str] = None
    concept_b_type: Optional[str] = None
    initiative_a_name: Optional[str] = None
    initiative_b_name: Optional[str] = None


class CrossProjectMappingRunRequest(BaseModel):
    """Request body for triggering cross-project mapping between two projects."""
    initiative_a_id: int
    initiative_b_id: int


class CrossProjectMappingRunResult(BaseModel):
    """Result of running the cross-project mapping algorithm."""
    initiative_a_id: int
    initiative_b_id: int
    exact_matches: int = 0
    fuzzy_matches: int = 0
    ai_validated: int = 0
    total_mappings: int = 0
    ai_cost_inr: float = 0.0


class CrossProjectStats(BaseModel):
    """Cross-project mapping statistics."""
    total_mappings: int = 0
    confirmed_mappings: int = 0
    candidate_mappings: int = 0
    project_pairs: int = 0
