# DokuDoc — Complete Feature Implementation Plan (v2)
## Product Owner + Solution Architect Blueprint

> **Revision notes from audit review:**
> - Feature 1.2: Email notifications scoped out (no SMTP infra); in-app only for MVP
> - Feature 1.3: Audit Dashboard redesigned as rich visual dashboard (see layout spec below)
> - Feature 1.4: Slash commands REMOVED from scope
> - Feature 1.5: In-dock approvals reclassified Medium effort; RAG pipeline change required
> - Feature 2.1: BRD generation specified as multi-step chunked orchestration, not single AI call
> - Feature 2.2: API key auth middleware added as cross-cutting concern; effort revised to 4–5 days
> - Feature 3.1: Integration providers phased by auth complexity; realistic per-provider estimate is 3–4 days
> - npm deps gap documented: recharts, mermaid, react-diff-viewer all NOT installed

---

## Context & Why This Matters

DokuDoc's core value proposition: **living documentation that stays in sync with code**. Every pending feature either removes friction from that loop (Integrations, Auto Docs) or deepens trust and governance (Version Comparison, Audit, Approvals). This plan executes all pending features in priority order — highest user-visible value first.

**Guiding principle:** Re-use existing patterns. The codebase has established templates for dashboards, modals, tables, and API calls. Every new screen follows those patterns exactly.

---

## Architectural Conventions (ALL features must follow these)

The codebase follows a strict **4-layer pattern**: `model → schema → crud → endpoint`. Every new feature must implement all 4 layers. Skip any layer and the endpoint will either have no type safety or bypass the data access abstraction.

**Schema pattern** (from `app/schemas/approval.py`):
```python
class FooCreate(BaseModel): ...           # input for POST/PUT
class FooUpdate(BaseModel): ...           # partial input for PATCH
class FooResponse(BaseModel):             # output from any endpoint
    class Config: from_attributes = True  # required for SQLAlchemy → Pydantic conversion
class FooStatsResponse(BaseModel): ...    # summary/analytics responses
```

**CRUD pattern** (from `app/crud/crud_notification.py`):
```python
class CRUDFoo:
    def create(self, db: Session, *, tenant_id, ...) -> Foo: ...
    def get_by_id(self, db: Session, *, id, tenant_id) -> Optional[Foo]: ...
    def get_multi(self, db: Session, *, tenant_id, skip, limit) -> List[Foo]: ...
    def update(self, db: Session, *, db_obj, update_data) -> Foo: ...
    def delete(self, db: Session, *, id, tenant_id) -> bool: ...
crud_foo = CRUDFoo()   # singleton at module level
```

**Sidebar navigation:** The sidebar items live in `/frontend/components/layout/Sidebar.tsx`, **not** `AppLayout.tsx`. `AppLayout.tsx` is a wrapper shell. All navigation additions go in `Sidebar.tsx`.

---

## New npm Dependencies Required

Before development starts, install these packages (none currently in `package.json`):

```bash
# In /frontend
npm install recharts mermaid react-diff-viewer
npm install --save-dev @types/react-diff-viewer
```

| Package | Used In | Why not custom |
|---------|---------|---------------|
| `recharts` | Audit Dashboard, Auto Docs | Production-grade chart library; hand-rolling charts is waste |
| `mermaid` | Auto Docs 2.1b | Mermaid diagram syntax rendering is non-trivial to implement |
| `react-diff-viewer` | Document Version Comparison | Diff rendering with line highlighting is complex; library handles edge cases |

---

## New Schemas, CRUD Files, and Permissions — Master Reference

### New Schema Files (`/backend/app/schemas/`)

**`document_version.py`**
```python
class DocumentVersionResponse(BaseModel):
    id: int; document_id: int; version_number: int
    content_hash: str; file_size: int
    uploaded_by_id: int; uploaded_by_email: str
    created_at: datetime
    class Config: from_attributes = True

class DocumentDiffRequest(BaseModel):
    version_a: int; version_b: int

class DocumentDiffResponse(BaseModel):
    version_a: int; version_b: int
    added: list[str]; removed: list[str]
    stats: dict  # {added_count, removed_count, change_pct}
```

**`notification_preference.py`**
```python
class NotificationPreferenceUpdate(BaseModel):
    analysis_complete: bool | None = None
    analysis_failed: bool | None = None
    validation_alert: bool | None = None
    mention: bool | None = None
    system: bool | None = None

class NotificationPreferenceResponse(BaseModel):
    id: int; user_id: int
    analysis_complete: bool; analysis_failed: bool
    validation_alert: bool; mention: bool; system: bool
    class Config: from_attributes = True
```

**`api_key.py`**
```python
class APIKeyCreate(BaseModel):
    name: str; scopes: list[str]; expires_at: datetime | None = None

class APIKeyResponse(BaseModel):          # used for LIST — no full key
    id: int; name: str; key_prefix: str; scopes: list[str]
    last_used_at: datetime | None; call_count_30d: int
    expires_at: datetime | None; is_active: bool; created_at: datetime
    class Config: from_attributes = True

class APIKeyCreateResponse(APIKeyResponse):
    full_key: str                          # ONLY returned on creation, never again

class APIKeyUsageResponse(BaseModel):
    id: int; last_used_at: datetime | None; call_count_30d: int
```

**`integration_config.py`**
```python
class NotionConnectRequest(BaseModel):
    api_key: str; workspace_name: str | None = None

class JiraConnectRequest(BaseModel):
    site_url: str; email: str; api_token: str

class IntegrationResponse(BaseModel):
    id: int; provider: str; auth_type: str; is_active: bool
    config_json: dict; last_sync_at: datetime | None; created_at: datetime
    class Config: from_attributes = True

class IntegrationPreviewItem(BaseModel):
    external_id: str; title: str; doc_type: str
    last_modified: datetime | None; url: str | None

class IntegrationSyncResponse(BaseModel):
    id: int; integration_id: int; status: str
    docs_found: int; docs_synced: int; docs_failed: int
    started_at: datetime; completed_at: datetime | None; error_message: str | None
    class Config: from_attributes = True
```

**`generated_doc.py`**
```python
class GeneratedDocRequest(BaseModel):
    force_regenerate: bool = False    # bypass cache if True

class GeneratedDocResponse(BaseModel):
    id: int; doc_type: str; title: str
    content_json: dict; mermaid_source: str | None
    input_token_count: int; cost_usd: float
    created_at: datetime; version: int
    cache_hit: bool    # was this served from cache?
    class Config: from_attributes = True
```

---

### New CRUD Files (`/backend/app/crud/`)

**`crud_document_version.py`** — `CRUDDocumentVersion`
- `create(db, *, document_id, content_text, content_hash, uploaded_by_id, file_size) → DocumentVersion`
- `get_by_document(db, *, document_id, tenant_id) → list[DocumentVersion]` — sorted by version_number desc
- `get_by_id(db, *, version_id, document_id) → DocumentVersion | None`
- `get_content(db, *, version_id) → str` — returns `content_text`
- `prune_old(db, *, document_id, keep_last_n=20)` — delete older versions beyond limit

**`crud_notification_preference.py`** — `CRUDNotificationPreference`
- `get_or_create_defaults(db, *, user_id, tenant_id) → NotificationPreference` — creates with all-True defaults on first call
- `update(db, *, user_id, tenant_id, update_data: dict) → NotificationPreference`
- `is_enabled(db, *, user_id, notification_type: str) → bool` — used by notification_service

**`crud_api_key.py`** — `CRUDAPIKey`
- `create(db, *, user_id, tenant_id, name, scopes, key_hash, key_prefix, expires_at) → APIKey`
- `get_by_user(db, *, user_id, tenant_id) → list[APIKey]`
- `verify_key(db, *, raw_key: str) → APIKey | None` — hash and compare
- `revoke(db, *, key_id, user_id, tenant_id) → bool`
- `update_usage(db, *, key_id)` — sets last_used_at, increments call_count_30d
- `reset_monthly_counts(db)` — called by Celery beat task on 1st of month

