# Phase 9 Strategy — Analytics, Usage & Billing

> **Document type:** Strategy (NOT implementation).
> **Status:** Draft for review. Stop-and-decide before any code is written.
> **Owner perspective:** Product Owner thinking from every role in our RBAC enum.
> **GTM context:** Phase 9 is the **#1 go-to-market blocker**. Without billing we cannot charge. Without analytics, CXOs cannot justify the purchase.

---

## 1. Strategic Framing — Why Phase 9 Exists

DokyDoc today can ingest documents, analyze code, run validations, and surface mismatches. What it **cannot** do today:

1. **Show a customer the value over time** — there is no trend chart proving "docs improved from 62% coverage to 84%".
2. **Charge the customer** — no Stripe checkout, no tier enforcement, no invoicing.
3. **Protect itself from abuse** — a free-tier user today can run unlimited AI analyses and burn our Gemini budget.
4. **Tell a CXO what they're paying for** — no usage meter, no AI cost breakdown, no ROI story.

Phase 9 closes all four gaps. It is the single phase that converts DokyDoc from "interesting prototype" to "sellable SaaS product."

### The 5-Layer Mental Model

Think of Phase 9 as a stack. Each layer depends on the one below it.

```
  Layer 5  AI COST INTELLIGENCE     →  "What does each tenant cost us to serve?"
  Layer 4  BILLING & CHECKOUT       →  "How do customers pay us?"
  Layer 3  ANALYTICS & DASHBOARDS   →  "What value are they getting?"
  Layer 2  TIER ENFORCEMENT         →  "What are they allowed to do?"
  Layer 1  USAGE LOGGING            →  "What did they actually do?"
```

- **Layer 1 (Usage Logging)** is the foundation. Every AI call, every document upload, every repo scan must be counted against a tenant.
- **Layer 2 (Tier Enforcement)** reads the counts and says "stop" when limits hit.
- **Layer 3 (Analytics)** reads the same data and visualizes it for humans.
- **Layer 4 (Billing)** connects Stripe so users can self-upgrade and we get paid.
- **Layer 5 (Cost Intelligence)** is the internal-only view for us to know our margins.

We must build **bottom-up**. Shipping Layer 3 without Layer 1 means pretty graphs with fake numbers. Shipping Layer 4 without Layer 2 means taking money while users are still blocked by nothing.

---

## 2. Layman Feature Table — Everything in Phase 9

| # | Feature (Plain English) | What It Actually Does | Why It Matters | Who Uses It | Layer |
|---|-------------------------|-----------------------|----------------|-------------|-------|
| **P9.1** | **Coverage Trend Time-Series** | Every night a job snapshots "how much of your code is documented" and stores the number. Over weeks this becomes a line on a chart. | CXOs can finally show their board: "We went from 62% to 84% documentation coverage in 6 weeks — that's why DokyDoc is worth the money." | CXO, PM, BA | L3 (Analytics) |
| **P9.2** | **Analytics API** | Backend endpoints that return numbers — "total validations this month", "mismatches fixed vs open", "top 10 risky components". | Powers every dashboard. Without this, the frontend has nothing to show. | Internal (frontend) | L3 |
| **P9.3** | **Executive Analytics Dashboard** | A rich, role-aware dashboard page. A CXO sees strategic KPIs. A developer sees "my open mismatches". An auditor sees compliance counts. | This is the first thing a CXO sees on Monday morning. It's the "justify the spend" screen. | **All 6 roles** (filtered views) | L3 |
| **P9.4** | **Usage Tracking & Tier Enforcement** | Every AI call, upload, and repo scan is logged against the tenant. When a tenant hits their tier's monthly limit, the next request returns `402 Payment Required`. | Protects our Gemini budget. Creates the upgrade pressure that makes free → paid conversion happen. | ADMIN (sees limits), All (blocked at limit) | L1 + L2 |
| **P9.5** | **Usage Dashboard** | Visual meters showing "You've used 340/500 AI analyses this month (68%)" with a progress bar that turns yellow at 80% and red at 95%. | Users are never surprised by a hard block. They see it coming and upgrade proactively. | ADMIN primarily, All can view own | L3 |
| **P9.6** | **AI Cost Dashboard** | Internal-only page showing how much Gemini/OpenAI spend each tenant generates. Per tenant, per feature, per day. | We can spot a tenant burning $500/day in AI calls and either block them or upgrade them. Protects our margins. | ADMIN (internal team only — superuser flag) | L5 |
| **P9.7** | **Self-Serve Stripe Upgrade Flow** | ADMIN clicks "Upgrade to Pro" → Stripe Checkout → webhook updates tier → unlocks immediately. | Removes sales friction entirely. "Try it free, upgrade with a credit card, start using Pro features in 90 seconds." | ADMIN only (billing owner) | L4 |
| **P9.8** | **Usage Alerts & Proactive Notifications** | When a tenant hits 80% of their limit, email the ADMIN. At 100%, email + in-app banner + Slack (if wired). | Avoids the "why did it stop working?" support ticket. Turns a hard wall into a gentle upsell. | ADMIN (receives alerts), All (see banner) | L2 + L4 |

