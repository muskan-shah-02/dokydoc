"""
Pytest configuration and fixtures for backend tests.

This file provides reusable test fixtures like test database,
test client, and authenticated users.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base_class import Base
from app.db.session import get_db
from main import app

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def test_tenant(db_session):
    """Create a test tenant."""
    from app.models.tenant import Tenant
    
    tenant = Tenant(
        name="Test Company",
        subdomain="testco",
        status="active",
        tier="professional",
        billing_type="prepaid",
        max_users=10,
        max_documents=100,
        settings={}
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant

@pytest.fixture
def test_admin_user(db_session, test_tenant):
    """Create a test admin user."""
    from app.models.user import User
    from app.core.security import get_password_hash
    
    user = User(
        email="admin@testco.com",
        hashed_password=get_password_hash("Test123!"),
        roles=["CXO"],
        is_active=True,
        is_superuser=False,
        tenant_id=test_tenant.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_developer_user(db_session, test_tenant):
    """Create a test developer user."""
    from app.models.user import User
    from app.core.security import get_password_hash
    
    user = User(
        email="developer@testco.com",
        hashed_password=get_password_hash("Test123!"),
        roles=["Developer"],
        is_active=True,
        is_superuser=False,
        tenant_id=test_tenant.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def admin_token(client, test_admin_user):
    """Get access token for admin user."""
    response = client.post(
        "/api/login/access-token",
        data={
            "username": test_admin_user.email,
            "password": "Test123!"
        }
    )
    return response.json()["access_token"]

@pytest.fixture
def developer_token(client, test_developer_user):
    """Get access token for developer user."""
    response = client.post(
        "/api/login/access-token",
        data={
            "username": test_developer_user.email,
            "password": "Test123!"
        }
    )
    return response.json()["access_token"]

@pytest.fixture
def auth_headers(admin_token):
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}
