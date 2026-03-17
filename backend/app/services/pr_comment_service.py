"""
PR Comment Service — Post Analysis Summaries to GitHub PRs

Sprint 5 Remaining: Integrates DokyDoc analysis results into pull request
comments so developers see validation mismatches and concept changes
directly in their PR workflow.

Supports:
  - GitHub (via REST API with personal access token or GitHub App token)

Flow:
  1. Webhook receives PR merge event
  2. Analysis runs on changed files (existing)
  3. After analysis, this service posts a summary comment to the PR
  4. Comment includes: new/changed concepts, validation mismatches, coverage
"""

import httpx
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app import crud
from app.core.config import settings
from app.core.logging import LoggerMixin
from app.models.concept_mapping import ConceptMapping


class PRCommentService(LoggerMixin):
    """Post analysis summaries as comments on GitHub pull requests."""

    GITHUB_API = "https://api.github.com"

    def __init__(self):
        super().__init__()
        self.logger.info("PRCommentService initialized")

    def _get_github_headers(self) -> Optional[Dict[str, str]]:
        """Get GitHub API headers if token is configured."""
        token = getattr(settings, "GITHUB_TOKEN", None)
        if not token:
            return None
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _parse_repo_from_url(self, repo_url: str) -> Optional[str]:
        """Extract owner/repo from a GitHub URL."""
        url = repo_url.rstrip("/").rstrip(".git")
        if "github.com" not in url:
            return None
        parts = url.split("github.com/")
        if len(parts) < 2:
            return None
        return parts[1]

    def build_analysis_summary(
        self, db: Session, *, tenant_id: int, repo_id: int,
        changed_files: List[str], branch: str,
    ) -> str:
        """
        Build a markdown summary of the analysis results for a PR comment.
        """
        from app.models.code_component import CodeComponent
        from app.services.mapping_service import mapping_service

        # Get analysis results for changed files
        components = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.repository_id == repo_id,
            CodeComponent.location.in_(changed_files),
        ).all()

        analyzed_count = sum(1 for c in components if c.analysis_status == "completed")
        failed_count = sum(1 for c in components if c.analysis_status == "failed")

        # Get concept counts
        total_concepts = 0
        concept_types: Dict[str, int] = {}
        for comp in components:
            if comp.structured_analysis and isinstance(comp.structured_analysis, dict):
                concepts = comp.structured_analysis.get("concepts", [])
                total_concepts += len(concepts)
                for c in concepts:
                    t = c.get("type", "unknown")
                    concept_types[t] = concept_types.get(t, 0) + 1

        # Get current mismatches
        mismatches = mapping_service.get_mismatches(db=db, tenant_id=tenant_id)
        gap_count = mismatches.get("total_gaps", 0)
        undoc_count = mismatches.get("total_undocumented", 0)
        contradiction_count = mismatches.get("total_contradictions", 0)

        # Build markdown
        lines = [
            "## DokyDoc Analysis Summary",
            "",
            f"**Branch:** `{branch}`",
            f"**Files analyzed:** {analyzed_count}/{len(changed_files)}",
            "",
        ]

        if failed_count > 0:
            lines.append(f"> :warning: {failed_count} file(s) failed analysis")
            lines.append("")

        # Concepts discovered
        if total_concepts > 0:
            lines.append("### Concepts Discovered")
            lines.append("")
            lines.append(f"Found **{total_concepts}** concepts across analyzed files:")
            lines.append("")
            for ctype, count in sorted(concept_types.items(), key=lambda x: -x[1]):
                lines.append(f"- `{ctype}`: {count}")
            lines.append("")

        # Validation status
        has_issues = gap_count > 0 or undoc_count > 0 or contradiction_count > 0
        if has_issues:
            lines.append("### Validation Status")
            lines.append("")
            if gap_count > 0:
                lines.append(f"- :red_circle: **{gap_count}** document requirements with no code implementation (gaps)")
            if undoc_count > 0:
                lines.append(f"- :yellow_circle: **{undoc_count}** code features with no documentation (undocumented)")
            if contradiction_count > 0:
                lines.append(f"- :no_entry: **{contradiction_count}** contradictions between docs and code")
            lines.append("")
        else:
            lines.append("### Validation Status")
            lines.append("")
            lines.append(":white_check_mark: No validation issues detected.")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by [DokyDoc](https://dokydoc.ai) — AI-powered document governance*")

        return "\n".join(lines)

    async def post_pr_comment(
        self, *, repo_url: str, pr_number: int, body: str,
    ) -> Optional[Dict]:
        """Post a comment to a GitHub pull request."""
        headers = self._get_github_headers()
        if not headers:
            self.logger.info("GitHub token not configured — skipping PR comment")
            return None

        repo_path = self._parse_repo_from_url(repo_url)
        if not repo_path:
            self.logger.warning(f"Cannot parse GitHub repo from URL: {repo_url}")
            return None

        url = f"{self.GITHUB_API}/repos/{repo_path}/issues/{pr_number}/comments"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json={"body": body})
                if response.status_code == 201:
                    self.logger.info(f"Posted analysis comment to PR #{pr_number} on {repo_path}")
                    return response.json()
                else:
                    self.logger.warning(
                        f"Failed to post PR comment: {response.status_code} — {response.text[:200]}"
                    )
                    return None
        except Exception as e:
            self.logger.error(f"Error posting PR comment: {e}")
            return None

    def post_pr_comment_sync(
        self, *, repo_url: str, pr_number: int, body: str,
    ) -> Optional[Dict]:
        """Synchronous wrapper for posting PR comments (for use in Celery tasks)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In async context already — create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.post_pr_comment(repo_url=repo_url, pr_number=pr_number, body=body)
                    )
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(
                    self.post_pr_comment(repo_url=repo_url, pr_number=pr_number, body=body)
                )
        except Exception:
            return asyncio.run(
                self.post_pr_comment(repo_url=repo_url, pr_number=pr_number, body=body)
            )


# Global instance
pr_comment_service = PRCommentService()
