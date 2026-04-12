# DokyDoc — Phase 9 Implementation Plan (Billing, Wallet, Payments, Analytics)
# Solution Architect Edition — Ticket-Level Detail for Frontend, Backend & DB Developers
# Branch: `claude/document-pending-tasks-l6Ppu`
# Last updated: April 2026

---

## HOW TO USE THIS PLAN

This plan closes the 25 gaps (G1–G25) identified in the Phase 9 re-analysis and prepares the platform for:
1. **Real money flow** — Razorpay wallet top-ups via UPI/cards/netbanking
2. **Trust-first pricing** — 15% flat markup on raw AI cost, fully transparent
3. **Multi-model support** — Gemini 3 Flash / Gemini 3 Flash-Lite / Claude Sonnet 4.6 / Claude Haiku 4.5
4. **Gemini 2.5 Flash deprecation** — Hard deadline: **June 17, 2026**
5. **Downloadable cost exports** — CSV, PDF, JSON, DOCX
6. **Demo organization** — One-command setup for customer demos

### Plan Structure

- **PART A — Database Migrations** (new tables/columns to support wallet, routing, model metadata)
- **PART B — Backend Core** (cost service refactor, markup logic, model router, enforcement updates)
- **PART C — Backend Payments** (Razorpay SDK, checkout endpoint, webhook, reconciliation)
- **PART D — Backend Exports & Utilities** (CSV/PDF/JSON/DOCX export, demo org seeder, Celery tasks)
- **PART E — Frontend** (recharge modal, model selector, cost preview, export UI, upgrade flow)
- **PART F — Track A vs Track B** (what to ship now without GSTIN vs after GSTIN)

### Ticket Conventions

- Each ticket has: **ID**, **Title**, **Owner Role**, **Effort**, **Files**, **Acceptance Criteria**, **Dependencies**
- `[TRACK A]` = Ship now, no GSTIN required
- `[TRACK B]` = Blocked by GSTIN registration
- `[URGENT]` = Has an external hard deadline
- Migration chain: `s9d1` (latest) → `s9p1` → `s9p2` → `s9p3` → `s9p4` → `s9p5` → `s9p6`

### What is ALREADY Built (don't re-implement)

- ✅ `backend/app/services/cost_service.py` — Token-accurate cost calculator (single-model only)
- ✅ `backend/app/models/tenant_billing.py` — Prepaid/postpaid billing table
- ✅ `backend/app/models/usage_log.py` — Per-call usage tracking with feature/operation enums
- ✅ `backend/app/services/billing_enforcement_service.py` — Pre-check + deduct flow
- ✅ `backend/app/api/endpoints/billing.py` — 21 analytics endpoints, usage summary, top-up stub
- ✅ `backend/app/schemas/billing.py` — Core Pydantic schemas
- ✅ `frontend/app/settings/billing/page.tsx` — Billing settings UI (role-gated CXO/Admin)
- ✅ `frontend/app/settings/billing/analytics/` — Analytics dashboard
- ✅ `frontend/app/settings/billing/users/` — Per-user cost breakdown

Roughly **85% of Phase 9 infrastructure already exists.** This plan closes the remaining 15%.

---

## DECISIONS LOCKED IN (for reference)

| ID  | Decision                                                                                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------------- |
| D1  | 15% flat markup on raw AI cost (trust-first floor)                                                                               |
| D2  | Recharge presets ₹100 / ₹200 / ₹500 / ₹1,000 / ₹2,500 / ₹5,000 + custom amount; min ₹100; no max; no bonus credits                |
| D3  | ₹100 free credit on signup + **Model Routing**: Free tier = Gemini 3 Flash-Lite only; Paid tier = user picks any supported model |
| D4  | Migrate Gemini 2.5 Flash → Gemini 3 Flash before June 17, 2026                                                                   |
| D5  | Expose multi-model selection to users (per-document or tenant default)                                                           |
| D6  | Downloadable cost breakdown in **CSV, PDF, JSON, DOCX**                                                                          |
| D7  | Postpaid kept, manual enable per enterprise customer, contact form on marketing site                                             |
| D8  | Razorpay only at v1 (add Stripe when international customers onboard)                                                            |
| D9  | Nightly reconciliation vs Google Cloud Billing API (alerts if drift >5%)                                                         |
| D10 | Postpaid customers submit card-on-file (Razorpay Tokens); auto-charge monthly; hard limit from signed contract                   |

---

## PART A — DATABASE MIGRATIONS

All migrations are additive (new tables / new nullable columns). Zero backfills required for existing rows.

---

### TICKET A1 — Add `model_preference` + `free_credit_remaining_inr` to `tenants`
**Owner:** DB / Backend
**Effort:** 0.5 day
**Track:** A
**Depends on:** None
**Migration:** `s9p1_tenant_wallet_fields.py`
**Down revision:** `s9d1`

#### Files
- **New:** `backend/alembic/versions/s9p1_tenant_wallet_fields.py`
- **Modify:** `backend/app/models/tenant.py`

#### Model changes (`tenant.py`)
Add after existing `tier` column:
```python
# Phase 9: Model routing & free-tier budget
default_model: Mapped[str] = mapped_column(
    String, default="gemini-3-flash-lite", nullable=False
)  # One of: gemini-3-flash-lite, gemini-3-flash, claude-sonnet-4-6, claude-haiku-4-5
free_credit_remaining_inr: Mapped[float] = mapped_column(
    Numeric(12, 2), default=100.00, nullable=False
)  # Signup bonus pool; decremented BEFORE wallet balance
has_recharged_ever: Mapped[bool] = mapped_column(
    Boolean, default=False, nullable=False
)  # Flips true on first successful Razorpay payment; unlocks paid models
```

#### Migration (`s9p1_tenant_wallet_fields.py`)
```python
"""Add model_preference, free_credit, has_recharged_ever to tenants

Revision ID: s9p1
Revises: s9d1
Create Date: 2026-04-10
"""
import sqlalchemy as sa
from alembic import op

revision = "s9p1"
down_revision = "s9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("default_model", sa.String(), server_default="gemini-3-flash-lite", nullable=False))
    op.add_column("tenants", sa.Column("free_credit_remaining_inr", sa.Numeric(12, 2), server_default="100.00", nullable=False))
    op.add_column("tenants", sa.Column("has_recharged_ever", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("tenants", "has_recharged_ever")
    op.drop_column("tenants", "free_credit_remaining_inr")
    op.drop_column("tenants", "default_model")
```

#### Acceptance Criteria
- [ ] `alembic upgrade head` succeeds on dev DB
- [ ] All existing tenants get `default_model="gemini-3-flash-lite"`, `free_credit_remaining_inr=100.00`, `has_recharged_ever=false` via server_default
- [ ] `alembic downgrade -1` cleanly reverts
- [ ] `Tenant` SQLAlchemy model loads without warnings

---

### TICKET A2 — Create `wallet_transactions` table (audit ledger)
**Owner:** DB / Backend
**Effort:** 0.5 day
**Track:** A
**Depends on:** A1
**Migration:** `s9p2_wallet_transactions.py`

#### Files
- **New:** `backend/alembic/versions/s9p2_wallet_transactions.py`
- **New:** `backend/app/models/wallet_transaction.py`
- **Modify:** `backend/app/db/base.py` (register new model)

