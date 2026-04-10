# Phase 9 — Billing, Wallet & Analytics (Plain-English Strategy)

> **Who this document is for:** Anyone — founders, investors, sales team, customers, non-technical team members. You do **not** need to be a developer to understand this.
> **Last updated:** April 2026
> **Status:** Locked-in strategy. Implementation plan lives in `PHASE_9_IMPLEMENTATION_PLAN.md`.

---

## 1. What is Phase 9 in One Sentence

> Phase 9 is how **DokyDoc starts earning real money** — it turns our free prototype into a product customers can pay for using UPI, cards, or net banking, with complete honesty about every rupee they spend.

That's it. Everything in this document flows from that one goal.

---

## 2. The Problem We Are Solving

Right now (April 2026), DokyDoc works beautifully:

- ✅ It reads your documents
- ✅ It analyzes your code
- ✅ It finds gaps between what your documents say and what your code does
- ✅ It shows dashboards, runs validations, answers questions

**But there is one thing it cannot do: take money from a customer.**

Until we fix that, DokyDoc is a free gift to the world. We are paying Google and Anthropic every time a customer uses it, and nothing is coming back. Phase 9 fixes this — without turning DokyDoc into one of those pushy SaaS products that nickels-and-dimes its users.

### What we will NOT do

We have deliberately **rejected** the usual SaaS playbook:

| ❌ What most SaaS does                  | ✅ What DokyDoc does instead                          |
| --------------------------------------- | ----------------------------------------------------- |
| 3–5 fixed tiers (Starter/Pro/Business)  | No tiers. One wallet. Pay for what you use.           |
| Hide the actual cost from users         | Show every token, every rupee, every model call       |
| Charge 3×–10× markup on AI costs        | Charge just **15%** on top of what Google charges us  |
| Lock features behind expensive plans    | All features available to everyone                   |
| Auto-charge surprise overage fees       | You spend what's in your wallet. Never a rupee more. |
| Force yearly commitments                | Recharge ₹100 today, come back next month if you like |

The philosophy is simple: **build trust first, profits later.** We are okay making no profit for the first 2–3 years as long as we are not burning our own money. The goal is word-of-mouth growth, not extraction.

---

## 3. How the Money Actually Works — The Wallet Model

Think of DokyDoc like a **mobile phone recharge**, not like Netflix.

### The wallet — in 4 steps

1. **You sign up.** DokyDoc puts ₹100 into your wallet as a free welcome gift. No card, no commitment.
2. **You use the product.** Every time DokyDoc analyzes a document or runs code analysis, a small amount is deducted from your wallet — usually a few rupees per document.
3. **You run low.** When your wallet drops below ₹100, we send you a friendly reminder email. Nothing stops working yet.
4. **You recharge.** Open the Billing page, pick a recharge amount (₹100 / ₹200 / ₹500 / ₹1,000 / ₹2,500 / ₹5,000, or type any custom amount), pay via UPI / Google Pay / PhonePe / card / net banking, and your wallet is topped up within seconds.

**That's the entire business model.** No subscriptions, no auto-renewals, no hidden fees, no "plans" to upgrade or downgrade.

### A concrete example

Let's say you are a Business Analyst at a mid-sized bank. You upload a 20-page PRD for a new loan product and ask DokyDoc to analyze it.

| What happens                                   | What it costs you   |
| ---------------------------------------------- | ------------------- |
| DokyDoc reads the PRD                          | ~₹1.50              |
| DokyDoc breaks it into requirements            | ~₹1.20              |
| DokyDoc extracts business rules                | ~₹2.80              |
| DokyDoc checks it against your existing code   | ~₹0.80              |
| **Total for the whole document**               | **~₹6.30**          |

Before DokyDoc does anything, it shows you a **cost preview**: "This will cost approximately ₹6–8. Continue?" You click yes. After it's done, you see the exact amount charged along with a breakdown showing every AI call, token count, and rupee spent.

If you don't have enough money in your wallet, DokyDoc simply stops and asks you to recharge. **It never charges you without permission.**

---

## 4. The 15% Markup — Why We Picked It (and Why It's Fair)

