"""Pydantic schemas for enterprise contact requests — Phase 9."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class EnterpriseContactCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=300)
    contact_name: str = Field(..., min_length=1, max_length=300)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    team_size: Optional[str] = Field(None, description="1-10 | 11-50 | 51-200 | 200+")
    use_case: Optional[str] = None
    message: Optional[str] = None


class EnterpriseContactResponse(BaseModel):
    id: int
    company_name: str
    contact_name: str
    email: str
    phone: Optional[str] = None
    team_size: Optional[str] = None
    use_case: Optional[str] = None
    message: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CostPreviewRequest(BaseModel):
    doc_size_kb: float = Field(10.0, gt=0, description="Document size in KB")
    passes: int = Field(3, ge=1, le=10, description="Number of analysis passes")
    model_id: Optional[str] = Field(None, description="Model to estimate for")


class CostPreviewResponse(BaseModel):
    model_id: str
    doc_size_kb: float
    passes: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    raw_cost_inr: float
    markup_percent: float
    markup_inr: float
    total_cost_inr: float
    wallet_balance_inr: Optional[float] = None
    can_afford: Optional[bool] = None
