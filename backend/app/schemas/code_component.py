# This is the updated content for your file at:
# backend/app/schemas/code_component.py

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

# --- Base Schema ---
# Defines the common properties shared across all related schemas.
class CodeComponentBase(BaseModel):
    name: str
    component_type: str
    location: str
    version: str

# --- Create Schema ---
# Defines the properties required to create a new component.
# This is what the API will expect in the request body on a POST.
class CodeComponentCreate(CodeComponentBase):
    pass

# --- Update Schema ---
# Defines the properties that can be updated. All are optional.
# This is what the API will expect in the request body on a PATCH/PUT.
class CodeComponentUpdate(BaseModel):
    name: Optional[str] = None
    component_type: Optional[str] = None
    location: Optional[str] = None
    version: Optional[str] = None
    summary: Optional[str] = None
    structured_analysis: Optional[Dict[str, Any]] = None
    analysis_status: Optional[str] = None

# --- InDBBase Schema (The one you asked about) ---
# This is a critical addition. It represents all the fields for a component
# as it exists in the database, including auto-generated fields like id, owner_id, etc.
# It serves as a reusable base for any schema that reads from the DB.
class CodeComponentInDBBase(CodeComponentBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Analysis fields
    summary: Optional[str] = None
    structured_analysis: Optional[Dict[str, Any]] = None
    analysis_status: str

    # Link to parent repository (nullable for standalone file components)
    repository_id: Optional[int] = None

    # Cost tracking fields
    ai_cost_inr: Optional[float] = None
    token_count_input: Optional[int] = None
    token_count_output: Optional[int] = None
    cost_breakdown: Optional[Dict[str, Any]] = None

    # Analysis timing
    analysis_started_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None

    class Config:
        # This vital setting allows Pydantic to read data directly from
        # a SQLAlchemy ORM model instance.
        # Pydantic V2: renamed from 'orm_mode' to 'from_attributes'
        from_attributes = True

# --- Main API Response Schema ---
# This is the final schema that will be used when returning data from the API.
# It inherits everything from our InDBBase and represents a complete object.
class CodeComponent(CodeComponentInDBBase):
    pass


class CodeComponentWithProgress(CodeComponent):
    """Extended response that includes repository analysis progress.
    For components linked to a repository, these fields show how many
    files have been analyzed out of the total — enabling real-time
    progress indicators in the UI.
    """
    repo_analyzed_files: Optional[int] = None
    repo_total_files: Optional[int] = None
    repo_analysis_status: Optional[str] = None


# =========================================================================
# Phase 3 (P3.7 / GAP-2): Data Flow response schemas
# =========================================================================

class DataFlowNodeSchema(BaseModel):
    """A node in the data flow graph — maps to a CodeComponent (or external)."""
    component_id: Optional[int] = None
    name: str
    location: Optional[str] = None
    file_role: Optional[str] = None
    summary: Optional[str] = None
    is_external: bool = False

    class Config:
        from_attributes = True


class DataFlowEdgeSchema(BaseModel):
    """A directed edge between two components in the data flow graph."""
    id: Optional[int] = None
    source_component_id: int
    target_component_id: Optional[int] = None
    edge_type: str
    # Per-spec individual columns (GAP-3)
    source_function: Optional[str] = None
    target_function: Optional[str] = None
    data_in_description: Optional[str] = None
    data_out_description: Optional[str] = None
    human_label: Optional[str] = None
    external_target_name: Optional[str] = None
    step_index: Optional[int] = None
    # Short Mermaid caption
    data_summary: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EgocentricFlowResponse(BaseModel):
    """Response for GET /code-components/{id}/data-flow/egocentric."""
    component_id: int
    file_role: Optional[str] = None
    edges_in: list[DataFlowEdgeSchema]
    edges_out: list[DataFlowEdgeSchema]
    nodes: list[DataFlowNodeSchema]
    mermaid_technical: str
    mermaid_simple: str
    total_edges: int
    edges_built_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RequestTraceResponse(BaseModel):
    """Response for GET /code-components/{id}/data-flow/request-trace."""
    start_component_id: int
    depth: int
    nodes: list[DataFlowNodeSchema]
    edges: list[DataFlowEdgeSchema]
    mermaid_technical: str
    mermaid_simple: str
    total_nodes: int
    total_edges: int
    edges_built_at: Optional[datetime] = None

    class Config:
        from_attributes = True

