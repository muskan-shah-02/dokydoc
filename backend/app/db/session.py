from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# create_engine is the entry point to the database.
# It's configured with the database URL from our settings.
# The "pool_pre_ping=True" argument helps prevent database connection errors.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# A sessionmaker is a factory for creating new Session objects.
# It's configured to work with our engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
