"""
Usage Log schemas for billing analytics API.
"""
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class FeatureTypeEnum(str, Enum):
    """Types of features that use AI API calls."""
    DOCUMENT_ANALYSIS = "document_analysis"
    CODE_ANALYSIS = "code_analysis"
    VALIDATION = "validation"
    CHAT = "chat"
    SUMMARY = "summary"
    OTHER = "other"


class OperationTypeEnum(str, Enum):
    """Specific operations within features."""
    PASS_1_COMPOSITION = "pass_1_composition"
    PASS_2_SEGMENTING = "pass_2_segmenting"
    PASS_3_EXTRACTION = "pass_3_extraction"
    CODE_REVIEW = "code_review"
    CODE_EXPLANATION = "code_explanation"
    CODE_GENERATION = "code_generation"
    REQUIREMENT_VALIDATION = "requirement_validation"
    CODE_VALIDATION = "code_validation"
    TRACEABILITY_CHECK = "traceability_check"
    CHAT_RESPONSE = "chat_response"
    DOCUMENT_SUMMARY = "document_summary"
    CUSTOM = "custom"


class TimeRangeEnum(str, Enum):
    """Pre-defined time ranges for filtering."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_15_DAYS = "last_15_days"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_YEAR = "this_year"
    CUSTOM = "custom"


# --- Create Schema ---
class UsageLogCreate(BaseModel):
    """Schema for creating a new usage log entry."""
    tenant_id: int
    user_id: Optional[int] = None
    document_id: Optional[int] = None
    feature_type: str = Field(..., description="Feature type: document_analysis, code_analysis, etc.")
    operation: str = Field(..., description="Specific operation: pass_1_composition, code_review, etc.")
    model_used: str = Field(default="gemini-2.5-flash")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    cost_inr: float = Field(default=0.0, ge=0)
    processing_time_seconds: Optional[float] = None
    extra_data: Optional[dict] = None


# --- Response Schema ---
class UsageLogResponse(BaseModel):
    """Schema for a single usage log entry."""
    id: int
    tenant_id: int
    user_id: Optional[int] = None
    document_id: Optional[int] = None
    feature_type: str
    operation: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int = Field(..., description="input_tokens + output_tokens")
    cost_usd: float
    cost_inr: float
    processing_time_seconds: Optional[float] = None
    extra_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Analytics Response Schemas ---
class FeatureUsageSummary(BaseModel):
    """Summary of usage for a specific feature."""
    feature_type: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_cost_inr: float
    avg_cost_per_call_inr: float
    percentage_of_total: float = Field(..., description="Percentage of total cost")


class OperationUsageSummary(BaseModel):
    """Summary of usage for a specific operation."""
    feature_type: str
    operation: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_inr: float


class TimeSeriesDataPoint(BaseModel):
    """Single data point for time series charts."""
    date: date
    total_cost_inr: float
    total_tokens: int
    call_count: int


class DocumentUsageSummary(BaseModel):
    """Usage summary for a specific document."""
    document_id: int
    filename: str
    feature_type: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_inr: float
    last_used: datetime


class CodeComponentUsageSummary(BaseModel):
    """Usage summary for a specific code component."""
    component_id: int
    name: str
    component_type: str
    total_cost_inr: float
    token_count_input: int
    token_count_output: int
    total_tokens: int
    analysis_status: str


class TokenSummary(BaseModel):
    """Aggregate token summary."""
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    total_tokens: int
    avg_input_per_call: float
    avg_output_per_call: float
    input_output_ratio: float = Field(..., description="Ratio of input to output tokens")


# --- Main Analytics Response ---
class BillingAnalyticsResponse(BaseModel):
    """Comprehensive billing analytics response."""
    # Time range info
    time_range: str
    start_date: datetime
    end_date: datetime

    # Overall summary
    total_cost_inr: float
    total_cost_usd: float
    total_api_calls: int

    # Token summary
    tokens: TokenSummary

    # Feature breakdown
    by_feature: List[FeatureUsageSummary]

    # Operation breakdown (top 10)
    by_operation: List[OperationUsageSummary]

    # Time series data (for charts)
    daily_usage: List[TimeSeriesDataPoint]

    # Top documents by cost
    top_documents: List[DocumentUsageSummary]

    # Top code components by cost
    top_code_components: List[CodeComponentUsageSummary] = []


class BillingAnalyticsFilters(BaseModel):
    """Filters for billing analytics queries."""
    time_range: TimeRangeEnum = Field(default=TimeRangeEnum.THIS_MONTH)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    feature_type: Optional[str] = None
    document_id: Optional[int] = None
    user_id: Optional[int] = None


class WeeklyUsageSummary(BaseModel):
    """Weekly usage summary for dashboard cards."""
    week_number: int
    week_start: date
    week_end: date
    total_cost_inr: float
    total_tokens: int
    call_count: int
    change_from_previous_week: Optional[float] = None


class MonthlyUsageSummary(BaseModel):
    """Monthly usage summary."""
    month: int
    year: int
    month_name: str
    total_cost_inr: float
    total_tokens: int
    call_count: int
    by_feature: List[FeatureUsageSummary]


# --- User-Level Analytics (For Admin/CXO Dashboard) ---
class UserUsageSummary(BaseModel):
    """Usage summary for a specific user - for Admin/CXO billing view."""
    user_id: Optional[int] = None
    user_email: str
    user_name: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_cost_inr: float
    percentage_of_total: float = Field(..., description="Percentage of total tenant cost")
    last_activity: Optional[datetime] = None


class UserBillingAnalyticsResponse(BaseModel):
    """Detailed billing analytics for a specific user."""
    user_id: int
    user_email: str
    user_name: str
    time_range: str
    start_date: datetime
    end_date: datetime
    total_cost_inr: float
    total_cost_usd: float
    total_api_calls: int
    total_tokens: int
    by_feature: List[FeatureUsageSummary]
    daily_usage: List[TimeSeriesDataPoint]
    top_documents: List[DocumentUsageSummary]


class AllUsersAnalyticsResponse(BaseModel):
    """Analytics response showing all users' billing breakdown."""
    time_range: str
    start_date: datetime
    end_date: datetime
    total_tenant_cost_inr: float
    total_tenant_calls: int
    users: List[UserUsageSummary]
