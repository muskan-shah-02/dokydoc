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
You are a senior software architect generating a precise technical architecture diagram from REAL analyzed code.

━━━ CRITICAL RULES ━━━
1. Use ONLY the actual service names, class names, API paths, database tables, and external APIs that appear in SOURCE CONTEXT below.
2. Do NOT use generic labels like "API Service", "Web App", "Backend", "Database" — use the real names from the code.
3. Every arrow MUST have a label showing: protocol + what data flows (e.g. `REST: JWT token`, `SQL: user rows`, `Redis: task queue`, `HTTP: analysis JSON`).
4. Group nodes into subgraphs by architectural layer.
5. Show background workers, message queues, and async flows.

━━━ OUTPUT FORMAT ━━━
Produce a **Mermaid flowchart** (flowchart LR) followed by Markdown descriptions.

```mermaid
flowchart LR

  subgraph Frontend["🖥 Frontend (Browser)"]
    direction TB
    WebUI["Next.js UI\n(React)"]
  end

  subgraph APILayer["⚙ API Layer"]
    direction TB
    FastAPI["FastAPI\n(uvicorn)"]
    AuthAPI["Auth / JWT\n/api/login"]
    ... (add real endpoint groups from context)
  end

  subgraph ServiceLayer["🔧 Service Layer"]
    direction TB
    ... (real service class names from context, e.g. GeminiService, CodeAnalysisService)
  end

  subgraph Workers["⚡ Background Workers"]
    direction TB
    CeleryWorker["Celery Worker"]
    ... (real task names from context)
  end

  subgraph DataLayer["🗄 Data Layer"]
    direction TB
    DB[(PostgreSQL\nORM: SQLAlchemy)]
    Cache[(Redis\nBroker + Cache)]
  end

  subgraph ExternalAPIs["🌐 External APIs"]
    direction TB
    ... (real external APIs found in code: Gemini, GitHub, Jira, etc.)
  end

  %% Draw connections with labeled edges — every arrow must have a label
  WebUI -->|"HTTPS: user request"| FastAPI
  FastAPI -->|"SQL: tenant query"| DB
  ... (all real flows from context)
```

## Component Descriptions
One paragraph per node explaining its real role and responsibilities from the code.

## Key Data Flows
Numbered list of the most important data flows found in the codebase (e.g., "1. User uploads BRD → FastAPI → GeminiService → response stored in PostgreSQL").

