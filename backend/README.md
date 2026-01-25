# DokyDoc Backend

**AI-Powered Document Analysis & Governance Platform**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary-yellow.svg)]()

DokyDoc is a production-ready SaaS platform that transforms documents into structured, analyzable data through intelligent multi-pass AI analysis. Built with multi-tenancy, RBAC, and billing enforcement from the ground up.

---

## 🚀 **Quick Start**

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Fresh Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd dokydoc/backend

# 2. Copy environment template
cp .env.example .env

# 3. Start database and Redis
docker-compose up -d db redis

# 4. Initialize database (creates all tables)
docker-compose run --rm app python scripts/init_db.py

# 5. Mark migrations as applied
docker-compose run --rm app alembic stamp head

# 6. Create default tenant and users
docker-compose exec app python initial_data.py

# 7. Start all services
docker-compose up -d
```

### Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Open API documentation
open http://localhost:8000/docs
```

### Default Users

Login at `/api/v1/auth/login`:

| Email | Password | Roles |
|-------|----------|-------|
| superuser@example.com | superuserpassword | CXO, BA, Developer, Product Manager |
| cxo@example.com | cxopassword | CXO |
| ba@example.com | bapassword | BA |
| dev@example.com | devpassword | Developer |
| pm@example.com | pmpassword | Product Manager |

**Default Tenant:** `default` (subdomain)

---

## ✨ **Features**

### **Sprint 1 Features**

- ✅ **Document Analysis Engine (DAE)** - Multi-pass AI analysis with Google Gemini
- ✅ **PDF Parsing with OCR** - Extract text from scanned PDFs using Tesseract
- ✅ **Cost Tracking** - Track AI API costs per document
- ✅ **Rate Limiting** - Per-user API rate limiting
- ✅ **Distributed Locks** - Redis-based locking for concurrent operations
- ✅ **Refresh Tokens** - Secure token refresh system
- ✅ **Billing API** - Basic billing endpoints
- ✅ **Cache Service** - Redis caching layer
- ✅ **Integration Tests** - 53 tests covering core features

### **Sprint 2 Features** ⭐ NEW

- ✅ **Multi-Tenancy** - Complete data isolation between organizations
- ✅ **RBAC (Role-Based Access Control)** - 4 roles, 20 fine-grained permissions
- ✅ **Billing Enforcement** - Prepaid and postpaid billing with balance management
- ✅ **Tenant Management** - Organization registration and management
- ✅ **User Management** - CXO can invite and manage users within tenant
- ✅ **Security Hardening** - Schrödinger's Document pattern, timing attack prevention
- ✅ **Performance Optimization** - N+1 query fix (10x faster), composite indexes (100x faster)
- ✅ **Comprehensive Testing** - 130+ integration tests (85% coverage)

---

## 🏗️ **Architecture**

DokyDoc follows a modular, scalable architecture optimized for multi-tenant SaaS deployment.

### **Technology Stack**

**Backend Framework:**
- FastAPI (async web framework)
- SQLAlchemy (ORM with PostgreSQL)
- Alembic (database migrations)
- Pydantic (data validation)

**Database & Cache:**
- PostgreSQL 15 (primary database)
- Redis 7 (caching & session storage)

**AI & Processing:**
- Google Gemini API (document analysis)
- Celery (background task processing)
- Tesseract OCR (PDF text extraction)

**Infrastructure:**
- Docker & Docker Compose
- Nginx (reverse proxy)
- Gunicorn (WSGI server)

### **Project Structure**

