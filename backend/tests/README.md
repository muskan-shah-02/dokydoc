# DokyDoc Integration Tests

## Overview

Comprehensive integration tests for Sprint 1 and Sprint 2 features:

### Sprint 1 Tests ✅
- BE-04/AUTH-01: Refresh Token Flow
- FLAW-10: Distributed Locks
- API-01: Rate Limiting
- BE-COST-01/02/03: Cost Tracking
- BE-01: Error Handling

### Sprint 2 Tests ✅ (Phase 7)
- **Tenant Isolation**: Data separation between tenants
- **RBAC Permissions**: Role-based access control
- **Billing Enforcement**: Balance checks and cost deduction
- **Cross-Tenant Security**: Security against cross-tenant access
- **Schrödinger's Document Pattern**: Information leakage prevention

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Specific Test File
```bash
# Sprint 1 tests
pytest tests/integration/test_auth_refresh_tokens.py -v
pytest tests/integration/test_distributed_locks.py -v

# Sprint 2 tests
pytest tests/integration/test_tenant_isolation.py -v
pytest tests/integration/test_rbac_permissions.py -v
pytest tests/integration/test_billing_enforcement.py -v
pytest tests/integration/test_cross_tenant_security.py -v
```

### With Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Run Only Sprint 2 Tests
```bash
pytest tests/integration/test_tenant_isolation.py \
       tests/integration/test_rbac_permissions.py \
       tests/integration/test_billing_enforcement.py \
       tests/integration/test_cross_tenant_security.py -v
```

## Test Structure

```
tests/
├── conftest.py                              # Shared fixtures (Sprint 1 & 2)
├── integration/
│   # Sprint 1 Tests
│   ├── test_auth_refresh_tokens.py          # BE-04/AUTH-01 tests
│   ├── test_distributed_locks.py            # FLAW-10 tests
│   ├── test_rate_limiting.py                # API-01 tests
│   ├── test_cost_tracking.py                # Cost calculation tests
│   ├── test_error_handling.py               # BE-01 error tests
│   # Sprint 2 Tests (Phase 7)
│   ├── test_tenant_isolation.py             # Tenant data isolation
│   ├── test_rbac_permissions.py             # Role-based access control
│   ├── test_billing_enforcement.py          # Billing checks & enforcement
│   └── test_cross_tenant_security.py        # Cross-tenant security
└── unit/                                     # Future unit tests
```

## Prerequisites

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

2. Set up test environment variables:
```bash
export SECRET_KEY="test-secret-key-for-testing-only"
export DATABASE_URL="sqlite:///:memory:"
export GEMINI_API_KEY="test-key"
```

3. Ensure Redis is running (for lock and rate limit tests):
```bash
docker-compose up redis
```

## Sprint 2 Test Coverage (Phase 7)

### Tenant Isolation Tests (test_tenant_isolation.py)
✅ **Document Isolation**
- Users cannot see documents from other tenants
- Cannot access other tenant documents by ID (404, not 403)

✅ **Code Component Isolation**
- Users cannot see code components from other tenants
- Cannot delete other tenant code components

✅ **Analysis Result Isolation**
- Cannot see analysis results from other tenants

✅ **Mismatch Isolation**
- Cannot see validation mismatches from other tenants

✅ **User Isolation**
- CXO can only see users in their own tenant
- Cannot modify other tenant user roles
- Cannot delete other tenant users

### RBAC Permission Tests (test_rbac_permissions.py)
✅ **CXO Permissions** (20 permissions - tenant admin)
- Can view, invite, manage, and delete users
- Can view and manage billing
- Cannot modify own roles (admin lockout prevention)
- Cannot delete self (admin lockout prevention)

✅ **Developer Permissions** (15 permissions)
- Can read/write documents and code
- Can view users and billing (read-only)
- Cannot invite users or manage roles
- Cannot manage billing

✅ **Business Analyst Permissions** (14 permissions)
- Can read/write documents
- Can run validation scans
- Can view code (read-only)
- Cannot write/delete code
- Cannot invite users

✅ **Product Manager Permissions** (10 permissions - mostly read-only)
- Can read/write documents (PRDs)
- Can view code (read-only)
- Cannot write/delete code
- Cannot manage users or billing

✅ **Permission Endpoint**
- Each role sees correct permissions via GET /users/me/permissions

### Billing Enforcement Tests (test_billing_enforcement.py)
✅ **Prepaid Billing**
- Can proceed with sufficient balance
- Blocked with insufficient balance (InsufficientBalanceException)
- Balance deducted after analysis
- Low balance alerts triggered correctly