### What's Explicitly Out of Scope for Phase 9

| Not in Phase 9 | Why | Where It Lives |
|----------------|-----|----------------|
| Annual invoicing / purchase orders / NET-30 | Enterprise billing is a Phase 9.5 "sales-assisted" extension | Post-GTM |
| Per-seat pricing | v1 is per-tenant flat tiers (free/pro/enterprise) | v2 consideration |
| Multi-currency | USD only at launch | Post-Series A |
| Chargebacks / refund automation | Handled manually via Stripe dashboard at v1 | Post-GTM |
| Tax calculation (VAT/GST) | Stripe Tax handles it; we just enable it | Config flag |
| Partner / reseller billing | Not a v1 motion | Post Series A |

---

## 3. Tier Definitions (Proposed — Needs Your Sign-Off)

Before user journeys make sense, we need concrete tiers. Here is a **proposal** — open for debate.

| Tier | Price | AI Analyses / mo | Repos | Users | Documents | Retention | Support |
|------|-------|------------------|-------|-------|-----------|-----------|---------|
| **Free** | $0 | 100 | 1 | 3 | 50 | 30 days | Community |
| **Pro** | $299/mo | 2,000 | 5 | 15 | 500 | 1 year | Email (24h) |
| **Enterprise** | Custom (from $1,500/mo) | Unlimited* | Unlimited | Unlimited | Unlimited | 7 years | Dedicated CSM, SOC 2, SLA |

*"Unlimited" on enterprise still has soft caps enforced by Phase 9.6 cost dashboard — if a tenant burns >$X/day in AI we get alerted.

**Key strategic question for you:** Are these numbers right? The journey flows below assume these tiers. If we change tiers, the upgrade trigger points change.

---

---

## 4. Role-by-Role User Journeys

DokyDoc has 6 roles in the `UserRole` enum. Each role has different goals, different fears, and therefore **different views into Phase 9's data**. The same raw numbers get filtered and presented differently per role.

> **Design principle:** Phase 9 is NOT "one dashboard for everyone." It is "one data layer, six role-aware views."

### 4.1 CXO — The Buyer / Budget Owner

**Who:** CEO, CTO, CFO, Head of Engineering. The person who signed the contract.
**Their goal:** Justify the spend to the board. Prove ROI. See risk before it becomes a crisis.
**Their fear:** "Am I wasting money? Is my team actually using this? Are we safer than before DokyDoc?"
**Time they'll spend on DokyDoc per week:** 10 minutes, on Monday morning, on their phone.

#### Monday Morning Journey (the "coffee check-in")