#### Why
Razorpay webhooks must write to an immutable ledger for reconciliation + tax reporting. We cannot reuse `usage_logs` (that's AI consumption; this is money flow).

#### Model (`wallet_transaction.py`)
```python
"""
Wallet Transaction model — immutable ledger for all money movements.
Phase 9: Billing & Payments
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class WalletTransaction(Base):
    """
    Immutable ledger of all wallet credits and debits.

    Credit sources: signup bonus, Razorpay top-up, admin grant, refund
    Debit sources:  document analysis, code analysis, chat, postpaid invoice
    """
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )

    # Direction & amount
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "credit" | "debit"
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Balance snapshot (post-transaction, for fast audit)
    balance_after_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Transaction type
    txn_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Values: "signup_bonus", "razorpay_topup", "admin_grant", "refund",
    #         "document_analysis", "code_analysis", "chat", "postpaid_invoice"

    # Reference keys
    usage_log_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("usage_logs.id"), nullable=True, index=True
    )
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)

    # Human-readable description (shown in UI)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    # Additional metadata (e.g. model_used, document_id, refund_reason)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, index=True
    )
```

#### Migration
```python
"""Create wallet_transactions ledger

Revision ID: s9p2
Revises: s9p1
"""
import sqlalchemy as sa
from alembic import op

revision = "s9p2"
down_revision = "s9p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("txn_type", sa.String(40), nullable=False),
        sa.Column("usage_log_id", sa.Integer(), sa.ForeignKey("usage_logs.id"), nullable=True),
        sa.Column("razorpay_order_id", sa.String(60), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(60), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_wallet_txn_tenant_created", "wallet_transactions", ["tenant_id", "created_at"])
    op.create_index("ix_wallet_txn_razorpay_payment", "wallet_transactions", ["razorpay_payment_id"])
    op.create_index("ix_wallet_txn_txn_type", "wallet_transactions", ["txn_type"])


def downgrade() -> None:
    op.drop_index("ix_wallet_txn_txn_type", table_name="wallet_transactions")
    op.drop_index("ix_wallet_txn_razorpay_payment", table_name="wallet_transactions")
    op.drop_index("ix_wallet_txn_tenant_created", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")
```

#### Acceptance Criteria
- [ ] Table created with 4 indexes
- [ ] `razorpay_payment_id` must be unique per row where not null (enforce in service layer; unique index optional)
- [ ] Model importable from `app.db.base` (for Alembic autogen)
- [ ] Immutable by convention — no UPDATE/DELETE code should ever touch this table

---

### TICKET A3 — Create `razorpay_orders` table (pending payment tracking)
**Owner:** DB / Backend
**Effort:** 0.25 day
**Track:** B (GSTIN-blocked)
**Depends on:** A2
**Migration:** `s9p3_razorpay_orders.py`

#### Files
- **New:** `backend/alembic/versions/s9p3_razorpay_orders.py`
- **New:** `backend/app/models/razorpay_order.py`

#### Why
Razorpay order creation happens **before** payment. We need to track pending orders so the webhook can verify and idempotently credit the wallet.

#### Model (`razorpay_order.py`)
```python
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class RazorpayOrder(Base):
    __tablename__ = "razorpay_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Razorpay identifiers
    razorpay_order_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)

    # Amount in INR (we bill in rupees; Razorpay takes paise)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # State machine
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    # created -> attempted -> paid | failed | expired

    # For webhook idempotency
    credited_to_wallet: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
```

#### Acceptance Criteria
- [ ] Unique index on `razorpay_order_id`
- [ ] `credited_to_wallet` default false, flipped true only inside webhook transaction
- [ ] Service layer enforces one-way state transitions

---

### TICKET A4 — Add `model_used` + `markup_inr` + `raw_cost_inr` to `usage_logs`
**Owner:** DB / Backend
**Effort:** 0.5 day
**Track:** A
**Depends on:** None
**Migration:** `s9p4_usage_log_markup_fields.py`

#### Files
- **New:** `backend/alembic/versions/s9p4_usage_log_markup_fields.py`
- **Modify:** `backend/app/models/usage_log.py`

#### Why
Currently `usage_logs.cost_inr` stores one number. We need to split it into:
- `raw_cost_inr` → what Google/Anthropic actually charged us
- `markup_inr` → our 15% platform fee
- `cost_inr` → total billed to the customer (raw + markup)

This enables per-row transparency and future markup A/B tests. `model_used` already exists in the model (default `"gemini-2.5-flash"`) but needs to be consistently populated at all call sites.

#### Model changes (`usage_log.py`)
Add after existing `cost_inr`:
```python
# Phase 9: Markup split for transparency
raw_cost_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)
markup_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)
markup_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=15.00)
```

#### Migration
```python
"""Add raw_cost/markup split to usage_logs

Revision ID: s9p4
Revises: s9p3
"""
import sqlalchemy as sa
from alembic import op

revision = "s9p4"
down_revision = "s9p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_logs", sa.Column("raw_cost_inr", sa.Numeric(12, 4), server_default="0.0", nullable=False))
    op.add_column("usage_logs", sa.Column("markup_inr", sa.Numeric(12, 4), server_default="0.0", nullable=False))
    op.add_column("usage_logs", sa.Column("markup_percent", sa.Numeric(5, 2), server_default="15.00", nullable=False))

    # Backfill existing rows: assume all historic cost was raw (zero markup)
    op.execute("UPDATE usage_logs SET raw_cost_inr = cost_inr, markup_inr = 0, markup_percent = 0 WHERE raw_cost_inr = 0")


def downgrade() -> None:
    op.drop_column("usage_logs", "markup_percent")
    op.drop_column("usage_logs", "markup_inr")
    op.drop_column("usage_logs", "raw_cost_inr")
```

#### Acceptance Criteria
- [ ] Existing rows keep their `cost_inr`; `raw_cost_inr` is backfilled to equal it
- [ ] All new rows enforce `cost_inr = raw_cost_inr + markup_inr` in service layer (not a DB constraint — too rigid for rounding)
- [ ] `markup_percent` column lets us show "15% platform fee" on invoices

---

### TICKET A5 — Create `enterprise_contact_requests` table
**Owner:** DB / Backend
**Effort:** 0.25 day
**Track:** A
**Depends on:** None
**Migration:** `s9p5_enterprise_contact.py`

#### Files
- **New:** `backend/alembic/versions/s9p5_enterprise_contact.py`
- **New:** `backend/app/models/enterprise_contact.py`

#### Why
D7: Postpaid exists in code but isn't advertised. Enterprise customers submit a contact form; ops manually enables postpaid.

#### Model
```python
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EnterpriseContactRequest(Base):
    __tablename__ = "enterprise_contact_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    work_email: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    team_size: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    estimated_monthly_usage_inr: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    # new -> contacted -> converted | declined

    handled_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
```

#### Acceptance Criteria
- [ ] Indexed on `work_email` for dedup checks
- [ ] Admin-only CRUD endpoint (G14 — covered in Part B)

---

### TICKET A6 — Add `razorpay_customer_id` + `card_token` to `tenant_billing` (postpaid card-on-file)
**Owner:** DB / Backend
**Effort:** 0.25 day
**Track:** B (GSTIN-blocked — Razorpay Tokens needs live API access)
**Depends on:** A1
**Migration:** `s9p6_tenant_billing_card_on_file.py`

#### Files
- **New:** `backend/alembic/versions/s9p6_tenant_billing_card_on_file.py`
- **Modify:** `backend/app/models/tenant_billing.py`

#### Model additions
```python
# Phase 9: Postpaid card-on-file (D10)
razorpay_customer_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
card_token: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
card_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
card_network: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Visa/Mastercard/Rupay
autocharge_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
contract_hard_limit_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
```

#### Acceptance Criteria
- [ ] All fields nullable (prepaid customers never populate them)
- [ ] `card_token` encrypted at rest (reuse existing `app.core.encryption` util if present; otherwise flag for Phase 14)
- [ ] `autocharge_enabled` gated behind admin toggle + contract_hard_limit_inr NOT NULL

---

## PART A SUMMARY

| Ticket | What                                            | Track | Days |
| ------ | ----------------------------------------------- | ----- | ---- |
| A1     | `tenants.default_model` + `free_credit`         | A     | 0.5  |
| A2     | `wallet_transactions` ledger                    | A     | 0.5  |
| A3     | `razorpay_orders`                               | B     | 0.25 |
| A4     | `usage_logs` markup split                       | A     | 0.5  |
| A5     | `enterprise_contact_requests`                   | A     | 0.25 |
| A6     | `tenant_billing.razorpay_customer_id` + card    | B     | 0.25 |
| **Total Part A**                                 |       | **2.25 days** |

✅ **PART A COMPLETE** — All 6 migrations defined. Total: 6 new/modified tables, zero destructive changes, all downgrade-safe.

---

## PART B — BACKEND CORE SERVICES


> **Architect's guarantee:** Every ticket in Part B is written so that **no existing caller, test, or API endpoint breaks**. The rule is: additive first, then replace. Old method signatures are preserved. New behaviour is layered on top via fallbacks where needed.
>
> **Dependency order for execution:** A1 + A4 must migrate first. B0 is independent — start immediately.
>
> **All Part B tickets are Track A** (no GSTIN required).

---

### TICKET B0 — Gemini 3 Migration
**Owner:** Backend
**Effort:** 0.5 day
**Track:** A
**[URGENT] Hard external deadline: June 17, 2026. Gemini 2.5 Flash is shut down on that date.**
**Depends on:** Nothing — start immediately, parallel with Part A

#### Context

Three places in the codebase have Gemini 2.5 Flash hardcoded:

1. `backend/app/core/config.py` — `GEMINI_MODEL` and `GEMINI_VISION_MODEL` default to `"gemini-2.5-flash"`
2. `backend/app/services/ai/gemini.py` line 168 — `model_used="gemini-2.5-flash"` hardcoded string in auto-billing block
3. `backend/app/services/cost_service.py` — single pricing constant, no registry

All three must be updated before June 17. The new model IDs are `"gemini-3-flash"` (paid lane) and `"gemini-3-flash-lite"` (free lane). **Verify exact API string against Google's documentation at time of implementation — Google may publish as `gemini-3.0-flash`.**

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/core/config.py` | Add 2 settings; update 2 defaults |
| `backend/app/services/cost_service.py` | Add 2 pricing constants + registry + lookup function |
| `backend/app/services/ai/gemini.py` | Replace 1 hardcoded string |

#### Step 1 — `config.py`

Update the two existing defaults and add two new settings after `GEMINI_VISION_MODEL`:

```python
# Updated defaults (was "gemini-2.5-flash")
GEMINI_MODEL: str = Field(default="gemini-3-flash", env="GEMINI_MODEL")
GEMINI_VISION_MODEL: str = Field(default="gemini-3-flash", env="GEMINI_VISION_MODEL")

# Phase 9 additions — model routing
GEMINI_DEFAULT_MODEL: str = Field(default="gemini-3-flash", env="GEMINI_DEFAULT_MODEL")
GEMINI_FREE_MODEL: str = Field(default="gemini-3-flash-lite", env="GEMINI_FREE_MODEL")
```

> **Rollback strategy:** If Google delays Gemini 3, set `GEMINI_MODEL=gemini-2.5-flash` in `.env` — no code deploy needed.

#### Step 2 — `cost_service.py`

Add after the existing `GEMINI_15_FLASH_PRICING` constant. **Do NOT remove existing constants** — they are needed to recalculate costs on historical `usage_log` rows.

```python
# ============================================================================
# GEMINI 3 FLASH PRICING — Paid lane default
# TODO: Verify exact rates from ai.google.dev/pricing before June 17, 2026
# ============================================================================
GEMINI_3_FLASH_PRICING = PricingTier(
    model="gemini-3-flash",
    input_per_1m_usd=Decimal("0.10"),
    output_per_1m_usd=Decimal("0.40"),
    thinking_per_1m_usd=Decimal("0.40"),
    cached_per_1m_usd=Decimal("0.025"),
    search_per_1k_usd=Decimal("14.00"),
    description="Gemini 3 Flash — paid lane default"
)

# ============================================================================
# GEMINI 3 FLASH-LITE PRICING — Free lane (signup credit pool)
# TODO: Verify exact rates from ai.google.dev/pricing before June 17, 2026
# ============================================================================
GEMINI_3_FLASH_LITE_PRICING = PricingTier(
    model="gemini-3-flash-lite",
    input_per_1m_usd=Decimal("0.025"),
    output_per_1m_usd=Decimal("0.10"),
    thinking_per_1m_usd=Decimal("0.00"),  # No thinking on lite model
    cached_per_1m_usd=Decimal("0.00625"),
    search_per_1k_usd=Decimal("14.00"),
    description="Gemini 3 Flash-Lite — free lane"
)

# Pricing registry — single source of truth for all model → pricing lookups.
# Add new models here. Never remove old entries (needed for historical rows).
PRICING_REGISTRY: dict[str, PricingTier] = {
    "gemini-1.5-flash":    GEMINI_15_FLASH_PRICING,
    "gemini-2.5-flash":    GEMINI_25_FLASH_PRICING,
    "gemini-3-flash":      GEMINI_3_FLASH_PRICING,
    "gemini-3-flash-lite": GEMINI_3_FLASH_LITE_PRICING,
}


def get_pricing_for_model(model_id: str) -> PricingTier:
    """
    Look up PricingTier by model API ID string.
    Falls back to GEMINI_25_FLASH_PRICING for unknown models —
    safe fallback: slightly overestimates cost, never underestimates.
    """
    return PRICING_REGISTRY.get(model_id, GEMINI_25_FLASH_PRICING)
```

#### Step 3 — `gemini.py` line 168

```python
# BEFORE:
model_used="gemini-2.5-flash",

# AFTER:
model_used=settings.GEMINI_MODEL,
```

Ensure `from app.core.config import settings` is already imported in the file (it should be — check top-of-file imports).

#### What Does NOT Change

- `CostService.__init__()` still sets `self.pricing = GEMINI_25_FLASH_PRICING` — that changes in B1. Intentionally left here to keep B0 blast radius minimal.
- `GeminiService` class interface — zero method signature changes.
- All existing callers of `gemini_service`.
- All existing tests.

#### Acceptance Criteria

- [ ] `settings.GEMINI_MODEL` → `"gemini-3-flash"` (or `.env` override)
- [ ] `settings.GEMINI_DEFAULT_MODEL` and `settings.GEMINI_FREE_MODEL` exist in settings
- [ ] `get_pricing_for_model("gemini-3-flash")` → `GEMINI_3_FLASH_PRICING`
- [ ] `get_pricing_for_model("unknown-xyz")` → `GEMINI_25_FLASH_PRICING` (no crash)
- [ ] Auto-billing in `gemini.py` logs `model_used="gemini-3-flash"` (not hardcoded)
- [ ] `pytest backend/tests/` — all existing tests pass
- [ ] **Deployed before June 17, 2026**

---

### TICKET B1 — Cost Service Markup Refactor
**Owner:** Backend
**Effort:** 1 day
**Track:** A
**Depends on:** B0 (needs `get_pricing_for_model()`), A4 (new `usage_logs` columns must exist before logging markup fields)

#### Context

Current `calculate_cost_from_actual_tokens()` in `cost_service.py`:
- Returns a flat `dict` with `cost_inr` = raw AI cost (no markup)
- Hardcoded to `self.pricing = GEMINI_25_FLASH_PRICING` in `__init__`
- No model parameter — cannot price Claude or Gemini 3 calls differently

After this ticket:
- Returns the same dict shape **plus** new keys for markup split (additive — no existing key removed)
- `cost_inr` key now equals the **customer-facing price** (raw + 15% markup)
- New keys `raw_cost_inr`, `markup_inr`, `markup_percent` added for transparency display
- Accepts optional `model` parameter for per-model pricing
- `CostBreakdown` dataclass available for new callers who want typed access

**Backward compatibility rule:** Every existing caller reads `result["cost_inr"]`. After this change `cost_inr` becomes the marked-up price — which is the correct value to charge the customer. The dict shape is unchanged (old keys all present), new keys are additive. Zero callers break.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/services/cost_service.py` | Add constant + dataclass + modify one method + update `__init__` |

#### Step 1 — Add `MARKUP_PERCENT` constant

Add after the `PRICING_REGISTRY` dict (from B0):

```python
# Platform markup — 15% flat fee on raw AI cost (Decision D1)
# This is the margin DokyDoc keeps. Fully transparent to customers.
MARKUP_PERCENT: Decimal = Decimal("15.00")
```

#### Step 2 — Add `CostBreakdown` dataclass

Add after `MARKUP_PERCENT`. This is the typed return type for new callers (B4, B3, export endpoints). Existing callers still get the flat dict via `to_legacy_dict()`.

```python
@dataclass
class CostBreakdown:
    """
    Typed cost calculation result.

    Use this in new code (B3, B4, export). Legacy callers use to_legacy_dict().

    raw_cost_inr:   What Google/Anthropic charged us
    markup_inr:     Our 15% platform fee
    total_cost_inr: What the customer pays (raw + markup)
    cost_inr:       Alias for total_cost_inr — kept for compatibility
    """
    model: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cached_tokens: int

    raw_cost_usd: float
    raw_cost_inr: float
    markup_inr: float
    markup_percent: float        # Always 15.0 at v1
    total_cost_inr: float        # = raw_cost_inr + markup_inr
    cost_inr: float              # = total_cost_inr (alias — do not remove)
    cost_usd: float              # = raw_cost_usd (for backwards compat)

    # Per-token breakdown (INR)
    input_cost_inr: float
    output_cost_inr: float
    thinking_cost_inr: float
    cached_cost_inr: float

    # Snapshot of rates applied (for audit trail in usage_logs)
    rates_applied: dict

    def to_legacy_dict(self) -> dict:
        """
        Returns the same dict shape as the old calculate_cost_from_actual_tokens().
        Use this when passing results to code written before B1.
        All old keys present. New keys (raw_cost_inr, markup_inr, markup_percent) added.
        """
        return {
            # --- Original keys (unchanged values where possible) ---
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.input_tokens + self.output_tokens + self.thinking_tokens,
            "cost_usd": self.cost_usd,
            "cost_inr": self.cost_inr,           # Now = total (marked-up). Callers billing customers: correct.
            "input_cost_inr": self.input_cost_inr,
            "output_cost_inr": self.output_cost_inr,
            "thinking_cost_inr": self.thinking_cost_inr,
            "cached_cost_inr": self.cached_cost_inr,
            "rates_applied": self.rates_applied,
            # --- New keys (additive — no old caller reads these yet) ---
            "raw_cost_inr": self.raw_cost_inr,
            "markup_inr": self.markup_inr,
            "markup_percent": self.markup_percent,
        }
```

#### Step 3 — Update `CostService.__init__()`

Replace the hardcoded `self.pricing = GEMINI_25_FLASH_PRICING` line:

```python
# BEFORE:
self.pricing = GEMINI_25_FLASH_PRICING

# AFTER:
# Default pricing for backward-compat callers that don't pass model param.
# Will use GEMINI_DEFAULT_MODEL once B0 config is deployed.
self.pricing = get_pricing_for_model(settings.GEMINI_MODEL)
```

Also update the per-1K convenience fields that derive from `self.pricing` — they are already computed from `self.pricing` so they will automatically reflect the new model.

#### Step 4 — Modify `calculate_cost_from_actual_tokens()`

Add one optional `model` parameter and markup logic. Return type stays `dict` (via `to_legacy_dict()`) for backward compatibility. No parameter removed.

```python
def calculate_cost_from_actual_tokens(
    self,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    cached_tokens: int = 0,
    search_queries: int = 0,
    model: str | None = None,          # NEW — optional, defaults to self.pricing.model
) -> dict:
    """
    Calculate cost using actual token counts from API response.

    Args:
        input_tokens:   Actual prompt_token_count from API
        output_tokens:  Actual candidates_token_count from API
        thinking_tokens: Actual thoughts_token_count from Gemini (CRITICAL — often 2-5× output)
        cached_tokens:  Tokens served from cache
        search_queries: Number of search queries (if grounding enabled)
        model:          Model API ID string. If None, uses self.pricing.model.
                        Pass this for multi-model accuracy (Gemini 3 vs Claude etc.)

    Returns:
        dict — same shape as before B1, plus new keys: raw_cost_inr, markup_inr, markup_percent
    """
    # Resolve pricing for this specific model call
    pricing = get_pricing_for_model(model) if model else self.pricing

    # Per-1K rates from resolved pricing
    cost_per_1k_input = pricing.input_per_1m_usd / 1000
    cost_per_1k_output = pricing.output_per_1m_usd / 1000
    cost_per_1k_thinking = pricing.thinking_per_1m_usd / 1000
    cost_per_1k_cached = pricing.cached_per_1m_usd / 1000

    # Raw costs in USD
    input_cost_usd = (Decimal(input_tokens) / 1000) * cost_per_1k_input
    output_cost_usd = (Decimal(output_tokens) / 1000) * cost_per_1k_output
    thinking_cost_usd = (Decimal(thinking_tokens) / 1000) * cost_per_1k_thinking
    cached_cost_usd = (Decimal(cached_tokens) / 1000) * cost_per_1k_cached
    search_cost_usd = (Decimal(search_queries) / 1000) * pricing.search_per_1k_usd
    raw_total_usd = input_cost_usd + output_cost_usd + thinking_cost_usd + cached_cost_usd + search_cost_usd

    # Convert raw to INR
    raw_total_inr = float(raw_total_usd * self.usd_to_inr)

    # Apply 15% platform markup
    markup_inr = round(raw_total_inr * float(MARKUP_PERCENT) / 100, 4)
    total_cost_inr = round(raw_total_inr + markup_inr, 4)

    breakdown = CostBreakdown(
        model=pricing.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        cached_tokens=cached_tokens,
        raw_cost_usd=float(raw_total_usd),
        raw_cost_inr=raw_total_inr,
        markup_inr=markup_inr,
        markup_percent=float(MARKUP_PERCENT),
        total_cost_inr=total_cost_inr,
        cost_inr=total_cost_inr,        # customer-facing price
        cost_usd=float(raw_total_usd),  # raw USD (unchanged semantics for callers)
        input_cost_inr=float(input_cost_usd * self.usd_to_inr),
        output_cost_inr=float(output_cost_usd * self.usd_to_inr),
        thinking_cost_inr=float(thinking_cost_usd * self.usd_to_inr),
        cached_cost_inr=float(cached_cost_usd * self.usd_to_inr),
        rates_applied={
            "model": pricing.model,
            "input_per_1m_usd": float(pricing.input_per_1m_usd),
            "output_per_1m_usd": float(pricing.output_per_1m_usd),
            "thinking_per_1m_usd": float(pricing.thinking_per_1m_usd),
            "usd_to_inr": float(self.usd_to_inr),
            "markup_percent": float(MARKUP_PERCENT),
        }
    )

    return breakdown.to_legacy_dict()
```

#### Step 5 — Update `gemini.py` auto-billing to log markup fields

The auto-billing block in `gemini.py` calls `calculate_cost_from_actual_tokens()` and reads `cost_inr`. After B1, `cost_inr` is the marked-up total — correct behavior.

Additionally, log the new markup fields into `usage_logs` (A4 added these columns):

```python
# Existing call (unchanged):
cost_result = cost_service.calculate_cost_from_actual_tokens(
    input_tokens=tokens.get("input_tokens", 0),
    output_tokens=tokens.get("output_tokens", 0),
    thinking_tokens=tokens.get("thinking_tokens", 0),
    model=settings.GEMINI_MODEL,      # Pass model — new param from B1
)
cost_usd = cost_result["cost_usd"]
cost_inr = cost_result["cost_inr"]   # Now = raw + 15% markup ✓

# Updated log_usage call — add new fields (A4 columns):
crud.usage_log.log_usage(
    db=billing_db,
    tenant_id=tenant_id,
    user_id=user_id,
    feature_type=...,
    operation=operation,
    model_used=settings.GEMINI_MODEL,
    input_tokens=tokens.get("input_tokens", 0),
    output_tokens=tokens.get("output_tokens", 0) + tokens.get("thinking_tokens", 0),
    cost_usd=cost_usd,
    cost_inr=cost_inr,
    # New fields from A4:
    raw_cost_inr=cost_result.get("raw_cost_inr", cost_inr),
    markup_inr=cost_result.get("markup_inr", 0.0),
    markup_percent=cost_result.get("markup_percent", 0.0),
    extra_data={
        "thinking_tokens": tokens.get("thinking_tokens", 0),
        "auto_logged": True,
        "model_pricing_snapshot": cost_result.get("rates_applied", {}),
    },
)
```

> **Note:** `crud.usage_log.log_usage()` must be updated to accept and write the new A4 columns. This is a purely additive change to that CRUD method — add the new parameters with `default=None` so all existing callers continue to work unchanged.

#### What Does NOT Change

- Method signature of `calculate_cost_from_actual_tokens()` — new `model` param has default `None`
- All existing dict keys in the returned result — no key removed
- `calculate_cost()` (the text-based wrapper) — calls through to the updated method automatically
- `estimate_document_cost()` — unchanged
- `get_pricing_info()` — unchanged (still describes `self.pricing`)

#### Acceptance Criteria

- [ ] `calculate_cost_from_actual_tokens(1000, 500)` → dict contains `cost_inr`, `raw_cost_inr`, `markup_inr`, `markup_percent`
- [ ] `markup_inr` ≈ `raw_cost_inr * 0.15` (within rounding)
- [ ] `cost_inr` = `raw_cost_inr + markup_inr`
- [ ] `calculate_cost_from_actual_tokens(1000, 500, model="gemini-3-flash-lite")` uses `GEMINI_3_FLASH_LITE_PRICING` rates
- [ ] `calculate_cost_from_actual_tokens(1000, 500, model="unknown")` does not raise — uses fallback pricing
- [ ] All existing callers that read `cost_result["cost_inr"]` still receive a float
- [ ] `crud.usage_log.log_usage()` accepts new fields with `default=None` — existing call sites with no new fields still work
- [ ] `pytest backend/tests/` — all existing tests pass

---

### TICKET B2 — Model Selector Service
**Owner:** Backend
**Effort:** 0.5 day
**Track:** A
**Depends on:** A1 (needs `tenant.has_recharged_ever` and `tenant.default_model`), B0 (needs `settings.GEMINI_FREE_MODEL`)

#### Context

Decision D3: Free tier (has_recharged_ever=False) → Gemini 3 Flash-Lite only. Paid tier → user picks any of 4 supported models.

Currently `provider_router.py` routes by **task type** (code → Claude, docs → Gemini). It has zero knowledge of the tenant's recharge status or model preference. We need a separate concern: **model selection** (which specific model ID within a provider). These are two different decisions.

This is a **pure new file**. Zero changes to any existing file.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/services/ai/model_selector.py` | **New file** |

#### Implementation — `model_selector.py`

```python
"""
Model Selector — Phase 9 (D3, D5)

Decides WHICH specific model ID to use for a given tenant and request.
This is separate from ProviderRouter (which decides which SDK client to use).

Routing rules:
  - tenant.has_recharged_ever == False  →  always gemini-3-flash-lite (free lane)
  - tenant.has_recharged_ever == True   →  requested_model if supported, else tenant.default_model
"""
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.model_selector")

# Supported models — display name + API ID + whether it requires paid status
SUPPORTED_MODELS: dict[str, dict] = {
    "gemini-3-flash-lite": {
        "display_name": "Gemini 3 Flash-Lite",
        "provider": "google",
        "tier": "free",           # Available on free lane
        "description": "Fast and affordable. Best for straightforward documents.",
    },
    "gemini-3-flash": {
        "display_name": "Gemini 3 Flash",
        "provider": "google",
        "tier": "paid",
        "description": "High quality. Best for complex BRDs and regulatory documents.",
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "tier": "paid",
        "description": "Deep reasoning. Best for code analysis and nuanced validation.",
    },
    "claude-haiku-4-5": {
        "display_name": "Claude Haiku 4.5",
        "provider": "anthropic",
        "tier": "paid",
        "description": "Fast and capable. Best for quick summaries and chat.",
    },
}


class ModelSelector:
    """
    Decides the model ID to use for a given tenant + optional user request.

    Call resolve() once at the start of each analysis operation.
    The returned model ID string is passed to:
      - cost_service.calculate_cost_from_actual_tokens(model=...)  [B1]
      - provider_router.get_client_for_model(model_id)             [B2 extension]
      - usage_log.model_used
    """

    def resolve(self, tenant, requested_model: Optional[str] = None) -> str:
        """
        Resolve the model ID to use for this tenant + request.

        Args:
            tenant:           SQLAlchemy Tenant object (needs has_recharged_ever, default_model)
            requested_model:  Model ID string from API request body (optional)

        Returns:
            Model ID string — always a valid key in SUPPORTED_MODELS
        """
        # Guard: if tenant object doesn't have Phase 9 fields yet (pre-A1 DB),
        # fall back gracefully to the configured default.
        has_recharged = getattr(tenant, "has_recharged_ever", False)
        tenant_default = getattr(tenant, "default_model", settings.GEMINI_DEFAULT_MODEL)

        # FREE LANE: tenant has never recharged → always use lite model, no exceptions
        if not has_recharged:
            model = settings.GEMINI_FREE_MODEL
            logger.debug(f"Free lane → {model} (tenant_id={tenant.id}, has_recharged=False)")
            return model

        # PAID LANE: validate requested model
        if requested_model:
            if requested_model in SUPPORTED_MODELS:
                logger.debug(f"Paid lane → {requested_model} (tenant_id={tenant.id}, user-requested)")
                return requested_model
            else:
                # Unknown model requested — log warning, fall through to tenant default
                logger.warning(
                    f"Unsupported model '{requested_model}' requested by tenant {tenant.id}. "
                    f"Falling back to tenant default: {tenant_default}"
                )

        # PAID LANE: use tenant's stored default
        if tenant_default in SUPPORTED_MODELS:
            logger.debug(f"Paid lane → {tenant_default} (tenant_id={tenant.id}, tenant-default)")
            return tenant_default

        # Final fallback — should never reach here in normal operation
        fallback = settings.GEMINI_DEFAULT_MODEL
        logger.warning(
            f"tenant.default_model='{tenant_default}' not in SUPPORTED_MODELS. "
            f"Using config default: {fallback}"
        )
        return fallback

    def get_supported_models(self, tenant) -> list[dict]:
        """
        Returns list of models available to this tenant — for frontend dropdown.

        Free-lane tenants: only see gemini-3-flash-lite.
        Paid-lane tenants: see all 4 models with current tenant default flagged.
        """
        has_recharged = getattr(tenant, "has_recharged_ever", False)
        tenant_default = getattr(tenant, "default_model", settings.GEMINI_DEFAULT_MODEL)

        result = []
        for model_id, info in SUPPORTED_MODELS.items():
            if not has_recharged and info["tier"] != "free":
                continue  # Free lane: hide paid models

            result.append({
                "model_id": model_id,
                "display_name": info["display_name"],
                "provider": info["provider"],
                "description": info["description"],
                "is_default": model_id == tenant_default,
                "requires_recharge": info["tier"] == "paid",
            })

        return result


# Singleton instance
model_selector = ModelSelector()
```

#### How Callers Use This

In any service that triggers an AI call (document pipeline, validation service, code analysis, chat), add at the top of the operation:

```python
from app.services.ai.model_selector import model_selector

# Resolve model for this tenant (+ optional user preference from request)
model_id = model_selector.resolve(tenant, requested_model=request.model_preference)

# Pass model_id to cost calculation (B1)
cost = cost_service.calculate_cost_from_actual_tokens(..., model=model_id)

# Pass model_id to provider router (B2 extension below)
```

#### Extension to `provider_router.py` (Additive — No Existing Method Changed)

Add a new method `get_client_for_model()` alongside the existing methods. Do NOT modify `analyze_code()` or any existing method.

```python
# In ProviderRouter class, add this new method:

def get_client_for_model(self, model_id: str):
    """
    Returns the correct SDK client for a given model ID.
    New method — does not replace existing routing logic.

    gemini-3-flash / gemini-3-flash-lite → self.gemini
    claude-sonnet-4-6 / claude-haiku-4-5  → self.claude (if available, else self.gemini)
    """
    if model_id.startswith("claude-"):
        if self.claude_available:
            return self.claude, model_id
        else:
            # Claude unavailable — fall back to Gemini default with a warning
            self.logger.warning(
                f"Claude unavailable, falling back to Gemini for model={model_id}"
            )
            return self.gemini, settings.GEMINI_DEFAULT_MODEL
    else:
        return self.gemini, model_id
```

#### What Does NOT Change

- `ProviderRouter.analyze_code()` — untouched
- `ProviderRouter.analyze_document()` — untouched
- All existing routing logic — the new method is additive
- `gemini_service` direct callers — they continue to work without model_selector

#### Acceptance Criteria

- [ ] `model_selector.resolve(free_tenant)` → `"gemini-3-flash-lite"` regardless of `requested_model`
- [ ] `model_selector.resolve(paid_tenant, "claude-sonnet-4-6")` → `"claude-sonnet-4-6"`
- [ ] `model_selector.resolve(paid_tenant, "invalid-model")` → tenant's `default_model` (no crash)
- [ ] `model_selector.resolve(paid_tenant)` with no request → tenant's `default_model`
- [ ] `model_selector.get_supported_models(free_tenant)` → list with 1 item only
- [ ] `model_selector.get_supported_models(paid_tenant)` → list with 4 items, correct `is_default` flag
- [ ] `provider_router.get_client_for_model("claude-sonnet-4-6")` → returns claude client when available
- [ ] `provider_router.get_client_for_model("gemini-3-flash")` → returns gemini client
- [ ] Tenant with no `has_recharged_ever` attribute (pre-A1 DB) → `getattr` fallback, no AttributeError
- [ ] `pytest backend/tests/` — all existing tests pass (new file, nothing changed)

---

### TICKET B3 — Wallet Service
**Owner:** Backend
**Effort:** 1 day
**Track:** A
**Depends on:** A1 (tenant fields), A2 (wallet_transactions table must exist)

#### Context

`billing_enforcement_service.py` currently deducts cost by directly writing to `tenant_billing.balance_inr`. There is no ledger. No audit trail. No idempotency. No SELECT FOR UPDATE. This is fine for a prototype but breaks the moment two concurrent analysis requests arrive for the same tenant.

This ticket creates an immutable, idempotent ledger service. It is a **pure new file** — `billing_enforcement_service.py` is NOT touched here (that happens in B4).

The wallet has two pools per tenant:
1. `tenant.free_credit_remaining_inr` — signup bonus. Exhausted first, always.
2. `tenant_billing.balance_inr` — real wallet money. Used after free credit runs out.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/services/wallet_service.py` | **New file** |
| `backend/app/crud/__init__.py` | Add `from .crud_wallet_transaction import wallet_transaction` |
| `backend/app/crud/crud_wallet_transaction.py` | **New file** |

#### CRUD — `crud_wallet_transaction.py`

```python
"""
CRUD operations for WalletTransaction — Phase 9
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.wallet_transaction import WalletTransaction
from app.core.logging import get_logger

logger = get_logger("crud.wallet_transaction")


class CRUDWalletTransaction:

    def create(self, db: Session, *, obj_in: dict) -> WalletTransaction:
        txn = WalletTransaction(**obj_in)
        db.add(txn)
        db.flush()   # Get ID without full commit — caller commits
        return txn

    def get_by_idempotency_key(self, db: Session, *, key: str) -> Optional[WalletTransaction]:
        return db.query(WalletTransaction).filter(
            WalletTransaction.idempotency_key == key
        ).first()

    def get_ledger(
        self, db: Session, *, tenant_id: int, limit: int = 50, offset: int = 0
    ) -> list[WalletTransaction]:
        return (
            db.query(WalletTransaction)
            .filter(WalletTransaction.tenant_id == tenant_id)
            .order_by(WalletTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_total_credits(self, db: Session, *, tenant_id: int) -> float:
        from sqlalchemy import func
        result = db.query(func.sum(WalletTransaction.amount_inr)).filter(
            WalletTransaction.tenant_id == tenant_id,
            WalletTransaction.direction == "credit",
            WalletTransaction.is_reversed == False,
        ).scalar()
        return float(result or 0)

    def get_total_debits(self, db: Session, *, tenant_id: int) -> float:
        from sqlalchemy import func
        result = db.query(func.sum(WalletTransaction.amount_inr)).filter(
            WalletTransaction.tenant_id == tenant_id,
            WalletTransaction.direction == "debit",
            WalletTransaction.is_reversed == False,
        ).scalar()
        return float(result or 0)


wallet_transaction = CRUDWalletTransaction()
```

#### Service — `wallet_service.py`

```python
"""
Wallet Service — Phase 9
Manages the two-pool balance system (free_credit + wallet balance).
All money movements write to the wallet_transactions ledger.

Two-pool rule:
  free_credit_remaining_inr is exhausted BEFORE balance_inr.
  If a deduction spans both pools, two separate ledger rows are created.

Race condition protection:
  All reads + writes that touch balances use SELECT FOR UPDATE.
  Never read balance in one query and write in another without a lock.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app import crud
from app.core.logging import get_logger
from app.models.tenant import Tenant
from app.models.tenant_billing import TenantBilling

logger = get_logger("services.wallet")


class WalletService:

    # ------------------------------------------------------------------
    # CREDITS
    # ------------------------------------------------------------------

    def record_credit(
        self,
        db: Session,
        *,
        tenant_id: int,
        amount_inr: float,
        txn_type: str,
        idempotency_key: str,
        user_id: Optional[int] = None,
        razorpay_order_id: Optional[str] = None,
        razorpay_payment_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Credit the tenant's wallet balance (NOT free credit pool).
        Idempotent: if idempotency_key already exists, returns existing transaction.

        txn_type values: "signup_bonus", "razorpay_topup", "admin_grant", "refund"

        For signup_bonus: call record_free_credit() instead — this writes to
        free_credit_remaining_inr on the tenant, not balance_inr.
        """
        # Idempotency check
        existing = crud.wallet_transaction.get_by_idempotency_key(db, key=idempotency_key)
        if existing:
            logger.info(f"Idempotent credit — key already exists: {idempotency_key}")
            return {"status": "already_processed", "transaction_id": existing.id}

        # Lock billing row
        billing = (
            db.query(TenantBilling)
            .filter(TenantBilling.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if not billing:
            billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        old_balance = float(billing.balance_inr)
        new_balance = old_balance + amount_inr

        billing.balance_inr = Decimal(str(new_balance))
        db.add(billing)

        txn = crud.wallet_transaction.create(db, obj_in={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "direction": "credit",
            "amount_inr": Decimal(str(amount_inr)),
            "balance_after_inr": Decimal(str(new_balance)),
            "txn_type": txn_type,
            "idempotency_key": idempotency_key,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "notes": notes,
        })

        db.commit()
        logger.info(f"Wallet credited: tenant={tenant_id}, amount=₹{amount_inr}, txn_type={txn_type}, id={txn.id}")
        return {"status": "ok", "transaction_id": txn.id, "new_balance_inr": new_balance}

    def record_free_credit(
        self,
        db: Session,
        *,
        tenant_id: int,
        amount_inr: float,
        idempotency_key: str,
    ) -> dict:
        """
        Grant free credit (signup bonus) to tenant.free_credit_remaining_inr.
        Idempotent — safe to call multiple times with same key.
        """
        existing = crud.wallet_transaction.get_by_idempotency_key(db, key=idempotency_key)
        if existing:
            logger.info(f"Idempotent free credit — key exists: {idempotency_key}")
            return {"status": "already_processed", "transaction_id": existing.id}

        # Lock tenant row
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .with_for_update()
            .first()
        )
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        old_free = float(getattr(tenant, "free_credit_remaining_inr", 0))
        new_free = old_free + amount_inr
        tenant.free_credit_remaining_inr = Decimal(str(new_free))
        db.add(tenant)

        # Billing row balance_after reflects free credit pool separately
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
        wallet_balance_after = float(billing.balance_inr)

        txn = crud.wallet_transaction.create(db, obj_in={
            "tenant_id": tenant_id,
            "direction": "credit",
            "amount_inr": Decimal(str(amount_inr)),
            "balance_after_inr": Decimal(str(wallet_balance_after)),
            "txn_type": "signup_bonus",
            "idempotency_key": idempotency_key,
            "notes": f"Free credit grant. free_credit_pool_after=₹{new_free}",
        })

        db.commit()
        logger.info(f"Free credit granted: tenant={tenant_id}, amount=₹{amount_inr}, id={txn.id}")
        return {"status": "ok", "transaction_id": txn.id, "free_credit_remaining_inr": new_free}

    # ------------------------------------------------------------------
    # DEBITS
    # ------------------------------------------------------------------

    def deduct(
        self,
        db: Session,
        *,
        tenant_id: int,
        amount_inr: float,
        txn_type: str,
        usage_log_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Deduct amount from tenant balance using two-pool logic.
        Pool order: free_credit_remaining_inr first, then balance_inr.

        Uses SELECT FOR UPDATE to prevent race conditions on concurrent requests.

        Returns dict with:
          - transaction_ids: list of created WalletTransaction IDs (1 or 2)
          - free_credit_used_inr: amount taken from free pool
          - wallet_used_inr: amount taken from paid wallet
          - free_credit_remaining_inr: remaining free credit after deduction
          - wallet_balance_inr: remaining wallet balance after deduction
        """
        amount = Decimal(str(amount_inr))

        # Lock BOTH rows in consistent order (tenant first, then billing — always same order to avoid deadlocks)
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .with_for_update()
            .first()
        )
        billing = (
            db.query(TenantBilling)
            .filter(TenantBilling.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )

        if not tenant or not billing:
            raise ValueError(f"Tenant or billing record not found for tenant_id={tenant_id}")

        free_credit = Decimal(str(getattr(tenant, "free_credit_remaining_inr", 0)))
        wallet_balance = Decimal(str(billing.balance_inr))

        transaction_ids = []
        free_credit_used = Decimal("0")
        wallet_used = Decimal("0")

        # POOL 1: Draw from free credit first
        if free_credit > 0 and amount > 0:
            take_from_free = min(free_credit, amount)
            free_credit_used = take_from_free
            new_free = free_credit - take_from_free
            tenant.free_credit_remaining_inr = new_free
            db.add(tenant)

            txn1 = crud.wallet_transaction.create(db, obj_in={
                "tenant_id": tenant_id,
                "direction": "debit",
                "amount_inr": take_from_free,
                "balance_after_inr": wallet_balance,     # wallet pool unchanged here
                "txn_type": f"{txn_type}_free_credit",
                "usage_log_id": usage_log_id,
                "notes": f"Free credit pool deduction. Pool remaining: ₹{new_free}",
            })
            transaction_ids.append(txn1.id)
            amount -= take_from_free

        # POOL 2: Draw remainder from paid wallet
        if amount > 0:
            wallet_used = amount
            new_balance = wallet_balance - amount
            billing.balance_inr = new_balance
            billing.current_month_cost += amount
            billing.last_30_days_cost += amount
            db.add(billing)

            txn2 = crud.wallet_transaction.create(db, obj_in={
                "tenant_id": tenant_id,
                "direction": "debit",
                "amount_inr": amount,
                "balance_after_inr": new_balance,
                "txn_type": txn_type,
                "usage_log_id": usage_log_id,
                "notes": notes,
            })
            transaction_ids.append(txn2.id)

        db.commit()

        result = {
            "transaction_ids": transaction_ids,
            "free_credit_used_inr": float(free_credit_used),
            "wallet_used_inr": float(wallet_used),
            "free_credit_remaining_inr": float(getattr(tenant, "free_credit_remaining_inr", 0)),
            "wallet_balance_inr": float(billing.balance_inr),
        }
        logger.info(
            f"Wallet deducted: tenant={tenant_id}, total=₹{amount_inr}, "
            f"free_credit_used=₹{free_credit_used}, wallet_used=₹{wallet_used}"
        )
        return result

    # ------------------------------------------------------------------
    # BALANCE READ
    # ------------------------------------------------------------------

    def get_balance(self, db: Session, *, tenant_id: int) -> dict:
        """
        Returns combined balance snapshot. Non-locking read — for display only.
        Do NOT use this to make spend decisions; use check_can_afford() in billing_enforcement.
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)

        free_credit = float(getattr(tenant, "free_credit_remaining_inr", 0)) if tenant else 0.0
        wallet = float(billing.balance_inr)

        return {
            "free_credit_remaining_inr": free_credit,
            "wallet_balance_inr": wallet,
            "total_available_inr": free_credit + wallet,
        }

    def get_ledger(
        self, db: Session, *, tenant_id: int, limit: int = 50, offset: int = 0
    ) -> list:
        return crud.wallet_transaction.get_ledger(db, tenant_id=tenant_id, limit=limit, offset=offset)


# Singleton instance
wallet_service = WalletService()
```

#### What Does NOT Change

- `billing_enforcement_service.py` — not touched in this ticket (B4 handles that)
- `tenant_billing` CRUD — not touched
- No existing endpoints change

#### Acceptance Criteria

- [ ] `wallet_service.record_free_credit(db, tenant_id=1, amount_inr=100.0, idempotency_key="signup:1")` → creates 1 `WalletTransaction` row with `txn_type="signup_bonus"`, updates `tenant.free_credit_remaining_inr`
- [ ] Calling same method twice with same idempotency_key → returns `{"status": "already_processed"}`, only 1 row in DB
- [ ] `wallet_service.deduct(db, tenant_id=1, amount_inr=12.0, txn_type="document_analysis")` when `free_credit=10, wallet=500` → creates 2 rows: `free_credit_used=10`, `wallet_used=2`; `tenant.free_credit_remaining_inr=0`; `billing.balance_inr=498`
- [ ] `wallet_service.deduct(...)` when `free_credit=0, wallet=500` → creates 1 row (wallet only)
- [ ] `wallet_service.deduct(...)` when `free_credit=200, wallet=0` and amount=50 → creates 1 row (free credit only, wallet unchanged)
- [ ] Two concurrent `deduct()` calls do not double-deduct (SELECT FOR UPDATE prevents race)
- [ ] `wallet_service.get_balance(db, tenant_id=1)` → `total_available_inr = free_credit + wallet`
- [ ] `pytest backend/tests/` — all existing tests pass (new files only)

---

### TICKET B4 — Billing Enforcement Service Update
**Owner:** Backend
**Effort:** 1 day
**Track:** A
**Depends on:** A1, B3 (wallet_service must exist)

#### Context

`billing_enforcement_service.py` currently:
- `check_can_afford_analysis()` → checks `billing.balance_inr` only (ignores free credit pool)
- `deduct_cost()` → writes directly to `billing.balance_inr` (no ledger, no SELECT FOR UPDATE)
- `check_low_balance()` → ignores free credit pool

After this ticket:
- Both methods keep **identical signatures** — zero callers break
- `check_can_afford_analysis()` checks combined balance (free_credit + wallet)
- `deduct_cost()` delegates to `wallet_service.deduct()` for ledger + race protection
- Low balance alert throttle uses `last_low_balance_alert_at` from A4

**Backward compatibility rule:** If the new DB fields (A1) are not yet present on the tenant object (pre-migration DB), `getattr(..., default)` fallbacks ensure the old behavior is preserved. The service degrades gracefully, not crashes.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/services/billing_enforcement_service.py` | Modify two methods. Signatures unchanged. |

#### Step 1 — Update `check_can_afford_analysis()`

The method signature stays identical: `(db, *, tenant_id, estimated_cost_inr=5.0) -> Dict`

Replace the prepaid balance check block inside the method with two-pool aware logic:

```python
def check_can_afford_analysis(
    self,
    db: Session,
    *,
    tenant_id: int,
    estimated_cost_inr: float = 5.0
) -> Dict:
    """
    Check if tenant can afford a document analysis operation.
    Signature unchanged from pre-B4. Callers need no update.

    Two-pool check: free_credit_remaining_inr is checked FIRST,
    then balance_inr. A tenant with ₹10 free credit + ₹500 wallet
    CAN afford a ₹12 analysis (combined = ₹510 >= ₹12).
    """
    self.logger.info(
        f"Checking affordability for tenant {tenant_id}, estimated cost: ₹{estimated_cost_inr}"
    )

    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
    self._check_and_perform_rollover(db, billing)

    # Read two-pool balance
    # getattr fallback: if A1 migration hasn't run yet, free_credit=0 (old behavior)
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    free_credit = float(getattr(tenant, "free_credit_remaining_inr", 0)) if tenant else 0.0
    wallet_balance = float(billing.balance_inr)
    combined_balance = free_credit + wallet_balance

    result = {
        "can_proceed": True,
        "reason": "OK",
        "billing_type": billing.billing_type,
        "current_month_cost": float(billing.current_month_cost),
        "monthly_limit_inr": float(billing.monthly_limit_inr) if billing.monthly_limit_inr else None,
        # New fields (additive — no old caller breaks by receiving extra keys)
        "free_credit_remaining_inr": free_credit,
        "wallet_balance_inr": wallet_balance,
        "combined_balance_inr": combined_balance,
    }

    if billing.billing_type == "prepaid":
        result["balance_inr"] = combined_balance  # Keep old key; now = combined total

        if combined_balance < estimated_cost_inr:
            self.logger.warning(
                f"Insufficient balance for tenant {tenant_id}: "
                f"combined=₹{combined_balance} (free=₹{free_credit} + wallet=₹{wallet_balance}), "
                f"required=₹{estimated_cost_inr}"
            )
            raise InsufficientBalanceException(
                tenant_id=tenant_id,
                required=estimated_cost_inr,
                available=combined_balance
            )

        self.logger.info(
            f"Prepaid check passed: free_credit=₹{free_credit}, wallet=₹{wallet_balance}, "
            f"combined=₹{combined_balance}"
        )

    elif billing.billing_type == "postpaid":
        # Postpaid: monthly limit check (unchanged logic)
        if billing.monthly_limit_inr is not None:
            projected_cost = billing.current_month_cost + Decimal(str(estimated_cost_inr))
            if projected_cost > billing.monthly_limit_inr:
                self.logger.warning(
                    f"Monthly limit exceeded for tenant {tenant_id}: "
                    f"limit=₹{billing.monthly_limit_inr}, projected=₹{projected_cost}"
                )
                raise MonthlyLimitExceededException(
                    tenant_id=tenant_id,
                    limit=float(billing.monthly_limit_inr),
                    current=float(billing.current_month_cost)
                )

        self.logger.info(f"Postpaid check passed: current_month=₹{billing.current_month_cost}")

    return result
```

#### Step 2 — Update `deduct_cost()`

The method signature stays identical: `(db, *, tenant_id, cost_inr, description="Document analysis") -> Dict`

Replace the direct `billing.balance_inr` mutation with a `wallet_service.deduct()` call. Wrap in try/except so that if wallet_service fails for any reason, the old direct-write fallback activates — the deduction still happens, just without ledger recording.

```python
def deduct_cost(
    self,
    db: Session,
    *,
    tenant_id: int,
    cost_inr: float,
    description: str = "Document analysis"
) -> Dict:
    """
    Deduct cost from tenant after operation completes.
    Signature unchanged from pre-B4. Callers need no update.

    Now delegates to wallet_service for two-pool deduction + ledger recording.
    Falls back to direct deduction if wallet_service is unavailable.
    """
    self.logger.info(f"Deducting ₹{cost_inr} from tenant {tenant_id} for: {description}")

    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
    self._check_and_perform_rollover(db, billing)

    result = {
        "success": True,
        "billing_type": billing.billing_type,
        "cost_deducted_inr": cost_inr,
        "low_balance_alert": False,
    }

    if billing.billing_type == "prepaid":
        try:
            # Delegate to wallet_service for two-pool deduction + ledger
            from app.services.wallet_service import wallet_service
            wallet_result = wallet_service.deduct(
                db,
                tenant_id=tenant_id,
                amount_inr=cost_inr,
                txn_type="document_analysis",
                notes=description,
            )
            result["new_balance_inr"] = wallet_result["wallet_balance_inr"]
            result["free_credit_remaining_inr"] = wallet_result["free_credit_remaining_inr"]
            result["new_current_month_cost"] = float(billing.current_month_cost)
            result["wallet_transaction_ids"] = wallet_result["transaction_ids"]

            # Low balance alert (combined balance check)
            combined = wallet_result["wallet_balance_inr"] + wallet_result["free_credit_remaining_inr"]
            if Decimal(str(combined)) < billing.low_balance_threshold:
                result["low_balance_alert"] = True
                self._maybe_send_low_balance_alert(db, billing, combined)

        except Exception as wallet_err:
            # Fallback: old direct deduction (no ledger — better than blocking the user)
            self.logger.warning(
                f"wallet_service.deduct() failed for tenant {tenant_id}: {wallet_err}. "
                f"Falling back to direct deduction."
            )
            new_balance = billing.balance_inr - Decimal(str(cost_inr))
            billing.balance_inr = new_balance
            billing.current_month_cost += Decimal(str(cost_inr))
            billing.last_30_days_cost += Decimal(str(cost_inr))
            db.add(billing)
            db.commit()
            db.refresh(billing)

            result["new_balance_inr"] = float(new_balance)
            result["new_current_month_cost"] = float(billing.current_month_cost)
            if new_balance < billing.low_balance_threshold:
                result["low_balance_alert"] = True

    elif billing.billing_type == "postpaid":
        # Postpaid: record in usage/month cost (unchanged logic)
        billing.current_month_cost += Decimal(str(cost_inr))
        billing.last_30_days_cost += Decimal(str(cost_inr))
        db.add(billing)
        db.commit()
        db.refresh(billing)
        result["new_current_month_cost"] = float(billing.current_month_cost)
        self.logger.info(f"Postpaid charge recorded: new_current_month=₹{billing.current_month_cost}")

    return result
```

#### Step 3 — Add `_maybe_send_low_balance_alert()` helper

Add this private method to `BillingEnforcementService`. Uses `last_low_balance_alert_at` (A4 column on `tenant_billing`) to throttle repeated alerts to max 1 per 24 hours.

```python
def _maybe_send_low_balance_alert(self, db: Session, billing, combined_balance: float) -> None:
    """
    Send low balance alert if not already sent in the last 24 hours.
    Uses last_low_balance_alert_at from tenant_billing (added in A4).
    Silently skips if column doesn't exist yet (pre-A4 DB).
    """
    try:
        from datetime import datetime, timedelta
        last_alert = getattr(billing, "last_low_balance_alert_at", None)
        if last_alert and (datetime.now() - last_alert) < timedelta(hours=24):
            return  # Already alerted recently

        self.logger.warning(
            f"Low balance alert for tenant {billing.tenant_id}: "
            f"combined=₹{combined_balance}, threshold=₹{billing.low_balance_threshold}"
        )
        # Update throttle timestamp
        billing.last_low_balance_alert_at = datetime.now()
        db.add(billing)
        db.commit()
        # TODO (Part E): trigger email/notification here
    except Exception as e:
        self.logger.warning(f"Low balance alert failed (non-critical): {e}")
```

#### What Does NOT Change

- `InsufficientBalanceException` class — unchanged
- `MonthlyLimitExceededException` class — unchanged
- `check_low_balance()` method — unchanged (still works, reads balance_inr only; acceptable for now)
- `get_current_usage()` method — unchanged
- `_check_and_perform_rollover()` — unchanged
- `estimate_analysis_cost()` — unchanged
- Singleton `billing_enforcement_service` — same import path, same name

#### Acceptance Criteria

- [ ] `check_can_afford_analysis(db, tenant_id=1, estimated_cost_inr=12.0)` when `free_credit=10, wallet=500` → `can_proceed=True`, `combined_balance_inr=510.0`
- [ ] `check_can_afford_analysis(db, tenant_id=1, estimated_cost_inr=50.0)` when `free_credit=5, wallet=30` → raises `InsufficientBalanceException(available=35.0)`
- [ ] `deduct_cost(db, tenant_id=1, cost_inr=12.0)` when `free_credit=10, wallet=500` → 2 wallet_transaction rows created; `free_credit_remaining_inr=0`; `wallet_balance_inr=498`
- [ ] `deduct_cost(...)` when wallet_service raises → fallback path runs, billing.balance_inr decremented directly, no exception to caller
- [ ] `result["new_balance_inr"]` key still present in deduct_cost() return value (callers that read this key still work)
- [ ] `_maybe_send_low_balance_alert()` does not send twice within 24h
- [ ] `_maybe_send_low_balance_alert()` does not crash if `last_low_balance_alert_at` column missing (pre-A4 DB)
- [ ] Tenant with no `free_credit_remaining_inr` attribute → `getattr` returns 0, old prepaid behavior preserved
- [ ] `pytest backend/tests/` — all existing tests pass

---

### TICKET B5 — Signup Free Credit Grant
**Owner:** Backend
**Effort:** 0.25 day
**Track:** A
**Depends on:** A1, A2, B3 (wallet_service must exist)

#### Context

When a tenant registers today, step 5 in `tenants.py` creates a billing record:
```python
billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant.id)
```
That's where it ends. `tenant.free_credit_remaining_inr` is set to `100.00` by the DB `server_default` (from migration A1), but there is no ledger record. No `wallet_transactions` row. No audit trail for the ₹100 bonus.

This ticket adds a single step after the billing record creation that records the signup bonus in the ledger. It is wrapped in `try/except` — a wallet_service failure must **never block registration**.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/tenants.py` | Add 1 try/except block after step 5 |

#### Change — `tenants.py` `register_tenant()` function

After line `billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant.id)`, add:

```python
        # 5a. Record signup free credit in wallet ledger (Phase 9 — B5)
        # Wrapped in try/except — wallet ledger failure must never block registration.
        try:
            from app.services.wallet_service import wallet_service
            wallet_service.record_free_credit(
                db,
                tenant_id=tenant.id,
                amount_inr=100.0,
                idempotency_key=f"signup:{tenant.id}",
            )
            logger.info(f"Signup free credit recorded in ledger for tenant {tenant.id}")
        except Exception as wallet_err:
            # Non-fatal: free_credit_remaining_inr is already set to 100.00 by DB default (A1).
            # Missing ledger entry is a data quality issue, not a blocking error.
            logger.warning(
                f"Could not record signup free credit in wallet ledger for tenant {tenant.id}: {wallet_err}. "
                f"Registration continues — tenant.free_credit_remaining_inr set by DB default."
            )
```

The full registration flow after this change:
1. Validate subdomain availability
2. Check admin email uniqueness
3. Create tenant record — DB default sets `free_credit_remaining_inr=100.00`
4. Create first admin user (CXO role)
5. Initialize billing record
5a. **[NEW]** Record ₹100 signup bonus in wallet_transactions ledger ← this ticket
6. Generate access tokens
7. Return response

#### Idempotency Note

`record_free_credit()` uses `idempotency_key=f"signup:{tenant.id}"`. If registration is retried (network timeout on client side, duplicate POST), the second call returns `{"status": "already_processed"}` and does not create a duplicate ledger row. The tenant still only gets ₹100.

#### What Does NOT Change

- Registration response shape — unchanged
- All other registration steps — unchanged
- Rate limiting decorator — unchanged
- Error handling for steps 1–4 — unchanged

#### Acceptance Criteria

- [ ] New tenant registration → 1 `wallet_transactions` row with `txn_type="signup_bonus"`, `amount_inr=100.00`, `direction="credit"`
- [ ] `tenant.free_credit_remaining_inr` = 100.00 after registration
- [ ] Calling `/register` twice with same idempotency key → only 1 ledger row, second call returns 200/201 as normal (registration fails at subdomain check before reaching B5 step — the idempotency_key guard is a secondary protection)
- [ ] If `wallet_service.record_free_credit()` raises any exception → registration still succeeds (HTTP 201), warning is logged
- [ ] `pytest backend/tests/` — all existing tests pass

---

## PART B SUMMARY

