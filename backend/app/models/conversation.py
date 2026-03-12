"""
Conversation and ChatMessage models for RAG/Chat Assistant.
Sprint 7: Enables natural-language Q&A over documents, code, and knowledge graphs.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Conversation(Base):
    """
    A chat conversation scoped to a tenant/user.
    Can optionally be scoped to a specific entity (document, repository, initiative).
    """
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False, default="New Conversation")

    # Context scoping: "general" | "document" | "repository" | "initiative"
    context_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    context_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Model selection (Task 6): "gemini" (default) | "claude" | "auto"
    model_preference: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini")

    # Aggregate stats
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    messages: Mapped[list] = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, title='{self.title}', context={self.context_type})>"


class ChatMessage(Base):
    """
    A single message in a conversation (user or assistant).
    Tracks token usage and retrieved context for transparency.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # What context was retrieved for this response (assistant messages only)
    context_used: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Token and cost tracking
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)

    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role}, tokens={self.input_tokens + self.output_tokens})>"
