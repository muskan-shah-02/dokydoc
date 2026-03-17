"""
Documentation Integrations API
Sprint 8: Module 11 — Notion, Jira, Confluence, SharePoint.

Phase 1: Notion + Jira (OAuth token-based connection)

  GET    /integrations/                       — List connected integrations
  POST   /integrations/connect                — Save access token for a provider
  DELETE /integrations/{id}                   — Disconnect an integration
  GET    /integrations/{provider}/pages       — List pages/issues from the connected provider
  POST   /integrations/{provider}/import/{id} — Import a page/issue as a DokuDoc document
"""
from typing import Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import httpx

from app import models
from app.api import deps
from app.db.session import get_db
from app.crud.crud_integration_config import crud_integration_config
from app.core.logging import get_logger

logger = get_logger("api.integrations")

router = APIRouter()

SUPPORTED_PROVIDERS = ["notion", "jira", "confluence", "sharepoint"]


# ---- Schemas ----

class ConnectRequest(BaseModel):
    provider: str = Field(..., pattern="^(notion|jira|confluence|sharepoint)$")
    access_token: str = Field(..., min_length=1)
    workspace_name: Optional[str] = None
    workspace_id: Optional[str] = None
    base_url: Optional[str] = None  # Required for Jira: https://company.atlassian.net


class IntegrationStatusResponse(BaseModel):
    id: int
    provider: str
    workspace_name: Optional[str] = None
    workspace_id: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool
    last_synced_at: Optional[str] = None
    sync_error: Optional[str] = None
    created_at: str


class ImportPageRequest(BaseModel):
    external_id: str = Field(..., description="Page ID (Notion) or issue key (Jira)")
    title: Optional[str] = None


# ---- Endpoints ----

