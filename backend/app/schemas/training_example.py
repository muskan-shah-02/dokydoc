from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TrainingExampleCreate(BaseModel):
    tenant_id: int
    task_type: str
    input_text: str
    ai_output: str
    ai_confidence: Optional[float] = None
    model_name: Optional[str] = None
    source_mismatch_id: Optional[int] = None


class TrainingExampleUpdate(BaseModel):
    human_label: Optional[str] = None
    feedback_source: Optional[str] = None
    feedback_at: Optional[datetime] = None
    reviewer_id: Optional[int] = None


class FeedbackRequest(BaseModel):
    """Body for POST /training-examples/{id}/feedback"""
    feedback_source: str  # 'accept' | 'reject' | 'edit'
    human_label: Optional[str] = None  # required when feedback_source == 'edit'


class TrainingExampleOut(BaseModel):
    id: int
    tenant_id: int
    task_type: str
    input_text: str
    ai_output: str
    ai_confidence: Optional[float]
    model_name: Optional[str]
    human_label: Optional[str]
    feedback_source: str
    feedback_at: Optional[datetime]
    source_mismatch_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