Here is something almost no SaaS company will show you: **the exact split between what they pay for AI and what they charge you.**

DokyDoc will.

### The math

When Google or Anthropic charges us for running your document through their AI, we call that the **raw cost**. On top of that raw cost, we add a **15% flat platform fee**. That's it.

```
What you pay  =  Raw AI cost  +  15% platform fee
              =  (what Google/Anthropic actually charged us)  ×  1.15
```

### Why 15% and not 100% or 300%?

Most AI-powered products charge 3× to 10× their raw AI cost. The logic is "we built the software, we deserve the margin." That's a normal business.

We chose differently. Here's why:

1. **Trust is the biggest moat.** A customer who sees the raw cost of ₹5.50 + ₹0.82 markup on their receipt will tell their friends. A customer who realizes you charged them ₹22 for a ₹5.50 service will tell their friends too — just a different story.
2. **Our real competitors are DIY builds.** Any tech team can build a simple version of DokyDoc in a weekend with Gemini or Claude. If we charge too much, they will. At 15% markup we are *cheaper than doing it yourself* once you factor in engineering time.
3. **India is a price-sensitive market.** A ₹1,500 monthly software bill is a hard sell to a 20-person company. A ₹200 pay-as-you-go wallet is not.
4. **We need cash flow, not profit.** The 15% covers our server costs, Razorpay fees, and keeps us alive. That is enough for the first 2–3 years.

### The trade-off we are accepting

We will not make meaningful profit from the AI markup alone. Our future profit will come from:

- **Volume** — lots of small customers instead of a few big ones
- **Enterprise contracts** — large companies who want postpaid invoicing, SLAs, and custom features (these are manually negotiated, not advertised on the website)
- **Word of mouth** — the cheapest marketing there is

This is a long game. We are willing to play it.

---

## 5. Model Routing — Free vs Paid (In Plain English)

A question everyone asks: *"Gemini and Claude are expensive. How do you give ₹100 free credit without going broke?"*

The answer is **model routing** — giving free users a cheaper, smaller AI model, and letting paying users pick whichever premium model they like.

### The two lanes

| Lane         | Who uses it                            | Which AI model                               | Cost per document (approx) |
| ------------ | -------------------------------------- | -------------------------------------------- | -------------------------- |
| **Free lane** | Everyone on signup (₹100 welcome gift) | **Gemini 3 Flash-Lite** (small & cheap)      | ₹1 – ₹3 per document       |
| **Paid lane** | Anyone who has recharged their wallet  | Pick one: Gemini 3 Flash, Claude Sonnet 4.6, or Claude Haiku 4.5 | ₹4 – ₹12 per document |

### Why this works

- On Flash-Lite, ₹100 of free credit actually gets you **30–100 documents** worth of analysis — enough to genuinely try the product and decide if it's worth paying for.
- The free lane isn't a crippled demo. The small model still produces real, useful analysis. It's just slightly slower and slightly less detailed than the premium models.
- The moment you recharge even ₹100 into your wallet, the premium models unlock. You pick which one to use from a dropdown, and every document tells you up-front which model it will use and what it will cost.
- You can switch models at any time. Different documents, different models. One complex regulatory PRD might use Claude Sonnet 4.6 for deep reasoning; a simple change request might use Gemini 3 Flash-Lite for speed.

### Why we rejected the "two Google accounts" idea

Early on, we considered silently using Google's free credit account to serve paying customers — pocketing the difference. We decided against this because:

1. It violates Google's Terms of Service (one free trial per organization).
2. Google's free AI Studio trains on the data customers send. We would be leaking our customers' confidential documents to Google's training pipeline.
3. If Google detects this, our entire account gets banned — killing the product overnight.

Model routing achieves the same outcome (cheap free tier, sustainable paid tier) without breaking rules or risking customer data.

### Important deadline — Gemini 2.5 Flash deprecation

Google is shutting down Gemini 2.5 Flash on **June 17, 2026**. DokyDoc currently uses 2.5 Flash for everything. Before that date we must migrate to Gemini 3 Flash (for the paid lane) and Gemini 3 Flash-Lite (for the free lane). This is tracked as a P0 item in the implementation plan.