**`crud_integration.py`** — `CRUDIntegration`
- `create(db, *, tenant_id, provider, auth_type, credentials_encrypted, config_json, created_by_id) → IntegrationConfig`
- `get_by_tenant(db, *, tenant_id) → list[IntegrationConfig]`
- `get_by_id(db, *, id, tenant_id) → IntegrationConfig | None`
- `update_last_sync(db, *, id) → IntegrationConfig`
- `delete(db, *, id, tenant_id) → bool`

**`crud_integration_sync.py`** — `CRUDIntegrationSync`
- `create(db, *, integration_id, celery_task_id) → IntegrationSync` — initial status="running"
- `update_status(db, *, sync_id, status, docs_found, docs_synced, docs_failed, error_message) → IntegrationSync`
- `list_by_integration(db, *, integration_id, limit=20) → list[IntegrationSync]`

**`crud_generated_doc.py`** — `CRUDGeneratedDoc`
- `create(db, *, tenant_id, doc_type, title, content_json, mermaid_source, input_token_count, cost_usd, cache_key, **optional_ids) → GeneratedDoc`
- `get_cached(db, *, cache_key: str, tenant_id: int) → GeneratedDoc | None` — cache lookup
- `get_latest(db, *, doc_type, tenant_id, **filter_ids) → GeneratedDoc | None`
- `list_by_entity(db, *, entity_type, entity_id, tenant_id) → list[GeneratedDoc]`
- `increment_version(db, *, doc_type, **filter_ids) → int` — returns next version number

---

### New Permission Enum Values

Add to `/backend/app/core/permissions.py`:
```python
# Integration Permissions
INTEGRATION_MANAGE = "integration:manage"   # connect/disconnect integrations
INTEGRATION_SYNC = "integration:sync"       # trigger sync operations

# API Key Permissions
API_KEY_MANAGE = "api_key:manage"           # create/revoke own API keys

# Auto Docs Permissions
AUTO_DOCS_GENERATE = "auto_docs:generate"   # trigger AI generation (costs credits)
AUTO_DOCS_VIEW = "auto_docs:view"           # view generated docs

# Extended Audit Permissions (AUDIT_VIEW and AUDIT_EXPORT already exist)
AUDIT_ANALYTICS = "audit:analytics"         # view security insights + anomaly panel
AUDIT_COMPLIANCE = "audit:compliance"       # download compliance report

# Notification Preferences
NOTIFICATION_PREFS_MANAGE = "notification_prefs:manage"
```

**Role assignments** (add to role definitions):
| Permission | Developer | BA | CXO | Admin | Auditor |
|-----------|-----------|-----|-----|-------|---------|
| `INTEGRATION_MANAGE` | ✓ | ✓ | ✓ | ✓ | — |
| `INTEGRATION_SYNC` | ✓ | ✓ | ✓ | ✓ | — |
| `API_KEY_MANAGE` | ✓ | — | — | ✓ | — |
| `AUTO_DOCS_GENERATE` | ✓ | ✓ | ✓ | ✓ | — |
| `AUTO_DOCS_VIEW` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `AUDIT_ANALYTICS` | — | — | ✓ | ✓ | ✓ |
| `AUDIT_COMPLIANCE` | — | — | ✓ | ✓ | ✓ |
| `NOTIFICATION_PREFS_MANAGE` | ✓ | ✓ | ✓ | ✓ | ✓ |

---

### Progress Tracking for Long-Running Operations

**Pattern:** Reuse the existing polling approach used by document analysis.

All async operations (BRD generation, integration syncs) return immediately:
```json
{"task_id": "celery-uuid-...", "status": "processing", "estimated_seconds": 45}
```

Frontend polls `GET /api/v1/tasks/{task_id}/status` every 3 seconds until `status === "completed"` or `"failed"`. This endpoint already exists — reuse it.

For integration syncs, also poll `GET /api/v1/integrations/{id}/sync-history?limit=1` to get latest sync record.

**Do NOT implement WebSockets or SSE** — the existing polling pattern is sufficient and consistent.

---

## Implementation Phases

### PHASE 1 — Quick Wins & UX Completeness (Sprint 1–2)
*Complete partial features that users already expect*

### PHASE 2 — Core Value Features (Sprint 3–4)
*AI-powered features that justify the platform*

### PHASE 3 — Enterprise & Integrations (Sprint 5–8)
*External data sources and developer API access*

---

## PHASE 1 — Quick Wins

---

### Feature 1.1: Document Version Comparison UI
**Module 3 | Priority: HIGH | Effort: 3 days**

**Why:** Users upload updated documents but can't see what changed. Without a diff view, document governance is blind.

**What to build:**
- Version history tab on the document detail page (`/dashboard/documents/[id]`)
- Side-by-side diff viewer comparing two selected versions
- Change indicators: added (green), removed (red), modified (amber)
- "Restore to version" action

**New npm install:** `react-diff-viewer` (see dependency section above)

**Backend — `/backend/app/api/endpoints/documents.py`:**
```python
GET  /api/v1/documents/{id}/versions               # list versions: [{version_number, uploaded_by, created_at, file_size, content_hash}]
GET  /api/v1/documents/{id}/versions/{ver_id}      # get text content of one version
POST /api/v1/documents/{id}/versions/diff          # body: {version_a: int, version_b: int}
                                                   # returns: {added: [str], removed: [str], stats: {added_count, removed_count}}
POST /api/v1/documents/{id}/versions/{ver_id}/restore  # restore to version
```

**New model — `/backend/app/models/document_version.py`:**
```python
class DocumentVersion(Base):
    id: int
    document_id: int                    # FK → Document
    version_number: int
    content_text: str                   # full extracted text at this version
    content_hash: str                   # sha256 for change detection
    uploaded_by_id: int                 # FK → User
    file_size: int
    created_at: datetime
```

Diff computation: `difflib.unified_diff(old_lines, new_lines)` server-side. Return structured JSON so frontend can render without additional processing.

**New Alembic migration:** `s8a3_add_document_versions.py`

**Frontend — `/frontend/app/dashboard/documents/[id]/page.tsx`:**

**Upload New Version (prerequisite for version comparison to work):**
- Add "Upload New Version" button in the document detail header alongside existing actions
- Reuse the existing upload dialog — just pass `parent_document_id` in the POST body
- Backend auto-increments version number (`max(version_number) + 1` for this document)
- On upload complete: refresh version list, trigger re-analysis

**Version History Tab:**
- Add "Version History" tab to existing tab bar
- New component: `/frontend/components/documents/VersionHistoryPanel.tsx`
  - Sorted list: version number, timestamp, uploader badge, file size
  - "Compare" button: user selects version A then version B → opens diff modal
  - "Restore" button on past versions → confirmation dialog → `POST /versions/{id}/restore`
- New component: `/frontend/components/documents/VersionDiffModal.tsx`
  - Uses `react-diff-viewer` in split/unified view
  - Stats bar: "+X added  −Y removed"
  - "Restore this version" button at bottom

---

### Feature 1.2: Notification Preferences (In-App Only)
**Module 10 | Priority: MEDIUM | Effort: 1 day**

**Why:** Notification fatigue kills adoption. Users need to control which event types appear in their notification feed.

**Scope:** In-app notification filtering only. Email is OUT OF SCOPE for MVP — there is no SMTP infrastructure. Email toggles are deferred to Phase 2 when an email service is wired up.

**Backend — new model `/backend/app/models/notification_preference.py`:**
```python
class NotificationPreference(Base):
    id: int
    tenant_id: int
    user_id: int                           # FK → User (unique per user)
    analysis_complete: bool = True         # show in-app notifications for this type?
    analysis_failed: bool = True
    validation_alert: bool = True
    mention: bool = True
    system: bool = True
    # Future Phase 2 fields (do NOT add now):
    # email_enabled: bool
    # digest_frequency: str
```

