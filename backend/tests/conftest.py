"""
Sprint 1 Integration Tests - Pytest Configuration & Fixtures
Provides shared test fixtures for database, API client, authentication, etc.
"""
import pytest
import os
import sys
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import crud, schemas
from app.core.security import get_password_hash
from app.models.user import User


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh database engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user_in = schemas.user.UserCreate(
        email="test@example.com",
        password="testpassword123",
        full_name="Test User",
        roles=["user"]
    )

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        roles=user_in.roles,
        tenant_id=1  # Default tenant
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session: Session) -> User:
    """Create a test admin user."""
    user_in = schemas.user.UserCreate(
        email="admin@example.com",
        password="adminpassword123",
        full_name="Admin User",
        roles=["admin", "user"]
    )

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        roles=user_in.roles,
        tenant_id=1
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def user_token(client: TestClient, test_user: User) -> dict:
    """Get authentication tokens for test user."""
    response = client.post(
        "/login/access-token",
        data={"username": test_user.email, "password": "testpassword123"}
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="function")
def admin_token(client: TestClient, admin_user: User) -> dict:
    """Get authentication tokens for admin user."""
    response = client.post(
        "/login/access-token",
        data={"username": admin_user.email, "password": "adminpassword123"}
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="function")
def authorized_client(client: TestClient, user_token: dict) -> TestClient:
    """Create a client with authorization headers."""
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {user_token['access_token']}"
    }
    return client
