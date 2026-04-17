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
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from pydantic import BaseModel
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

            # Post analysis summary as PR comment (Sprint 5)
            pr_comment_posted = False
            if pr_data.get("pr_number"):
                try:
                    from app.services.pr_comment_service import pr_comment_service
                    summary = pr_comment_service.build_analysis_summary(
                        db=db,
                        tenant_id=repo.tenant_id,
                        repo_id=repo.id,
                        changed_files=[],  # All files on merged branch
                        branch=pr_data["head_branch"],
                    )
                    result = pr_comment_service.post_pr_comment_sync(
                        repo_url=pr_data["repo_url"],
                        pr_number=pr_data["pr_number"],
                        body=summary,
                    )
                    pr_comment_posted = result is not None
                except Exception as e:
                    logger.warning(f"Webhook: PR comment failed (non-fatal): {e}")

            return {
                "status": "accepted",
                "action": "promote_preview",
                "repo": repo.name,
                "branch": pr_data["head_branch"],
                "pr_comment_posted": pr_comment_posted,
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


@router.post("/pr-comment")
def post_pr_analysis_comment(
    *,
    repo_id: int,
    pr_number: int,
    branch: str = "main",
    db: Session = Depends(get_db),
):
    """
    Manually trigger a PR analysis comment (Sprint 5).
    Useful for testing or retroactively posting analysis summaries.
    """
    repo = db.query(crud.repository.model).filter(
        crud.repository.model.id == repo_id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.services.pr_comment_service import pr_comment_service

    summary = pr_comment_service.build_analysis_summary(
        db=db,
        tenant_id=repo.tenant_id,
        repo_id=repo.id,
        changed_files=[],
        branch=branch,
    )

    result = pr_comment_service.post_pr_comment_sync(
        repo_url=repo.url,
        pr_number=pr_number,
        body=summary,
    )

    return {
        "status": "posted" if result else "skipped",
        "repo": repo.name,
        "pr_number": pr_number,
        "comment_id": result.get("id") if result else None,
        "summary_preview": summary[:500],
    }


# ── P5C-06: CI Test Result Webhook ───────────────────────────────────────────

class CITestResult(BaseModel):
    test_name: str
    status: str                              # "pass" | "fail" | "error"
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    atom_id_hint: Optional[str] = None      # e.g. "REQ-004"
    duration_ms: Optional[float] = None


class CIWebhookPayload(BaseModel):
    document_id: int
    run_id: str
    commit_sha: Optional[str] = None
    test_results: List[CITestResult]


def _verify_ci_hmac(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Verify X-DokyDoc-Signature: sha256=<hmac> header."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    received = signature_header[7:]
    return hmac.compare_digest(expected, received)


@router.post("/ci/test-results", status_code=202)
async def receive_ci_test_results(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """
    P5C-06: Receive CI pipeline test results and auto-create mismatches for failures.
    Authentication: HMAC-SHA256 signature in X-DokyDoc-Signature header.
    Auto-closes runtime_test_failure mismatches for tests that now pass.
    """
    from app.models.document import Document
    from app.models.ci_webhook_config import CIWebhookConfig
    from app.models.requirement_atom import RequirementAtom
    from app.models.mismatch import Mismatch
    from app.models.code_component import CodeComponent

    raw_body = await request.body()
    try:
        payload_data = await request.json()
        payload = CIWebhookPayload(**payload_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")

    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    config = db.query(CIWebhookConfig).filter_by(tenant_id=doc.tenant_id).first()
    if not config:
        raise HTTPException(status_code=401, detail="CI webhook not configured for this tenant")

    sig_header = request.headers.get("X-DokyDoc-Signature", "")
    if not _verify_ci_hmac(raw_body, sig_header, config.webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    failures = [r for r in payload.test_results if r.status in ("fail", "error")]
    created_mismatch_ids = []

    for result in failures:
        atom = None
        if result.atom_id_hint:
            atom = db.query(RequirementAtom).filter(
                RequirementAtom.document_id == payload.document_id,
                RequirementAtom.tenant_id == doc.tenant_id,
                RequirementAtom.atom_id == result.atom_id_hint,
            ).first()

        # Dedup: skip if same run_id + test_name already created a mismatch
        existing = db.query(Mismatch).filter(
            Mismatch.document_id == payload.document_id,
            Mismatch.tenant_id == doc.tenant_id,
            Mismatch.details["ci_run_id"].astext == payload.run_id,
            Mismatch.details["test_name"].astext == result.test_name,
        ).first()
        if existing:
            continue

        # Find or create synthetic CI code component
        ci_component = db.query(CodeComponent).filter_by(
            tenant_id=doc.tenant_id,
            name="__ci_pipeline__",
        ).first()
        if not ci_component:
            ci_component = CodeComponent(
                tenant_id=doc.tenant_id,
                name="CI Pipeline",
                component_type="ci",
                location="__ci_pipeline__",
            )
            db.add(ci_component)
            db.flush()

        severity = "high" if (atom and getattr(atom, "criticality", None) in ("critical", "high")) else "medium"

        mismatch = Mismatch(
            tenant_id=doc.tenant_id,
            document_id=payload.document_id,
            code_component_id=ci_component.id,
            requirement_atom_id=atom.id if atom else None,
            owner_id=doc.owner_id,
            mismatch_type="runtime_test_failure",
            severity=severity,
            status="open",
            direction="forward",
            description=(
                f"CI test failed: {result.test_name}. "
                f"{result.error_message or 'No error message provided.'}"
            ),
            details={
                "ci_run_id": payload.run_id,
                "commit_sha": payload.commit_sha,
                "test_name": result.test_name,
                "test_file": result.file_path,
                "error_message": result.error_message,
                "duration_ms": result.duration_ms,
                "atom_id_hint": result.atom_id_hint,
            },
        )
        db.add(mismatch)
        db.flush()
        created_mismatch_ids.append(mismatch.id)

    # Auto-close previously-open runtime_test_failure mismatches for tests that now pass
    passing_test_names = {r.test_name for r in payload.test_results if r.status == "pass"}
    if passing_test_names:
        stale = db.query(Mismatch).filter(
            Mismatch.document_id == payload.document_id,
            Mismatch.tenant_id == doc.tenant_id,
            Mismatch.mismatch_type == "runtime_test_failure",
            Mismatch.status == "open",
        ).all()
        for m in stale:
            if m.details and m.details.get("test_name") in passing_test_names:
                m.status = "auto_closed"

    db.commit()

    return {
        "received": len(payload.test_results),
        "failures": len(failures),
        "mismatches_created": len(created_mismatch_ids),
        "mismatch_ids": created_mismatch_ids,
    }