**Backend — new endpoints in `/backend/app/api/endpoints/notifications.py`:**
```python
GET /api/v1/notification-preferences       # returns prefs; creates defaults on first call
PUT /api/v1/notification-preferences       # body: {analysis_complete: bool, ...}
```

**Backend — `/backend/app/services/notification_service.py`:**
- In the `create_notification()` function, before persisting, query `NotificationPreference` for the target user
- If the relevant type is `False`, skip creating the notification record entirely

**New Alembic migration:** `s8a4_add_notification_preferences.py`

**Frontend — `/frontend/app/settings/page.tsx`:**
- New `NotificationPreferencesCard` section below existing settings cards
- Toggle grid using shadcn `Switch` component — one row per notification type
- Pattern: `api.get("/notification-preferences")` on mount → `api.put(...)` on each toggle change (debounced 500ms)
- No submit button — auto-save on toggle (same pattern as other preference switches)

---

### Feature 1.3: Security / Audit Dashboard — Rich Visual Layout
**Module 2 | Priority: MEDIUM | Effort: 2 days**

**Why:** Enterprise buyers need a dedicated security overview with visual signals — not just a raw log list.

**What's already built (do NOT duplicate):**
- `GET /api/v1/audit/stats` → total events, creates, updates, deletes (already rendered as stat cards)
- `GET /api/v1/audit/logs` → cursor-paginated event list (already rendered as table)
- `GET /api/v1/audit/export` and `GET /api/v1/audit/export/pdf` → already exist

**What is genuinely NEW:**

**Backend — 3 new endpoints in `/backend/app/api/endpoints/audit.py`:**
```python
GET /api/v1/audit/analytics
# Returns: {
#   daily_counts: [{date: str, count: int}],   # last 14 days
#   action_breakdown: {create: int, update: int, delete: int, login: int},
#   top_users: [{user_id, name, event_count}],  # top 5 by activity
#   busiest_hour: int                           # 0-23
# }

GET /api/v1/audit/anomalies
# Returns: {
#   repeated_failures: [{user_id, name, count, last_attempt}],  # >5 failed actions in 1h
#   off_hours_access: [{user_id, name, hour, date}],            # access between 22:00-06:00
#   bulk_deletes: [{user_id, name, count, date}]                # >10 deletes in 1h
# }

GET /api/v1/audit/compliance-report
# Returns: structured JSON for SOC2/ISO27001 template fields:
# {period: str, total_events, unique_users, failed_actions, admin_actions, data_exports, anomaly_count}
# Frontend downloads as JSON; no PDF rendering needed (deferred to Phase 2)
```

**Frontend — `/frontend/app/dashboard/audit-trail/page.tsx` redesign:**

The page is restructured into 3 visual zones:

**Zone 1 — Header KPI Row** (existing stat cards, keep as-is)
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Total Events │   Creates    │   Updates    │   Deletes    │
│    2,451     │     891      │    1,203     │     357      │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

**Zone 2 — Security Insights Panel** (NEW — collapsible section above log table)
```
┌────────────────────────────────────────────────────────────────────────────┐
│  Security Insights                                        [Collapse ▲]     │
│                                                                            │
│  ┌─── Activity (Last 14 Days) ────────────┐  ┌─── Action Mix ───────────┐ │
│  │  [recharts BarChart: date vs count]    │  │  [recharts PieChart]     │ │
│  │  bars colored by action type           │  │  Create/Update/Delete    │ │
│  └────────────────────────────────────────┘  └──────────────────────────┘ │
│                                                                            │
│  ┌─── Anomaly Alerts ─────────────────────────────────────────────────────┐ │
│  │  🔴 3 repeated failures   — john.doe@acme.com  (last: 14 min ago)     │ │
│  │  🟡 Off-hours access      — sarah.k@acme.com   (02:14 AM yesterday)   │ │
│  │  🔴 Bulk delete detected  — admin@acme.com     (47 deletes in 30 min) │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─── Top Active Users ────────────────────────────────────────────────────┐ │
│  │  Name           │ Events │ Last Active    │ Role       │               │ │
│  │  john.doe       │   312  │ 2 min ago      │ Developer  │               │ │
│  │  sarah.k        │   198  │ 1 hr ago       │ BA         │               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  [Download Compliance Report JSON]                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

**Zone 3 — Log Table** (existing table, unchanged — just repositioned below Zone 2)

**New component:** `/frontend/components/audit/SecurityInsightsPanel.tsx`
- Fetches `GET /audit/analytics` and `GET /audit/anomalies` in parallel on mount
- Uses `recharts` `BarChart` and `PieChart` (new dependency)
- Anomaly alerts displayed as colored alert rows (red/amber) using existing shadcn `Alert` component
- "Download Compliance Report JSON" → `GET /audit/compliance-report` → `JSON.stringify(data, null, 2)` → `Blob` download

---

### Feature 1.4: AskyDoc Slash Commands (Re-added)
**Module 13 | Priority: HIGH | Effort: 3 days**

**Why:** Power users expect command shortcuts. Without discoverable commands, users don't know what AskyDoc can do. The Help & Support module (Feature 1.7) will include a full slash command reference guide.

**Architecture — two-tier (addresses earlier raised concern):** Simple commands skip the RAG pipeline entirely. AI-powered commands reuse it with a directive hint.

**Backend — new endpoint in `/backend/app/api/endpoints/chat.py`:**
```python
POST /api/v1/chat/conversations/{id}/command
# body: {command: str, args: str}
# Handles ONLY: /help, /status, /export, /search, /pending
# Returns same ChatMessageResponse format — NO billing, NO RAG
```

For AI-powered commands (`/summarize`, `/analyze`, `/compare`), detect early in `send_message()` and inject a directive before RAG:
```python
SIMPLE_COMMANDS = {"/help", "/status", "/export", "/search", "/pending"}
if message.content.startswith("/"):
    command, *args = message.content.split(" ", 1)
    if command in SIMPLE_COMMANDS:
        return await _handle_simple_command(command, args, db, tenant_id, user_id)
    # AI commands: inject hint and fall through to normal RAG
    message.system_hint = COMMAND_HINTS.get(command, "")
```

**Commands to implement:**

| Command | Type | Backend | Description |
|---------|------|---------|-------------|
| `/help` | Simple | `/command` | Show all commands with examples |
| `/status` | Simple | `/command` | Docs count, analyses, pending items |
| `/export` | Simple | `/command` | Export current conversation |
| `/search [query]` | Simple | `/command` | Semantic search, top 5 results |
| `/pending` | Simple | `/command` | List user's pending approvals |
| `/summarize [doc name]` | AI-RAG | `send_message` | Summarize document by name |
| `/analyze [component]` | AI-RAG | `send_message` | Analyze code component |
| `/compare [A] vs [B]` | AI-RAG | `send_message` | Compare two docs or components |

**Doc name resolution** for `/summarize`/`/compare`: if multiple docs match, return top 3 choices as a numbered list. User replies "1", "2", or "3" to select.

**New schema — add to `/backend/app/schemas/conversation.py`:**
```python
class CommandRequest(BaseModel):
    command: str    # "/help"
    args: str = ""  # text after command