```
 1. Opens email → sees "DokyDoc Weekly Executive Summary" from us
    [P9.8 — Usage Alerts / Weekly Digest]

 2. Clicks the "View Dashboard" button in the email → lands on DokyDoc
    login (SSO in enterprise, or magic link)

 3. Redirected to /analytics — sees the Executive Dashboard (CXO view)
    [P9.3 — Executive Analytics Dashboard, role=CXO]

 4. At the top: 4 big KPI cards
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ Coverage    │  │ Open Risks  │  │ Avg Fix     │  │ Team Active │
       │ 84% ▲ +12%  │  │    17 ▼ -5  │  │ 3.2d ▼ -1d  │  │ 28/32 users │
       └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘

 5. Below the KPIs: coverage trend line chart (6 weeks)
    [P9.1 — Coverage Trend Time-Series]
    → CXO sees: "We went from 62% to 84%. This is the graph I'll show the board."

 6. Scrolls down → "Top 5 Highest-Risk Components" table
    → Each row clickable; opens the component view in a new tab

 7. Scrolls to bottom → "Compliance Readiness" card
    → SOC 2 readiness %, audit log integrity status
    (data from Phase 6 gaps, surfaced here)

 8. Closes tab. Total time: 4 minutes. Board-ready screenshot saved.
```

**What the CXO must NOT see:** AI cost breakdown (that's internal), individual developer productivity (that's HR-sensitive), raw usage meters (that's the admin's job).

**Phase 9 features the CXO touches:** P9.1, P9.2, P9.3, P9.8 (read-only).

---

### 4.2 ADMIN — The Platform Owner / Billing Manager

**Who:** IT lead, DevOps manager, Head of Platform. The person who provisions users and pays the invoice.
**Their goal:** Keep the lights on. Manage seats. Stay within budget. Prove the tool is being used.
**Their fear:** "Are we about to hit a limit? Is the bill going to surprise me? Do I have idle seats I'm paying for?"
**Time they'll spend per week:** 30 minutes, mostly on Monday and the day before invoice renewal.

#### Journey A: End-of-Month Budget Check

```
 1. Logs in → lands on default home → clicks "Billing & Usage" in sidebar
    (new nav item in Phase 9)

 2. Sees the Usage Dashboard
    [P9.5 — Usage Dashboard]

       AI Analyses     1,847 / 2,000  ███████████████████░  92% ⚠
       Repositories        4 / 5      ████████████████░░░░  80%
       Users              12 / 15     █████████████░░░░░░░  80%
       Documents         387 / 500    ███████████████░░░░░  77%

    → Yellow/red warnings on anything >80%

 3. Notices AI analyses at 92%. Clicks the bar → drill-down.
    → "AI analyses by user this month"
    → "AI analyses by feature (validation, mismatch, chat, ...)"
    → Admin realizes Devs are running validations on every commit.

 4. Two options visible:
    a) "Change developer behavior" — no action in DokyDoc
    b) "Upgrade to Enterprise" button → opens upgrade flow
       [P9.7 — Stripe Upgrade Flow]

 5. Admin chooses (b). Stripe Checkout opens in modal.
    → Enters card (or sees existing card on file)
    → Confirms
    → Webhook fires → tier updated → page auto-refreshes
    → New dashboard shows "Unlimited" where "2,000" was

 6. Admin gets confirmation email + invoice PDF from Stripe.
    Total time: 6 minutes.
```

#### Journey B: Mid-Month Alert Response

```
 1. Gets an email at 2pm Tuesday: "⚠ DokyDoc: You've used 80% of your
    monthly AI analyses"
    [P9.8 — Usage Alerts]

 2. Clicks → lands directly on /billing/usage (deep link, SSO)

 3. Same drill-down as Journey A, but earlier in the month.

 4. Has 3 choices, all visible on the page:
    a) Wait it out (hope devs slow down)
    b) Upgrade now (button → Stripe)
    c) Add per-analysis overage pack ($0.10/analysis, no tier change)
       [⚠ OPEN QUESTION — do we offer overage packs at v1?]

 5. Admin picks one. 3-minute flow.
```

**What the ADMIN must see:** All usage, all billing, all seat info.
**What the ADMIN must NOT see:** AI cost dashboard (internal margin data), other tenants' data.

**Phase 9 features the ADMIN touches:** P9.4, P9.5, P9.7, P9.8 (primary); P9.3 (read-only).

