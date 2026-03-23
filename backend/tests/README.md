# Backend Tests

Automated tests for DokyDoc backend API.

## Running Tests

### Run all tests
```bash
cd backend
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_user_management.py -v
```

### Run specific test class
```bash
pytest tests/test_user_management.py::TestInviteUser -v
```

### Run with coverage report
```bash
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

### Run and stop on first failure
```bash
pytest tests/ -x
```

## Writing New Tests

1. Create test file in `tests/` directory with `test_` prefix
2. Use fixtures from `conftest.py`:
   - `client`: FastAPI test client
   - `db_session`: Test database session
   - `test_tenant`: Test tenant object
   - `test_admin_user`: Admin user
   - `test_developer_user`: Developer user
   - `admin_token`: JWT token for admin
   - `auth_headers`: Authorization headers

3. Example:
```python
def test_my_feature(client, auth_headers):
    response = client.get("/api/v1/endpoint", headers=auth_headers)
    assert response.status_code == 200
```

## Test Organization

- `conftest.py`: Shared fixtures and configuration
- `test_user_management.py`: User/tenant CRUD operations
- `test_auth.py`: Authentication and authorization
- `test_documents.py`: Document management
- `test_tasks.py`: Task management
- `test_permissions.py`: RBAC permissions

## CI/CD Integration

Tests run automatically on:
- Pull request creation
- Commits to main branch
- Before deployment

## Coverage Goals

- Overall: 80%+
- Critical paths (auth, multi-tenancy): 95%+
- New features: 100%
