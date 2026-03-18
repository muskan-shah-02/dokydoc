"""
Sprint 7: Chat / RAG Assistant API Endpoints
Phase 2: Backend Hardening (Tasks 8-12)

Provides conversational AI over documents, code, and knowledge graphs.

Endpoints:
  POST   /chat/conversations                   -> create conversation
  GET    /chat/conversations                   -> list user's conversations
  GET    /chat/conversations/{id}              -> get conversation detail
  POST   /chat/conversations/{id}/messages     -> send message, get AI response
  GET    /chat/conversations/{id}/messages     -> message history
  PUT    /chat/conversations/{id}              -> update title
  DELETE /chat/conversations/{id}              -> delete conversation
  PUT    /chat/conversations/{id}/model        -> switch AI model
  GET    /chat/suggested-prompts               -> role-based starter prompts (Task 10)
  POST   /chat/messages/{id}/feedback          -> thumbs up/down (Task 11)
  GET    /chat/conversations/search            -> search conversations (Task 12)
  GET    /chat/conversations/{id}/export       -> export conversation (Task 12)
"""

import time
from typing import Any, Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

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
    ModelPreferenceUpdate,
    CommandRequest,
    CommandResponse,
)
from app.core.logging import logger
from app.core.permissions import Permission
from app.middleware.rate_limiter import limiter, RateLimits

router = APIRouter()

# Chat-specific rate limit: 20 messages per minute (Task 12)
CHAT_MESSAGE_RATE = "20/minute;200/hour"
# Max messages per conversation before warning (Task 12)
MAX_CONVERSATION_MESSAGES = 500


def _check_billing(db: Session, tenant_id: int, estimated_cost_inr: float = 1.0) -> None:
    """Pre-check billing before AI operations (Task 8)."""
    from app.services.billing_enforcement_service import (
        billing_enforcement_service,
        InsufficientBalanceException,
        MonthlyLimitExceededException,
    )
    try:
        billing_enforcement_service.check_can_afford_analysis(
            db, tenant_id=tenant_id, estimated_cost_inr=estimated_cost_inr,
        )
    except InsufficientBalanceException as e:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "INSUFFICIENT_BALANCE",
                "message": str(e),
                "required_inr": e.required,
                "available_inr": e.available,
            },
        )
    except MonthlyLimitExceededException as e:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "MONTHLY_LIMIT_EXCEEDED",
                "message": str(e),
                "monthly_limit_inr": e.limit,
                "current_month_cost": e.current,
            },
        )


def _log_chat_usage(
    db: Session, *, tenant_id: int, user_id: int,
    input_tokens: int, output_tokens: int,
    cost_usd: float, model_used: str,
    processing_time: Optional[float] = None,
    conversation_id: Optional[int] = None,
) -> None:
    """Log chat usage for billing analytics (Task 8)."""
    usd_to_inr = 85.0
    cost_inr = cost_usd * usd_to_inr
    crud.usage_log.log_usage(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        feature_type="chat",
        operation="chat_response",
        model_used=model_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        cost_inr=cost_inr,
        processing_time_seconds=processing_time,
        extra_data={"conversation_id": conversation_id} if conversation_id else None,
    )

    # Deduct cost from billing
    if cost_inr > 0:
        from app.services.billing_enforcement_service import billing_enforcement_service
        try:
            billing_enforcement_service.deduct_cost(
                db, tenant_id=tenant_id, cost_inr=cost_inr,
                description=f"Chat response ({model_used})",
            )
        except Exception:
            logger.warning(f"Billing deduction failed for tenant {tenant_id}, cost_inr={cost_inr}")


# -------------------------------------------------------------------
# Conversation CRUD
# -------------------------------------------------------------------

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """Create a new chat conversation."""
    conv = crud.conversation.create(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        title=payload.title or "New Conversation",
        context_type=payload.context_type,
        context_id=payload.context_id,
        model_preference=payload.model_preference,
    )
    return conv


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
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


