# Sprint 1 Integration Tests

## Overview

Comprehensive integration tests for Sprint 1 features:
- ✅ BE-04/AUTH-01: Refresh Token Flow
- ✅ FLAW-10: Distributed Locks
- ✅ API-01: Rate Limiting
- ✅ BE-COST-01/02/03: Cost Tracking
- ✅ BE-01: Error Handling

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Specific Test File
```bash
pytest tests/integration/test_auth_refresh_tokens.py -v
```

### With Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── integration/
│   ├── test_auth_refresh_tokens.py     # BE-04/AUTH-01 tests
│   ├── test_distributed_locks.py        # FLAW-10 tests
│   ├── test_rate_limiting.py            # API-01 tests
│   ├── test_cost_tracking.py            # Cost calculation tests
│   └── test_error_handling.py           # BE-01 error tests
└── unit/                                 # Future unit tests
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

## Test Coverage

### Authentication & Authorization
- Login with refresh token
- Token refresh endpoint
- Token type validation
- Invalid token handling

### Distributed Locks
- Lock acquisition and release
- Concurrent access prevention
- Lock expiration
- Context manager usage
- Document processing locks
- Tenant billing locks

### Rate Limiting
- Login rate limits (5/min, 20/hour)
- Upload rate limits (10/min, 50/hour)
- Per-user vs global limits
- Rate limit error responses

### Cost Tracking
- Token counting accuracy
- Cost calculation for input/output
- Gemini pricing accuracy (Jan 2025)
- Exchange rate reasonableness
- Cost breakdown calculations
- Zero cost for zero tokens

### Error Handling
- Validation errors
- Authentication errors
- 404 Not Found errors
- Invalid token errors
- Duplicate email errors
- Internal errors (no sensitive info exposure)

## Notes

- Tests use in-memory SQLite database
- Some tests require Redis (will skip gracefully if unavailable)
- Rate limit tests may be flaky due to time windows
- Tests are designed to be idempotent and isolated

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:
```yaml
# Example GitHub Actions
- name: Run Tests
  run: pytest tests/ --cov=app --cov-report=xml
```

## Future Enhancements

- [ ] Unit tests for individual services
- [ ] End-to-end document processing tests
- [ ] Performance/load tests
- [ ] Security penetration tests
- [ ] Mock Gemini API for faster tests