---

## 6. How Customers Actually Pay Us — Razorpay

We picked **Razorpay** as our payment gateway. For non-technical readers, a payment gateway is the company that sits between DokyDoc and the customer's bank — it handles the actual money movement, takes care of card security, and deposits the cleared funds into our bank account.

### Why Razorpay (not Stripe, not PayPal)

| What we needed                                   | Why Razorpay wins                              |
| ------------------------------------------------ | ---------------------------------------------- |
| Accept Indian customers (UPI, Rupay, net banking) | Razorpay is India-first; UPI works out of the box |
| Low fees on UPI                                  | **0% on UPI**, ~2% on cards                   |
| Fast settlement to our bank account              | T+2 business days                              |
| Compliance with RBI rules                        | Razorpay handles KYC, GST invoicing, tax filing |
| Easy integration                                 | 2–3 days of developer work                     |

We will add **Stripe** later (Phase 9.5 or Phase 12) when we start getting international customers who want to pay in USD.

### The payment flow — what the customer sees

1. Customer clicks "Recharge ₹500" in the Billing page
2. A Razorpay popup appears with buttons for UPI, Google Pay, PhonePe, Paytm, Credit Card, Debit Card, and Net Banking
3. Customer picks their method and completes the payment (usually takes 10–30 seconds on UPI)
4. Razorpay tells DokyDoc "yes, this payment is real, ₹500 has cleared"
5. DokyDoc adds ₹500 to the customer's wallet instantly
6. Customer gets a GST-compliant invoice via email

No redirects to sketchy third-party pages. No "sign up with our payment provider" dark patterns. One click, done.

### The GSTIN blocker — what's on hold

There is one thing stopping us from turning Razorpay on today: **we do not yet have a GSTIN (Goods and Services Tax Identification Number).**

Razorpay will not let us accept money until we register our business with the Indian tax department and receive a GSTIN. This is a legal requirement, not a technical one.

**What this means for the plan:**

- ✅ **Track A** (everything that does NOT need Razorpay) — we build this right now. This includes the wallet system, the 15% markup logic, model routing, the Gemini 3 migration, the cost export feature, the analytics dashboards, and the demo organization setup. Roughly 80% of Phase 9.
- ⏸️ **Track B** (everything that DOES need Razorpay) — we write the code but keep it behind a feature flag. The moment our GSTIN arrives, we flip the flag and go live. Roughly 20% of Phase 9.

This way, the GSTIN delay does not block our engineering work. We keep shipping, and the "final switch" is just a config change when the paperwork comes through.

---

## 7. The Customer Journey — What Users Actually See

Here is what a brand-new customer experiences in their first week on DokyDoc.

### Day 0 — Signup

1. User lands on dokydoc.ai, clicks "Start free"
2. Fills in company name, email, password. No credit card asked.
3. Lands on the dashboard. A green banner at the top says:
   > 🎁 Welcome! You have **₹100 free credit** to try DokyDoc. No card needed.

### Day 1 — First document upload

1. User uploads a PRD
2. Before analysis starts, a small modal appears:
   > This document will use **Gemini 3 Flash-Lite** (free lane). Estimated cost: **₹2.40**. Wallet balance after: **₹97.60**. [Cancel] [Continue]
3. User clicks Continue. Analysis runs. After ~90 seconds, results appear.
4. On the results page, a small footer shows:
   > 💰 This analysis cost **₹2.35** (raw: ₹2.04 + platform fee: ₹0.31). [See full breakdown]

### Day 3 — Hits the ₹100 limit

1. User has analyzed ~35 documents. Wallet is down to ₹5.
2. User tries to upload doc #36.
3. A friendly modal appears:
   > Your wallet has **₹5 left** — not enough for this document (~₹2.40). Recharge to continue. [Recharge ₹100] [Recharge ₹500] [Custom amount]
4. User clicks "Recharge ₹500"
5. Razorpay popup → UPI → done in 15 seconds
6. Wallet now shows **₹505**. Premium models unlock (Gemini 3 Flash, Claude Sonnet 4.6, Claude Haiku 4.5) in the model picker.