```
backend/
├── app/
│   ├── api/                    # API endpoints and routing
│   │   ├── deps.py            # Dependency injection (auth, permissions)
│   │   └── endpoints/         # API route handlers
│   │       ├── tenants.py     # Tenant management
│   │       ├── users.py       # User management
│   │       ├── billing.py     # Billing endpoints
│   │       ├── documents.py   # Document CRUD
│   │       └── ...
│   ├── core/                  # Core application config
│   │   ├── config.py          # Environment configuration
│   │   ├── security.py        # JWT authentication
│   │   ├── permissions.py     # RBAC permissions (Sprint 2)
│   │   └── logging.py         # Structured logging
│   ├── crud/                  # Database operations
│   │   ├── base.py            # Base CRUD class
│   │   ├── crud_tenant.py     # Tenant operations (Sprint 2)
│   │   ├── crud_user.py       # User operations
│   │   └── ...
│   ├── db/                    # Database configuration
│   │   ├── base.py            # All models imported here
│   │   └── session.py         # DB session management
│   ├── models/                # SQLAlchemy models
│   │   ├── tenant.py          # Tenant model (Sprint 2)
│   │   ├── billing.py         # Billing model (Sprint 2)
│   │   ├── user.py            # User model
│   │   ├── document.py        # Document model
│   │   └── ...
│   ├── schemas/               # Pydantic schemas
│   │   ├── tenant.py          # Tenant validation (Sprint 2)
│   │   ├── billing.py         # Billing validation (Sprint 2)
│   │   ├── user.py            # User validation + Role enum
│   │   └── ...
│   └── services/              # Business logic
│       ├── ai/                # AI service integration
│       │   ├── gemini.py      # Google Gemini client
│       │   └── prompt_manager.py
│       ├── billing_enforcement_service.py  # Billing logic (Sprint 2)
│       ├── permission_checker.py           # RBAC checker (Sprint 2)
│       ├── analysis_service.py             # Document analysis
│       ├── validation_service.py           # Validation engine
│       └── ...
├── alembic/                   # Database migrations
│   └── versions/              # Migration files
├── scripts/                   # Utility scripts
│   └── init_db.py            # Direct table creation (Sprint 2)
├── tests/                     # Test suite
│   ├── conftest.py           # Test fixtures
│   └── integration/          # Integration tests
│       ├── test_tenant_isolation.py         # 25+ tests
│       ├── test_rbac_permissions.py         # 40+ tests
│       ├── test_billing_enforcement.py      # 25+ tests
│       └── test_cross_tenant_security.py    # 30+ tests
├── logs/                      # Application logs
├── uploads/                   # File upload storage
├── main.py                    # FastAPI app entry point
├── initial_data.py           # Default tenant/user creation
├── docker-compose.yml         # Container orchestration
└── Dockerfile                 # Container definition
```

---

## 🔐 **Multi-Tenancy & Security**

### **Multi-Tenancy Design**

DokyDoc uses a **shared database, shared schema** approach:

- All tables include `tenant_id` foreign key (NOT NULL)
- All queries automatically filter by `tenant_id`
- Complete data isolation between tenants
- Composite indexes on `(tenant_id, id)` for performance

**Benefits:**
- ✅ Cost-effective (single database)
- ✅ Easy to manage (single schema)
- ✅ Fast queries (10-100x with indexes)
- ✅ Simple backup/restore

### **RBAC (Role-Based Access Control)**

**4 Roles:**

1. **CXO** (Chief Experience Officer)
   - Full administrative access
   - All 20 permissions
   - User management, billing, tenant configuration

2. **Developer**
   - Technical features access
   - 15 permissions
   - Code analysis, document analysis, validation

3. **BA** (Business Analyst)
   - Document and analysis focus
   - 14 permissions
   - Document management, validation, analysis

4. **Product Manager**
   - Product feature access
   - 10 permissions
   - Document viewing, analysis viewing

**20 Fine-Grained Permissions:**
```
document:read, document:write, document:delete, document:upload, document:analyze
code:read, code:write, code:delete, code:analyze
analysis:view, analysis:run, analysis:delete
user:read, user:invite, user:update_roles, user:delete
tenant:read, tenant:update
billing:view, billing:manage
validation:run, validation:view_results
```

See `API_REFERENCE.md` for complete permission matrix.

### **Security Features**

**Schrödinger's Document Pattern:**
- Returns **404** (not 403) for cross-tenant resources
- Prevents information leakage about resource existence
- Attacker cannot determine if document exists in another tenant

**Timing Attack Prevention:**
- Composite indexes ensure consistent query performance
- No timing differences between "not found" and "forbidden"

**Admin Lockout Prevention:**
- Cannot modify your own roles
- Cannot delete your own account

**Data Isolation:**
- All queries filter by `tenant_id` (enforced at CRUD layer)
- Background tasks explicitly receive `tenant_id`
- No cross-tenant data access possible

---

## 💰 **Billing System**

### **Billing Models**

**Prepaid:**
- Tenant maintains a balance (in INR)
- Balance checked BEFORE analysis
- Cost deducted AFTER success
- HTTP 402 when insufficient balance

