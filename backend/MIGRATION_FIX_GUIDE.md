# Migration Fix Guide: Resolving tenant_id Column Issue

## Problem Summary

The application was failing with the error:
```
column documents.tenant_id does not exist
```

### Root Causes

1. **Schema Mismatch**: The database schema was out of sync with SQLAlchemy models
   - Models expect `tenant_id` column in all tables
   - Database was created without this column

2. **Migration Order Issue**:
   - Phase 2 migration (`b342e208f554`) creates base tables WITHOUT `tenant_id`
   - Sprint 1 migration (`c8f2a1d9e321`) adds `tenant_id` to those tables
   - Migrations weren't applied correctly

3. **Migration Bugs Fixed**:
   - ✅ Sprint 1 migration had typo: `consolidated_analysis` → `consolidated_analyses`
   - ✅ Phase 2 ENUM creation used try/except causing transaction errors

## Solution Applied

### 1. Fixed Migration Files

#### Sprint 1 Migration (`c8f2a1d9e321_sprint1_multi_tenancy_and_cost_tracking.py`)
- **Fixed**: Table name typo `consolidated_analysis` → `consolidated_analyses`
- **Lines Changed**: 50, 141

#### Phase 2 Migration (`b342e208f554_add_phase_2_architecture_analysis_runs_.py`)
- **Fixed**: ENUM creation now uses PostgreSQL `DO $$ ... END $$` blocks
- **Reason**: Prevents "current transaction is aborted" errors
- **Lines Changed**: 25-42

### 2. Created Recovery Script

Location: `backend/scripts/reset_and_migrate.sh`

## Quick Fix (Recommended)

### Option A: Automated Script (Linux/Mac)

```bash
cd backend
./scripts/reset_and_migrate.sh
```

### Option B: Manual Steps (Windows PowerShell)

```powershell
# Navigate to backend directory
cd .\backend\

# Step 1: Stop and clean everything
docker-compose down -v

# Step 2: Start database and Redis only
docker-compose up -d db redis

# Step 3: Wait for database to be ready
Start-Sleep -Seconds 5

# Step 4: Run migrations
docker-compose run --rm app alembic upgrade head

# Step 5: Start all services
docker-compose up -d

# Step 6: Check logs
docker-compose logs -f
```

## Verification Steps

After running migrations, verify the fix:

### 1. Check Migration Status

```bash
docker-compose exec app alembic current
```

Expected output:
```
c8f2a1d9e321 (head)
```

### 2. Verify Database Schema

```bash
docker-compose exec db psql -U postgres -d dokydoc -c "\d documents"
```

Verify that `tenant_id` column exists in the output.

### 3. Check Application Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### 4. Test Document Upload

Try uploading a document through the API or UI. The Celery worker should process it without errors.

Check worker logs:
```bash
docker-compose logs -f dokydoc_worker
```

## Migration Details

### Migration Chain

```
[Initial State]
    ↓
b342e208f554 (Phase 2: Base schema)
    ↓ Creates: users, documents, code_components, analysis_runs, etc.
    ↓ WITHOUT tenant_id
    ↓
c8f2a1d9e321 (Sprint 1: Multi-tenancy)
    ↓ Adds: tenant_id to all tables
    ↓ Adds: cost tracking fields
    ↓ Creates: tenant_billing table
    ↓
[Current State]
```

### Tables Updated with tenant_id

- users
- documents
- code_components
- mismatches
- document_segments
- analysisresult
- document_code_links
- initiatives
- initiative_assets
- ontology_concepts
- ontology_relationships
- analysis_runs
- consolidated_analyses

### New Tables Created

- tenant_billing (Sprint 1)

### New ENUMs Created

- analysisrunstatus (Phase 2)
- analysisresultstatus (Phase 2)
- segmentstatus (Phase 2)

## Troubleshooting

### Issue: "Permission denied" when running script

**Solution**:
```bash
chmod +x scripts/reset_and_migrate.sh
```

### Issue: "type already exists" error persists

**Solution**: Clean up PostgreSQL ENUMs manually

```bash
docker-compose exec db psql -U postgres -d dokydoc -c "
DROP TYPE IF EXISTS analysisrunstatus CASCADE;
DROP TYPE IF EXISTS analysisresultstatus CASCADE;
DROP TYPE IF EXISTS segmentstatus CASCADE;
"
```

Then run migrations again.

### Issue: Migration shows wrong version

**Solution**: Reset Alembic version table

```bash
docker-compose exec db psql -U postgres -d dokydoc -c "
TRUNCATE alembic_version;
"
```

Then run migrations from scratch.

### Issue: "Database does not exist"

**Solution**: Create the database

```bash
docker-compose exec db psql -U postgres -c "CREATE DATABASE dokydoc;"
```

## Important Notes

⚠️ **WARNING**: The reset script (`reset_and_migrate.sh`) will **DELETE ALL DATA** in your database.

- Use this only in development environments
- For production, consult with your DBA for a proper migration strategy
- Always backup your data before running migrations

## Next Steps After Fix

1. ✅ Verify all services are running: `docker-compose ps`
2. ✅ Check application logs for errors: `docker-compose logs -f`
3. ✅ Test document upload functionality
4. ✅ Verify tenant isolation (if applicable)
5. ✅ Test cost tracking features

## Support

If you encounter issues not covered in this guide:

1. Check application logs: `docker-compose logs -f app`
2. Check worker logs: `docker-compose logs -f dokydoc_worker`
3. Check database logs: `docker-compose logs -f db`
4. Review migration history: `docker-compose exec app alembic history`

## Technical Details

### Why tenant_id?

The `tenant_id` column enables multi-tenancy support, allowing the application to serve multiple organizations/tenants while keeping their data isolated.

### Default tenant_id

All records get `tenant_id = 1` by default, representing the default tenant.

### Cost Tracking

Sprint 1 also added cost tracking fields to monitor AI API usage:
- `ai_cost_inr`: Total cost in Indian Rupees
- `token_count_input`: Input tokens used
- `token_count_output`: Output tokens generated
- `cost_breakdown`: JSON with per-pass costs

---

**Last Updated**: 2026-01-17
**Migration Versions**: b342e208f554 → c8f2a1d9e321
