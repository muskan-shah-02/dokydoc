from typing import Generator, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("database")

# Enhanced database engine with connection pooling and monitoring
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections every hour
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    future=True,          # Use SQLAlchemy 2.0 features
)

# Session factory with configuration
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Keep objects accessible after commit
)

# Database health check and monitoring
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance."""
    if "sqlite" in settings.DATABASE_URL.lower():
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log connection checkout for monitoring."""
    logger.debug("Database connection checked out")

@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Log connection checkin for monitoring."""
    logger.debug("Database connection checked in")

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Automatically handles session lifecycle and error handling.
    """
    db = SessionLocal()
    try:
        logger.debug("Database session created")
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in database session: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("Database session closed")

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Useful for non-FastAPI contexts.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Error in database context: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def check_database_health() -> bool:
    """
    Check if the database is accessible and healthy.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        with engine.connect() as connection:
            # Execute a simple query to test connectivity
            connection.execute(text("SELECT 1"))
        logger.debug("Database health check passed")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

def get_database_info() -> dict:
    """
    Get information about the database connection.
    
    Returns:
        dict: Database connection information
    """
    try:
        with engine.connect() as connection:
            # Get database version
            if "postgresql" in settings.DATABASE_URL.lower():
                version = connection.execute(text("SELECT version()")).scalar()
            elif "sqlite" in settings.DATABASE_URL.lower():
                version = connection.execute(text("SELECT sqlite_version()")).scalar()
            else:
                version = "Unknown"
            
            # Get connection pool status
            pool = engine.pool
            pool_info = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow()
            }
            
            return {
                "status": "healthy" if check_database_health() else "unhealthy",
                "database_type": "postgresql" if "postgresql" in settings.DATABASE_URL.lower() else "sqlite",
                "version": version,
                "pool_info": pool_info,
                "url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local"
            }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def close_database_connections():
    """Close all database connections. Useful for graceful shutdown."""
    try:
        engine.dispose()
        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

# Initialize database on startup
def init_database():
    """Initialize database connection, create tables, and verify connectivity."""
    try:
        if check_database_health():
            logger.info("Database connection established successfully")
            
            # Create all tables if they don't exist
            from app.db.base_class import Base
            from app.models import (
                User, Document, DocumentCodeLink, CodeComponent,
                Mismatch, AnalysisResult, DocumentSegment
            )
            
            logger.info("Creating database tables if they don't exist...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified successfully")
            
            # Log database information
            db_info = get_database_info()
            logger.info(f"Database info: {db_info}")
            
            return True
        else:
            logger.error("Failed to establish database connection")
            return False
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

# Export the main dependency
__all__ = ["get_db", "get_db_context", "check_database_health", "get_database_info", "init_database", "close_database_connections"]