---

### 4.3 BA — The Business Analyst

**Who:** Business analyst writing BRDs, PRDs, process docs. The "documentation person."
**Their goal:** Keep docs and code aligned. Spot mismatches fast. Prove their documentation work is valuable.
**Their fear:** "Is anyone reading my docs? Am I keeping up with what developers ship?"
**Time they'll spend per week:** 3-5 hours (heavy user). They live in DokyDoc.

#### Journey: Weekly Documentation Health Review

```
 1. Opens DokyDoc Monday morning → lands on their personalized dashboard
    [P9.3 — Executive Analytics Dashboard, role=BA]

 2. BA view is very different from CXO view:
       ┌──────────────────────────┐  ┌──────────────────────────┐
       │ Docs I Own               │  │ Mismatches on My Docs    │
       │ 23 documents             │  │ 7 open, 4 new this week  │
       └──────────────────────────┘  └──────────────────────────┘
       ┌──────────────────────────┐  ┌──────────────────────────┐
       │ Doc Coverage by Initiative│  │ Stale Docs (>30 days)    │
       │ Bar chart by project      │  │ 5 docs need review       │
       └──────────────────────────┘  └──────────────────────────┘

 3. Scrolls to "Mismatch Activity (last 7 days)"
    → Table of mismatches where BA is the doc owner
    → Clicks a row → jumps to mismatch detail (existing Phase 2 UI)

 4. Sees a "My Impact" card:
    "Docs you authored prevented 12 code-doc mismatches this quarter"
    → This is the "prove I'm valuable" number. Critical for BA morale.
    [P9.2 — Analytics API, new endpoint: /analytics/user-impact]

 5. At top-right: "AI Analyses remaining: 680" (tenant-wide counter,
    read-only for BA)
    → BA knows NOT to run 50 validations today.
    [P9.4 — Usage visibility, not enforcement, for non-admins]
```

**What the BA must see:** Their own impact, doc health, mismatch queue, tenant usage (read-only).
**What the BA must NOT see:** Billing, Stripe, cost data, admin controls.

**Phase 9 features the BA touches:** P9.1 (their trends), P9.2 (new user-impact endpoint), P9.3 (BA view), P9.5 (read-only).

---

### 4.4 DEVELOPER — The Code Author

**Who:** Software engineers writing and shipping code. They did not choose DokyDoc; their PM or CTO did.
**Their goal:** Ship features without DokyDoc getting in their way. Fix mismatches when surfaced in their PR.
**Their fear:** "Is this thing going to block my PR? Is it going to flag my code unfairly?"
**Time they'll spend on DokyDoc per week:** 15 minutes — ideally zero. They want it invisible, working through GitHub comments (Phase 7).

#### Journey: Friday Afternoon "Am I Blocking Anyone?" Check

```
 1. Dev gets a Slack DM from their PM: "Can you look at the mismatches
    on the payments initiative?"

 2. Opens DokyDoc → lands on developer dashboard
    [P9.3 — Executive Analytics Dashboard, role=DEVELOPER]

 3. Developer view is task-oriented, NOT strategic:
       ┌──────────────────────────┐  ┌──────────────────────────┐
       │ Mismatches Assigned to Me│  │ My PRs with Findings     │
       │ 4 open                   │  │ 2 this week              │
       └──────────────────────────┘  └──────────────────────────┘
       ┌──────────────────────────┐  ┌──────────────────────────┐
       │ Components I Own          │  │ My Validation Runs       │
       │ 12 components, 3 at risk  │  │ 47 this month            │
       └──────────────────────────┘  └──────────────────────────┘

 4. Clicks "Mismatches Assigned to Me" → standard mismatch list.
    Resolves 2, marks 2 as won't-fix with justification.

 5. Notices top-right: "AI Analyses: 680 remaining (tenant-wide)"
    → Dev knows they shouldn't spam re-runs.
    [P9.5 — Read-only usage visibility]

 6. Leaves. Total: 8 minutes. That's all the time devs will ever give us.
```

