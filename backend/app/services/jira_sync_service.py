"""
JiraSyncService — fetches and syncs JIRA project data into DokuDoc.
Sprint 9: Deep JIRA integration.

Responsibilities:
  1. Fetch epics / stories / tasks / bugs from Jira REST API v3
  2. Upsert them as JiraItem records (tenant-scoped, no hardcoding)
  3. Ingest high-value items into the Brain:
       - Creates OntologyConcept (source_type="jira") per epic/story
       - Creates RequirementTrace per acceptance criterion
       - Queues embedding generation
  4. Update IntegrationConfig.last_synced_at

Multi-tenancy: all operations scoped by tenant_id and integration_config_id.
Token refresh: caller must ensure access_token is valid (refresh handled externally).
"""
import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.logging import LoggerMixin
from app.crud.crud_jira_item import crud_jira_item
from app.crud.crud_integration_config import crud_integration_config
from app.models.jira_item import JiraItem


_JIRA_ISSUE_TYPES_MAP = {
    "epic": "epic",
    "story": "story",
    "task": "task",
    "bug": "bug",
    "sub-task": "sub_task",
    "subtask": "sub_task",
    "feature": "feature",
}


class JiraSyncService(LoggerMixin):
    """Orchestrates a full or incremental JIRA project sync for a tenant."""

    # Maximum issues fetched per project per sync run (safety cap)
    MAX_ISSUES = 500

    async def sync_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_config_id: int,
    ) -> dict:
        """
        Run a full sync for the given Jira integration config.
        Returns a summary dict: {synced, ingested, errors}.
        """
        config = crud_integration_config.get_by_id(db, config_id=integration_config_id, tenant_id=tenant_id)
        if not config or not config.is_active:
            return {"error": "Integration config not found or inactive"}

        sync_config = config.sync_config or {}
        project_keys: list[str] = sync_config.get("project_keys", [])
        if not project_keys:
            return {"error": "No project_keys configured. Please set project keys in Integration settings."}

        ac_field = (
            sync_config.get("custom_field_mappings", {}).get("acceptance_criteria")
            or "customfield_10100"  # Atlassian default AC field
        )
        include_subtasks = sync_config.get("include_subtasks", False)
        base_url = config.base_url or ""
        token = config.access_token or ""

        stats = {"synced": 0, "ingested": 0, "errors": []}

        for project_key in project_keys:
            try:
                issues = await self._fetch_project_issues(
                    token=token,
                    base_url=base_url,
                    project_key=project_key,
                    ac_field=ac_field,
                    include_subtasks=include_subtasks,
                )
                for issue_data in issues:
                    item = crud_jira_item.upsert_by_key(
                        db,
                        tenant_id=tenant_id,
                        integration_config_id=integration_config_id,
                        external_key=issue_data["external_key"],
                        data=issue_data,
                    )
                    stats["synced"] += 1

                    # Ingest epics and stories with AC into the brain
                    if item.item_type in ("epic", "story", "feature") or item.acceptance_criteria:
                        ingested = self._ingest_to_brain(db, tenant_id=tenant_id, item=item)
                        if ingested:
                            stats["ingested"] += 1

            except Exception as e:
                self.logger.error(f"Jira sync failed for project {project_key} (tenant {tenant_id}): {e}")
                stats["errors"].append(f"{project_key}: {str(e)[:200]}")

        # Update last_synced_at
        crud_integration_config.mark_synced(db, config_id=integration_config_id, tenant_id=tenant_id)

        self.logger.info(
            f"Jira sync complete — tenant={tenant_id} "
            f"synced={stats['synced']} ingested={stats['ingested']} errors={len(stats['errors'])}"
        )
        return stats

    # ------------------------------------------------------------------ #
    # Jira API helpers
    # ------------------------------------------------------------------ #

    async def _fetch_project_issues(
        self,
        *,
        token: str,
        base_url: str,
        project_key: str,
        ac_field: str,
        include_subtasks: bool,
    ) -> list[dict]:
        """Fetch all issues for a Jira project using JQL pagination."""
        fields = [
            "summary", "description", "issuetype", "status", "priority",
            "assignee", "reporter", "labels", "components",
            "parent", "customfield_10014",  # Epic Link
            "customfield_10020",             # Sprint
            ac_field,
        ]
        jql = f'project = "{project_key}" ORDER BY created DESC'
        if not include_subtasks:
            jql = f'project = "{project_key}" AND issuetype != Sub-task ORDER BY created DESC'

        issues: list[dict] = []
        start_at = 0
        page_size = 50

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            while len(issues) < self.MAX_ISSUES:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": page_size,
                    "fields": ",".join(fields),
                }
                resp = await client.get(
                    f"{base_url.rstrip('/')}/rest/api/3/search",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("issues", [])
                if not batch:
                    break

                for raw in batch:
                    parsed = self._parse_issue(raw, ac_field=ac_field)
                    if parsed:
                        issues.append(parsed)

                total = data.get("total", 0)
                start_at += len(batch)
                if start_at >= total or start_at >= self.MAX_ISSUES:
                    break

        return issues

    def _parse_issue(self, raw: dict, ac_field: str) -> Optional[dict]:
        """Parse a raw Jira issue API response into our normalized dict."""
        try:
            key = raw.get("key", "")
            fields = raw.get("fields", {})
            if not key:
                return None

            issue_type_raw = (fields.get("issuetype") or {}).get("name", "task").lower()
            item_type = _JIRA_ISSUE_TYPES_MAP.get(issue_type_raw, "task")

            # Extract description text from ADF format
            desc_raw = fields.get("description") or {}
            description = _adf_to_text(desc_raw) if isinstance(desc_raw, dict) else str(desc_raw or "")

            # Extract acceptance criteria from the configured custom field
            ac_raw = fields.get(ac_field)
            acceptance_criteria = self._extract_acceptance_criteria(ac_raw)

            # Sprint name from customfield_10020 (array of sprint objects)
            sprint_name = None
            sprint_field = fields.get("customfield_10020")
            if sprint_field and isinstance(sprint_field, list) and sprint_field:
                sprint_obj = sprint_field[-1]  # last = current sprint
                sprint_name = sprint_obj.get("name") if isinstance(sprint_obj, dict) else None

            # Epic link: customfield_10014 (classic) or parent.key for next-gen
            epic_key = fields.get("customfield_10014") or None
            parent = fields.get("parent") or {}
            parent_key = parent.get("key") or None
            if not epic_key and parent_key:
                # Determine if parent is an epic
                parent_type = (parent.get("fields", {}).get("issuetype") or {}).get("name", "").lower()
                if parent_type == "epic":
                    epic_key = parent_key

            # Project key from issue key (e.g. "PROJ-123" → "PROJ")
            project_key = key.rsplit("-", 1)[0] if "-" in key else None

            return {
                "external_key": key,
                "project_key": project_key,
                "item_type": item_type,
                "title": fields.get("summary", key),
                "description": description[:5000] if description else None,
                "acceptance_criteria": acceptance_criteria,
                "status": (fields.get("status") or {}).get("name"),
                "priority": (fields.get("priority") or {}).get("name"),
                "assignee": (fields.get("assignee") or {}).get("displayName"),
                "reporter": (fields.get("reporter") or {}).get("displayName"),
                "epic_key": epic_key,
                "parent_key": parent_key,
                "sprint_name": sprint_name,
                "labels": fields.get("labels") or [],
                "components": [c.get("name") for c in (fields.get("components") or [])],
                "raw_data": {
                    "key": key,
                    "type": issue_type_raw,
                    "fields_keys": list(fields.keys()),
                },
            }
        except Exception as e:
            self.logger.warning(f"Failed to parse Jira issue {raw.get('key', '?')}: {e}")
            return None

    def _extract_acceptance_criteria(self, ac_raw) -> Optional[list]:
        """
        Extract acceptance criteria from a Jira custom field value.
        Handles: ADF document, plain string, list of strings.
        Returns a list of criterion strings, or None if empty.
        """
        if ac_raw is None:
            return None

        # ADF format (dict with "content" key)
        if isinstance(ac_raw, dict):
            text = _adf_to_text(ac_raw)
            if not text.strip():
                return None
            return _split_criteria(text)

        # Plain string
        if isinstance(ac_raw, str):
            if not ac_raw.strip():
                return None
            return _split_criteria(ac_raw)

        # Already a list
        if isinstance(ac_raw, list):
            result = []
            for item in ac_raw:
                if isinstance(item, str) and item.strip():
                    result.append(item.strip())
                elif isinstance(item, dict):
                    text = _adf_to_text(item)
                    if text.strip():
                        result.extend(_split_criteria(text))
            return result if result else None

        return None

    # ------------------------------------------------------------------ #
    # Brain ingestion
    # ------------------------------------------------------------------ #

    def _ingest_to_brain(self, db: Session, *, tenant_id: int, item: JiraItem) -> bool:
        """
        Create/update OntologyConcept and RequirementTraces from a JiraItem.
        Links the concept back to the JiraItem.
        Returns True if a concept was created/updated.
        """
        try:
            from app.models.ontology_concept import OntologyConcept
            from app.models.ontology_concept import ConceptType

            # Map Jira item type to concept type
            concept_type_map = {
                "epic": "FEATURE",
                "feature": "FEATURE",
                "story": "PROCESS",
                "task": "PROCESS",
                "bug": "PROCESS",
                "sub_task": "PROCESS",
            }
            concept_type = concept_type_map.get(item.item_type, "FEATURE")

            # Build description text
            desc_parts = []
            if item.description:
                desc_parts.append(item.description[:500])
            if item.acceptance_criteria:
                ac_text = "\n".join(f"- {c}" for c in item.acceptance_criteria[:10])
                desc_parts.append(f"Acceptance Criteria:\n{ac_text}")
            description = "\n\n".join(desc_parts) if desc_parts else item.title

            # Check for existing concept linked to this Jira item
            existing_concept = None
            if item.ontology_concept_id:
                existing_concept = db.query(OntologyConcept).filter(
                    OntologyConcept.id == item.ontology_concept_id,
                    OntologyConcept.tenant_id == tenant_id,
                ).first()

            if existing_concept:
                existing_concept.description = description
                existing_concept.name = item.title[:200]
                db.commit()
                concept = existing_concept
            else:
                # Check for existing concept with same name + source_type=jira
                concept = db.query(OntologyConcept).filter(
                    OntologyConcept.tenant_id == tenant_id,
                    OntologyConcept.name == item.title[:200],
                    OntologyConcept.source_type == "jira",
                ).first()

                if not concept:
                    concept = OntologyConcept(
                        tenant_id=tenant_id,
                        name=item.title[:200],
                        concept_type=concept_type,
                        description=description,
                        source_type="jira",
                        confidence_score=0.90,
                        is_active=True,
                    )
                    db.add(concept)
                    db.flush()

            # Link concept back to JiraItem
            if concept.id and item.ontology_concept_id != concept.id:
                crud_jira_item.set_ontology_concept(db, jira_item_id=item.id, concept_id=concept.id)

            # Create RequirementTrace entries for each acceptance criterion
            if item.acceptance_criteria:
                self._upsert_requirement_traces(
                    db,
                    tenant_id=tenant_id,
                    jira_item=item,
                    concept_id=concept.id,
                )

            db.commit()
            return True

        except Exception as e:
            self.logger.warning(f"Brain ingestion failed for {item.external_key}: {e}")
            db.rollback()
            return False

    def _upsert_requirement_traces(
        self,
        db: Session,
        *,
        tenant_id: int,
        jira_item: JiraItem,
        concept_id: int,
    ) -> None:
        """Create RequirementTrace rows for each acceptance criterion string."""
        try:
            from app.models.requirement_trace import RequirementTrace

            for criterion in (jira_item.acceptance_criteria or []):
                if not criterion or not criterion.strip():
                    continue

                # Check for existing trace with same source and text to avoid duplicates
                existing = db.query(RequirementTrace).filter(
                    RequirementTrace.tenant_id == tenant_id,
                    RequirementTrace.requirement_text == criterion[:1000],
                    RequirementTrace.source == "jira",
                ).first()

                if not existing:
                    trace = RequirementTrace(
                        tenant_id=tenant_id,
                        requirement_text=criterion[:1000],
                        source="jira",
                        external_key=jira_item.external_key,
                        coverage_status="not_covered",
                        linked_concept_ids=[concept_id],
                    )
                    db.add(trace)
        except Exception as e:
            self.logger.warning(f"RequirementTrace upsert failed for {jira_item.external_key}: {e}")

    async def fetch_projects(self, *, token: str, base_url: str) -> list[dict]:
        """Return list of accessible Jira projects: [{key, name, id}]."""
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url.rstrip('/')}/rest/api/3/project",
                headers=headers,
                params={"maxResults": 100},
            )
            resp.raise_for_status()
            projects = resp.json()
        return [
            {"key": p.get("key", ""), "name": p.get("name", ""), "id": p.get("id", "")}
            for p in (projects if isinstance(projects, list) else projects.get("values", []))
        ]

    async def fetch_epics(self, *, token: str, base_url: str, project_key: str) -> list[dict]:
        """Return epics for a Jira project."""
        jql = f'project = "{project_key}" AND issuetype = Epic ORDER BY created DESC'
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url.rstrip('/')}/rest/api/3/search",
                headers=headers,
                params={"jql": jql, "maxResults": 100, "fields": "summary,status"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {
                "key": i["key"],
                "title": (i.get("fields") or {}).get("summary", i["key"]),
                "status": ((i.get("fields") or {}).get("status") or {}).get("name"),
            }
            for i in data.get("issues", [])
        ]

    async def fetch_sprints(self, *, token: str, base_url: str, project_key: str) -> list[dict]:
        """Return active/closed sprints for a project via Agile API."""
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        # First get boards for the project
        boards: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{base_url.rstrip('/')}/rest/agile/1.0/board",
                    headers=headers,
                    params={"projectKeyOrId": project_key, "maxResults": 10},
                )
                resp.raise_for_status()
                boards = resp.json().get("values", [])
        except Exception:
            return []

        sprints: list[dict] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for board in boards[:2]:  # limit to first 2 boards
                try:
                    resp = await client.get(
                        f"{base_url.rstrip('/')}/rest/agile/1.0/board/{board['id']}/sprint",
                        headers=headers,
                        params={"state": "active,closed", "maxResults": 20},
                    )
                    resp.raise_for_status()
                    for s in resp.json().get("values", []):
                        sprints.append({
                            "id": s.get("id"),
                            "name": s.get("name"),
                            "state": s.get("state"),
                        })
                except Exception:
                    continue

        return sprints

    async def create_issue(
        self,
        *,
        token: str,
        base_url: str,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        labels: list | None = None,
        epic_key: str | None = None,
        assignee_account_id: str | None = None,
    ) -> dict:
        """
        P5B-03: Creates a single Jira issue from a DokyDoc mismatch.
        Returns: {"key": "PROJ-123", "id": "10001", "url": "https://..."}
        """
        import httpx as _httpx

        payload: dict = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "labels": labels or ["dokydoc"],
            }
        }
        if epic_key:
            payload["fields"]["parent"] = {"key": epic_key}
        if assignee_account_id:
            payload["fields"]["assignee"] = {"accountId": assignee_account_id}

        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/rest/api/3/issue",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        issue_key = data["key"]
        # Build browse URL from base_url
        browse_base = base_url.split("/rest/")[0] if "/rest/" in base_url else base_url
        return {
            "key": issue_key,
            "id": data["id"],
            "url": f"{browse_base}/browse/{issue_key}",
        }


