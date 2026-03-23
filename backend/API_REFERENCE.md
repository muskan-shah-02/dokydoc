# DokyDoc API Reference - Sprint 2

Complete API documentation for Sprint 2 multi-tenancy, RBAC, and billing features.

**Base URL:** `http://localhost:8000/api/v1`

**Authentication:** All endpoints (except registration) require JWT Bearer token

**Format:** All requests/responses use JSON

---

## Table of Contents

1. [Authentication](#authentication)
2. [Tenant Management](#tenant-management)
3. [User Management](#user-management)
4. [Billing](#billing)
5. [Documents](#documents)
6. [Code Components](#code-components)
7. [Validation](#validation)
8. [RBAC Permissions](#rbac-permissions)
9. [Error Responses](#error-responses)

---

## Authentication

### Login

Authenticate user and receive JWT token.

**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "username": "cxo@example.com",
  "password": "cxopassword"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "cxo@example.com",
    "roles": ["CXO"],
    "tenant_id": 1
  },
  "tenant": {
    "id": 1,
    "name": "Default Organization",
    "subdomain": "default",
    "tier": "pro",
    "status": "active"
  }
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Incorrect email or password"
}
```

---

### Get Current User

Get currently authenticated user's information.

**Endpoint:** `GET /auth/me`

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "cxo@example.com",
  "roles": ["CXO"],
  "tenant_id": 1,
  "is_active": true,
  "created_at": "2026-01-25T10:00:00Z"
}
```

---

## Tenant Management

### Register New Tenant

Register a new organization/tenant.

**Endpoint:** `POST /tenants/register`

**Authentication:** Not required

**Request:**
```json
{
  "name": "Acme Corporation",
  "subdomain": "acme",
  "admin_email": "admin@acme.com",
  "admin_password": "SecurePass123!",
  "tier": "pro",
  "billing_type": "prepaid"
}
```

**Validation Rules:**
- `subdomain`: Lowercase alphanumeric + hyphens only, 3-63 chars
- `tier`: One of `free`, `basic`, `pro`, `enterprise`
- `billing_type`: One of `prepaid`, `postpaid`
- `admin_email`: Valid email format, unique globally
- `admin_password`: Minimum 8 characters

**Response (201 Created):**
```json
{
  "tenant": {
    "id": 2,
    "name": "Acme Corporation",
    "subdomain": "acme",
    "tier": "pro",
    "status": "active",
    "billing_type": "prepaid",
    "max_users": 50,
    "max_documents": 1000,
    "max_code_components": 500
  },
  "admin_user": {
    "id": 10,
    "email": "admin@acme.com",
    "roles": ["CXO"],
    "tenant_id": 2
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Subdomain 'acme' is already taken"
}
```

---

### Get Current Tenant

Get current user's tenant information.

**Endpoint:** `GET /tenants/me`

**Permission:** None (any authenticated user)

**Response (200 OK):**
```json
{
  "id": 1,
  "name": "Default Organization",
  "subdomain": "default",
  "tier": "pro",
  "status": "active",
  "billing_type": "prepaid",
  "max_users": 50,
  "max_documents": 1000,
  "max_code_components": 500,
  "settings": {},
  "created_at": "2026-01-25T10:00:00Z",
  "updated_at": "2026-01-25T10:00:00Z"
}
```

---

### Update Tenant Settings

Update tenant configuration.

**Endpoint:** `PUT /tenants/me`

**Permission:** `tenant:update` (CXO only)

**Request:**
```json
{
  "name": "Acme Corporation (Updated)",
  "settings": {
    "feature_flags": {
      "advanced_analytics": true
    },
    "notification_preferences": {
      "email_alerts": true
    }
  }
}
```

**Response (200 OK):**
```json
{
  "id": 2,
  "name": "Acme Corporation (Updated)",
  "subdomain": "acme",
  "tier": "pro",
  "status": "active",
  "settings": {
    "feature_flags": {
      "advanced_analytics": true
    },
    "notification_preferences": {
      "email_alerts": true
    }
  },
  "updated_at": "2026-01-25T12:00:00Z"
}
```

---

### Get Tenant Statistics

Get usage statistics for current tenant.

**Endpoint:** `GET /tenants/me/statistics`

**Permission:** `tenant:read` (CXO only)

**Response (200 OK):**
```json
{
  "tenant_id": 1,
  "tenant_name": "Default Organization",
  "users": {
    "current": 5,
    "limit": 50,
    "percentage": 10.0
  },
  "documents": {
    "current": 127,
    "limit": 1000,
    "percentage": 12.7
  },
  "code_components": {
    "current": 43,
    "limit": 500,
    "percentage": 8.6
  },
  "storage": {
    "total_mb": 1523.45,
    "by_type": {
      "PDF": 1200.5,
      "DOCX": 200.3,
      "TXT": 122.65
    }
  },
  "analysis": {
    "total_analyses": 345,
    "successful": 330,
    "failed": 15,
    "pending": 0
  }
}
```

---

## User Management

All user management endpoints require **CXO role** (except `/users/me/permissions`).

### List Tenant Users

Get all users in current tenant.

**Endpoint:** `GET /users/`

**Permission:** `user:read` (CXO only)

**Query Parameters:**
- `skip` (int, optional): Pagination offset, default 0
- `limit` (int, optional): Page size, default 100, max 100

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "email": "cxo@example.com",
      "roles": ["CXO"],
      "tenant_id": 1,
      "is_active": true,
      "created_at": "2026-01-25T10:00:00Z"
    },
    {
      "id": 2,
      "email": "dev@example.com",
      "roles": ["DEVELOPER"],
      "tenant_id": 1,
      "is_active": true,
      "created_at": "2026-01-25T10:05:00Z"
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 100
}
```

---

### Invite User to Tenant

Invite a new user to the current tenant.

**Endpoint:** `POST /users/invite`

**Permission:** `user:invite` (CXO only)

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "roles": ["DEVELOPER", "BA"]
}
```

**Validation:**
- Email must be unique within tenant
- Password minimum 8 characters
- Roles must be valid: `CXO`, `DEVELOPER`, `BA`, `PRODUCT_MANAGER`
- Checks tenant user limit before creating

**Response (201 Created):**
```json
{
  "id": 6,
  "email": "newuser@example.com",
  "roles": ["DEVELOPER", "BA"],
  "tenant_id": 1,
  "is_active": true,
  "created_at": "2026-01-25T14:00:00Z"
}
```

**Response (400 Bad Request - User Limit Reached):**
```json
{
  "detail": "Cannot invite user: tenant has reached maximum user limit (50/50)"
}
```

**Response (400 Bad Request - Email Exists):**
```json
{
  "detail": "A user with email 'newuser@example.com' already exists in your tenant"
}
```

---

### Update User Roles

Update roles for an existing user.

**Endpoint:** `PUT /users/{user_id}/roles`

**Permission:** `user:update_roles` (CXO only)

**Request:**
```json
{
  "roles": ["DEVELOPER", "PRODUCT_MANAGER"]
}
```

**Security:**
- ❌ Cannot modify your own roles (admin lockout prevention)

**Response (200 OK):**
```json
{
  "id": 6,
  "email": "newuser@example.com",
  "roles": ["DEVELOPER", "PRODUCT_MANAGER"],
  "tenant_id": 1,
  "is_active": true,
  "updated_at": "2026-01-25T15:00:00Z"
}
```

**Response (403 Forbidden - Modifying Own Roles):**
```json
{
  "detail": "Cannot modify your own roles (admin lockout prevention)"
}
```

**Response (404 Not Found - Cross-Tenant Access):**
```json
{
  "detail": "User not found"
}
```

---

### Delete User

Delete a user from the tenant.

**Endpoint:** `DELETE /users/{user_id}`

**Permission:** `user:delete` (CXO only)

**Security:**
- ❌ Cannot delete yourself (admin lockout prevention)

**Response (200 OK):**
```json
{
  "message": "User newuser@example.com deleted successfully"
}
```

**Response (403 Forbidden - Deleting Self):**
```json
{
  "detail": "Cannot delete your own account (admin lockout prevention)"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "User not found"
}
```

---

### Get My Permissions

Get list of permissions for current user based on their roles.

**Endpoint:** `GET /users/me/permissions`

**Permission:** None (any authenticated user)

**Response (200 OK - CXO):**
```json
{
  "user_id": 1,
  "email": "cxo@example.com",
  "roles": ["CXO"],
  "permissions": [
    "document:read",
    "document:write",
    "document:delete",
    "document:upload",
    "document:analyze",
    "code:read",
    "code:write",
    "code:delete",
    "code:analyze",
    "analysis:view",
    "analysis:run",
    "analysis:delete",
    "user:read",
    "user:invite",
    "user:update_roles",
    "user:delete",
    "tenant:read",
    "tenant:update",
    "billing:view",
    "billing:manage"
  ]
}
```

**Response (200 OK - Developer):**
```json
{
  "user_id": 2,
  "email": "dev@example.com",
  "roles": ["DEVELOPER"],
  "permissions": [
    "document:read",
    "document:write",
    "document:delete",
    "document:upload",
    "document:analyze",
    "code:read",
    "code:write",
    "code:delete",
    "code:analyze",
    "analysis:view",
    "analysis:run",
    "analysis:delete",
    "validation:run",
    "validation:view_results"
  ]
}
```

---

## Billing

### Get Billing Information

Get billing details for current tenant.

**Endpoint:** `GET /billing/`

**Permission:** `billing:view` (CXO only)

**Response (200 OK - Prepaid):**
```json
{
  "id": 1,
  "tenant_id": 1,
  "billing_type": "prepaid",
  "balance_inr": "5000.00",
  "currency": "INR",
  "low_balance_threshold_inr": "100.00",
  "monthly_cost_inr": "0.00",
  "monthly_limit_inr": null,
  "last_rollover_date": "2026-01-01",
  "settings": {
    "low_balance_alerts": true,
    "auto_recharge": false
  },
  "created_at": "2026-01-25T10:00:00Z",
  "updated_at": "2026-01-25T10:00:00Z"
}
```

**Response (200 OK - Postpaid):**
```json
{
  "id": 2,
  "tenant_id": 2,
  "billing_type": "postpaid",
  "balance_inr": null,
  "currency": "INR",
  "low_balance_threshold_inr": null,
  "monthly_cost_inr": "1250.50",
  "monthly_limit_inr": "10000.00",
  "last_rollover_date": "2026-01-01",
  "settings": {},
  "created_at": "2026-01-25T11:00:00Z",
  "updated_at": "2026-01-25T14:30:00Z"
}
```

---

### Get Usage Statistics

Get detailed usage statistics for billing period.

**Endpoint:** `GET /billing/usage`

**Permission:** `billing:view` (CXO only)

**Response (200 OK):**
```json
{
  "tenant_id": 1,
  "billing_type": "prepaid",
  "current_period": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31"
  },
  "balance": {
    "current_inr": "5000.00",
    "initial_inr": "10000.00",
    "spent_inr": "5000.00"
  },
  "usage": {
    "total_analyses": 345,
    "total_cost_inr": "5000.00",
    "average_cost_per_analysis_inr": "14.49",
    "by_document_type": {
      "PRD": {
        "count": 120,
        "cost_inr": "1800.00"
      },
      "API_SPEC": {
        "count": 100,
        "cost_inr": "1500.00"
      },
      "USER_STORY": {
        "count": 125,
        "cost_inr": "1700.00"
      }
    }
  },
  "alerts": [
    {
      "type": "low_balance",
      "message": "Balance below ₹100 threshold",
      "triggered_at": "2026-01-25T14:00:00Z"
    }
  ]
}
```

---

### Add Balance

Add funds to prepaid tenant balance.

**Endpoint:** `POST /billing/add-balance`

**Permission:** `billing:manage` (CXO only)

**Request:**
```json
{
  "amount_inr": 5000.00,
  "payment_reference": "RAZORPAY-TXN-123456"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "tenant_id": 1,
  "billing_type": "prepaid",
  "balance_inr": "10000.00",
  "previous_balance_inr": "5000.00",
  "added_amount_inr": "5000.00",
  "transaction": {
    "amount_inr": "5000.00",
    "payment_reference": "RAZORPAY-TXN-123456",
    "timestamp": "2026-01-25T15:00:00Z"
  },
  "updated_at": "2026-01-25T15:00:00Z"
}
```

**Response (400 Bad Request - Postpaid Tenant):**
```json
{
  "detail": "Cannot add balance to postpaid billing type"
}
```

---

### Update Billing Settings

Update billing configuration.

**Endpoint:** `PUT /billing/settings`

**Permission:** `billing:manage` (CXO only)

**Request:**
```json
{
  "low_balance_threshold_inr": 500.00,
  "settings": {
    "low_balance_alerts": true,
    "auto_recharge": true,
    "auto_recharge_amount_inr": 5000.00,
    "auto_recharge_threshold_inr": 1000.00
  }
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "tenant_id": 1,
  "low_balance_threshold_inr": "500.00",
  "settings": {
    "low_balance_alerts": true,
    "auto_recharge": true,
    "auto_recharge_amount_inr": 5000.00,
    "auto_recharge_threshold_inr": 1000.00
  },
  "updated_at": "2026-01-25T16:00:00Z"
}
```

---

## Documents

All document endpoints are automatically scoped to current user's tenant.

### Analyze Document

Start analysis for a document (with billing check).

**Endpoint:** `POST /documents/{document_id}/analyze`

**Permission:** `document:analyze`

**Billing:** Checks balance/limit BEFORE analysis, deducts cost AFTER success

**Cost Estimation:**
- Base cost: ₹2.00
- Per KB: ₹0.01/KB
- Maximum: ₹12.00

**Response (202 Accepted):**
```json
{
  "message": "Document analysis started",
  "document_id": 123,
  "task_id": "celery-task-uuid-12345",
  "estimated_cost_inr": "3.50",
  "billing": {
    "can_afford": true,
    "balance_after_inr": "4996.50"
  }
}
```

**Response (402 Payment Required - Insufficient Balance):**
```json
{
  "detail": "Insufficient balance: ₹2.00 available, ₹3.50 required. Please add funds to your account."
}
```

**Response (402 Payment Required - Monthly Limit Exceeded):**
```json
{
  "detail": "Monthly limit exceeded: ₹9,998.00 / ₹10,000.00 used. Estimated cost: ₹3.50"
}
```

**Response (404 Not Found - Cross-Tenant Access):**
```json
{
  "detail": "Document not found"
}
```

---

## Code Components

All code component endpoints are automatically scoped to current user's tenant.

### Analyze Code Component

Start background analysis for a code component.

**Endpoint:** `POST /code-components/{component_id}/analyze`

**Permission:** `code:analyze`

**Response (202 Accepted):**
```json
{
  "message": "Code component analysis started",
  "component_id": 45,
  "task_id": "celery-task-uuid-67890"
}
```

**Response (404 Not Found - Cross-Tenant Access):**
```json
{
  "detail": "Code component not found"
}
```

---

## Validation

### Run Validation Scan

Start validation scan for documents.

**Endpoint:** `POST /validation/run`

**Permission:** `validation:run`

**Request:**
```json
{
  "document_ids": [123, 124, 125]
}
```

**Tenant Isolation:** Only validates documents belonging to current tenant

**Response (202 Accepted):**
```json
{
  "message": "Validation scan started",
  "scan_id": "scan-uuid-12345",
  "document_count": 3,
  "tenant_id": 1
}
```

---

## RBAC Permissions

### Permission Matrix

| Permission | CXO | Developer | BA | PM | Description |
|------------|-----|-----------|----|----|-------------|
| `document:read` | ✅ | ✅ | ✅ | ✅ | View documents |
| `document:write` | ✅ | ✅ | ✅ | ✅ | Create/edit documents |
| `document:delete` | ✅ | ✅ | ✅ | ❌ | Delete documents |
| `document:upload` | ✅ | ✅ | ✅ | ✅ | Upload document files |
| `document:analyze` | ✅ | ✅ | ✅ | ✅ | Run AI analysis |
| `code:read` | ✅ | ✅ | ✅ | ✅ | View code components |
| `code:write` | ✅ | ✅ | ❌ | ❌ | Create/edit code |
| `code:delete` | ✅ | ✅ | ❌ | ❌ | Delete code components |
| `code:analyze` | ✅ | ✅ | ❌ | ❌ | Run code analysis |
| `analysis:view` | ✅ | ✅ | ✅ | ✅ | View analysis results |
| `analysis:run` | ✅ | ✅ | ✅ | ❌ | Run analysis |
| `analysis:delete` | ✅ | ✅ | ✅ | ❌ | Delete analysis results |
| `user:read` | ✅ | ❌ | ❌ | ❌ | List users |
| `user:invite` | ✅ | ❌ | ❌ | ❌ | Invite users |
| `user:update_roles` | ✅ | ❌ | ❌ | ❌ | Update user roles |
| `user:delete` | ✅ | ❌ | ❌ | ❌ | Delete users |
| `tenant:read` | ✅ | ❌ | ❌ | ❌ | View tenant info |
| `tenant:update` | ✅ | ❌ | ❌ | ❌ | Update tenant settings |
| `billing:view` | ✅ | ❌ | ❌ | ❌ | View billing info |
| `billing:manage` | ✅ | ❌ | ❌ | ❌ | Manage billing |
| `validation:run` | ✅ | ✅ | ✅ | ❌ | Run validation scans |
| `validation:view_results` | ✅ | ✅ | ✅ | ❌ | View validation results |

### Role Definitions

**CXO (Chief Experience Officer)**
- Full administrative access
- All 20 permissions
- User management
- Billing management
- Tenant configuration

**Developer**
- Technical features access
- 15 permissions
- Code analysis and management
- Document analysis
- Validation scans
- ❌ No admin features

**BA (Business Analyst)**
- Document and analysis focus
- 14 permissions
- Document management
- Analysis and validation
- ❌ No code write/delete
- ❌ No admin features

**Product Manager**
- Product feature access
- 10 permissions
- Document viewing
- Analysis viewing
- ❌ No code management
- ❌ No analysis execution
- ❌ No admin features

---

## Error Responses

### Standard Error Format

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| **200** | OK | Successful request |
| **201** | Created | Resource created successfully |
| **202** | Accepted | Async operation started |
| **400** | Bad Request | Invalid input, validation error |
| **401** | Unauthorized | Missing or invalid authentication token |
| **402** | Payment Required | Insufficient balance or monthly limit exceeded |
| **403** | Forbidden | Authenticated but no permission |
| **404** | Not Found | Resource not found OR cross-tenant access (Schrödinger's Document) |
| **422** | Unprocessable Entity | Request validation failed |
| **500** | Internal Server Error | Server error |

### Schrödinger's Document Pattern

To prevent information leakage, DokyDoc returns **404 (Not Found)** instead of **403 (Forbidden)** when:
- User tries to access another tenant's resource
- User lacks permission for a resource

**Security Benefit:** Attackers cannot determine if a resource exists in another tenant.

**Example:**
```
GET /documents/999 (belongs to tenant B, user in tenant A)

Response: 404 Not Found
{
  "detail": "Document not found"
}

(NOT 403 Forbidden - this would leak that document 999 exists)
```

### Common Errors

**Missing Authentication:**
```json
{
  "detail": "Not authenticated"
}
```

**Insufficient Permissions:**
```json
{
  "detail": "You do not have permission to user:invite"
}
```

**Insufficient Balance (Prepaid):**
```json
{
  "detail": "Insufficient balance: ₹2.00 available, ₹3.50 required. Please add funds to your account."
}
```

**Monthly Limit Exceeded (Postpaid):**
```json
{
  "detail": "Monthly limit exceeded: ₹9,998.00 / ₹10,000.00 used. Estimated cost: ₹3.50"
}
```

**Tenant User Limit Reached:**
```json
{
  "detail": "Cannot invite user: tenant has reached maximum user limit (50/50)"
}
```

**Admin Lockout Prevention:**
```json
{
  "detail": "Cannot modify your own roles (admin lockout prevention)"
}
```

```json
{
  "detail": "Cannot delete your own account (admin lockout prevention)"
}
```

**Subdomain Taken:**
```json
{
  "detail": "Subdomain 'acme' is already taken"
}
```

**Email Already Exists:**
```json
{
  "detail": "A user with email 'dev@example.com' already exists in your tenant"
}
```

---

## Request Headers

All authenticated endpoints require:

```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

---

## Pagination

List endpoints support pagination with query parameters:

- `skip`: Offset (default: 0)
- `limit`: Page size (default: 100, max: 100)

**Example:**
```
GET /users/?skip=0&limit=20
```

---

## Rate Limiting

Rate limiting is applied per tenant:

- **Free tier:** 100 requests/hour
- **Basic tier:** 500 requests/hour
- **Pro tier:** 2000 requests/hour
- **Enterprise tier:** Unlimited

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 2000
X-RateLimit-Remaining: 1999
X-RateLimit-Reset: 1706194800
```

---

## Testing the API

### Using cURL

**Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "cxo@example.com", "password": "cxopassword"}'
```

**Get Tenant Info:**
```bash
TOKEN="<your_jwt_token>"
curl -X GET http://localhost:8000/api/v1/tenants/me \
  -H "Authorization: Bearer $TOKEN"
```

**Invite User:**
```bash
curl -X POST http://localhost:8000/api/v1/users/invite \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@example.com", "password": "pass123", "roles": ["DEVELOPER"]}'
```

### Using Swagger UI

Visit: `http://localhost:8000/docs`

1. Click "Authorize" button
2. Enter token: `Bearer <your_jwt_token>`
3. Click "Authorize"
4. Test endpoints interactively

---

## API Changelog

### Sprint 2 (2026-01-25)

**Added:**
- Tenant management endpoints (4 endpoints)
- User management endpoints (5 endpoints)
- Billing endpoints (4 endpoints)
- RBAC permission system (20 permissions)
- Multi-tenancy support across all endpoints
- Billing enforcement on analysis endpoints
- HTTP 402 (Payment Required) responses
- Schrödinger's Document pattern (404 not 403)

**Changed:**
- Login response now includes `tenant` and `tenant_id`
- All endpoints now filter by tenant_id
- Document analysis requires billing check
- All background tasks include tenant_id

**Security:**
- Added composite indexes for timing attack prevention
- Implemented admin lockout prevention
- Added tenant isolation in all queries

---

## Support

For API issues or questions:
- **Documentation:** See `MIGRATION_GUIDE.md`, `PERFORMANCE.md`
- **Testing:** See `tests/README.md`
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

**Last Updated:** 2026-01-25
**API Version:** v1 (Sprint 2)
**Status:** Production Ready ✅