| Ticket | Title | Owner | Track | Effort | New Files | Modified Files |
|--------|-------|-------|-------|--------|-----------|----------------|
| B0 | Gemini 3 Migration (**URGENT**) | Backend | A | 0.5d | — | config.py, cost_service.py, gemini.py |
| B1 | Cost Service Markup Refactor | Backend | A | 1d | — | cost_service.py, gemini.py |
| B2 | Model Selector Service | Backend | A | 0.5d | model_selector.py | provider_router.py (additive) |
| B3 | Wallet Service | Backend | A | 1d | wallet_service.py, crud_wallet_transaction.py | crud/__init__.py |
| B4 | Billing Enforcement Update | Backend | A | 1d | — | billing_enforcement_service.py |
| B5 | Signup Free Credit Grant | Backend | A | 0.25d | — | tenants.py |
| **Total Part B** | | | | **4.25 days** | | |

### Execution Order

```
B0  ─────────────────────────────────────────────► deploy before June 17
      ↓ (after B0 pricing registry exists)
B1  ──────────────────────────────────────────────► cost service + markup
      ↓ (after A1 tenant fields exist)
B2  ──────────────────────────────────────────────► model selector (parallel with B1)
      ↓ (after A2 wallet_transactions table exists)
B3  ──────────────────────────────────────────────► wallet service
      ↓ (after A1 + B3)
B4  ──────────────────────────────────────────────► billing enforcement update
      ↓ (after A1 + A2 + B3)
B5  ──────────────────────────────────────────────► signup bonus ledger entry
```

### Backward Compatibility Guarantees (Full List)

| Concern | How it is protected |
|---------|---------------------|
| `calculate_cost_from_actual_tokens()` callers reading `cost_inr` | Key still present; now = marked-up total (correct behavior for billing) |
| `calculate_cost_from_actual_tokens()` signature | New `model` param has `default=None` — all existing calls work |
| `check_can_afford_analysis()` signature | Identical — no parameter added or removed |
| `check_can_afford_analysis()` return dict | Old keys all present; new keys added (callers ignore unknown keys) |
| `deduct_cost()` signature | Identical — no parameter added or removed |
| `deduct_cost()` return dict | `new_balance_inr` key still present |
| `deduct_cost()` when wallet_service fails | Falls back to old direct-write; caller gets 200, not a 500 |
| Tenant without A1 fields (pre-migration DB) | `getattr(tenant, "free_credit_remaining_inr", 0)` — no AttributeError |
| Tenant without A4 fields (pre-migration DB) | `getattr(billing, "last_low_balance_alert_at", None)` — no AttributeError |
| `provider_router.py` existing methods | Untouched — `get_client_for_model()` is additive only |
| Registration endpoint response | Shape unchanged |
| All existing tests | No interface changes in any public method |

✅ **PART B COMPLETE** — 6 tickets, 4.25 days. Zero breaking changes to existing callers. All Track A (no GSTIN required).

---

## PART C — BACKEND PAYMENTS

> **Context:** Part C covers everything that moves real money. Most tickets here are Track B (blocked by GSTIN — Razorpay will not activate a merchant without one). However, the code is written and tested now so that the day GSTIN arrives, flipping `RAZORPAY_ENABLED=true` in `.env` is the only deploy needed.
>
> **Feature flag:** Every Razorpay-touching endpoint checks `settings.RAZORPAY_ENABLED` at runtime and returns `HTTP 503 {"detail": "Payments not yet available in your region. Contact support."}` when false. This is not a code gate — it is a config gate. No re-deployment required to go live.
>
> **Track A tickets in Part C:** C5 (enterprise contact form) and C6 (wallet balance endpoints) and C7 (nightly reconciliation) ship immediately. They do not touch Razorpay.
>
> **Existing stub:** `POST /billing/topup` currently adds balance directly with no Razorpay. It is NOT removed — it stays as a manual admin top-up path (used by B5 signup bonus internally and by admin grant scenarios). It is renamed in docs but the route stays.

---

### TICKET C1 — Razorpay SDK Setup & Config
**Owner:** Backend
**Effort:** 0.25 day
**Track:** B (GSTIN-blocked — but write the code now)
**Depends on:** Nothing

#### Context

Razorpay provides an official Python SDK (`razorpay`). All API calls (create order, fetch payment, verify signature) go through it. The webhook signature verification uses HMAC-SHA256 with the webhook secret.

#### Files

| File | Type of change |
|------|---------------|
| `backend/requirements.txt` (or `pyproject.toml`) | Add `razorpay>=1.4.1` |
| `backend/app/core/config.py` | Add 4 new settings |
| `backend/app/services/razorpay_service.py` | **New file** |

#### Step 1 — `requirements.txt`

```
razorpay>=1.4.1
```

#### Step 2 — `config.py` additions

Add after the Anthropic settings block:

```python
# --- Razorpay Payment Gateway (Phase 9 — Track B, D8) ---
# Set RAZORPAY_ENABLED=true ONLY after GSTIN is registered and Razorpay account is activated
RAZORPAY_ENABLED: bool = Field(default=False, env="RAZORPAY_ENABLED")
RAZORPAY_KEY_ID: str = Field(default="", env="RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET: str = Field(default="", env="RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET: str = Field(default="", env="RAZORPAY_WEBHOOK_SECRET")
```

> **Security note:** `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` must never be committed to source control. Add to `.env.example` as empty strings with comments. Add to production secrets manager.

#### Step 3 — `razorpay_service.py` (new file)

```python
"""
Razorpay Service — Phase 9 (Track B, D8)
Wrapper around the razorpay Python SDK.
All methods check RAZORPAY_ENABLED and raise PaymentsDisabledException if false.
"""
import hmac
import hashlib
import razorpay
from typing import Optional
from decimal import Decimal
from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import DokyDocException

logger = get_logger("services.razorpay")

# Minimum and maximum recharge amounts (Decision D2)
RECHARGE_PRESETS_INR = [100, 200, 500, 1000, 2500, 5000]
MIN_RECHARGE_INR = 100
# No maximum enforced per D2


class PaymentsDisabledException(DokyDocException):
    """Raised when Razorpay is accessed before GSTIN is registered."""
    def __init__(self):
        super().__init__(
            message="Payments are not yet available. Contact support@dokydoc.ai to enable.",
            details={"reason": "RAZORPAY_ENABLED=false", "action": "acquire_gstin"}
        )


class RazorpayService:
    """
    Thin wrapper around razorpay SDK.
    Raises PaymentsDisabledException on all methods when RAZORPAY_ENABLED=false.
    """

    def _client(self) -> razorpay.Client:
        """Returns authenticated Razorpay client. Raises if payments disabled."""
        if not settings.RAZORPAY_ENABLED:
            raise PaymentsDisabledException()
        return razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def create_order(self, amount_inr: float, tenant_id: int, idempotency_key: str) -> dict:
        """
        Create a Razorpay order.

        Razorpay amounts are in paise (1 INR = 100 paise).
        Returns the full Razorpay order dict (includes 'id' = razorpay_order_id).
        """
        if amount_inr < MIN_RECHARGE_INR:
            raise ValueError(f"Minimum recharge is ₹{MIN_RECHARGE_INR}. Got ₹{amount_inr}")

        amount_paise = int(Decimal(str(amount_inr)) * 100)  # Never use float multiplication for money

        client = self._client()
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": idempotency_key,          # Our internal key, echoed back in webhook
            "notes": {
                "tenant_id": str(tenant_id),
                "platform": "dokydoc",
            },
            "payment_capture": 1,                # Auto-capture on payment (not manual capture)
        })
        logger.info(f"Razorpay order created: {order['id']} for tenant={tenant_id}, amount=₹{amount_inr}")
        return order

    def fetch_payment(self, razorpay_payment_id: str) -> dict:
        """Fetch payment details by payment ID."""
        client = self._client()
        return client.payment.fetch(razorpay_payment_id)

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """
        Verify the HMAC-SHA256 signature from Razorpay checkout callback.
        Must be called after customer completes payment on frontend.
        Returns True if valid, False if tampered/invalid.
        """
        if not settings.RAZORPAY_ENABLED:
            raise PaymentsDisabledException()

        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected, razorpay_signature)
        if not is_valid:
            logger.warning(
                f"Payment signature mismatch! order={razorpay_order_id}, "
                f"payment={razorpay_payment_id}"
            )
        return is_valid

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify the HMAC-SHA256 signature on incoming Razorpay webhooks.
        body must be the raw request bytes (before JSON parsing).
        Returns True if valid, False if not.
        """
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            logger.error("RAZORPAY_WEBHOOK_SECRET is not set — cannot verify webhook")
            return False

        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# Singleton instance
razorpay_service = RazorpayService()
```

#### Acceptance Criteria

- [ ] `razorpay_service.create_order(...)` raises `PaymentsDisabledException` when `RAZORPAY_ENABLED=false`
- [ ] `razorpay_service.verify_payment_signature(...)` returns False for tampered signature (unit testable without network)
- [ ] `razorpay_service.verify_webhook_signature(...)` returns False for mismatched HMAC
- [ ] `pytest backend/tests/` — all existing tests pass (new file only)

---

### TICKET C2 — Create Order Endpoint
**Owner:** Backend
**Effort:** 0.5 day
**Track:** B (GSTIN-blocked)
**Depends on:** A3 (razorpay_orders table), C1 (razorpay_service)

#### Context

Step 1 of the payment flow: customer clicks "Recharge ₹500", frontend calls this endpoint to get a Razorpay `order_id`. The frontend then opens the Razorpay checkout popup using that `order_id` + our `key_id`. Without this endpoint, the frontend has nothing to hand to Razorpay.

**Why we create an order server-side (not client-side):**
Razorpay requires a signed order from your server before showing checkout. This prevents a customer from manipulating the amount in the browser.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add new endpoint |
| `backend/app/schemas/billing.py` | Add request/response schemas |
| `backend/app/crud/crud_razorpay_order.py` | **New file** |
| `backend/app/crud/__init__.py` | Register new CRUD |

#### CRUD — `crud_razorpay_order.py`

```python
"""CRUD for RazorpayOrder — Phase 9"""
from sqlalchemy.orm import Session
from app.models.razorpay_order import RazorpayOrder
from typing import Optional


class CRUDRazorpayOrder:

    def create(self, db: Session, *, obj_in: dict) -> RazorpayOrder:
        order = RazorpayOrder(**obj_in)
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def get_by_razorpay_order_id(self, db: Session, *, razorpay_order_id: str) -> Optional[RazorpayOrder]:
        return db.query(RazorpayOrder).filter(
            RazorpayOrder.razorpay_order_id == razorpay_order_id
        ).first()

    def get_by_idempotency_key(self, db: Session, *, key: str) -> Optional[RazorpayOrder]:
        return db.query(RazorpayOrder).filter(
            RazorpayOrder.idempotency_key == key
        ).first()

    def update_status(
        self, db: Session, *, razorpay_order_id: str,
        status: str, razorpay_payment_id: str = None
    ) -> Optional[RazorpayOrder]:
        order = self.get_by_razorpay_order_id(db, razorpay_order_id=razorpay_order_id)
        if order:
            order.status = status
            if razorpay_payment_id:
                order.razorpay_payment_id = razorpay_payment_id
            db.add(order)
            db.commit()
            db.refresh(order)
        return order


razorpay_order = CRUDRazorpayOrder()
```

#### Schemas — `billing.py` additions

```python
class CreateOrderRequest(BaseModel):
    amount_inr: float = Field(..., ge=100, description="Recharge amount in INR. Minimum ₹100.")

    @validator("amount_inr")
    def round_to_two_decimal(cls, v):
        return round(v, 2)


class CreateOrderResponse(BaseModel):
    razorpay_order_id: str       # Pass to Razorpay checkout: options.order_id
    razorpay_key_id: str         # Pass to Razorpay checkout: options.key
    amount_inr: float
    amount_paise: int            # Razorpay's native unit — for frontend validation
    currency: str = "INR"
    internal_order_id: int       # Our razorpay_orders.id — for tracking
```

#### Endpoint — add to `billing.py`

```python
@router.post("/create-order", response_model=schemas.billing.CreateOrderResponse)
@limiter.limit("10/minute")
def create_recharge_order(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    body: schemas.billing.CreateOrderRequest,
):
    """
    Create a Razorpay payment order for wallet recharge.
    [TRACK B — returns 503 until RAZORPAY_ENABLED=true]

    Step 1 of payment flow:
      1. Frontend calls this → gets razorpay_order_id + key_id
      2. Frontend opens Razorpay checkout popup
      3. Customer pays
      4. Frontend calls POST /billing/verify-payment (C3)

    Presets: ₹100, ₹200, ₹500, ₹1,000, ₹2,500, ₹5,000 or any custom amount ≥ ₹100.
    """
    if not settings.RAZORPAY_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Payments not yet available. Contact support@dokydoc.ai"
        )

    # Idempotency key — prevents duplicate orders on network retry
    idempotency_key = f"order:{tenant_id}:{current_user.id}:{int(body.amount_inr * 100)}"

    # Check if a pending order already exists for same amount (prevent double-click)
    existing = crud.razorpay_order.get_by_idempotency_key(db, key=idempotency_key)
    if existing and existing.status == "created":
        logger.info(f"Returning existing pending order for tenant {tenant_id}: {existing.razorpay_order_id}")
        return schemas.billing.CreateOrderResponse(
            razorpay_order_id=existing.razorpay_order_id,
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
            amount_inr=body.amount_inr,
            amount_paise=int(body.amount_inr * 100),
            internal_order_id=existing.id,
        )

    # Create order via Razorpay API
    from app.services.razorpay_service import razorpay_service
    rp_order = razorpay_service.create_order(
        amount_inr=body.amount_inr,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    )

    # Persist to razorpay_orders table (A3)
    internal_order = crud.razorpay_order.create(db, obj_in={
        "tenant_id": tenant_id,
        "user_id": current_user.id,
        "amount_inr": body.amount_inr,
        "razorpay_order_id": rp_order["id"],
        "status": "created",
        "idempotency_key": idempotency_key,
    })

    logger.info(
        f"Order created: internal_id={internal_order.id}, "
        f"razorpay_order_id={rp_order['id']}, amount=₹{body.amount_inr}, tenant={tenant_id}"
    )

    return schemas.billing.CreateOrderResponse(
        razorpay_order_id=rp_order["id"],
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount_inr=body.amount_inr,
        amount_paise=int(body.amount_inr * 100),
        internal_order_id=internal_order.id,
    )
```

#### Acceptance Criteria

- [ ] `POST /billing/create-order` with `RAZORPAY_ENABLED=false` → HTTP 503
- [ ] `POST /billing/create-order {"amount_inr": 50}` → HTTP 422 (below ₹100 minimum)
- [ ] `POST /billing/create-order {"amount_inr": 500}` with `RAZORPAY_ENABLED=true` → `razorpay_order_id` returned, row in `razorpay_orders` with `status="created"`
- [ ] Second call with same amount before paying → returns same `razorpay_order_id` (idempotent)
- [ ] `amount_paise = amount_inr * 100` (e.g. ₹500 → 50000 paise)
- [ ] Rate limit: 11th call/min → 429

---

### TICKET C3 — Verify Payment Endpoint (Frontend-Triggered)
**Owner:** Backend
**Effort:** 0.5 day
**Track:** B (GSTIN-blocked)
**Depends on:** C1, C2, B3 (wallet_service)

#### Context

After the customer completes payment in the Razorpay popup, Razorpay calls the frontend's `handler` callback with three values:
- `razorpay_order_id` — the order we created in C2
- `razorpay_payment_id` — the new payment ID (format: `pay_XXXX`)
- `razorpay_signature` — HMAC-SHA256 proof that the payment is real

The frontend sends these three values to this endpoint. We verify the HMAC signature and, only if valid, credit the wallet. This is the **primary** success path for standard checkout.

**Why this AND a webhook (C4)?** The frontend call happens in seconds. The webhook (C4) is an async backup for cases where the user closes the browser before the frontend handler fires. Together they guarantee the wallet is credited. Both are idempotent — the second to arrive is a no-op.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add endpoint |
| `backend/app/schemas/billing.py` | Add schemas |

#### Schemas

```python
class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    status: str           # "credited" | "already_processed"
    amount_inr: float
    new_wallet_balance_inr: float
    transaction_id: int
    message: str
```

#### Endpoint

```python
@router.post("/verify-payment", response_model=schemas.billing.VerifyPaymentResponse)
@limiter.limit("20/minute")
def verify_payment(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    body: schemas.billing.VerifyPaymentRequest,
):
    """
    Verify Razorpay payment signature and credit the tenant wallet.
    [TRACK B — returns 503 until RAZORPAY_ENABLED=true]

    Step 3 of payment flow (after create-order and customer completing payment).
    Idempotent: safe to call multiple times — wallet is credited exactly once.

    Security: HMAC-SHA256 signature verification prevents fake credit requests.
    """
    if not settings.RAZORPAY_ENABLED:
        raise HTTPException(status_code=503, detail="Payments not yet available.")

    from app.services.razorpay_service import razorpay_service, PaymentsDisabledException
    from app.services.wallet_service import wallet_service

    # 1. Verify HMAC signature — reject if invalid, no exceptions
    is_valid = razorpay_service.verify_payment_signature(
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        razorpay_signature=body.razorpay_signature,
    )
    if not is_valid:
        logger.warning(
            f"Invalid payment signature from tenant {tenant_id}: "
            f"order={body.razorpay_order_id}, payment={body.razorpay_payment_id}"
        )
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    # 2. Look up internal order record
    internal_order = crud.razorpay_order.get_by_razorpay_order_id(
        db, razorpay_order_id=body.razorpay_order_id
    )
    if not internal_order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # 3. Verify order belongs to this tenant (prevent cross-tenant fraud)
    if internal_order.tenant_id != tenant_id:
        logger.error(
            f"Tenant mismatch! order.tenant_id={internal_order.tenant_id}, "
            f"calling tenant={tenant_id}"
        )
        raise HTTPException(status_code=403, detail="Order does not belong to this account.")

    # 4. Idempotency — idempotency_key = "rp:{razorpay_payment_id}"
    idempotency_key = f"rp:{body.razorpay_payment_id}"

    # 5. Credit wallet (idempotent — safe if webhook already processed it)
    wallet_result = wallet_service.record_credit(
        db,
        tenant_id=tenant_id,
        amount_inr=float(internal_order.amount_inr),
        txn_type="razorpay_topup",
        idempotency_key=idempotency_key,
        user_id=current_user.id,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        notes=f"Razorpay top-up via frontend verify. Payment: {body.razorpay_payment_id}",
    )

    # 6. Mark order as paid in razorpay_orders table
    crud.razorpay_order.update_status(
        db,
        razorpay_order_id=body.razorpay_order_id,
        status="paid",
        razorpay_payment_id=body.razorpay_payment_id,
    )

    # 7. Flip has_recharged_ever on tenant (unlocks paid models — D3)
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant and not getattr(tenant, "has_recharged_ever", True):
        tenant.has_recharged_ever = True
        db.add(tenant)
        db.commit()
        logger.info(f"Tenant {tenant_id} has_recharged_ever flipped to True — paid models unlocked")

    already_processed = wallet_result.get("status") == "already_processed"

    balance_after = wallet_result.get("new_balance_inr", 0)
    if already_processed:
        # Re-read balance for response
        billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
        balance_after = float(billing.balance_inr)

    logger.info(
        f"Payment {'already processed' if already_processed else 'credited'}: "
        f"tenant={tenant_id}, amount=₹{internal_order.amount_inr}, "
        f"payment={body.razorpay_payment_id}"
    )

    return schemas.billing.VerifyPaymentResponse(
        status="already_processed" if already_processed else "credited",
        amount_inr=float(internal_order.amount_inr),
        new_wallet_balance_inr=balance_after,
        transaction_id=wallet_result.get("transaction_id", 0),
        message=(
            "Payment already processed — no double credit applied."
            if already_processed
            else f"₹{internal_order.amount_inr} added to your wallet."
        ),
    )
```

#### Acceptance Criteria

- [ ] Valid signature + new payment → `status="credited"`, wallet balance increased, `has_recharged_ever=True` on tenant
- [ ] Valid signature + same `razorpay_payment_id` called twice → `status="already_processed"`, wallet NOT credited twice
- [ ] Tampered/invalid signature → HTTP 400
- [ ] Order belonging to different tenant → HTTP 403
- [ ] `razorpay_orders.status` updated to `"paid"` after successful verify
- [ ] `has_recharged_ever` is set to `True` only on first successful payment (not on free credit use)

---

### TICKET C4 — Razorpay Webhook Handler
**Owner:** Backend
**Effort:** 1 day
**Track:** B (GSTIN-blocked)
**Depends on:** C1, C2, C3, B3

#### Context