**Postpaid:**
- Tenant has monthly limit (in INR)
- Cost added to monthly total AFTER success
- HTTP 402 when limit exceeded
- Monthly rollover on 1st of month

### **Cost Calculation**

```python
base_cost = ₹2.00
per_kb_cost = ₹0.01/KB
max_cost = ₹12.00

total = min(base_cost + (size_kb * per_kb_cost), max_cost)
```

**Examples:**
- 10KB document: ₹2.10
- 100KB document: ₹3.00
- 1000KB document: ₹12.00 (capped)

### **Billing API**

```bash
# Get billing info (CXO only)
GET /api/v1/billing/

# Get usage statistics
GET /api/v1/billing/usage

# Add balance (prepaid, CXO only)
POST /api/v1/billing/add-balance
{
  "amount_inr": 5000.00,
  "payment_reference": "RAZORPAY-TXN-12345"
}

# Update billing settings
PUT /api/v1/billing/settings
{
  "low_balance_threshold_inr": 500.00,
  "settings": {
    "low_balance_alerts": true
  }
}
```

---

## 📡 **API Documentation**

### **Authentication**

All endpoints (except registration) require JWT Bearer token:

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "cxo@example.com", "password": "cxopassword"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { ... },
  "tenant": { ... }
}

# Use token in subsequent requests
curl -X GET http://localhost:8000/api/v1/tenants/me \
  -H "Authorization: Bearer <token>"
```

### **API Endpoints**

**Tenant Management:**
```
POST   /api/v1/tenants/register          - Register new tenant
GET    /api/v1/tenants/me                - Get current tenant
PUT    /api/v1/tenants/me                - Update tenant
GET    /api/v1/tenants/me/statistics     - Get usage stats
```

**User Management (CXO only):**
```
GET    /api/v1/users/                    - List users
POST   /api/v1/users/invite              - Invite user
PUT    /api/v1/users/{id}/roles          - Update roles
DELETE /api/v1/users/{id}                - Delete user
GET    /api/v1/users/me/permissions      - Get my permissions
```

**Billing (CXO only):**
```
GET    /api/v1/billing/                  - Get billing info
GET    /api/v1/billing/usage             - Get usage stats
POST   /api/v1/billing/add-balance       - Add balance
PUT    /api/v1/billing/settings          - Update settings
```

**Documents:**
```
GET    /api/v1/documents/                - List documents
POST   /api/v1/documents/                - Create document
GET    /api/v1/documents/{id}            - Get document
PUT    /api/v1/documents/{id}            - Update document
DELETE /api/v1/documents/{id}            - Delete document
POST   /api/v1/documents/{id}/analyze    - Analyze document (with billing check)
```

See **`API_REFERENCE.md`** for complete API documentation with request/response examples.

### **Interactive API Docs**

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🧪 **Testing**

### **Test Suite**

DokyDoc includes 130+ integration tests across 4 modules:

```bash
# Run all Sprint 2 tests
pytest tests/integration/test_tenant_isolation.py \
       tests/integration/test_rbac_permissions.py \
       tests/integration/test_billing_enforcement.py \
       tests/integration/test_cross_tenant_security.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

### **Test Modules**

1. **test_tenant_isolation.py** (25+ tests)
   - Users cannot see other tenants' documents
   - Cross-tenant access returns 404
   - Background tasks respect tenant boundaries

2. **test_rbac_permissions.py** (40+ tests)
   - Permission checks for all 4 roles
   - CXO has all 20 permissions
   - Developer/BA/PM have correct permission subsets
   - Admin lockout prevention works

3. **test_billing_enforcement.py** (25+ tests)
   - Prepaid balance checks work
   - Postpaid monthly limits work
   - Cost estimation is accurate
   - HTTP 402 returned for insufficient funds
   - Monthly rollover works correctly

4. **test_cross_tenant_security.py** (30+ tests)
   - Schrödinger's Document pattern works
   - No information leakage in errors
   - Timing attack prevention verified
   - Tenant context extraction works

See **`tests/README.md`** for detailed testing documentation.

---

## 📊 **Performance**

### **Optimizations Implemented**

**N+1 Query Fix:**
- Problem: 51 queries for 50 segments
- Solution: Eager loading with `joinedload()`
- Impact: 98% query reduction, 10x faster (500ms → 50ms)

