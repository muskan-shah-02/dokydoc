"""
AutoDocsService — AI-powered documentation generation.
Sprint 8 Module 12: Auto Docs.
Sprint 9: Multi-source generation.

Sprint A doc types: component_spec, architecture_diagram, api_summary
Sprint B doc types: brd, test_cases, data_models

Source types:
  "document"   — single document
  "repository" — single repository
  "multi"      — list of {type, id} dicts passed to generate_multi()
"""
import asyncio
from typing import Optional
from sqlalchemy.orm import Session

from app.core.logging import LoggerMixin


# ----- Prompt templates per doc_type -----

_PROMPTS: dict[str, str] = {

    "component_spec": """
You are a senior software architect. Generate a professional **Component Specification** document for the system described below.

The document MUST be in Markdown and include these sections:
## 1. Overview
## 2. Responsibilities
## 3. Interfaces (inputs, outputs, APIs exposed)
## 4. Dependencies
## 5. Configuration & Environment
## 6. Non-functional Requirements (performance, security, scalability)
## 7. Known Limitations

Source context:
{context}
""",

    "architecture_diagram": """
You are a senior software architect. Analyze the system described below and produce an **Architecture Diagram** in **Mermaid** format.

Requirements:
- Use `graph TD` (top-down) or `graph LR` (left-right) layout as appropriate
- Show major services, databases, message queues, external APIs, and their connections
- Add brief edge labels describing the communication type (REST, WebSocket, SQL, etc.)
- After the diagram, add a ## Component Descriptions section with a short paragraph for each major node

Output format:
```mermaid
<diagram here>
```

## Component Descriptions
<descriptions here>

Source context:
{context}
""",

    "api_summary": """
You are a technical writer. Generate a concise **API Summary** document from the context below.

The document MUST be in Markdown and include:
## Endpoints Overview
A table with columns: Method | Path | Auth Required | Description

## Key Request/Response Schemas
Show the most important request bodies and response shapes as JSON examples.

## Authentication
Explain the authentication mechanism used.

## Rate Limiting & Errors
Standard error codes and any rate limit info.

Source context:
{context}
""",

    "brd": """
You are a senior Business Analyst. Generate a formal **Business Requirements Document (BRD)** based on the context below.

The BRD MUST follow this structure in Markdown:
## 1. Executive Summary
## 2. Business Objectives
## 3. Scope (in-scope / out-of-scope)
## 4. Stakeholders
## 5. Functional Requirements
  - List each requirement as: FR-XXX: <description>
## 6. Non-Functional Requirements
  - NFR-XXX: <description>
## 7. Acceptance Criteria
## 8. Assumptions & Constraints
## 9. Glossary

Source context:
{context}
""",

    "test_cases": """
You are a QA architect. Generate comprehensive **Test Cases** from the context below.

Format each test case as:

### TC-XXX: <Test Case Title>
- **Category**: Unit / Integration / E2E / Security / Performance
- **Pre-conditions**: <what must be set up>
- **Steps**: Numbered list of steps
- **Expected Result**: <what should happen>
- **Priority**: High / Medium / Low

Group test cases under ## sections by feature area.

Source context:
{context}
""",

    "data_models": """
You are a database architect. Generate a **Data Model Documentation** from the context below.

Include:
## Entity Relationship Overview
A Mermaid ER diagram (use `erDiagram` syntax).

## Table Definitions
For each entity:
### <EntityName>
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|

## Key Relationships
Describe the most important foreign-key relationships in plain English.

## Indexes & Constraints
List important indexes and unique constraints.

Source context:
{context}
""",
}

_DOC_TYPE_TITLES: dict[str, str] = {
    "component_spec": "Component Specification",
    "architecture_diagram": "Architecture Diagram",
    "api_summary": "API Summary",
    "brd": "Business Requirements Document",
    "test_cases": "Test Cases",
    "data_models": "Data Models",
}