Razorpay retries webhooks up to 3 times on failure (HTTP non-2xx). Our handler must be:
1. **Idempotent** — process `payment.captured` exactly once even if Razorpay retries
2. **Signature-verified** — reject any request without a valid HMAC-SHA256 header
3. **Non-blocking** — return HTTP 200 immediately, do wallet crediting synchronously (Razorpay's retry window is 30 minutes)
4. **Never raise** — any internal error must be caught and logged; always return 200 to prevent Razorpay from retrying valid payments indefinitely

**Why a separate route from verify-payment (C3)?** The webhook comes directly from Razorpay's servers (no user session, no JWT). It bypasses all auth middleware. The verify-payment endpoint requires a logged-in user. Both write to the same idempotency key `"rp:{razorpay_payment_id}"` — so exactly one of them does the actual crediting.

**Webhook route registration:** The webhook endpoint must be **excluded from JWT auth middleware**. Add `"/api/v1/billing/webhook/razorpay"` to the public routes allowlist in `backend/app/api/deps.py` or `backend/main.py` middleware configuration.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add webhook endpoint |
| `backend/app/api/deps.py` or `backend/main.py` | Add webhook route to auth bypass list |

#### Endpoint

```python
@router.post("/webhook/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request, db: Session = Depends(deps.get_db)):
    """
    Razorpay webhook receiver.
    [TRACK B — silently returns 200 when RAZORPAY_ENABLED=false to avoid Razorpay retries]

    NO JWT AUTH — this endpoint is called by Razorpay servers directly.
    Must be added to auth bypass list in middleware.

    Signature: X-Razorpay-Signature header (HMAC-SHA256 of raw body)

    Events handled:
      payment.captured  — customer paid successfully
      payment.failed    — payment failed (log only, no wallet action)
      order.paid        — order fully paid (backup to payment.captured)

    Events ignored (logged and 200 returned):
      Any other event type.
    """
    # Early return when payments disabled (Razorpay retries otherwise)
    if not settings.RAZORPAY_ENABLED:
        return {"status": "payments_disabled"}

    # 1. Read raw body BEFORE parsing (signature is over raw bytes)
    raw_body = await request.body()

    # 2. Verify webhook signature
    signature = request.headers.get("X-Razorpay-Signature", "")
    from app.services.razorpay_service import razorpay_service
    if not razorpay_service.verify_webhook_signature(raw_body, signature):
        logger.warning(f"Razorpay webhook signature verification FAILED. IP: {request.client.host}")
        # Return 200 anyway — a 4xx would cause Razorpay to retry
        # Instead we log and discard. Legitimate payments go through C3 (verify-payment).
        return {"status": "signature_invalid"}

    # 3. Parse event
    import json
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Razorpay webhook: invalid JSON body")
        return {"status": "invalid_json"}

    event = payload.get("event", "")
    logger.info(f"Razorpay webhook received: event={event}")

    # 4. Route by event type
    try:
        if event == "payment.captured":
            await _handle_payment_captured(db, payload)
        elif event == "payment.failed":
            _handle_payment_failed(payload)
        elif event == "order.paid":
            await _handle_order_paid(db, payload)
        else:
            logger.debug(f"Razorpay webhook: ignoring event type '{event}'")

    except Exception as e:
        # CRITICAL: Never raise from webhook handler — would cause Razorpay to retry
        logger.error(f"Razorpay webhook handler error (event={event}): {e}", exc_info=True)

    return {"status": "ok"}


async def _handle_payment_captured(db: Session, payload: dict) -> None:
    """
    Handle payment.captured event — the primary success event.
    Idempotent via razorpay_payment_id idempotency key.
    """
    from app.services.wallet_service import wallet_service

    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_payment_id = payment.get("id")
    razorpay_order_id = payment.get("order_id")
    amount_paise = payment.get("amount", 0)
    amount_inr = amount_paise / 100

    if not razorpay_payment_id or not razorpay_order_id:
        logger.error(f"payment.captured missing payment_id or order_id: {payload}")
        return

    # Look up our internal order to get tenant_id
    internal_order = crud.razorpay_order.get_by_razorpay_order_id(
        db, razorpay_order_id=razorpay_order_id
    )
    if not internal_order:
        logger.error(f"payment.captured: razorpay_order_id={razorpay_order_id} not found in our DB")
        return

    tenant_id = internal_order.tenant_id
    idempotency_key = f"rp:{razorpay_payment_id}"

    # Credit wallet — idempotent (C3 may have already processed this)
    result = wallet_service.record_credit(
        db,
        tenant_id=tenant_id,
        amount_inr=amount_inr,
        txn_type="razorpay_topup",
        idempotency_key=idempotency_key,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        notes=f"Razorpay webhook: payment.captured. Payment: {razorpay_payment_id}",
    )

    # Update order status
    crud.razorpay_order.update_status(
        db,
        razorpay_order_id=razorpay_order_id,
        status="paid",
        razorpay_payment_id=razorpay_payment_id,
    )

    # Flip has_recharged_ever if not already set
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant and not getattr(tenant, "has_recharged_ever", True):
        tenant.has_recharged_ever = True
        db.add(tenant)
        db.commit()

    if result.get("status") == "already_processed":
        logger.info(f"Webhook: payment.captured already processed by C3: {razorpay_payment_id}")
    else:
        logger.info(f"Webhook: payment.captured processed: tenant={tenant_id}, ₹{amount_inr}")


def _handle_payment_failed(payload: dict) -> None:
    """Log payment failures. No wallet action needed."""
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    logger.warning(
        f"Razorpay payment.failed: payment_id={payment.get('id')}, "
        f"order_id={payment.get('order_id')}, "
        f"error={payment.get('error_description', 'unknown')}"
    )


async def _handle_order_paid(db: Session, payload: dict) -> None:
    """order.paid is a backup signal — delegate to payment.captured logic."""
    # Extract payment details from order.paid payload and re-use handler
    order = payload.get("payload", {}).get("order", {}).get("entity", {})
    payments = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if payments:
        await _handle_payment_captured(db, {
            "payload": {"payment": {"entity": payments}}
        })
```

#### Auth Bypass — `main.py` or `deps.py`

Add the webhook URL to the JWT skip list. The exact implementation depends on how middleware is structured:

```python
# In backend/main.py, wherever JWT middleware is applied:
WEBHOOK_PATHS_NO_AUTH = [
    "/api/v1/billing/webhook/razorpay",
]
# Skip JWT verification for these paths in the middleware
```

#### Acceptance Criteria

- [ ] Valid `payment.captured` webhook with correct signature → wallet credited, `razorpay_orders.status="paid"`
- [ ] Same webhook delivered twice (Razorpay retry) → idempotent, wallet credited only once
- [ ] Invalid/missing `X-Razorpay-Signature` → always returns HTTP 200 (not 401/400), logs warning
- [ ] `payment.failed` event → HTTP 200, warning logged, no wallet change
- [ ] Unknown event type → HTTP 200, debug logged, no action
- [ ] Any exception inside handler → caught, logged, HTTP 200 returned (never propagates)
- [ ] `has_recharged_ever` flipped to True on first successful webhook credit
- [ ] Webhook route returns 200 without JWT token in Authorization header

---

### TICKET C5 — Wallet Balance & Ledger Endpoints
**Owner:** Backend
**Effort:** 0.5 day
**Track:** A (no GSTIN required — reads ledger, doesn't move money)
**Depends on:** B3 (wallet_service), A2 (wallet_transactions table)

#### Context

Customers need to see their live balance (both pools) and a full history of every credit and debit. This powers the billing page in the frontend (Part E). The `/topup` endpoint already exists but returns stale `billing.balance_inr` only — it does not show free credit or ledger history.

These are read-only endpoints. Track A — ship immediately.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add 2 endpoints |
| `backend/app/schemas/billing.py` | Add response schemas |

#### Schemas

```python
class WalletBalanceResponse(BaseModel):
    free_credit_remaining_inr: float   # Signup bonus pool
    wallet_balance_inr: float          # Paid recharge pool
    total_available_inr: float         # Combined
    has_recharged_ever: bool           # Unlocks paid models
    low_balance_alert: bool            # true if total < low_balance_threshold


class WalletTransactionResponse(BaseModel):
    id: int
    direction: str                     # "credit" | "debit"
    amount_inr: float
    balance_after_inr: float
    txn_type: str
    notes: Optional[str]
    created_at: datetime


class WalletLedgerResponse(BaseModel):
    transactions: List[WalletTransactionResponse]
    total_count: int
    page: int
    limit: int
```

#### Endpoints

```python
@router.get("/wallet", response_model=schemas.billing.WalletBalanceResponse)
@limiter.limit(RateLimits.BILLING)
def get_wallet_balance(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get current wallet balance (both free credit pool and paid wallet pool).
    [TRACK A — available immediately]
    """
    from app.services.wallet_service import wallet_service
    from app.models.tenant import Tenant

    balance = wallet_service.get_balance(db, tenant_id=tenant_id)
    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    total = balance["total_available_inr"]
    threshold = float(billing.low_balance_threshold)

    return schemas.billing.WalletBalanceResponse(
        free_credit_remaining_inr=balance["free_credit_remaining_inr"],
        wallet_balance_inr=balance["wallet_balance_inr"],
        total_available_inr=total,
        has_recharged_ever=getattr(tenant, "has_recharged_ever", False) if tenant else False,
        low_balance_alert=total < threshold,
    )


@router.get("/wallet/transactions", response_model=schemas.billing.WalletLedgerResponse)
@limiter.limit(RateLimits.BILLING)
def get_wallet_ledger(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get paginated wallet transaction history (credits and debits).
    [TRACK A — available immediately]
    Shows every wallet movement: signup bonus, recharges, analysis charges.
    """
    from app.services.wallet_service import wallet_service

    offset = (page - 1) * limit
    transactions = wallet_service.get_ledger(
        db, tenant_id=tenant_id, limit=limit, offset=offset
    )
    total = crud.wallet_transaction.get_total_credits(db, tenant_id=tenant_id)  # approximate count

    return schemas.billing.WalletLedgerResponse(
        transactions=[
            schemas.billing.WalletTransactionResponse(
                id=t.id,
                direction=t.direction,
                amount_inr=float(t.amount_inr),
                balance_after_inr=float(t.balance_after_inr),
                txn_type=t.txn_type,
                notes=t.notes,
                created_at=t.created_at,
            )
            for t in transactions
        ],
        total_count=len(transactions),   # TODO: replace with COUNT query in next iteration
        page=page,
        limit=limit,
    )
```

#### Acceptance Criteria

- [ ] `GET /billing/wallet` → `total_available_inr = free_credit + wallet_balance`
- [ ] After signup: `free_credit_remaining_inr=100.0`, `wallet_balance_inr=0.0`, `has_recharged_ever=false`
- [ ] After first recharge: `has_recharged_ever=true`, `wallet_balance_inr > 0`
- [ ] `GET /billing/wallet/transactions?page=1&limit=5` → max 5 rows, sorted newest-first
- [ ] `GET /billing/wallet/transactions?limit=101` → HTTP 422 (exceeds max)

---

### TICKET C6 — Enterprise Contact Request Endpoint
**Owner:** Backend
**Effort:** 0.25 day
**Track:** A (no GSTIN required — stores a record and sends an email)
**Depends on:** A5 (enterprise_contact_requests table)

#### Context

Decision D7: Postpaid is manually enabled per enterprise customer — no self-serve. The entry point is a contact form on the billing page. When a customer submits it, we store the request and alert the sales team.

This is Track A because it does not touch Razorpay.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add endpoint |
| `backend/app/schemas/billing.py` | Add schema |
| `backend/app/crud/crud_enterprise_contact.py` | **New file** |

#### CRUD — `crud_enterprise_contact.py`

```python
from sqlalchemy.orm import Session
from app.models.enterprise_contact_request import EnterpriseContactRequest


class CRUDEnterpriseContact:
    def create(self, db: Session, *, obj_in: dict) -> EnterpriseContactRequest:
        record = EnterpriseContactRequest(**obj_in)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_pending(self, db: Session, limit: int = 50):
        return (
            db.query(EnterpriseContactRequest)
            .filter(EnterpriseContactRequest.status == "pending")
            .order_by(EnterpriseContactRequest.created_at.desc())
            .limit(limit)
            .all()
        )


enterprise_contact = CRUDEnterpriseContact()
```

#### Schema

```python
class EnterpriseContactRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    contact_name: str = Field(..., min_length=2, max_length=200)
    contact_email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    estimated_monthly_spend_inr: Optional[float] = Field(default=None, ge=0)
    message: Optional[str] = Field(default=None, max_length=2000)
    use_case: Optional[str] = Field(default=None, max_length=500)
```

#### Endpoint

```python
@router.post("/enterprise-contact", status_code=202)
@limiter.limit("3/minute")
def submit_enterprise_contact(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    body: schemas.billing.EnterpriseContactRequest,
):
    """
    Submit a request to be contacted about enterprise/postpaid billing.
    [TRACK A — available immediately, no GSTIN required]

    Stores the request in enterprise_contact_requests table (A5).
    Sends an internal alert to the sales team (currently via logger;
    wire up email/Slack in Part D or future sprint).
    """
    record = crud.enterprise_contact.create(db, obj_in={
        "tenant_id": tenant_id,
        "user_id": current_user.id,
        "company_name": body.company_name,
        "contact_name": body.contact_name,
        "contact_email": body.contact_email,
        "phone": body.phone,
        "estimated_monthly_spend_inr": body.estimated_monthly_spend_inr,
        "message": body.message,
        "use_case": body.use_case,
        "status": "pending",
    })

    # Sales team alert — replace with email/Slack webhook in next iteration
    logger.info(
        f"[ENTERPRISE LEAD] New enterprise contact request: "
        f"company={body.company_name}, email={body.contact_email}, "
        f"tenant={tenant_id}, record_id={record.id}"
    )

    return {
        "status": "received",
        "message": "We'll reach out within 1 business day.",
        "reference_id": record.id,
    }
```

#### Acceptance Criteria

- [ ] Valid request → HTTP 202, row in `enterprise_contact_requests` with `status="pending"`
- [ ] Missing required fields → HTTP 422
- [ ] Rate limit: 4th call/minute → 429
- [ ] `reference_id` returned so frontend can show confirmation
- [ ] Logger outputs `[ENTERPRISE LEAD]` line with contact details (for manual monitoring until email is wired)

---

### TICKET C7 — Nightly Reconciliation Celery Task
**Owner:** Backend
**Effort:** 1 day
**Track:** A (runs locally against our own DB; Google Cloud Billing API integration is optional enhancement)
**Depends on:** A4 (raw_cost_inr in usage_logs), B1 (markup logic writes raw_cost_inr)

#### Context

Decision D9: Nightly reconciliation that compares what we charged customers against what Google/Anthropic charged us. Alerts if drift > 5%.

**Why this matters:** If `raw_cost_inr` in `usage_logs` drifts from actual Google Cloud bills, we are either over-charging or under-charging customers. Over-charging is a legal and reputational risk. Under-charging means we are losing money. This task is the safety net that catches both.

**Two-tier implementation:**

- **Tier 1 (Track A — ship now):** Internal consistency check. Sums `usage_logs.cost_inr` (customer-facing marked-up total) and `usage_logs.raw_cost_inr` (raw AI cost). Verifies `markup = cost_inr - raw_cost_inr` equals exactly 15% of raw. Catches bugs in B1 markup logic.

- **Tier 2 (Track A — adds Google Cloud API call):** Fetches actual daily spend from Google Cloud Billing API. Compares against `SUM(usage_logs.raw_cost_inr)` for the same date. Alerts if drift > 5%. This requires `GOOGLE_CLOUD_BILLING_ACCOUNT_ID` env var.

Both tiers produce a daily reconciliation record in a new `reconciliation_reports` table.

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/tasks/billing_tasks.py` | **New file** — Celery task |
| `backend/app/models/reconciliation_report.py` | **New file** — result storage |
| `backend/app/core/config.py` | Add `GOOGLE_CLOUD_BILLING_ACCOUNT_ID` setting |
| `backend/app/worker.py` | Register new task module |
| `backend/app/tasks/celery_beat_schedule.py` (or `worker.py`) | Add nightly beat schedule |

#### Model — `reconciliation_report.py`

```python
"""
ReconciliationReport — daily record of billing consistency check.
Phase 9 (D9)
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Numeric, Date, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, unique=True)

    # What our usage_logs say
    total_raw_cost_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    total_markup_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    total_charged_inr: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    usage_log_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Internal consistency check (Tier 1)
    markup_pct_actual: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # Should be 15.00
    markup_drift_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)   # |actual - 15| / 15 * 100
    tier1_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Google Cloud Billing API comparison (Tier 2 — nullable if API not configured)
    google_actual_cost_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    google_drift_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    tier2_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    tier2_skipped: Mapped[bool] = mapped_column(Boolean, default=False)  # True if API not configured

    # Alert status
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Raw results for debugging
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
```

**Migration:** `backend/alembic/versions/s9p7_reconciliation_reports.py`
- Down revision: `s9p6` (card-on-file)
- Creates `reconciliation_reports` table

#### Config addition

```python
# Google Cloud Billing API (Phase 9 — D9 Tier 2 reconciliation)
# Leave empty to skip Tier 2 (only Tier 1 internal check runs)
GOOGLE_CLOUD_BILLING_ACCOUNT_ID: str = Field(default="", env="GOOGLE_CLOUD_BILLING_ACCOUNT_ID")
```

#### Task — `billing_tasks.py`

```python
"""
Billing Celery Tasks — Phase 9
Nightly reconciliation: internal consistency (Tier 1) + Google Cloud API (Tier 2)
"""
from celery import shared_task
from datetime import date, timedelta, datetime
from decimal import Decimal
from sqlalchemy import func
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.logging import get_logger
from app.models.usage_log import UsageLog
from app.models.reconciliation_report import ReconciliationReport

logger = get_logger("tasks.billing_reconciliation")

DRIFT_ALERT_THRESHOLD_PCT = 5.0   # Alert if drift > 5% (D9)
MARKUP_EXPECTED_PCT = 15.0        # Must match MARKUP_PERCENT in cost_service.py


@shared_task(name="nightly_billing_reconciliation", bind=True, max_retries=2)
def nightly_billing_reconciliation(self, target_date: str = None):
    """
    Nightly reconciliation task. Runs at 01:00 UTC.
    target_date: ISO date string (YYYY-MM-DD). Defaults to yesterday.

    Tier 1: Internal consistency — verifies markup math in our own DB
    Tier 2: External comparison — compares against Google Cloud Billing API
    """
    db = SessionLocal()
    try:
        check_date = (
            date.fromisoformat(target_date)
            if target_date
            else date.today() - timedelta(days=1)
        )

        logger.info(f"Starting billing reconciliation for {check_date}")

        # --- TIER 1: Internal consistency check ---
        result = _run_tier1(db, check_date)

        # --- TIER 2: Google Cloud API comparison (optional) ---
        if settings.GOOGLE_CLOUD_BILLING_ACCOUNT_ID:
            result = _run_tier2(db, check_date, result)
        else:
            result["tier2_skipped"] = True
            result["tier2_passed"] = None
            logger.info("Tier 2 skipped: GOOGLE_CLOUD_BILLING_ACCOUNT_ID not configured")

        # --- Save report ---
        _save_report(db, check_date, result)

        # --- Alert if needed ---
        if not result.get("tier1_passed") or result.get("tier2_passed") is False:
            _send_alert(result, check_date)

        logger.info(
            f"Reconciliation complete for {check_date}: "
            f"tier1={'PASS' if result.get('tier1_passed') else 'FAIL'}, "
            f"tier2={'SKIP' if result.get('tier2_skipped') else ('PASS' if result.get('tier2_passed') else 'FAIL')}"
        )

    except Exception as e:
        logger.error(f"Reconciliation task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=3600)   # Retry in 1 hour
    finally:
        db.close()


def _run_tier1(db, check_date: date) -> dict:
    """
    Tier 1: Sum usage_logs for the day. Verify:
    - total_charged = total_raw * 1.15 (±0.01 INR rounding tolerance)
    - markup_pct ≈ 15.00%
    """
    from_dt = datetime.combine(check_date, datetime.min.time())
    to_dt = datetime.combine(check_date + timedelta(days=1), datetime.min.time())

    rows = db.query(
        func.count(UsageLog.id).label("count"),
        func.sum(UsageLog.cost_inr).label("total_charged"),
        func.coalesce(func.sum(UsageLog.raw_cost_inr), 0).label("total_raw"),
        func.coalesce(func.sum(UsageLog.markup_inr), 0).label("total_markup"),
    ).filter(
        UsageLog.created_at >= from_dt,
        UsageLog.created_at < to_dt,
    ).first()

    count = rows.count or 0
    total_charged = float(rows.total_charged or 0)
    total_raw = float(rows.total_raw or 0)
    total_markup = float(rows.total_markup or 0)

    # Calculate actual markup percentage
    actual_markup_pct = (
        (total_markup / total_raw * 100) if total_raw > 0 else MARKUP_EXPECTED_PCT
    )
    markup_drift_pct = abs(actual_markup_pct - MARKUP_EXPECTED_PCT) / MARKUP_EXPECTED_PCT * 100

    # Tier 1 passes if markup within 1% of expected (handles rounding noise)
    tier1_passed = markup_drift_pct <= 1.0 or count == 0

    result = {
        "usage_log_count": count,
        "total_raw_cost_inr": total_raw,
        "total_markup_inr": total_markup,
        "total_charged_inr": total_charged,
        "markup_pct_actual": round(actual_markup_pct, 2),
        "markup_drift_pct": round(markup_drift_pct, 2),
        "tier1_passed": tier1_passed,
    }

    if not tier1_passed:
        logger.warning(
            f"Tier 1 FAILED for {check_date}: expected markup=15%, "
            f"actual={actual_markup_pct:.2f}%, drift={markup_drift_pct:.2f}%"
        )

    return result


def _run_tier2(db, check_date: date, result: dict) -> dict:
    """
    Tier 2: Compare our raw cost against Google Cloud Billing API.
    Requires google-cloud-billing SDK and GOOGLE_CLOUD_BILLING_ACCOUNT_ID.
    """
    try:
        from google.cloud import billing_v1
        from google.cloud.billing_v1.services.cloud_billing import CloudBillingClient

        client = CloudBillingClient()
        account_name = f"billingAccounts/{settings.GOOGLE_CLOUD_BILLING_ACCOUNT_ID}"

        # Fetch costs for the day from Google Cloud Billing API
        # NOTE: Google Cloud Billing API requires the Billing Budget API or
        # BigQuery export for per-day granularity. The simplest approach is
        # to use the BigQuery billing export. See:
        # https://cloud.google.com/billing/docs/how-to/export-data-bigquery
        #
        # If BigQuery export is not set up, set GOOGLE_CLOUD_BILLING_ACCOUNT_ID=""
        # and Tier 2 will be skipped automatically.
        #
        # Placeholder implementation — wire up BigQuery query here:
        google_cost_usd = _query_bigquery_billing(check_date)

        if google_cost_usd is None:
            result["tier2_skipped"] = True
            result["tier2_passed"] = None
            return result

        # Convert to INR using same exchange rate logic as cost_service
        from app.services.cost_service import cost_service
        google_cost_inr = google_cost_usd * float(cost_service.usd_to_inr)

        our_raw_inr = result["total_raw_cost_inr"]
        drift_pct = abs(google_cost_inr - our_raw_inr) / google_cost_inr * 100 if google_cost_inr > 0 else 0

        result["google_actual_cost_inr"] = round(google_cost_inr, 4)
        result["google_drift_pct"] = round(drift_pct, 2)
        result["tier2_passed"] = drift_pct <= DRIFT_ALERT_THRESHOLD_PCT
        result["tier2_skipped"] = False

        if not result["tier2_passed"]:
            logger.error(
                f"Tier 2 FAILED for {check_date}: "
                f"our_raw=₹{our_raw_inr:.2f}, google=₹{google_cost_inr:.2f}, "
                f"drift={drift_pct:.2f}% (threshold: {DRIFT_ALERT_THRESHOLD_PCT}%)"
            )

    except ImportError:
        logger.warning("google-cloud-billing not installed. Skipping Tier 2.")
        result["tier2_skipped"] = True
        result["tier2_passed"] = None
    except Exception as e:
        logger.error(f"Tier 2 reconciliation error: {e}", exc_info=True)
        result["tier2_skipped"] = True
        result["tier2_passed"] = None

    return result


def _query_bigquery_billing(check_date: date):
    """
    Query Google Cloud Billing BigQuery export for daily AI spend.
    Returns total cost in USD for the given date, or None if not available.

    Setup required:
    1. Enable BigQuery billing export in Google Cloud Console
    2. Set GOOGLE_CLOUD_PROJECT and BIGQUERY_BILLING_DATASET in config
    3. Install google-cloud-bigquery

    Until this is set up, returns None (Tier 2 silently skipped).
    """
    # TODO: Implement BigQuery query when billing export is configured
    # Example query:
    # SELECT SUM(cost) FROM `{project}.{dataset}.gcp_billing_export_v1_*`
    # WHERE DATE(usage_start_time) = '{check_date}'
    #   AND service.description LIKE '%Generative Language%'
    return None


def _save_report(db, check_date: date, result: dict):
    """Save reconciliation result to DB. Upsert by date."""
    existing = db.query(ReconciliationReport).filter(
        ReconciliationReport.report_date == check_date
    ).first()

    if existing:
        for k, v in result.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        db.add(existing)
    else:
        report = ReconciliationReport(
            report_date=check_date,
            raw_data=result,
            alert_sent=False,
            **{k: v for k, v in result.items() if k != "raw_data"},
        )
        db.add(report)

    db.commit()


def _send_alert(result: dict, check_date: date):
    """
    Send alert when reconciliation fails.
    Currently: log at ERROR level (wire to email/PagerDuty in next sprint).
    """
    reasons = []
    if not result.get("tier1_passed"):
        reasons.append(
            f"Tier 1: markup drift {result.get('markup_drift_pct', '?')}% "
            f"(expected ~0%, got markup_actual={result.get('markup_pct_actual', '?')}%)"
        )
    if result.get("tier2_passed") is False:
        reasons.append(
            f"Tier 2: Google cost drift {result.get('google_drift_pct', '?')}% "
            f"(our_raw=₹{result.get('total_raw_cost_inr', '?')}, "
            f"google=₹{result.get('google_actual_cost_inr', '?')})"
        )

    alert_msg = f"[BILLING ALERT] Reconciliation FAILED for {check_date}: {'; '.join(reasons)}"
    logger.error(alert_msg)
    # TODO (Part D / future): send email to finance@dokydoc.ai + Slack #billing-alerts


@shared_task(name="run_reconciliation_for_date")
def run_reconciliation_for_date(target_date: str):
    """Manual trigger for a specific date. Useful for backfill and debugging."""
    nightly_billing_reconciliation.apply(args=[], kwargs={"target_date": target_date})
```

#### Celery Beat Schedule

Add to the beat schedule (wherever other periodic tasks are registered):

```python
"nightly-billing-reconciliation": {
    "task": "nightly_billing_reconciliation",
    "schedule": crontab(hour=1, minute=0),  # 01:00 UTC daily
    # Yesterday's data is complete by 01:00 UTC (accounting for late usage_log writes)
},
```

#### Worker Registration

In `backend/app/worker.py`, add to the `include` list:
```python
include=[
    ...,
    "app.tasks.billing_tasks",
]
```

#### Acceptance Criteria

- [ ] `nightly_billing_reconciliation.apply()` with no usage_logs for a day → `tier1_passed=True`, `usage_log_count=0`
- [ ] 100 usage_log rows with correct 15% markup → `tier1_passed=True`, `markup_drift_pct ≤ 1.0`
- [ ] 1 usage_log row with wrong markup (e.g. 20%) → `tier1_passed=False`, alert logged
- [ ] `GOOGLE_CLOUD_BILLING_ACCOUNT_ID=""` → `tier2_skipped=True`, no crash
- [ ] `ReconciliationReport` row created for each run date (upsert on re-run)
- [ ] Task failure (DB unavailable) → retries in 1 hour (max 2 retries)
- [ ] Beat schedule registered: `alembic check` + Celery worker shows task in scheduled list
- [ ] Migration `s9p7_reconciliation_reports.py` created with correct `down_revision="s9p6"`

---

---

## PART C SUMMARY

| Ticket | Title | Track | Effort | Key Files |
|--------|-------|-------|--------|-----------|
| C1 | Razorpay SDK Setup + Config | B | 0.25d | razorpay_service.py (new), config.py |
| C2 | Create Order Endpoint | B | 0.5d | billing.py, crud_razorpay_order.py (new) |
| C3 | Verify Payment Endpoint | B | 0.5d | billing.py |
| C4 | Webhook Handler | B | 1d | billing.py, deps.py (auth bypass) |
| C5 | Wallet Balance & Ledger Endpoints | **A** | 0.5d | billing.py |
| C6 | Enterprise Contact Request | **A** | 0.25d | billing.py, crud_enterprise_contact.py (new) |
| C7 | Nightly Reconciliation Celery Task | **A** | 1d | billing_tasks.py (new), reconciliation_report.py (new) |
| **Total Part C** | | | **4.0 days** | |

### Payment Flow — End to End

```
Customer clicks "Recharge ₹500"
         │
         ▼
POST /billing/create-order          [C2, Track B]
  → Razorpay API creates order
  → Returns razorpay_order_id + key_id
         │
         ▼
Frontend opens Razorpay checkout popup
Customer pays via UPI / card / netbanking
         │
    ┌────┴────┐
    │         │  (both paths are idempotent — only one credits wallet)
    ▼         ▼
POST           Razorpay webhook
/billing/      POST /billing/webhook/razorpay
verify-payment [C4, Track B]
[C3, Track B]
    │         │
    └────┬────┘
         ▼
wallet_service.record_credit()      [B3]
  → idempotency_key = "rp:{payment_id}"
  → Exactly one write, regardless of which path arrives first
         │
         ▼
tenant.has_recharged_ever = True    [C3 or C4]
  → Paid models unlocked in model_selector [B2]
         │
         ▼
GET /billing/wallet                 [C5, Track A]
  → Customer sees updated balance
```

### What Flips When GSTIN Arrives

Only one change: set `RAZORPAY_ENABLED=true` in `.env`. No code deploy needed. C2, C3, C4 all check this flag at runtime. The entire payment flow activates immediately.

### Additional Migration Created in Part C

| Migration | What | Down revision |
|-----------|------|---------------|
| `s9p7_reconciliation_reports.py` | `reconciliation_reports` table | s9p6 |

Updated migration chain: `s9d1 → s9p1 → s9p2 → s9p3 → s9p4 → s9p5 → s9p6 → s9p7`

✅ **PART C COMPLETE** — 7 tickets, 4.0 days. Track B tickets are feature-flagged and activate on GSTIN. Track A tickets ship immediately.

---

## PART D — BACKEND EXPORTS & UTILITIES

> **What this part delivers:** Four-format cost export (CSV, PDF, JSON, DOCX) via a single endpoint, and a one-command demo organization seeder for sales calls. All tickets are Track A — no GSTIN required.
>
> **New dependency:** `fpdf2>=2.7.9` for PDF generation (pure Python, no system deps). Add to `requirements.txt`. `python-docx` is already installed.
>
> **Design principle for exports:** One service assembles a single `ExportDataset` object from the DB. Four renderers consume it. Adding a 5th format later (e.g. XLSX) means writing one new renderer — zero DB logic changes.

---

### TICKET D1 — Cost Export Service
**Owner:** Backend
**Effort:** 1.5 days
**Track:** A
**Depends on:** A4 (raw_cost_inr in usage_logs), A2 (wallet_transactions), B1 (markup fields populated)

#### Context

The export must show — per the strategy — every rupee with full transparency: raw AI cost, 15% platform fee, and the total charged, broken down by document, user, model, and day. The service has two responsibilities:
1. **Data assembly** — query `usage_logs` + `wallet_transactions` for the requested date range and build a structured `ExportDataset`
2. **Format rendering** — render the same dataset to CSV, PDF, JSON, or DOCX

#### Files

| File | Type of change |
|------|---------------|
| `backend/requirements.txt` | Add `fpdf2>=2.7.9` |
| `backend/app/services/cost_export_service.py` | **New file** |

#### `requirements.txt` addition

```
fpdf2>=2.7.9
```

#### Service — `cost_export_service.py`

```python
"""
Cost Export Service — Phase 9 (D6)
Assembles billing data and renders to CSV / PDF / JSON / DOCX.

Design: ExportDataset is built once from DB, then passed to
format-specific renderers. Adding a new format = new renderer only.
"""
import csv
import io
import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.logging import get_logger

logger = get_logger("services.cost_export")

MARKUP_PERCENT = 15.0  # Must match cost_service.MARKUP_PERCENT


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExportLineItem:
    """One row in the export — maps to a single usage_log record."""
    date: str                      # ISO date (YYYY-MM-DD)
    document_name: str
    user_email: str
    model_used: str
    feature_type: str
    operation: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    raw_cost_inr: float            # What Google/Anthropic charged us
    markup_inr: float              # Our 15% platform fee
    total_cost_inr: float          # What the customer pays


@dataclass
class WalletEntry:
    """One row in the transaction ledger."""
    date: str
    direction: str                 # "credit" | "debit"
    amount_inr: float
    balance_after_inr: float
    txn_type: str
    notes: Optional[str]


@dataclass
class ExportDataset:
    """
    Complete billing dataset for a tenant over a date range.
    Assembled once, rendered to any format.
    """
    tenant_name: str
    tenant_id: int
    from_date: str
    to_date: str
    generated_at: str

    # Line items (one per usage_log row)
    line_items: list[ExportLineItem] = field(default_factory=list)

    # Wallet ledger
    wallet_entries: list[WalletEntry] = field(default_factory=list)

    # Aggregated summaries (computed from line_items)
    total_raw_inr: float = 0.0
    total_markup_inr: float = 0.0
    total_charged_inr: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Breakdowns (dicts: key → {raw_cost_inr, markup_inr, total_cost_inr})
    by_document: dict = field(default_factory=dict)
    by_user: dict = field(default_factory=dict)
    by_model: dict = field(default_factory=dict)
    by_day: dict = field(default_factory=dict)   # date string → costs


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

class CostExportService:

    def build_dataset(
        self,
        db: Session,
        *,
        tenant_id: int,
        from_date: date,
        to_date: date,
    ) -> ExportDataset:
        """
        Query DB and assemble ExportDataset for the given date range.
        All format renderers call this first.
        """
        from app.models.usage_log import UsageLog
        from app.models.document import Document
        from app.models.user import User
        from app.models.wallet_transaction import WalletTransaction
        from app.models.tenant import Tenant

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_name = tenant.name if tenant else f"Tenant {tenant_id}"

        from_dt = datetime.combine(from_date, datetime.min.time())
        to_dt = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

        # --- Usage log rows ---
        logs = (
            db.query(UsageLog)
            .filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.created_at >= from_dt,
                UsageLog.created_at < to_dt,
            )
            .order_by(UsageLog.created_at.desc())
            .all()
        )

        # Pre-load document names and user emails in bulk
        doc_ids = {log.document_id for log in logs if log.document_id}
        user_ids = {log.user_id for log in logs if log.user_id}

        doc_map = {}
        if doc_ids:
            docs = db.query(Document.id, Document.title).filter(
                Document.id.in_(doc_ids)
            ).all()
            doc_map = {d.id: d.title for d in docs}

        user_map = {}
        if user_ids:
            users = db.query(User.id, User.email).filter(
                User.id.in_(user_ids)
            ).all()
            user_map = {u.id: u.email for u in users}

        # Build line items
        line_items = []
        for log in logs:
            raw = float(getattr(log, "raw_cost_inr", 0) or log.cost_inr or 0)
            markup = float(getattr(log, "markup_inr", 0) or 0)
            total = float(log.cost_inr or 0)

            # Fallback: if A4 columns not yet populated, derive from total
            if raw == 0 and total > 0:
                raw = round(total / 1.15, 4)
                markup = round(total - raw, 4)

            line_items.append(ExportLineItem(
                date=log.created_at.date().isoformat(),
                document_name=doc_map.get(log.document_id, "—") if log.document_id else "—",
                user_email=user_map.get(log.user_id, "system") if log.user_id else "system",
                model_used=log.model_used or "unknown",
                feature_type=log.feature_type or "",
                operation=log.operation or "",
                input_tokens=log.input_tokens or 0,
                output_tokens=log.output_tokens or 0,
                thinking_tokens=int((log.extra_data or {}).get("thinking_tokens", 0)),
                raw_cost_inr=raw,
                markup_inr=markup,
                total_cost_inr=total,
            ))

        # Wallet ledger
        wallet_rows = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.tenant_id == tenant_id,
                WalletTransaction.created_at >= from_dt,
                WalletTransaction.created_at < to_dt,
            )
            .order_by(WalletTransaction.created_at.desc())
            .all()
        )
        wallet_entries = [
            WalletEntry(
                date=w.created_at.date().isoformat(),
                direction=w.direction,
                amount_inr=float(w.amount_inr),
                balance_after_inr=float(w.balance_after_inr),
                txn_type=w.txn_type,
                notes=w.notes,
            )
            for w in wallet_rows
        ]

        # Compute aggregates + breakdowns
        dataset = ExportDataset(
            tenant_name=tenant_name,
            tenant_id=tenant_id,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            generated_at=datetime.now().isoformat(timespec="seconds"),
            line_items=line_items,
            wallet_entries=wallet_entries,
        )
        self._compute_aggregates(dataset)
        return dataset

    def _compute_aggregates(self, dataset: ExportDataset) -> None:
        """Compute totals and breakdowns in-place from line_items."""
        for item in dataset.line_items:
            dataset.total_raw_inr += item.raw_cost_inr
            dataset.total_markup_inr += item.markup_inr
            dataset.total_charged_inr += item.total_cost_inr
            dataset.total_input_tokens += item.input_tokens
            dataset.total_output_tokens += item.output_tokens

            for key, label in [
                ("by_document", item.document_name),
                ("by_user", item.user_email),
                ("by_model", item.model_used),
                ("by_day", item.date),
            ]:
                bucket = getattr(dataset, key)
                if label not in bucket:
                    bucket[label] = {"raw_cost_inr": 0.0, "markup_inr": 0.0, "total_cost_inr": 0.0}
                bucket[label]["raw_cost_inr"] += item.raw_cost_inr
                bucket[label]["markup_inr"] += item.markup_inr
                bucket[label]["total_cost_inr"] += item.total_cost_inr

        # Round all floats to 4 decimal places
        dataset.total_raw_inr = round(dataset.total_raw_inr, 4)
        dataset.total_markup_inr = round(dataset.total_markup_inr, 4)
        dataset.total_charged_inr = round(dataset.total_charged_inr, 4)

    # -----------------------------------------------------------------------
    # FORMAT RENDERERS
    # -----------------------------------------------------------------------

    def render_json(self, dataset: ExportDataset) -> bytes:
        """Render dataset as pretty-printed JSON bytes."""
        data = asdict(dataset)
        return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    def render_csv(self, dataset: ExportDataset) -> bytes:
        """
        Render dataset as multi-sheet CSV.
        Sheets are separated by a blank line + section header row.
        Compatible with Excel / Google Sheets import.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # --- Sheet 1: Summary ---
        writer.writerow(["DokyDoc Cost Export"])
        writer.writerow(["Tenant", dataset.tenant_name])
        writer.writerow(["Period", f"{dataset.from_date} to {dataset.to_date}"])
        writer.writerow(["Generated", dataset.generated_at])
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["Total Raw AI Cost (INR)", f"{dataset.total_raw_inr:.4f}"])
        writer.writerow(["Platform Fee 15% (INR)", f"{dataset.total_markup_inr:.4f}"])
        writer.writerow(["Total Charged (INR)", f"{dataset.total_charged_inr:.4f}"])
        writer.writerow(["Total Input Tokens", dataset.total_input_tokens])
        writer.writerow(["Total Output Tokens", dataset.total_output_tokens])
        writer.writerow([])

        # --- Sheet 2: Line Items ---
        writer.writerow(["LINE ITEMS (per analysis call)"])
        writer.writerow([
            "Date", "Document", "User", "Model", "Feature", "Operation",
            "Input Tokens", "Output Tokens", "Thinking Tokens",
            "Raw Cost INR", "Platform Fee INR", "Total Charged INR"
        ])
        for item in dataset.line_items:
            writer.writerow([
                item.date, item.document_name, item.user_email,
                item.model_used, item.feature_type, item.operation,
                item.input_tokens, item.output_tokens, item.thinking_tokens,
                f"{item.raw_cost_inr:.4f}", f"{item.markup_inr:.4f}",
                f"{item.total_cost_inr:.4f}",
            ])
        writer.writerow([])

        # --- Sheet 3: By Document ---
        writer.writerow(["BY DOCUMENT"])
        writer.writerow(["Document", "Raw Cost INR", "Platform Fee INR", "Total INR"])
        for doc, costs in sorted(dataset.by_document.items(), key=lambda x: -x[1]["total_cost_inr"]):
            writer.writerow([doc, f"{costs['raw_cost_inr']:.4f}",
                             f"{costs['markup_inr']:.4f}", f"{costs['total_cost_inr']:.4f}"])
        writer.writerow([])

        # --- Sheet 4: By User ---
        writer.writerow(["BY USER"])
        writer.writerow(["User Email", "Raw Cost INR", "Platform Fee INR", "Total INR"])
        for user, costs in sorted(dataset.by_user.items(), key=lambda x: -x[1]["total_cost_inr"]):
            writer.writerow([user, f"{costs['raw_cost_inr']:.4f}",
                             f"{costs['markup_inr']:.4f}", f"{costs['total_cost_inr']:.4f}"])
        writer.writerow([])

        # --- Sheet 5: By Model ---
        writer.writerow(["BY MODEL"])
        writer.writerow(["Model", "Raw Cost INR", "Platform Fee INR", "Total INR"])
        for model, costs in sorted(dataset.by_model.items(), key=lambda x: -x[1]["total_cost_inr"]):
            writer.writerow([model, f"{costs['raw_cost_inr']:.4f}",
                             f"{costs['markup_inr']:.4f}", f"{costs['total_cost_inr']:.4f}"])
        writer.writerow([])

        # --- Sheet 6: Wallet Ledger ---
        writer.writerow(["WALLET LEDGER"])
        writer.writerow(["Date", "Direction", "Amount INR", "Balance After INR", "Type", "Notes"])
        for entry in dataset.wallet_entries:
            writer.writerow([
                entry.date, entry.direction, f"{entry.amount_inr:.2f}",
                f"{entry.balance_after_inr:.2f}", entry.txn_type, entry.notes or ""
            ])

        return output.getvalue().encode("utf-8")

    def render_pdf(self, dataset: ExportDataset) -> bytes:
        """
        Render dataset as a PDF using fpdf2.
        Professional layout with header, summary box, and tables.
        """
        from fpdf import FPDF, XPos, YPos

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # --- Header ---
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 10, "DokyDoc — Cost Export Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, f"Tenant: {dataset.tenant_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"Period: {dataset.from_date}  →  {dataset.to_date}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"Generated: {dataset.generated_at}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        # --- Summary box ---
        pdf.set_fill_color(245, 247, 255)
        pdf.set_draw_color(200, 210, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 8, "Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        col_w = 95
        for label, value in [
            ("Raw AI Cost (what Google/Anthropic charged us):", f"INR {dataset.total_raw_inr:.2f}"),
            ("Platform Fee (15% markup):", f"INR {dataset.total_markup_inr:.2f}"),
            ("Total Charged to Wallet:", f"INR {dataset.total_charged_inr:.2f}"),
            ("Total Input Tokens:", f"{dataset.total_input_tokens:,}"),
            ("Total Output Tokens:", f"{dataset.total_output_tokens:,}"),
        ]:
            pdf.cell(col_w, 7, label)
            pdf.cell(col_w, 7, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        def _table_header(headers: list[tuple[str, int]], fill_color=(30, 60, 114)):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(*fill_color)
            pdf.set_text_color(255, 255, 255)
            for text, w in headers:
                pdf.cell(w, 7, text, border=1, fill=True)
            pdf.ln()
            pdf.set_text_color(40, 40, 40)
            pdf.set_font("Helvetica", "", 8)

        def _table_row(values: list[tuple[str, int]], fill=False):
            pdf.set_fill_color(248, 248, 255)
            for text, w in values:
                pdf.cell(w, 6, text, border=1, fill=fill)
            pdf.ln()

        # --- By Document table ---
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 8, "Cost by Document", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _table_header([("Document", 90), ("Raw INR", 30), ("Fee INR", 30), ("Total INR", 30)])
        for doc, costs in sorted(dataset.by_document.items(), key=lambda x: -x[1]["total_cost_inr"])[:20]:
            _table_row([
                (doc[:45], 90),
                (f"{costs['raw_cost_inr']:.2f}", 30),
                (f"{costs['markup_inr']:.2f}", 30),
                (f"{costs['total_cost_inr']:.2f}", 30),
            ])
        pdf.ln(4)

        # --- By Model table ---
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 8, "Cost by AI Model", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _table_header([("Model", 80), ("Raw INR", 35), ("Fee INR", 35), ("Total INR", 30)])
        for model, costs in sorted(dataset.by_model.items(), key=lambda x: -x[1]["total_cost_inr"]):
            _table_row([
                (model, 80),
                (f"{costs['raw_cost_inr']:.2f}", 35),
                (f"{costs['markup_inr']:.2f}", 35),
                (f"{costs['total_cost_inr']:.2f}", 30),
            ])
        pdf.ln(4)

        # --- By User table ---
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 8, "Cost by Team Member", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _table_header([("User", 80), ("Raw INR", 35), ("Fee INR", 35), ("Total INR", 30)])
        for user, costs in sorted(dataset.by_user.items(), key=lambda x: -x[1]["total_cost_inr"]):
            _table_row([
                (user[:40], 80),
                (f"{costs['raw_cost_inr']:.2f}", 35),
                (f"{costs['markup_inr']:.2f}", 35),
                (f"{costs['total_cost_inr']:.2f}", 30),
            ])
        pdf.ln(4)

        # --- Daily trend table ---
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 60, 114)
        pdf.cell(0, 8, "Daily Spend", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _table_header([("Date", 50), ("Raw INR", 45), ("Fee INR", 45), ("Total INR", 40)])
        for day, costs in sorted(dataset.by_day.items()):
            _table_row([
                (day, 50),
                (f"{costs['raw_cost_inr']:.2f}", 45),
                (f"{costs['markup_inr']:.2f}", 45),
                (f"{costs['total_cost_inr']:.2f}", 40),
            ])

        # --- Footer on all pages ---
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, "DokyDoc — Transparent AI cost reporting | support@dokydoc.ai",
                 align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output())

    def render_docx(self, dataset: ExportDataset) -> bytes:
        """
        Render dataset as a DOCX file using python-docx.
        Suitable for pasting into monthly status reports.
        """
        from docx import Document as DocxDocument
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = DocxDocument()

        # Title
        title = doc.add_heading("DokyDoc — Cost Export Report", 0)
        title.runs[0].font.color.rgb = RGBColor(30, 60, 114)

        # Meta
        doc.add_paragraph(f"Tenant: {dataset.tenant_name}")
        doc.add_paragraph(f"Period: {dataset.from_date}  →  {dataset.to_date}")
        doc.add_paragraph(f"Generated: {dataset.generated_at}")
        doc.add_paragraph("")

        # Summary section
        doc.add_heading("Summary", 1)
        summary_data = [
            ("Raw AI Cost (Google/Anthropic)", f"INR {dataset.total_raw_inr:.2f}"),
            ("Platform Fee (15%)", f"INR {dataset.total_markup_inr:.2f}"),
            ("Total Charged", f"INR {dataset.total_charged_inr:.2f}"),
            ("Total Input Tokens", f"{dataset.total_input_tokens:,}"),
            ("Total Output Tokens", f"{dataset.total_output_tokens:,}"),
        ]
        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        tbl.rows[0].cells[0].text = "Metric"
        tbl.rows[0].cells[1].text = "Value"
        for label, val in summary_data:
            row = tbl.add_row()
            row.cells[0].text = label
            row.cells[1].text = val

        doc.add_paragraph("")

        def _add_table(heading: str, headers: list[str], rows: list[list[str]]):
            doc.add_heading(heading, 2)
            if not rows:
                doc.add_paragraph("No data for this period.")
                return
            t = doc.add_table(rows=1, cols=len(headers))
            t.style = "Table Grid"
            for i, h in enumerate(headers):
                t.rows[0].cells[i].text = h
            for row_data in rows:
                r = t.add_row()
                for i, val in enumerate(row_data):
                    r.cells[i].text = val
            doc.add_paragraph("")

        # By Document
        _add_table(
            "Cost by Document",
            ["Document", "Raw INR", "Platform Fee INR", "Total INR"],
            [
                [doc_name[:60], f"{c['raw_cost_inr']:.2f}", f"{c['markup_inr']:.2f}", f"{c['total_cost_inr']:.2f}"]
                for doc_name, c in sorted(dataset.by_document.items(), key=lambda x: -x[1]["total_cost_inr"])[:30]
            ]
        )

        # By User
        _add_table(
            "Cost by Team Member",
            ["User", "Raw INR", "Platform Fee INR", "Total INR"],
            [
                [u, f"{c['raw_cost_inr']:.2f}", f"{c['markup_inr']:.2f}", f"{c['total_cost_inr']:.2f}"]
                for u, c in sorted(dataset.by_user.items(), key=lambda x: -x[1]["total_cost_inr"])
            ]
        )

        # By Model
        _add_table(
            "Cost by AI Model",
            ["Model", "Raw INR", "Platform Fee INR", "Total INR"],
            [
                [m, f"{c['raw_cost_inr']:.2f}", f"{c['markup_inr']:.2f}", f"{c['total_cost_inr']:.2f}"]
                for m, c in sorted(dataset.by_model.items(), key=lambda x: -x[1]["total_cost_inr"])
            ]
        )

        # Wallet Ledger
        _add_table(
            "Wallet Transaction History",
            ["Date", "Direction", "Amount INR", "Balance After", "Type"],
            [
                [e.date, e.direction, f"{e.amount_inr:.2f}", f"{e.balance_after_inr:.2f}", e.txn_type]
                for e in dataset.wallet_entries
            ]
        )

        # Footer paragraph
        doc.add_paragraph("")
        footer = doc.add_paragraph("DokyDoc — Transparent AI cost reporting | support@dokydoc.ai")
        footer.runs[0].font.size = Pt(8)
        footer.runs[0].font.color.rgb = RGBColor(150, 150, 150)

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


# Singleton
cost_export_service = CostExportService()
```

#### Acceptance Criteria

- [ ] `build_dataset(db, tenant_id=1, from_date=X, to_date=Y)` → `ExportDataset` with correct aggregates
- [ ] `total_charged_inr` ≈ `total_raw_inr * 1.15` (within rounding tolerance)
- [ ] `by_document` sums to `total_charged_inr`; `by_user` sums to `total_charged_inr`
- [ ] `render_json(dataset)` → valid JSON bytes, parseable, contains all sections
- [ ] `render_csv(dataset)` → valid UTF-8, six section headers, correct column counts
- [ ] `render_pdf(dataset)` → non-empty bytes, no fpdf2 exception
- [ ] `render_docx(dataset)` → valid DOCX bytes openable by Word / LibreOffice
- [ ] Empty date range (no usage_logs) → all formats render without crash, totals are zero
- [ ] `usage_logs` rows missing `raw_cost_inr` (pre-A4 DB) → fallback derives raw from `cost_inr / 1.15`

---

### TICKET D2 — Billing Export Endpoint
**Owner:** Backend
**Effort:** 0.5 day
**Track:** A
**Depends on:** D1 (cost_export_service)

#### Context

Single endpoint, four formats, one date range selector. The frontend sends `format=csv|pdf|json|docx` and a date range. The endpoint builds the dataset and streams the file back with the correct `Content-Type` and `Content-Disposition` headers so the browser triggers a download automatically.

**Important:** This is a new endpoint added to `billing.py`. It does NOT modify the existing `exports.py` (which handles document/code/ontology exports — a different domain).

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/api/endpoints/billing.py` | Add endpoint |
| `backend/app/schemas/billing.py` | Add date range helpers |

#### Date Range Helpers — `billing.py` additions

```python
# Add near top of billing.py (after imports)
from datetime import date, timedelta
from enum import Enum

class ExportFormat(str, Enum):
    csv  = "csv"
    pdf  = "pdf"
    json = "json"
    docx = "docx"

class DateRangePreset(str, Enum):
    last_7_days   = "last_7_days"
    this_month    = "this_month"
    last_month    = "last_month"
    last_quarter  = "last_quarter"
    custom        = "custom"       # requires from_date + to_date params

def _resolve_date_range(
    preset: DateRangePreset,
    from_date: Optional[date],
    to_date: Optional[date],
) -> tuple[date, date]:
    """Resolve a preset or custom date range. Returns (from_date, to_date) inclusive."""
    today = date.today()

    if preset == DateRangePreset.last_7_days:
        return today - timedelta(days=6), today

    if preset == DateRangePreset.this_month:
        return today.replace(day=1), today

    if preset == DateRangePreset.last_month:
        first_this_month = today.replace(day=1)
        last_last_month  = first_this_month - timedelta(days=1)
        first_last_month = last_last_month.replace(day=1)
        return first_last_month, last_last_month

    if preset == DateRangePreset.last_quarter:
        return today - timedelta(days=89), today

    # custom
    if not from_date or not to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date and to_date are required when preset=custom"
        )
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be ≤ to_date")
    if (to_date - from_date).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days")
    return from_date, to_date
```

#### Endpoint

```python
@router.get("/export")
@limiter.limit("10/minute")
def export_billing_data(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    format: ExportFormat = Query(default=ExportFormat.csv, description="Output format"),
    preset: DateRangePreset = Query(
        default=DateRangePreset.this_month,
        description="Date range preset"
    ),
    from_date: Optional[date] = Query(default=None, description="Start date (required if preset=custom)"),
    to_date: Optional[date] = Query(default=None, description="End date (required if preset=custom)"),
):
    """
    Export billing data in CSV, PDF, JSON, or DOCX format.
    [TRACK A — available immediately]

    Date range presets:
      last_7_days  — rolling 7 days including today
      this_month   — 1st of current month to today
      last_month   — full previous calendar month
      last_quarter — rolling 90 days
      custom       — requires from_date and to_date query params

    All formats contain:
      - Summary totals (raw cost, 15% markup, total charged)
      - Line items (one per AI call)
      - Breakdown by document, user, model, and day
      - Wallet transaction ledger

    Response: file download (Content-Disposition: attachment)
    """
    from app.services.cost_export_service import cost_export_service
    from fastapi.responses import StreamingResponse

    # RBAC: only CXO or Admin can export (billing data is sensitive)
    allowed_roles = {"CXO", "Admin", "admin", "owner"}
    user_roles = set(current_user.roles or [])
    if not (user_roles & allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="Only CXO or Admin roles can export billing data."
        )

    # Resolve date range
    start, end = _resolve_date_range(preset, from_date, to_date)

    logger.info(
        f"Billing export: tenant={tenant_id}, format={format}, "
        f"range={start}→{end}, user={current_user.email}"
    )

    # Build dataset
    dataset = cost_export_service.build_dataset(
        db, tenant_id=tenant_id, from_date=start, to_date=end
    )

    # Render to requested format
    filename_base = f"dokydoc_costs_{start}_{end}"

    if format == ExportFormat.csv:
        content = cost_export_service.render_csv(dataset)
        media_type = "text/csv; charset=utf-8"
        filename = f"{filename_base}.csv"

    elif format == ExportFormat.pdf:
        content = cost_export_service.render_pdf(dataset)
        media_type = "application/pdf"
        filename = f"{filename_base}.pdf"

    elif format == ExportFormat.json:
        content = cost_export_service.render_json(dataset)
        media_type = "application/json; charset=utf-8"
        filename = f"{filename_base}.json"

    elif format == ExportFormat.docx:
        content = cost_export_service.render_docx(dataset)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{filename_base}.docx"

    return StreamingResponse(
        content=io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
            "X-Export-From": start.isoformat(),
            "X-Export-To": end.isoformat(),
            "X-Export-Records": str(len(dataset.line_items)),
        }
    )
```

#### Acceptance Criteria

- [ ] `GET /billing/export?format=csv` → file download, `Content-Type: text/csv`, filename contains date range
- [ ] `GET /billing/export?format=pdf` → file download, `Content-Type: application/pdf`, non-empty bytes
- [ ] `GET /billing/export?format=json` → valid JSON download
- [ ] `GET /billing/export?format=docx` → valid DOCX download
- [ ] `GET /billing/export?preset=custom&from_date=2026-01-01&to_date=2026-03-31` → 90-day range
- [ ] `GET /billing/export?preset=custom` (no dates) → HTTP 422
- [ ] `GET /billing/export?preset=custom&from_date=2026-04-01&to_date=2026-01-01` → HTTP 422 (from > to)
- [ ] `GET /billing/export?preset=custom&from_date=2025-01-01&to_date=2026-06-01` → HTTP 422 (>366 days)
- [ ] Developer role → HTTP 403
- [ ] Rate limit: 11th call/minute → HTTP 429
- [ ] `X-Export-Records` header matches actual line item count
- [ ] Empty result (no usage in range) → valid file with zero totals, not a 500

---

### TICKET D3 — Demo Organization Seeder
**Owner:** Backend
**Effort:** 1.5 days
**Track:** A
**Depends on:** B3 (wallet_service), A1, A2

#### Context

Every enterprise sales call lives or dies in the first 90 seconds. An empty DokyDoc dashboard loses deals. This script creates a polished, pre-populated "Acme Corp (Demo)" organization in one command:

```bash
python -m app.scripts.seed_demo_org --name "Acme Corp" --reset
```

`--reset` wipes and recreates the org cleanly before every call. Without `--reset`, it is additive (safe to run in dev without destroying existing data).

#### What Gets Created

| Item | Count | Detail |
|------|-------|--------|
| Tenant | 1 | "Acme Corp (Demo)", subdomain `acme-demo`, tier `pro` |
| Users | 6 | One per role: CXO, Admin, BA, Developer, PM, Auditor |
| Documents | 5 | PRD, SRS, API Spec, Regulatory Doc, Change Request — pre-analyzed |
| Wallet balance | ₹5,000 | Already loaded, realistic transaction history |
| Wallet transactions | 23 | 3 recharges + 20 analysis deductions over 30 days |
| Usage logs | 20 | Matching the 20 deduction transactions |
| Mismatches | 12 | 3 open critical, 4 open normal, 2 resolved, 2 fixed, 1 escalated |
| Coverage snapshots | 30 | One per day for last 30 days (62% → 84% trend) |

#### Files

| File | Type of change |
|------|---------------|
| `backend/app/scripts/__init__.py` | **New file** (empty, makes it a package) |
| `backend/app/scripts/seed_demo_org.py` | **New file** |

---

#### `seed_demo_org.py` — Part 1: CLI entry point + reset + tenant/users

```python
"""
Demo Organization Seeder — Phase 9

Creates a fully pre-populated demo tenant for sales calls.

Usage:
    python -m app.scripts.seed_demo_org --name "Acme Corp" --reset
    python -m app.scripts.seed_demo_org --name "TechCo"           # additive, no wipe
    python -m app.scripts.seed_demo_org --list                     # list existing demo orgs

Options:
    --name TEXT     Company name (default: "Acme Corp")
    --reset         Wipe existing demo org before seeding (safe for demo prep)
    --list          List all tenants with is_demo=True and exit
    --subdomain     Override auto-generated subdomain (default: {name}-demo)
    --balance       Starting wallet balance in INR (default: 5000)
"""
import argparse
import sys
import os
import random
from datetime import datetime, date, timedelta
from decimal import Decimal

# Bootstrap path so script can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.core.logging import get_logger

logger = get_logger("scripts.seed_demo_org")

# ── Demo data constants ─────────────────────────────────────────────────────

DEMO_PASSWORD = "Demo@DokyDoc2026!"   # Same for all demo users — printed at end

DEMO_USERS = [
    {"name": "Priya Sharma",    "role": "CXO",       "email_prefix": "cxo"},
    {"name": "Arjun Mehta",     "role": "Admin",     "email_prefix": "admin"},
    {"name": "Sneha Reddy",     "role": "BA",        "email_prefix": "ba"},
    {"name": "Rahul Verma",     "role": "Developer", "email_prefix": "dev"},
    {"name": "Kavita Nair",     "role": "PM",        "email_prefix": "pm"},
    {"name": "Deepak Joshi",    "role": "Auditor",   "email_prefix": "auditor"},
]

DEMO_DOCUMENTS = [
    {
        "title": "Loan Origination System — PRD v2.1",
        "document_type": "PRD",
        "description": "Product requirements for the new digital loan origination system covering KYC, credit scoring, and disbursement workflows.",
        "coverage_score": 0.84,
    },
    {
        "title": "Customer Onboarding — SRS v1.4",
        "document_type": "SRS",
        "description": "Software requirements specification for the customer onboarding microservice including video KYC and Aadhaar verification.",
        "coverage_score": 0.71,
    },
    {
        "title": "Payment Gateway Integration — API Spec v3.0",
        "document_type": "API_SPEC",
        "description": "API specification for integrating with Razorpay, including webhook contracts, idempotency requirements, and error codes.",
        "coverage_score": 0.92,
    },
    {
        "title": "RBI Digital Lending Guidelines — Compliance Doc",
        "document_type": "REGULATORY",
        "description": "Analysis of RBI DLG compliance requirements mapped against existing lending platform implementation.",
        "coverage_score": 0.63,
    },
    {
        "title": "Credit Score Module — Change Request #47",
        "document_type": "CHANGE_REQUEST",
        "description": "Change request to update credit scoring algorithm to include bureau score V2 and rental payment history.",
        "coverage_score": 0.78,
    },
]

DEMO_MISMATCH_TEMPLATES = [
    # (severity, status, title, description)
    ("critical", "open",
     "KYC verification timeout not implemented",
     "PRD §3.2 requires a 30-second timeout on video KYC calls with automatic retry. No timeout logic found in kyc_service.py."),
    ("critical", "open",
     "Loan disbursement missing idempotency key",
     "PRD §5.1 mandates idempotency on all disbursement API calls. POST /disburse has no idempotency_key parameter."),
    ("critical", "open",
     "Credit score fallback not handling bureau downtime",
     "SRS §4.3 requires fallback to internal score when bureau API is unavailable. No fallback branch in credit_service.py."),
    ("high", "open",
     "Customer consent timestamp not stored",
     "RBI DLG §7 requires storing timestamp of customer consent for data processing. consent_at column missing from customers table."),
    ("high", "open",
     "Rate limiting absent on OTP endpoint",
     "SRS §2.4 requires max 3 OTP attempts per 10 minutes. POST /auth/otp has no rate limiting."),
    ("high", "open",
     "Loan offer expiry not enforced",
     "PRD §4.5 states offers expire after 72 hours. No expiry check in loan_offer_service.py."),
    ("high", "open",
     "Audit log missing for admin balance adjustments",
     "Compliance doc §12 requires immutable audit trail for all balance changes. admin_adjust_balance() has no audit write."),
    ("medium", "resolved",
     "Missing pagination on /loans endpoint",
     "PRD §6.1 requires paginated results. Fixed in sprint 14 — verified paginated response shape."),
    ("medium", "resolved",
     "Bureau API key stored in plaintext config",
     "SRS §9.2 requires secrets in vault. Fixed — migrated to AWS Secrets Manager in sprint 13."),
    ("low", "fixed",
     "Document title truncated at 100 chars in UI",
     "Change request §2 requires 255 char support. Fixed in frontend PR #234."),
    ("low", "fixed",
     "Currency symbol missing on mobile view",
     "Minor display issue — INR symbol not rendering on iOS Safari. Fixed in hotfix v2.1.3."),
    ("high", "escalated",
     "PAN verification API timeout cascades to 504",
     "PRD §3.4 requires graceful degradation. PAN API timeout propagates as 504 to end users. Escalated to infrastructure team."),
]
```
---

#### `seed_demo_org.py` — Part 2: Seeder functions

```python
# ── Seeder functions ────────────────────────────────────────────────────────

def _wipe_demo_org(db, subdomain: str) -> None:
    """Delete existing demo org and all its data via cascade."""
    from app.models.tenant import Tenant
    existing = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
    if existing:
        logger.info(f"Wiping existing demo org: {existing.name} (id={existing.id})")
        db.delete(existing)   # Cascade deletes users, documents, billing, etc.
        db.commit()
        logger.info("Wipe complete.")


def _create_tenant(db, name: str, subdomain: str) -> object:
    """Create the demo tenant record."""
    from app.models.tenant import Tenant
    from app.models.tenant_billing import TenantBilling

    tenant = Tenant(
        name=f"{name} (Demo)",
        subdomain=subdomain,
        tier="pro",
        billing_type="prepaid",
        settings={
            "industry": "fintech",
            "sub_domain": "lending",
            "is_demo": True,
            "regulatory_context": ["RBI", "PCI-DSS", "Aadhaar Act"],
            "onboarding_complete": True,
        },
        # Phase 9 fields (A1) — set demo org as already recharged
        default_model="gemini-3-flash",
        free_credit_remaining_inr=Decimal("0.00"),   # Exhausted (demo shows paid lane)
        has_recharged_ever=True,
    )
    db.add(tenant)
    db.flush()   # Get tenant.id before creating billing

    billing = TenantBilling(
        tenant_id=tenant.id,
        billing_type="prepaid",
        balance_inr=Decimal("0.00"),   # Will be set by wallet seeding below
        low_balance_threshold=Decimal("100.00"),
        current_month_cost=Decimal("0.00"),
        last_30_days_cost=Decimal("0.00"),
    )
    db.add(billing)
    db.flush()

    logger.info(f"Created demo tenant: {tenant.name} (id={tenant.id})")
    return tenant


def _create_users(db, tenant_id: int, subdomain: str) -> dict:
    """Create 6 demo users, one per role. Returns {role: user} dict."""
    from app.models.user import User

    users = {}
    for u in DEMO_USERS:
        email = f"{u['email_prefix']}@{subdomain}.demo"
        user = User(
            email=email,
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name=u["name"],
            roles=[u["role"]],
            tenant_id=tenant_id,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        users[u["role"]] = user
        logger.info(f"  Created user: {email} ({u['role']})")
    return users


def _create_documents(db, tenant_id: int, users: dict) -> list:
    """Create 5 demo documents with realistic metadata. Returns list of Document objects."""
    from app.models.document import Document

    docs = []
    ba_user = users.get("BA")
    pm_user = users.get("PM")
    uploaders = [ba_user, pm_user, ba_user, pm_user, ba_user]

    for i, doc_data in enumerate(DEMO_DOCUMENTS):
        doc = Document(
            tenant_id=tenant_id,
            title=doc_data["title"],
            document_type=doc_data["document_type"],
            description=doc_data["description"],
            status="analyzed",
            uploaded_by=uploaders[i].id if uploaders[i] else None,
            file_size_kb=random.randint(45, 320),
            page_count=random.randint(8, 42),
            created_at=datetime.now() - timedelta(days=random.randint(3, 28)),
        )
        db.add(doc)
        db.flush()
        docs.append(doc)
        logger.info(f"  Created document: {doc.title[:50]} (id={doc.id})")
    return docs


def _seed_wallet(db, tenant_id: int, users: dict, starting_balance: float) -> None:
    """
    Seed realistic wallet transaction history:
    - 3 Razorpay top-ups (5, 15, and 25 days ago)
    - 20 analysis deductions spread over 30 days
    Final balance ≈ starting_balance (top-ups minus deductions)
    """
    from app.models.wallet_transaction import WalletTransaction
    from app.models.tenant_billing import TenantBilling

    # Deduction amounts for 20 analysis events (realistic spread)
    deduction_amounts = [
        2.35, 4.80, 6.12, 3.47, 8.90, 5.23, 2.91, 11.40, 4.65, 7.33,
        3.18, 9.77, 6.44, 2.88, 14.22, 5.61, 3.95, 8.17, 4.43, 7.89,
    ]
    total_deductions = sum(deduction_amounts)

    # 3 top-ups that sum to starting_balance + total_deductions (so balance ends at starting_balance)
    topup_1 = round(starting_balance * 0.3, 2)
    topup_2 = round(starting_balance * 0.4, 2)
    topup_3 = round(starting_balance + total_deductions - topup_1 - topup_2, 2)
    topup_amounts = [topup_1, topup_2, topup_3]

    running_balance = Decimal("0.00")
    cxo_user = users.get("CXO")

    # Top-up events: 25, 15, 5 days ago
    topup_days_ago = [25, 15, 5]
    for i, (amount, days_ago) in enumerate(zip(topup_amounts, topup_days_ago)):
        running_balance += Decimal(str(amount))
        txn = WalletTransaction(
            tenant_id=tenant_id,
            user_id=cxo_user.id if cxo_user else None,
            direction="credit",
            amount_inr=Decimal(str(amount)),
            balance_after_inr=running_balance,
            txn_type="razorpay_topup",
            idempotency_key=f"demo-topup-{tenant_id}-{i}",
            notes=f"Demo recharge #{i+1}",
            created_at=datetime.now() - timedelta(days=days_ago),
        )
        db.add(txn)

    # Analysis deductions: spread across 30 days
    dev_user = users.get("Developer")
    ba_user = users.get("BA")
    deduction_users = [ba_user, dev_user] * 10
    random.shuffle(deduction_users)

    for i, (amount, user) in enumerate(zip(deduction_amounts, deduction_users)):
        running_balance -= Decimal(str(amount))
        days_offset = random.randint(0, 29)
        txn = WalletTransaction(
            tenant_id=tenant_id,
            user_id=user.id if user else None,
            direction="debit",
            amount_inr=Decimal(str(amount)),
            balance_after_inr=max(running_balance, Decimal("0.00")),
            txn_type="document_analysis",
            idempotency_key=f"demo-deduct-{tenant_id}-{i}",
            notes="Document analysis (demo)",
            created_at=datetime.now() - timedelta(days=days_offset, hours=random.randint(0, 23)),
        )
        db.add(txn)

    # Update billing record to reflect final balance
    billing = db.query(TenantBilling).filter(
        TenantBilling.tenant_id == tenant_id
    ).first()
    if billing:
        billing.balance_inr = Decimal(str(starting_balance))
        billing.last_30_days_cost = Decimal(str(round(total_deductions, 2)))
        billing.current_month_cost = Decimal(str(round(total_deductions * 0.6, 2)))
        db.add(billing)

    logger.info(f"  Seeded {len(topup_amounts)} top-ups + {len(deduction_amounts)} deductions. Final balance: ₹{starting_balance}")
```
---

#### `seed_demo_org.py` — Part 3: Usage logs, mismatches, coverage snapshots, main()

```python
def _seed_usage_logs(db, tenant_id: int, documents: list, users: dict) -> None:
    """Create 20 realistic usage_log rows matching the wallet deductions."""
    from app.models.usage_log import UsageLog

    models_used = ["gemini-3-flash", "gemini-3-flash", "claude-sonnet-4-6", "gemini-3-flash-lite"]
    operations = ["pass_1_composition", "pass_2_segmenting", "pass_3_extraction"]
    dev_user = users.get("Developer")
    ba_user = users.get("BA")
    log_users = [ba_user, dev_user] * 10

    for i in range(20):
        raw_cost = round(random.uniform(1.5, 12.0), 4)
        markup = round(raw_cost * 0.15, 4)
        total = round(raw_cost + markup, 4)
        input_toks = random.randint(3000, 18000)
        output_toks = random.randint(800, 4000)
        thinking_toks = random.randint(500, 6000)

        log = UsageLog(
            tenant_id=tenant_id,
            user_id=log_users[i].id if log_users[i] else None,
            document_id=random.choice(documents).id,
            feature_type="document_analysis",
            operation=random.choice(operations),
            model_used=random.choice(models_used),
            input_tokens=input_toks,
            output_tokens=output_toks,
            cached_tokens=0,
            cost_usd=round(total / 84.0, 6),
            cost_inr=Decimal(str(total)),
            # A4 fields
            raw_cost_inr=Decimal(str(raw_cost)),
            markup_inr=Decimal(str(markup)),
            markup_percent=Decimal("15.00"),
            processing_time_seconds=round(random.uniform(8.0, 45.0), 2),
            extra_data={"thinking_tokens": thinking_toks, "demo": True},
            created_at=datetime.now() - timedelta(days=random.randint(0, 29)),
        )
        db.add(log)
    logger.info("  Seeded 20 usage log entries.")


def _seed_mismatches(db, tenant_id: int, documents: list, users: dict) -> None:
    """Create 12 mismatches across all states to make the demo rich."""
    from app.models.mismatch import Mismatch   # adjust import to actual model path

    dev_user = users.get("Developer")
    ba_user = users.get("BA")

    for i, (severity, status, title, description) in enumerate(DEMO_MISMATCH_TEMPLATES):
        doc = documents[i % len(documents)]
        mismatch = Mismatch(
            tenant_id=tenant_id,
            document_id=doc.id,
            title=title,
            description=description,
            severity=severity,
            status=status,
            detected_by="ai",
            assigned_to=dev_user.id if dev_user else None,
            created_by=ba_user.id if ba_user else None,
            created_at=datetime.now() - timedelta(days=random.randint(1, 20)),
            resolved_at=(
                datetime.now() - timedelta(days=random.randint(0, 5))
                if status in ("resolved", "fixed")
                else None
            ),
        )
        db.add(mismatch)
    logger.info("  Seeded 12 mismatches (3 critical open, 4 high open, 2 resolved, 2 fixed, 1 escalated).")


def _seed_coverage_snapshots(db, tenant_id: int, documents: list) -> None:
    """
    Create 30 daily coverage snapshots to show the 62% → 84% improvement story.
    Each document gets one snapshot per day for the last 30 days.
    """
    from app.models.coverage_snapshot import CoverageSnapshot  # adjust to actual path

    for doc_data, doc in zip(DEMO_DOCUMENTS, documents):
        target_score = doc_data["coverage_score"]
        start_score = max(0.40, target_score - 0.22)   # start 22 points below final

        for day in range(29, -1, -1):
            snap_date = date.today() - timedelta(days=day)
            # Linear progression from start_score to target_score
            progress = (29 - day) / 29
            score = start_score + (target_score - start_score) * progress
            score = round(score, 4)

            atom_count = random.randint(28, 65)
            covered = int(atom_count * score)
            missing = atom_count - covered

            snapshot = CoverageSnapshot(
                tenant_id=tenant_id,
                document_id=doc.id,
                scope="document",
                coverage_score=score,
                atom_count=atom_count,
                atoms_covered=covered,
                atoms_missing=missing,
                mismatch_count=max(0, missing - 2),
                critical_mismatch_count=max(0, int(missing * 0.25)),
                open_mismatch_count=max(0, int(missing * 0.6)),
                resolved_mismatch_count=max(0, missing - int(missing * 0.6)),
                coverage_delta=round(score - (start_score + (target_score - start_score) * max(0, (29 - day - 1)) / 29), 4) if day < 29 else None,
                snapshot_date=snap_date,
                created_at=datetime.combine(snap_date, datetime.min.time()),
            )
            db.add(snapshot)

    logger.info("  Seeded 30-day coverage snapshots (62%→84% trend visible in dashboard).")


def seed(name: str, subdomain: str, reset: bool, balance: float) -> None:
    """Main seeding orchestrator."""
    db = SessionLocal()
    try:
        if reset:
            _wipe_demo_org(db, subdomain)

        # Check for existing (if not resetting)
        from app.models.tenant import Tenant
        existing = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
        if existing and not reset:
            print(f"Demo org '{existing.name}' already exists (subdomain={subdomain}). Use --reset to recreate.")
            return

        print(f"\n🌱 Seeding demo org: '{name} (Demo)' ...")

        tenant = _create_tenant(db, name, subdomain)
        users = _create_users(db, tenant.id, subdomain)
        documents = _create_documents(db, tenant.id, users)
        _seed_wallet(db, tenant.id, users, balance)
        _seed_usage_logs(db, tenant.id, documents, users)

        # Mismatches and coverage snapshots — wrapped in try/except
        # because model paths may differ slightly across branches
        try:
            _seed_mismatches(db, tenant.id, documents, users)
        except Exception as e:
            logger.warning(f"Mismatch seeding skipped (model import error): {e}")

        try:
            _seed_coverage_snapshots(db, tenant.id, documents)
        except Exception as e:
            logger.warning(f"Coverage snapshot seeding skipped: {e}")

        db.commit()

        # Print login credentials
        print(f"\n✅ Demo org created successfully!\n")
        print(f"{'─'*55}")
        print(f"  Tenant:    {tenant.name}")
        print(f"  Subdomain: {subdomain}")
        print(f"  Wallet:    ₹{balance:,.2f}")
        print(f"  Password:  {DEMO_PASSWORD}  (all users)")
        print(f"{'─'*55}")
        for role_info in DEMO_USERS:
            email = f"{role_info['email_prefix']}@{subdomain}.demo"
            print(f"  {role_info['role']:<12} {email}")
        print(f"{'─'*55}\n")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        print(f"\n❌ Seeding failed: {e}")
        sys.exit(1)
    finally:
        db.close()


def list_demo_orgs() -> None:
    """Print all existing demo organizations."""
    db = SessionLocal()
    try:
        from app.models.tenant import Tenant
        demos = db.query(Tenant).filter(
            Tenant.settings["is_demo"].as_boolean() == True
        ).all()
        if not demos:
            print("No demo organizations found.")
            return
        print(f"\n{'─'*55}")
        print(f"  {'Name':<30} {'Subdomain':<20} {'Tier'}")
        print(f"{'─'*55}")
        for t in demos:
            print(f"  {t.name:<30} {t.subdomain:<20} {t.tier}")
        print(f"{'─'*55}\n")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a demo organization for DokyDoc sales calls.")
    parser.add_argument("--name",      default="Acme Corp",   help="Company name")
    parser.add_argument("--subdomain", default=None,          help="Override subdomain (default: {name}-demo)")
    parser.add_argument("--reset",     action="store_true",   help="Wipe and recreate if exists")
    parser.add_argument("--list",      action="store_true",   help="List existing demo orgs and exit")
    parser.add_argument("--balance",   type=float, default=5000.0, help="Starting wallet balance in INR")
    args = parser.parse_args()

    if args.list:
        list_demo_orgs()
        sys.exit(0)

    subdomain = args.subdomain or f"{args.name.lower().replace(' ', '-')}-demo"
    seed(name=args.name, subdomain=subdomain, reset=args.reset, balance=args.balance)
```

#### Acceptance Criteria

- [ ] `python -m app.scripts.seed_demo_org --name "Acme Corp" --reset` completes in < 30 seconds
- [ ] Creates 1 tenant, 6 users, 5 documents, 23 wallet transactions, 20 usage logs
- [ ] Running with `--reset` twice → clean state, no duplicate rows
- [ ] Running without `--reset` when org exists → prints warning, exits 0, no crash
- [ ] `python -m app.scripts.seed_demo_org --list` → shows the demo org in table
- [ ] CXO login `cxo@acme-corp-demo.demo` / `Demo@DokyDoc2026!` → dashboard shows ₹5,000 wallet
- [ ] Coverage trend chart shows upward 62% → 84% movement over 30 days
- [ ] Mismatches page shows 3 critical open + 1 escalated + resolved examples
- [ ] If Mismatch or CoverageSnapshot model import fails → warning printed, rest of seed continues
- [ ] `--balance 2000` → wallet seeded at ₹2,000

---

## Part D Summary

| Ticket | Title | File(s) Changed | New Dependencies | Risk | Estimated LOC |
|--------|-------|-----------------|-----------------|------|---------------|
| D1 | Cost Export Service | `backend/app/services/cost_export_service.py` (new) | `fpdf2>=2.7.9` | Low — pure new service, no existing code touched | ~280 |
| D2 | Billing Export Endpoint | `backend/app/api/endpoints/billing.py` (additive) | — | Low — single new route, no existing route modified | ~85 |
| D3 | Demo Org Seeder | `backend/app/scripts/__init__.py` (new), `backend/app/scripts/seed_demo_org.py` (new) | — | Low — script only; never runs in production automatically | ~320 |

### Part D Dependency Graph

```
D1 (CostExportService)
  └─ D2 (Export Endpoint) depends on D1 being importable
  
D3 (Demo Seeder) — independent, depends only on A1 models being
                   migrated (Alembic) and B3 WalletService present
```

### Part D Execution Order

1. Add `fpdf2>=2.7.9` to `requirements.txt` (or `pyproject.toml`)
2. Implement **D1** — `cost_export_service.py`
3. Implement **D2** — export endpoint in `billing.py`
4. Implement **D3** — `seed_demo_org.py` + `scripts/__init__.py`
5. Run seeder locally: `python -m app.scripts.seed_demo_org --name "Acme Corp" --reset`
6. Manually verify export endpoint with `curl -H "Authorization: Bearer <cxo_token>" "/billing/export?format=csv&preset=last_7_days"`

### Part D: What Ships vs What Waits

| Item | Ships in Track A (now) | Notes |
|------|------------------------|-------|
| Cost export CSV/PDF/JSON/DOCX | Yes — works from usage_logs | No payment data until C tickets ship |
| Export endpoint RBAC | Yes | CXO / Admin roles only |
| Demo seeder | Yes — dev/staging only | Never in production cronjobs |
| Wallet transaction section in export | After B3 ships | WalletTransaction table must exist |

---


---

# Part E — Frontend (Billing UI)

## Overview

Part E wires the backend billing APIs into the React frontend. Every component
is **additive** — no existing page is removed or broken. Track B components
(recharge modal, model selector) render behind the `RAZORPAY_ENABLED` flag
propagated via a new `/billing/config` endpoint (shipped in C1). The free credit
banner and low-balance alert are **always on** (Track A).

### Components in this Part

| Ticket | Component | Track | Blocking Ticket |
|--------|-----------|-------|----------------|
| E1 | `useBilling` hook + BillingContext | A | B3 wallet endpoint |
| E2 | Free Credit Welcome Banner | A | E1 |
| E3 | Low Balance Alert | A | E1 |
| E4 | Model Selector Dropdown | B | E1 + B2 |
| E5 | Cost Preview Modal (pre-analysis) | B | E1 + B2 |
| E6 | Post-Analysis Cost Receipt Drawer | A | E1 |
| E7 | Recharge Modal (preset + custom) | B | C2 + C3 |
| E8 | Cost Export UI | A | D2 |

---

## E1 — `useBilling` Hook + BillingContext

**File:** `frontend/src/contexts/BillingContext.tsx` (new)
**File:** `frontend/src/hooks/useBilling.ts` (new)
**File:** `frontend/src/types/billing.ts` (new)

### Why

Multiple components need real-time wallet state (balance, free credit,
`has_recharged_ever`, `razorpay_enabled` flag). A shared context avoids
repeated `useQuery` calls and keeps derived state (low balance threshold,
free-lane active) computed once.

### Types (`billing.ts`)

```typescript
// frontend/src/types/billing.ts

export interface WalletState {
  balance_inr: number;            // paid wallet in INR (float)
  free_credit_remaining_inr: number; // free pool remaining
  free_credit_total_inr: number;  // original free grant (display only)
  has_recharged_ever: boolean;
  razorpay_enabled: boolean;      // from /billing/config
  currency: "INR";
}

export interface TransactionRow {
  id: string;
  created_at: string;             // ISO-8601
  type: "credit" | "debit";
  amount_inr: number;
  description: string;
  balance_after_inr: number;
  metadata: Record<string, unknown>;
}

export interface CostBreakdownDisplay {
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  raw_cost_inr: number;
  markup_inr: number;
  total_inr: number;
  markup_percent: number;
  pool_used: "free" | "paid";
}

export type ExportFormat = "csv" | "pdf" | "json" | "docx";
export type DatePreset =
  | "last_7_days"
  | "this_month"
  | "last_month"
  | "last_quarter"
  | "custom";
```

### BillingContext

```typescript
// frontend/src/contexts/BillingContext.tsx
import React, {
  createContext, useCallback, useContext, useEffect, useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { billingApi } from "@/api/billingApi";
import type { WalletState } from "@/types/billing";

interface BillingContextValue {
  wallet: WalletState | null;
  isLoading: boolean;
  isLowBalance: boolean;       // balance_inr < LOW_BALANCE_THRESHOLD_INR
  isFreeLaneActive: boolean;   // free_credit_remaining_inr > 0
  refetch: () => void;
}

const LOW_BALANCE_THRESHOLD_INR = 50;

const BillingContext = createContext<BillingContextValue | null>(null);

export function BillingProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const { data: wallet, isLoading } = useQuery({
    queryKey: ["billing", "wallet"],
    queryFn: billingApi.getWallet,
    staleTime: 30_000,          // re-fetch every 30s
    refetchInterval: 60_000,    // background poll every 60s
  });

  const isLowBalance =
    !isLoading &&
    wallet !== null &&
    wallet !== undefined &&
    wallet.free_credit_remaining_inr <= 0 &&
    wallet.balance_inr < LOW_BALANCE_THRESHOLD_INR;

  const isFreeLaneActive =
    wallet !== null &&
    wallet !== undefined &&
    wallet.free_credit_remaining_inr > 0;

  const refetch = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["billing", "wallet"] });
  }, [queryClient]);

  return (
    <BillingContext.Provider
      value={{ wallet, isLoading, isLowBalance, isFreeLaneActive, refetch }}
    >
      {children}
    </BillingContext.Provider>
  );
}

export function useBillingContext(): BillingContextValue {
  const ctx = useContext(BillingContext);
  if (!ctx) {
    throw new Error("useBillingContext must be used inside <BillingProvider>");
  }
  return ctx;
}
```

### API Layer (`billingApi.ts`)

```typescript
// frontend/src/api/billingApi.ts  (additive — new file)
import { apiClient } from "@/api/client";   // existing axios/fetch wrapper
import type { WalletState, TransactionRow } from "@/types/billing";

export const billingApi = {
  getWallet: async (): Promise<WalletState> => {
    const { data } = await apiClient.get("/billing/wallet");
    return data;
  },

  getTransactions: async (params?: {
    page?: number;
    page_size?: number;
  }): Promise<{ items: TransactionRow[]; total: number }> => {
    const { data } = await apiClient.get("/billing/wallet/transactions", {
      params,
    });
    return data;
  },

  createOrder: async (amount_inr: number) => {
    const { data } = await apiClient.post("/billing/create-order", {
      amount_inr,
    });
    return data; // { order_id, amount_paise, currency, key_id }
  },

  verifyPayment: async (payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }) => {
    const { data } = await apiClient.post("/billing/verify-payment", payload);
    return data;
  },

  exportCosts: async (params: {
    format: string;
    preset?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> => {
    const response = await apiClient.get("/billing/export", {
      params,
      responseType: "blob",
    });
    return response.data;
  },
};
```

### Integration

Add `<BillingProvider>` in `frontend/src/App.tsx` (or layout root) wrapping
the authenticated routes tree:

```typescript
// In App.tsx — additive change only
import { BillingProvider } from "@/contexts/BillingContext";

// Inside the authenticated route wrapper:
<BillingProvider>
  {/* existing authenticated children */}
</BillingProvider>
```

### Acceptance Criteria

- [ ] `useBillingContext()` outside `<BillingProvider>` → throws descriptive error
- [ ] `wallet` is `null` while loading, populated after first fetch completes
- [ ] `isLowBalance` is `true` when `balance_inr < 50` AND `free_credit_remaining_inr === 0`
- [ ] `isFreeLaneActive` is `true` when `free_credit_remaining_inr > 0`
- [ ] Wallet refetches every 60 seconds in background without page reload
- [ ] `refetch()` invalidates React Query cache and triggers immediate re-fetch
- [ ] `billingApi.exportCosts` returns a `Blob` (not JSON) for file download

---

## E2 — Free Credit Welcome Banner

**File:** `frontend/src/components/billing/FreeCreditBanner.tsx` (new)
**File:** `frontend/src/components/billing/index.ts` (new barrel)

### Purpose

Show a dismissible banner to first-time users who still have free credit
remaining. Banner explains the free pool, which model is available, and
provides a CTA to upgrade (recharge).

```typescript
// frontend/src/components/billing/FreeCreditBanner.tsx
import { useState } from "react";
import { useBillingContext } from "@/contexts/BillingContext";

const DISMISS_KEY = "dokydoc_free_credit_banner_dismissed";

export function FreeCreditBanner() {
  const { wallet, isFreeLaneActive } = useBillingContext();
  const [dismissed, setDismissed] = useState<boolean>(() => {
    return localStorage.getItem(DISMISS_KEY) === "1";
  });

  // Only show if: free credit remains AND user hasn't recharged AND not dismissed
  if (!wallet || !isFreeLaneActive || wallet.has_recharged_ever || dismissed) {
    return null;
  }

  const pctUsed = wallet.free_credit_total_inr > 0
    ? Math.round(
        ((wallet.free_credit_total_inr - wallet.free_credit_remaining_inr) /
          wallet.free_credit_total_inr) * 100
      )
    : 0;

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, "1");
    setDismissed(true);
  };

  return (
    <div
      role="alert"
      className="relative flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900"
    >
      {/* Icon */}
      <span className="mt-0.5 shrink-0 text-blue-500">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm1 14h-2v-2h2v2zm0-4h-2V7h2v5z" />
        </svg>
      </span>

      <div className="flex-1">
        <p className="font-semibold">
          You have ₹{wallet.free_credit_remaining_inr.toFixed(2)} free credit
          remaining
        </p>
        <p className="mt-0.5 text-blue-700">
          Free analyses use <strong>Gemini Flash Lite</strong> — our fastest
          model. Recharge to unlock all 4 models and keep working when credit
          runs out.
        </p>
        {/* Progress bar */}
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
          <div
            className="h-full rounded-full bg-blue-500 transition-all"
            style={{ width: `${pctUsed}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-blue-600">
          {pctUsed}% used · ₹{wallet.free_credit_remaining_inr.toFixed(2)} of
          ₹{wallet.free_credit_total_inr.toFixed(2)} remaining
        </p>
      </div>

      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="absolute right-3 top-3 rounded p-0.5 hover:bg-blue-100"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>
    </div>
  );
}
```

### Placement

Mount on the **Dashboard** page header (just below the top nav, above the
main content grid). No other pages need it.

```typescript
// frontend/src/pages/Dashboard.tsx  — additive import + mount
import { FreeCreditBanner } from "@/components/billing";

// Inside Dashboard JSX, as first child of main content wrapper:
<FreeCreditBanner />
```

### Acceptance Criteria

- [ ] Banner renders when `free_credit_remaining_inr > 0` AND `has_recharged_ever === false`
- [ ] Banner does NOT render when user has recharged at least once
- [ ] Banner does NOT render when free credit exhausted
- [ ] Progress bar reflects correct percentage used
- [ ] Dismiss persists across page reloads (localStorage)
- [ ] Banner does NOT re-appear after dismiss, even after page refresh
- [ ] `role="alert"` present for screen reader accessibility

---

## E3 — Low Balance Alert

**File:** `frontend/src/components/billing/LowBalanceAlert.tsx` (new)

### Purpose

Sticky alert shown when paid wallet drops below ₹50 and free credit is
exhausted. Guides the user to recharge before analyses start failing.

```typescript
// frontend/src/components/billing/LowBalanceAlert.tsx
import { useBillingContext } from "@/contexts/BillingContext";

interface LowBalanceAlertProps {
  onRechargeClick?: () => void; // callback to open RechargeModal (E7)
}

export function LowBalanceAlert({ onRechargeClick }: LowBalanceAlertProps) {
  const { isLowBalance, wallet } = useBillingContext();

  if (!isLowBalance || !wallet) return null;

  const isCritical = wallet.balance_inr < 10; // less than ₹10 — analyses will fail soon

  return (
    <div
      role="alert"
      className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-sm ${
        isCritical
          ? "border-red-300 bg-red-50 text-red-900"
          : "border-yellow-300 bg-yellow-50 text-yellow-900"
      }`}
    >
      <span className={isCritical ? "text-red-500" : "text-yellow-500"}>
        {isCritical ? (
          // Warning triangle (critical)
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 20h20L12 2zm0 13h-1v-4h2v4h-1zm0 3a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
          </svg>
        ) : (
          // Info circle (warning)
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm1 14h-2v-2h2v2zm0-4h-2V7h2v5z" />
          </svg>
        )}
      </span>

      <div className="flex-1">
        <p className="font-semibold">
          {isCritical
            ? "Wallet critically low — analyses may fail"
            : "Low wallet balance"}
        </p>
        <p className="mt-0.5 opacity-80">
          Current balance: <strong>₹{wallet.balance_inr.toFixed(2)}</strong>.
          {isCritical
            ? " Add funds immediately to continue."
            : " Add funds to avoid service interruption."}
        </p>
      </div>

      {onRechargeClick && (
        <button
          onClick={onRechargeClick}
          className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
            isCritical
              ? "bg-red-600 text-white hover:bg-red-700"
              : "bg-yellow-500 text-white hover:bg-yellow-600"
          }`}
        >
          Add Funds
        </button>
      )}
    </div>
  );
}
```

### Placement

Mount on the **Dashboard** page (below `FreeCreditBanner`) and on the
**Billing Settings** page. Pass `onRechargeClick` to open `RechargeModal`
(implemented in E7).

### Acceptance Criteria

- [ ] Alert renders when `balance_inr < 50` AND `free_credit_remaining_inr === 0`
- [ ] Shows yellow variant when `10 ≤ balance_inr < 50`
- [ ] Shows red (critical) variant when `balance_inr < 10`
- [ ] "Add Funds" button calls `onRechargeClick` prop if provided
- [ ] Alert is hidden when balance is healthy or free credit still available
- [ ] `role="alert"` for accessibility

---

## E4 — Model Selector Dropdown

**File:** `frontend/src/components/billing/ModelSelector.tsx` (new)
**Track:** B — only visible when `wallet.razorpay_enabled === true` OR
             `wallet.has_recharged_ever === true`

### Purpose

Lets paid users choose which model to use before running an analysis. Free
users are locked to Gemini Flash Lite and see the selector in a disabled
"locked" state explaining why.

### Model Registry (mirrors backend `PRICING_REGISTRY`)

```typescript
// frontend/src/constants/models.ts  (new)
export interface ModelMeta {
  id: string;
  display_name: string;
  provider: "google" | "anthropic";
  tier: "free" | "paid";
  context_window: number;
  description: string;
  est_cost_per_page_inr: number; // rough guide shown to user
}

