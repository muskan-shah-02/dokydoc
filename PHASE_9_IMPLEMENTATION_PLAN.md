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
