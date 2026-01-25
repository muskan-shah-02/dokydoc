"""
Sprint 1 & 2 Integration Tests - Pytest Configuration & Fixtures
Provides shared test fixtures for database, API client, authentication, multi-tenancy, etc.

SPRINT 2 Phase 7: Added multi-tenant fixtures for comprehensive testing.
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
from app import crud, schemas, models
from app.core.security import get_password_hash
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.user import Role


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


# SPRINT 2 Phase 7: Multi-Tenancy Fixtures

@pytest.fixture(scope="function")
def tenant_a(db_session: Session) -> Tenant:
    """Create test tenant A."""
    tenant = Tenant(
        name="Acme Corp",
        subdomain="acme",
        max_users=10,
        max_documents=100,
        max_code_components=50
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture(scope="function")
def tenant_b(db_session: Session) -> Tenant:
    """Create test tenant B."""
    tenant = Tenant(
        name="Beta Inc",
        subdomain="beta",
        max_users=10,
        max_documents=100,
        max_code_components=50
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture(scope="function")
def cxo_user_a(db_session: Session, tenant_a: Tenant) -> User:
    """Create CXO user in tenant A (admin)."""
    user = User(
        email="cxo@acme.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.CXO.value],
        is_superuser=False,
        tenant_id=tenant_a.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def developer_user_a(db_session: Session, tenant_a: Tenant) -> User:
    """Create Developer user in tenant A."""
    user = User(
        email="dev@acme.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.DEVELOPER.value],
        is_superuser=False,
        tenant_id=tenant_a.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def ba_user_a(db_session: Session, tenant_a: Tenant) -> User:
    """Create BA user in tenant A."""
    user = User(
        email="ba@acme.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.BA.value],
        is_superuser=False,
        tenant_id=tenant_a.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def pm_user_a(db_session: Session, tenant_a: Tenant) -> User:
    """Create Product Manager user in tenant A."""
    user = User(
        email="pm@acme.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.PRODUCT_MANAGER.value],
        is_superuser=False,
        tenant_id=tenant_a.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def cxo_user_b(db_session: Session, tenant_b: Tenant) -> User:
    """Create CXO user in tenant B (admin)."""
    user = User(
        email="cxo@beta.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.CXO.value],
        is_superuser=False,
        tenant_id=tenant_b.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def developer_user_b(db_session: Session, tenant_b: Tenant) -> User:
    """Create Developer user in tenant B."""
    user = User(
        email="dev@beta.com",
        hashed_password=get_password_hash("password123"),
        roles=[Role.DEVELOPER.value],
        is_superuser=False,
        tenant_id=tenant_b.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def get_user_token(client: TestClient):
    """Factory function to get auth token for any user."""
    def _get_token(email: str, password: str = "password123") -> dict:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        assert response.status_code == 200, f"Login failed for {email}: {response.text}"
        return response.json()
    return _get_token


@pytest.fixture(scope="function")
def cxo_a_token(client: TestClient, cxo_user_a: User, get_user_token) -> dict:
    """Get auth token for CXO user A."""
    return get_user_token(cxo_user_a.email)


@pytest.fixture(scope="function")
def developer_a_token(client: TestClient, developer_user_a: User, get_user_token) -> dict:
    """Get auth token for Developer user A."""
    return get_user_token(developer_user_a.email)


@pytest.fixture(scope="function")
def ba_a_token(client: TestClient, ba_user_a: User, get_user_token) -> dict:
    """Get auth token for BA user A."""
    return get_user_token(ba_user_a.email)


@pytest.fixture(scope="function")
def pm_a_token(client: TestClient, pm_user_a: User, get_user_token) -> dict:
    """Get auth token for PM user A."""
    return get_user_token(pm_user_a.email)


@pytest.fixture(scope="function")
def cxo_b_token(client: TestClient, cxo_user_b: User, get_user_token) -> dict:
    """Get auth token for CXO user B."""
    return get_user_token(cxo_user_b.email)


@pytest.fixture(scope="function")
def developer_b_token(client: TestClient, developer_user_b: User, get_user_token) -> dict:
    """Get auth token for Developer user B."""
    return get_user_token(developer_user_b.email)


@pytest.fixture(scope="function")
def auth_headers():
    """Factory function to create auth headers from token."""
    def _headers(token: dict) -> dict:
        return {"Authorization": f"Bearer {token['access_token']}"}
    return _headers
