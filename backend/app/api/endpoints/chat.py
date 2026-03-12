"""
Sprint 7: Chat / RAG Assistant API Endpoints

Provides conversational AI over documents, code, and knowledge graphs.

Endpoints:
  POST   /chat/conversations                   -> create conversation
  GET    /chat/conversations                   -> list user's conversations
  GET    /chat/conversations/{id}              -> get conversation detail
  POST   /chat/conversations/{id}/messages     -> send message, get AI response
  GET    /chat/conversations/{id}/messages     -> message history
  PUT    /chat/conversations/{id}              -> update title
  DELETE /chat/conversations/{id}              -> delete conversation
"""

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models
from app.api import deps
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSendResponse,
    ChatMessageListResponse,
)
from app.core.logging import logger

router = APIRouter()


# -------------------------------------------------------------------
# Conversation CRUD
# -------------------------------------------------------------------

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Create a new chat conversation."""
    conv = crud.conversation.create(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        title=payload.title or "New Conversation",
        context_type=payload.context_type,
        context_id=payload.context_id,
    )
    return conv


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """List the current user's conversations."""
    convs = crud.conversation.get_by_user(
        db, tenant_id=tenant_id, user_id=current_user.id,
        skip=skip, limit=limit,
    )
    total = crud.conversation.count_by_user(
        db, tenant_id=tenant_id, user_id=current_user.id,
    )
    return {"conversations": convs, "total": total}


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get a single conversation."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")
    return conv


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: int,
    title: str = Query(..., min_length=1, max_length=500),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Update conversation title."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")
    return crud.conversation.update_title(db, conversation=conv, title=title)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Delete a conversation and all its messages."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")
    crud.conversation.delete(db, id=conversation_id, tenant_id=tenant_id)
    return {"detail": "Conversation deleted"}


# -------------------------------------------------------------------
# Messages — send + retrieve
# -------------------------------------------------------------------

@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
async def send_message(
    conversation_id: int,
    payload: ChatMessageCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Send a user message and get an AI response.

    Pipeline:
      1. Save user message
      2. Retrieve relevant context (semantic search + graph)
      3. Build prompt with conversation history
      4. Generate AI answer
      5. Save assistant message with context metadata
    """
    # Validate conversation
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    # 1. Save user message
    user_msg = crud.chat_message.create(
        db,
        conversation_id=conversation_id,
        role="user",
        content=payload.content,
    )

    # 2. Retrieve context
    from app.services.rag_service import rag_service
    context = rag_service.retrieve_context(
        db, payload.content, tenant_id,
        context_type=conv.context_type,
        context_id=conv.context_id,
    )

    # 3. Get conversation history for multi-turn
    recent_messages = crud.chat_message.get_recent(
        db, conversation_id=conversation_id, limit=8,
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in recent_messages
        if m.id != user_msg.id  # Exclude the message we just saved
    ]

    # 4. Generate AI answer (role-aware: passes user roles + db for org context)
    result = await rag_service.generate_answer(
        payload.content, context, history,
        tenant_id=tenant_id,
        user_id=current_user.id,
        user_roles=current_user.roles,
        db=db,
    )

    # 5. Save assistant message (include citations in context_used)
    context_summary = context.to_summary_dict()
    citations = result.get("citations", [])
    if citations:
        context_summary["citations"] = citations
    assistant_msg = crud.chat_message.create(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=result["answer"],
        context_used=context_summary,
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
        model_used=result["model_used"],
    )

    # Update conversation stats (count both user + assistant messages)
    total_tokens = result["input_tokens"] + result["output_tokens"]
    conv.message_count += 2
    conv.total_tokens += total_tokens
    conv.total_cost_usd = float(conv.total_cost_usd or 0) + result["cost_usd"]

    # Auto-title on first message
    if conv.message_count <= 2 and conv.title == "New Conversation":
        conv.title = payload.content[:80] + ("..." if len(payload.content) > 80 else "")

    db.commit()

    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "context_summary": context_summary,
        "citations": citations,
    }


@router.get("/conversations/{conversation_id}/messages", response_model=ChatMessageListResponse)
def list_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Get message history for a conversation."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    messages = crud.chat_message.get_by_conversation(
        db, conversation_id=conversation_id, skip=skip, limit=limit,
    )
    total = crud.chat_message.count_by_conversation(
        db, conversation_id=conversation_id,
    )
    return {"messages": messages, "total": total}
