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

    # ── New diagram types (Sprint C) ──────────────────────────────────────────

    "class_diagram": """
You are a UML expert. Generate a precise **Class Diagram** from the REAL analyzed code below.

Use Mermaid `classDiagram` syntax.

━━━ RULES ━━━
1. Extract EVERY class, interface, abstract class, and enum found in the code.
2. Show attributes with visibility (`+` public, `-` private, `#` protected) and types (e.g., `+String name`, `-int count`).
3. Show methods with visibility, parameters, and return types (e.g., `+login(email: str, password: str) Token`).
4. Show ALL relationships with correct Mermaid notation:
   - Inheritance: `ChildClass --|> ParentClass`
   - Composition: `Owner *-- Component`
   - Aggregation: `Container o-- Item`
   - Association: `ClassA --> ClassB`
   - Dependency (uses): `ClassA ..> ClassB`
   - Implements interface: `ConcreteClass ..|> Interface`
5. Add cardinality labels: `"1"`, `"*"`, `"0..1"`, `"1..*"`
6. Use REAL names from the code — no invented names.

Output format:
```mermaid
classDiagram
  class RealClassName {
    +String realAttribute
    -int privateField
    +realMethod(param: Type) ReturnType
  }
  RealClassName --|> ParentClass
  ...
```

## Class Responsibilities
| Class | Role |
|-------|------|
| RealClassName | one-line description |

## Key Design Patterns
Identify any design patterns (Repository, Factory, Singleton, Strategy, Observer, etc.) used.

Source context:
{context}
""",

    "sequence_diagram": """
You are a systems architect. Generate a detailed **Sequence Diagram** showing the complete request/response flow.

Use Mermaid `sequenceDiagram` syntax.

━━━ RULES ━━━
1. Show ALL actors in order: Client → Router → Middleware (Auth/Validation) → Handler → Service(s) → Repository/DB → External APIs
2. Use REAL function/method names from the code as message labels (e.g., `create_doc(payload)`, `gemini_service.generate_content(prompt)`)
3. Show data being passed on EVERY arrow (e.g., `user_id: int, jwt: str`, `AnalysisResult JSON`)
4. Show `activate` / `deactivate` blocks for synchronous processing
5. Show async operations with `par` blocks
6. Show error paths with `alt Happy Path / else Error Path` blocks
7. Show database queries as: `DB-->>Service: SELECT * FROM users WHERE id=1`
8. Show external API calls with actual payload shape
9. For each auth check, show the JWT validation step

Output format:
```mermaid
sequenceDiagram
  actor Client
  participant Router as "POST /real/endpoint"
  participant Auth as "JWT Middleware"
  participant Handler as "RealHandler.real_method()"
  participant Service as "RealService"
  participant DB as "PostgreSQL\n(real_table)"
  participant ExtAPI as "External API Name"

  Client->>Router: HTTP POST {real payload fields}
  activate Router
  Router->>Auth: validate JWT
  Auth-->>Router: tenant_id, user_id
  ...
```

## Flow Description
Numbered step-by-step plain-English description of the sequence.

## Error Scenarios
| Scenario | HTTP Status | Response |
|----------|------------|----------|
| Auth failure | 401 | {detail: "..."} |

Source context:
{context}
""",

    "code_flow_diagram": """
You are a code analyst. Generate a **Code Flow Diagram** showing how data transforms through the code.

Use Mermaid `flowchart TD` (top-down).

━━━ RULES ━━━
1. Show each function/method as a rectangle node with its REAL name and brief purpose
2. Show decision points (if/else, try/except, validation checks) as diamond nodes {Decision}
3. Show data transformation steps — what goes in and what comes out
4. Show external calls (DB queries, API calls, file I/O) as distinct shapes:
   - Database: `[(TableName SQL query)]`
   - External API: `{{API Name: operation}}`
   - File/IO: `[/File operation/]`
5. Label EVERY arrow with the data being passed or the condition being met
6. Show error paths (exceptions, validation failures) with dashed arrows `-.->` in red styling
7. Group related processing steps into subgraphs
8. Use REAL variable names and function names from the code

Output format:
```mermaid
flowchart TD
  Start(["Input: real_param: Type"])

  subgraph Validation["Input Validation"]
    V1{{"Is valid?"}}
    V2["validate_real_field(value)"]
  end

  subgraph Processing["Core Processing"]
    P1["real_function(param)"]
    P2["transform_data(result)"]
  end

  DB[(real_table\nSELECT ...)]
  EXT{{ExternalAPI\nPOST /endpoint}}

  Start --> V1
  V1 -->|"valid"| P1
  V1 -->|"invalid"| Error["400 ValidationError"]
  P1 -->|"query: {field: value}"| DB
  DB -->|"rows: List[Model]"| P2
  P2 -->|"result: OutputType"| End(["Return: ResponseModel"])

  style Error fill:#fee2e2,stroke:#ef4444
```

## Code Flow Walkthrough
Numbered step-by-step explanation of the main code path.

## Key Data Transformations
| Step | Input Type | Output Type | Operation |
|------|-----------|-------------|-----------|

Source context:
{context}
""",

    "component_interaction_diagram": """
You are a systems architect analyzing TWO components. Generate a diagram showing HOW THEY INTERACT.

━━━ STEP 1: Detect the relationship type ━━━
Analyze the SOURCE CONTEXT to determine:
A) Does one component call/import the other? → Use `sequenceDiagram`
B) Do they share interfaces, models, or base classes? → Use `classDiagram`
C) Are they peer services at the same layer exchanging data? → Use `flowchart LR`
D) Do they have no direct link but share dependencies? → Use `flowchart LR` showing shared deps

━━━ STEP 2: Generate the MOST APPROPRIATE diagram ━━━

If sequenceDiagram (A):
```mermaid
sequenceDiagram
  participant Caller as "RealCallerClass\n(caller_file.py)"
  participant Callee as "RealCalleeClass\n(callee_file.py)"
  Caller->>Callee: real_method(param: Type)
  note over Callee: What it does internally
  Callee-->>Caller: ReturnType
```

If classDiagram (B):
```mermaid
classDiagram
  class File1Class { ... }
  class File2Class { ... }
  File1Class --> File2Class : uses / extends / implements
```

If flowchart (C or D):
```mermaid
flowchart LR
  subgraph File1["File 1 Name"]
    A["RealFunction()\nwhat it does"]
  end
  subgraph File2["File 2 Name"]
    B["RealFunction()\nwhat it does"]
  end
  A -->|"data: Type"| B
  B -->|"response: Type"| A
```

━━━ RULES ━━━
- Use REAL class names, function names, and data types from the context
- Label every arrow with the data being exchanged
- Show what triggers the interaction and what the outcome is
- Show error handling between the two components

## Interaction Summary
- **Relationship type**: Caller-Callee / Peer / Shared dependency
- **Direction**: Unidirectional / Bidirectional
- **Data exchanged**: List the key data structures passed between them
- **Coupling level**: Tight / Loose — and why

## Shared Contracts
List shared interfaces, models, or types that both components depend on.

Source context:
{context}
""",

    "folder_architecture": """
You are a software architect. Generate a **Module Architecture Diagram** for the folder/package below.

Use Mermaid `flowchart LR` (left-to-right).

━━━ RULES ━━━
1. Show EVERY file in the folder as a node, labeled with its real filename and 1-line purpose
2. Use correct node shapes for different file roles:
   - Route handlers / controllers: `Handler["filename.py\nRoute Handler"]`
   - Services / business logic: `Service(["filename.py\nService"])` (rounded)
   - Data models / ORM: `Model[("filename.py\nDB Model")]` (cylinder)
   - Utilities / helpers: `Util["filename.py\nUtility"]`
   - Config / settings: `Conf{{"filename.py\nConfig"}}`
   - Tests: `Test[/"filename.py\nTests"/]`
3. Show connections between files (imports, function calls, shared data):
   - Direct import: `FileA -->|"imports ClassName"| FileB`
   - API call: `FileA -->|"calls method()"| FileB`
   - Shared model: `FileA & FileB -->|"uses"| ModelFile`
4. Group sub-folders as subgraphs
5. Label ALL arrows — what is imported or called
6. Show external dependencies (DB, APIs) as separate nodes

Output format:
```mermaid
flowchart LR
  subgraph Folder["📁 folder/path"]
    direction TB
    File1["real_file.py\nRoute handler for /endpoint"]
    File2(["real_service.py\nBusiness logic"])
    File3[("real_model.py\nDB ORM Model")]
  end

  subgraph SubFolder["📁 folder/subfolder"]
    File4["another_file.py\nPurpose"]
  end

  DB[(PostgreSQL)]
  ExtAPI{{External API}}

  File1 -->|"imports Service"| File2
  File2 -->|"queries Model"| File3
  File3 -->|"SQL"| DB
```

## Module Overview
| File | Type | Responsibility |
|------|------|----------------|

## Module Boundaries
What this module exposes to the rest of the system (its public interface/API).

## Internal Dependencies
The dependency graph within this module (which files depend on which).

Source context:
{context}
""",

    "api_data_flow": """
You are a systems architect. Generate a **Complete API Data Flow Diagram** for the specific endpoint described.

Use Mermaid `sequenceDiagram` syntax showing the FULL request lifecycle.

━━━ RULES ━━━
1. Show the COMPLETE flow from HTTP request to HTTP response — nothing skipped
2. Use REAL names: the actual route path, handler class/function, service names, table names
3. Show EVERY step:
   a. Client sends request → show real request body schema with field names and types
   b. CORS / Rate limiting middleware
   c. JWT Authentication → token validation → extract tenant_id, user_id
   d. Request validation (Pydantic model) → show what fields are validated
   e. Route handler receives → what it extracts from the request
   f. Service method called → show method signature
   g. Database queries → show actual table names and operation (SELECT/INSERT/UPDATE/DELETE)
   h. External API calls → show what is sent and what comes back
   i. Background tasks spawned (if any) → show what they do async
   j. Response constructed → show response schema fields
   k. Client receives response

4. Show BOTH paths: Happy Path AND at least 3 error scenarios (auth failure, validation error, not found, external API failure)
5. Use `activate`/`deactivate` for long operations
6. Use `note over` for important processing notes
7. Show `par` blocks for parallel operations

Output format:
```mermaid
sequenceDiagram
  actor Client
  participant GW as "API Gateway\n(FastAPI/uvicorn)"
  participant Auth as "JWT Auth Middleware"
  participant Handler as "RealHandler\nPOST /real/path"
  participant Svc as "RealService"
  participant DB as "PostgreSQL\n(real_table)"
  participant ExtAPI as "Real External API"
  participant Worker as "Celery Worker\n(background)"

  Client->>GW: POST /real/endpoint
  note over Client,GW: Request body: {field1: Type, field2: Type}

  GW->>Auth: validate Bearer token
  alt Token valid
    Auth-->>GW: {tenant_id: int, user_id: int}
  else Token invalid/expired
    Auth-->>Client: 401 Unauthorized {detail: "..."}
  end

  GW->>Handler: route_handler(payload: RealSchema)
  activate Handler

  Handler->>Handler: validate input
  alt Validation passes
    Handler->>Svc: service_method(param1, param2)
    activate Svc
    Svc->>DB: INSERT INTO real_table (col1, col2) VALUES (...)
    DB-->>Svc: returning id: int
    Svc->>ExtAPI: POST /external/endpoint {payload}
    ExtAPI-->>Svc: {response_field: value}
    Svc-->>Handler: RealResponseModel
    deactivate Svc
    Handler-->>Client: 201 {id, field1, field2}
  else Validation fails
    Handler-->>Client: 422 Unprocessable Entity {detail: [{field, msg}]}
  end
  deactivate Handler
```

## Request Schema
```json
{
  "field1": "Type — description",
  "field2": "Type — description (optional)"
}
```

## Response Schema
```json
// Success (2xx)
{
  "id": "int",
  "field": "Type"
}
// Error (4xx/5xx)
{
  "detail": "string | [{loc, msg, type}]"
}
```

## Processing Steps
Numbered plain-English description of each step in the API lifecycle.

## Performance Considerations
Key performance characteristics: DB query count, external API calls, caching, async operations.

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
    # Sprint C diagram types
    "class_diagram": "Class Diagram",
    "sequence_diagram": "Sequence Diagram",
    "code_flow_diagram": "Code Flow Diagram",
    "component_interaction_diagram": "Component Interaction Diagram",
    "folder_architecture": "Folder Architecture",
    "api_data_flow": "API Data Flow",
}

# Context token caps per doc_type (chars — safety cap before sending to AI)
_TOKEN_CAP: dict[str, int] = {
    "architecture_diagram":          18000,
    "folder_architecture":           18000,
    "api_data_flow":                 18000,
    "class_diagram":                 14000,
    "sequence_diagram":              14000,
    "component_interaction_diagram": 14000,
    "code_flow_diagram":             12000,
}
# All other types default to 12000 (via dict.get fallback)


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

        cap = _TOKEN_CAP.get(doc_type, 12000)
        # Use replace() not .format() — context may contain literal {braces}
        # from JSON (e.g. {"Decision": "..."}) which would cause KeyError with .format()
        prompt = _PROMPTS[doc_type].replace("{context}", context_text[:cap])

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
            elif source_type == "confluence_page":
                return f"Confluence Page #{source_id}"
        except Exception:
            pass
        return f"{source_type} #{source_id}"

    def _build_context(
        self, db: Session, source_type: str, source_id: int, tenant_id: int,
        doc_type: str = "",
        # Extra metadata for new source types
        folder_path: str = "",
        endpoint_path: str = "",
    ) -> str:
        """Assemble a rich text context block from the source's analysis data."""
        parts = []

        try:
            if source_type == "document":
                parts.extend(self._context_from_document(db, source_id, tenant_id))
            elif source_type == "repository":
                if doc_type in ("architecture_diagram", "folder_architecture"):
                    parts.extend(self._context_from_repository_architecture(db, source_id, tenant_id))
                else:
                    parts.extend(self._context_from_repository(db, source_id, tenant_id))
            elif source_type == "folder":
                parts.extend(self._context_from_folder(db, source_id, folder_path, tenant_id))
            elif source_type == "api_endpoint":
                parts.extend(self._context_from_api_endpoint(db, endpoint_path, tenant_id))
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
        cap = _TOKEN_CAP.get(doc_type, 12000)
        # Use replace() not .format() — context may contain literal {braces}
        # from JSON (e.g. {"Decision": "..."}) which would cause KeyError with .format()
        prompt = _PROMPTS[doc_type].replace("{context}", context_text[:cap])

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
                folder_path = s.get("folder_path", "")
                endpoint_path = s.get("endpoint_path", "")

                if src_type == "document":
                    src_parts = self._context_from_document(db, src_id, tenant_id)
                elif src_type == "repository":
                    if doc_type in ("architecture_diagram", "folder_architecture"):
                        src_parts = self._context_from_repository_architecture(db, src_id, tenant_id)
                    else:
                        src_parts = self._context_from_repository(db, src_id, tenant_id)
                elif src_type == "folder":
                    src_parts = self._context_from_folder(db, src_id, folder_path, tenant_id)
                elif src_type == "api_endpoint":
                    src_parts = self._context_from_api_endpoint(db, endpoint_path, tenant_id)
                elif src_type in ("code_file", "standalone"):
                    src_parts = self._context_from_code_file(db, src_id, tenant_id)
                elif src_type == "jira_item":
                    src_parts = self._context_from_jira_item(db, src_id, tenant_id)
                elif src_type == "analysis":
                    src_parts = self._context_from_analysis(db, src_id, tenant_id)
                elif src_type == "confluence_page":
                    src_parts = self._context_from_confluence_page(db, src_id, tenant_id)
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

    def _context_from_confluence_page(
        self, db: Session, page_id: int, tenant_id: int
    ) -> list[str]:
        """Fetch a Confluence page via the stored OAuth token and return its content as context."""
        import re as _re
        import httpx
        from app.crud.crud_integration_config import crud_integration_config

        config = crud_integration_config.get_by_provider(db, tenant_id=tenant_id, provider="confluence")
        if not config or not config.is_active or not config.access_token:
            return [f"[Confluence integration not connected — cannot fetch page #{page_id}]"]

        base_url = config.base_url or ""
        headers = {"Authorization": f"Bearer {config.access_token}", "Accept": "application/json"}

        try:
            with httpx.Client(timeout=20) as client:
                resp = client.get(
                    f"{base_url}/wiki/rest/api/content/{page_id}",
                    headers=headers,
                    params={"expand": "body.storage,space,version,ancestors"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return [f"[Confluence page #{page_id} fetch error: {e}]"]

        title = data.get("title", f"page_{page_id}")
        space = data.get("space", {}).get("name", "")
        ancestors = data.get("ancestors", [])
        breadcrumb = " > ".join(a["title"] for a in ancestors) if ancestors else ""

        storage_body = data.get("body", {}).get("storage", {}).get("value", "")
        # Convert Confluence storage XML to readable text
        text = _re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: "#" * int(m.group(1)) + " " + m.group(2) + "\n", storage_body, flags=_re.DOTALL)
        text = _re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=_re.DOTALL)
        text = _re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=_re.DOTALL)
        text = _re.sub(r'<br\s*/?>', '\n', text)
        text = _re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=_re.DOTALL)
        text = _re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=_re.DOTALL)
        text = _re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', ' ', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
        text = _re.sub(r' {2,}', ' ', text)
        text = _re.sub(r'\n{3,}', '\n\n', text.strip())

        parts = [f"CONFLUENCE PAGE: {title}"]
        if space:
            parts.append(f"SPACE: {space}")
        if breadcrumb:
            parts.append(f"PATH: {breadcrumb} > {title}")
        if text:
            parts.append(f"CONTENT:\n{text[:4000]}")

        return parts


    # ── New Sprint C context builders ────────────────────────────────────────

    def _context_from_folder(
        self, db: Session, repo_id: int, folder_path: str, tenant_id: int
    ) -> list[str]:
        """
        Build context for all code components whose location matches a folder path prefix.
        Extracts inter-file dependencies, API contracts, and module structure.
        """
        import json
        from app.models.code_component import CodeComponent
        from app.models.repository import Repository

        parts = []

        repo = db.query(Repository).filter(
            Repository.id == repo_id, Repository.tenant_id == tenant_id
        ).first()
        repo_name = repo.name if repo else f"Repository #{repo_id}"

        parts.append(f"FOLDER: {folder_path}\nREPOSITORY: {repo_name}")

        # Find all components whose location contains the folder path
        all_comps = db.query(CodeComponent).filter(
            CodeComponent.repository_id == repo_id,
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
        ).all()

        # Filter by folder path prefix (case-insensitive partial match)
        folder_lower = folder_path.lower().rstrip("/")
        components = [
            c for c in all_comps
            if folder_lower in (c.location or "").lower()
        ]

        if not components:
            parts.append(f"[No analyzed files found under path: {folder_path}]")
            return parts

        parts.append(f"FILES IN FOLDER ({len(components)} files):")

        all_api_contracts = []
        all_imports: list[dict] = []
        all_services: list[dict] = []
        all_db_models: list[dict] = []

        for comp in components:
            sa = comp.structured_analysis or {}
            comp_name = comp.name or comp.location or ""
            summary = (comp.summary or "")[:200]

            # Extract file path from GitHub URL
            loc = comp.location or ""
            import re
            path_match = re.search(r"(?:raw\.githubusercontent\.com|github\.com)/[^/]+/[^/]+/(?:[^/]+/)?(.+)", loc)
            file_path = path_match.group(1) if path_match else loc

            parts.append(f"  • {file_path}: {summary}")

            # Collect API contracts
            for c in sa.get("api_contracts", []):
                if isinstance(c, dict):
                    c["_file"] = comp_name
                    all_api_contracts.append(c)

            # Collect inter-file dependencies/imports
            for dep in sa.get("dependencies", []):
                if isinstance(dep, dict):
                    dep_type = dep.get("type", "")
                    if dep_type in ("internal", "relative", "local") or ".".join(
                        dep.get("name", "").split(".")[:2]
                    ) in folder_lower:
                        all_imports.append({"from": comp_name, **dep})

            # Collect service names
            for component_entry in sa.get("components", []):
                if isinstance(component_entry, dict):
                    ctype = component_entry.get("type", "")
                    if ctype in ("Service", "Class", "Router", "Handler", "Manager"):
                        all_services.append({
                            "name": component_entry.get("name"),
                            "type": ctype,
                            "file": comp_name,
                            "purpose": (component_entry.get("purpose") or "")[:120],
                        })

            # Collect DB models
            for m in sa.get("data_model_relationships", []):
                if isinstance(m, dict):
                    all_db_models.append({"entity": m.get("entity"), "file": comp_name})

        if all_api_contracts:
            parts.append(
                f"\nAPI ENDPOINTS IN THIS FOLDER:\n"
                + json.dumps(all_api_contracts[:20], indent=2)[:2000]
            )

        if all_services:
            parts.append(
                f"\nSERVICES/CLASSES IN THIS FOLDER:\n"
                + json.dumps(all_services[:20], indent=2)[:1500]
            )

        if all_imports:
            parts.append(
                f"\nINTER-FILE IMPORTS (how files depend on each other):\n"
                + json.dumps(all_imports[:20], indent=2)[:1000]
            )

        if all_db_models:
            parts.append(
                f"\nDB MODELS IN THIS FOLDER:\n"
                + json.dumps(all_db_models[:10], indent=2)[:500]
            )

        return parts

    def _context_from_api_endpoint(
        self, db: Session, endpoint_query: str, tenant_id: int, repo_id: int | None = None
    ) -> list[str]:
        """
        Build a rich context for a specific API endpoint by searching all analyzed
        components' api_contracts for a matching path+method, then tracing the call chain.
        """
        import json
        import re
        from app.models.code_component import CodeComponent

        parts = []
        parts.append(f"API ENDPOINT ANALYSIS REQUEST: {endpoint_query}")

        # Normalize query: extract method and path
        method_match = re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(.+)$",
                                endpoint_query.strip().upper())
        search_method = method_match.group(1) if method_match else None
        search_path = method_match.group(2) if method_match else endpoint_query.strip()

        # Search all components for matching API contracts
        query = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        )
        if repo_id:
            query = query.filter(CodeComponent.repository_id == repo_id)

        all_comps = query.all()

        handler_files: list[dict] = []
        related_comps: list[dict] = []

        for comp in all_comps:
            sa = comp.structured_analysis or {}
            contracts = sa.get("api_contracts", [])
            if not isinstance(contracts, list):
                continue

            matched = False
            for contract in contracts:
                if not isinstance(contract, dict):
                    continue
                ep_path = contract.get("endpoint", "") or contract.get("path", "")
                ep_method = (contract.get("method", "") or "").upper()

                # Check if this contract matches the query
                path_match = (
                    search_path.lower() in ep_path.lower() or
                    ep_path.lower() in search_path.lower() or
                    # Flexible: remove path params for matching
                    re.sub(r"\{[^}]+\}", "", ep_path).strip("/").lower() in
                    re.sub(r"\{[^}]+\}", "", search_path).strip("/").lower()
                )
                method_ok = not search_method or ep_method == search_method or not ep_method

                if path_match and method_ok:
                    matched = True
                    handler_files.append({
                        "file": comp.name or comp.location or "",
                        "component_id": comp.id,
                        "contract": contract,
                        "summary": (comp.summary or "")[:300],
                        "structured_analysis": {
                            k: v for k, v in sa.items()
                            if k in ("components", "dependencies", "data_flows",
                                     "security_patterns", "business_rules")
                        },
                    })
                    break

            if not matched:
                # Check if file name suggests it's related (e.g., "auto_docs.py" for "/auto-docs/")
                clean_path = re.sub(r"[^a-z0-9]", "_", search_path.lower().strip("/"))
                file_name = (comp.name or "").lower()
                if any(part in file_name for part in clean_path.split("_") if len(part) > 3):
                    related_comps.append({
                        "file": comp.name or "",
                        "summary": (comp.summary or "")[:200],
                    })

        if handler_files:
            parts.append(
                f"\nHANDLER FILES FOUND ({len(handler_files)}):\n"
                + json.dumps(handler_files[:5], indent=2)[:5000]
            )
        else:
            parts.append(f"\n[No exact handler found for: {endpoint_query}]")
            if related_comps:
                parts.append(
                    f"POTENTIALLY RELATED FILES:\n"
                    + json.dumps(related_comps[:5], indent=2)[:1000]
                )

        return parts

    def recommend_diagram_type(
        self, db: Session, sources: list[dict], tenant_id: int
    ) -> dict:
        """
        Analyze sources and recommend the most appropriate diagram type.

        sources: list of {type, id, folder_path?, endpoint_path?}
        Returns: {recommended, reason, alternatives, confidence}
        """
        from app.models.code_component import CodeComponent

        source_types = [s.get("type", "") for s in sources]
        n = len(sources)

        # ── Special source types ──────────────────────────────────────────────

        if "api_endpoint" in source_types:
            return {
                "recommended": "api_data_flow",
                "reason": "An API endpoint source traces the full request lifecycle: client → auth → handler → service → database → response.",
                "alternatives": ["sequence_diagram", "component_spec"],
                "confidence": 0.97,
            }

        if "repository" in source_types:
            return {
                "recommended": "architecture_diagram",
                "reason": "A full repository is best shown as a system architecture diagram with services, databases, external APIs, and data flows.",
                "alternatives": ["component_spec", "api_summary", "data_models"],
                "confidence": 0.95,
            }

        if "folder" in source_types:
            return {
                "recommended": "folder_architecture",
                "reason": "A folder source generates a module diagram showing all files, their roles, and how they import/call each other.",
                "alternatives": ["architecture_diagram", "api_summary"],
                "confidence": 0.92,
            }

        # ── Code file analysis ────────────────────────────────────────────────

        code_source_types = ("code_file", "standalone")
        code_sources = [s for s in sources if s.get("type") in code_source_types]
        comp_ids = [s["id"] for s in code_sources if s.get("id")]

        comps = []
        if comp_ids:
            try:
                comps = db.query(CodeComponent).filter(
                    CodeComponent.id.in_(comp_ids),
                    CodeComponent.tenant_id == tenant_id,
                ).all()
            except Exception:
                pass

        # Aggregate signals from all selected files
        total_api_contracts = 0
        total_classes = 0
        total_data_models = 0
        has_router = False
        has_service = False

        for comp in comps:
            sa = comp.structured_analysis or {}
            api_contracts = sa.get("api_contracts", [])
            if isinstance(api_contracts, list):
                total_api_contracts += len(api_contracts)
            data_models = sa.get("data_model_relationships", [])
            if isinstance(data_models, list):
                total_data_models += len(data_models)
            components_list = sa.get("components", [])
            if isinstance(components_list, list):
                for c in components_list:
                    if isinstance(c, dict):
                        ctype = c.get("type", "")
                        if ctype in ("Class", "Model", "AbstractClass"):
                            total_classes += 1
                        if ctype in ("Router", "Controller", "Handler"):
                            has_router = True
                        if ctype in ("Service", "Manager"):
                            has_service = True

        # ── Two-file interaction ──────────────────────────────────────────────

        if n == 2 and all(s.get("type") in code_source_types for s in sources):
            if total_api_contracts > 0:
                return {
                    "recommended": "sequence_diagram",
                    "reason": f"One of these files contains {total_api_contracts} API endpoint(s). A sequence diagram will show the complete request flow between them.",
                    "alternatives": ["component_interaction_diagram", "class_diagram", "code_flow_diagram"],
                    "confidence": 0.88,
                }
            return {
                "recommended": "component_interaction_diagram",
                "reason": "With 2 files selected, a component interaction diagram reveals how they communicate: what they call, what data they exchange, and their dependency direction.",
                "alternatives": ["sequence_diagram", "class_diagram", "code_flow_diagram"],
                "confidence": 0.85,
            }

        # ── Single file ───────────────────────────────────────────────────────

        if n == 1:
            if total_api_contracts > 0 or has_router:
                return {
                    "recommended": "sequence_diagram",
                    "reason": f"This file contains {total_api_contracts} API endpoint(s). A sequence diagram shows the complete request/response lifecycle from client to database.",
                    "alternatives": ["api_data_flow", "code_flow_diagram", "class_diagram"],
                    "confidence": 0.90,
                }
            if total_classes >= 2:
                return {
                    "recommended": "class_diagram",
                    "reason": f"This file defines {total_classes} class(es) with relationships. A UML class diagram shows structure, attributes, methods, and inheritance.",
                    "alternatives": ["sequence_diagram", "code_flow_diagram", "component_spec"],
                    "confidence": 0.87,
                }
            if total_data_models > 0:
                return {
                    "recommended": "data_models",
                    "reason": f"This file contains {total_data_models} database model definition(s). An ER diagram shows entities, fields, and relationships.",
                    "alternatives": ["class_diagram", "component_spec"],
                    "confidence": 0.85,
                }
            return {
                "recommended": "code_flow_diagram",
                "reason": "This file is a utility or service module. A code flow diagram shows how data transforms through functions, decision branches, and external calls.",
                "alternatives": ["component_spec", "sequence_diagram", "class_diagram"],
                "confidence": 0.75,
            }

        # ── Multiple files (3+) ───────────────────────────────────────────────

        if n > 2:
            if total_api_contracts > 3:
                return {
                    "recommended": "architecture_diagram",
                    "reason": f"With {n} files containing {total_api_contracts} endpoints, an architecture diagram gives the best system-level overview.",
                    "alternatives": ["api_summary", "component_spec", "sequence_diagram"],
                    "confidence": 0.82,
                }
            return {
                "recommended": "component_spec",
                "reason": f"With {n} mixed sources, a component specification provides a comprehensive structured overview of all components.",
                "alternatives": ["architecture_diagram", "api_summary"],
                "confidence": 0.70,
            }

        # ── Documents / JIRA / Analysis ───────────────────────────────────────

        if "document" in source_types:
            return {
                "recommended": "brd",
                "reason": "Document sources are best analyzed as a Business Requirements Document.",
                "alternatives": ["component_spec", "test_cases"],
                "confidence": 0.75,
            }

        if "jira_item" in source_types:
            return {
                "recommended": "brd",
                "reason": "JIRA items contain requirements that are best structured as a BRD with acceptance criteria and functional requirements.",
                "alternatives": ["test_cases", "component_spec"],
                "confidence": 0.80,
            }

        # ── Default ───────────────────────────────────────────────────────────

        return {
            "recommended": "component_spec",
            "reason": "A component specification provides a comprehensive overview for the selected sources.",
            "alternatives": ["architecture_diagram", "api_summary"],
            "confidence": 0.60,
        }

    def get_discovered_endpoints(
        self, db: Session, tenant_id: int, repo_id: int | None = None, query: str = ""
    ) -> list[dict]:
        """
        Search all analyzed components' api_contracts for discovered endpoints.
        Returns a deduplicated list of {method, path, source_file, component_id}.
        """
        import re
        from app.models.code_component import CodeComponent

        comp_query = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.analysis_status == "completed",
            CodeComponent.structured_analysis.isnot(None),
        )
        if repo_id:
            comp_query = comp_query.filter(CodeComponent.repository_id == repo_id)

        comps = comp_query.all()

        seen: set[str] = set()
        results: list[dict] = []
        q_lower = query.lower()

        for comp in comps:
            sa = comp.structured_analysis or {}
            contracts = sa.get("api_contracts", [])
            if not isinstance(contracts, list):
                continue

            for contract in contracts:
                if not isinstance(contract, dict):
                    continue
                method = (contract.get("method", "") or "").upper()
                path = contract.get("endpoint", "") or contract.get("path", "")
                if not path:
                    continue

                key = f"{method}:{path}"
                if key in seen:
                    continue
                seen.add(key)

                label = f"{method} {path}" if method else path

                # Filter by query if provided
                if q_lower and q_lower not in label.lower():
                    continue

                results.append({
                    "method": method,
                    "path": path,
                    "label": label,
                    "description": contract.get("description", ""),
                    "source_file": comp.name or "",
                    "component_id": comp.id,
                    "repo_id": comp.repository_id,
                })

        # Sort: exact matches first, then alphabetical
        results.sort(key=lambda e: (
            0 if q_lower in e["path"].lower() else 1,
            e.get("path", ""),
        ))

        return results[:200]


auto_docs_service = AutoDocsService()
