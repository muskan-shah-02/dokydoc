# DokyDoc Sprint 1 - Staging Deployment Guide

## Overview
This guide walks you through deploying DokyDoc Sprint 1 to a staging environment and running comprehensive integration tests to verify all features.

---

## Prerequisites

### Required Software
- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **Git** (for version control)
- **curl** (for health checks)

### Verify Prerequisites
```bash
docker --version
docker-compose --version  # or: docker compose version
git --version
curl --version
```

### System Requirements
- **RAM**: Minimum 4GB, Recommended 8GB
- **Disk Space**: Minimum 5GB free
- **CPU**: 2 cores minimum

---

## Quick Start (Automated)

### 1. Deploy to Staging
```bash
cd /home/user/dokydoc/backend
./scripts/deploy_staging.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Verify environment configuration
- ✅ Build Docker images with OCR dependencies
- ✅ Start all services (PostgreSQL, Redis, API, Worker, Flower)
- ✅ Run database migrations
- ✅ Perform health checks

### 2. Run Integration Tests
```bash
./scripts/run_integration_tests.sh
```

This script will:
- ✅ Verify all services are running
- ✅ Run 53 integration tests across 5 modules
- ✅ Verify all Sprint 1 features
- ✅ Generate test report

---

## Manual Deployment (Step-by-Step)

### Step 1: Environment Configuration

1. **Check if .env exists:**
```bash
ls -la .env
```

2. **If missing, create from template:**
```bash
cp env.example .env
```

3. **Update critical values in .env:**
```bash
nano .env  # or use your preferred editor
```

**Required Changes:**
```bash
# CRITICAL: Change this to a secure random string (32+ characters)
SECRET_KEY=your-actual-super-secret-key-min-32-chars-long-prod-ready

# Your actual Gemini API key
GEMINI_API_KEY=your-actual-gemini-api-key-here

# Staging environment settings
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO

# Rate limiting (adjust based on expected load)
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
```

### Step 2: Build Docker Images

**Build all services:**
```bash
docker-compose build --no-cache
```

**Expected output:**
- ✓ Building base image with Python 3.11
- ✓ Installing system dependencies (PostgreSQL, Redis, OCR tools)
- ✓ Installing Python packages (53 dependencies)
- ✓ Setting up application structure

**Build time:** ~3-5 minutes depending on network speed

### Step 3: Start Services

**Start infrastructure services first:**
```bash
docker-compose up -d db redis
```

**Wait for infrastructure to be ready (~10 seconds):**
```bash
docker-compose ps
```

**Start application services:**
```bash
docker-compose up -d app worker flower
```

**Verify all services are running:**
```bash
docker-compose ps
```

**Expected status:**
```
NAME                IMAGE              STATUS          PORTS
dokydoc_app         backend_app        Up (healthy)    0.0.0.0:8000->8000/tcp
dokydoc_db          postgres:15-alpine Up (healthy)    0.0.0.0:5432->5432/tcp
dokydoc_redis       redis:7-alpine     Up (healthy)    0.0.0.0:6379->6379/tcp
dokydoc_worker      backend_worker     Up              -
dokydoc_flower      backend_flower     Up              0.0.0.0:5555->5555/tcp
```

### Step 4: Run Database Migrations

```bash
docker-compose exec app alembic upgrade head
```

### Step 5: Verify Deployment

**Check API health:**
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "staging"
}
```

**Check API documentation:**
```bash
# Open in browser:
open http://localhost:8000/docs
```

**Check Flower dashboard:**
```bash
# Open in browser:
open http://localhost:5555
```

---

## Running Integration Tests

### Option 1: Using Test Runner Script (Recommended)

```bash
./scripts/run_integration_tests.sh
```

### Option 2: Manual Test Execution

**Run all tests:**
```bash
docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -v --tb=short
```

**Run specific test module:**
```bash
docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/test_distributed_locks.py -v
```

**Run with coverage:**
```bash
docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -v --cov=app --cov-report=html
```

### Test Modules

