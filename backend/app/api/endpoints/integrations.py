"""
Documentation Integrations API
Sprint 8: Module 11 — Notion, Jira, Confluence, SharePoint, Slack.

Manual token connect (Notion):
  POST   /integrations/connect                — Save access token for a provider

Jira OAuth 2.0 (Atlassian):
  GET    /integrations/jira/oauth/authorize   — Get Atlassian OAuth URL
  GET    /integrations/jira/oauth/callback    — Exchange code, store tokens, redirect to frontend

Slack OAuth 2.0:
  GET    /integrations/slack/oauth/authorize  — Get Slack OAuth URL
  GET    /integrations/slack/oauth/callback   — Exchange code, store tokens, redirect to frontend

Common:
  GET    /integrations/                       — List connected integrations
  DELETE /integrations/{id}                   — Disconnect an integration
  GET    /integrations/{provider}/pages       — List pages/issues/channels from provider
  POST   /integrations/{provider}/import/{id} — Import content as a DokuDoc document
"""
import base64
import hashlib
import hmac
import json
from typing import Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import httpx

from app import models
from app.api import deps
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.crud.crud_integration_config import crud_integration_config

logger = get_logger("api.integrations")

router = APIRouter()

SUPPORTED_PROVIDERS = ["notion", "jira", "confluence", "sharepoint", "slack"]


# ---- Schemas ----

class ConnectRequest(BaseModel):
    provider: str = Field(..., pattern="^(notion|jira|confluence|sharepoint|slack)$")
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
    external_id: str = Field(..., description="Page ID (Notion), issue key (Jira), or channel ID (Slack)")
    title: Optional[str] = None


# ---- OAuth State Helpers ----

def _make_oauth_state(tenant_id: int, user_id: int) -> str:
    """Create a signed state parameter encoding tenant_id and user_id."""
    payload = json.dumps({"t": tenant_id, "u": user_id})
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    combined = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(combined.encode()).decode()


def _verify_oauth_state(state: str) -> tuple[int, int]:
    """Verify state signature and return (tenant_id, user_id)."""
    try:
        decoded = base64.urlsafe_b64decode(state.encode()).decode()
        payload, sig = decoded.rsplit("|", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Bad signature")
        data = json.loads(payload)
        return data["t"], data["u"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or tampered OAuth state parameter")


# ---- Common Endpoints ----

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
    Save an OAuth access token for a provider (manual token flow).
    For Jira: also provide base_url (e.g. https://company.atlassian.net).
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


# ============================================================
# Jira OAuth 2.0 (Atlassian)
# ============================================================

@router.get("/jira/oauth/authorize")
def jira_oauth_authorize(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Return the Atlassian OAuth 2.0 authorization URL."""
    if not settings.JIRA_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Jira OAuth is not configured. Set JIRA_CLIENT_ID and JIRA_CLIENT_SECRET.",
        )
    state = _make_oauth_state(tenant_id, current_user.id)
    redirect_uri = f"{settings.BACKEND_URL}/api/{settings.API_VERSION}/integrations/jira/oauth/callback"
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.JIRA_CLIENT_ID,
        "scope": "read:jira-work read:jira-user offline_access",
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    url = "https://auth.atlassian.com/authorize?" + urlencode(params)
    return {"url": url, "provider": "jira"}


@router.get("/jira/oauth/callback")
async def jira_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Atlassian redirects here after user grants access.
    Exchange the authorization code for tokens, fetch cloud site info, and save.
    Finally redirect browser back to the frontend integrations page.
    """
    tenant_id, user_id = _verify_oauth_state(state)
    redirect_uri = f"{settings.BACKEND_URL}/api/{settings.API_VERSION}/integrations/jira/oauth/callback"

    try:
        # 1. Exchange authorization code for tokens
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.JIRA_CLIENT_ID,
                    "client_secret": settings.JIRA_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/json"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # 2. Get accessible Atlassian cloud sites
        async with httpx.AsyncClient(timeout=10) as client:
            sites_resp = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            sites_resp.raise_for_status()
            sites = sites_resp.json()

        if not sites:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error=no_sites&provider=jira"
            )

        # Use first cloud site
        cloud = sites[0]
        cloud_id = cloud["id"]
        workspace_name = cloud.get("name", "Jira Cloud")
        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"

        # 3. Save to DB
        crud_integration_config.upsert(
            db,
            tenant_id=tenant_id,
            provider="jira",
            created_by_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            workspace_name=workspace_name,
            workspace_id=cloud_id,
            base_url=base_url,
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"Jira OAuth callback HTTP error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error=token_exchange&provider=jira"
        )
    except Exception as e:
        logger.error(f"Jira OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error=unknown&provider=jira"
        )

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_success=jira&workspace={workspace_name}"
    )


# ============================================================
# Slack OAuth 2.0
# ============================================================

@router.get("/slack/oauth/authorize")
def slack_oauth_authorize(
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """Return the Slack OAuth 2.0 authorization URL."""
    if not settings.SLACK_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Slack OAuth is not configured. Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET.",
        )
    state = _make_oauth_state(tenant_id, current_user.id)
    redirect_uri = f"{settings.BACKEND_URL}/api/{settings.API_VERSION}/integrations/slack/oauth/callback"
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "scope": "channels:read,channels:history,chat:write,files:read,users:read",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    url = "https://slack.com/oauth/v2/authorize?" + urlencode(params)
    return {"url": url, "provider": "slack"}


@router.get("/slack/oauth/callback")
async def slack_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> Any:
    """
    Slack redirects here after user grants access.
    Exchange the authorization code for a bot token and save.
    """
    tenant_id, user_id = _verify_oauth_state(state)
    redirect_uri = f"{settings.BACKEND_URL}/api/{settings.API_VERSION}/integrations/slack/oauth/callback"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.SLACK_CLIENT_ID,
                    "client_secret": settings.SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

        if not token_data.get("ok"):
            error = token_data.get("error", "unknown")
            logger.error(f"Slack OAuth error: {error}")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error={error}&provider=slack"
            )

        access_token = token_data["access_token"]
        team = token_data.get("team", {})
        workspace_id = team.get("id", "")
        workspace_name = team.get("name", "Slack Workspace")

        crud_integration_config.upsert(
            db,
            tenant_id=tenant_id,
            provider="slack",
            created_by_id=user_id,
            access_token=access_token,
            workspace_name=workspace_name,
            workspace_id=workspace_id,
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"Slack OAuth callback HTTP error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error=token_exchange&provider=slack"
        )
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_error=unknown&provider=slack"
        )

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard/integrations?oauth_success=slack&workspace={workspace_name}"
    )