**Composite Indexes:**
- Indexes on `(tenant_id, id)` for 7 tables
- Impact: 10-100x faster tenant-scoped lookups
- Security: Prevents timing attacks

### **Performance Benchmarks**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Segments endpoint queries | 51 | 1 | 98% reduction |
| Segments response time | 500ms | 50ms | 10x faster |
| Document lookup | Full scan | Index seek | 100x faster |

See **`PERFORMANCE.md`** for detailed benchmarks and future optimization roadmap.

---

## 📚 **Documentation**

### **Available Documentation**

- **README.md** (this file) - Overview and quick start
- **ARCHITECTURE.md** - Detailed architecture documentation
- **API_REFERENCE.md** - Complete API documentation
- **MIGRATION_GUIDE.md** - Database setup and troubleshooting
- **PERFORMANCE.md** - Performance optimizations and benchmarks
- **SPRINT2_SUMMARY.md** - Sprint 2 deliverables and changes
- **tests/README.md** - Testing documentation

### **Migration & Setup**

See **`MIGRATION_GUIDE.md`** for:
- Fresh database setup
- Upgrading existing databases
- Troubleshooting common errors
- Initial data creation

---

## 🔧 **Configuration**

### **Environment Variables**

Create `.env` file from template:

```bash
cp .env.example .env
```

**Key Configuration:**

```bash
# Database
DATABASE_URL=postgresql://dokydoc:dokydoc@db:5432/dokydoc

# Redis
REDIS_URL=redis://redis:6379/0

# JWT Authentication
SECRET_KEY=<your-secret-key>
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google Gemini API
GEMINI_API_KEY=<your-gemini-api-key>

# Application
DEBUG=false
ENVIRONMENT=production
```

---

## 🚀 **Deployment**

### **Docker Deployment**

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### **Production Considerations**

- Use environment-specific `.env` files
- Enable SSL/TLS with Nginx reverse proxy
- Set `DEBUG=false` in production
- Use strong `SECRET_KEY` (generate with `openssl rand -hex 32`)
- Configure connection pool sizes
- Set up monitoring and alerting
- Regular database backups
- Set up log aggregation

See **`DEPLOYMENT_GUIDE.md`** for production deployment instructions.

---

## 🐛 **Troubleshooting**

### **Common Issues**

**Issue:** `tenant_id is REQUIRED`
**Solution:** Run `initial_data.py` to create default tenant

**Issue:** `type "analysisrunstatus" already exists`
**Solution:** Fresh start with `docker-compose down -v`

**Issue:** `relation "documents" does not exist`
**Solution:** Use `scripts/init_db.py` instead of migrations

See **`MIGRATION_GUIDE.md`** for complete troubleshooting guide.

---

## 📈 **Roadmap**

### **Sprint 3 (Planned)**

**High Priority:**
- Optimistic locking for billing (prevent race conditions)
- Redis caching for tenants/users (30-90% DB load reduction)
- Connection pool tuning for Celery

**Medium Priority:**
- Cursor-based pagination
- Async database I/O (SQLAlchemy async)
- Read replicas for horizontal scaling

**Low Priority:**
- Query result caching
- Database partitioning (for > 1M rows)
- CDN for static assets

---

## 🤝 **Contributing**

### **Development Setup**

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linter
flake8 app/

# Format code
black app/
```

### **Code Standards**

- Type hints throughout
- Comprehensive docstrings
- Error handling best practices
- All CRUD operations MUST include `tenant_id`
- Use `require_permission()` for protected endpoints
- Write tests for new features

---

## 📄 **License**

Proprietary - All rights reserved

---

## 📞 **Support**

For issues, questions, or feature requests:

- **Documentation:** See docs in this directory
- **API Docs:** http://localhost:8000/docs
- **Issues:** File on GitHub (if applicable)

---

## ✅ **Status**

**Sprint 1:** ✅ Complete (20 tasks, 53 tests)
**Sprint 2:** ✅ Complete (150 hours, 130+ tests, 85% coverage)
**Production Ready:** ✅ Yes

**Last Updated:** 2026-01-25
**Version:** 2.0 (Sprint 2)

---

**Built with ❤️ using FastAPI, PostgreSQL, Redis, and Google Gemini AI**