### Day 5 — Power user

1. User uploads a complex regulatory document
2. Picks Claude Sonnet 4.6 from the dropdown (since reasoning quality matters more than speed)
3. Cost preview: "Estimated ₹18–25"
4. User continues. Charged ₹22.40. Wallet goes from ₹505 → ₹482.60.

### Day 7 — CFO wants a cost report

1. User's CFO asks: "How much did we actually spend on DokyDoc this week?"
2. User goes to **Billing → Export**
3. Picks "Last 7 days" and format **PDF** (other options: CSV, JSON, DOCX)
4. Downloads a beautifully formatted PDF with:
   - Total spent this week
   - Breakdown by day
   - Breakdown by document
   - Breakdown by model used
   - Breakdown by team member
   - Raw cost + platform fee separated for every line item
5. Forwards it to the CFO. CFO is happy. User is happy.

### What this journey proves

- **No surprises.** The customer sees the cost before every action.
- **No lock-in.** They paid ₹500 because they wanted to, not because they were forced into a subscription.
- **No hidden margins.** Every line item shows raw cost and platform fee separately.
- **Enterprise-ready reporting.** Even a single-user account can produce a CFO-grade cost report.

---

## 8. The Demo Organization — How We Show DokyDoc to Prospects

Sales calls need a realistic account to demo. Not an empty one. Not a messy developer test account. A polished, purpose-built demo environment.

Phase 9 includes a **one-command demo organization seeder** that creates:

1. A fresh tenant called "Acme Corp (Demo)" with realistic branding
2. **6 pre-seeded user accounts** — one per role (CXO, Admin, BA, Developer, Product Manager, Auditor) — so the salesperson can log in as any role and show the role-specific view
3. **5 sample documents** pre-analyzed (a PRD, an SRS, an API spec, a regulatory doc, a change request) — so the demo is not waiting 90 seconds for Gemini during a live call
4. **A populated wallet** with ₹5,000 starting balance and a realistic transaction history showing 20+ past deductions and 3 past recharges
5. **Coverage trends** already computed for the last 30 days, so the CXO dashboard shows the "we went from 62% to 84%" story out of the box
6. **Mismatches in every state** — open, fixed, escalated, resolved — so the workflow demo is rich

Running the seeder is a single command:

```bash
python -m app.scripts.seed_demo_org --name "Acme Corp" --reset
```

### Why this matters

Every enterprise SaaS sales call lives or dies in the first 90 seconds of the demo. An empty dashboard is a lost deal. A pre-populated demo org lets the salesperson walk into any call and say "let me show you what this looks like for a real customer" — without exposing any actual customer data.

The demo org can be reset and re-seeded before every call, so it is always clean.

---

## 9. What Gets Downloaded — Cost Reports in 4 Formats

Customers can download their usage data in **4 formats**. Different stakeholders want different things.

| Format   | Who uses it                       | Why they want it                                       |
| -------- | --------------------------------- | ------------------------------------------------------ |
| **CSV**  | Analysts, ops, finance teams      | Import into Excel / Google Sheets for their own pivots |
| **PDF**  | CFOs, auditors, procurement       | "Print it and show it to the board" — tamper-evident   |
| **JSON** | Developers, integrations          | Feed into internal cost-tracking tools, BI pipelines   |
| **DOCX** | Sales, account managers, managers | Paste into monthly status reports, client updates      |

All four formats contain the same data:

- Wallet transaction history (every credit and debit)
- Per-document cost breakdown
- Per-user cost breakdown
- Per-model cost breakdown
- Raw cost vs platform fee split
- Date range selector

The customer can export for any custom date range — "last 7 days", "this month", "last quarter", or a manual range.

---

## 10. Glossary — Terms in Plain English