@router.get("/conversations/search")
def search_conversations(
    q: str = Query(..., min_length=1, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """Search conversations by title (Task 12)."""
    query = db.query(models.Conversation).filter(
        models.Conversation.tenant_id == tenant_id,
        models.Conversation.user_id == current_user.id,
        models.Conversation.title.ilike(f"%{q}%"),
    ).order_by(desc(models.Conversation.updated_at))

    total = query.count()
    conversations = query.offset(skip).limit(limit).all()
    return {"conversations": conversations, "total": total}


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
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
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
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
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
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
@limiter.limit(CHAT_MESSAGE_RATE)
async def send_message(
    request: Request,
    response: Response,
    conversation_id: int,
    payload: ChatMessageCreate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """
    Send a user message and get an AI response.

    Pipeline:
      1. Billing pre-check (Task 8)
      2. Rate + conversation length check (Task 12)
      3. Save user message
      4. Retrieve relevant context (semantic search + graph)
      5. Build prompt with conversation history
      6. Generate AI answer
      7. Save assistant message with context metadata
      8. Log usage for billing analytics (Task 8)
    """
    start_time = time.time()

    # Validate conversation
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    # Task 8: Billing pre-check (estimated ₹1 per chat message)
    _check_billing(db, tenant_id, estimated_cost_inr=1.0)

    # Task 12: Conversation length check
    if conv.message_count >= MAX_CONVERSATION_MESSAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Conversation has reached the maximum of {MAX_CONVERSATION_MESSAGES} messages. "
                   "Please start a new conversation.",
        )

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
        user_id=current_user.id,
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

    # 4. Generate AI answer (role-aware + model selection)
    result = await rag_service.generate_answer(
        payload.content, context, history,
        tenant_id=tenant_id,
        user_id=current_user.id,
        user_roles=current_user.roles,
        model_preference=conv.model_preference,
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

    # Task 8: Log usage for billing analytics
    # Wrapped in try/except: a logging failure must NOT crash the response —
    # the user message + AI answer are already committed to the DB at this point.
    processing_time = time.time() - start_time
    try:
        _log_chat_usage(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cost_usd=result["cost_usd"],
            # model_used can be None when AI call falls back to error message;
            # the DB column is NOT NULL so supply a default to prevent a crash.
            model_used=result["model_used"] or "unknown",
            processing_time=processing_time,
            conversation_id=conversation_id,
        )
    except Exception as log_err:
        logger.warning(f"Chat usage logging failed (non-fatal): {log_err}")

    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "context_summary": context_summary,
        "citations": citations,
        "approval_references": context.pending_approvals if context.pending_approvals else None,
    }


@router.get("/conversations/{conversation_id}/messages", response_model=ChatMessageListResponse)
def list_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
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


# -------------------------------------------------------------------
# Model Selection (Task 6)
# -------------------------------------------------------------------

@router.put("/conversations/{conversation_id}/model", response_model=ConversationResponse)
def update_model_preference(
    conversation_id: int,
    payload: ModelPreferenceUpdate,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """Switch AI model mid-conversation (gemini / claude / auto)."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    conv.model_preference = payload.model_preference
    db.commit()
    db.refresh(conv)
    return conv


# -------------------------------------------------------------------
# Suggested Prompts (Task 10)
# -------------------------------------------------------------------

ROLE_SUGGESTED_PROMPTS = {
    "CXO": [
        "What's the overall health of our documentation vs codebase alignment?",
        "Show me the top compliance risks across all projects.",
        "Summarize cost trends for AI usage this month.",
        "Which initiatives have the most requirement gaps?",
        "Give me a strategic overview of our technical debt.",
    ],
    "ADMIN": [
        "How many users are active this month?",
        "What's our current billing usage summary?",
        "Show me the audit trail for recent changes.",
        "Which teams are using the most AI credits?",
        "What system health issues should I be aware of?",
    ],
    "DEVELOPER": [
        "Explain the architecture of the authentication module.",
        "Find all API endpoints that lack input validation.",
        "What code components have the most mismatches with requirements?",
        "Show me the dependency graph for this repository.",
        "Which functions have the highest complexity scores?",
    ],
    "BA": [
        "What requirements are missing traceability to code?",
        "Compare the PRD with the actual implementation.",
        "Show me all validation mismatches for this document.",
        "What are the key findings from the latest analysis?",
        "Which requirements have partial or no coverage?",
    ],
    "PRODUCT_MANAGER": [
        "What's the feature coverage status for the current initiative?",
        "Show me requirements that changed in the last sprint.",
        "Which features are at risk based on code analysis?",
        "Summarize the gap between PRD and implementation.",
        "What are the top user-facing issues from code analysis?",
    ],
    "AUDITOR": [
        "Show me the compliance status across all documents.",
        "What changes were made to critical components this week?",
        "List all requirement traces with failed coverage.",
        "Generate an audit summary for recent document analyses.",
        "What are the top security-related findings?",
    ],
}

# Default prompts for users without specific role matches
DEFAULT_SUGGESTED_PROMPTS = [
    "What documents have been analyzed recently?",
    "Show me an overview of the knowledge graph.",
    "What are the most common validation issues?",
    "Explain the relationship between these components.",
    "What insights can you share about our codebase?",
]


@router.get("/suggested-prompts")
def get_suggested_prompts(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """Get role-based suggested starter prompts (Task 10)."""
    prompts = []
    matched_role = None

    # Priority order for role matching
    role_priority = ["CXO", "ADMIN", "DEVELOPER", "BA", "PRODUCT_MANAGER", "AUDITOR"]

    for role in role_priority:
        if role in (current_user.roles or []):
            prompts = ROLE_SUGGESTED_PROMPTS[role]
            matched_role = role
            break

    if not prompts:
        prompts = DEFAULT_SUGGESTED_PROMPTS
        matched_role = "default"

    return {
        "prompts": prompts,
        "role": matched_role,
        "total": len(prompts),
    }


# -------------------------------------------------------------------
# Message Feedback (Task 11)
# -------------------------------------------------------------------

@router.post("/messages/{message_id}/feedback")
def submit_feedback(
    message_id: int,
    rating: int = Query(..., ge=-1, le=1),
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """
    Submit feedback for an assistant message (Task 11).

    rating: -1 (thumbs down), 0 (neutral/reset), 1 (thumbs up)
    """
    msg = db.query(models.ChatMessage).filter(
        models.ChatMessage.id == message_id,
    ).first()

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify ownership via conversation
    conv = crud.conversation.get(db, id=msg.conversation_id, tenant_id=tenant_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your message")

    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Can only rate assistant messages")

    msg.feedback_rating = rating
    db.commit()

    return {"detail": "Feedback recorded", "message_id": message_id, "rating": rating}


# -------------------------------------------------------------------
# Conversation Export (Task 12)
# -------------------------------------------------------------------

SLASH_COMMAND_HELP = """## AskyDoc Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show all available commands | `/help` |
| `/status` | System overview: docs, analyses, pending items | `/status` |
| `/search [query]` | Semantic search across your knowledge base | `/search authentication flow` |
| `/export` | Export the current conversation as JSON | `/export` |
| `/pending` | List your pending approval requests | `/pending` |
| `/summarize [name]` | Summarize a document by name (AI) | `/summarize Requirements.pdf` |
| `/analyze [name]` | Analyze a code component by name (AI) | `/analyze AuthService` |
| `/compare [A] vs [B]` | Compare two documents or components (AI) | `/compare v1.pdf vs v2.pdf` |

> **Tip:** For AI commands (/summarize, /analyze, /compare), if multiple items match your search term, AskyDoc will show you the top matches to choose from.

View full documentation → [Help & Docs](/dashboard/help)
"""


def _handle_simple_command(
    command: str,
    args: str,
    conversation_id: int,
    db: Session,
    tenant_id: int,
    current_user: Any,
) -> str:
    """Handle simple slash commands that don't need the RAG pipeline."""
    if command == "/help":
        return SLASH_COMMAND_HELP

    if command == "/status":
        from app.models import Document, CodeComponent, Approval
        doc_count = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False) if hasattr(Document, "is_deleted") else True,
        ).count()
        code_count = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
        ).count()
        pending_approvals = db.query(Approval).filter(
            Approval.tenant_id == tenant_id,
            Approval.status == "pending",
        ).count()
        my_pending = db.query(Approval).filter(
            Approval.tenant_id == tenant_id,
            Approval.status == "pending",
            Approval.requested_by_id == current_user.id,
        ).count()
        return (
            f"## System Status\n\n"
            f"| Metric | Count |\n"
            f"|--------|-------|\n"
            f"| **Documents** | {doc_count} |\n"
            f"| **Code Components** | {code_count} |\n"
            f"| **Pending Approvals (all)** | {pending_approvals} |\n"
            f"| **My Pending Approvals** | {my_pending} |\n"
        )

    if command == "/pending":
        from app.models import Approval
        items = db.query(Approval).filter(
            Approval.tenant_id == tenant_id,
            Approval.status == "pending",
            Approval.requested_by_id == current_user.id,
        ).order_by(Approval.created_at.desc()).limit(10).all()
        if not items:
            return "## Pending Approvals\n\nNo pending approvals — you're all caught up! ✓"
        lines = ["## Your Pending Approvals\n", "| # | Entity | Type | Created |", "|---|--------|------|---------|"]
        for i, item in enumerate(items, 1):
            name = item.entity_name or f"#{item.entity_id}"
            created = item.created_at.strftime("%b %d") if item.created_at else "—"
            lines.append(f"| {i} | **{name}** | {item.entity_type} | {created} |")
        lines.append(f"\n> Navigate to [Approvals](/dashboard/approvals) to act on these.")
        return "\n".join(lines)

    if command == "/search":
        if not args.strip():
            return "> **Usage:** `/search [query]`\n\nProvide a search term, e.g. `/search authentication flow`"
        try:
            from app.services.semantic_search_service import semantic_search_service
            results = semantic_search_service.unified_search(
                db, query=args.strip(), tenant_id=tenant_id, limit=5
            )
            items = results.get("results", []) if isinstance(results, dict) else results
            if not items:
                return f"## Search: \"{args.strip()}\"\n\nNo results found. Try different keywords."
            lines = [f"## Search Results for \"{args.strip()}\"\n"]
            for i, r in enumerate(items, 1):
                name = r.get("name") or r.get("title") or "Untitled"
                rtype = r.get("type") or r.get("result_type") or "item"
                lines.append(f"{i}. **{name}** — `{rtype}`")
                snippet = r.get("snippet") or r.get("description") or ""
                if snippet:
                    lines.append(f"   > {snippet[:150]}")
            return "\n".join(lines)
        except Exception:
            return f"## Search: \"{args.strip()}\"\n\nSearch is temporarily unavailable. Try asking your question directly."

    if command == "/export":
        return (
            "## Export Conversation\n\n"
            "To export this conversation, click the **Download** button in the conversation header, "
            "or use the export button (↓) at the top of the chat.\n\n"
            "> The export includes all messages, model info, token counts, and timestamps in JSON format."
        )

    return f"> Unknown command: `{command}`\n\nType `/help` to see all available commands."