# Returns standard ChatMessageResponse (no new response schema needed)
```

**Frontend — `/frontend/app/dashboard/chat/page.tsx`:**
- Detect `/` as first character in textarea → show `SlashCommandPalette`
- New component: `/frontend/components/chat/SlashCommandPalette.tsx`
  - Keyboard navigation (↑↓, Enter to select, Esc to dismiss)
  - Filter by typing after `/` (e.g. `/su` → shows `/summarize`)
  - Each row: command + short description + example
  - Fills command template into textarea
- Simple commands POST to `/command`; AI commands POST to `/messages`
- `/help` response includes link: "View full reference → Help & Docs"

---

### Feature 1.5: AskyDoc Chat Response Formatting (ChatGPT-style)
**Module 13 | Priority: HIGH | Effort: 1–2 days**

**Why (from screenshot):** AI responses currently render as a wall of plain text. Markdown markers (`**bold**`, headers, bullet points) are either stripped or unstyled. The result is unreadable for long analytical responses. This must look and feel like ChatGPT — with visual hierarchy, numbered lists, bold labels, code blocks, and proper paragraph spacing.

**Root cause (two parts):**
1. **Frontend:** `react-markdown` is installed but either not applied to AI responses, or applied without typography/prose styling.
2. **Backend:** The AI system prompt may not instruct the model to always respond in rich markdown. Even if it does, the frontend ignores the structure.

**Backend — `/backend/app/services/ai/prompt_manager.py` (or system prompt location):**

Find the base system prompt for AskyDoc and add explicit markdown formatting instruction:
```python
SYSTEM_PROMPT_SUFFIX = """
Always format your responses using rich Markdown:
- Use ## and ### headings to organize sections
- Use **bold** for key terms, labels, and risk indicators
- Use bullet points (-) for lists of items
- Use numbered lists (1. 2. 3.) for sequential steps or ranked items
- Use > blockquotes to highlight critical warnings or key insights
- Use `inline code` for file names, function names, and technical identifiers
- Use ```language code blocks for multi-line code
- Separate sections with blank lines for readability
- Never output a wall of plain text — always structure your response
"""
```

**Frontend — `/frontend/app/dashboard/chat/page.tsx`:**

The AI message bubble must pass response content through a styled markdown renderer, not raw text.

**Step 1:** Ensure all AI response messages use `react-markdown`:
```tsx
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'   // GitHub Flavored Markdown: tables, strikethrough, task lists

// In message render:
<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  components={markdownComponents}
>
  {message.content}
</ReactMarkdown>
```

**Note:** `remark-gfm` needs to be installed: `npm install remark-gfm` (it's a companion to `react-markdown` which IS installed).

**Step 2:** Create `markdownComponents` object with Tailwind-styled overrides:
```tsx
// New file: /frontend/components/chat/MarkdownRenderer.tsx

const markdownComponents = {
  h1: ({children}) => <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900">{children}</h1>,
  h2: ({children}) => <h2 className="text-lg font-bold mt-4 mb-2 text-gray-800 border-b border-gray-200 pb-1">{children}</h2>,
  h3: ({children}) => <h3 className="text-base font-semibold mt-3 mb-1 text-gray-800">{children}</h3>,
  p:  ({children}) => <p className="mb-3 leading-relaxed text-gray-700">{children}</p>,
  ul: ({children}) => <ul className="list-disc pl-5 mb-3 space-y-1 text-gray-700">{children}</ul>,
  ol: ({children}) => <ol className="list-decimal pl-5 mb-3 space-y-1 text-gray-700">{children}</ol>,
  li: ({children}) => <li className="leading-relaxed">{children}</li>,
  strong: ({children}) => <strong className="font-semibold text-gray-900">{children}</strong>,
  em: ({children}) => <em className="italic text-gray-700">{children}</em>,
  blockquote: ({children}) => (
    <blockquote className="border-l-4 border-blue-400 pl-4 py-1 my-3 bg-blue-50 text-blue-900 rounded-r-md">
      {children}
    </blockquote>
  ),
  code: ({inline, children, className}) =>
    inline
      ? <code className="bg-gray-100 text-rose-600 px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>
      : <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 my-3 overflow-x-auto text-sm font-mono">
          <code>{children}</code>
        </pre>,
  table: ({children}) => (
    <div className="overflow-x-auto my-3">
      <table className="min-w-full border-collapse border border-gray-200 text-sm">{children}</table>
    </div>
  ),
  th: ({children}) => <th className="border border-gray-300 bg-gray-50 px-3 py-2 font-semibold text-left">{children}</th>,
  td: ({children}) => <td className="border border-gray-200 px-3 py-2 text-gray-700">{children}</td>,
  hr: () => <hr className="my-4 border-gray-200" />,
}
```

**Visual result (what the screenshot should look like after fix):**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  Key Strategic Concerns for DokyDoc B2B SaaS                           │
│  ─────────────────────────────────────────────                          │
│                                                                         │
│  ## 1. Scalability and Performance under Multi-Tenant Load              │
│                                                                         │
│  **Implication:** While multi-tenancy is implemented...                 │
│                                                                         │
│  > ⚠ Risk: Slow performance can lead to customer churn                 │
│                                                                         │
│  ## 2. Robust Data Security and Tenant Isolation                        │
│                                                                         │
│  **Implication:** For B2B clients, data security...                     │
│  - `tenant_id` requirements enforced on all queries                     │
│  - Security audit validates no data leakage                             │
│                                                                         │
│  > ⚠ Risk: A single incident could lead to financial penalties         │
│                                                                         │
│  ## 3. Compliance and Data Governance                                   │
│  ...                                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Additional UX improvements to match ChatGPT:**
- Message bubble max-width: `max-w-3xl` (not full-width stretch)
- AI messages: white background, subtle left border accent, no bubble outline
- User messages: keep existing purple/blue bubble
- Add smooth scroll-to-bottom on new message
- Copy button (already exists per exploration) — keep it
- Add "Regenerate response" button on last AI message (calls API with same prompt)

**New file:** `/frontend/components/chat/MarkdownRenderer.tsx` — exports the `MarkdownRenderer` component that wraps ReactMarkdown with all styled components above.

---

### Feature 1.5 (renumbered from 1.4): AskyDoc In-Dock Approve/Reject
**Module 13 | Priority: MEDIUM | Effort: 3 days** *(revised from Small)*

**Why:** When AskyDoc surfaces a pending approval in a response, the user must leave chat to act on it. This breaks the conversational flow.

**The gap:** Approvals are currently not part of the RAG retrieval pipeline. `rag_service.retrieve_context()` must be modified to also fetch relevant pending approvals.

**Backend — Step 1: Update `/backend/app/services/rag_service.py`:**

In the `RetrievedContext` dataclass, add:
```python
@dataclass
class RetrievedContext:
    # ... existing fields ...
    pending_approvals: list[dict] = field(default_factory=list)
    # [{id, entity_type, entity_id, entity_name, status, level, created_at}]
```

In `retrieve_context()`, add a new retrieval stage after existing stages:
```python
# Stage N: Fetch pending approvals relevant to conversation context
pending_approvals = db.query(Approval).filter(
    Approval.tenant_id == tenant_id,
    Approval.status == "pending",
    Approval.assignee_id == user_id      # only approvals assigned to this user
).order_by(Approval.created_at.desc()).limit(5).all()
context.pending_approvals = [approval.to_dict() for approval in pending_approvals]
```

**Backend — Step 2: Update `/backend/app/api/endpoints/chat.py`:**

In `ChatMessageResponse`, add:
```python
approval_references: list[dict] = []   # populated from context.pending_approvals
```

In `send_message()`, after generating the AI response, populate:
```python
response.approval_references = context.pending_approvals
```

Existing approval action endpoints are already complete:
- `POST /api/v1/approvals/{id}/approve`
- `POST /api/v1/approvals/{id}/reject`

**Frontend — `/frontend/app/dashboard/chat/page.tsx`:**
- In message rendering loop, check `message.approval_references`
- If `approval_references.length > 0` and any have `status === "pending"`, render `InlineApprovalActions` below the message bubble

**New component — `/frontend/components/chat/InlineApprovalActions.tsx`:**
```
┌─────────────────────────────────────────────────────────────────┐
│  📋 Pending Approvals                                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ "API Auth Module" — Code Component · L1 Peer Review        ││
│  │         [✓ Approve]  [✗ Reject]  [→ View Details]          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```
- On Approve: `api.post("/approvals/{id}/approve")` → optimistic UI update → success toast
- On Reject: opens mini-modal for rejection reason → `api.post("/approvals/{id}/reject", {reason})`
- On View: `router.push("/dashboard/approvals")`
- After action: button state updates to "Approved ✓" / "Rejected ✗" (disabled)

---

### Feature 1.7: Help & Support Module (New)
**New Module | Priority: HIGH | Effort: 2 days**

**Why:** As slash commands, Auto Docs, and Integrations are added, users need a discoverable reference guide. Without documentation inside the app, users email support or churn. This module is the self-service layer.

**Route:** `/dashboard/help` — new page in sidebar

**Sections:**

#### 1. Slash Command Reference
The primary reason for this module — users need to discover and learn commands.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  AskyDoc Slash Commands                                                  │
├──────────────┬──────────────────────────────┬────────────────────────────┤
│  Command     │ Description                  │ Example                    │
├──────────────┼──────────────────────────────┼────────────────────────────┤
│  /help       │ Show all available commands   │ /help                      │
│  /status     │ System health & counts        │ /status                    │
│  /search     │ Semantic search               │ /search "auth flow"        │
│  /export     │ Export conversation           │ /export                    │
│  /pending    │ List pending approvals        │ /pending                   │
│  /summarize  │ Summarize a document          │ /summarize Requirements.pdf│
│  /analyze    │ Analyze a code component      │ /analyze AuthService       │
│  /compare    │ Compare two items             │ /compare v1.pdf vs v2.pdf  │
└──────────────┴──────────────────────────────┴────────────────────────────┘
```