export const MODEL_REGISTRY: ModelMeta[] = [
  {
    id: "gemini-3-flash-lite",
    display_name: "Gemini Flash Lite",
    provider: "google",
    tier: "free",
    context_window: 128_000,
    description: "Fast & free — good for routine checks",
    est_cost_per_page_inr: 0.0,
  },
  {
    id: "gemini-2.5-flash",
    display_name: "Gemini 2.5 Flash",
    provider: "google",
    tier: "paid",
    context_window: 1_000_000,
    description: "Balanced speed & depth",
    est_cost_per_page_inr: 0.05,
  },
  {
    id: "gemini-2.5-pro",
    display_name: "Gemini 2.5 Pro",
    provider: "google",
    tier: "paid",
    context_window: 2_000_000,
    description: "Deep analysis, very large docs",
    est_cost_per_page_inr: 0.22,
  },
  {
    id: "claude-3-7-sonnet",
    display_name: "Claude 3.7 Sonnet",
    provider: "anthropic",
    tier: "paid",
    context_window: 200_000,
    description: "Best for compliance & legal language",
    est_cost_per_page_inr: 0.18,
  },
];

export const FREE_MODEL_ID = "gemini-3-flash-lite";
```

### Component

```typescript
// frontend/src/components/billing/ModelSelector.tsx
import { useBillingContext } from "@/contexts/BillingContext";
import { MODEL_REGISTRY, FREE_MODEL_ID } from "@/constants/models";
import type { ModelMeta } from "@/constants/models";

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelSelector({ value, onChange, disabled }: ModelSelectorProps) {
  const { isFreeLaneActive, wallet } = useBillingContext();

  // Free-lane users are locked to the free model
  const isLocked = isFreeLaneActive && !wallet?.has_recharged_ever;

  if (isLocked) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500">
        <span className="text-gray-400">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1a5 5 0 0 0-5 5v3H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V11a2 2 0 0 0-2-2h-2V6a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V6a3 3 0 0 1 3-3zm0 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4z" />
          </svg>
        </span>
        <span>Gemini Flash Lite (free tier)</span>
        <span className="ml-auto text-xs text-blue-500 cursor-pointer hover:underline">
          Recharge to unlock all models
        </span>
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full appearance-none rounded-md border border-gray-300 bg-white px-3 py-2 pr-8 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {MODEL_REGISTRY.filter((m) => m.tier === "paid").map((model) => (
          <option key={model.id} value={model.id}>
            {model.display_name} — ~₹{model.est_cost_per_page_inr.toFixed(2)}/page
          </option>
        ))}
      </select>
      {/* Chevron */}
      <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-gray-400">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 10l5 5 5-5z" />
        </svg>
      </span>

      {/* Model description tooltip area */}
      {value && (
        <p className="mt-1 text-xs text-gray-500">
          {MODEL_REGISTRY.find((m) => m.id === value)?.description}
        </p>
      )}
    </div>
  );
}
```

### Integration

The `ModelSelector` is embedded in the **document analysis form** (wherever
the user triggers an analysis). Pass the selected model ID via the analysis
API call as a `model_id` query param or request body field.

```typescript
// In analysis form component (existing):
const [selectedModel, setSelectedModel] = useState(FREE_MODEL_ID);