# ------------------------------------------------------------------ #
# Module-level helpers
# ------------------------------------------------------------------ #

def _adf_to_text(doc: dict, depth: int = 0) -> str:
    """Minimal Atlassian Document Format → plain text (reused from integrations.py pattern)."""
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
            f"- {''.join(_adf_to_text(c, depth + 1) for c in item.get('content', []))}\n"
            for item in content
        )
    if node_type == "orderedList":
        return "\n".join(
            f"{i}. {''.join(_adf_to_text(c, depth + 1) for c in item.get('content', []))}"
            for i, item in enumerate(content, 1)
        ) + "\n"
    if node_type == "heading":
        level = doc.get("attrs", {}).get("level", 2)
        return "#" * level + " " + "".join(_adf_to_text(c, depth) for c in content) + "\n"
    if node_type == "codeBlock":
        lang = doc.get("attrs", {}).get("language", "")
        inner = "".join(_adf_to_text(c, depth) for c in content)
        return f"```{lang}\n{inner}\n```\n"
    return "".join(_adf_to_text(c, depth) for c in content)


def _split_criteria(text: str) -> list[str]:
    """
    Split a block of text into individual acceptance criterion strings.
    Handles bullet lists, numbered lists, and plain paragraphs.
    """
    # Try splitting on bullet/numbered list items
    lines = text.strip().split("\n")
    criteria: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                criteria.append(" ".join(current).strip())
                current = []
            continue
        # Detect list item start
        is_item = bool(re.match(r"^[-*•]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped))
        if is_item:
            if current:
                criteria.append(" ".join(current).strip())
                current = []
            # Strip the bullet/number prefix
            cleaned = re.sub(r"^[-*•]\s+|^\d+[.)]\s+", "", stripped)
            current.append(cleaned)
        else:
            current.append(stripped)

    if current:
        criteria.append(" ".join(current).strip())

    # Filter out empty or very short entries
    return [c for c in criteria if len(c) > 5]


jira_sync_service = JiraSyncService()
