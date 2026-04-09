# DokyDoc — What's Left to Build & Go-To-Market Roadmap

---

## The Simple Picture

**Done:** Phases 0, 1, 2 (foundation, training data capture, smart mapping)
**Plans Ready:** Phases 3, 4, 5 (data flow diagrams, 4-engine integration, industry-aware prompts)
**Needs Planning:** Phases 6–17 (enterprise features, integrations, billing, performance, security, AI)

---

## Layman Table: Everything Pending

| # | What Is It? | Why Does It Matter? | Status | Can Start Now? | How Big? | Blocks GTM? |
|---|-------------|---------------------|--------|----------------|----------|-------------|
| **3** | **Data Flow Diagrams** — Visual maps showing how data moves through code (e.g., "User clicks Register -> AuthService -> Database") | Killer feature for demos. CXOs and BAs finally understand code visually. Premium upsell. | Plan ready | Yes | 2 weeks | No — nice to have |
| **4** | **4-Engine Integration** — Make our 4 AI engines talk to each other instead of working in silos | Cuts Gemini API costs by 75-80%. Same quality, 4x cheaper to run. Directly improves margins. | Plan ready | Yes | 1 week | No — but saves money fast |
| **5** | **Industry-Aware AI** — AI knows if you're a fintech (PCI-DSS) or hospital (HIPAA) and adjusts analysis accordingly | Every output becomes smarter. "Payment" means different things in banking vs healthcare. | Plan ready | Yes | 1 week | No — but improves quality |
| **6** | **Enterprise Governance Gaps** — SLA tracking on approvals, tamper-proof audit logs, initiative health scores | Banks and hospitals won't buy without audit trails they can show regulators. ~65% already built. | **Needs plan** | Yes | ~1 week (gap fill) | **YES** — enterprise deals |
| **7** | **Integrations** — Jira sync (both ways), Confluence publishing, GitHub PR comments, Slack alerts | Enterprise teams live in Jira/GitHub/Slack. If findings don't flow there, nobody opens DokyDoc. | Needs plan | Yes | 2-3 weeks | **YES** — adoption blocker |
| **8** | **Smart Search & Chat** — Search across everything (docs, code, mismatches) at once. Chat with slash commands. | "Which BRDs mention payments?" answered in 2 seconds instead of 20 minutes of clicking. | Needs plan | After Phase 5 | 2-3 weeks | No — engagement feature |
| **9** | **Analytics & Billing** — Coverage trend charts, usage meters, Stripe checkout, tier enforcement | **Without billing, there is zero revenue.** Without analytics, CXOs can't justify the purchase. | Needs plan | Yes | 2 weeks | **YES — #1 GTM BLOCKER** |
| **10** | **LLM Training Foundation** — Pipeline to clean, version, and evaluate training data for future fine-tuning | Not urgent now, but every week without it the training data becomes harder to use later. | Needs plan | Yes | 3 weeks | No — strategic/long-term |
| **11** | **Living Documentation** — Auto-regenerate docs when code changes. Multi-source synthesis. Diff view. | The feature enterprises will pay the most for. But needs Phase 5 first. | Needs plan | After Phase 5 | 2-3 weeks | No — but flagship feature |
| **12** | **Performance & Scale** — Database indexes, caching, worker queues, load testing | At 10 tenants it's fine. At 100+ tenants with big repos, it will crash. Fix before scaling. | Needs plan | Yes | 2 weeks | **YES** — if scaling soon |
| **13** | **Developer Experience** — Python SDK, CLI tool for CI/CD, API playground, docs site | Developers need `pip install dokydoc` not raw HTTP calls. Self-serve = faster adoption. | Needs plan | After Phase 7 | 2-3 weeks | No — post-launch |
| **14** | **Security (SOC 2)** — Secrets manager, encryption, MFA, JWT hardening, vulnerability scanning | Banks literally cannot sign a contract without SOC 2 evidence. Non-negotiable for regulated industries. | Needs plan | After Phase 6 | 3 weeks | **YES** — regulated deals |
| **15** | **Observability** — Distributed tracing, structured logs, SLOs, alerting, incident runbooks | When an enterprise says "it was slow this morning," you need an answer in 30 seconds, not 30 minutes. | Needs plan | After Phase 12 | 2 weeks | No — but needed for SLAs |
| **16** | **Multi-Region & DR** — Backups, failover, EU data residency, disaster recovery playbook | EU customers = GDPR data residency. Banks = "what if your server goes down?" Must have answers. | Needs plan | After 12+14+15 | 4 weeks | No — post Series A |
| **17** | **Custom AI Models** — Fine-tune our own models, per-tenant LoRA adapters, multimodal (diagrams) | The long-term moat. Stop paying Gemini for everything. But needs 500+ labeled examples first. | Needs plan | After Phase 10 | 6+ weeks | No — competitive moat |

---

## Deep GTM Strategy Analysis

### The Core Question: What Must Exist Before the First Paying Customer?

A customer goes through this journey:

```
Discover DokyDoc → Try it (free tier) → See value (analytics) → Want to pay (billing)
   → Integrate into workflow (Jira/GitHub) → Get team onboard (governance/RBAC)
      → Pass security review (SOC 2/audit) → Sign enterprise contract
```

Every broken link in this chain = no deal. Let's map phases to the chain:

| Customer Journey Step | What's Needed | Phase | Built? |
|----------------------|---------------|-------|--------|
| 1. Try the product | Core analysis works | 0, 1, 2 | DONE |
| 2. See smart results | Industry-aware AI, 4-engine efficiency | 3, 4, 5 | Plan ready |
| 3. See value clearly | Analytics dashboard, coverage trends | **9** | **NOT BUILT** |
| 4. Pay for it | Stripe billing, tier enforcement | **9** | **NOT BUILT** |
| 5. Use daily | Jira/Slack/GitHub integration | **7** | NOT BUILT |
| 6. Get team on board | RBAC, approvals, initiative tracking | **6** | ~65% built |
| 7. Pass procurement | Audit trail, SOC 2 evidence | **6 + 14** | ~50% built |
| 8. Scale usage | Performance, multi-repo | **12** | NOT BUILT |

### The 3 Absolute GTM Blockers

**BLOCKER 1: Phase 9 (Analytics & Billing) — "Can they pay us?"**
- Without Stripe checkout → literally zero revenue, no matter how good the product is
- Without coverage trend charts → CXOs can't show board "look, docs improved 62% to 84%"
- Without tier enforcement → free users get everything, no upgrade pressure
- Without usage meters → users don't know they're approaching limits
- **Impact of delay:** Every week without billing = every demo ends with "we'll invoice manually" (kills conversion)

**BLOCKER 2: Phase 7 (Integrations) — "Can they use it daily?"**
- Jira sync is table stakes — if mismatches don't become Jira tickets, developers ignore them
- GitHub PR comments — the "aha moment" when a developer sees DokyDoc comment on their PR
- Slack alerts — CXOs get notified when critical mismatches appear, without logging into DokyDoc
- **Impact of delay:** Pilot customers try it once, never come back because it's disconnected from their workflow

**BLOCKER 3: Phase 6 Gaps + Phase 14 (Governance & Security) — "Can they sign the contract?"**
- Enterprise procurement teams send security questionnaires before signing
- Without tamper-proof audit logs → fail SOC 2 readiness check
- Without MFA → fail security questionnaire item #1
- The ~65% already built in Phase 6 means this is fast to close
- **Impact of delay:** Enterprise deal cycles are 3-6 months. Starting late means revenue 6+ months later.

### What Can Wait (Post-GTM)

| Phase | Why It Can Wait |
|-------|----------------|
| 8 (Search/Chat) | Nice feature, not a purchase decision driver. Current chat works. |
| 10 (LLM Strategy) | Training data is accumulating automatically (Phase 1). No urgency. |
| 11 (Auto-Docs) | Important but existing auto-docs work. Living docs is v2. |
| 12 (Performance) | Only matters at scale. Fix when you have 50+ tenants, not before. |
| 13 (Developer Experience) | SDK/CLI matters after you have enterprise customers asking for CI/CD. |
| 15-17 (Observability, Multi-Region, Custom AI) | Post-Series A investments. |

---

## Recommended Execution Order for GTM

```
PHASE     WHAT                          WHY                           TIME
------    ----------------------------  ----------------------------  --------
NOW       Phase 3 + 4 + 5 (parallel)   Core product polish           2 weeks
          Plans are ready, just code.   (cost savings + smarter AI)

NEXT      Phase 9 — Billing & Analytics THE #1 GTM BLOCKER            2 weeks
          Stripe, tier gates, trends    Can't charge = can't launch

NEXT      Phase 7 — Integrations        #2 BLOCKER: daily adoption    2-3 wks
          Jira + GitHub + Slack          No workflow = no stickiness

PARALLEL  Phase 6 gaps (~35%)           Quick win, closes enterprise  ~1 week
          Audit chain, initiative health governance loop

THEN      Phase 14 — Security            Enterprise contract blocker  3 weeks
          SOC 2, MFA, JWT hardening      Banks/hospitals need this

          ========= GTM READY =========

POST-GTM  Phase 12 (Performance)         Scale prep                   2 weeks
          Phase 8 (Search/Chat)          Engagement                   2-3 wks
          Phase 11 (Living Docs)         Flagship upsell              2-3 wks
          Phase 13 (SDK/CLI)             Self-serve                   2-3 wks

LATER     Phase 10, 15, 16, 17          Strategic / post Series A
```

### Total Time to GTM-Ready: ~10-11 weeks (with parallelism)

The critical path is: **Phase 9 → Phase 7 → Phase 14** (7-8 weeks sequential).
Phases 3/4/5/6 can run in parallel with Phase 9, compressing the timeline.

---

## Phase 6 Current State (What's Built vs What's Missing)

| Sub-task | Master Plan | Already Built? | Remaining Gap |
|----------|-------------|----------------|---------------|
| P6.1 RBAC Hardening | 6 roles, 20+ permissions | **DONE** — 6 roles (CXO, ADMIN, BA, DEV, PM, AUDITOR), 32+ permissions | None |
| P6.2 Approval Workflow | Configurable gates, SLA | **MOSTLY DONE** — 3-level approvals, auto-approve | SLA deadline tracking, Celery escalation task, tenant-configurable approval gates |
| P6.3 Approval Frontend | Pending/history/bulk | **DONE** — Full tab UI, detail modal, actions | None (minor: bulk approve button) |
| P6.4 Audit Hardening | Checksum chain, retention | **PARTIAL** — Middleware logging, analytics, anomalies | Checksum hash chain, retention policy, legal hold flag |
| P6.5 Initiative Health | Health score, gap report | **PARTIAL** — CRUD + endpoints | Health score computation, cross-asset validation summary, BOE gap report |
| P6.6 Multi-Repo Analysis | Cross-repo within initiative | **NOT DONE** | Full feature: unified cross-repo concept graph, cross-repo validation |
| P6.7 User Management UI | Admin with new roles | **DONE** — Full admin page | None |
| P6.8 Invite System | Email-based invite | **DONE** — POST /users/invite | None |

**Estimated remaining effort: ~5-7 days for 1 developer**

> See `PHASE_6_IMPLEMENTATION_PLAN_GAPS.md` for the detailed implementation plan of remaining gaps.