Each command row: expandable to show full usage guide, expected output, tips.

#### 2. Getting Started Guide
Step-by-step onboarding flow with checkboxes:
- [ ] Upload your first document
- [ ] Connect a code repository
- [ ] Run your first analysis
- [ ] Ask AskyDoc a question
- [ ] Generate your first BRD
- [ ] Connect an external integration

Progress tracker: "You've completed 3 of 6 setup steps" — drives adoption.

#### 3. Feature Reference Cards

Grid of feature cards — one per module:
```
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  📄 Documents  │  │  💻 Code       │  │  🤖 AskyDoc   │
│  Upload, tag,  │  │  Sync, compare,│  │  Chat, slash   │
│  version diff  │  │  analyze code  │  │  commands, RAG │
│  [Learn More]  │  │  [Learn More]  │  │  [Learn More]  │
└────────────────┘  └────────────────┘  └────────────────┘
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  📊 Auto Docs  │  │  🔗 Integrat. │  │  🔑 API Keys  │
│  BRD, specs,   │  │  Notion, Jira, │  │  CI/CD access, │
│  arch diagrams │  │  Confluence    │  │  scopes, usage │
│  [Learn More]  │  │  [Learn More]  │  │  [Learn More]  │
└────────────────┘  └────────────────┘  └────────────────┘
```

#### 4. FAQ
Collapsible accordion — common questions:
- "How does document analysis work?"
- "What file types are supported?"
- "How are costs calculated?"
- "How do I give a teammate access?"
- "What's the difference between an Initiative and a Repository?"
- "How do I use slash commands in AskyDoc?"
- "Why did my analysis fail?"

#### 5. Keyboard Shortcuts Reference
Table of global shortcuts (if any exist in the app).

#### 6. What's New / Changelog
Simple list of recent features added — version-stamped entries. Hardcoded initially; can be dynamic later.

#### 7. Contact Support
- "Report a Bug" → opens a modal with description textarea → triggers an API call (or mailto: fallback)
- "Request a Feature" → external link
- "Documentation" → external link (if external docs site exists)

**Backend (minimal):**
- No new endpoints needed for static content
- Optional: `POST /api/v1/support/bug-report` — body: `{description, page_url, severity}` → creates an internal ticket or sends email notification to admin

**Frontend — `/frontend/app/dashboard/help/page.tsx` (new page):**
- Tabbed layout: Commands | Getting Started | Features | FAQ | What's New | Support
- All content is static/hardcoded initially (can be CMS-driven in future)
- Getting Started checklist: checks actual user activity via `GET /api/v1/audit/logs` to determine which steps are complete
- Sidebar link "Help & Docs" added at bottom of sidebar (below all feature links)

**Sidebar update in `/frontend/components/layout/Sidebar.tsx`:**
- Add "Help & Docs" link at the very bottom with a `?` or `BookOpen` icon — always visible regardless of role

---

## PHASE 2 — Core Value Features

---

### Feature 2.1: Auto Docs (Module 12) — THE KILLER FEATURE
**Module 12 | Priority: CRITICAL | Effort: 9 days total**

**Why:** Users upload code → DokuDoc generates professional documentation automatically. Primary product differentiator.

---

**Sprint split for Auto Docs:**
- **Sprint 2 (lower AI complexity):** 2.1a Component Spec + 2.1b Architecture Graph + 2.1c API Summary
- **Sprint 3 (multi-step orchestration):** 2.1g BRD Generator + 2.1f Change Summary + 2.1e Test Cases + 2.1d Data Models

---

#### AI Orchestration Pattern (applies to all 2.1 sub-features)

All generation endpoints follow this pattern. **Do not shortcut this.**

```python
# In /backend/app/services/document_generation_service.py

async def generate_with_chunking(
    content_chunks: list[str],
    prompt_template: str,
    merge_prompt: str,
    max_tokens_per_chunk: int = 4000
) -> str:
    """
    Multi-step AI generation for large content sets:
    1. Process each chunk individually with prompt_template
    2. Merge all chunk outputs using merge_prompt
    3. Return final structured output
    """
```

**Token budget rule:** Each chunk ≤ 4,000 tokens input. If initiative has 20 documents × 5,000 tokens each = 100k tokens total → split into 25 chunks, generate partial BRDs, then merge.

**Cost estimation:** Before any generation, call `/billing/estimate` with `{feature_type: "brd_generation", input_tokens: N}`. If cost exceeds tenant credit threshold, return `402` with estimated cost — let user confirm before proceeding.

**Rate limiting for generation endpoints:** Use existing `rate_limiter.py` middleware. Apply limit: **5 generations per user per hour** per `doc_type`. Return `429` with headers:
```
Retry-After: 3600
X-Remaining-Generations: 0
X-Rate-Limit-Reset: 2026-03-17T15:00:00Z
```
Limit is stored in Redis: key `gen_rate:{user_id}:{doc_type}:{hour_bucket}`, TTL = 3600s.

**Caching for generated docs:** Before making any AI call, compute a `cache_key`:
```python
cache_key = sha256(f"{doc_type}:{entity_id}:{input_data_hash}:{template_version}")
# input_data_hash = hash of component analysis JSON / ontology snapshot / document text
```
Query `crud_generated_doc.get_cached(db, cache_key=cache_key, tenant_id=tenant_id)`. If found, return cached doc with `cache_hit: true` — **no AI call, no billing charge**.

`force_regenerate: true` in `GeneratedDocRequest` bypasses the cache (used by "Regenerate" button in UI).

**Prompt template registration:** Each generation type registers a named template in `prompt_manager.py`:
- `"component_spec"` — input: component analysis JSON, output: structured spec
- `"architecture_diagram"` — input: ontology nodes/edges, output: Mermaid source
- `"api_summary"` — input: endpoint list from code analysis, output: developer docs
- `"data_models"` — input: model definitions, output: ER-style documentation
- `"test_cases"` — input: function signatures + docstrings, output: test scenario list
- `"change_summary"` — input: two AnalysisRun diffs, output: human-readable summary
- `"brd_section"` — input: document chunk, output: BRD sub-section (used in chunking)
- `"brd_merge"` — input: list of BRD sub-sections, output: final BRD document

**New Alembic migration:** `s8a5_add_generated_docs.py`
```python
class GeneratedDoc(Base):
    id: int
    tenant_id: int
    initiative_id: int | None
    repository_id: int | None
    component_id: int | None
    doc_type: str        # "component_spec"|"architecture"|"api_summary"|"data_models"|"test_cases"|"change_summary"|"brd"
    title: str
    content_json: JSON   # structured output
    mermaid_source: str | None
    input_token_count: int
    cost_usd: float
    created_at: datetime
    created_by_id: int
    version: int         # increment on regeneration
```

