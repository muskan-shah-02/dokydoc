import logging
from app.db.session import engine
from app.db.base_class import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db() -> None:
    # Create all tables in the database.
    # This is equivalent to "Create Table" statements in raw SQL.
    logger.info("Creating initial database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

if __name__ == "__main__":
    init_db()