**Critical UX rule for developers:** Their dashboard must NOT show coverage percentages or "health scores." Developers hate being graded. Show **tasks assigned**, not **metrics earned**.

**What the DEVELOPER must see:** Their assigned work, their own usage, their components' status.
**What the DEVELOPER must NOT see:** Billing, tenant-wide coverage %, other developers' stats (no leaderboards — morale killer).

**Phase 9 features the DEVELOPER touches:** P9.2 (task-oriented endpoints), P9.3 (dev view), P9.5 (read-only usage).

---

### 4.5 PRODUCT_MANAGER — The Feature Owner

**Who:** PMs owning initiatives/features. They coordinate BAs + developers + stakeholders.
**Their goal:** Ship initiatives on time with high quality. Know when something is slipping.
**Their fear:** "Is my initiative healthy? Am I about to miss a deadline? Are there hidden risks in the code nobody told me about?"
**Time they'll spend per week:** 1-2 hours. They're the "checks the dashboard daily" user.

#### Journey: Daily Initiative Health Scan

```
 1. Morning stand-up at 9:30. PM opens DokyDoc at 9:15 to prep.

 2. Lands on PM dashboard
    [P9.3 — Executive Analytics Dashboard, role=PRODUCT_MANAGER]

 3. PM view is initiative-centric:
       ┌─────────────────────────────────────────────────────┐
       │ My Initiatives (3 active)                           │
       │ ─────────────────────────────────────────────────── │
       │ ▸ Payment Gateway v2    Health: 78 🟡  Mismatches: 5│
       │ ▸ Mobile Auth Overhaul  Health: 91 🟢  Mismatches: 1│
       │ ▸ Reporting Revamp      Health: 54 🔴  Mismatches:12│
       └─────────────────────────────────────────────────────┘

    → Health scores come from Phase 6 gap (initiative health service).
    → Phase 9 surfaces them on the PM dashboard.

 4. Clicks "Reporting Revamp" (the red one) → drill-down.

 5. Sees initiative timeline: "Health was 82 last week, dropped to 54"
    [P9.1 — Time-series extended to initiative health]
    → Chart shows the drop started 3 days ago.

 6. Sees "Top Contributing Risks":
       - 8 new mismatches on `report_generator.py` (assigned to @alice)
       - 4 stale docs not updated after code change
       - 1 critical validation failure

 7. PM has their stand-up agenda: "Alice, let's talk about report_generator.
    Bob, let's refresh the reporting docs."

 8. Sub-10-minute flow. PM uses DokyDoc as a daily leading indicator.
```

**What the PM must see:** Initiative health, trend over time, contributing risks, team assignments.
**What the PM must NOT see:** Billing (admin only), cross-tenant data, raw AI cost.

**Phase 9 features the PM touches:** P9.1 (initiative trends), P9.2 (initiative endpoints), P9.3 (PM view), P9.5 (read-only usage).

---

### 4.6 AUDITOR — The Compliance Reviewer

**Who:** Internal auditor, external SOC 2 assessor, regulator, security officer.
**Their goal:** Verify DokyDoc is being used for compliance. Export evidence. Prove tamper-evidence.
**Their fear:** "Can I trust these audit logs? Can I prove nothing was deleted? Can I pull a report fast?"
**Time they'll spend per week:** Heavy during audits (hours/day), zero between audits.

#### Journey: Quarterly Compliance Export

