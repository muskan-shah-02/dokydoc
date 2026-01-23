# DokyDoc Sprint 1 - Quick Start Guide

## Prerequisites Check

Before starting, ensure you have Docker and Docker Compose installed:

```bash
docker --version          # Should show 20.10+
docker-compose --version  # Should show 2.0+
```

---

## Deploy to Staging (3 Simple Steps)

### Step 1: Navigate to Backend Directory

```bash
cd /home/user/dokydoc/backend
```

### Step 2: Deploy All Services

```bash
./scripts/deploy_staging.sh
```

**This script will:**
- ✅ Check prerequisites
- ✅ Build Docker images (takes ~3-5 minutes first time)
- ✅ Start PostgreSQL, Redis, API, Celery Worker, Flower
- ✅ Run database migrations
- ✅ Perform health checks

**Expected output:**
```
==================================================
   DokyDoc Sprint 1 - Staging Deployment
==================================================
[SUCCESS] Deployment complete!

Service URLs:
🌐 API Server:          http://localhost:8000
📚 API Documentation:   http://localhost:8000/docs
🌺 Flower Dashboard:    http://localhost:5555
```

### Step 3: Run Integration Tests

```bash
./scripts/run_integration_tests.sh
```

**This script will:**
- ✅ Verify all services are running
- ✅ Run 53 integration tests
- ✅ Verify all Sprint 1 features
- ✅ Show detailed results

**Expected output:**
```
==================================================
   Sprint 1 Feature Verification
==================================================
✓ Distributed Locks (FLAW-10)
✓ Rate Limiting (API-01)
✓ Refresh Tokens (BE-04)
✓ Cost Tracking (FLAW-17)
✓ Error Handling (BE-01)

[SUCCESS] All integration tests completed!
Sprint 1 is verified and ready for production deployment
```

---

## Verify Services Are Running

```bash
# Check all containers
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Open API docs in browser
open http://localhost:8000/docs  # or visit manually

# Check Flower dashboard
open http://localhost:5555
```

---

## View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app     # API logs
docker-compose logs -f worker  # Celery worker logs
docker-compose logs -f db      # Database logs
```

---

## Common Commands

```bash
# Stop services (keep data)
docker-compose stop

# Start services again
docker-compose start

# Restart a service
docker-compose restart app

# Stop and remove containers (keep data)
docker-compose down

# Fresh start (removes all data!)
docker-compose down -v
```

---

## Manual Testing

### Test API Endpoint

```bash
# Register a user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User"
  }'

# Login
curl -X POST http://localhost:8000/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpassword123"
```

### Test Rate Limiting

```bash
# This should return 429 after hitting the rate limit
for i in {1..150}; do
  curl http://localhost:8000/health
  echo "Request $i"
done
```

### Test Flower Dashboard

1. Open http://localhost:5555 in browser
2. You should see:
   - Active workers
   - Task history
   - Real-time monitoring

---

## Troubleshooting

### Issue: Port Already in Use

```bash
# Find what's using the port
lsof -i :8000
lsof -i :5432
lsof -i :6379

# Stop the conflicting service
sudo systemctl stop postgresql  # if local PostgreSQL is running
sudo systemctl stop redis       # if local Redis is running
```

### Issue: Services Not Starting

```bash
# Check logs
docker-compose logs app

# Restart all services
docker-compose down
docker-compose up -d

# Wait for health checks
docker-compose ps
```

### Issue: Tests Failing

```bash
# Ensure services are fully initialized (may take 30-60 seconds)
sleep 30
./scripts/run_integration_tests.sh

# Or check service health manually
curl http://localhost:8000/health
docker-compose exec redis redis-cli ping
```

---

## What Gets Deployed?

### Services

1. **PostgreSQL Database** (port 5432)
   - Stores user data, documents, billing info
   - Persistent volume: `postgres_data`

2. **Redis Cache** (port 6379)
   - Caching layer
   - Celery message broker
   - Distributed locks storage
   - Rate limiting storage
   - Persistent volume: `redis_data`

3. **FastAPI Application** (port 8000)
   - Main REST API
   - JWT authentication
   - Document upload/processing
   - Billing management

4. **Celery Worker**
   - Background document processing
   - PDF parsing with 4-tier fallback
   - OCR processing
   - AI analysis with Gemini

5. **Flower Monitoring** (port 5555)
   - Real-time task monitoring
   - Worker statistics
   - Task history

### Sprint 1 Features Included

- ✅ **FLAW-10:** Distributed Locks (Redis)
- ✅ **API-01:** Rate Limiting (slowapi + Redis)
- ✅ **BE-04:** Refresh Token System (JWT)
- ✅ **FLAW-17:** Real Token-Based Cost Tracking (tiktoken)
- ✅ **BE-01:** Production Error Messages
- ✅ **CONFIG-01:** Configuration Security (externalized secrets)
- ✅ **FLAW-18:** Flower Monitoring Dashboard
- ✅ **DAE-01/02:** PDF Parser Hardening (4-tier fallback + OCR)
- ✅ **TESTING:** 53 Integration Tests

---

## Next Steps After Testing

1. **Production Deployment:**
   - Review security checklist in DEPLOYMENT_GUIDE.md
   - Set up HTTPS/SSL
   - Configure production SECRET_KEY
   - Set up monitoring and alerts

2. **Sprint 2 Development:**
   - Begin multi-tenancy implementation
   - Add tenant isolation features
   - Implement tenant-specific billing

3. **Performance Testing:**
   - Load testing with realistic traffic
   - Optimize database queries
   - Tune rate limits

---

## Support

- **Deployment Guide:** `DEPLOYMENT_GUIDE.md` (comprehensive guide)
- **Verification Report:** `SPRINT1_VERIFICATION_REPORT.md`
- **Status Report:** `SPRINT1_STATUS.md`
- **Architecture:** `ARCHITECTURE.md`

---

**Ready to deploy? Run: `./scripts/deploy_staging.sh`**