| Module | Tests | Features Tested |
|--------|-------|-----------------|
| `test_distributed_locks.py` | 8 | FLAW-10: Redis locks, concurrency control |
| `test_rate_limiting.py` | 10 | API-01: Rate limiting, user vs IP-based |
| `test_auth_refresh_tokens.py` | 7 | BE-04: Dual token system, token validation |
| `test_cost_tracking.py` | 12 | FLAW-17: Token counting, cost calculation |
| `test_error_handling.py` | 15 | BE-01: Error categorization, user messages |
| **Total** | **53** | **All Sprint 1 features** |

---

## Service URLs

After successful deployment, access these services:

| Service | URL | Description |
|---------|-----|-------------|
| **API Server** | http://localhost:8000 | Main FastAPI application |
| **API Docs (Swagger)** | http://localhost:8000/docs | Interactive API documentation |
| **API Docs (ReDoc)** | http://localhost:8000/redoc | Alternative API documentation |
| **Flower Dashboard** | http://localhost:5555 | Celery task monitoring |
| **PostgreSQL** | localhost:5432 | Database (use `psql` or GUI client) |
| **Redis** | localhost:6379 | Cache & message broker |

---

## Monitoring & Logs

### View Logs

**All services:**
```bash
docker-compose logs -f
```

**Specific service:**
```bash
docker-compose logs -f app        # API server logs
docker-compose logs -f worker     # Celery worker logs
docker-compose logs -f db         # PostgreSQL logs
docker-compose logs -f redis      # Redis logs
```

**Last 100 lines:**
```bash
docker-compose logs --tail=100 app
```

### Check Service Status

```bash
docker-compose ps
```

### Check Resource Usage

```bash
docker stats
```

### Access Container Shell

```bash
docker exec -it dokydoc_app bash
```

---

## Troubleshooting

### Issue: Services Not Starting

**Symptoms:**
- Containers exit immediately
- Health checks failing
- Port binding errors

**Solutions:**

1. **Check if ports are already in use:**
```bash
lsof -i :8000    # API port
lsof -i :5432    # PostgreSQL port
lsof -i :6379    # Redis port
lsof -i :5555    # Flower port
```

2. **Stop conflicting services:**
```bash
# If you have local PostgreSQL/Redis running:
sudo systemctl stop postgresql
sudo systemctl stop redis
```

3. **Check logs for errors:**
```bash
docker-compose logs app
```

### Issue: Database Connection Failures

**Symptoms:**
- API returns "Database connection failed"
- Migration errors

**Solutions:**

1. **Verify PostgreSQL is healthy:**
```bash
docker-compose ps db
docker-compose logs db
```

2. **Check database connectivity:**
```bash
docker exec dokydoc_app psql postgresql://postgres:simplepass@db:5432/dokydoc -c "SELECT 1"
```

3. **Restart database:**
```bash
docker-compose restart db
sleep 10
docker-compose restart app
```

### Issue: Redis Connection Failures

**Symptoms:**
- Lock service errors
- Rate limiting not working
- Celery tasks not processing

**Solutions:**

1. **Verify Redis is healthy:**
```bash
docker-compose ps redis
docker-compose exec redis redis-cli ping
```

2. **Check Redis logs:**
```bash
docker-compose logs redis
```

3. **Restart Redis:**
```bash
docker-compose restart redis
docker-compose restart app worker
```

### Issue: Integration Tests Failing

**Symptoms:**
- Tests timeout
- Connection refused errors
- Import errors

**Solutions:**

1. **Ensure all services are running:**
```bash
docker-compose ps
```

2. **Wait for services to be fully initialized:**
```bash
# Services may take 30-60 seconds to be fully ready
sleep 30
./scripts/run_integration_tests.sh
```

3. **Check if dependencies are installed:**
```bash
docker exec dokydoc_app pip list | grep -E "(pytest|fastapi|redis|celery)"
```

4. **Run tests with verbose output:**
```bash
docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -vv --tb=long
```

### Issue: OCR Tests Failing

**Symptoms:**
- `test_pdf_parser_ocr_fallback` fails
- "tesseract not found" errors

**Solutions:**

1. **Verify OCR dependencies are installed:**
```bash
docker exec dokydoc_app which tesseract
docker exec dokydoc_app tesseract --version
```