class AutoDocsService(LoggerMixin):
    """Generates structured documentation artifacts using the AI provider."""

    SUPPORTED_TYPES = list(_PROMPTS.keys())

    async def generate(
        self,
        db: Session,
        *,
        doc_type: str,
        source_type: str,
        source_id: int,
        tenant_id: int,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Build context from the source, send to AI, store the result.

        Returns a dict with: title, content, status, metadata.
        Does NOT save to DB — caller saves via crud_generated_doc.
        """
        if doc_type not in _PROMPTS:
            raise ValueError(f"Unknown doc_type '{doc_type}'. Supported: {self.SUPPORTED_TYPES}")

        context_text = self._build_context(db, source_type, source_id, tenant_id)
        source_name = self._get_source_name(db, source_type, source_id, tenant_id)
        title = f"{_DOC_TYPE_TITLES.get(doc_type, doc_type)} — {source_name}"

        prompt = _PROMPTS[doc_type].format(context=context_text[:12000])  # safety cap

        try:
            from app.services.ai.gemini import gemini_service

            response = await gemini_service.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"auto_docs_{doc_type}",
            )
            content = response.text or ""
            tokens = gemini_service.extract_token_usage(response)
            status = "completed"
        except Exception as e:
            self.logger.error(f"AutoDocs generation failed for {doc_type}: {e}")
            content = f"*Generation failed: {e}*"
            tokens = {}
            status = "failed"

        return {
            "title": title,
            "content": content,
            "status": status,
            "source_name": source_name,
            "metadata": {
                "doc_type": doc_type,
                "source_type": source_type,
                "source_id": source_id,
                **tokens,
            },
        }

    def _get_source_name(
        self, db: Session, source_type: str, source_id: int, tenant_id: int
    ) -> str:
        try:
            if source_type == "document":
                from app.models.document import Document

                doc = db.query(Document).filter(
                    Document.id == source_id, Document.tenant_id == tenant_id
                ).first()
                return doc.filename if doc else f"Document #{source_id}"
            elif source_type == "repository":
                from app.models.repository import Repository

                repo = db.query(Repository).filter(
                    Repository.id == source_id, Repository.tenant_id == tenant_id
                ).first()
                return repo.name if repo else f"Repository #{source_id}"
        except Exception:
            pass
        return f"{source_type} #{source_id}"

    def _build_context(
        self, db: Session, source_type: str, source_id: int, tenant_id: int
    ) -> str:
        """Assemble a rich text context block from the source's analysis data."""
        parts = []

        try:
            if source_type == "document":
                parts.extend(self._context_from_document(db, source_id, tenant_id))
            elif source_type == "repository":
                parts.extend(self._context_from_repository(db, source_id, tenant_id))
        except Exception as e:
            self.logger.warning(f"Context assembly partial failure: {e}")
            parts.append(f"[Context assembly error: {e}]")

        return "\n\n".join(parts) if parts else "No analysis data available yet."

    def _context_from_document(
        self, db: Session, doc_id: int, tenant_id: int
    ) -> list[str]:
        parts = []

        # Raw text
        from app.models.document import Document

        doc = db.query(Document).filter(
            Document.id == doc_id, Document.tenant_id == tenant_id
        ).first()
        if doc:
            parts.append(f"DOCUMENT: {doc.filename}")
            if doc.raw_text:
                parts.append(f"CONTENT (first 4000 chars):\n{doc.raw_text[:4000]}")

        # Consolidated analysis
        from app.models.consolidated_analysis import ConsolidatedAnalysis

        ca = (
            db.query(ConsolidatedAnalysis)
            .filter(
                ConsolidatedAnalysis.document_id == doc_id,
                ConsolidatedAnalysis.tenant_id == tenant_id,
            )
            .order_by(ConsolidatedAnalysis.created_at.desc())
            .first()
        )
        if ca and ca.structured_data:
            import json
            parts.append(f"ANALYSIS:\n{json.dumps(ca.structured_data, indent=2)[:3000]}")

        return parts

    def _context_from_repository(
        self, db: Session, repo_id: int, tenant_id: int
    ) -> list[str]:
        parts = []

        from app.models.repository import Repository

        repo = db.query(Repository).filter(
            Repository.id == repo_id, Repository.tenant_id == tenant_id
        ).first()
        if repo:
            parts.append(f"REPOSITORY: {repo.name}")
            if getattr(repo, "synthesis_summary", None):
                parts.append(f"SYNTHESIS:\n{repo.synthesis_summary[:3000]}")

        # Top code components by analysis
        from app.models.code_component import CodeComponent

        components = (
            db.query(CodeComponent)
            .filter(
                CodeComponent.repository_id == repo_id,
                CodeComponent.tenant_id == tenant_id,
            )
            .limit(30)
            .all()
        )
        if components:
            lines = []
            for c in components:
                summary = (getattr(c, "summary", None) or "")[:200]
                lines.append(f"  - {c.location}: {summary}")
            parts.append("CODE COMPONENTS:\n" + "\n".join(lines))

        return parts


    async def generate_multi(
        self,
        db: Session,
        *,
        doc_type: str,
        sources: list[dict],
        tenant_id: int,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Generate documentation from multiple sources combined.

        sources: [{"type": "document"|"repository", "id": <int>}, ...]

        Returns a dict with: title, content, status, source_name, metadata, source_ids.
        Does NOT save to DB — caller saves via crud_generated_doc.
        """
        if doc_type not in _PROMPTS:
            raise ValueError(f"Unknown doc_type '{doc_type}'. Supported: {self.SUPPORTED_TYPES}")

        if not sources:
            raise ValueError("At least one source must be provided")

        # Deduplicate sources by (type, id)
        seen = set()
        unique_sources = []
        for s in sources:
            key = (s.get("type"), s.get("id"))
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)

        context_text = self._build_context_multi(db, unique_sources, tenant_id)
        source_names = [
            self._get_source_name(db, s["type"], s["id"], tenant_id)
            for s in unique_sources
        ]
        source_label = " + ".join(source_names[:3])
        if len(source_names) > 3:
            source_label += f" [+{len(source_names) - 3} more]"

        title = f"{_DOC_TYPE_TITLES.get(doc_type, doc_type)} — {source_label}"
        prompt = _PROMPTS[doc_type].format(context=context_text[:12000])

        try:
            from app.services.ai.gemini import gemini_service

            response = await gemini_service.generate_content(
                prompt,
                tenant_id=tenant_id,
                user_id=user_id,
                operation=f"auto_docs_{doc_type}_multi",
            )
            content = response.text or ""
            tokens = gemini_service.extract_token_usage(response)
            status = "completed"
        except Exception as e:
            self.logger.error(f"AutoDocs multi-source generation failed for {doc_type}: {e}")
            content = f"*Generation failed: {e}*"
            tokens = {}
            status = "failed"

        return {
            "title": title,
            "content": content,
            "status": status,
            "source_name": source_label,
            "source_ids": unique_sources,
            "metadata": {
                "doc_type": doc_type,
                "source_type": "multi",
                "source_count": len(unique_sources),
                **tokens,
            },
        }

    def _build_context_multi(
        self, db: Session, sources: list[dict], tenant_id: int
    ) -> str:
        """
        Assemble context from multiple sources.
        Allocates a proportional token budget per source, then merges.
        """
        parts = []
        per_source_cap = max(2000, 12000 // max(len(sources), 1))

        for s in sources:
            src_type = s.get("type", "")
            src_id = s.get("id")
            if src_id is None:
                continue
            try:
                if src_type == "document":
                    src_parts = self._context_from_document(db, src_id, tenant_id)
                elif src_type == "repository":
                    src_parts = self._context_from_repository(db, src_id, tenant_id)
                else:
                    continue

                src_text = "\n\n".join(src_parts)
                if len(src_text) > per_source_cap:
                    src_text = src_text[:per_source_cap] + "\n[… truncated for length …]"
                parts.append(f"--- SOURCE ({src_type.upper()} #{src_id}) ---\n{src_text}")
            except Exception as e:
                self.logger.warning(f"Context assembly error for {src_type} #{src_id}: {e}")
                parts.append(f"[Context error for {src_type} #{src_id}: {e}]")

        return "\n\n".join(parts) if parts else "No analysis data available yet."


auto_docs_service = AutoDocsService()
