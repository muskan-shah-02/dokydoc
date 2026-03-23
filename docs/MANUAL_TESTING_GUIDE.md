# DokyDoc — Comprehensive Manual Testing Guide

> **Version:** Sprint 4 (ADHOC Phase 1 Complete)
> **Audience:** Manual QA Tester (UI/End-User Testing)
> **Written by:** System Architect — covers all flows, edge cases, success & failure scenarios

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Pre-Testing Checklist](#2-pre-testing-checklist)
3. [Module 1: Health Check & System Verification](#3-module-1-health-check--system-verification)
4. [Module 2: Tenant Registration](#4-module-2-tenant-registration)
5. [Module 3: Authentication & Login](#5-module-3-authentication--login)
6. [Module 4: Dashboard & Navigation](#6-module-4-dashboard--navigation)
7. [Module 5: Document Management](#7-module-5-document-management)
8. [Module 6: Document Analysis Pipeline](#8-module-6-document-analysis-pipeline)
9. [Module 7: Repository & Code Analysis](#9-module-7-repository--code-analysis)
10. [Module 8: Business Ontology (Document Graph)](#10-module-8-business-ontology-document-graph)
11. [Module 9: Code Ontology (Code Graph)](#11-module-9-code-ontology-code-graph)
12. [Module 10: Cross-Graph Mapping & Visual Architecture](#12-module-10-cross-graph-mapping--visual-architecture)
13. [Module 11: Gap Analysis](#13-module-11-gap-analysis)
14. [Module 12: User & Role Management](#14-module-12-user--role-management)
15. [Module 13: Billing & Cost Tracking](#15-module-13-billing--cost-tracking)
16. [Module 14: Task Management](#16-module-14-task-management)
17. [Module 15: Initiatives (Project Management)](#17-module-15-initiatives-project-management)
18. [Module 16: Audit Trail](#18-module-16-audit-trail)
19. [Module 17: Export](#19-module-17-export)
20. [Module 18: Webhook Integration (Admin)](#20-module-18-webhook-integration-admin)
21. [Module 19: Multi-Tenancy Isolation](#21-module-19-multi-tenancy-isolation)
22. [Module 20: RBAC & Permissions](#22-module-20-rbac--permissions)
23. [Module 21: Rate Limiting](#23-module-21-rate-limiting)
24. [Appendix A: Migration Commands](#appendix-a-migration-commands)
25. [Appendix B: Docker Commands](#appendix-b-docker-commands)
26. [Appendix C: Troubleshooting](#appendix-c-troubleshooting)

---

## 1. Environment Setup

### 1.1 Prerequisites

- Docker & Docker Compose installed
- Git installed
- A modern web browser (Chrome recommended for DevTools)
- A sample BRD/requirements document (PDF, DOCX, or TXT — under 50 MB)
- A GitHub/GitLab repository URL for code analysis testing
- Access to the `.env` file (ask your team lead)

### 1.2 Clone & Start the Application

```bash
# Step 1: Clone the repository
git clone <repo-url> dokydoc
cd dokydoc

# Step 2: Switch to the current development branch
git checkout claude/dokydoc-evolution-guide-49riQ

# Step 3: Copy environment file
cp backend/.env.example backend/.env
# Edit backend/.env and fill in required values (see below)

# Step 4: Start all services
cd backend
docker-compose up -d --build

# Step 5: Wait ~60 seconds for services to become healthy
docker-compose ps
```

### 1.3 Required Environment Variables

Edit `backend/.env` with these minimum values:

| Variable | Example Value | Required? |
|----------|---------------|-----------|
| `SECRET_KEY` | `your-secret-key-minimum-32-characters-long!!` | YES |
| `DATABASE_URL` | `postgresql://postgres:simplepass@db:5432/dokydoc` | YES |
| `REDIS_URL` | `redis://redis:6379` | YES |
| `GEMINI_API_KEY` | `AIzaSy...your-key` | YES |
| `ANTHROPIC_API_KEY` | `sk-ant-...your-key` | Optional |
| `WEBHOOK_SECRET` | `mysecretwebhook123` | Optional |
| `AI_PROVIDER_MODE` | `gemini` or `dual` | Optional (default: `gemini`) |
| `ENVIRONMENT` | `development` | Optional |
| `DEBUG` | `true` | Optional |

### 1.4 Run Database Migrations

```bash
# Inside the running app container:
docker-compose exec app alembic upgrade head

# You should see output like:
# INFO [alembic.runtime.migration] Running upgrade -> c8f2a1d9e321, sprint1_multi_tenancy_and_cost_tracking
# INFO [alembic.runtime.migration] Running upgrade c8f2a1d9e321 -> b342e208f554, add_phase_2_architecture_analysis_runs
# ... (11 migrations total)
# INFO [alembic.runtime.migration] Running upgrade ... -> s3a2, concept_mapping_table
```

### 1.5 Verify All Services Are Running

```bash
docker-compose ps
```

**Expected Output — all 5 services should show "Up (healthy)":**

| Service | Port | Status Expected |
|---------|------|-----------------|
| `dokydoc_db` (PostgreSQL) | 5432 | Up (healthy) |
| `dokydoc_redis` (Redis) | 6379 | Up (healthy) |
| `dokydoc_app` (FastAPI) | 8000 | Up (healthy) |
| `dokydoc_worker` (Celery) | — | Up |
| `dokydoc_flower` (Flower) | 5555 | Up |

### 1.6 Access Points

| Application | URL |
|-------------|-----|
| **Frontend (Next.js)** | `http://localhost:3000` |
| **Backend API** | `http://localhost:8000` |
| **API Docs (Swagger)** | `http://localhost:8000/docs` |
| **Flower (Task Monitor)** | `http://localhost:5555` |

---

## 2. Pre-Testing Checklist

Before starting any test module, verify:

- [ ] All 5 Docker services are running (`docker-compose ps`)
- [ ] Frontend loads at `http://localhost:3000` (you see a login or landing page)
- [ ] Backend health check passes: open `http://localhost:8000/api/health` — should return `{"status": "healthy"}`
- [ ] Flower dashboard loads at `http://localhost:5555`
- [ ] You have a test document file ready (PDF/DOCX/TXT, under 50 MB)
- [ ] You have a test repository URL ready (public GitHub repo)

---

## 3. Module 1: Health Check & System Verification

### Test 1.1: Basic Health Check

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open browser, go to `http://localhost:8000/api/health` | JSON response: `{"status": "healthy"}` |
| 2 | Go to `http://localhost:8000/api/health/detailed` | JSON with DB status, Redis status, uptime info |
| 3 | Go to `http://localhost:8000/api/` | JSON with API version info (`v1`) |

### Test 1.2: Swagger UI

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:8000/docs` | Interactive Swagger UI loads with all endpoints listed |
| 2 | Scroll through the page | You should see sections: login, tenants, documents, code-components, repositories, ontology, billing, users, webhooks, initiatives, tasks |

### Test 1.3: Frontend Landing

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:3000` | Landing page or login page loads without errors |
| 2 | Open browser DevTools (F12) → Console tab | No red error messages (warnings are OK) |

### Test 1.4: Flower Dashboard

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:5555` | Flower dashboard loads |
| 2 | Click "Workers" tab | At least 1 worker should be listed as online |
| 3 | Click "Tasks" tab | Empty or shows previous tasks |

**FAILURE SCENARIOS:**
- If health check fails → Check `docker-compose logs app` for errors
- If DB is unhealthy → Check `docker-compose logs db`
- If Flower shows no workers → Check `docker-compose logs worker`

---

## 4. Module 2: Tenant Registration

> **Context:** DokyDoc is multi-tenant. Every user belongs to a tenant (organization). You must register a tenant before you can log in.

### Test 2.1: Successful Tenant Registration

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:3000` | See the landing/login page |
| 2 | Click "Register" or "Sign Up" link | Registration form appears |
| 3 | Fill in: **Organization Name:** `Test Company`, **Subdomain:** `testco`, **Admin Email:** `admin@testco.com`, **Admin Password:** `SecurePass123!`, **Admin Name:** `Test Admin` | All fields accept input |
| 4 | Select Plan/Tier: `Free` | Tier selected |
| 5 | Click "Register" / "Create Account" | Success message. Redirected to login page or dashboard |

**VERIFY:** The tenant and admin user were created. You should be able to log in now.

### Test 2.2: Duplicate Subdomain Registration (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Try registering again with **same subdomain** `testco` but different email | Error: Subdomain already taken / Tenant already exists |

### Test 2.3: Invalid Email Format (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Register with email: `not-an-email` | Validation error: Invalid email format |

### Test 2.4: Weak Password (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Register with password: `123` | Validation error: Password too short / doesn't meet requirements |

### Test 2.5: Empty Required Fields (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Leave Organization Name blank, submit | Validation error on required field |
| 2 | Leave Email blank, submit | Validation error on required field |

---

## 5. Module 3: Authentication & Login

### Test 3.1: Successful Login

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:3000/login` | Login form appears |
| 2 | Enter email: `admin@testco.com`, password: `SecurePass123!` | Fields accept input |
| 3 | Click "Login" / "Sign In" | Redirected to dashboard (`/dashboard`). Welcome message or user name shown in top-right |
| 4 | Check browser DevTools → Application → Local Storage or Cookies | Access token and refresh token are stored |

### Test 3.2: Wrong Password (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Enter correct email but wrong password: `wrongpass` | Error: "Invalid credentials" or "Incorrect email or password" |
| 2 | Verify you remain on login page | Not redirected, no token stored |

### Test 3.3: Non-Existent Email (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Enter email: `nobody@nowhere.com`, any password | Error: "Invalid credentials" |

### Test 3.4: Empty Fields (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Leave email blank, click Login | Validation error |
| 2 | Leave password blank, click Login | Validation error |

### Test 3.5: Session Persistence

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After successful login, close the browser tab | — |
| 2 | Open a new tab, go to `http://localhost:3000/dashboard` | Still logged in (token persists). Dashboard loads without redirecting to login |

### Test 3.6: Logout

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click your profile icon or name in top-right | Dropdown menu appears |
| 2 | Click "Logout" / "Sign Out" | Redirected to login page. Tokens cleared |
| 3 | Try navigating to `http://localhost:3000/dashboard` | Redirected to login page (access denied) |

### Test 3.7: Access Protected Page Without Login

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open a private/incognito browser window | Fresh session, no tokens |
| 2 | Go directly to `http://localhost:3000/dashboard` | Redirected to `/login` or shown access denied page |

---

## 6. Module 4: Dashboard & Navigation

> **Prerequisite:** Logged in as admin@testco.com

### Test 4.1: Dashboard Page

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After login, you should be on `/dashboard` | Dashboard page loads with summary cards/widgets |
| 2 | Look for stats: document count, code component count, recent activity | Cards display (may show 0 if nothing uploaded yet) |

### Test 4.2: Sidebar Navigation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look at the left sidebar | Menu items visible |
| 2 | Click each menu item and verify navigation: | |
| | → **Dashboard** | Navigates to `/dashboard` |
| | → **Documents** | Navigates to `/dashboard/documents` |
| | → **Code** | Navigates to `/dashboard/code` |
| | → **Visual Architecture** | Navigates to `/dashboard/visual-architecture` |
| | → **Validation Panel** | Navigates to `/dashboard/validation-panel` |
| | → **Business Ontology** | Navigates to `/dashboard/ontology` |
| | → **Sync Timeline** | Navigates to `/dashboard/sync-timeline` |
| | → **Export** | Navigates to `/dashboard/export` |
| | → **Audit Trail** | Navigates to `/dashboard/audit-trail` |
| 3 | Look for a Settings section (may be a collapsible submenu) | Settings submenu visible |
| 4 | Click Settings items: | |
| | → **Profile** | Navigates to settings page |
| | → **Permissions** | Navigates to permissions settings |
| | → **User Management** | Navigates to user management (CXO/Admin only) |
| | → **Organization** | Navigates to organization settings |
| | → **Billing** | Navigates to billing settings |

### Test 4.3: Active Menu Highlighting

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Documents" in sidebar | Documents menu item is highlighted/active |
| 2 | Click "Code" in sidebar | Code menu item is highlighted, Documents is not |

### Test 4.4: Responsive Behavior

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Resize browser window to narrow width (< 768px) | Sidebar collapses to hamburger menu or icons-only mode |
| 2 | Click hamburger menu (if present) | Sidebar expands as overlay |

---

## 7. Module 5: Document Management

> **Prerequisite:** Logged in. Have a test document ready (PDF, DOCX, or TXT, under 50 MB).

### Test 5.1: Document Upload — Success

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Documents" in sidebar | Documents list page loads |
| 2 | Click "Upload Document" or "+" button | Upload dialog/form appears |
| 3 | Select your test PDF/DOCX file (under 50 MB) | File selected, filename shown |
| 4 | Click "Upload" | Upload starts. Progress indicator shown |
| 5 | Wait for upload to complete | Success message: "Document uploaded successfully" |
| 6 | Check documents list | New document appears in the list with status "pending" or "parsing" |

### Test 5.2: Document Upload — Oversized File (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Try uploading a file larger than 50 MB | Error: "File too large" or "Maximum file size is 50 MB" |

### Test 5.3: Document Upload — Invalid File Type (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Try uploading a `.jpg` or `.exe` file | Error: "Unsupported file type" or only `.pdf, .docx, .doc, .txt` allowed |

### Test 5.4: Document Upload — Empty File (Edge Case)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create an empty `.txt` file (0 bytes) and upload it | Either rejected with error OR accepted but analysis shows "no content" |

### Test 5.5: View Document List

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Documents page | List of uploaded documents shown |
| 2 | Each document shows: name, upload date, status, file type | All columns populated |
| 3 | Status values should be one of: `pending`, `parsing`, `analyzing`, `completed`, `analysis_failed` | Valid status displayed |

### Test 5.6: View Document Detail

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a document name in the list | Document detail page opens (`/dashboard/documents/{id}`) |
| 2 | See document metadata: name, upload date, file size, status | All fields displayed |
| 3 | If status is "completed" → analysis results section visible | Segments, entities, relationships shown |

### Test 5.7: Download Document

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | On document detail page, click "Download" button | Original file downloads to your computer |
| 2 | Open downloaded file | File content matches what you uploaded |

### Test 5.8: Check Document Processing Status

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Upload a new document | Status shows "pending" |
| 2 | Wait 10-30 seconds, refresh the page | Status changes to "parsing" → "analyzing" |
| 3 | Wait 1-5 minutes (depending on doc size), refresh | Status changes to "completed" |
| 4 | Open Flower at `http://localhost:5555` → Tasks tab | You should see `process_document_pipeline` task completed |

**FAILURE SCENARIO:**
- If status shows "analysis_failed" → Open document detail, check for error message
- Common causes: Gemini API key invalid, API rate limit hit, document is corrupted/unreadable

---

## 8. Module 6: Document Analysis Pipeline

> **Prerequisite:** Upload a BRD/requirements document and wait for status = "completed"

### Test 6.1: View Analysis Results

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a completed document | Detail page opens |
| 2 | Look for "Analysis" or "Segments" section | Analyzed segments shown |
| 3 | Each segment should show: text content, analysis metadata | Segments listed with content |

### Test 6.2: Verify 3-Pass DAE Results

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In document analysis, look for classification info | Each segment has a category (e.g., "Functional Requirement", "Non-Functional Requirement", "Business Rule") |
| 2 | Look for entity extraction results | Business entities extracted (e.g., "Customer", "Order", "Payment") |
| 3 | Look for relationship information | Relationships between entities shown |

### Test 6.3: Verify Ontology Enrichment After Document Analysis

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After document completes, go to "Business Ontology" page | Ontology page loads |
| 2 | Click "Document" layer tab | Document-layer concepts displayed |
| 3 | Concepts extracted from your document should appear | Concept names match entities from the document (e.g., "Customer", "Order") |

### Test 6.4: Multiple Document Upload

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Upload a second document (different content) | Both documents appear in list |
| 2 | Wait for both to complete | Both show "completed" status |
| 3 | Check Ontology page | Concepts from both documents appear in the graph |

### Test 6.5: Analysis Pipeline — Flower Monitoring

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Upload a document | — |
| 2 | Immediately open Flower (`http://localhost:5555`) | — |
| 3 | Click "Tasks" tab | See `process_document_pipeline` task in STARTED state |
| 4 | After a minute, see `extract_ontology_entities` task | Chained task appears after pipeline completes |
| 5 | All tasks eventually show SUCCESS | Green success status |

**FAILURE SCENARIOS:**
- Task shows FAILURE in Flower → Click on task ID to see traceback
- Common errors: `google.api_core.exceptions.ResourceExhausted` (rate limit) — wait 60 seconds and retry
- `InvalidArgument: API key not valid` — check GEMINI_API_KEY in `.env`

---

## 9. Module 7: Repository & Code Analysis

> **Prerequisite:** Logged in. Have a public GitHub repository URL ready.

### Test 7.1: Onboard a Repository — Success

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Code" in sidebar | Code/Repository page loads |
| 2 | Click "Add Repository" or "+" button | Repository form appears |
| 3 | Enter: **Name:** `test-repo`, **URL:** `https://github.com/<owner>/<repo>`, **Branch:** `main` | Fields accept input |
| 4 | Click "Save" / "Add" | Repository created, appears in list with status "pending" |

### Test 7.2: Trigger Code Analysis

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on the repository you just added | Repository detail page opens |
| 2 | Click "Analyze" or "Run Analysis" button | Analysis triggered. Status changes to "analyzing" |
| 3 | Provide or select files to analyze (if prompted) | File list accepted |
| 4 | Monitor progress on the page or in Flower | Progress % increases |
| 5 | Wait for completion (1-10 minutes depending on file count) | Status: "completed". Code components listed |

### Test 7.3: View Code Components

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After analysis completes, check repository detail | List of analyzed code components (files) shown |
| 2 | Click on a code component | Detail view: business rules extracted, API contracts, security concerns |
| 3 | Each component shows: file path, language, analysis summary | All fields populated |

### Test 7.4: Code Ontology Enrichment

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After code analysis completes, go to "Business Ontology" | Ontology page loads |
| 2 | Click "Code" layer tab | Code-layer concepts shown |
| 3 | Concepts extracted from code should appear (e.g., class names, API endpoints, business logic entities) | Code concepts listed with "code" source badge |

### Test 7.5: Repository with Invalid URL (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Add repository with URL: `https://invalid-url-nothing-here.com/repo` | Error or repo created but analysis fails |

### Test 7.6: Repository Statistics

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for a stats/summary section on the Code page | Shows: total repos, analyzed files, languages breakdown |

---

## 10. Module 8: Business Ontology (Document Graph)

> **Prerequisite:** At least one document uploaded and fully analyzed (status: completed)

### Test 8.1: View Full Ontology Graph

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Business Ontology" in sidebar | Ontology page loads at `/dashboard/ontology` |
| 2 | Graph visualization renders | SVG force-directed graph with nodes and edges |
| 3 | Nodes represent business concepts | Each node shows concept name |
| 4 | Edges represent relationships | Lines connecting related concepts |

### Test 8.2: Layer Tabs — All / Document / Code

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for layer tabs at the top: **All**, **Document**, **Code** | Three tabs visible |
| 2 | Click **All** tab | Shows ALL concepts (both document and code) |
| 3 | Click **Document** tab | Shows ONLY document-layer concepts |
| 4 | Click **Code** tab | Shows ONLY code-layer concepts |
| 5 | Toggle between tabs | Graph re-renders with filtered concepts |

### Test 8.3: Source Type Badges

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | On "All" tab, look at concept nodes | Some nodes show a badge indicator |
| 2 | Nodes from code analysis show a **"C"** badge | Badge visible on code-sourced concepts |
| 3 | Nodes that exist in both layers show a **"B"** badge | Badge visible on dual-source concepts |
| 4 | Document-only concepts have no extra badge | Clean node display |

### Test 8.4: View Concept Detail

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a concept node in the graph | Side panel or detail dialog opens |
| 2 | Shows: concept name, type, source_type (document/code/both), description | All fields visible |
| 3 | Shows relationships: connected concepts listed | Relationship list populated |

### Test 8.5: Create Manual Concept

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Add Concept" or "+" button on Ontology page | Button visible |
| 2 | Click it | Create concept dialog/form appears |
| 3 | Enter: **Name:** `Test Manual Concept`, **Type:** `Entity` | Fields accept input |
| 4 | Click "Save" / "Create" | Concept created, appears in graph |

### Test 8.6: Edit Concept

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a concept → Edit button | Edit form opens with current values |
| 2 | Change the name or description | Fields editable |
| 3 | Save | Changes reflected in graph |

### Test 8.7: Delete Concept

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a concept → Delete button | Confirmation dialog: "Are you sure?" |
| 2 | Confirm deletion | Concept removed from graph. Related relationships also removed |

### Test 8.8: Create Relationship Between Concepts

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Add Relationship" button | Button visible |
| 2 | Select source concept, target concept, relationship type | Dropdowns populated with existing concepts |
| 3 | Click "Create" | Relationship appears as edge in graph |

### Test 8.9: Delete Relationship

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a relationship/edge → Delete | Confirmation dialog |
| 2 | Confirm | Edge removed from graph |

### Test 8.10: Search Concepts

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for a search box on Ontology page | Search input visible |
| 2 | Type a concept name (e.g., "Customer") | Results filtered/highlighted |
| 3 | Clear search | Full graph restored |

### Test 8.11: Concept Type Filter

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for a type filter dropdown | Filter control visible |
| 2 | Select a specific type (e.g., "Entity", "Process") | Only concepts of that type shown |
| 3 | Clear filter | All concepts restored |

### Test 8.12: Empty State (Edge Case)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | If no documents analyzed yet, visit Ontology page | Empty state message: "No concepts yet" or empty graph |
| 2 | After uploading & analyzing a document, revisit | Concepts now populated |

---

## 11. Module 9: Code Ontology (Code Graph)

> **Prerequisite:** At least one repository analyzed

### Test 9.1: View Code Graph

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | On Ontology page, click **Code** tab | Graph shows only code-layer concepts |
| 2 | Concepts represent code entities (classes, functions, APIs) | Nodes labeled with code-derived names |
| 3 | Relationships show code dependencies | Edges connect related code concepts |

### Test 9.2: Verify Code vs Document Separation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click **Document** tab | Only document concepts shown |
| 2 | Click **Code** tab | Only code concepts shown |
| 3 | Concepts should NOT overlap (unless mapped) | Different set of concepts in each tab |
| 4 | Click **All** tab | Both sets combined |

---

## 12. Module 10: Cross-Graph Mapping & Visual Architecture

> **Prerequisite:** BOTH a document and a repository have been analyzed (so both graphs have concepts)

### Test 10.1: Access Visual Architecture Page

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Visual Architecture" in sidebar | Page loads at `/dashboard/visual-architecture` |
| 2 | See summary stat cards at top | 6 cards showing: Total Document Concepts, Total Code Concepts, Total Mappings, Confirmed, Candidates, Rejected |
| 3 | Initially mappings may be 0 | Cards show 0 for mapping counts until pipeline is run |

### Test 10.2: Run Mapping Pipeline

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click **"Run Mapping Pipeline"** button | Button triggers the 3-tier algorithmic mapping |
| 2 | See loading/progress indicator | Pipeline running in background (Celery task) |
| 3 | Open Flower → Tasks tab | See `run_cross_graph_mapping` task |
| 4 | Wait for completion (30 seconds to 2 minutes) | Task shows SUCCESS in Flower |
| 5 | Refresh the Visual Architecture page | Stat cards now show mapping counts > 0 |
| 6 | Mappings categorized by method: "exact", "fuzzy", "ai_validation" | Different mapping methods visible |

### Test 10.3: Cross-Graph View (Bipartite Visualization)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | On Visual Architecture page, look for the "Cross-Graph Mappings" tab | Tab visible and active by default |
| 2 | Bipartite graph renders: **Document concepts on LEFT**, **Code concepts on RIGHT** | Two-column layout visible |
| 3 | Curved lines (Bezier curves) connect mapped concepts | Lines visible between columns |
| 4 | Line colors differ by status: confirmed (green), candidate (yellow/orange), rejected (red/gray) | Color coding visible |
| 5 | Unmapped concepts shown with **dashed borders** | Visual distinction for unmapped nodes |

### Test 10.4: Inspect a Mapping

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a mapping line or mapped concept pair | Mapping detail panel opens on the right |
| 2 | Shows: Document concept name, Code concept name, Confidence score (0.0–1.0), Mapping method (exact/fuzzy/ai_validation) | All fields displayed |
| 3 | If AI-validated: shows AI reasoning text | Reasoning text visible for Tier 3 mappings |
| 4 | Confidence bar/indicator shows the score visually | Visual confidence indicator |

### Test 10.5: Confirm a Candidate Mapping

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In the Mapping Review Panel (right side), find a **candidate** mapping | Candidate mappings listed with status badge |
| 2 | Click "Expand" or click the mapping row | Detail view with Confirm/Reject buttons |
| 3 | Click **"Confirm"** button | Status changes from "candidate" → "confirmed" |
| 4 | Line color in graph changes to green | Visual update |
| 5 | Stat card "Confirmed" count increments by 1, "Candidates" decrements by 1 | Numbers update |

### Test 10.6: Reject a Candidate Mapping

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Find another **candidate** mapping | — |
| 2 | Click **"Reject"** button | Status changes to "rejected" |
| 3 | Line color changes to red/gray or disappears | Visual update |
| 4 | Stat cards update accordingly | Numbers update |

### Test 10.7: Delete a Mapping

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Find any mapping, look for a "Delete" option | Delete button/icon visible |
| 2 | Click Delete | Confirmation dialog |
| 3 | Confirm | Mapping removed entirely from list and graph |

### Test 10.8: Filter Mappings by Status

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In the Mapping Review Panel, look for status filter | Filter options: All, Candidate, Confirmed, Rejected |
| 2 | Select "Confirmed" | Only confirmed mappings shown |
| 3 | Select "Candidate" | Only candidate mappings shown |
| 4 | Select "All" | All mappings shown |

### Test 10.9: Re-run Mapping Pipeline

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Run Mapping Pipeline" again | Pipeline re-runs |
| 2 | Previously confirmed mappings should remain confirmed | Confirmed status preserved |
| 3 | New candidate mappings may appear | New mappings added if new concepts exist |

### Test 10.10: No Concepts Edge Case

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | If only documents analyzed (no code), visit Visual Architecture | Document concepts shown on left, right column empty |
| 2 | Click "Run Mapping Pipeline" | No mappings created (nothing to map) |
| 3 | Message: "No code concepts" or similar empty state | Clear messaging |

---

## 13. Module 11: Gap Analysis

> **Prerequisite:** Mapping pipeline has been run

### Test 11.1: Access Gap Analysis

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | On Visual Architecture page, click **"Gap Analysis"** tab | Tab switches to gap analysis view |
| 2 | Dashboard loads with summary cards | Cards show gap categories |

### Test 11.2: Documentation Gaps (Unmatched Code Concepts)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Documentation Gaps" or "Undocumented Code" section | Section visible |
| 2 | Lists code concepts that have NO matching document concept | Code entities without documentation listed |
| 3 | Each item shows: concept name, type, source info | Details visible |
| 4 | These are code features that lack corresponding business requirements documentation | Interpretation clear |

### Test 11.3: Implementation Gaps (Unmatched Document Concepts)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Implementation Gaps" or "Unimplemented Requirements" section | Section visible |
| 2 | Lists document concepts that have NO matching code concept | Document entities without code implementation listed |
| 3 | These are documented requirements that appear to be unimplemented | Interpretation clear |

### Test 11.4: Contradictions (Low-Confidence Mappings)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Contradictions" or "Mismatches" section | Section visible (may be empty) |
| 2 | Lists mappings where confidence is very low or AI flagged a concern | Problematic mappings listed |

### Test 11.5: Gap Analysis with Full Coverage

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | If all concepts are mapped, gap analysis should show minimal gaps | "All concepts mapped" or very few items |

---

## 14. Module 12: User & Role Management

> **Prerequisite:** Logged in as admin (CXO or Admin role)

### Test 12.1: View User List

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to Settings → User Management | User list page loads |
| 2 | See list of tenant users | At least your admin user shown |
| 3 | Each user shows: name, email, role(s), status | All columns populated |

### Test 12.2: Invite New User

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Invite User" button | Invite form/dialog opens |
| 2 | Enter email: `developer@testco.com`, select role: `Developer` | Fields accept input |
| 3 | Click "Send Invite" / "Invite" | Invitation sent. User appears in list (pending) |

### Test 12.3: Assign Role

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a user → Role management | Role options shown |
| 2 | Assign "BA" (Business Analyst) role | Role added |
| 3 | User now has both original and new role | Multiple roles shown |

### Test 12.4: Remove Role

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a user → Remove a role | Confirmation dialog |
| 2 | Confirm removal | Role removed from user |

### Test 12.5: Delete User

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click delete on a non-admin user | Confirmation dialog |
| 2 | Confirm | User removed from tenant |

### Test 12.6: Non-Admin Access (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log in as a Developer user (not admin) | Dashboard loads |
| 2 | Try to access User Management | Access denied or menu item not visible |

### Available Roles Reference

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **CXO** | Executive-level access | Full access to everything including billing and org settings |
| **Admin** | Administrative access | User management, permissions, org settings |
| **Developer** | Development team member | Code analysis, repository management, ontology view |
| **BA** (Business Analyst) | Business analysis | Document management, ontology editing, initiative management |
| **PM** (Product Manager) | Product management | Documents, initiatives, reporting, export |

---

## 15. Module 13: Billing & Cost Tracking

> **Prerequisite:** Logged in as admin/CXO

### Test 13.1: View Current Cost Summary

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to Settings → Billing | Billing page loads |
| 2 | See cost summary: current month cost, last 30 days cost, balance, monthly limit | All values displayed |
| 3 | If AI calls were made (document/code analysis), cost > 0 | Costs reflect actual usage |

### Test 13.2: Usage Analytics

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Analytics" or "Usage" section on Billing page | Analytics dashboard visible |
| 2 | Charts/graphs showing usage over time | Visual usage data |

### Test 13.3: Usage Logs

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for "Usage Logs" or "Activity Log" section | Detailed log entries visible |
| 2 | Each entry shows: timestamp, action type, cost, user | Log details populated |

### Test 13.4: Subscription Information

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for current subscription/plan info | Shows current tier: Free/Pro/Enterprise |
| 2 | Shows billing type: prepaid or postpaid | Billing type displayed |

### Test 13.5: Low Balance Alert (Edge Case)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | If balance is low relative to limit | `low_balance_alert: true` indicator shown |
| 2 | Warning banner or notification | Alert visible to admin |

---

## 16. Module 14: Task Management

> **Prerequisite:** Logged in

### Test 14.1: View Task List

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to task management (may be under a project/initiative or separate section) | Task list loads |
| 2 | See tasks with: title, status, priority, assignee, due date | All columns visible |

### Test 14.2: Create Task

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Create Task" or "+" | Task creation form |
| 2 | Enter: **Title:** `Review BRD Analysis`, **Priority:** High, **Status:** Open | Fields accept input |
| 3 | Save | Task created, appears in list |

### Test 14.3: Update Task Status

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on a task | Detail view |
| 2 | Change status: Open → In Progress → Done | Status updates |

### Test 14.4: Add Comment to Task

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open a task detail | — |
| 2 | Add comment: "Analysis looks good, needs review" | Comment saved and displayed |

### Test 14.5: Delete Task

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Delete a task | Confirmation dialog |
| 2 | Confirm | Task removed from list |

---

## 17. Module 15: Initiatives (Project Management)

> **Prerequisite:** Logged in

### Test 15.1: Create Initiative

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to Initiatives section (if available in sidebar or dashboard) | Initiative list loads |
| 2 | Click "Create Initiative" | Creation form |
| 3 | Enter: **Name:** `Q1 Platform Upgrade`, **Description:** `Upgrade core platform features`, **Status:** `Active` | Fields accept input |
| 4 | Save | Initiative created |

### Test 15.2: Link Document to Initiative

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open the initiative | Detail view |
| 2 | Click "Link Asset" or "Add Document" | Asset linking dialog |
| 3 | Select a document from the list | Document linked |
| 4 | Document now appears under the initiative's assets | Asset visible |

### Test 15.3: Link Code Component to Initiative

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Link Asset" → select code component | — |
| 2 | Code component linked | Appears in initiative assets |

### Test 15.4: Unlink Asset

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click remove/unlink on an asset | Confirmation |
| 2 | Confirm | Asset removed from initiative (not deleted from system) |

### Test 15.5: Filter Initiatives by Status

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Look for status filter: Active, Completed, On Hold | Filter options available |
| 2 | Select a filter | List filtered accordingly |

### Test 15.6: Delete Initiative

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Delete an initiative | Confirmation dialog |
| 2 | Confirm | Initiative removed. Linked assets are NOT deleted |

---

## 18. Module 16: Audit Trail

### Test 16.1: View Audit Trail

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Audit Trail" in sidebar | Audit trail page loads at `/dashboard/audit-trail` |
| 2 | See chronological log of actions | Actions listed with timestamps |
| 3 | Log entries include: who did what, when, on what resource | Details visible |

### Test 16.2: Verify Actions Are Logged

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go back and upload a document | — |
| 2 | Return to Audit Trail | New entry for document upload |
| 3 | Create a concept in Ontology | — |
| 4 | Return to Audit Trail | New entry for concept creation |

---

## 19. Module 17: Export

### Test 17.1: Export Functionality

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "Export" in sidebar | Export page loads at `/dashboard/export` |
| 2 | Select what to export (documents, analysis results, ontology) | Export options available |
| 3 | Choose format (if available) | Format options shown |
| 4 | Click "Export" / "Download" | File downloads |
| 5 | Open exported file | Content matches what was displayed in UI |

---

## 20. Module 18: Webhook Integration (Admin)

> **Note:** This is a backend integration feature. Testing requires a tool like Postman, curl, or a GitHub repository with webhooks configured.

### Test 18.1: Configure Webhook in GitHub

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to your GitHub repository → Settings → Webhooks | Webhook settings page |
| 2 | Click "Add webhook" | Webhook form |
| 3 | **Payload URL:** `http://<your-server>:8000/api/v1/webhooks/git` | — |
| 4 | **Content type:** `application/json` | — |
| 5 | **Secret:** Same value as `WEBHOOK_SECRET` in your `.env` | — |
| 6 | **Events:** Select "Just the push event" | — |
| 7 | Click "Add webhook" | Webhook created |

### Test 18.2: Trigger Webhook via Git Push

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Make a code change in the repository and push | Push triggers webhook |
| 2 | Check Flower dashboard | `webhook_triggered_analysis` task appears |
| 3 | Task processes changed files incrementally | Only modified files re-analyzed |
| 4 | Check Code page in UI | Updated analysis for changed files |

### Test 18.3: Webhook with Invalid Signature (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Send a POST to `/api/v1/webhooks/git` with wrong HMAC signature | HTTP 401 or 403: Invalid signature |

### Test 18.4: Webhook for Non-Existent Repository

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Webhook fires for a repo not onboarded in DokyDoc | Response: `{"status": "ignored"}` — webhook accepted but no action taken |

---

## 21. Module 19: Multi-Tenancy Isolation

> **Purpose:** Verify that data from Tenant A is NEVER visible to Tenant B. This is a critical security requirement.

### Test 19.1: Create Second Tenant

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log out from first tenant | — |
| 2 | Register a new tenant: **Org:** `Other Corp`, **Subdomain:** `othercorp`, **Email:** `admin@othercorp.com` | Second tenant created |
| 3 | Log in as `admin@othercorp.com` | Dashboard loads (empty — no documents, no repos) |

### Test 19.2: Verify Data Isolation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | As Tenant B (`othercorp`), go to Documents | **EMPTY list** — should NOT see Tenant A's documents |
| 2 | Go to Code page | **EMPTY** — should NOT see Tenant A's repos |
| 3 | Go to Ontology | **EMPTY** — should NOT see Tenant A's concepts |
| 4 | Go to Billing | Shows Tenant B's own billing info (zeroed out) |
| 5 | Go to User Management | Only shows Tenant B's admin user |

### Test 19.3: Upload Data as Tenant B

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Upload a document as Tenant B | Document appears |
| 2 | Log out, log in as Tenant A (`admin@testco.com`) | — |
| 3 | Go to Documents | Only Tenant A's documents visible. Tenant B's document NOT visible |

### Test 19.4: Cross-Tenant API Access (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | As Tenant A, note a document ID (e.g., `abc-123`) | — |
| 2 | Log in as Tenant B | — |
| 3 | Try to access `http://localhost:3000/dashboard/documents/abc-123` | Access denied or "Not Found" — cannot access Tenant A's document |

**THIS IS A CRITICAL SECURITY TEST.** If Tenant B can see Tenant A's data, report immediately as a P0 bug.

---

## 22. Module 20: RBAC & Permissions

> **Prerequisite:** Multiple users with different roles in the same tenant

### Test 20.1: CXO Role — Full Access

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log in as CXO user | Dashboard loads |
| 2 | Verify access to ALL sidebar items | All menu items clickable |
| 3 | Verify access to: User Management, Billing, Organization | All admin pages accessible |
| 4 | Verify can: upload documents, analyze code, manage ontology, manage users, view billing | All operations succeed |

### Test 20.2: Developer Role — Limited Access

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log in as Developer user | Dashboard loads |
| 2 | Can access: Code, Ontology (view), documents (view) | Pages accessible |
| 3 | Cannot access: User Management, Organization Settings | Menu items hidden or access denied |
| 4 | Cannot access: Billing details (or limited view) | Restricted |

### Test 20.3: BA Role — Document Focus

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log in as BA user | Dashboard loads |
| 2 | Can access: Documents, Ontology (full edit), Initiatives | Pages accessible |
| 3 | Limited or no access to: Code analysis, User Management | Restricted |

### Test 20.4: PM Role

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Log in as PM user | Dashboard loads |
| 2 | Can access: Documents (view), Initiatives, Export, Reporting | Pages accessible |
| 3 | Limited access to: Code, Ontology editing | Restricted |

### Test 20.5: Unauthorized Action (Failure)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | As Developer, try to delete a user | Action blocked: "Permission denied" or button not visible |
| 2 | As BA, try to access billing | Action blocked |

---

## 23. Module 21: Rate Limiting

### Test 23.1: Login Rate Limit

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Attempt to log in with wrong password 6 times rapidly | After 5th attempt: "Too many requests" or "Rate limit exceeded" |
| 2 | Wait 60 seconds | Can attempt login again |

### Test 23.2: Document Upload Rate Limit

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Upload 11 documents in rapid succession (within 1 minute) | After 10th: rate limit error |
| 2 | Wait and retry | Upload succeeds |

### Rate Limits Reference

| Endpoint Category | Per Minute | Per Hour |
|-------------------|-----------|----------|
| Auth (login, register) | 5 | 20 |
| Document upload | 10 | 50 |
| Billing queries | 30 | 200 |
| All other endpoints | 100 | 1,000 |

---

## Appendix A: Migration Commands

Run these commands inside the `dokydoc_app` container:

```bash
# Enter the container
docker-compose exec app bash

# Check current migration status
alembic current

# Run all pending migrations (RECOMMENDED — always do this first)
alembic upgrade head

# Check migration history
alembic history

# Downgrade one step (CAUTION — may lose data)
alembic downgrade -1

# Downgrade to a specific revision
alembic downgrade c8f2a1d9e321
```

### Migration List (in order)

| # | Revision | Description |
|---|----------|-------------|
| 1 | `c8f2a1d9e321` | Sprint 1: Multi-tenancy & cost tracking (base) |
| 2 | `b342e208f554` | Phase 2: Analysis runs & consolidated analysis tables |
| 3 | `d4f3e2a1b567` | Sprint 2: Tenant & TenantBilling tables with FKs |
| 4 | `f1a2b3c4d5e6` | Security: Composite indexes on tenant_id columns |
| 5 | `a1b2c3d4e5f6` | Sprint 2 Phase 10: Tasks & TaskComments tables |
| 6 | `g2b3c4d5e6f7` | Billing: UsageLog table for analytics |
| 7 | `merge_s2_s3` | Merge point: Sprint 2 → Sprint 3 |
| 8 | `s3a1` | Sprint 3: Repository table, repository_id FK on CodeComponent |
| 9 | `s3b1` | Sprint 3: source_type field on OntologyConcept (document/code/both) |
| 10 | `s3d5` | Sprint 3 Day 5: Delta analysis fields on CodeComponent |
| 11 | `s3a2` | Sprint 4 ADHOC: ConceptMapping table for cross-graph linking |

---

## Appendix B: Docker Commands

```bash
# Start all services
docker-compose up -d

# Start with rebuild
docker-compose up -d --build

# Stop all services
docker-compose down

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f app        # FastAPI backend
docker-compose logs -f worker     # Celery worker
docker-compose logs -f db         # PostgreSQL

# Restart a single service
docker-compose restart app
docker-compose restart worker

# Check service health
docker-compose ps

# Execute command inside a container
docker-compose exec app bash           # Shell into app container
docker-compose exec db psql -U postgres dokydoc   # PostgreSQL shell

# View Celery worker status
docker-compose exec app celery -A app.worker inspect active

# Purge all pending Celery tasks (CAUTION)
docker-compose exec app celery -A app.worker purge

# Reset database (CAUTION — deletes all data)
docker-compose down -v   # Removes volumes including DB data
docker-compose up -d     # Fresh start
docker-compose exec app alembic upgrade head   # Re-run migrations
```

---

## Appendix C: Troubleshooting

### Problem: "Connection refused" when accessing localhost:8000

**Cause:** App container not started or crashed.

**Fix:**
```bash
docker-compose ps          # Check if app is running
docker-compose logs app    # Check for errors
docker-compose restart app # Restart the app
```

### Problem: Document stuck in "parsing" or "analyzing" status

**Cause:** Celery worker crashed or task failed silently.

**Fix:**
1. Check Flower (`http://localhost:5555`) → look for failed tasks
2. Check worker logs: `docker-compose logs worker`
3. Restart worker: `docker-compose restart worker`
4. Re-upload the document

### Problem: "API key not valid" error in analysis

**Cause:** Invalid or missing `GEMINI_API_KEY`.

**Fix:**
1. Verify your API key is correct in `backend/.env`
2. Restart the app: `docker-compose restart app worker`

### Problem: "Rate limit exceeded" from Gemini API

**Cause:** Too many AI calls in a short period (15 RPM limit).

**Fix:**
1. Wait 60 seconds before retrying
2. The system has built-in 4-second delays between analysis calls
3. For large documents, be patient — analysis can take several minutes

### Problem: Ontology page shows no concepts after document analysis

**Cause:** Ontology extraction task may have failed.

**Fix:**
1. Check Flower for `extract_ontology_entities` task status
2. Check worker logs: `docker-compose logs worker`
3. Verify document status is "completed" (not "analysis_failed")

### Problem: Cross-graph mappings show 0 after running pipeline

**Cause:** Either only one graph has concepts, or mapping task failed.

**Fix:**
1. Verify both Document and Code tabs in Ontology show concepts
2. Check Flower for `run_cross_graph_mapping` task
3. Both a document AND a repository must be analyzed first

### Problem: Cannot log in — "Invalid credentials"

**Cause:** Wrong email/password or user doesn't exist.

**Fix:**
1. Verify you registered a tenant first (Module 2)
2. Check exact email and password used during registration
3. Password is case-sensitive

### Problem: Frontend shows blank page

**Cause:** Frontend build error or API connection issue.

**Fix:**
1. Open browser DevTools (F12) → Console for JavaScript errors
2. Check Network tab for failed API calls (red entries)
3. Verify backend is running: `http://localhost:8000/api/health`

### Problem: Webhook not triggering analysis

**Cause:** Webhook secret mismatch, repo not onboarded, or wrong URL.

**Fix:**
1. Verify `WEBHOOK_SECRET` in `.env` matches GitHub webhook configuration
2. Check the repository is onboarded in DokyDoc (Code page)
3. Check webhook delivery status in GitHub → Settings → Webhooks → Recent Deliveries
4. Check worker logs for webhook task errors

---

## End-to-End Testing Flow (Complete User Journey)

For a full end-to-end test covering the primary user journey, execute these modules in order:

```
1. Module 1  → Verify system is healthy
2. Module 2  → Register tenant "TestCo"
3. Module 3  → Login as admin
4. Module 4  → Navigate through all pages
5. Module 5  → Upload a BRD document (PDF)
6. Module 6  → Wait for analysis to complete, verify results
7. Module 7  → Onboard a GitHub repo, trigger analysis
8. Module 8  → Check Document graph in Ontology
9. Module 9  → Check Code graph in Ontology
10. Module 10 → Run cross-graph mapping, review mappings
11. Module 11 → Check gap analysis
12. Module 12 → Invite a Developer user
13. Module 13 → Check billing reflects AI usage costs
14. Module 19 → Create second tenant, verify data isolation
15. Module 20 → Test role-based access restrictions
```

**Estimated Time:** 2-3 hours for full end-to-end test

---

*Document generated for DokyDoc Sprint 4 — Manual Testing Guide*
*Last updated: February 2026*
