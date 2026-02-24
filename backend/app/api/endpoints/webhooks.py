"""
Git Webhook Endpoint (ADHOC-09)

Receives push events from GitHub/GitLab/Bitbucket and auto-triggers
repository re-analysis for changed files.

Webhook flow:
  1. Git provider sends push event → POST /api/webhooks/git
  2. We extract repo URL, branch, and changed files from the payload
  3. Look up the repo in our database by URL
  4. Dispatch incremental analysis Celery task for changed files

Security:
  - Webhook secret verification (HMAC-SHA256 for GitHub)
  - Only processes repos that are already onboarded
  - Tenant isolation enforced via repo → tenant_id
"""

import hmac
import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app import crud
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("webhooks")

router = APIRouter()


def _verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def _extract_github_push(payload: dict) -> Optional[dict]:
    """Extract relevant data from a GitHub push event payload."""
    repo_url = payload.get("repository", {}).get("clone_url") or \
               payload.get("repository", {}).get("html_url")
    if not repo_url:
        return None

    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

    # Collect all changed files across commits
    changed_files = set()
    for commit in payload.get("commits", []):
        changed_files.update(commit.get("added", []))
        changed_files.update(commit.get("modified", []))
        # Removed files tracked but not analyzed

    return {
        "repo_url": repo_url.rstrip(".git"),
        "branch": branch,
        "changed_files": list(changed_files),
        "pusher": payload.get("pusher", {}).get("name", "unknown"),
        "head_commit": payload.get("head_commit", {}).get("id", "")[:8],
    }


def _extract_gitlab_push(payload: dict) -> Optional[dict]:
    """Extract relevant data from a GitLab push event payload."""
    repo_url = payload.get("repository", {}).get("homepage") or \
               payload.get("project", {}).get("web_url")
    if not repo_url:
        return None

    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

    changed_files = set()
    for commit in payload.get("commits", []):
        changed_files.update(commit.get("added", []))
        changed_files.update(commit.get("modified", []))

    return {
        "repo_url": repo_url,
        "branch": branch,
        "changed_files": list(changed_files),
        "pusher": payload.get("user_name", "unknown"),
        "head_commit": payload.get("after", "")[:8],
    }


def _extract_github_pr(payload: dict) -> Optional[dict]:
    """Extract PR merge data from GitHub pull_request event."""
    pr = payload.get("pull_request", {})
    repo_url = payload.get("repository", {}).get("clone_url") or \
               payload.get("repository", {}).get("html_url")
    if not repo_url:
        return None

    return {
        "repo_url": repo_url.rstrip(".git"),
        "action": payload.get("action"),           # "closed", "opened", etc.
        "merged": pr.get("merged", False),          # True if actually merged
        "head_branch": pr.get("head", {}).get("ref", ""),
        "base_branch": pr.get("base", {}).get("ref", ""),
        "pr_number": pr.get("number"),
    }


def _extract_branch_from_delete(payload: dict) -> Optional[dict]:
    """Extract branch name and repo URL from GitHub delete event."""
    ref_type = payload.get("ref_type", "")
    if ref_type != "branch":
        return None

    repo_url = payload.get("repository", {}).get("clone_url") or \
               payload.get("repository", {}).get("html_url")
    if not repo_url:
        return None

    return {
        "repo_url": repo_url.rstrip(".git"),
        "branch": payload.get("ref", ""),
    }


def _find_repo_by_url(db: Session, repo_url: str):
    """Look up a repo in the database, trying multiple URL variations."""
    url_variations = [
        repo_url,
        repo_url + ".git",
        repo_url.replace("https://", "http://"),
        repo_url.replace("http://", "https://"),
    ]
    for url in url_variations:
        repos = db.query(crud.repository.model).filter(
            crud.repository.model.url == url
        ).all()
        if repos:
            return repos[0]
    return None