2. **If missing, rebuild image:**
```bash
docker-compose build --no-cache app
docker-compose up -d app
```

### Issue: SECRET_KEY Error

**Symptoms:**
- "SECRET_KEY environment variable is required" error
- Services fail to start

**Solutions:**

1. **Check .env file:**
```bash
grep SECRET_KEY .env
```

2. **Ensure SECRET_KEY is set:**
```bash
# Add to .env:
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
```

3. **Restart services:**
```bash
docker-compose down
docker-compose up -d
```

---

## Cleanup

### Stop Services (Keep Data)

```bash
docker-compose stop
```

### Stop and Remove Containers

```bash
docker-compose down
```

### Remove All Data (Fresh Start)

```bash
docker-compose down -v  # ⚠️  This deletes all data!
```

### Remove Images

```bash
docker-compose down --rmi all -v
```

---

## Sprint 1 Feature Verification Checklist

After deployment and testing, verify these features are working:

- [ ] **FLAW-10: Distributed Locks**
  - [ ] Concurrent document processing prevented
  - [ ] Lock context managers work correctly
  - [ ] Locks auto-expire after timeout

- [ ] **API-01: Rate Limiting**
  - [ ] Endpoints return 429 when rate limit exceeded
  - [ ] User-based rate limiting works for authenticated users
  - [ ] IP-based rate limiting works for unauthenticated requests

- [ ] **BE-04: Refresh Token System**
  - [ ] Login returns both access and refresh tokens
  - [ ] Refresh tokens cannot be used for API access
  - [ ] Refresh endpoint generates new token pair

- [ ] **FLAW-17: Cost Tracking**
  - [ ] Token counting uses tiktoken accurately
  - [ ] Cost calculated with Gemini 2.5 Flash pricing
  - [ ] USD to INR conversion works

- [ ] **BE-01: Error Handling**
  - [ ] Database errors return user-friendly messages
  - [ ] Connection errors handled gracefully
  - [ ] AI service errors categorized correctly

- [ ] **DAE-01/02: PDF Parser Hardening**
  - [ ] PyMuPDF extraction works
  - [ ] Fallback to pdfplumber works
  - [ ] Fallback to PyPDF2 works
  - [ ] OCR fallback works for scanned PDFs

- [ ] **FLAW-18: Flower Monitoring**
  - [ ] Flower dashboard accessible at http://localhost:5555
  - [ ] Active workers visible
  - [ ] Task history displayed

- [ ] **CONFIG-01: Configuration Security**
  - [ ] SECRET_KEY required (no default)
  - [ ] Exchange rate externalized
  - [ ] Environment-specific configs work

---

## Production Deployment Notes

**Before deploying to production:**

1. **Security:**
   - [ ] Generate secure SECRET_KEY (32+ random characters)
   - [ ] Use strong database passwords
   - [ ] Enable HTTPS with SSL certificates
   - [ ] Configure firewall rules
   - [ ] Set up authentication for Flower dashboard

2. **Performance:**
   - [ ] Adjust rate limits based on expected traffic
   - [ ] Configure resource limits (CPU, memory)
   - [ ] Set up database connection pooling
   - [ ] Enable Redis persistence

3. **Monitoring:**
   - [ ] Set up application monitoring (e.g., Sentry)
   - [ ] Configure log aggregation (e.g., ELK stack)
   - [ ] Set up uptime monitoring
   - [ ] Configure alerts for errors

4. **Backup:**
   - [ ] Set up automated database backups
   - [ ] Configure Redis snapshots
   - [ ] Plan for disaster recovery

---

## Support

**If you encounter issues:**

1. Check the logs: `docker-compose logs -f`
2. Review the troubleshooting section above
3. Verify all prerequisites are met
4. Ensure .env file is properly configured

**Additional Resources:**
- Sprint 1 Status Report: `SPRINT1_STATUS.md`
- Verification Report: `SPRINT1_VERIFICATION_REPORT.md`
- Architecture: `ARCHITECTURE.md`

---

**Status:** Sprint 1 is production-ready and fully tested.
**Last Updated:** 2026-01-23
**Version:** 1.0.0
