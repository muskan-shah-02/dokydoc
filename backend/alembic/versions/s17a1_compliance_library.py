"""
Phase 6: Compliance Library — compliance_frameworks + tenant_compliance_selections.

Seeded with 15 global/regional regulatory frameworks keyed to industries.

Revision ID: s17a1
Revises: s16f1
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

revision = 's17a1'
down_revision = 's16f1'
branch_labels = None
depends_on = None

# ─── System framework seed data ──────────────────────────────────────────────

SYSTEM_FRAMEWORKS = [
    ("PCI-DSS",  "Payment Card Industry Data Security Standard",
     "Financial Security", "Global",
     ["fintech/payments", "banking", "ecommerce"],
     "Mandates controls for organisations that handle cardholder data: encryption, access control, vulnerability management, and network segmentation."),
    ("GDPR",     "General Data Protection Regulation",
     "Data Privacy", "EU",
     ["fintech/payments", "fintech/lending", "banking", "healthcare", "saas", "ecommerce", "logistics", "devtools"],
     "EU regulation on data protection and privacy for individuals within the EU/EEA. Requires lawful basis for processing, data minimisation, and breach notification."),
    ("HIPAA",    "Health Insurance Portability and Accountability Act",
     "Healthcare Compliance", "US",
     ["healthcare", "pharma"],
     "US law requiring safeguards for Protected Health Information (PHI). Covers Privacy Rule, Security Rule, and Breach Notification Rule."),
    ("SOC2",     "SOC 2 Type II",
     "Security & Trust", "Global",
     ["saas", "fintech/payments", "devtools", "fintech/lending", "banking"],
     "AICPA trust services framework assessing controls across Security, Availability, Processing Integrity, Confidentiality, and Privacy."),
    ("ISO27001", "ISO/IEC 27001 — Information Security Management",
     "Security & Trust", "Global",
     ["saas", "fintech/payments", "banking", "devtools", "healthcare"],
     "International standard for establishing, implementing, maintaining and improving an Information Security Management System (ISMS)."),
    ("SOX",      "Sarbanes-Oxley Act",
     "Financial Reporting", "US",
     ["banking", "fintech/lending", "fintech/payments"],
     "US federal law setting requirements for financial record keeping and reporting for public companies. Section 404 mandates internal controls over financial reporting."),
    ("CCPA",     "California Consumer Privacy Act",
     "Data Privacy", "US",
     ["saas", "ecommerce", "fintech/payments", "healthcare", "devtools"],
     "California law granting consumers rights over their personal data: right to know, delete, opt-out of sale, and non-discrimination."),
    ("PSD2",     "Payment Services Directive 2",
     "Financial Regulation", "EU",
     ["fintech/payments", "banking"],
     "EU directive regulating payment services and payment service providers. Mandates Strong Customer Authentication (SCA) and Open Banking APIs."),
    ("DORA",     "Digital Operational Resilience Act",
     "Financial Regulation", "EU",
     ["fintech/payments", "fintech/lending", "banking"],
     "EU regulation requiring financial entities to manage ICT risks, test operational resilience, and report major ICT-related incidents."),
    ("FCA",      "FCA Consumer Duty",
     "Financial Regulation", "UK",
     ["fintech/payments", "fintech/lending", "banking"],
     "UK FCA rules requiring firms to deliver good outcomes for retail customers across products, price, service, and communications."),
    ("RBI",      "RBI Guidelines for Payment Systems",
     "Financial Regulation", "India",
     ["fintech/payments", "banking"],
     "Reserve Bank of India guidelines covering payment aggregators, wallets, KYC/AML, data localisation, and cybersecurity controls."),
    ("SWIFT-CSP","SWIFT Customer Security Programme",
     "Financial Security", "Global",
     ["banking", "fintech/payments"],
     "Mandatory security controls for SWIFT messaging infrastructure users, covering access control, credential management, and cyber incident response."),
    ("NIST-CSF", "NIST Cybersecurity Framework",
     "Security & Trust", "US",
     ["saas", "devtools", "healthcare", "fintech/payments", "banking"],
     "NIST framework organising cybersecurity activities into five functions: Identify, Protect, Detect, Respond, Recover."),
    ("MiFID2",   "Markets in Financial Instruments Directive II",
     "Financial Regulation", "EU",
     ["banking", "fintech/payments"],
     "EU legislation regulating investment services: best execution, transaction reporting, systematic internaliser regime, and investor protection."),
    ("Basel3",   "Basel III Capital Requirements",
     "Financial Regulation", "Global",
     ["banking"],
     "International banking accord setting minimum capital requirements, leverage ratios, and liquidity standards for banks."),
]


def upgrade():
    # ── compliance_frameworks ──────────────────────────────────────────────────
    op.create_table(
        'compliance_frameworks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('geography', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('applicable_industries', postgresql.JSONB(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'tenant_id', name='uq_compliance_code_tenant'),
    )
    op.create_index('ix_compliance_frameworks_code', 'compliance_frameworks', ['code'])
    op.create_index('ix_compliance_frameworks_category', 'compliance_frameworks', ['category'])
    op.create_index('ix_compliance_frameworks_tenant_id', 'compliance_frameworks', ['tenant_id'])

    # ── tenant_compliance_selections ───────────────────────────────────────────
    op.create_table(
        'tenant_compliance_selections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('framework_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('selected_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['framework_id'], ['compliance_frameworks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'framework_id', name='uq_tenant_framework'),
    )
    op.create_index('ix_tenant_compliance_tenant_id', 'tenant_compliance_selections', ['tenant_id'])

    # ── Seed system frameworks ─────────────────────────────────────────────────
    now = datetime.utcnow().isoformat()
    from sqlalchemy.sql import text
    conn = op.get_bind()
    for code, name, category, geography, industries, description in SYSTEM_FRAMEWORKS:
        import json
        conn.execute(
            text(
                "INSERT INTO compliance_frameworks "
                "(code, name, category, geography, description, applicable_industries, is_system, tenant_id, created_at) "
                "VALUES (:code, :name, :category, :geography, :description, :industries, true, NULL, :now)"
            ),
            {"code": code, "name": name, "category": category, "geography": geography,
             "description": description, "industries": json.dumps(industries), "now": now}
        )


def downgrade():
    op.drop_index('ix_tenant_compliance_tenant_id')
    op.drop_table('tenant_compliance_selections')
    op.drop_index('ix_compliance_frameworks_tenant_id')
    op.drop_index('ix_compliance_frameworks_category')
    op.drop_index('ix_compliance_frameworks_code')
    op.drop_table('compliance_frameworks')
