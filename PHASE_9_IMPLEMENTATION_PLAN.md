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