---

#### 2.1a: Component Spec Generator

**Route:** `/dashboard/auto-docs/component/[id]`

**Backend:** `POST /api/v1/code-components/{id}/generate/spec`
1. Fetch `CodeComponent` + its `AnalysisResult` + related `OntologyConcept` records
2. Estimate tokens → check billing → return 402 if insufficient
3. Build single prompt (component is already small enough for one call)
4. Prompt template `"component_spec"` → returns:
   ```json
   {
     "purpose": "...",
     "inputs": [{"name": "...", "type": "...", "description": "..."}],
     "outputs": [...],
     "dependencies": [...],
     "usage_examples": ["..."],
     "edge_cases": ["..."]
   }
   ```
5. Save to `GeneratedDoc` table, return doc

**Frontend:** Tab page with sections: Overview | API Contract | Dependencies | Examples | Edge Cases

---

#### 2.1b: Architecture Graph (Mermaid)

**Route:** `/dashboard/auto-docs/architecture/[repo_id]`

**New npm install:** `mermaid` (see dependency section)

**Backend:** `POST /api/v1/repositories/{id}/generate/diagram`
1. Fetch all `OntologyConcept` + `OntologyRelationship` for the repo (already in DB)
2. Convert graph to Mermaid flowchart format directly (no AI needed for basic structure):
   ```python
   def ontology_to_mermaid(concepts, relationships) -> str:
       lines = ["flowchart TD"]
       for concept in concepts:
           lines.append(f'  {concept.id}["{concept.name}"]')
       for rel in relationships:
           lines.append(f'  {rel.source_id} -->|"{rel.relationship_type}"| {rel.target_id}')
       return "\n".join(lines)
   ```
3. For "AI-enhanced" diagram: optionally pass the Mermaid source through the `"architecture_diagram"` prompt to add meaningful labels and grouping
4. Returns: `{mermaid_source: str, concept_count: int, relationship_count: int}`

**Frontend:**
- Renders Mermaid via `import mermaid from "mermaid"` with `useEffect`
- Diagram rendered into a `<div ref={mermaidRef}>` element
- Controls: Copy Source | Download PNG (via canvas) | Fullscreen
- Fallback: if Mermaid render fails, show raw source in code block

---

#### 2.1c: API Summary Generator

**Route:** `/dashboard/auto-docs/api/[repo_id]`

**Backend:** `POST /api/v1/repositories/{id}/generate/api-summary`
1. Fetch all `CodeComponent` records for repo where `analysis_result.endpoints` is populated
2. Chunk by endpoint group (controller/route file = one chunk)
3. AI prompt `"api_summary"` per chunk → structured endpoint doc
4. Merge: flatten all endpoint docs into one sorted list
5. Returns: `{endpoints: [{method, path, summary, params: [], responses: [], example_request, example_response}]}`

**Frontend:** Swagger-lite reference UI — grouped by path prefix, collapsible sections per endpoint

---

#### 2.1d: Data Models Generator

**Backend:** `POST /api/v1/repositories/{id}/generate/data-models`
1. Fetch code components tagged as models/schemas from analysis
2. AI prompt `"data_models"` → returns: `{models: [{name, fields: [{name, type, nullable, description}], relationships: [{target, type}]}]}`

**Frontend:** Card grid — one card per model with field table + relationship arrows (CSS only, no D3)

---

#### 2.1e: Test Case Suggestions

**Backend:** `POST /api/v1/code-components/{id}/generate/test-cases`
1. Fetch component analysis (functions, parameters, return types, edge cases from analysis)
2. AI prompt `"test_cases"` → returns: `[{test_name, scenario, input_fixture, expected_output, test_type: "unit|integration|edge"}]`

**Frontend:** Card list
- Filter by type (unit / integration / edge)
- "Copy as pytest" → generates Python test function string
- "Copy as Jest" → generates JavaScript describe/it block string

---

#### 2.1f: Change Summary (Graph Diff)

**Backend:** `GET /api/v1/repositories/{id}/change-summary?from_run={id}&to_run={id}`
1. Fetch two `AnalysisRun` records + their associated `CodeComponent` and `OntologyConcept` snapshots
2. Diff the two sets: new, removed, modified items
3. AI prompt `"change_summary"` to convert raw diff to human-readable narrative
4. Returns: `{summary_text: str, new_components: [], removed_components: [], modified_components: [], new_concepts: [], removed_concepts: []}`

**Frontend:** Timeline-style diff view — green badge for added, red for removed, amber for changed

---

#### 2.1g: Unified BRD Generator — Multi-Step Orchestration

**Route:** `/dashboard/auto-docs/brd/[initiative_id]`

**Backend:** `POST /api/v1/initiatives/{id}/generate/brd`

This is the most complex generation task. Full orchestration:
```
1. Fetch all linked Documents + their extracted text
2. Fetch all linked Repositories + their AnalysisResults
3. Estimate total tokens → enforce billing check (402 if insufficient)
4. Chunk documents: each chunk ≤ 4,000 tokens
5. For each chunk: run prompt "brd_section" → returns partial BRD JSON
   {requirements: [], actors: [], workflows: [], constraints: []}
6. Merge all partial BRDs: run prompt "brd_merge" with all sections concatenated
7. Structure final BRD:
   {
     title, executive_summary,
     functional_requirements: [{id, description, priority, source_doc}],
     technical_architecture: {components: [], integrations: [], data_flows: []},
     data_models: [{name, purpose}],
     api_surface: [{endpoint, purpose}],
     risks: [{description, severity, mitigation}],
     appendix: {glossary: {}}
   }
8. Save to GeneratedDoc table
9. Return doc (or async Celery task ID if >30s expected)
```

**For large initiatives (>10 documents):** Run as Celery task. Endpoint returns `{task_id, status: "processing"}`. Frontend polls `GET /api/v1/tasks/{task_id}/status` until complete.

**Frontend — `/frontend/app/dashboard/auto-docs/brd/[initiative_id]/page.tsx`:**
```
┌────────────────────────────────────────────────────────────────────────┐
│  BRD: Project Alpha                    [Regenerate ↺] [Export PDF ↓]  │
├────────────────────────────────────────────────────────────────────────┤
│  1. Executive Summary                                                  │
│  2. Functional Requirements          [filter by priority]              │
│     REQ-001  High   User authentication must support SSO...            │
│     REQ-002  Med    System must handle 10k concurrent users...         │
│  3. Technical Architecture                                             │
│  4. Data Models                                                        │
│  5. API Surface                                                        │
│  6. Risks                                                              │
│  7. Appendix / Glossary                                                │
│                                                                        │
│  Generated at: 2026-03-17 14:32  ·  Cost: $0.42  ·  v2               │
└────────────────────────────────────────────────────────────────────────┘
```
- "Export PDF" → browser `window.print()` with print-only CSS (no PDF library needed)
- "Regenerate" → confirm dialog ("This will cost ~$0.40") → POST → poll for completion
- Shows previous version diff if `version > 1`

**Navigation entry points:**
- New sidebar section "Auto Docs" with sub-links: Architecture, API Docs, BRD, Test Cases, Data Models
- From code component detail page: "Generate Spec" button
- From repository detail page: "Generate Docs" dropdown
- From initiative detail page: "Generate BRD" button

---

### Feature 2.2: API Keys / Integration Panel
**Module 10 | Priority: HIGH | Effort: 4–5 days** *(revised — auth middleware is a cross-cutting concern)*

**Why:** Developers need to trigger DokuDoc analysis from CI/CD pipelines without sharing user credentials.

**Route:** New tab "API Keys" in `/frontend/app/settings/page.tsx`

