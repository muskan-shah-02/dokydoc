"""
CRUD operations for Conversation and ChatMessage.
Sprint 7: RAG/Chat Assistant.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation import Conversation, ChatMessage


class CRUDConversation:
    """CRUD for Conversation model."""

    def create(self, db: Session, *, tenant_id: int, user_id: int, title: str = "New Conversation",
               context_type: str = "general", context_id: Optional[int] = None) -> Conversation:
        obj = Conversation(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            context_type=context_type,
            context_id=context_id,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get(self, db: Session, *, id: int, tenant_id: int) -> Optional[Conversation]:
        return db.query(Conversation).filter(
            Conversation.id == id,
            Conversation.tenant_id == tenant_id,
        ).first()

    def get_by_user(self, db: Session, *, tenant_id: int, user_id: int,
                    skip: int = 0, limit: int = 50) -> List[Conversation]:
        return db.query(Conversation).filter(
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
        ).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit).all()

    def count_by_user(self, db: Session, *, tenant_id: int, user_id: int) -> int:
        return db.query(Conversation).filter(
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
        ).count()

    def update_title(self, db: Session, *, conversation: Conversation, title: str) -> Conversation:
        conversation.title = title
        db.commit()
        db.refresh(conversation)
        return conversation

    def increment_stats(self, db: Session, *, conversation: Conversation,
                        tokens: int, cost_usd: float) -> None:
        conversation.message_count += 1
        conversation.total_tokens += tokens
        conversation.total_cost_usd += cost_usd
        db.commit()

    def delete(self, db: Session, *, id: int, tenant_id: int) -> bool:
        obj = self.get(db, id=id, tenant_id=tenant_id)
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False


class CRUDChatMessage:
    """CRUD for ChatMessage model."""

    def create(self, db: Session, *, conversation_id: int, role: str, content: str,
               context_used: Optional[dict] = None, input_tokens: int = 0,
               output_tokens: int = 0, cost_usd: float = 0.0,
               model_used: Optional[str] = None) -> ChatMessage:
        obj = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            context_used=context_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            model_used=model_used,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_conversation(self, db: Session, *, conversation_id: int,
                            skip: int = 0, limit: int = 100) -> List[ChatMessage]:
        return db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
        ).order_by(ChatMessage.created_at).offset(skip).limit(limit).all()

    def count_by_conversation(self, db: Session, *, conversation_id: int) -> int:
        return db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
        ).count()

    def get_recent(self, db: Session, *, conversation_id: int, limit: int = 10) -> List[ChatMessage]:
        """Get the most recent messages for conversation history context."""
        messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
        ).order_by(desc(ChatMessage.created_at)).limit(limit).all()
        return list(reversed(messages))


conversation = CRUDConversation()
chat_message = CRUDChatMessage()