# ============================================================
# Provider page / channel browse
# ============================================================

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
    Fetch pages (Notion), issues (Jira), or channels (Slack) from the connected integration.
    Returns a normalized list: [{id, title, url, updated_at}]
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
        elif provider == "slack":
            items = await _slack_list_channels(config.access_token, query=query, limit=limit)
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
    Fetch the full content of a Notion page, Jira issue, or Slack channel
    and store it as a DokuDoc Document (raw_text + filename set, status='uploaded').
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
        elif provider == "slack":
            content, title = await _slack_fetch_channel_history(
                config.access_token, payload.external_id, channel_name=payload.title
            )
        else:
            raise HTTPException(status_code=400, detail=f"Import not yet supported for {provider}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Provider API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Integration import error ({provider}/{payload.external_id}): {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch content: {str(e)}")

    final_title = payload.title or title or f"{provider}_{payload.external_id}"

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
# Provider helpers — Notion
# ============================================================

async def _notion_list_pages(token: str, query: Optional[str], limit: int) -> list[dict]:
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
        title = _extract_notion_title(props) or result.get("id", "Untitled")
        items.append({
            "id": result["id"],
            "title": title,
            "url": result.get("url", ""),
            "updated_at": result.get("last_edited_time", ""),
        })
    return items


async def _notion_fetch_page(token: str, page_id: str) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        page_resp = await client.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers)
        page_resp.raise_for_status()
        page_data = page_resp.json()
        title = _extract_notion_title(page_data.get("properties", {}))

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
# Provider helpers — Jira (works with both Bearer token and OAuth)
# ============================================================

async def _jira_list_issues(
    token: str, base_url: str, query: Optional[str], limit: int
) -> list[dict]:
    """Search Jira issues using JQL. Works with both API token and OAuth access token."""
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
        return "".join(
            f"- {''.join(_adf_to_text(c, depth+1) for c in item.get('content', []))}\n"
            for item in content
        )
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
    return "".join(_adf_to_text(c, depth) for c in content)


# ============================================================
# Provider helpers — Slack
# ============================================================

async def _slack_list_channels(token: str, query: Optional[str], limit: int) -> list[dict]:
    """List Slack public channels the bot has access to."""
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "exclude_archived": "true",
        "types": "public_channel",
        "limit": min(limit, 200),
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://slack.com/api/conversations.list",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise Exception(f"Slack API error: {data.get('error', 'unknown')}")

    channels = data.get("channels", [])
    if query:
        q = query.lower()
        channels = [c for c in channels if q in c.get("name", "").lower()]

    items = []
    for ch in channels[:limit]:
        items.append({
            "id": ch["id"],
            "title": f"#{ch.get('name', ch['id'])}",
            "url": "",
            "updated_at": "",
            "member_count": ch.get("num_members", 0),
            "topic": ch.get("topic", {}).get("value", ""),
        })
    return items


async def _slack_fetch_channel_history(
    token: str, channel_id: str, channel_name: Optional[str] = None, limit: int = 100
) -> tuple[str, str]:
    """Fetch recent messages from a Slack channel and format as markdown."""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://slack.com/api/conversations.history",
            headers=headers,
            params={"channel": channel_id, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise Exception(f"Slack API error: {data.get('error', 'unknown')}")

    display_name = channel_name or f"#{channel_id}"
    lines = [f"# Slack Channel: {display_name}", f"\n*Imported {limit} most recent messages*\n", "---\n"]

    for msg in reversed(data.get("messages", [])):
        if msg.get("type") != "message" or msg.get("subtype"):
            continue
        ts = msg.get("ts", "")
        user = msg.get("user", "unknown")
        text = msg.get("text", "").strip()
        if not text:
            continue
        # Convert Slack timestamp to readable date
        try:
            from datetime import datetime as dt
            readable_ts = dt.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            readable_ts = ts
        lines.append(f"**{user}** _{readable_ts}_\n{text}\n")

    return "\n".join(lines), display_name