// In form JSX (additive):
<div className="mb-4">
  <label className="mb-1 block text-sm font-medium text-gray-700">
    AI Model
  </label>
  <ModelSelector value={selectedModel} onChange={setSelectedModel} />
</div>
```

### Acceptance Criteria

- [ ] Free-lane users see locked state with padlock icon and "Recharge" CTA
- [ ] Paid users see dropdown with 3 paid models and estimated cost/page
- [ ] Selecting a model updates the parent form state via `onChange`
- [ ] `disabled` prop greys out and blocks interaction during submission
- [ ] Model description renders below the select as hint text
- [ ] Locked state does NOT render a `<select>` (no DOM element for screen readers to tab to)

---

## E5 — Cost Preview Modal (Pre-Analysis)

**File:** `frontend/src/components/billing/CostPreviewModal.tsx` (new)
**Track:** B — only shown when user is on paid lane

### Purpose

Before a costly analysis runs, show a modal with estimated cost, current
balance, and balance after deduction. Gives users sticker shock protection
and a chance to abort or switch to a cheaper model.

```typescript
// frontend/src/components/billing/CostPreviewModal.tsx
import { useBillingContext } from "@/contexts/BillingContext";
import { MODEL_REGISTRY } from "@/constants/models";

interface CostPreviewModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onModelChange: (modelId: string) => void;
  modelId: string;
  estimatedPages: number;   // caller passes doc page count
}

