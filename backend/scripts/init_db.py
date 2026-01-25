"""
Initialize database with all tables directly from SQLAlchemy models.

Use this for fresh database setup instead of migrations.
After running this, mark migrations as applied with: alembic stamp head
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import engine
from app.core.logging import get_logger

logger = get_logger("init_db")

def init_db():
    """Create all tables from SQLAlchemy models."""
    logger.info("Creating all database tables...")
    
    # This creates ALL tables defined in models
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ All tables created successfully!")
    logger.info("Tables created:")
    for table in Base.metadata.sorted_tables:
        logger.info(f"  - {table.name}")
    
    logger.info("\n📝 Next steps:")
    logger.info("1. Mark migrations as applied: docker-compose run --rm app alembic stamp head")
    logger.info("2. Run initial data script: docker-compose exec app python initial_data.py")
    logger.info("3. Start all services: docker-compose up -d")

if __name__ == "__main__":
    init_db()