━━━ SOURCE CONTEXT (use ONLY real names from here) ━━━
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

        context_text = self._build_context(db, source_type, source_id, tenant_id, doc_type=doc_type)
        source_name = self._get_source_name(db, source_type, source_id, tenant_id)
        title = f"{_DOC_TYPE_TITLES.get(doc_type, doc_type)} — {source_name}"

        cap = 18000 if doc_type == "architecture_diagram" else 12000
        prompt = _PROMPTS[doc_type].format(context=context_text[:cap])

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
            elif source_type in ("code_file", "standalone"):
                from app.models.code_component import CodeComponent
                comp = db.query(CodeComponent).filter(
                    CodeComponent.id == source_id, CodeComponent.tenant_id == tenant_id
                ).first()
                return comp.name if comp else f"File #{source_id}"
            elif source_type == "jira_item":
                from app.models.jira_item import JiraItem
                item = db.query(JiraItem).filter(
                    JiraItem.id == source_id, JiraItem.tenant_id == tenant_id
                ).first()
                if item:
                    return f"{item.external_key}: {item.title[:40]}"
                return f"JIRA #{source_id}"
            elif source_type == "analysis":
                from app.models.generated_doc import GeneratedDoc
                doc = db.query(GeneratedDoc).filter(
                    GeneratedDoc.id == source_id, GeneratedDoc.tenant_id == tenant_id
                ).first()
                if doc:
                    return doc.title[:50] if doc.title else f"Analysis #{source_id}"
                return f"Analysis #{source_id}"
        except Exception:
            pass
        return f"{source_type} #{source_id}"

    def _build_context(
        self, db: Session, source_type: str, source_id: int, tenant_id: int,
        doc_type: str = "",
    ) -> str:
        """Assemble a rich text context block from the source's analysis data."""
        parts = []

        try:
            if source_type == "document":
                parts.extend(self._context_from_document(db, source_id, tenant_id))
            elif source_type == "repository":
                if doc_type == "architecture_diagram":
                    parts.extend(self._context_from_repository_architecture(db, source_id, tenant_id))
                else:
                    parts.extend(self._context_from_repository(db, source_id, tenant_id))
            elif source_type in ("code_file", "standalone"):
                parts.extend(self._context_from_code_file(db, source_id, tenant_id))
            elif source_type == "jira_item":
                parts.extend(self._context_from_jira_item(db, source_id, tenant_id))
            elif source_type == "analysis":
                parts.extend(self._context_from_analysis(db, source_id, tenant_id))
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

    def _context_from_repository_architecture(
        self, db: Session, repo_id: int, tenant_id: int
    ) -> list[str]:
        """
        Build a rich architecture-specific context from repository analysis data.
        Extracts real service names, API contracts, DB models, external integrations,
        and inter-service data flows to power an accurate architecture diagram.
        """
        import json
        from app.models.repository import Repository
        from app.models.code_component import CodeComponent

        parts = []

        repo = db.query(Repository).filter(
            Repository.id == repo_id, Repository.tenant_id == tenant_id
        ).first()
        if not repo:
            return ["[Repository not found]"]

        parts.append(f"REPOSITORY: {repo.name}\nURL: {getattr(repo, 'url', '')}")

        # ── 1. Synthesis data (high-level architecture detected by AI) ──
        synthesis = getattr(repo, "synthesis_data", None)
        if synthesis and isinstance(synthesis, dict):
            arch = synthesis.get("architecture", {})
            tech = synthesis.get("technology_stack", {})
            overview = synthesis.get("system_overview", "")
            services = synthesis.get("services", [])
            data_flows = synthesis.get("data_flows", [])

            if overview:
                parts.append(f"SYSTEM OVERVIEW:\n{overview[:1000]}")
            if arch:
                parts.append(f"DETECTED ARCHITECTURE:\n{json.dumps(arch, indent=2)[:1500]}")
            if tech:
                parts.append(f"TECHNOLOGY STACK:\n{json.dumps(tech, indent=2)[:800]}")
            if services:
                parts.append(f"SERVICES (from synthesis):\n{json.dumps(services, indent=2)[:1000]}")
            if data_flows:
                parts.append(f"DATA FLOWS (from synthesis):\n{json.dumps(data_flows, indent=2)[:1000]}")

        # ── 2. All API contracts across the codebase ──
        components = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        ).all()

        all_api_contracts = []
        all_external_deps = []
        all_db_models = []
        all_services = []
        all_data_flows = []
        all_security = []
        file_type_map: dict[str, list[str]] = {}

        for comp in components:
            sa = comp.structured_analysis or {}
            lang_info = sa.get("language_info", {})
            file_type = lang_info.get("file_type", "Other")
            comp_name = comp.name or ""

            # Group by file type for architecture layer mapping
            if file_type not in file_type_map:
                file_type_map[file_type] = []
            file_type_map[file_type].append(comp_name)

            # Collect API contracts (real endpoints)
            for contract in sa.get("api_contracts", []):
                if isinstance(contract, dict):
                    contract["_source_file"] = comp_name
                    all_api_contracts.append(contract)

            # Collect external dependencies (external APIs, SDKs)
            for dep in sa.get("dependencies", []):
                if isinstance(dep, dict):
                    dep_name = dep.get("name", "") or dep.get("to", "")
                    dep_type = dep.get("type", "")
                    # Flag external dependencies (not internal imports)
                    if dep_type in ("external", "pip", "npm", "third_party") or any(
                        k in dep_name.lower() for k in [
                            "google", "gemini", "openai", "anthropic", "github", "gitlab",
                            "jira", "atlassian", "redis", "celery", "stripe", "twilio",
                            "sendgrid", "aws", "azure", "gcp", "slack", "oauth",
                        ]
                    ):
                        all_external_deps.append({
                            "name": dep_name,
                            "type": dep_type,
                            "source_file": comp_name,
                        })

            # Collect data model relationships (DB tables)
            for model in sa.get("data_model_relationships", []):
                if isinstance(model, dict):
                    model["_source_file"] = comp_name
                    all_db_models.append(model)

            # Collect service class names
            for component_entry in sa.get("components", []):
                if isinstance(component_entry, dict):
                    ctype = component_entry.get("type", "")
                    if ctype in ("Service", "Class", "Module", "Handler", "Manager", "Router"):
                        all_services.append({
                            "name": component_entry.get("name", ""),
                            "type": ctype,
                            "purpose": component_entry.get("purpose", "")[:150],
                            "file": comp_name,
                        })

            # Collect data flows
            for flow in sa.get("data_flows", []):
                if isinstance(flow, dict):
                    all_data_flows.append(flow)

            # Collect component interactions
            for interaction in sa.get("component_interactions", []):
                if isinstance(interaction, dict):
                    all_data_flows.append(interaction)

            # Security patterns (auth, JWT, etc.)
            for sec in sa.get("security_patterns", []):
                if isinstance(sec, dict) and sec not in all_security:
                    all_security.append(sec)

        # ── 3. Emit structured context sections ──
        if file_type_map:
            layer_text = "\n".join(
                f"  {layer} layer: {', '.join(files[:8])}"
                for layer, files in sorted(file_type_map.items())
                if files
            )
            parts.append(f"FILES BY ARCHITECTURAL LAYER:\n{layer_text}")

        if all_services:
            # Deduplicate by name
            seen_names = set()
            unique_services = []
            for s in all_services:
                if s["name"] and s["name"] not in seen_names:
                    seen_names.add(s["name"])
                    unique_services.append(s)
            parts.append(
                f"REAL SERVICE/CLASS NAMES (use these in diagram nodes):\n"
                + json.dumps(unique_services[:30], indent=2)[:2000]
            )

        if all_api_contracts:
            # Deduplicate by endpoint
            seen_endpoints: set[str] = set()
            unique_contracts = []
            for c in all_api_contracts:
                ep = c.get("endpoint", "") or c.get("path", "")
                if ep and ep not in seen_endpoints:
                    seen_endpoints.add(ep)
                    unique_contracts.append(c)
            parts.append(
                f"REAL API ENDPOINTS (use paths in diagram edge labels):\n"
                + json.dumps(unique_contracts[:25], indent=2)[:2500]
            )

        if all_db_models:
            parts.append(
                f"DATABASE MODELS / TABLES (show in Data Layer subgraph):\n"
                + json.dumps(all_db_models[:15], indent=2)[:1500]
            )

        if all_external_deps:
            # Deduplicate
            seen_ext: set[str] = set()
            unique_ext = []
            for d in all_external_deps:
                key = d.get("name", "")
                if key and key not in seen_ext:
                    seen_ext.add(key)
                    unique_ext.append(d)
            parts.append(
                f"EXTERNAL API / SERVICE INTEGRATIONS (show in External APIs subgraph):\n"
                + json.dumps(unique_ext[:20], indent=2)[:1000]
            )

        if all_data_flows:
            parts.append(
                f"DATA FLOWS BETWEEN COMPONENTS (use for arrow labels):\n"
                + json.dumps(all_data_flows[:20], indent=2)[:1500]
            )

        if all_security:
            parts.append(
                f"SECURITY / AUTH PATTERNS (show in diagram):\n"
                + json.dumps(all_security[:5], indent=2)[:500]
            )

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

        context_text = self._build_context_multi(db, unique_sources, tenant_id, doc_type=doc_type)
        source_names = [
            self._get_source_name(db, s["type"], s["id"], tenant_id)
            for s in unique_sources
        ]
        source_label = " + ".join(source_names[:3])
        if len(source_names) > 3:
            source_label += f" [+{len(source_names) - 3} more]"

        title = f"{_DOC_TYPE_TITLES.get(doc_type, doc_type)} — {source_label}"
        cap = 18000 if doc_type == "architecture_diagram" else 12000
        prompt = _PROMPTS[doc_type].format(context=context_text[:cap])

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
        self, db: Session, sources: list[dict], tenant_id: int, doc_type: str = "",
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
                    if doc_type == "architecture_diagram":
                        src_parts = self._context_from_repository_architecture(db, src_id, tenant_id)
                    else:
                        src_parts = self._context_from_repository(db, src_id, tenant_id)
                elif src_type in ("code_file", "standalone"):
                    src_parts = self._context_from_code_file(db, src_id, tenant_id)
                elif src_type == "jira_item":
                    src_parts = self._context_from_jira_item(db, src_id, tenant_id)
                elif src_type == "analysis":
                    src_parts = self._context_from_analysis(db, src_id, tenant_id)
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

    def _context_from_code_file(
        self, db: Session, component_id: int, tenant_id: int
    ) -> list[str]:
        """Context from a single analyzed code component (file or standalone)."""
        parts = []
        from app.models.code_component import CodeComponent
        import json

        comp = db.query(CodeComponent).filter(
            CodeComponent.id == component_id, CodeComponent.tenant_id == tenant_id
        ).first()
        if not comp:
            return [f"[Code component #{component_id} not found]"]

        parts.append(f"CODE FILE: {comp.name}")
        if comp.location:
            parts.append(f"LOCATION: {comp.location}")
        if comp.summary:
            parts.append(f"SUMMARY:\n{comp.summary[:2000]}")
        if comp.structured_analysis:
            sa = comp.structured_analysis
            # Extract the richest fields: business rules, API contracts, data models, security
            for field in ("business_rules", "api_contracts", "data_models", "security_patterns",
                          "dependencies", "language_info", "key_concepts"):
                val = sa.get(field)
                if val:
                    parts.append(f"{field.upper().replace('_', ' ')}:\n{json.dumps(val, indent=2)[:800]}")

        return parts

    def _context_from_jira_item(
        self, db: Session, jira_item_id: int, tenant_id: int
    ) -> list[str]:
        """Context from a JIRA item (epic, story, task, bug)."""
        parts = []
        try:
            from app.models.jira_item import JiraItem
            item = db.query(JiraItem).filter(
                JiraItem.id == jira_item_id, JiraItem.tenant_id == tenant_id
            ).first()
            if not item:
                return [f"[JIRA item #{jira_item_id} not found]"]

            parts.append(f"JIRA {item.item_type.upper()}: {item.external_key} — {item.title}")
            meta = []
            if item.status:
                meta.append(f"Status: {item.status}")
            if item.priority:
                meta.append(f"Priority: {item.priority}")
            if item.sprint_name:
                meta.append(f"Sprint: {item.sprint_name}")
            if item.assignee:
                meta.append(f"Assignee: {item.assignee}")
            if meta:
                parts.append(" | ".join(meta))
            if item.description:
                parts.append(f"DESCRIPTION:\n{item.description[:2000]}")
            if item.acceptance_criteria:
                criteria = item.acceptance_criteria
                if isinstance(criteria, list):
                    parts.append("ACCEPTANCE CRITERIA:\n" + "\n".join(f"  - {c}" for c in criteria))
                else:
                    parts.append(f"ACCEPTANCE CRITERIA:\n{str(criteria)[:1000]}")
        except Exception as e:
            parts.append(f"[JIRA context error: {e}]")
        return parts

    def _context_from_analysis(
        self, db: Session, doc_id: int, tenant_id: int
    ) -> list[str]:
        """Context from a previously generated Auto Docs result."""
        parts = []
        from app.models.generated_doc import GeneratedDoc

        doc = db.query(GeneratedDoc).filter(
            GeneratedDoc.id == doc_id, GeneratedDoc.tenant_id == tenant_id
        ).first()
        if not doc:
            return [f"[Generated doc #{doc_id} not found]"]

        parts.append(f"PREVIOUS ANALYSIS: {doc.title}")
        parts.append(f"TYPE: {doc.doc_type} | SOURCE: {doc.source_name or 'unknown'}")
        if doc.content:
            parts.append(f"CONTENT:\n{doc.content[:4000]}")

        return parts


auto_docs_service = AutoDocsService()