| Term                  | What it means                                                                                                   |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Wallet**            | A prepaid balance, like a mobile phone recharge. Starts at ₹100 free. Top up whenever you like.                |
| **Raw cost**          | The money Google or Anthropic charges us when your document runs through their AI.                            |
| **Platform fee**      | Our 15% markup on top of the raw cost. Covers servers, Razorpay fees, keeps the lights on.                     |
| **Token**             | A small piece of text (roughly 4 characters). AI companies charge per million tokens processed.                |
| **Input tokens**      | Text we send TO the AI (your document + our prompt).                                                           |
| **Output tokens**     | Text the AI sends back (the analysis).                                                                         |
| **Model routing**     | The rule that decides whether to use a cheap model (free lane) or a premium model (paid lane).                 |
| **Free lane**         | Gemini 3 Flash-Lite. Available to everyone on signup. Powered by the ₹100 welcome credit.                      |
| **Paid lane**         | Gemini 3 Flash, Claude Sonnet 4.6, or Claude Haiku 4.5. Unlocked once you recharge any amount.                 |
| **Prepaid**           | You pay us first, then use the product. This is the default for everyone.                                     |
| **Postpaid**          | You use the product first, we invoice you at month-end. Only for enterprise customers on signed contracts.    |
| **Razorpay**          | The Indian payment gateway we use to accept UPI, cards, and net banking.                                       |
| **GSTIN**             | Goods and Services Tax ID. Legally required before Razorpay will release money to us.                        |
| **Reconciliation**    | A nightly job that compares what we charged customers against what Google/Anthropic charged us. Safety net.   |
| **Markup percentage** | Always 15%. Shown on every invoice. We will change it only after giving customers 30 days' notice.           |

---

## 11. Summary — What Phase 9 Delivers

When Phase 9 ships, DokyDoc will be able to:

- ✅ Accept real money from Indian customers via UPI, cards, and net banking
- ✅ Give every new signup ₹100 of free credit to try the product
- ✅ Charge customers exactly 15% above what the AI actually cost us
- ✅ Show customers the full cost breakdown for every action they take
- ✅ Let customers pick between cheap and premium AI models
- ✅ Survive the Gemini 2.5 Flash deprecation (June 17, 2026)
- ✅ Export cost reports in CSV, PDF, JSON, and DOCX
- ✅ Spin up a polished demo organization for sales calls in one command
- ✅ Keep a complete audit trail of every rupee charged and deducted

The only thing it will NOT be able to do on day one is actually take money — because we do not yet have a GSTIN. Everything is built, tested, and behind a feature flag. The day our GSTIN arrives, we flip one switch and go live.

---

## 12. What Is Explicitly NOT in Phase 9 (Saved for Future Phases)

To keep Phase 9 shippable, we pushed the following to later phases. These are captured in `MASTER_IMPLEMENTATION_PLAN.md` under the **"Phase 9 Nice-to-Haves (N1–N10)"** section:

1. **Auto-refill wallet** — "keep my wallet above ₹500 automatically"
2. **Volume-based cost alerts** — "warn me if my spending jumps 50% week-over-week"
3. **Per-user monthly spend caps** — "Rajesh cannot spend more than ₹500 per month"
4. **One-click invoice PDF download** from payment history
5. **In-app notification center** for billing events
6. **AI-based cost forecasting** — "at your current rate, you'll spend ₹3,200 this month"
7. **Shareable public cost reports** — "send this link to my CFO"
8. **Slack / Teams billing alerts** — "post low-balance warnings to #finance"
9. **Multi-currency display** — "show me costs in USD/EUR even though I pay in INR"
10. **Budget vs actual variance tracking** — "I budgeted ₹2,000 this month, I'm tracking at ₹2,400"

These are all good ideas. They just aren't required to start charging customers. We will add them once real customers tell us which ones matter most.

---

## 13. The Bottom Line

Phase 9 is the difference between DokyDoc being a **science experiment** and DokyDoc being a **real business**.

We are building it with one unusual principle: **we would rather a customer feel they got a fair deal than we extract maximum margin**. Every technical decision in this plan — the 15% markup, the full cost transparency, the no-commitment wallet, the explicit model choice, the 4-format cost exports — flows from that one principle.

If we are right, word of mouth carries DokyDoc. If we are wrong, we adjust the markup. Either way, we start earning in 2026, and we do it without making a single customer feel tricked.

**That is Phase 9.**