@router.post("/conversations/{conversation_id}/command", response_model=CommandResponse)
async def execute_command(
    conversation_id: int,
    payload: CommandRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """
    Execute a slash command without the full RAG/billing pipeline.
    Handles: /help, /status, /search, /export, /pending
    AI-powered commands (/summarize, /analyze, /compare) go through the normal send_message endpoint.
    """
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    command = payload.command.lower().strip()
    if not command.startswith("/"):
        command = f"/{command}"

    content = _handle_simple_command(
        command, payload.args, conversation_id, db, tenant_id, current_user,
    )

    return CommandResponse(command=command, content=content)


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.require_permission(Permission.CHAT_USE)),
) -> Any:
    """Export a conversation as structured JSON (Task 12)."""
    conv = crud.conversation.get(db, id=conversation_id, tenant_id=tenant_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your conversation")

    messages = crud.chat_message.get_by_conversation(
        db, conversation_id=conversation_id, skip=0, limit=10000,
    )

    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "context_type": conv.context_type,
            "model_preference": conv.model_preference,
            "message_count": conv.message_count,
            "total_tokens": conv.total_tokens,
            "total_cost_usd": float(conv.total_cost_usd or 0),
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        },
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "model_used": m.model_used,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "cost_usd": float(m.cost_usd or 0),
                "feedback_rating": m.feedback_rating,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "exported_at": datetime.utcnow().isoformat(),
    }
