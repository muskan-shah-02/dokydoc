# Sprint 2 Migration Guide

## Fresh Database Setup (Recommended)

If you're starting fresh or want to reset your database completely:

```bash
# 1. Stop all containers and remove volumes
docker-compose down -v

# 2. Start database and redis
docker-compose up -d db redis

# 3. Initialize database (create all tables from models)
docker-compose run --rm app python scripts/init_db.py

# 4. Mark migrations as applied
docker-compose run --rm app alembic stamp head

# 5. Create initial data (creates default tenant and users)
docker-compose exec app python initial_data.py

# 6. Start all services
docker-compose up -d
```

**Why use `init_db.py` instead of migrations?**

The Alembic migrations were written to ADD multi-tenancy to an existing schema, but the base migration that creates the initial tables is missing. Rather than rewriting all migrations, `init_db.py` creates all tables directly from SQLAlchemy models (which already include `tenant_id`). We then mark migrations as "applied" with `alembic stamp head` so future migrations will work correctly.

## Initial Data Created

The `initial_data.py` script creates:

### Default Tenant
- **Name**: Default Organization
- **Subdomain**: default
- **Tier**: pro
- **Billing Type**: prepaid

### Default Users (all in default tenant)

| Email | Password | Roles |
|-------|----------|-------|
| superuser@example.com | superuserpassword | CXO, BA, Developer, Product Manager |
| cxo@example.com | cxopassword | CXO |
| ba@example.com | bapassword | BA |
| dev@example.com | devpassword | Developer |
| pm@example.com | pmpassword | Product Manager |

## Upgrading Existing Database

If you have existing data and want to upgrade to Sprint 2:

```bash
# 1. Backup your data first!
docker-compose exec db pg_dump -U dokydoc dokydoc > backup.sql

# 2. Run migrations
docker-compose run --rm app alembic upgrade head

# 3. Update existing users with tenant_id
# (Manual SQL needed - see below)
```

### Manual Tenant Assignment for Existing Users

```sql
-- Create a default tenant
INSERT INTO tenants (name, subdomain, status, tier, billing_type, max_users, max_documents, settings)
VALUES ('Default Organization', 'default', 'active', 'pro', 'prepaid', 50, 1000, '{}');

-- Get the tenant ID
SELECT id FROM tenants WHERE subdomain = 'default';

-- Update all existing users to belong to this tenant (replace <tenant_id> with actual ID)
UPDATE users SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;

-- Update all existing documents to belong to this tenant
UPDATE documents SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;

-- Update all existing code components to belong to this tenant  
UPDATE code_components SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;

-- Update all existing analysis results to belong to this tenant
UPDATE analysisresult SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;

-- Update all existing mismatches to belong to this tenant
UPDATE mismatches SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;

-- Update all existing document code links to belong to this tenant
UPDATE document_code_links SET tenant_id = <tenant_id> WHERE tenant_id IS NULL;
```

## Troubleshooting

### Enum Type Already Exists Error

If you see: `type "analysisrunstatus" already exists`

This means a previous migration failed partway through. Solutions:

**Option 1: Fresh start (easiest)**
```bash
docker-compose down -v
docker-compose up -d db redis
docker-compose run --rm app alembic upgrade head
```

**Option 2: Manual cleanup**
```bash
# Connect to database
docker-compose exec db psql -U dokydoc dokydoc

# Drop the enum types
DROP TYPE IF EXISTS analysisrunstatus CASCADE;
DROP TYPE IF EXISTS analysisresultstatus CASCADE;
DROP TYPE IF EXISTS segmentstatus CASCADE;

# Exit psql
\q

# Re-run migration
docker-compose run --rm app alembic upgrade head
```

### Missing tenant_id Error

If you see: `tenant_id is REQUIRED`

This means you're trying to create a user without a tenant. Make sure:
1. You've run the migrations first (`alembic upgrade head`)
2. You've created a tenant (or run `initial_data.py`)
3. You're passing `tenant_id` when creating users

