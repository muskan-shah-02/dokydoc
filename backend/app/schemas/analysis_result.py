# This is the content for your NEW file at:
# backend/app/schemas/analysis_result.py

from pydantic import BaseModel
from datetime import datetime
from typing import Any, Optional

# --- Base Schema ---
# Contains the essential fields needed to describe an analysis result.
class AnalysisResultBase(BaseModel):
    segment_id: int
    document_id: Optional[int] = None

# --- Create Schema ---
# This defines the data your API will expect when creating a new analysis result.
# The `structured_data` can be any valid JSON structure returned by the AI.
class AnalysisResultCreate(AnalysisResultBase):
    structured_data: Any

# --- Main Schema for API Responses ---
# This is the schema used when returning analysis result data from the API.
class AnalysisResult(AnalysisResultBase):
    id: int
    structured_data: Any
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 uses `from_attributes` to create the schema from a DB model.
    class Config:
        from_attributes = True