✅ **Postpaid Billing**
- Can proceed within monthly limit
- Blocked when exceeding monthly limit (MonthlyLimitExceededException)
- Cost added to monthly total
- Unlimited if no monthly limit set

✅ **Monthly Rollover**
- Current month cost resets on 1st of month

✅ **Cost Estimation**
- Base cost: ₹2
- Scales with document size: ₹0.01/KB
- Max cap: ₹12 (₹2 base + ₹10 size)

✅ **Billing API**
- CXO can view usage and add balance
- Developer cannot add balance (no BILLING_MANAGE permission)
- Document analysis blocked when insufficient funds (HTTP 402)

### Cross-Tenant Security Tests (test_cross_tenant_security.py)
✅ **Cross-Tenant Document Security**
- Cannot create links to other tenant's documents
- Cannot create links to other tenant's code

✅ **Cross-Tenant Validation Security**
- Cannot run validation on other tenant's documents

✅ **Cross-Tenant User Security**
- Cannot list users from other tenants
- Cannot view other tenant user details

✅ **Cross-Tenant Billing Security**
- Cannot view other tenant's billing info

✅ **Schrödinger's Document Pattern**
- GET returns 404 (not 403) for other tenant's resources
- DELETE returns 404 (not 403) for other tenant's resources
- Prevents information leakage about resource existence

✅ **Tenant Limit Enforcement**
- Cannot exceed max_users limit
- Limits are tenant-specific (not global)

✅ **Background Task Security**
- Validation scan receives and uses tenant_id

✅ **Data Leakage Prevention**
- Error messages don't reveal existence in other tenants
- Generic "not found" instead of "forbidden"/"belongs to another tenant"

## Sprint 2 Multi-Tenant Fixtures (conftest.py)

### Tenants
- `tenant_a`: Acme Corp (subdomain: acme)
- `tenant_b`: Beta Inc (subdomain: beta)

### Tenant A Users
- `cxo_user_a`: CXO (cxo@acme.com) - tenant admin
- `developer_user_a`: Developer (dev@acme.com)
- `ba_user_a`: Business Analyst (ba@acme.com)
- `pm_user_a`: Product Manager (pm@acme.com)

### Tenant B Users
- `cxo_user_b`: CXO (cxo@beta.com) - tenant admin
- `developer_user_b`: Developer (dev@beta.com)

### Auth Tokens
- `cxo_a_token`, `developer_a_token`, `ba_a_token`, `pm_a_token`
- `cxo_b_token`, `developer_b_token`
- `auth_headers(token)`: Factory to create Authorization headers

## Test Design Principles

### Multi-Tenancy Testing
1. **Isolation First**: Always verify data cannot cross tenant boundaries
2. **Schrödinger's Document**: Use 404 (not 403) to prevent info leakage
3. **Tenant-Specific Limits**: Test limits are enforced per-tenant
4. **Background Tasks**: Verify tenant_id is passed to async operations

### RBAC Testing
1. **Positive Tests**: Verify each role CAN do what they should
2. **Negative Tests**: Verify each role CANNOT do what they shouldn't
3. **Admin Lockout Prevention**: Test self-modification safeguards
4. **Permission Inheritance**: Test roles have correct permission sets

### Security Testing
1. **Attack Vectors**: Test cross-tenant access attempts
2. **Information Leakage**: Verify error messages don't reveal data
3. **Privilege Escalation**: Test users can't elevate own permissions
4. **Data Integrity**: Verify operations don't affect other tenants

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: |
    pytest tests/ --cov=app --cov-report=xml --cov-report=term
    
- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Notes

- Tests use in-memory SQLite database
- Some tests require Redis (will skip gracefully if unavailable)
- Rate limit tests may be flaky due to time windows
- Tests are designed to be idempotent and isolated
- Each test gets a fresh database (function-scoped fixtures)

## Test Statistics

### Sprint 1 Tests
- **5 test files**, ~50 test cases
- **Coverage**: Authentication, locks, rate limiting, cost tracking, errors

### Sprint 2 Tests (Phase 7)
- **4 test files**, ~80 test cases
- **Coverage**: Tenant isolation, RBAC, billing, cross-tenant security

### Total
- **9 test files**, ~130 test cases
- **Estimated run time**: 30-60 seconds (without Redis: ~10 seconds)

## Future Enhancements

- [ ] Unit tests for individual services
- [ ] End-to-end document processing tests
- [ ] Performance/load tests
- [ ] Security penetration tests
- [ ] Mock Gemini API for faster tests
- [ ] Background task integration tests with Celery workers
- [ ] Database migration tests
- [ ] API contract tests (OpenAPI validation)