@router.post("/git")
async def handle_git_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_gitlab_event: Optional[str] = Header(None),
):
    """
    Receive git webhook and trigger appropriate action.

    Sprint 4 Phase 4: Now handles three event types:
      - push → main branch: permanent analysis / feature branch: preview extraction
      - pull_request → merged: promote preview to permanent SQL
      - delete → branch deleted: clean up Redis preview

    Supports:
      - GitHub (x-github-event: push, pull_request, delete)
      - GitLab (x-gitlab-event: Push Hook)
    """
    raw_body = await request.body()
    payload = await request.json()

    # Detect provider
    if x_github_event:
        provider = "github"
        event_type = x_github_event

        # Verify signature if webhook secret is configured
        webhook_secret = getattr(settings, "WEBHOOK_SECRET", None)
        if webhook_secret and x_hub_signature_256:
            if not _verify_github_signature(raw_body, x_hub_signature_256, webhook_secret):
                logger.warning("GitHub webhook signature verification failed")
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

    elif x_gitlab_event:
        provider = "gitlab"
        event_type = x_gitlab_event
    else:
        provider = "unknown"
        event_type = "push"

    logger.info(f"Webhook received: provider={provider}, event_type={event_type}")

    # ── PULL REQUEST EVENT (Sprint 4 Phase 4) ──
    if event_type == "pull_request" and provider == "github":
        pr_data = _extract_github_pr(payload)
        if not pr_data:
            return {"status": "error", "reason": "invalid_pr_payload"}

        repo = _find_repo_by_url(db, pr_data["repo_url"])
        if not repo:
            logger.info(f"Webhook PR: repo not onboarded — ignoring")
            return {"status": "ignored", "reason": "repo_not_onboarded"}

        # Only process merged PRs
        if pr_data["action"] == "closed" and pr_data["merged"]:
            try:
                from app.tasks.code_analysis_tasks import promote_branch_preview
                promote_branch_preview.delay(
                    repo_id=repo.id,
                    tenant_id=repo.tenant_id,
                    branch=pr_data["head_branch"],
                )
                logger.info(
                    f"Webhook: PR merged — promoting preview for "
                    f"{repo.name}/{pr_data['head_branch']}"
                )
            except Exception as e:
                logger.error(f"Webhook: failed to dispatch promote task: {e}")
                return {"status": "error", "reason": str(e)}

            return {
                "status": "accepted",
                "action": "promote_preview",
                "repo": repo.name,
                "branch": pr_data["head_branch"],
            }

        return {"status": "ignored", "reason": "pr_not_merged"}

    # ── DELETE EVENT (Sprint 4 Phase 4) ──
    if event_type == "delete" and provider == "github":
        delete_data = _extract_branch_from_delete(payload)
        if not delete_data:
            return {"status": "ignored", "reason": "not_a_branch_delete"}

        repo = _find_repo_by_url(db, delete_data["repo_url"])
        if not repo:
            return {"status": "ignored", "reason": "repo_not_onboarded"}

        from app.services.cache_service import cache_service
        deleted = cache_service.delete_branch_preview(
            tenant_id=repo.tenant_id,
            repo_id=repo.id,
            branch=delete_data["branch"],
        )
        logger.info(
            f"Webhook: branch '{delete_data['branch']}' deleted — "
            f"preview cleanup: {'removed' if deleted else 'not found'}"
        )
        return {
            "status": "accepted",
            "action": "cleanup_preview",
            "branch": delete_data["branch"],
            "preview_removed": deleted,
        }

    # ── PUSH EVENT (existing + branch routing) ──
    if event_type not in ("push", "Push Hook"):
        logger.info(f"Ignoring webhook event: {event_type}")
        return {"status": "ignored", "reason": f"event_type={event_type}"}

    # Extract push data
    if provider == "github":
        push_data = _extract_github_push(payload)
    elif provider == "gitlab":
        push_data = _extract_gitlab_push(payload)
    else:
        push_data = _extract_github_push(payload) or _extract_gitlab_push(payload)

    if not push_data:
        logger.warning("Could not extract push data from webhook payload")
        return {"status": "error", "reason": "invalid_payload"}

    logger.info(
        f"Webhook received: {provider} push from {push_data['pusher']} "
        f"to {push_data['branch']} ({len(push_data['changed_files'])} files changed)"
    )

    repo = _find_repo_by_url(db, push_data["repo_url"])

    if not repo:
        logger.info(f"Webhook: repo URL {push_data['repo_url']} not onboarded — ignoring")
        return {"status": "ignored", "reason": "repo_not_onboarded"}

    if not push_data["changed_files"]:
        logger.info(f"Webhook: no changed files in push to {repo.name}")
        return {"status": "ignored", "reason": "no_changed_files"}

    # Dispatch analysis task (branch routing handled inside the task)
    try:
        from app.tasks.code_analysis_tasks import webhook_triggered_analysis
        webhook_triggered_analysis.delay(
            repo_id=repo.id,
            tenant_id=repo.tenant_id,
            changed_files=push_data["changed_files"],
            branch=push_data["branch"],
            commit_hash=push_data["head_commit"],
        )
        logger.info(
            f"Webhook: dispatched analysis for {repo.name} — "
            f"{len(push_data['changed_files'])} files from {push_data['pusher']}"
        )
    except Exception as e:
        logger.error(f"Webhook: failed to dispatch analysis task: {e}")
        return {"status": "error", "reason": str(e)}

    return {
        "status": "accepted",
        "repo": repo.name,
        "branch": push_data["branch"],
        "files_queued": len(push_data["changed_files"]),
    }