```
 1. Auditor logs in → lands on auditor-specific dashboard
    [P9.3 — Executive Analytics Dashboard, role=AUDITOR]

 2. Auditor view is evidence-centric:
       ┌─────────────────────────────────────────────┐
       │ Audit Log Integrity                         │
       │ ✅ Hash chain verified (487,302 entries)    │
       │ Last verification: 2 hours ago               │
       │ [Re-verify now]  [Download certificate]      │
       └─────────────────────────────────────────────┘
       ┌─────────────────────────────────────────────┐
       │ This Quarter's Activity                     │
       │ • 12,847 validations executed                │
       │ • 1,203 mismatches resolved                  │
       │ • 47 approvals granted                       │
       │ • 0 audit log anomalies detected             │
       └─────────────────────────────────────────────┘

    → Hash chain integrity comes from Phase 6 Gap 2 (audit checksum).

 3. Clicks "Export Evidence Package" (new Phase 9 button)
    → Modal asks: date range, format (PDF/CSV/JSON), include attachments?
    → Click Generate.

 4. Background job compiles:
       - Full audit log for range (hash-chain verified)
       - Usage metrics for range (P9.1 time-series)
       - Approval history (from Phase 6)
       - Initiative health history (from Phase 6)
    → Outputs a signed ZIP.

 5. Email arrives in 3-5 minutes with download link.
    Auditor hands the ZIP to SOC 2 assessor.

 6. Auditor also uses the "Integrity Re-verify" button as a spot check
    and downloads the integrity certificate (PDF).

 7. Total time: 12 minutes for a full-quarter evidence export that
    used to take a week of manual work.
```

**What the AUDITOR must see:** All audit events, integrity proofs, evidence exports.
**What the AUDITOR must NOT see:** Billing (unless explicitly given admin), AI cost data (not their concern), ability to modify anything (read-only everywhere).

**Phase 9 features the AUDITOR touches:** P9.2 (export endpoints), P9.3 (auditor view). Bridges heavily to Phase 6 Gaps 2 & 3.

---

## 5. Cross-Role Summary Matrix

Who sees what in Phase 9, at a glance:

| Feature | CXO | ADMIN | BA | DEV | PM | AUDITOR |
|---------|-----|-------|----|----|----|---------|
| Coverage trend chart (P9.1) | Read | Read | Read | — | Read | Read |
| Analytics API (P9.2) | via UI | via UI | via UI | via UI | via UI | via UI |
| Exec Dashboard (P9.3) | CXO view | Admin view | BA view | Dev view | PM view | Auditor view |
| Usage Tracking (P9.4) | Read | **Enforce** | Read | Read | Read | Read |
| Usage Dashboard (P9.5) | Read summary | **Full control** | Read | Read | Read | Read |
| AI Cost Dashboard (P9.6) | — | Superuser only | — | — | — | — |
| Stripe Upgrade (P9.7) | — | **Primary** | — | — | — | — |
| Usage Alerts (P9.8) | Weekly digest | **Real-time** | — | — | Weekly digest | — |

Legend: **Bold** = primary owner; "Read" = read-only; "—" = not visible.

---

## 6. Strategic Decision Questions (Need Your Input Before Implementation)

Before we write a single line of code, I need answers to these strategic questions. Each choice meaningfully changes the implementation.

### Q1. Tier pricing — are the proposed numbers right?
The tier limits in Section 3 (Free 100/Pro 2000/Enterprise unlimited, $0/$299/$1500+) drive every enforcement rule. If these change, the usage thresholds, alert triggers, and upgrade copy all change.
**Default if you don't decide:** Ship with the table in Section 3.

### Q2. Hard block or overage charges at tier limits?
- **Option A (Hard Block):** At 100% the next request returns 402. User must upgrade. Simple. Creates urgency.
- **Option B (Overage Charges):** Beyond limit, charge per-unit (e.g., $0.10 per AI analysis). More revenue, more complexity, more surprise bills.
- **Option C (Soft Throttle):** Slow down instead of blocking. Friendly but users don't feel the pain that drives upgrades.
**My recommendation:** Option A for v1. Overage packs (Option B) as a Phase 9.5 add-on.

### Q3. Does the "AI Cost Dashboard" ship with Phase 9 or later?
P9.6 is **internal-only** (superuser flag). It's valuable (margin protection) but not customer-facing.
- **Ship now:** We know our margins from day 1. Extra week of work.
- **Ship later:** Launch faster; accept margin blindness for a few weeks.
**My recommendation:** Ship a minimal v1 now — per-tenant daily Gemini cost, no drilldowns. 2 days of work.

