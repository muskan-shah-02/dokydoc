from sqlalchemy.orm import declarative_base

# declarative_base() returns a class that all our models will inherit from.
# It's the central point for SQLAlchemy's ORM mapping.
Base = declarative_base()