@router.get("/")
def list_integrations(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Return all integrations configured for this tenant."""
    configs = crud_integration_config.get_for_tenant(db, tenant_id=tenant_id)
    return {
        "integrations": [
            IntegrationStatusResponse(
                id=c.id,
                provider=c.provider,
                workspace_name=c.workspace_name,
                workspace_id=c.workspace_id,
                base_url=c.base_url,
                is_active=c.is_active,
                last_synced_at=c.last_synced_at.isoformat() if c.last_synced_at else None,
                sync_error=c.sync_error,
                created_at=c.created_at.isoformat(),
            )
            for c in configs
        ],
        "supported_providers": SUPPORTED_PROVIDERS,
    }


@router.post("/connect", status_code=201)
def connect_integration(
    payload: ConnectRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Save an OAuth access token for a provider.
    For Jira: also provide base_url (e.g. https://company.atlassian.net).
    The access_token is stored as-is (encrypt in production).
    """
    if payload.provider == "jira" and not payload.base_url:
        raise HTTPException(
            status_code=400, detail="base_url is required for Jira (e.g. https://company.atlassian.net)"
        )

    obj = crud_integration_config.upsert(
        db,
        tenant_id=tenant_id,
        provider=payload.provider,
        created_by_id=current_user.id,
        access_token=payload.access_token,
        workspace_name=payload.workspace_name,
        workspace_id=payload.workspace_id,
        base_url=payload.base_url,
    )
    return {"status": "connected", "id": obj.id, "provider": obj.provider}


@router.delete("/{config_id}")
def disconnect_integration(
    config_id: int,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Revoke and remove the integration configuration."""
    obj = crud_integration_config.disconnect(db, config_id=config_id, tenant_id=tenant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"status": "disconnected", "id": config_id}


@router.get("/{provider}/pages")
async def list_provider_pages(
    provider: str,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
    query: Optional[str] = Query(None, description="Search / filter term"),
    limit: int = Query(20, ge=1, le=100),
) -> Any:
    """
    Fetch pages (Notion) or issues (Jira) from the connected integration.
    Returns a provider-normalized list: [{id, title, url, updated_at}]
    """
    config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider=provider)
    if not config or not config.is_active or not config.access_token:
        raise HTTPException(
            status_code=404,
            detail=f"No active {provider} integration found. Please connect first.",
        )

    try:
        if provider == "notion":
            items = await _notion_list_pages(config.access_token, query=query, limit=limit)
        elif provider == "jira":
            items = await _jira_list_issues(
                config.access_token, base_url=config.base_url or "", query=query, limit=limit
            )
        else:
            raise HTTPException(status_code=400, detail=f"List pages not yet supported for {provider}")
    except httpx.HTTPStatusError as e:
        crud_integration_config.mark_error(db, config_id=config.id, tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Provider API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Integration list_pages error ({provider}): {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch from {provider}: {str(e)}")

    return {"provider": provider, "items": items, "count": len(items)}


@router.post("/{provider}/import")
async def import_page(
    provider: str,
    payload: ImportPageRequest,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Fetch the full content of a Notion page or Jira issue and store it as
    a DokuDoc Document (raw_text + filename set, status='uploaded').
    """
    config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider=provider)
    if not config or not config.is_active or not config.access_token:
        raise HTTPException(
            status_code=404,
            detail=f"No active {provider} integration found.",
        )

    try:
        if provider == "notion":
            content, title = await _notion_fetch_page(config.access_token, payload.external_id)
        elif provider == "jira":
            content, title = await _jira_fetch_issue(
                config.access_token,
                base_url=config.base_url or "",
                issue_key=payload.external_id,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Import not yet supported for {provider}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Provider API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Integration import error ({provider}/{payload.external_id}): {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch content: {str(e)}")

    final_title = payload.title or title or f"{provider}_{payload.external_id}"

    # Store as a Document record
    from app.models.document import Document
    from datetime import datetime as dt

    doc = Document(
        tenant_id=tenant_id,
        filename=f"{final_title}.md",
        document_type="imported",
        version="1",
        raw_text=content,
        status="uploaded",
        created_at=dt.utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "status": "imported",
        "document_id": doc.id,
        "title": final_title,
        "provider": provider,
        "external_id": payload.external_id,
    }


# ============================================================
# Provider API helpers — Notion
# ============================================================

async def _notion_list_pages(token: str, query: Optional[str], limit: int) -> list[dict]:
    """Search Notion pages using the Search API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    body: dict = {"filter": {"value": "page", "property": "object"}, "page_size": limit}
    if query:
        body["query"] = query

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post("https://api.notion.com/v1/search", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for result in data.get("results", []):
        props = result.get("properties", {})
        # Extract title from Name or title property
        title = _extract_notion_title(props) or result.get("id", "Untitled")
        items.append({
            "id": result["id"],
            "title": title,
            "url": result.get("url", ""),
            "updated_at": result.get("last_edited_time", ""),
        })
    return items


async def _notion_fetch_page(token: str, page_id: str) -> tuple[str, str]:
    """Fetch a Notion page's block content and return (markdown_text, title)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        # Get page metadata
        page_resp = await client.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers)
        page_resp.raise_for_status()
        page_data = page_resp.json()
        title = _extract_notion_title(page_data.get("properties", {}))

        # Get blocks (content)
        blocks_resp = await client.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100",
            headers=headers,
        )
        blocks_resp.raise_for_status()
        blocks_data = blocks_resp.json()

    content_lines = [f"# {title or 'Notion Page'}", ""]
    for block in blocks_data.get("results", []):
        line = _notion_block_to_text(block)
        if line:
            content_lines.append(line)

    return "\n".join(content_lines), title or "Notion Page"


def _extract_notion_title(properties: dict) -> str:
    for key in ("Name", "title", "Title"):
        prop = properties.get(key)
        if prop and prop.get("type") == "title":
            rich = prop.get("title", [])
            if rich:
                return "".join(r.get("plain_text", "") for r in rich)
    return ""


def _notion_block_to_text(block: dict) -> str:
    bt = block.get("type", "")
    data = block.get(bt, {})
    rich = data.get("rich_text", [])
    text = "".join(r.get("plain_text", "") for r in rich) if rich else ""
    if bt == "paragraph":
        return text
    if bt.startswith("heading_"):
        level = int(bt[-1])
        return "#" * level + " " + text
    if bt in ("bulleted_list_item", "to_do"):
        return f"- {text}"
    if bt == "numbered_list_item":
        return f"1. {text}"
    if bt == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{text}\n```"
    if bt == "quote":
        return f"> {text}"
    if bt == "divider":
        return "---"
    return text


# ============================================================
# Provider API helpers — Jira
# ============================================================

async def _jira_list_issues(
    token: str, base_url: str, query: Optional[str], limit: int
) -> list[dict]:
    """Search Jira issues using JQL."""
    jql = f'text ~ "{query}"' if query else "order by updated DESC"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    params = {"jql": jql, "maxResults": limit, "fields": "summary,status,updated,assignee"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url.rstrip('/')}/rest/api/3/search", headers=headers, params=params
        )
        resp.raise_for_status()
        data = resp.json()

    items = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        items.append({
            "id": issue["key"],
            "title": f"[{issue['key']}] {fields.get('summary', 'Untitled')}",
            "url": f"{base_url.rstrip('/')}/browse/{issue['key']}",
            "updated_at": fields.get("updated", ""),
        })
    return items


async def _jira_fetch_issue(token: str, base_url: str, issue_key: str) -> tuple[str, str]:
    """Fetch a Jira issue and return (markdown_text, title)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}",
            headers=headers,
            params={"fields": "summary,description,status,priority,assignee,reporter,created,updated"},
        )
        resp.raise_for_status()
        data = resp.json()

    fields = data.get("fields", {})
    summary = fields.get("summary", issue_key)
    status = fields.get("status", {}).get("name", "")
    priority = fields.get("priority", {}).get("name", "")
    assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
    reporter = (fields.get("reporter") or {}).get("displayName", "Unknown")
    created = fields.get("created", "")
    updated = fields.get("updated", "")

    # Description is in Atlassian Document Format (ADF); do a simple plain-text extraction
    desc_raw = fields.get("description") or {}
    desc_text = _adf_to_text(desc_raw) if isinstance(desc_raw, dict) else str(desc_raw)

    content = f"""# [{issue_key}] {summary}

| Field | Value |
|-------|-------|
| Status | {status} |
| Priority | {priority} |
| Assignee | {assignee} |
| Reporter | {reporter} |
| Created | {created} |
| Updated | {updated} |

## Description

{desc_text}
"""
    return content, f"[{issue_key}] {summary}"


def _adf_to_text(doc: dict, depth: int = 0) -> str:
    """Minimal Atlassian Document Format (ADF) → plain text."""
    if not doc:
        return ""
    node_type = doc.get("type", "")
    content = doc.get("content", [])
    text = doc.get("text", "")

    if node_type == "text":
        return text
    if node_type in ("paragraph", "blockquote"):
        return "".join(_adf_to_text(c, depth) for c in content) + "\n"
    if node_type == "bulletList":
        return "".join(f"- {''.join(_adf_to_text(c, depth+1) for c in item.get('content', []))}\n" for item in content)
    if node_type == "orderedList":
        lines = []
        for i, item in enumerate(content, 1):
            lines.append(f"{i}. {''.join(_adf_to_text(c, depth+1) for c in item.get('content', []))}")
        return "\n".join(lines) + "\n"
    if node_type == "heading":
        level = doc.get("attrs", {}).get("level", 2)
        return "#" * level + " " + "".join(_adf_to_text(c, depth) for c in content) + "\n"
    if node_type == "codeBlock":
        lang = doc.get("attrs", {}).get("language", "")
        inner = "".join(_adf_to_text(c, depth) for c in content)
        return f"```{lang}\n{inner}\n```\n"
    if node_type in ("doc", "listItem", "tableRow", "tableHeader", "tableCell"):
        return "".join(_adf_to_text(c, depth) for c in content)

    # Fallback: recurse
    return "".join(_adf_to_text(c, depth) for c in content)
