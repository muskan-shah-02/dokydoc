#!/usr/bin/env python3
"""
Initialize Database - Create all tables directly from SQLAlchemy models

This script bypasses Alembic migrations and creates all tables directly
from the current SQLAlchemy model definitions. This is the recommended
approach for fresh installations to avoid migration chain issues.

Usage:
    docker-compose run --rm app python scripts/init_db.py

After running this script, use:
    docker-compose run --rm app alembic stamp head

to mark all migrations as applied.
"""

import sys
import logging
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import engine
from app.db.base import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Create all tables from SQLAlchemy models.

    This uses Base.metadata.create_all() which:
    1. Reads all model definitions from app.db.base
    2. Creates tables with current schema (including tenant_id)
    3. Creates indexes, constraints, and foreign keys
    4. Is idempotent (safe to run multiple times)
    """
    logger.info("Starting database initialization...")
    logger.info(f"Database URL: {engine.url.render_as_string(hide_password=True)}")

    try:
        # Create all tables
        logger.info("Creating all tables from SQLAlchemy models...")
        Base.metadata.create_all(bind=engine)

        logger.info("✅ All tables created successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Mark migrations as applied: docker-compose run --rm app alembic stamp head")
        logger.info("2. Create default data: docker-compose exec app python initial_data.py")
        logger.info("3. Start all services: docker-compose up -d")

    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise


if __name__ == "__main__":
    init_db()