### Q4. Stripe integration depth at launch?
- **Option A (Checkout-only):** Users check out on Stripe's hosted page. Fastest. Less brand control.
- **Option B (Stripe Elements, embedded):** Users never leave DokyDoc. 2-3 days more work.
- **Option C (Stripe Billing Portal):** Users manage everything via Stripe's portal (change plan, update card, view invoices).
**My recommendation:** A + C. Checkout for new upgrades, Billing Portal for management. Minimal code, professional UX.

### Q5. Usage alerts — channels at v1?
- Email: **must have**
- In-app banner: **must have**
- Slack: depends on Phase 7 timing
- SMS: probably never
**My recommendation:** Email + in-app banner at v1. Slack via Phase 7 integration.

### Q6. Role-aware dashboards — one page or six pages?
- **Option A (One page, server-filtered):** `/analytics` returns different data based on current user's role. Simpler routing.
- **Option B (Six distinct pages):** `/analytics/cxo`, `/analytics/admin`, etc. More code, cleaner per-role logic.
**My recommendation:** Option A. Single page, server decides what to return. Frontend renders conditionally.

### Q7. Historical backfill for coverage trends?
Phase 9.1 starts capturing snapshots from day-of-deploy. But existing tenants have months of data **pre-capture**.
- **Option A:** Start fresh. Trend line begins today. First chart is empty for 2 weeks.
- **Option B:** Backfill by replaying historical audit events to reconstruct trends. Complex, imperfect.
**My recommendation:** Option A + a "we started tracking trends on YYYY-MM-DD" banner.

### Q8. Sequencing — what ships first?
We can't ship all 8 features at once. What's the minimal first slice that unlocks revenue?

**Proposed minimum-viable Phase 9 (MVP):**
1. P9.4 Usage Logging (Layer 1) — silently count everything
2. P9.4 Tier Enforcement (Layer 2) — block at limit
3. P9.7 Stripe Checkout (Layer 4) — take money
4. P9.5 Usage Dashboard (L3) — admin can see limits
5. P9.8 Basic Alerts (email only)

**Deferred to Phase 9.1 (ships 1-2 weeks after MVP):**
- P9.1 Coverage Trends (beautiful but doesn't unlock revenue alone)
- P9.3 Full role-aware dashboards (CXO view is enough at launch)
- P9.6 AI Cost Dashboard
- P9.2 extended analytics endpoints

**Rationale:** MVP ships in ~2 weeks and unlocks paying customers. Full Phase 9 follows in week 3-4. This de-risks the GTM timeline.

---

## 7. What Happens After You Answer These Questions

Once you sign off on the 8 questions above, I will:

1. Create `PHASE_9_IMPLEMENTATION_PLAN.md` with ticket-level detail (exact files, exact lines, exact migrations — same format as the Phase 6 gaps doc).
2. Break Phase 9 into **small, shippable chunks** (each ~1 day of work).
3. Announce each chunk before starting ("Now writing P9.4 Gap 1 — tenant usage counters") and confirm after finishing ("P9.4 Gap 1 complete").
4. Never touch code until you've approved the plan.

---

## 8. Open Questions Parking Lot (for later)

These are important but don't block Phase 9 MVP. Capturing so we don't forget.

- Per-seat pricing (vs flat tenant pricing)
- Team-level budgets (PM gets 500 analyses, BA gets 200, etc.)
- Free trial extension logic (14-day → 21-day for engaged users)
- Referral credits ("invite a colleague, get 100 free analyses")
- Annual plans (discount for paying yearly)
- Volume discounts for enterprise
- Pausing a subscription (vs cancel)
- Downgrade flow (Pro → Free without losing data)

---

## 9. Document Status

| Part | Status |
|------|--------|
| 1. Strategic framing + feature table | ✅ Complete |
| 2. Role-based user journeys (all 6 roles) | ✅ Complete |
| 3. Cross-role summary matrix | ✅ Complete |
| 4. Strategic decision questions | ✅ Complete — awaiting your answers |
| 5. Implementation plan | ⏸ Blocked on Q1-Q8 sign-off |

**You are here:** Read this doc, answer Q1-Q8, then we go to implementation.