**Backend — New model `/backend/app/models/api_key.py`:**
```python
class APIKey(Base):
    id: int
    tenant_id: int
    user_id: int                    # which user created this key
    name: str                       # e.g., "GitHub Actions"
    key_prefix: str                 # first 12 chars: "dk_live_xxxx" (display only)
    key_hash: str                   # bcrypt hash of full 44-char key
    scopes: JSON                    # ["read:documents", "write:code", "read:analytics"]
    last_used_at: datetime | None
    call_count_30d: int = 0
    expires_at: datetime | None     # null = never expires
    is_active: bool = True
    created_at: datetime
```

Key format: `"dk_live_" + secrets.token_urlsafe(32)` → shown ONCE on creation, never stored in plaintext.

**Backend — New file `/backend/app/api/endpoints/api_keys.py`:**
```python
GET    /api/v1/api-keys              # list user's keys (never return key_hash, never return full key)
POST   /api/v1/api-keys              # create → returns full key ONE TIME in response
DELETE /api/v1/api-keys/{id}         # revoke (set is_active=False)
PUT    /api/v1/api-keys/{id}         # update name or expiry
GET    /api/v1/api-keys/{id}/usage   # {last_used_at, call_count_30d}
```

**Backend — Cross-cutting auth middleware (HIGH SEVERITY):**

New dependency in `/backend/app/api/deps.py`:
```python
async def get_current_user_or_api_key(
    request: Request,
    db: Session = Depends(get_db),
    bearer_token: str = Depends(oauth2_scheme_optional)
) -> tuple[User, set[str]]:
    """
    Accepts either:
    - JWT Bearer token (existing behavior) → returns (user, full_scopes)
    - API key Bearer token starting with "dk_live_" → returns (user, key.scopes)
    """
    if bearer_token and bearer_token.startswith("dk_live_"):
        # API key path
        key_hash = bcrypt.hash(bearer_token)   # verify against stored hashes
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        if not api_key or (api_key.expires_at and api_key.expires_at < datetime.utcnow()):
            raise HTTPException(401, "Invalid or expired API key")
        # Update last_used_at
        api_key.last_used_at = datetime.utcnow()
        api_key.call_count_30d += 1
        db.commit()
        user = db.query(User).filter(User.id == api_key.user_id).first()
        return user, set(api_key.scopes)
    else:
        # Existing JWT path
        user = await get_current_user(bearer_token, db)
        return user, {"full_access"}
```

Scope enforcement: Create decorator/dependency `require_scope("read:documents")` that checks the returned scopes set.

**Per-key rate limiting:** Add Redis counter `apikey:{id}:calls:{minute}`. Limit to 100 req/min per key. Return `429` with `Retry-After` header if exceeded.

**New Alembic migration:** `s8a6_add_api_keys.py`

**Frontend — new tab in `/frontend/app/settings/page.tsx`:**
```
┌──────────────────────────────────────────────────────────────────────────┐
│  API Keys                                             [+ Create New Key] │
├──────────────────────────────────────────────────────────────────────────┤
│  Name             │ Prefix          │ Scopes        │ Last Used │ Actions│
│  GitHub Actions   │ dk_live_Ab3x... │ read, write   │ 2 hrs ago │ Revoke │
│  Analytics Bot    │ dk_live_Xy9p... │ read:analytics│ Never     │ Revoke │
└──────────────────────────────────────────────────────────────────────────┘
```

"Create New Key" modal:
- Name input (required)
- Scope checkboxes: `read:documents` | `write:code` | `read:analytics` | `full_access`
- Expiry date picker (optional)
- On submit: POST → show one-time reveal modal:
  ```
  ┌────────────────────────────────────────────────────────────────────┐
  │  ⚠  Your API Key — Copy now, it will not be shown again           │
  │                                                                    │
  │  dk_live_AbCdEfGh1234567890XyZaBcDeFgHiJkLmNoPqRsTuVwXy          │
  │                                                    [Copy ✓]        │
  │                                          [I've copied it, close]   │
  └────────────────────────────────────────────────────────────────────┘
  ```

---

## PHASE 3 — Enterprise & Integrations

---

### Feature 3.1: Documentation Integrations (Module 11)
**Module 11 | Priority: HIGH | Effort: 14–16 days total (phased)**

**Why:** Manual document uploads are the #1 adoption blocker. Connecting to existing documentation sources removes it.

**Phasing by auth complexity and usage frequency:**

| Phase | Provider | Auth Method | Effort |
|-------|---------|-------------|--------|
| 3.1a | **Notion** | API key (Bearer) | 3 days |
| 3.1b | **Jira** | API token + email (Basic over HTTPS) | 3 days |
| 3.1c | **Confluence Cloud** | OAuth 2.0 (3LO — Authorization Code) | 4 days |
| 3.1d | **SharePoint Online** | Azure AD OAuth 2.0 | 4–6 days |

Start with Notion and Jira (simpler auth). Confluence and SharePoint are separate sprints.

**Architecture Decision:**
- Notion: `Authorization: Bearer {notion_api_key}` — user creates Integration token in Notion settings
- Jira Cloud: `Authorization: Basic base64(email:api_token)` — user creates token at id.atlassian.net
- Confluence Cloud: OAuth 2.0 3LO — DokuDoc registers as an Atlassian app, handles callback
- SharePoint: Azure AD app registration — DokuDoc handles OAuth2 code flow with Microsoft identity

**Backend — New models:**

`/backend/app/models/integration_config.py`:
```python
class IntegrationConfig(Base):
    id: int
    tenant_id: int
    provider: str           # "notion"|"jira"|"confluence"|"sharepoint"
    auth_type: str          # "api_key"|"basic"|"oauth2"
    credentials: str        # encrypted JSON: {token, email, refresh_token, ...}
    config_json: JSON       # {workspace_id, space_key, site_url, ...} — provider-specific scope
    is_active: bool = True
    last_sync_at: datetime | None
    created_by_id: int
    created_at: datetime
```

`/backend/app/models/integration_sync.py`:
```python
class IntegrationSync(Base):
    id: int
    integration_id: int         # FK → IntegrationConfig
    status: str                 # "running"|"completed"|"failed"
    docs_found: int
    docs_synced: int
    docs_failed: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    celery_task_id: str | None
```

**Backend — New endpoints `/backend/app/api/endpoints/integrations.py`:**
```python
GET    /api/v1/integrations                           # list connected integrations for tenant
POST   /api/v1/integrations/notion/connect            # body: {api_key, workspace_id?}
POST   /api/v1/integrations/jira/connect              # body: {email, api_token, site_url}
GET    /api/v1/integrations/confluence/oauth-url      # returns Atlassian OAuth initiation URL
GET    /api/v1/integrations/confluence/callback       # OAuth callback — stores tokens
GET    /api/v1/integrations/sharepoint/oauth-url      # returns Microsoft OAuth URL
GET    /api/v1/integrations/sharepoint/callback       # OAuth callback
GET    /api/v1/integrations/{id}/preview              # list available docs from provider
POST   /api/v1/integrations/{id}/sync                 # trigger Celery sync task
GET    /api/v1/integrations/{id}/sync-history         # list IntegrationSync records
DELETE /api/v1/integrations/{id}                      # disconnect (revoke tokens)
```

**Backend — Celery tasks `/backend/app/tasks/integration_tasks.py`:**

Each task follows this contract:
```python
@celery_app.task
def sync_notion_database(integration_id: int, database_ids: list[str]):
    # 1. Load IntegrationConfig, decrypt credentials
    # 2. Fetch pages from Notion API (paginated)
    # 3. Convert Notion blocks to plain text
    # 4. For each page: create/update Document record
    # 5. Trigger existing analyze_document task for each new doc
    # 6. Update IntegrationSync record with results

@celery_app.task
def sync_jira_project(integration_id: int, project_keys: list[str]):
    # Fetch Jira issues (type: Story, Epic, Bug) as requirement documents

@celery_app.task
def sync_confluence_space(integration_id: int, space_keys: list[str]):
    # Requires OAuth token; refresh if expired before API calls

@celery_app.task
def sync_sharepoint_library(integration_id: int, site_url: str, library_names: list[str]):
    # Requires Azure AD token; download files (PDF, DOCX) and pass to document parser
```