### Relation Does Not Exist Error

If you see: `relation "documents" does not exist` or `relation "users" does not exist`

This means migrations are running out of order. **Solution: Fresh start (required)**
```bash
# Stop and remove everything
docker-compose down -v

# Start database
docker-compose up -d db redis

# Run ALL migrations in correct order
docker-compose run --rm app alembic upgrade head

# Verify migrations completed
docker-compose exec db psql -U dokydoc dokydoc -c "\dt"

# You should see: tenants, users, documents, code_components, etc.
```

**Root Cause:** The migration chain must be (in order):
1. `c8f2a1d9e321` (down_revision=None) - Sprint 1 base tables (users, documents, etc.)
2. `d4f3e2a1b567` (revises c8f2a1d9e321) - Sprint 2 tenant table + foreign keys
3. `b342e208f554` (revises d4f3e2a1b567) - Sprint 2 analysis_runs table
4. `f1a2b3c4d5e6` (revises b342e208f554) - Sprint 2 composite indexes (security & performance)

### Cycle Detected Error

If you see: `Cycle is detected in revisions`

This means one of the migrations has an incorrect `down_revision` pointing back to a later migration.
**Solution: This should be fixed in latest code. Pull and try again:**
```bash
git pull
docker-compose down -v
docker-compose up -d db redis
docker-compose run --rm app alembic upgrade head
```

## API Changes in Sprint 2

### Authentication
- Login response now includes `tenant_id`
- All API requests automatically filter by user's tenant

### New Endpoints

#### Tenant Management
- `POST /api/v1/tenants/register` - Register new tenant
- `GET /api/v1/tenants/me` - Get current tenant info
- `GET /api/v1/tenants/me/statistics` - Get tenant usage stats

#### User Management (CXO only)
- `GET /api/v1/users/` - List tenant users
- `POST /api/v1/users/invite` - Invite user to tenant
- `PUT /api/v1/users/{id}/roles` - Update user roles
- `DELETE /api/v1/users/{id}` - Delete user from tenant
- `GET /api/v1/users/me/permissions` - Get my permissions

#### Billing
- `GET /api/v1/billing/` - Get billing info
- `GET /api/v1/billing/usage` - Get usage stats
- `POST /api/v1/billing/add-balance` - Add balance (CXO only)
- `PUT /api/v1/billing/settings` - Update billing settings (CXO only)

## Testing Sprint 2 Features

```bash
# Run Sprint 2 tests
pytest tests/integration/test_tenant_isolation.py \
       tests/integration/test_rbac_permissions.py \
       tests/integration/test_billing_enforcement.py \
       tests/integration/test_cross_tenant_security.py -v

# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html
```

## Sprint 2 Key Features

✅ **Multi-Tenancy**
- Complete data isolation between tenants
- Tenant-scoped user management
- Tenant limits (users, documents, code components)

✅ **RBAC (Role-Based Access Control)**
- 4 roles: CXO, Developer, BA, Product Manager
- 20 fine-grained permissions
- Permission-based endpoint protection

✅ **Billing Enforcement**
- Prepaid and postpaid billing models
- Balance checks before operations
- Monthly limits and rollover
- HTTP 402 responses for insufficient funds

✅ **Security**
- Schrödinger's Document pattern (404 not 403)
- Cross-tenant access prevention
- Admin lockout prevention
- Data leakage prevention in error messages

## Next Steps

After setup, you can:

1. **Test Login**: `POST /api/v1/auth/login` with any of the default users
2. **Register New Tenant**: `POST /api/v1/tenants/register`
3. **Invite Users**: `POST /api/v1/users/invite` (as CXO)
4. **Upload Documents**: `POST /api/v1/documents/` (as any user)
5. **Manage Billing**: `GET /api/v1/billing/` to check balance
