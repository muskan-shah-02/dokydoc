"""
Pydantic schemas for RAG/Chat Assistant.
Sprint 7.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- Conversation Schemas ---

class ConversationCreate(BaseModel):
    """Create a new conversation."""
    title: Optional[str] = "New Conversation"
    context_type: str = "general"  # "general" | "document" | "repository" | "initiative"
    context_id: Optional[int] = None


class ConversationResponse(BaseModel):
    """Conversation in API responses."""
    id: int
    tenant_id: int
    user_id: int
    title: str
    context_type: str
    context_id: Optional[int] = None
    message_count: int
    total_tokens: int
    total_cost_usd: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""
    conversations: List[ConversationResponse]
    total: int


# --- Message Schemas ---

class ChatMessageCreate(BaseModel):
    """Send a message in a conversation."""
    content: str = Field(..., min_length=1, max_length=10000)


class ChatMessageResponse(BaseModel):
    """Chat message in API responses."""
    id: int
    conversation_id: int
    role: str
    content: str
    context_used: Optional[dict] = None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSendResponse(BaseModel):
    """Response after sending a message — includes both user msg and AI response."""
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    context_summary: Optional[dict] = None


class ChatMessageListResponse(BaseModel):
    """List of messages in a conversation."""
    messages: List[ChatMessageResponse]
    total: int
