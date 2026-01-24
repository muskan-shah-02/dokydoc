"""
Data validation script for Sprint 2 tenant migration.

This script validates data integrity BEFORE adding foreign key constraints.
Run this before executing: alembic upgrade head

Usage:
    python scripts/validate_tenant_migration.py
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("validate_migration")

# All tables with tenant_id that need FK constraints
TENANT_TABLES = [
    'users',
    'documents',
    'document_segments',
    'analysisresult',
    'analysis_runs',
    'consolidated_analyses',
    'code_components',
    'document_code_links',
    'mismatches',
    'initiatives',
    'initiative_assets',
    'ontology_concepts',
    'ontology_relationships',
    'tenant_billing'
]


def validate_tenant_data():
    """
    Validate data integrity before adding FK constraints.

    Checks:
    1. No NULL tenant_id values
    2. No orphaned tenant_id references
    3. tenant_id column exists in all tables

    Returns:
        bool: True if validation passes, False otherwise
    """
    logger.info("=" * 80)
    logger.info("SPRINT 2 TENANT MIGRATION VALIDATION")
    logger.info("=" * 80)

    # Create database engine
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    issues = []
    warnings = []

    with engine.connect() as conn:
        # Check if tenants table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'tenants'
            )
        """))
        tenants_table_exists = result.scalar()

        if not tenants_table_exists:
            logger.warning("⚠️  Tenants table does not exist yet (will be created by migration)")
            warnings.append("Tenants table will be created by migration")

        # Validate each table
        for table in TENANT_TABLES:
            logger.info(f"\nValidating table: {table}")

            # Check if table exists
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = '{table}'
                )
            """))
            table_exists = result.scalar()

            if not table_exists:
                logger.warning(f"  ⚠️  Table '{table}' does not exist")
                warnings.append(f"Table '{table}' does not exist")
                continue

            # Check if tenant_id column exists
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = 'tenant_id'
                )
            """))
            has_tenant_id = result.scalar()

            if not has_tenant_id:
                logger.error(f"  ❌ Table '{table}' is missing tenant_id column")
                issues.append(f"Table '{table}' is missing tenant_id column")
                continue

            # Check for NULL tenant_id values
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))
            null_count = result.scalar()

            if null_count > 0:
                logger.error(f"  ❌ {null_count} rows have NULL tenant_id")
                issues.append(f"Table '{table}' has {null_count} rows with NULL tenant_id")
            else:
                logger.info(f"  ✅ No NULL tenant_id values")

            # Check for orphaned tenant_id references (only if tenants table exists)
            if tenants_table_exists:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE tenant_id NOT IN (SELECT id FROM tenants)
                """))
                orphan_count = result.scalar()

                if orphan_count > 0:
                    logger.error(f"  ❌ {orphan_count} rows have orphaned tenant_id references")
                    issues.append(f"Table '{table}' has {orphan_count} orphaned tenant_id references")
                else:
                    logger.info(f"  ✅ No orphaned tenant_id references")

            # Get row count
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            row_count = result.scalar()
            logger.info(f"  📊 Total rows: {row_count}")

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 80)

    if warnings:
        logger.info(f"\n⚠️  Warnings ({len(warnings)}):")
        for warning in warnings:
            logger.info(f"  - {warning}")

    if issues:
        logger.error(f"\n❌ VALIDATION FAILED ({len(issues)} issues):")
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("\nFix these issues before running migration:")
        logger.error("  1. Backfill NULL tenant_id values: UPDATE <table> SET tenant_id = 1 WHERE tenant_id IS NULL")
        logger.error("  2. Clean up orphaned references")
        return False
    else:
        logger.info("\n✅ VALIDATION PASSED - Safe to run migration!")
        logger.info("\nNext steps:")
        logger.info("  1. Run: cd backend && alembic upgrade head")
        logger.info("  2. Verify migration: SELECT COUNT(*) FROM tenants;")
        return True


if __name__ == "__main__":
    success = validate_tenant_data()
    sys.exit(0 if success else 1)