export function CostPreviewModal({
  isOpen, onConfirm, onCancel, onModelChange, modelId, estimatedPages,
}: CostPreviewModalProps) {
  const { wallet } = useBillingContext();

  if (!isOpen || !wallet) return null;

  const model = MODEL_REGISTRY.find((m) => m.id === modelId);
  const estCost = model ? model.est_cost_per_page_inr * estimatedPages : 0;
  const balanceAfter = wallet.balance_inr - estCost;
  const canAfford = balanceAfter >= 0 || wallet.free_credit_remaining_inr > 0;

  return (
    // Backdrop
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900">
          Estimated Analysis Cost
        </h2>

        <div className="mt-4 space-y-3">
          {/* Model row */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Model</span>
            <span className="font-medium">{model?.display_name ?? modelId}</span>
          </div>

          {/* Pages row */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Document pages</span>
            <span className="font-medium">{estimatedPages}</span>
          </div>

          {/* Estimated cost */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Estimated cost</span>
            <span className="font-semibold text-gray-900">
              ~₹{estCost.toFixed(2)}
            </span>
          </div>

          <hr className="border-gray-100" />

          {/* Current balance */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Current wallet</span>
            <span>₹{wallet.balance_inr.toFixed(2)}</span>
          </div>

          {/* Balance after */}
          <div className="flex items-center justify-between text-sm font-semibold">
            <span className="text-gray-700">Balance after analysis</span>
            <span className={balanceAfter < 0 ? "text-red-600" : "text-green-700"}>
              {balanceAfter < 0
                ? `−₹${Math.abs(balanceAfter).toFixed(2)} (insufficient)`
                : `₹${balanceAfter.toFixed(2)}`}
            </span>
          </div>
        </div>

        {/* Insufficient balance warning */}
        {!canAfford && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
            Insufficient balance. Please add funds or choose a cheaper model.
          </p>
        )}

        {/* Switch model hint */}
        <p className="mt-3 text-xs text-gray-400">
          Actual cost may vary ±20% based on document token density.
          Includes 15% service markup.
        </p>

        {/* Actions */}
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!canAfford}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Confirm & Analyse
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Acceptance Criteria

- [ ] Modal opens when user clicks "Analyse" and is on paid lane
- [ ] Shows correct model name, page count, estimated cost
- [ ] "Balance after" shown in green if positive, red if negative
- [ ] Confirm button disabled when `canAfford === false`
- [ ] Disclaimer "±20% ... 15% service markup" always visible
- [ ] `onCancel` closes modal without triggering analysis
- [ ] `onConfirm` closes modal and triggers the analysis API call

---

## E6 — Post-Analysis Cost Receipt Drawer

**File:** `frontend/src/components/billing/CostReceiptDrawer.tsx` (new)

### Purpose

After an analysis completes, slide in a drawer from the right showing the
exact cost breakdown: tokens used, raw cost, markup, total charged, and
which pool was debited (free / paid).

```typescript
// frontend/src/components/billing/CostReceiptDrawer.tsx
import { useBillingContext } from "@/contexts/BillingContext";
import type { CostBreakdownDisplay } from "@/types/billing";

interface CostReceiptDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  breakdown: CostBreakdownDisplay | null;
}

export function CostReceiptDrawer({
  isOpen, onClose, breakdown,
}: CostReceiptDrawerProps) {
  const { refetch } = useBillingContext();

  // Refresh wallet after analysis so header balance updates
  if (isOpen && breakdown) {
    refetch();
  }

  return (
    // Slide-in overlay
    <div
      className={`fixed inset-y-0 right-0 z-50 flex flex-col w-80 bg-white shadow-2xl transition-transform duration-300 ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
      aria-hidden={!isOpen}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <h3 className="font-semibold text-gray-900">Analysis Receipt</h3>
        <button onClick={onClose} aria-label="Close receipt" className="text-gray-400 hover:text-gray-600">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {!breakdown ? (
          <p className="text-sm text-gray-400">No receipt data.</p>
        ) : (
          <>
            {/* Pool badge */}
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  breakdown.pool_used === "free"
                    ? "bg-green-100 text-green-700"
                    : "bg-blue-100 text-blue-700"
                }`}
              >
                {breakdown.pool_used === "free" ? "Free credit" : "Paid wallet"}
              </span>
              <span className="text-xs text-gray-400">{breakdown.model_id}</span>
            </div>

            {/* Token counts */}
            <div className="rounded-lg bg-gray-50 p-3 text-sm space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-500">Input tokens</span>
                <span>{breakdown.input_tokens.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Output tokens</span>
                <span>{breakdown.output_tokens.toLocaleString()}</span>
              </div>
            </div>

            {/* Cost breakdown */}
            <div className="text-sm space-y-1.5">
              <div className="flex justify-between">
                <span className="text-gray-500">Raw API cost</span>
                <span>₹{breakdown.raw_cost_inr.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">
                  Service markup ({breakdown.markup_percent}%)
                </span>
                <span>₹{breakdown.markup_inr.toFixed(4)}</span>
              </div>
              <hr className="border-gray-100" />
              <div className="flex justify-between font-semibold">
                <span>Total charged</span>
                <span>₹{breakdown.total_inr.toFixed(4)}</span>
              </div>
            </div>

            {/* Transparency note */}
            <p className="text-xs text-gray-400">
              DokyDoc adds a 15% markup to cover infrastructure, support, and
              platform costs. This is always shown transparently.
            </p>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-100 px-5 py-3">
        <button
          onClick={onClose}
          className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          Done
        </button>
      </div>
    </div>
  );
}
```

### Integration

In the analysis page, after the API returns:

```typescript
const [receipt, setReceipt] = useState<CostBreakdownDisplay | null>(null);
const [receiptOpen, setReceiptOpen] = useState(false);

const handleAnalysisComplete = (apiResponse: AnalysisResponse) => {
  if (apiResponse.cost_breakdown) {
    setReceipt(apiResponse.cost_breakdown);
    setReceiptOpen(true);
  }
};
```

The backend analysis endpoints (updated in B4) must include a
`cost_breakdown` field in their response matching `CostBreakdownDisplay`.

### Acceptance Criteria

- [ ] Drawer slides in from the right after successful analysis
- [ ] Shows "Free credit" badge (green) or "Paid wallet" badge (blue)
- [ ] Input + output token counts displayed with thousands separator
- [ ] Raw cost, markup, and total shown to 4 decimal places
- [ ] Wallet balance in header/sidebar updates after receipt opens
- [ ] `onClose` slides drawer back out
- [ ] Drawer accessible via `aria-hidden` toggle
- [ ] "Done" button closes the drawer

---

## E7 — Recharge Modal (Preset + Custom)

**File:** `frontend/src/components/billing/RechargeModal.tsx` (new)
**Track:** B — requires `wallet.razorpay_enabled === true`

### Purpose

Allows users to top up their wallet using Razorpay. Presents 6 preset amounts
(₹100 / ₹200 / ₹500 / ₹1,000 / ₹2,500 / ₹5,000) and a custom input.
Handles the full Razorpay checkout → verify flow client-side.

### Razorpay Script Loader

```typescript
// frontend/src/utils/loadRazorpay.ts  (new)
export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if ((window as any).Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}
```

### Component

```typescript
// frontend/src/components/billing/RechargeModal.tsx
import { useState } from "react";
import { useBillingContext } from "@/contexts/BillingContext";
import { billingApi } from "@/api/billingApi";
import { loadRazorpayScript } from "@/utils/loadRazorpay";

const PRESETS = [100, 200, 500, 1_000, 2_500, 5_000]; // INR

interface RechargeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (amountInr: number) => void;
}

type RechargeState = "idle" | "creating_order" | "checkout" | "verifying" | "success" | "error";

export function RechargeModal({ isOpen, onClose, onSuccess }: RechargeModalProps) {
  const { wallet, refetch } = useBillingContext();
  const [selected, setSelected] = useState<number | null>(500);
  const [customValue, setCustomValue] = useState("");
  const [state, setState] = useState<RechargeState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  if (!isOpen) return null;

  // Track B gate: if razorpay not enabled, show maintenance message
  if (!wallet?.razorpay_enabled) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl text-center">
          <p className="text-gray-600 text-sm">
            Online recharge is temporarily unavailable. Please contact{" "}
            <a href="mailto:billing@dokydoc.com" className="text-blue-600 underline">
              billing@dokydoc.com
            </a>
            .
          </p>
          <button onClick={onClose} className="mt-4 text-sm text-gray-400 hover:text-gray-600">
            Close
          </button>
        </div>
      </div>
    );
  }

  const getAmount = (): number | null => {
    if (selected !== null) return selected;
    const v = parseFloat(customValue);
    return !isNaN(v) && v >= 100 ? v : null;
  };

  const handleRecharge = async () => {
    const amount = getAmount();
    if (!amount) {
      setErrorMsg("Minimum recharge amount is ₹100.");
      return;
    }
    setErrorMsg("");

    // 1. Load Razorpay SDK
    setState("creating_order");
    const loaded = await loadRazorpayScript();
    if (!loaded) {
      setState("error");
      setErrorMsg("Could not load payment gateway. Check your internet connection.");
      return;
    }

    // 2. Create Razorpay order on backend
    let order;
    try {
      order = await billingApi.createOrder(amount);
    } catch (err: any) {
      setState("error");
      setErrorMsg(err?.response?.data?.detail ?? "Failed to create order. Try again.");
      return;
    }

    // 3. Open Razorpay checkout
    setState("checkout");
    const rzp = new (window as any).Razorpay({
      key: order.key_id,
      amount: order.amount_paise,
      currency: "INR",
      order_id: order.order_id,
      name: "DokyDoc",
      description: `Wallet top-up ₹${amount}`,
      theme: { color: "#2563EB" },

      handler: async (response: {
        razorpay_order_id: string;
        razorpay_payment_id: string;
        razorpay_signature: string;
      }) => {
        // 4. Verify payment on backend
        setState("verifying");
        try {
          await billingApi.verifyPayment({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          });
          setState("success");
          refetch(); // update wallet balance in context
          onSuccess?.(amount);
        } catch (err: any) {
          setState("error");
          setErrorMsg(
            err?.response?.data?.detail ?? "Payment verification failed. Contact support."
          );
        }
      },

      modal: {
        ondismiss: () => {
          // User closed checkout without paying
          if (state === "checkout") setState("idle");
        },
      },
    });

    rzp.open();
  };

  const handleClose = () => {
    setState("idle");
    setErrorMsg("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Add Wallet Funds</h2>
          <button onClick={handleClose} aria-label="Close" className="text-gray-400 hover:text-gray-600">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {state === "success" ? (
          <div className="text-center py-6">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <p className="text-lg font-semibold text-gray-900">Payment Successful!</p>
            <p className="mt-1 text-sm text-gray-500">
              ₹{getAmount()?.toFixed(2)} has been added to your wallet.
            </p>
            <button
              onClick={handleClose}
              className="mt-5 rounded-md bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            {/* Current balance */}
            {wallet && (
              <p className="mb-4 text-sm text-gray-500">
                Current balance:{" "}
                <span className="font-semibold text-gray-900">
                  ₹{wallet.balance_inr.toFixed(2)}
                </span>
              </p>
            )}

            {/* Presets grid */}
            <div className="grid grid-cols-3 gap-2 mb-4">
              {PRESETS.map((amount) => (
                <button
                  key={amount}
                  onClick={() => { setSelected(amount); setCustomValue(""); }}
                  className={`rounded-lg border py-2.5 text-sm font-semibold transition-colors ${
                    selected === amount
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-gray-200 text-gray-700 hover:border-blue-300 hover:bg-blue-50"
                  }`}
                >
                  ₹{amount.toLocaleString("en-IN")}
                </button>
              ))}
            </div>

            {/* Custom amount */}
            <div className="mb-4">
              <label className="mb-1 block text-xs text-gray-500">
                Or enter custom amount (min ₹100)
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 text-sm">₹</span>
                <input
                  type="number"
                  min={100}
                  step={1}
                  value={customValue}
                  onChange={(e) => { setCustomValue(e.target.value); setSelected(null); }}
                  placeholder="500"
                  className="w-full rounded-md border border-gray-300 py-2 pl-7 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Error */}
            {errorMsg && (
              <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                {errorMsg}
              </p>
            )}

            {/* GST note */}
            <p className="mb-4 text-xs text-gray-400">
              Payments processed via Razorpay. GST applicable as per Indian tax regulations.
              By continuing you agree to our{" "}
              <a href="/terms" className="underline">Terms of Service</a>.
            </p>

            {/* CTA */}
            <button
              onClick={handleRecharge}
              disabled={state !== "idle" || !getAmount()}
              className="w-full rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {state === "creating_order" || state === "verifying"
                ? "Processing…"
                : `Pay ₹${getAmount()?.toLocaleString("en-IN") ?? "–"}`}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
```

### Acceptance Criteria

- [ ] 6 preset buttons render in a 3×2 grid; clicking one highlights it and deselects custom input
- [ ] Custom input accepts only numeric values ≥ 100; entering a value deselects preset
- [ ] "Pay ₹X" button label updates reactively as amount changes
- [ ] When `razorpay_enabled === false` → maintenance message shown, no checkout attempted
- [ ] Razorpay checkout opens with correct `order_id`, `amount`, `key_id`
- [ ] On payment success → verify endpoint called → success screen shown → wallet refreshed
- [ ] User dismissing Razorpay popup without paying → modal returns to `idle` state (no error)
- [ ] `onSuccess` callback fires with credited amount
- [ ] Error message shown on order creation failure or verification failure
- [ ] "Done" on success screen closes modal cleanly

---

## E8 — Cost Export UI

**File:** `frontend/src/components/billing/ExportPanel.tsx` (new)
**File:** `frontend/src/pages/BillingSettings.tsx` (additive — add export section)

### Purpose

Lets CXO / Admin users download cost reports directly from the UI.
Presents format selection (CSV / PDF / JSON / DOCX) and date range presets,
then triggers a file download via the `/billing/export` endpoint (D2).

```typescript
// frontend/src/components/billing/ExportPanel.tsx
import { useState } from "react";
import { billingApi } from "@/api/billingApi";
import type { ExportFormat, DatePreset } from "@/types/billing";

const FORMAT_OPTIONS: { value: ExportFormat; label: string; icon: string }[] = [
  { value: "csv",  label: "CSV",  icon: "📊" },
  { value: "pdf",  label: "PDF",  icon: "📄" },
  { value: "json", label: "JSON", icon: "{ }" },
  { value: "docx", label: "Word", icon: "📝" },
];

const PRESET_OPTIONS: { value: DatePreset; label: string }[] = [
  { value: "last_7_days",    label: "Last 7 days" },
  { value: "this_month",     label: "This month" },
  { value: "last_month",     label: "Last month" },
  { value: "last_quarter",   label: "Last quarter" },
  { value: "custom",         label: "Custom range" },
];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportPanel() {
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [preset, setPreset] = useState<DatePreset>("this_month");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState("");

  const handleExport = async () => {
    setError("");
    setIsExporting(true);
    try {
      const params: Record<string, string> = { format, preset };
      if (preset === "custom") {
        if (!startDate || !endDate) {
          setError("Please select both start and end dates.");
          setIsExporting(false);
          return;
        }
        params.start_date = startDate;
        params.end_date = endDate;
      }

      const blob = await billingApi.exportCosts(params);

      const ext = format === "docx" ? "docx" : format;
      const dateStr = new Date().toISOString().slice(0, 10);
      triggerDownload(blob, `dokydoc-costs-${dateStr}.${ext}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Export failed. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="mb-4 text-base font-semibold text-gray-900">
        Export Cost Report
      </h3>

      {/* Format selector */}
      <div className="mb-4">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Format
        </label>
        <div className="flex gap-2">
          {FORMAT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFormat(opt.value)}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors ${
                format === opt.value
                  ? "border-blue-600 bg-blue-50 font-semibold text-blue-700"
                  : "border-gray-200 text-gray-600 hover:border-blue-300"
              }`}
            >
              <span>{opt.icon}</span>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Date range */}
      <div className="mb-4">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Date Range
        </label>
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value as DatePreset)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          {PRESET_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Custom date range */}
      {preset === "custom" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-gray-500">Start date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">End date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}

      {/* Export button */}
      <button
        onClick={handleExport}
        disabled={isExporting}
        className="flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {isExporting ? (
          <>
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a10 10 0 0 1 10 10" />
            </svg>
            Exporting…
          </>
        ) : (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 15V3m0 12l-4-4m4 4l4-4M3 17v2a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2" />
            </svg>
            Download {format.toUpperCase()}
          </>
        )}
      </button>

      <p className="mt-3 text-xs text-gray-400">
        Reports include all analyses within the selected period.
        Available to Admin and CXO roles only.
      </p>
    </div>
  );
}
```

### Integration in BillingSettings page

```typescript
// frontend/src/pages/BillingSettings.tsx — additive block
import { ExportPanel } from "@/components/billing/ExportPanel";

// Inside BillingSettings JSX, after existing wallet section:
{(userRole === "cxo" || userRole === "admin") && (
  <section className="mt-8">
    <h2 className="mb-4 text-xl font-semibold text-gray-900">Cost Reports</h2>
    <ExportPanel />
  </section>
)}
```

### Acceptance Criteria

- [ ] 4 format buttons render; active format highlighted in blue
- [ ] "This month" is the default date range preset
- [ ] Selecting "Custom range" reveals start/end date pickers
- [ ] Submitting custom range without dates → inline error, no API call
- [ ] On successful export → browser "Save As" dialog opens with correct filename
  - CSV: `dokydoc-costs-YYYY-MM-DD.csv`
  - PDF: `dokydoc-costs-YYYY-MM-DD.pdf`
  - DOCX: `dokydoc-costs-YYYY-MM-DD.docx`
  - JSON: `dokydoc-costs-YYYY-MM-DD.json`
- [ ] Button shows spinner and "Exporting…" text during request
- [ ] Non-CXO/Admin users do NOT see the Export section
- [ ] API error shown as inline red message (no crash)

---

## Part E Summary

| Ticket | Component | File(s) | Track | Depends On | Est. LOC |
|--------|-----------|---------|-------|------------|---------|
| E1 | BillingContext + useBilling hook + billingApi | `contexts/BillingContext.tsx`, `hooks/useBilling.ts`, `types/billing.ts`, `api/billingApi.ts` | A | B3 `/billing/wallet` endpoint | ~110 |
| E2 | Free Credit Welcome Banner | `components/billing/FreeCreditBanner.tsx` | A | E1 | ~60 |
| E3 | Low Balance Alert | `components/billing/LowBalanceAlert.tsx` | A | E1 | ~55 |
| E4 | Model Selector Dropdown | `components/billing/ModelSelector.tsx`, `constants/models.ts` | B | E1 | ~75 |
| E5 | Cost Preview Modal | `components/billing/CostPreviewModal.tsx` | B | E1 + B2 | ~80 |
| E6 | Post-Analysis Cost Receipt Drawer | `components/billing/CostReceiptDrawer.tsx` | A | E1 | ~85 |
| E7 | Recharge Modal | `components/billing/RechargeModal.tsx`, `utils/loadRazorpay.ts` | B | C2 + C3 | ~135 |
| E8 | Cost Export UI | `components/billing/ExportPanel.tsx` | A | D2 | ~100 |

### Part E Execution Order

1. **E1** — foundation; all other E tickets depend on it
2. **E2, E3** — can be done in parallel after E1 (Track A, ship now)
3. **E6, E8** — can be done in parallel after E1 (Track A, ship now)
4. **E4, E5** — after E1 + backend B2 model routing (Track B)
5. **E7** — after E1 + backend C2 create-order + C3 verify-payment (Track B)

### Part E: Track A vs Track B

| Component | Track A (ships now) | Track B (after GSTIN) |
|-----------|--------------------|-----------------------|
| BillingContext | ✅ | — |
| Free Credit Banner | ✅ | — |
| Low Balance Alert | ✅ | — |
| Cost Receipt Drawer | ✅ | — |
| Export Panel | ✅ | — |
| Model Selector | — | ✅ (behind `razorpay_enabled`) |
| Cost Preview Modal | — | ✅ |
| Recharge Modal | — | ✅ |

---


---

# Part F — Track A vs Track B: Shipping Gates

## Overview

DokyDoc Phase 9 ships in two tracks to unblock development now while the
GSTIN (Indian tax registration) required for Razorpay live mode is still
pending. Every piece of Track B code is written and merged to `main` —
it just runs behind a single env var guard. **Zero redeploy needed** when
the GSTIN arrives.

---

## F1 — The Single Env Var Gate

```bash
# .env (production)
RAZORPAY_ENABLED=false      # Track A — everything below this line is dormant
RAZORPAY_KEY_ID=            # empty until GSTIN approved
RAZORPAY_KEY_SECRET=        # empty until GSTIN approved
RAZORPAY_WEBHOOK_SECRET=    # empty until GSTIN approved
```

When GSTIN arrives:

```bash
# .env (production) — one change, no redeploy
RAZORPAY_ENABLED=true
RAZORPAY_KEY_ID=rzp_live_XXXX
RAZORPAY_KEY_SECRET=XXXX
RAZORPAY_WEBHOOK_SECRET=XXXX
```

The `GET /billing/config` endpoint (shipped in C1) returns
`{ razorpay_enabled: true/false }` so the frontend reads the same flag
without a separate deploy.

---

## F2 — Complete Ticket-to-Track Mapping

| Ticket | Title | Track | Ships When | Notes |
|--------|-------|-------|-----------|-------|
| **A1** | Alembic migrations (new columns) | **A** | Now | Additive columns, null-safe |
| **B0** | Gemini deprecation fix | **A** | Now | **URGENT** — June 17 deadline |
| **B1** | CostBreakdown + markup | **A** | Now | `to_legacy_dict()` preserves callers |
| **B2** | Model routing `get_client_for_model()` | **A** | Now | Additive method, no existing routes changed |
| **B3** | WalletService + two-pool logic | **A** | Now | `deduct()` signature unchanged |
| **B4** | BillingEnforcementService two-pool | **A** | Now | `check_can_afford` / `deduct_cost` signatures unchanged |
| **B5** | Free credit on signup | **A** | Now | Try/except — won't break existing reg flow |
| **C1** | RazorpayService + config endpoint | **B** | After GSTIN | `/billing/config` always returns; payment calls gate on `RAZORPAY_ENABLED` |
| **C2** | Create order endpoint | **B** | After GSTIN | Returns 503 if `RAZORPAY_ENABLED=false` |
| **C3** | Verify payment endpoint | **B** | After GSTIN | Returns 503 if `RAZORPAY_ENABLED=false` |
| **C4** | Razorpay webhook handler | **B** | After GSTIN | 200 always; signature check skipped if disabled |
| **C5** | Wallet endpoints (balance + txns) | **A** | Now | Pure read — no Razorpay dependency |
| **C6** | Enterprise contact endpoint | **A** | Now | Email only — no Razorpay dependency |
| **C7** | Nightly reconciliation Celery task | **B** | After GSTIN | No orders to reconcile until B is live |
| **D1** | Cost export service | **A** | Now | Works from existing usage_logs table |
| **D2** | Export endpoint | **A** | Now | RBAC only — no payment dependency |
| **D3** | Demo org seeder | **A** | Dev/staging | Never in production cron |
| **E1** | BillingContext + hooks | **A** | Now | Wallet read endpoints are Track A |
| **E2** | Free credit banner | **A** | Now | Read-only — no payment |
| **E3** | Low balance alert | **A** | Now | Read-only — no payment |
| **E4** | Model selector | **B** | After GSTIN | Locked state shown in Track A |
| **E5** | Cost preview modal | **B** | After GSTIN | Skip in Track A |
| **E6** | Cost receipt drawer | **A** | Now | Works with Track A markup from B1 |
| **E7** | Recharge modal | **B** | After GSTIN | Maintenance screen shown if `razorpay_enabled=false` |
| **E8** | Export UI | **A** | Now | Calls D2 export endpoint |

---

## F3 — Track A Acceptance Gate (what must pass before any Track A ticket goes live)

All of the following must be true before Track A is considered production-ready:

- [ ] **A1 migration** applied on staging without data loss or column errors
- [ ] **B0** — `GEMINI_MODEL` env var set to `gemini-3-flash` on all environments
- [ ] **B1** — all analysis endpoints returning `cost_breakdown` in response
- [ ] **B3 / B4** — wallet `deduct()` tested with concurrent load (SELECT FOR UPDATE verified)
- [ ] **B5** — new user registration creates a `wallet_transaction` row with `type=credit`
- [ ] **C5** — `GET /billing/wallet` returns 200 for authenticated user
- [ ] **D1 / D2** — CSV export downloads successfully for a CXO user
- [ ] **E1** — `useBillingContext` available in authenticated layout
- [ ] **E2 / E3** — banner and alert render correctly for a new test user

---

## F4 — Track B Flip Checklist (when GSTIN arrives)

Perform these steps **in order** on the day of Track B activation:

1. Obtain Razorpay live `key_id`, `key_secret`, and `webhook_secret` from the Razorpay dashboard.
2. Update `.env` on production:
   ```
   RAZORPAY_ENABLED=true
   RAZORPAY_KEY_ID=rzp_live_XXXX
   RAZORPAY_KEY_SECRET=XXXX
   RAZORPAY_WEBHOOK_SECRET=XXXX
   ```
3. Restart only the web server process (gunicorn / uvicorn) — **no code deploy**.
4. Register webhook URL in Razorpay dashboard:
   `https://app.dokydoc.com/billing/webhook/razorpay`
   Events: `payment.captured`, `payment.failed`, `refund.created`
5. Place a test ₹100 payment using a Razorpay test card against the live endpoint.
6. Verify: wallet credited, ledger row created, receipt visible in UI.
7. Enable Celery beat for `nightly_reconciliation_task` (cron `0 1 * * *`).
8. Announce Track B live in status page.

---

## F5 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Razorpay GSTIN delayed beyond June 17 | Medium | High | B0 (Gemini deprecation) is Track A — ships independently. No revenue blocked. |
| Two concurrent payments credited twice | Low | High | Idempotency key `"rp:{payment_id}"` + SELECT FOR UPDATE covers both webhook and verify paths |
| Free credit seeded twice on signup | Low | Medium | Try/except in B5; check `has_free_credit_been_seeded` flag before inserting |
| Nightly reconciliation misses an order | Low | Low | C7 marks orders `reconciliation_failed` with alert — manual review possible |
| fpdf2 rendering differs across environments | Very Low | Low | Pin version `fpdf2==2.7.9`; PDF generation is pure Python, no system font dependencies |
| Demo seeder corrupts production data | Very Low | Critical | Seeder reads `settings.ENVIRONMENT` — aborts if not `development` or `staging` |

---

---

# Master Execution Checklist

Use this checklist to track Phase 9 progress across all parts. Tickets are
ordered by dependency — top to bottom is a safe execution sequence.

## Track A (ship now — no GSTIN needed)

- [ ] **A1** Run Alembic migration for new billing columns
- [ ] **B0** Set `GEMINI_MODEL=gemini-3-flash` in all envs
- [ ] **B1** Implement `CostBreakdown` + `MARKUP_PERCENT` in `cost_service.py`
- [ ] **B2** Add `get_client_for_model()` to `provider_router.py`
- [ ] **B3** Implement `WalletService` + `WalletTransaction` + CRUD
- [ ] **B4** Update `BillingEnforcementService` for two-pool logic
- [ ] **B5** Seed free credit on tenant registration
- [ ] **C5** Implement wallet read endpoints (`/wallet`, `/wallet/transactions`)
- [ ] **C6** Implement enterprise contact endpoint + email
- [ ] **D1** Implement `CostExportService` (add `fpdf2` to requirements)
- [ ] **D2** Add `/billing/export` endpoint
- [ ] **D3** Implement demo org seeder script
- [ ] **E1** Implement `BillingContext` + `billingApi`
- [ ] **E2** Implement `FreeCreditBanner`
- [ ] **E3** Implement `LowBalanceAlert`
- [ ] **E6** Implement `CostReceiptDrawer`
- [ ] **E8** Implement `ExportPanel` on BillingSettings page

## Track B (flip one env var when GSTIN arrives)

- [ ] **C1** Implement `RazorpayService` + `/billing/config` endpoint
- [ ] **C2** Implement `/billing/create-order` endpoint
- [ ] **C3** Implement `/billing/verify-payment` endpoint
- [ ] **C4** Implement `/billing/webhook/razorpay` handler
- [ ] **C7** Implement nightly reconciliation Celery task
- [ ] **E4** Implement `ModelSelector` component
- [ ] **E5** Implement `CostPreviewModal`
- [ ] **E7** Implement `RechargeModal`
- [ ] **F4** Execute Track B flip checklist on GSTIN day

---

*End of PHASE_9_IMPLEMENTATION_PLAN.md*


---

# Part G — Corrections & Gap Closures

## Why This Part Exists

A cross-layer strategic review (strategy ↔ backend ↔ frontend ↔ DB) found **7 gaps**
where the implementation plan diverged from `PHASE_9_STRATEGY.md`, or where the
frontend and backend made different assumptions that would break at runtime.

Every ticket in this part patches exactly one identified gap. Tickets are ordered
from most critical (P0 runtime breaks) to P1 (business logic and UX promises).

| Ticket | Gap | Severity | Layer(s) |
|--------|-----|----------|---------|
| G1 | `WalletState` TypeScript type ≠ C5 backend schema | P0 | Frontend + Backend |
| G2 | `LOW_BALANCE_THRESHOLD_INR = 50` vs ₹100 in strategy + DB | P1 | Frontend |
| G3 | `PRICING_REGISTRY` missing Claude pricing (40× undercharge) | P0 | Backend |
| G4 | `MODEL_REGISTRY` has wrong/stale model IDs | P0 | Frontend |
| G5 | Cost Preview Modal wrongly Track B — free users need it too | P1 | Frontend |
| G6 | No `InsufficientFundsModal` (strategy §7 Day 3 experience missing) | P1 | Frontend |
| G7 | Low balance email + GST invoice email are unimplemented TODOs | P1 | Backend |

**All Part G tickets are Track A** unless noted otherwise.

---

## G1 — Fix WalletState API Contract (Frontend + Backend)

**Owner:** Frontend + Backend
**Effort:** 0.5 day
**Track:** A
**Priority:** P0 — runtime break; wallet shows `undefined` values in UI
**Depends on:** C5 (wallet endpoint must exist first)

### Root Cause

E1 (`BillingContext.tsx`) defines `WalletState` with field names that **don't match**
what C5's `WalletBalanceResponse` actually returns. Additionally, E1 expects
`razorpay_enabled` from the wallet endpoint, but that field lives in `/billing/config`
(C1), a separate endpoint.

### Exact Mismatches

| E1 Frontend expects | C5 Backend returns | Resolution |
|---|---|---|
| `balance_inr` | `wallet_balance_inr` | Rename backend field to `balance_inr` |
| `free_credit_remaining_inr` | `free_credit_remaining_inr` | ✅ match |
| `free_credit_total_inr` | *(not returned)* | Add to backend response |
| `has_recharged_ever` | `has_recharged_ever` | ✅ match |
| `razorpay_enabled` | *(not returned — wrong endpoint)* | Add to backend response (read from `settings`) |
| `currency: "INR"` | *(not returned)* | Add to backend response (constant) |
| *(absent)* | `low_balance_alert` | Add to TypeScript type |
| *(absent)* | `total_available_inr` | Add to TypeScript type |

### Fix 1 — Backend: Update `WalletBalanceResponse` schema (C5 file)

In `backend/app/schemas/billing.py`, replace the `WalletBalanceResponse` class written
in C5 with this corrected version:

```python
class WalletBalanceResponse(BaseModel):
    # Wallet pools
    balance_inr: float              # RENAMED from wallet_balance_inr — matches frontend
    free_credit_remaining_inr: float
    free_credit_total_inr: float    # NEW — original signup bonus amount (for progress bar in E2)
    total_available_inr: float

    # Tenant flags
    has_recharged_ever: bool
    razorpay_enabled: bool          # NEW — read from settings; frontend gates RechargeModal on this

    # Alert
    low_balance_alert: bool         # true if total_available < low_balance_threshold

    # Meta
    currency: str = "INR"          # NEW — constant; frontend type uses literal "INR"
```

### Fix 2 — Backend: Update `/billing/wallet` endpoint (C5 file)

In `backend/app/api/endpoints/billing.py`, update the `get_wallet_balance` function
body to populate the corrected schema:

```python
@router.get("/wallet", response_model=schemas.billing.WalletBalanceResponse)
@limiter.limit(RateLimits.BILLING)
def get_wallet_balance(
    request: Request,
    *,
    tenant_id: int = Depends(deps.get_tenant_id),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    from app.services.wallet_service import wallet_service
    from app.models.tenant import Tenant

    balance = wallet_service.get_balance(db, tenant_id=tenant_id)
    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    total = balance["total_available_inr"]
    threshold = float(getattr(billing, "low_balance_threshold", 100.0))

    # free_credit_total_inr: read from tenant signup grant column (A1 adds this as
    # server_default=100.00; existing tenants have 100.00 unless manually adjusted)
    free_credit_total = float(
        getattr(tenant, "free_credit_total_inr", 100.0)  # A1 may not add this yet
        if tenant else 100.0
    )
    # Fallback: if column not present, use 100 (the known signup bonus from D3)
    if free_credit_total == 0:
        free_credit_total = 100.0

    return schemas.billing.WalletBalanceResponse(
        balance_inr=balance["wallet_balance_inr"],
        free_credit_remaining_inr=balance["free_credit_remaining_inr"],
        free_credit_total_inr=free_credit_total,
        total_available_inr=total,
        has_recharged_ever=getattr(tenant, "has_recharged_ever", False) if tenant else False,
        razorpay_enabled=settings.RAZORPAY_ENABLED,
        low_balance_alert=total < threshold,
        currency="INR",
    )
```

> **Note on `free_credit_total_inr`:** A1 migration adds `free_credit_remaining_inr`
> (the live counter) but not a `free_credit_total_inr` snapshot. Add this column in
> a follow-up migration `s9p7_free_credit_total.py` so the E2 progress bar can show
> "₹X of ₹100 remaining". Until then, the `getattr(..., 100.0)` fallback is correct
> because the signup bonus is fixed at ₹100.

### Fix 3 — Frontend: Update `WalletState` type (E1 file)

In `frontend/src/types/billing.ts`, replace the `WalletState` interface:

```typescript
export interface WalletState {
  // Wallet pools
  balance_inr: number;               // Paid wallet (renamed from wallet_balance_inr)
  free_credit_remaining_inr: number;
  free_credit_total_inr: number;     // For E2 progress bar
  total_available_inr: number;

  // Tenant flags
  has_recharged_ever: boolean;
  razorpay_enabled: boolean;         // Gates E7 RechargeModal

  // Alert
  low_balance_alert: boolean;        // Backend-computed; use this, not hardcoded threshold

  // Meta
  currency: "INR";
}
```

### Fix 4 — Frontend: Update `BillingContext` derived values (E1 file)

In `frontend/src/contexts/BillingContext.tsx`, remove the hardcoded threshold constant
and derive `isLowBalance` directly from the backend-computed field:

```typescript
// REMOVE this line:
// const LOW_BALANCE_THRESHOLD_INR = 50;

// REPLACE the isLowBalance computation with:
const isLowBalance =
  !isLoading &&
  wallet !== null &&
  wallet !== undefined &&
  wallet.low_balance_alert;          // Use backend-computed value — respects DB threshold

// isFreeLaneActive is unchanged:
const isFreeLaneActive =
  wallet !== null &&
  wallet !== undefined &&
  wallet.free_credit_remaining_inr > 0;
```

### Acceptance Criteria

- [ ] `GET /billing/wallet` response has field `balance_inr` (not `wallet_balance_inr`)
- [ ] `GET /billing/wallet` response includes `razorpay_enabled`, `free_credit_total_inr`, `total_available_inr`, `currency`
- [ ] `GET /billing/wallet` response includes `low_balance_alert: true` when total < `billing.low_balance_threshold`
- [ ] TypeScript `WalletState` compiles without errors against the live API response
- [ ] `wallet.balance_inr` renders a number (not `undefined`) in the `LowBalanceAlert` component
- [ ] `wallet.razorpay_enabled` correctly shows/hides `RechargeModal` in E7
- [ ] `isLowBalance` in `BillingContext` uses `wallet.low_balance_alert` (no hardcoded `50`)
- [ ] `FreeCreditBanner` (E2) progress bar renders correctly using `free_credit_total_inr`

---

## G2 — Fix Low Balance Threshold Inconsistency (Frontend)

**Owner:** Frontend
**Effort:** 0.25 day
**Track:** A
**Priority:** P1 — alert fires at wrong threshold (₹50 vs strategy's ₹100)
**Depends on:** G1 (must be done together — G1 removes the hardcoded threshold)
**Note:** G1 and G2 are one commit. G2 is listed separately for traceability.

### Root Cause

E1 `BillingContext.tsx` has `const LOW_BALANCE_THRESHOLD_INR = 50` on line 4841 of
the implementation plan. Strategy §3 explicitly says "When your wallet drops below
**₹100**, we send you a friendly reminder email." The DB default (A4 migration) sets
`low_balance_threshold = Decimal("100.00")`.

Having the frontend use a different threshold than the backend creates a UX split:
- Backend sends the low-balance email at ₹100 (correct)
- Frontend shows the amber alert at ₹50 (wrong — user sees no in-app warning between ₹100 and ₹50)
- The "window of silence" from ₹100 to ₹50 is where a user depletes their wallet
  and is neither warned by email nor shown the in-app alert

### Fix

This is fully covered by G1 Fix 4. The `isLowBalance` derivation switches to
`wallet.low_balance_alert` (backend-computed from the DB threshold of ₹100). The
hardcoded `LOW_BALANCE_THRESHOLD_INR` constant is deleted. No other changes needed.

### Acceptance Criteria

- [ ] `LOW_BALANCE_THRESHOLD_INR` constant does not exist in the codebase after this change
- [ ] `LowBalanceAlert` renders when `wallet.low_balance_alert === true` (not at a hardcoded value)
- [ ] If ops changes a tenant's `low_balance_threshold` in the DB to ₹200, the frontend alert
  reflects that on next wallet refresh (no code change needed)

---

## G3 — Add Claude Pricing to `PRICING_REGISTRY` (Backend)

**Owner:** Backend
**Effort:** 0.5 day
**Track:** A
**Priority:** P0 — every Claude analysis call undercharges by ~40× (revenue leak)
**Depends on:** B0 (PRICING_REGISTRY must exist first)
**File:** `backend/app/services/cost_service.py`

### Root Cause

B0 creates `PRICING_REGISTRY` with four Gemini entries only. B2 `model_selector.py`
correctly lists `claude-sonnet-4-6` and `claude-haiku-4-5` as supported paid models.

When a paid user picks Claude and an analysis runs:
```python
# In cost_service.py — B0 as written:
def get_pricing_for_model(model_id: str) -> PricingTier:
    return PRICING_REGISTRY.get(model_id, GEMINI_25_FLASH_PRICING)
#                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^
#   "claude-sonnet-4-6" not in registry → falls back to Gemini 2.5 Flash pricing
#   Claude Sonnet 4.6: $3.00/M input vs Gemini 2.5 Flash: $0.075/M input = 40× too cheap
```

The user receives Claude quality at Gemini price. DokyDoc absorbs the full delta.

### Step 1 — Add Claude pricing constants

Add after `GEMINI_3_FLASH_LITE_PRICING` in `cost_service.py` (after B0 section):

```python
# ============================================================================
# CLAUDE SONNET 4.6 PRICING — Deep reasoning, paid lane
# Source: console.anthropic.com/settings/billing (verify at implementation time)
# ============================================================================
CLAUDE_SONNET_4_6_PRICING = PricingTier(
    model="claude-sonnet-4-6",
    input_per_1m_usd=Decimal("3.00"),
    output_per_1m_usd=Decimal("15.00"),
    thinking_per_1m_usd=Decimal("0.00"),    # Extended thinking priced separately if used
    cached_per_1m_usd=Decimal("0.30"),      # Prompt cache reads
    search_per_1k_usd=Decimal("0.00"),      # Claude doesn't have search grounding
    description="Claude Sonnet 4.6 — paid lane, deep reasoning"
)

# ============================================================================
# CLAUDE HAIKU 4.5 PRICING — Fast, economical, paid lane
# Source: console.anthropic.com/settings/billing (verify at implementation time)
# ============================================================================
CLAUDE_HAIKU_4_5_PRICING = PricingTier(
    model="claude-haiku-4-5",
    input_per_1m_usd=Decimal("0.80"),
    output_per_1m_usd=Decimal("4.00"),
    thinking_per_1m_usd=Decimal("0.00"),
    cached_per_1m_usd=Decimal("0.08"),
    search_per_1k_usd=Decimal("0.00"),
    description="Claude Haiku 4.5 — paid lane, fast and economical"
)
```

> **IMPORTANT:** Verify both rate tables against `console.anthropic.com/settings/billing`
> at the time of implementation. Anthropic updates pricing periodically. The values above
> are correct as of April 2026 but must be confirmed before going live. Wrong rates
> either overcharge customers (churn) or undercharge (revenue leak).

### Step 2 — Add Claude entries to `PRICING_REGISTRY`

Update `PRICING_REGISTRY` in `cost_service.py`:

```python
PRICING_REGISTRY: dict[str, PricingTier] = {
    # Gemini — legacy
    "gemini-1.5-flash":    GEMINI_15_FLASH_PRICING,
    "gemini-2.5-flash":    GEMINI_25_FLASH_PRICING,   # Deprecated June 17, 2026 — keep for historical rows
    # Gemini — Phase 9 active
    "gemini-3-flash":      GEMINI_3_FLASH_PRICING,
    "gemini-3-flash-lite": GEMINI_3_FLASH_LITE_PRICING,
    # Claude — Phase 9 active (G3 addition)
    "claude-sonnet-4-6":   CLAUDE_SONNET_4_6_PRICING,
    "claude-haiku-4-5":    CLAUDE_HAIKU_4_5_PRICING,
}
```

### Step 3 — Update `SUPPORTED_MODELS` in `model_selector.py` to include pricing hint

Optionally, annotate `SUPPORTED_MODELS` in `model_selector.py` with an
`approx_input_per_1m_usd` field so model routing tests can assert rough cost ratios.
This is documentation-only and doesn't affect logic. Skip if team prefers minimal changes.

### Why NOT add a `PricingTier` for Claude thinking tokens

Claude 3.5+ models support extended thinking (similar to Gemini thinking tokens).
However, DokyDoc does not currently enable extended thinking in Anthropic API calls.
Set `thinking_per_1m_usd=Decimal("0.00")` in both Claude entries and add a comment:

```python
# thinking_per_1m_usd=0 because DokyDoc does not enable extended thinking at v1.
# When/if extended thinking is enabled for Claude, update this and re-test billing.
```

### Acceptance Criteria

- [ ] `get_pricing_for_model("claude-sonnet-4-6")` returns `CLAUDE_SONNET_4_6_PRICING` (not Gemini fallback)
- [ ] `get_pricing_for_model("claude-haiku-4-5")` returns `CLAUDE_HAIKU_4_5_PRICING`
- [ ] `calculate_cost_from_actual_tokens(1000, 500, model="claude-sonnet-4-6")` charges
  ~40× more than the same call with `model="gemini-2.5-flash"` (rough sanity check)
- [ ] `calculate_cost_from_actual_tokens(1000, 500, model="claude-haiku-4-5")` charges
  between Gemini 3 Flash-Lite and Claude Sonnet 4.6 (haiku is mid-price)
- [ ] `PRICING_REGISTRY` has exactly 6 entries (no entries removed — historical rows safe)
- [ ] Unit test: `assert CLAUDE_SONNET_4_6_PRICING.input_per_1m_usd > GEMINI_3_FLASH_PRICING.input_per_1m_usd`
- [ ] `pytest backend/tests/` — all existing tests pass

---

## G4 — Fix `MODEL_REGISTRY` Model IDs (Frontend)

**Owner:** Frontend
**Effort:** 0.25 day
**Track:** A
**Priority:** P0 — users select a model, wrong ID sent to backend, wrong model runs silently
**Depends on:** Nothing (pure frontend fix)
**File:** `frontend/src/constants/models.ts`

### Root Cause

E4 wrote `MODEL_REGISTRY` in `frontend/src/constants/models.ts` with model IDs that
don't match the backend `SUPPORTED_MODELS` in `model_selector.py`. These IDs flow
into every analysis API call as the `model_id` request field.

| E4 (wrong) | B2 backend expects | Strategy §5 specifies |
|---|---|---|
| `"gemini-2.5-flash"` | `"gemini-3-flash"` | `"gemini-3-flash"` |
| `"gemini-2.5-pro"` | *(not supported)* | *(not in strategy)* |
| `"claude-3-7-sonnet"` | `"claude-sonnet-4-6"` | `"claude-sonnet-4-6"` |
| *(missing)* | `"claude-haiku-4-5"` | `"claude-haiku-4-5"` |

When an unsupported `model_id` reaches `ModelSelector.resolve()` in B2:
```python
if requested_model and requested_model in SUPPORTED_MODELS:
    model = requested_model
else:
    model = tenant_default   # silent fallback — user picked Claude, gets Gemini
```
No error. No log entry at WARNING level. The user thinks their document ran on
Claude Sonnet; it actually ran on `gemini-3-flash-lite`. The receipt shows the
wrong model name. Trust destroyed silently.

### Fix — Replace `MODEL_REGISTRY` in `frontend/src/constants/models.ts`

Replace the entire `MODEL_REGISTRY` array (and the stale `ModelMeta` interface if
present) with the following corrected version:

```typescript
// frontend/src/constants/models.ts

export interface ModelMeta {
  id: string;
  display_name: string;
  provider: "google" | "anthropic";
  tier: "free" | "paid";
  context_window: number;          // tokens
  description: string;
  est_cost_per_page_inr: number;   // rough estimate for cost preview UI (E5)
}

// Single source of truth for model IDs used across the frontend.
// MUST stay in sync with backend/app/services/ai/model_selector.py SUPPORTED_MODELS.
// When adding a new model: add here AND in SUPPORTED_MODELS AND in PRICING_REGISTRY.
export const MODEL_REGISTRY: ModelMeta[] = [
  {
    id: "gemini-3-flash-lite",        // Free lane — do not change this ID
    display_name: "Gemini 3 Flash-Lite",
    provider: "google",
    tier: "free",
    context_window: 128_000,
    description: "Fast & free — good for routine document checks",
    est_cost_per_page_inr: 0.0,       // Deducted from free credit pool
  },
  {
    id: "gemini-3-flash",             // FIXED: was "gemini-2.5-flash"
    display_name: "Gemini 3 Flash",
    provider: "google",
    tier: "paid",
    context_window: 1_000_000,
    description: "Balanced speed & depth — best default for most documents",
    est_cost_per_page_inr: 0.05,
  },
  {
    id: "claude-sonnet-4-6",          // FIXED: was "claude-3-7-sonnet"
    display_name: "Claude Sonnet 4.6",
    provider: "anthropic",
    tier: "paid",
    context_window: 200_000,
    description: "Deep reasoning — best for compliance, legal, and nuanced analysis",
    est_cost_per_page_inr: 0.45,      // Updated to reflect Claude's higher price vs Gemini
  },
  {
    id: "claude-haiku-4-5",           // NEW: was missing entirely
    display_name: "Claude Haiku 4.5",
    provider: "anthropic",
    tier: "paid",
    context_window: 200_000,
    description: "Fast Anthropic model — good balance of quality and cost",
    est_cost_per_page_inr: 0.12,
  },
  // REMOVED: "gemini-2.5-pro" — not in strategy, not in backend SUPPORTED_MODELS
];

export const FREE_MODEL_ID = "gemini-3-flash-lite";

// Convenience: paid models only (shown in ModelSelector dropdown for paid users)
export const PAID_MODELS = MODEL_REGISTRY.filter((m) => m.tier === "paid");
```

> **`est_cost_per_page_inr` note:** These are rough estimates for the cost preview UI
> only — they are **not** the billing source of truth. Actual billing uses backend
> `PRICING_REGISTRY` token rates. The estimates should be updated if the backend
> pricing constants change significantly.

### Validation Comment to Add

Add this comment at the top of the file as a permanent guard:

```typescript
/**
 * MODEL_REGISTRY — Frontend model definitions.
 *
 * ⚠️  SYNC REQUIREMENT:
 * The `id` field of each entry MUST exactly match the keys in:
 *   backend/app/services/ai/model_selector.py  → SUPPORTED_MODELS
 *   backend/app/services/cost_service.py       → PRICING_REGISTRY
 *
 * If you add a model here, add it to both backend files too.
 * If you change an ID here, change it in both backend files too.
 * Stale IDs cause silent model fallback (user gets Gemini when they picked Claude).
 */
```

### Acceptance Criteria

- [ ] `MODEL_REGISTRY` has exactly 4 entries: `gemini-3-flash-lite`, `gemini-3-flash`,
  `claude-sonnet-4-6`, `claude-haiku-4-5`
- [ ] `"gemini-2.5-flash"` does not appear anywhere in `constants/models.ts`
- [ ] `"gemini-2.5-pro"` does not appear anywhere in `constants/models.ts`
- [ ] `"claude-3-7-sonnet"` does not appear anywhere in `constants/models.ts`
- [ ] `PAID_MODELS` exports 3 entries (all paid models)
- [ ] `FREE_MODEL_ID === "gemini-3-flash-lite"` (unchanged)
- [ ] `ModelSelector` (E4) dropdown renders 3 paid options: Gemini 3 Flash,
  Claude Sonnet 4.6, Claude Haiku 4.5
- [ ] Sending `model_id: "gemini-3-flash"` to the backend → backend resolves it
  correctly (not `tenant.default_model` fallback)

---

## G5 — Move Cost Preview Modal to Track A (Frontend)

**Owner:** Frontend
**Effort:** 0.5 day
**Track:** A (was incorrectly Track B)
**Priority:** P1 — free users have no visibility into costs before analysis runs
**Depends on:** G1 (correct `WalletState` types), E1 (`BillingContext`)
**File:** `frontend/src/components/billing/CostPreviewModal.tsx`

### Root Cause

E5 tagged `CostPreviewModal` as Track B (only show when `razorpay_enabled`).

Strategy §7 Day 1 explicitly describes a free-lane user on their **very first document**
seeing a cost preview:

> *"Before analysis starts, a small modal appears: This document will use **Gemini 3
> Flash-Lite (free lane)**. Estimated cost: **₹2.40**. Wallet balance after: ₹97.60.
> [Cancel] [Continue]"*

This experience has zero dependency on Razorpay. It only requires:
- A wallet balance (Track A — C5 endpoint)
- A model name (known at the time the user initiates analysis)
- A page count (from the document metadata already in the browser)

Hiding the cost preview behind GSTIN means every free user runs analyses without
knowing the cost — breaking the core trust promise of the strategy.

### What Changes

The component logic changes in two ways:

1. **Track flag:** `CostPreviewModal` is Track A. It shows for ALL users
   (free and paid) before every analysis.

2. **Free-lane variant:** When `isFreeLaneActive === true`, the modal renders
   differently — it shows the free model, deducts from free credit pool display,
   and has no "switch model" affordance (they can't switch on the free lane).

### Updated `CostPreviewModal` (replaces E5 entirely)

```typescript
// frontend/src/components/billing/CostPreviewModal.tsx
// TRACK A — shows for free AND paid users before every analysis

import { useBillingContext } from "@/contexts/BillingContext";
import { MODEL_REGISTRY, FREE_MODEL_ID } from "@/constants/models";

interface CostPreviewModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  modelId: string;                 // Resolved model ID (from ModelSelector or FREE_MODEL_ID)
  estimatedPages: number;
  onModelChange?: (modelId: string) => void;  // Only shown for paid users
}

export function CostPreviewModal({
  isOpen, onConfirm, onCancel, modelId, estimatedPages, onModelChange,
}: CostPreviewModalProps) {
  const { wallet, isFreeLaneActive } = useBillingContext();

  if (!isOpen || !wallet) return null;

  const model = MODEL_REGISTRY.find((m) => m.id === modelId);
  const estCost = model ? model.est_cost_per_page_inr * estimatedPages : 0;

  // For free lane: deduct from free_credit_remaining_inr
  // For paid lane: deduct from balance_inr
  const currentPool = isFreeLaneActive
    ? wallet.free_credit_remaining_inr
    : wallet.balance_inr;
  const poolLabel = isFreeLaneActive ? "Free credit" : "Wallet balance";
  const balanceAfter = currentPool - estCost;
  const canAfford = balanceAfter >= 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">

        <h2 className="text-lg font-semibold text-gray-900">
          Estimated Analysis Cost
        </h2>

        {/* Free lane banner */}
        {isFreeLaneActive && (
          <div className="mt-3 flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-xs text-green-700">
            <span>✓</span>
            <span>
              This analysis uses <strong>free credit</strong> —
              no charge to your paid wallet.
            </span>
          </div>
        )}

        <div className="mt-4 space-y-3">
          {/* Model */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Model</span>
            <div className="flex items-center gap-2">
              <span className="font-medium">{model?.display_name ?? modelId}</span>
              {isFreeLaneActive && (
                <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                  free lane
                </span>
              )}
            </div>
          </div>

          {/* Pages */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Document pages</span>
            <span className="font-medium">{estimatedPages}</span>
          </div>

          {/* Estimated cost */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Estimated cost</span>
            <span className="font-semibold">
              {isFreeLaneActive ? "Free" : `~₹${estCost.toFixed(2)}`}
            </span>
          </div>

          <hr className="border-gray-100" />

          {/* Pool balance */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">{poolLabel}</span>
            <span>₹{currentPool.toFixed(2)}</span>
          </div>

          {/* Balance after */}
          <div className="flex items-center justify-between text-sm font-semibold">
            <span className="text-gray-700">After this analysis</span>
            <span className={balanceAfter < 0 ? "text-red-600" : "text-green-700"}>
              {balanceAfter < 0
                ? `−₹${Math.abs(balanceAfter).toFixed(2)} (insufficient)`
                : `₹${balanceAfter.toFixed(2)}`}
            </span>
          </div>
        </div>

        {/* Insufficient balance */}
        {!canAfford && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
            {isFreeLaneActive
              ? "Not enough free credit for this analysis. Recharge to continue."
              : "Insufficient wallet balance. Please add funds or choose a cheaper model."}
          </p>
        )}

        {/* Transparency note — only for paid users */}
        {!isFreeLaneActive && (
          <p className="mt-3 text-xs text-gray-400">
            Includes 15% platform fee. Actual cost may vary ±20% based on token density.
          </p>
        )}

        {/* Actions */}
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!canAfford}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Confirm & Analyse
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Integration Update

In the analysis form, `CostPreviewModal` is now **always mounted** (Track A). The
model is resolved before opening the modal:

```typescript
// In analysis form — existing code, minimal change:
import { FREE_MODEL_ID } from "@/constants/models";
const { isFreeLaneActive } = useBillingContext();

// Resolve the model to use:
const resolvedModel = isFreeLaneActive ? FREE_MODEL_ID : selectedModel;

// Open preview before analysis (for both free and paid users):
const handleAnalyseClick = () => {
  setPreviewOpen(true);   // Always open the preview
};
```

### Update Part F Track Table

In the F2 ticket-to-track mapping table, update E5's row:

| Was | Now |
|---|---|
| E5 — Track B (after GSTIN) | E5 — **Track A** (ships now) |

### Acceptance Criteria

- [ ] Free-lane user on Day 1 sees cost preview with "free credit" green banner
- [ ] Free-lane preview shows `balance_after = free_credit_remaining_inr - estCost`
- [ ] Paid user sees cost preview with wallet balance and 15% markup note
- [ ] Paid user preview shows `balance_after = balance_inr - estCost`
- [ ] Confirm button disabled when estimated cost > available pool
- [ ] Free-lane user has NO model change affordance in the modal
- [ ] Component renders when `razorpay_enabled === false` (Track A)
- [ ] `onCancel` closes without running analysis in both lanes

---

## G6 — Add `InsufficientFundsModal` (Frontend)

**Owner:** Frontend
**Effort:** 0.5 day
**Track:** A
**Priority:** P1 — without this, a user with an empty wallet sees a raw API error
**Depends on:** G1 (correct wallet types), E7 (RechargeModal must exist to embed)
**File:** `frontend/src/components/billing/InsufficientFundsModal.tsx` (new)

### Root Cause

Strategy §7 Day 3 describes the experience when a user tries to run an analysis
with insufficient balance:

> *"A friendly modal appears: Your wallet has ₹5 left — not enough for this
> document (~₹2.40). Recharge to continue. [Recharge ₹100] [Recharge ₹500]
> [Custom amount]"*

The current plan has:
- `LowBalanceAlert` (E3) — a **passive banner** that shows when balance is low
- No component that intercepts a `402 Payment Required` from the analysis API

When `billing_enforcement_service.check_can_afford_analysis()` returns false,
the backend raises an HTTP 402. Without a frontend handler, React Query surfaces
a generic error. The user has no CTA, no context, and no way to fix it inline.

This modal is the **retention moment** — it's the difference between "the product
stopped working" and "I need to add ₹100, which I'll do right now."

### Implementation

```typescript
// frontend/src/components/billing/InsufficientFundsModal.tsx
import { useState } from "react";
import { useBillingContext } from "@/contexts/BillingContext";
import { RechargeModal } from "./RechargeModal";

interface InsufficientFundsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFundsAdded: () => void;       // Callback to retry the failed analysis
  estimatedCostInr?: number;      // From cost preview or error response body
  documentName?: string;          // For personalised copy: "Analyzing 'ACME PRD'"
}

const QUICK_RECHARGE_AMOUNTS = [100, 500, 1_000];

export function InsufficientFundsModal({
  isOpen, onClose, onFundsAdded, estimatedCostInr, documentName,
}: InsufficientFundsModalProps) {
  const { wallet, refetch } = useBillingContext();
  const [showRechargeModal, setShowRechargeModal] = useState(false);
  const [suggestedAmount, setSuggestedAmount] = useState<number>(500);

  if (!isOpen) return null;

  const shortfall = estimatedCostInr && wallet
    ? Math.max(0, estimatedCostInr - (wallet.balance_inr + wallet.free_credit_remaining_inr))
    : null;

  // Suggest the smallest preset that covers the shortfall + ₹50 buffer
  const recommendedAmount = shortfall
    ? QUICK_RECHARGE_AMOUNTS.find((a) => a >= shortfall + 50) ?? 1_000
    : 500;

  const handleQuickRecharge = (amount: number) => {
    setSuggestedAmount(amount);
    setShowRechargeModal(true);
  };

  const handleRechargeSuccess = (amountAdded: number) => {
    setShowRechargeModal(false);
    refetch();          // Update wallet balance in context
    onFundsAdded();     // Retry the analysis
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">

          {/* Icon */}
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
              stroke="#d97706" strokeWidth="2">
              <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
          </div>

          {/* Heading */}
          <h2 className="text-center text-lg font-semibold text-gray-900">
            Insufficient Wallet Balance
          </h2>

          {/* Body */}
          <div className="mt-3 text-center text-sm text-gray-500">
            {documentName && (
              <p className="mb-1 font-medium text-gray-700">
                "{documentName}"
              </p>
            )}
            {wallet && (
              <p>
                Your wallet has{" "}
                <strong className="text-gray-900">
                  ₹{(wallet.balance_inr + wallet.free_credit_remaining_inr).toFixed(2)}
                </strong>{" "}
                available
                {estimatedCostInr && (
                  <> — this analysis needs ~<strong>₹{estimatedCostInr.toFixed(2)}</strong></>
                )}
                .
              </p>
            )}
            <p className="mt-1">Add funds to continue.</p>
          </div>

          {/* Quick recharge buttons */}
          <div className="mt-5 space-y-2">
            {QUICK_RECHARGE_AMOUNTS.map((amount) => (
              <button
                key={amount}
                onClick={() => handleQuickRecharge(amount)}
                className={`w-full rounded-lg border py-2.5 text-sm font-semibold transition-colors ${
                  amount === recommendedAmount
                    ? "border-blue-600 bg-blue-600 text-white hover:bg-blue-700"
                    : "border-gray-200 text-gray-700 hover:border-blue-400 hover:bg-blue-50"
                }`}
              >
                Add ₹{amount.toLocaleString("en-IN")}
                {amount === recommendedAmount && (
                  <span className="ml-2 text-xs opacity-80">Recommended</span>
                )}
              </button>
            ))}
            <button
              onClick={() => handleQuickRecharge(0)}
              className="w-full rounded-lg border border-gray-200 py-2 text-sm text-gray-500 hover:border-gray-300"
            >
              Custom amount
            </button>
          </div>

          {/* Dismiss */}
          <button
            onClick={onClose}
            className="mt-4 w-full text-center text-xs text-gray-400 hover:text-gray-600"
          >
            Cancel analysis
          </button>
        </div>
      </div>

      {/* Inline RechargeModal — opens on top of InsufficientFundsModal */}
      <RechargeModal
        isOpen={showRechargeModal}
        onClose={() => setShowRechargeModal(false)}
        onSuccess={handleRechargeSuccess}
      />
    </>
  );
}
```

### Global 402 Handler in `billingApi`

To avoid duplicating the 402 handler in every page/feature that calls an analysis
endpoint, add an Axios interceptor in the API client:

```typescript
// frontend/src/api/client.ts — additive: add 402 interceptor
// (This is the existing Axios instance — add the interceptor, do not re-create)

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 402) {
      // Emit a custom event that the InsufficientFundsModal listens to
      // This avoids prop-drilling onError through every analysis component
      window.dispatchEvent(
        new CustomEvent("dokydoc:insufficient_funds", {
          detail: {
            estimatedCostInr: error.response.data?.required_inr ?? null,
            documentName: error.response.data?.document_name ?? null,
          },
        })
      );
      // Still reject — callers can handle it too if they want
      return Promise.reject(error);
    }
    return Promise.reject(error);
  }
);
```

### `InsufficientFundsProvider` — global listener

Wrap the authenticated layout with a provider that listens for the custom event:

```typescript
// frontend/src/components/billing/InsufficientFundsProvider.tsx  (new)
import { useState, useEffect } from "react";
import { InsufficientFundsModal } from "./InsufficientFundsModal";

export function InsufficientFundsProvider({ children }: { children: React.ReactNode }) {
  const [modalState, setModalState] = useState<{
    open: boolean;
    estimatedCostInr?: number;
    documentName?: string;
    retryFn?: () => void;
  }>({ open: false });

  useEffect(() => {
    const handler = (e: CustomEvent) => {
      setModalState({
        open: true,
        estimatedCostInr: e.detail.estimatedCostInr,
        documentName: e.detail.documentName,
        retryFn: undefined,   // No automatic retry — user re-initiates
      });
    };
    window.addEventListener("dokydoc:insufficient_funds", handler as EventListener);
    return () => window.removeEventListener("dokydoc:insufficient_funds", handler as EventListener);
  }, []);

  return (
    <>
      {children}
      <InsufficientFundsModal
        isOpen={modalState.open}
        estimatedCostInr={modalState.estimatedCostInr}
        documentName={modalState.documentName}
        onClose={() => setModalState({ open: false })}
        onFundsAdded={() => setModalState({ open: false })}
      />
    </>
  );
}
```

Mount in `App.tsx`:
```typescript
// App.tsx — add inside authenticated routes wrapper (alongside BillingProvider):
<BillingProvider>
  <InsufficientFundsProvider>
    {/* existing authenticated children */}
  </InsufficientFundsProvider>
</BillingProvider>
```

### Backend: Ensure 402 response body has context

In `billing_enforcement_service.py`, when raising the insufficient funds error,
include structured data the modal can use:

```python
# In check_can_afford_analysis() — update the HTTPException:
raise HTTPException(
    status_code=402,
    detail={
        "error": "insufficient_balance",
        "message": "Insufficient wallet balance for this analysis.",
        "available_inr": float(combined_balance),
        "required_inr": float(estimated_cost),
        "shortfall_inr": float(max(0, estimated_cost - combined_balance)),
    }
)
```

### Acceptance Criteria

- [ ] When analysis API returns 402, `InsufficientFundsModal` opens automatically
  (no page navigation, no toast — the modal)
- [ ] Modal shows current wallet balance and estimated cost
- [ ] Modal shows recommended recharge amount (smallest preset covering shortfall + buffer)
- [ ] Recommended amount button is highlighted in blue
- [ ] "Add ₹X" button opens `RechargeModal` on top without closing `InsufficientFundsModal`
- [ ] After successful recharge: wallet updates, `InsufficientFundsModal` closes
- [ ] "Cancel analysis" closes both modals
- [ ] When `razorpay_enabled === false`: `InsufficientFundsModal` still opens but
  the recharge buttons are disabled with message "Recharge temporarily unavailable"
- [ ] 402 from ANY analysis endpoint triggers the modal (interceptor covers all calls)
- [ ] 402 response body `required_inr` is used for shortfall calculation when present

---

## G7 — Implement Email Notifications (Low Balance + GST Invoice)

**Owner:** Backend
**Effort:** 1 day
**Track:** A (low balance email) + B (GST invoice — needs Razorpay payment data)
**Priority:** P1 — retention (low balance) + compliance (GST invoice)
**Depends on:** B4 (low balance hook exists as TODO), C3/C4 (payment hooks exist as TODO)

### Root Cause

Two email sends are documented in the strategy but left as TODO comments in the plan:

**1. Low balance reminder email** — Strategy §3:
> *"When your wallet drops below ₹100, we send you a friendly reminder email."*

B4 `_maybe_send_low_balance_alert()` calls `logger.info()` and sets
`billing.last_low_balance_alert_at` but the strategy promise of an actual email
to the customer is never fulfilled.

**2. GST-compliant invoice email** — Strategy §6 step 6:
> *"Customer gets a GST-compliant invoice via email."*

C3 verify-payment and C4 webhook both credit the wallet and return a response,
but no email is sent. The customer paid real money and received no receipt in
their inbox.

### Design Decision: Sync vs Async

Both emails are sent **synchronously** in the request path for v1:

| Email | Where sent | Why sync |
|---|---|---|
| Low balance | `_maybe_send_low_balance_alert()` | Already in a deduct transaction; fast SMTP call adds <200ms acceptable |
| Payment receipt | C3 `verify_payment()` + C4 webhook | User is waiting for confirmation; the email IS the confirmation |

If email latency becomes an issue in production, move both to Celery tasks.
For v1, keep it simple.

### Step 1 — Create `email_service.py`

**File:** `backend/app/services/email_service.py` (new)

```python
"""
Email Service — Phase 9 (G7)

Thin wrapper over Python's smtplib (or a third-party SMTP service).
Uses settings from config.py. Designed to be swapped for Sendgrid / SES later.

Two email types at v1:
  - send_low_balance_email()   → triggered by B4 billing enforcement
  - send_payment_receipt()     → triggered by C3 verify-payment + C4 webhook
"""
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from decimal import Decimal
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.email_service")


def _build_smtp_connection():
    """Returns a configured smtplib connection. Raises on failure."""
    if settings.SMTP_USE_TLS:
        conn = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    else:
        conn = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        conn.starttls()
    conn.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    return conn


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send a single email. Returns True on success, False on failure.
    Never raises — billing must not fail because email is down.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"DokyDoc Billing <{settings.EMAIL_FROM}>"
        msg["To"] = to_email

        # Plain-text fallback (strip tags crudely — sufficient for transactional email)
        plain = html_body.replace("<br>", "\n").replace("</p>", "\n\n")
        import re
        plain = re.sub(r"<[^>]+>", "", plain)

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        conn = _build_smtp_connection()
        conn.sendmail(settings.EMAIL_FROM, [to_email], msg.as_string())
        conn.quit()

        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as exc:
        logger.error(f"Email send failed to {to_email}: {exc}")
        return False


def send_low_balance_email(
    to_email: str,
    tenant_name: str,
    current_balance_inr: float,
    threshold_inr: float,
) -> bool:
    """
    Sent when combined wallet balance drops below low_balance_threshold.
    Strategy §3: "we send you a friendly reminder email."
    """
    subject = f"Your DokyDoc wallet balance is running low — ₹{current_balance_inr:.2f} remaining"

    html = f"""
    <p>Hi {tenant_name} team,</p>

    <p>Your DokyDoc wallet balance has dropped below ₹{threshold_inr:.0f}.</p>

    <p>
      <strong>Current balance: ₹{current_balance_inr:.2f}</strong><br>
      Alert threshold: ₹{threshold_inr:.0f}
    </p>

    <p>
      To keep your analyses running without interruption, please add funds to your wallet.
      You can recharge from the
      <a href="{settings.APP_BASE_URL}/settings/billing">Billing page</a>.
    </p>

    <p>
      Recharge options: ₹100 / ₹200 / ₹500 / ₹1,000 / ₹2,500 / ₹5,000 (or any custom amount).<br>
      Payments via UPI, Google Pay, cards, and net banking.
    </p>

    <p style="color:#6b7280;font-size:12px;">
      DokyDoc charges a flat 15% platform fee on top of raw AI costs.
      Your balance reflects exactly what is available for analysis.
    </p>

    <p>— DokyDoc Billing</p>
    """

    return _send(to_email, subject, textwrap.dedent(html))


def send_payment_receipt(
    to_email: str,
    tenant_name: str,
    amount_inr: float,
    payment_id: str,
    order_id: str,
    new_balance_inr: float,
    paid_at: datetime,
) -> bool:
    """
    Sent after a successful Razorpay payment.
    Strategy §6: "Customer gets a GST-compliant invoice via email."

    Note on GST compliance: Full GST invoice (with GSTIN, HSN code, tax breakdowns)
    requires our own GSTIN to be registered. Until GSTIN is available, this email
    is a payment confirmation only. Once GSTIN is registered, add tax fields below.
    Mark as TODO in the code until then.
    """
    subject = f"Payment confirmed — ₹{amount_inr:.2f} added to your DokyDoc wallet"

    paid_at_str = paid_at.strftime("%d %B %Y, %I:%M %p IST")

    # TODO (after GSTIN): Add GST fields — GSTIN, HSN code, IGST/CGST/SGST split
    # For now: this is a payment confirmation (not a tax invoice)
    html = f"""
    <p>Hi {tenant_name} team,</p>

    <p>Your payment has been received and your wallet has been credited.</p>

    <table style="border-collapse:collapse;width:100%;max-width:480px">
      <tr>
        <td style="padding:8px 0;color:#6b7280">Amount paid</td>
        <td style="padding:8px 0;font-weight:600">₹{amount_inr:.2f}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280">Payment date</td>
        <td style="padding:8px 0">{paid_at_str}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280">Payment ID</td>
        <td style="padding:8px 0;font-family:monospace;font-size:12px">{payment_id}</td>
      </tr>
      <tr>
        <td style="padding:8px 0;color:#6b7280">Order ID</td>
        <td style="padding:8px 0;font-family:monospace;font-size:12px">{order_id}</td>
      </tr>
      <tr style="border-top:1px solid #e5e7eb">
        <td style="padding:12px 0 8px;font-weight:600">New wallet balance</td>
        <td style="padding:12px 0 8px;font-weight:700;color:#059669">₹{new_balance_inr:.2f}</td>
      </tr>
    </table>

    <p>
      You can view your full payment history and download cost reports from the
      <a href="{settings.APP_BASE_URL}/settings/billing">Billing page</a>.
    </p>

    <p style="color:#6b7280;font-size:12px;">
      Payment processed via Razorpay. This is a payment confirmation.
      A GST-compliant tax invoice will be issued separately once our GSTIN is registered.
      Keep this email as your payment record.
    </p>

    <p>— DokyDoc Billing</p>
    """

    return _send(to_email, subject, textwrap.dedent(html))
```

### Step 2 — Add SMTP settings to `config.py`

In `backend/app/core/config.py`, add after the existing settings:

```python
# Email / SMTP settings (G7)
SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
SMTP_PORT: int = Field(default=465, env="SMTP_PORT")
SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
SMTP_USER: str = Field(default="", env="SMTP_USER")
SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
EMAIL_FROM: str = Field(default="billing@dokydoc.com", env="EMAIL_FROM")
APP_BASE_URL: str = Field(default="https://app.dokydoc.com", env="APP_BASE_URL")
```

Add to `.env.example`:
```bash
# Email (G7)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USE_TLS=true
SMTP_USER=billing@dokydoc.com
SMTP_PASSWORD=your_app_password_here
EMAIL_FROM=billing@dokydoc.com
APP_BASE_URL=https://app.dokydoc.com
```

### Step 3 — Wire `send_low_balance_email()` into B4

In `backend/app/services/billing_enforcement_service.py`, update
`_maybe_send_low_balance_alert()` (currently logs only):

```python
def _maybe_send_low_balance_alert(self, db: Session, billing, combined_balance: float) -> None:
    """Send one low-balance email per 24h per tenant. G7 implements the actual send."""
    from datetime import datetime, timedelta

    last_alert = getattr(billing, "last_low_balance_alert_at", None)
    if last_alert and (datetime.now() - last_alert) < timedelta(hours=24):
        return   # Throttled — already sent within 24h

    threshold = float(getattr(billing, "low_balance_threshold", 100.0))
    logger.info(
        f"[billing_alert] tenant_id={billing.tenant_id} "
        f"combined=₹{combined_balance}, threshold=₹{threshold}"
    )

    # G7 addition: actually send the email
    from app.services.email_service import send_low_balance_email
    from app.models.tenant import Tenant

    tenant = db.query(Tenant).filter(Tenant.id == billing.tenant_id).first()
    if tenant:
        # Use the tenant's billing contact email (admin user's email as proxy)
        # TODO: add a `billing_contact_email` field to tenant_billing in a future migration
        billing_email = getattr(billing, "billing_contact_email", None)
        if not billing_email:
            # Fallback: query for the admin user of this tenant
            from app.models.user import User
            admin = (
                db.query(User)
                .filter(User.tenant_id == billing.tenant_id, User.role == "admin")
                .first()
            )
            billing_email = admin.email if admin else None

        if billing_email:
            send_low_balance_email(
                to_email=billing_email,
                tenant_name=tenant.name,
                current_balance_inr=combined_balance,
                threshold_inr=threshold,
            )

    billing.last_low_balance_alert_at = datetime.now()
    db.add(billing)
    # Note: caller commits the transaction; do not commit here
```

### Step 4 — Wire `send_payment_receipt()` into C3 and C4

**In C3 (`verify_payment` endpoint)** — add after the wallet credit succeeds:

```python
# After wallet_service.credit_wallet() call in C3:
if credit_result["credited"]:
    from app.services.email_service import send_payment_receipt
    from app.models.tenant import Tenant
    from datetime import datetime

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    new_balance = wallet_service.get_balance(db, tenant_id=tenant_id)

    # Get billing contact email (same logic as G7 Step 3)
    billing_email = _get_billing_contact_email(db, tenant_id)
    if billing_email and tenant:
        send_payment_receipt(
            to_email=billing_email,
            tenant_name=tenant.name,
            amount_inr=float(order.amount_inr),
            payment_id=body.razorpay_payment_id,
            order_id=body.razorpay_order_id,
            new_balance_inr=new_balance["wallet_balance_inr"],
            paid_at=datetime.now(),
        )
```

**In C4 (webhook handler)** — same addition after the wallet credit. Use the same
idempotency check: if `credit_result["already_processed"]` is true, the email was
already sent by C3. Only send if `credit_result["credited"]` is true.

**Helper function** (add to `billing.py` as a module-level private function):

```python
def _get_billing_contact_email(db: Session, tenant_id: int) -> str | None:
    """
    Find the billing contact email for a tenant.
    Priority: billing_contact_email on tenant_billing → admin user email → None.
    """
    from app.models.user import User
    billing = crud.tenant_billing.get_or_create(db, tenant_id=tenant_id)
    if getattr(billing, "billing_contact_email", None):
        return billing.billing_contact_email
    admin = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.role == "admin")
        .first()
    )
    return admin.email if admin else None
```

### Step 5 — Future: `billing_contact_email` column

Add to the technical backlog (not Phase 9 scope):

```
FUTURE MIGRATION: Add `billing_contact_email` nullable column to `tenant_billing`.
Allows ops to set a dedicated billing email (e.g., finance@acme.com) separate from
the admin user email. Until this exists, `_get_billing_contact_email()` falls back
to the admin user email.
```

### Acceptance Criteria

**Low balance email (Track A):**
- [ ] `send_low_balance_email()` is called when `combined_balance < low_balance_threshold`
- [ ] Email is sent max once per 24 hours per tenant (`last_low_balance_alert_at` throttle)
- [ ] Email contains current balance, threshold, and link to Billing page
- [ ] If SMTP is misconfigured, `_send()` returns `False` and logs the error — billing flow NOT blocked
- [ ] `_maybe_send_low_balance_alert()` does not commit the DB session itself

**Payment receipt email (Track B — fires only after Razorpay payment):**
- [ ] Email sent from C3 after successful payment verification (not from C4 if C3 already sent)
- [ ] Email sent from C4 only if C3 did not process first (`credit_result["credited"]`)
- [ ] Email contains amount, payment ID, order ID, new balance, and payment date
- [ ] If email fails, payment is still credited — `_send()` is never in the critical path
- [ ] HTML is valid and renders correctly in Gmail, Outlook, and Apple Mail
- [ ] `to_email` resolves via admin user fallback when `billing_contact_email` is not set

**Config:**
- [ ] App starts when `SMTP_USER` and `SMTP_PASSWORD` are empty (test/dev environment)
- [ ] `APP_BASE_URL` appears correctly in email links

---


---

## Part G Summary

| Ticket | Gap Fixed | Files Changed | Priority | Track | Est. LOC |
|--------|-----------|---------------|----------|-------|---------|
| G1 | WalletState ↔ C5 API contract | `schemas/billing.py`, `billing.py` (endpoint), `types/billing.ts`, `contexts/BillingContext.tsx` | P0 | A | ~45 |
| G2 | LOW_BALANCE_THRESHOLD hardcode | (Covered by G1) | P1 | A | 0 |
| G3 | Claude pricing in PRICING_REGISTRY | `services/cost_service.py` | P0 | A | ~30 |
| G4 | MODEL_REGISTRY wrong model IDs | `constants/models.ts` | P0 | A | ~25 |
| G5 | Cost preview modal → Track A | `components/billing/CostPreviewModal.tsx` | P1 | A | ~40 |
| G6 | InsufficientFundsModal + 402 interceptor | `components/billing/InsufficientFundsModal.tsx` (new), `components/billing/InsufficientFundsProvider.tsx` (new), `api/client.ts` (interceptor), `billing_enforcement_service.py` (error body) | P1 | A | ~130 |
| G7 | Low balance + GST invoice emails | `services/email_service.py` (new), `core/config.py`, `billing_enforcement_service.py`, `billing.py` (C3/C4) | P1 | A+B | ~160 |

### Part G Execution Order

Execute G-tickets in this order. All P0s before any P1s.

```
G3 (Claude pricing in backend)       ← independent, do first
G4 (Fix frontend model IDs)          ← independent, do first (parallel with G3)
  ↓
G1 (Fix API contract: backend + FE)  ← after G3/G4 to avoid re-touching files
  ↓
G2 (covered by G1 — no extra work)
  ↓
G5 (Cost preview → Track A)          ← after G1 (needs correct WalletState type)
G6 (InsufficientFundsModal)          ← after G1 (needs correct WalletState type)
  ↓
G7 (Email service + wiring)          ← after G1 (uses billing schema from G1 endpoint)
```

### What `PHASE_9_STRATEGY.md` Promises vs What Now Ships

After Part G is complete, every promise in the strategy is implemented:

| Strategy Promise | Implemented In |
|---|---|
| "₹100 free credit on signup" | B5 (wallet seeding) |
| "Cost preview before every analysis" | G5 (E5 moved to Track A) |
| "Exact cost shown after analysis" | E6 (CostReceiptDrawer) |
| "15% markup transparent on every receipt" | B1 (CostBreakdown) + E6 |
| "Free lane = Gemini 3 Flash-Lite" | B2 (ModelSelector), G4 (correct ID) |
| "Paid lane = Gemini 3 Flash, Claude Sonnet 4.6, Claude Haiku 4.5" | B2 + G3 (pricing) + G4 (IDs) |
| "When wallet < ₹100, send reminder email" | G7 (send_low_balance_email) |
| "Recharge via UPI, cards, net banking" | C1–C4 (Razorpay, Track B) |
| "GST-compliant invoice after payment" | G7 (send_payment_receipt, Track B) |
| "When wallet empty, friendly modal not raw error" | G6 (InsufficientFundsModal) |
| "Download costs: CSV, PDF, JSON, DOCX" | D1 + D2 |
| "Demo org for sales calls" | D3 |
| "Export broken down by user, model, day" | D1 (ExportDataset) |

### Remaining Technical Debt (not in Phase 9)

Logged for future phases:

1. **`billing_contact_email` column** — Add to `tenant_billing` so ops can set a dedicated finance email (G7 Step 5)
2. **`free_credit_total_inr` column** — Add to `tenants` (referenced in G1 as `getattr` fallback; currently hardcoded to 100.0)
3. **Celery async email** — If SMTP latency is noticed in production, move G7 sends to Celery tasks
4. **True GST invoice PDF** — After GSTIN registered, replace payment confirmation email with a GSTIN-compliant tax invoice (HSN code, IGST/CGST/SGST split). Mark `send_payment_receipt()` with a `# TODO: GST invoice` comment as a migration target.
5. **Retry logic in `_send()`** — Currently tries once and logs on failure. Add 1 retry with 2s delay for transient SMTP errors.

---

*End of PHASE_9_IMPLEMENTATION_PLAN.md*