**New Alembic migration:** `s8a7_add_integrations.py`

**Frontend — `/frontend/app/dashboard/integrations/page.tsx` (new page):**

```
┌────────────────────────────────────────────────────────────────┐
│  Documentation Integrations                                    │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   Notion     │    Jira      │  Confluence  │   SharePoint     │
│   [Logo]     │   [Logo]     │   [Logo]     │    [Logo]        │
│              │              │              │                  │
│  ✓ Connected │  Not connected│  Not connected│  Not connected  │
│  42 docs     │              │              │                  │
│  Last: 2h ago│              │              │                  │
│              │              │              │                  │
│ [Sync Now]   │  [Connect]   │  [Connect]   │  [Connect]       │
│ [Configure]  │              │              │                  │
└──────────────┴──────────────┴──────────────┴──────────────────┘

Sync History
┌──────────────────────────────────────────────────────────────┐
│  Provider   │ Status     │ Docs Synced │ Date                │
│  Notion     │ ✓ Complete │ 12 new docs │ 2026-03-17 14:30   │
│  Notion     │ ✗ Failed   │ 0           │ 2026-03-15 09:00   │
└──────────────────────────────────────────────────────────────┘
```

Modals:
- `NotionConnectModal` — API key input + "How to get your Notion API key" link
- `JiraConnectModal` — site URL + email + API token inputs
- `SyncPreviewModal` — table of available docs (paginated list from `/preview`) with checkboxes → "Import Selected"
- Confluence/SharePoint: redirect-based OAuth flow (no modal; button opens OAuth URL, callback returns to page)

---

## Cross-Cutting Navigation Updates

Update `/frontend/components/layout/AppLayout.tsx` sidebar:

```
Existing items (unchanged)
  ...
  [NEW SECTION] Auto Docs
    - Architecture Diagrams
    - API Documentation
    - BRD Generator
    - Test Cases
    - Data Models
  [NEW ITEM under Tools/Settings group]
  Integrations
Settings
  [tabs: Profile | Billing | Team | API Keys (NEW) | Notification Prefs (NEW)]
```

---

## Database Migration Sequence

Run strictly in order:
```
s8a3_add_document_versions.py         down_revision: current HEAD
s8a4_add_notification_preferences.py  down_revision: s8a3
s8a5_add_generated_docs.py            down_revision: s8a4
s8a6_add_api_keys.py                  down_revision: s8a5
s8a7_add_integrations.py              down_revision: s8a6
```

---

## Revised Execution Order

| # | Feature | Key Files | Effort | Sprint |
|---|---------|-----------|--------|--------|
| 1 | **Chat Response Formatting (ChatGPT-style)** | `MarkdownRenderer.tsx` + system prompt update + `npm install remark-gfm` | **1–2 days** | **1 — first** |
| 2 | AskyDoc Slash Commands | `chat.py` command endpoint + `SlashCommandPalette.tsx` + `CommandRequest` schema | 3 days | 1 |
| 3 | Help & Support Module | `/dashboard/help/page.tsx` + 6 section tabs + optional bug-report endpoint | 2 days | 1 |
| 4 | Document Version Comparison | `document_version.py` model + schema + crud + 3 endpoints + 2 frontend components | 3 days | 1 |
| 5 | Notification Preferences (in-app only) | `notification_preference.py` model + schema + crud + 2 endpoints + settings card | 1 day | 1 |
| 6 | Audit Dashboard — Rich Visual Layout | 3 new audit endpoints + `SecurityInsightsPanel.tsx` (recharts) | 2 days | 1 |
| 7 | AskyDoc In-Dock Approvals | `rag_service.py` retrieval stage + `RetrievedContext` + `InlineApprovalActions.tsx` | 3 days | 2 |
| 8 | Auto Docs Sprint A — Spec + Arch + API | `document_generation_service.py` + rate limiter + cache + 3 endpoints + 3 pages | 5 days | 2 |
| 9 | Auto Docs Sprint B — BRD + Test + Diff + Models | 4 more endpoints + Celery orchestration + 4 sub-pages | 5 days | 3 |
| 10 | API Keys + Auth Middleware | `api_key.py` model + `deps.py` middleware + rate limiting + settings tab | 4–5 days | 4 |
| 11 | Integrations — Notion + Jira | 2 models + 4 endpoints + 2 Celery tasks + integrations page | 6 days | 5 |
| 12 | Integrations — Confluence + SharePoint | OAuth flows + 2 Celery tasks + OAuth callbacks | 8 days | 6–7 |

**Total revised estimate: 43–46 developer-days**

> **Chat formatting (#1) is Sprint 1, Day 1** — highest ROI for lowest effort. Every user interaction immediately looks better.
> **Help module (#3) ships before slash commands** ideally — so `/help` has something to link to from day 1.

---

## Key Reusable Patterns (with correct file paths)

| Pattern | File |
|---------|------|
| Dashboard page structure | `/frontend/app/dashboard/cxo/page.tsx` |
| API client with JWT | `/frontend/lib/api.ts` |
| Modal pattern (dialog + form) | `/frontend/app/settings/page.tsx` (billing modals) |
| Celery task creation | `/backend/app/tasks/document_analysis_tasks.py` |
| AI prompt dispatch | `/backend/app/services/ai/prompt_manager.py` |
| Approval action endpoints | `/backend/app/api/endpoints/approvals.py` |
| Notification dispatch | `/backend/app/services/notification_service.py` |
| Auth dependency | `/backend/app/api/deps.py` → `get_current_user` |

> **Note:** `recharts` is not currently installed. Do NOT reference the developer dashboard as using recharts — that dashboard uses a custom or different charting approach. Install `recharts` fresh.

---

## Out of Scope (Explicitly Deferred)

| Item | Reason |
|------|--------|
| Email notification channels | No SMTP infrastructure exists; build in Phase 2 when email service is wired |
| Slash command `/export` duplicate | `GET /chat/conversations/{id}/export` already exists — `/command` handler reuses it, no new endpoint |
| PDF export of compliance reports | JSON export sufficient for MVP; PDF templating is Phase 2 |
| Role-based Architecture Layers (Module 5) | Already implemented via L1–L5 brain hierarchy — mark DONE |
| Slack webhook notifications | Phase 2; Slack app setup requires external config |
| Jira OAuth 2.0 | API token (Basic auth) is sufficient for Jira Cloud MVP |

---

## Verification Checklist

After each feature:
- [ ] Backend: `docker-compose exec app python -m pytest tests/ -k "{feature_name}"`
- [ ] Migration: `docker-compose exec app alembic upgrade head` succeeds with no errors
- [ ] Frontend: `cd frontend && npm run build` succeeds (no TypeScript errors)
- [ ] API: test endpoint via Postman or browser network tab — confirm request/response contract
- [ ] E2E: complete user flow from UI without navigating to backend directly

**Feature-specific checks:**

| Feature | Verification |
|---------|-------------|
| Document Version Diff | Upload doc → re-upload updated version → open diff → see highlighted changes |
| Notification Prefs | Toggle off "analysis_complete" → trigger analysis → confirm notification NOT created in DB |
| Audit Dashboard | Open audit trail → Security Insights section shows bar chart + anomaly alerts |
| In-Dock Approvals | Ask AskyDoc "what approvals are pending?" → see inline Approve/Reject buttons → click Approve → verify DB status updated |
| Auto Docs BRD | Link 3 docs + 1 repo to initiative → click Generate BRD → poll until complete → verify all 6 sections populated |
| API Keys | Create key → copy key → make API request with key → verify `last_used_at` updated in DB |
| Integrations | Enter Notion API key → click Preview → verify pages listed → Sync → verify Documents created in DB |
