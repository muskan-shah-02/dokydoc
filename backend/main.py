from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import traceback

from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.exceptions import DokyDocException, handle_dokydoc_exception, create_error_response
from app.db.session import init_database, close_database_connections, check_database_health
from app.api.endpoints import (
    login, dashboard, documents, code_components,
    document_code_links, analysis_results, validation, billing, tenants, users, tasks,  # SPRINT 2 Phase 10
    ontology, initiatives,  # SPRINT 3: Business Ontology Engine + Governance
    repositories,  # SPRINT 3: Code Analysis Engine
    webhooks,  # SPRINT 4: Git Webhook Integration (ADHOC-09)
    audit, notifications, exports,  # SPRINT 5: Audit Trail, Notifications, Exports
    search,  # SPRINT 5: Unified Semantic Search
    approvals,  # SPRINT 6: Approval Workflow
    chat,  # SPRINT 7: RAG/Chat Assistant
    api_keys,  # SPRINT 8: API Key Authentication
    auto_docs,  # SPRINT 8: Auto Docs (Module 12)
    integrations,  # SPRINT 8: Documentation Integrations (Module 11)
    analytics,  # SPRINT 8: Analytics Dashboard
    training_examples,  # Phase 1: Data Flywheel
)
from app.middleware.rate_limiter import limiter, custom_rate_limit_handler
from app.middleware.tenant_context import TenantContextMiddleware
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.api_key_auth import ApiKeyAuthMiddleware
from slowapi.errors import RateLimitExceeded

# Setup logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("🚀 Starting DokyDoc application...")
    
    # Initialize database
    if not init_database():
        logger.error("❌ Failed to initialize database. Application startup failed.")
        raise RuntimeError("Database initialization failed")
    
    logger.info("✅ Database initialized successfully")

    # Sprint 6: Initialize field encryption listeners
    from app.services.field_encryption import register_encryption_listeners
    register_encryption_listeners()

    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    logger.info(f"📊 API Version: {settings.API_VERSION}")

    yield
    
    # Shutdown
    logger.info("🛑 Shutting down DokyDoc application...")
    close_database_connections()
    logger.info("✅ Application shutdown completed")

# Create the main FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# API-01 FIX: Add rate limiter state to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# --- Middleware Configuration ---

# SPRINT 8: API Key Auth Middleware (resolves X-API-Key before tenant context)
app.add_middleware(ApiKeyAuthMiddleware)

# SPRINT 5: Audit Middleware (logs mutating requests, runs AFTER tenant context)
app.add_middleware(AuditMiddleware)

# SPRINT 2: Tenant Context Middleware (MUST be added BEFORE CORS)
# This extracts tenant_id from JWT and injects it into request.state
app.add_middleware(TenantContextMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted host middleware (security)
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["dokydoc.com", "*.dokydoc.com", "localhost", "127.0.0.1"]
    )

# --- Request/Response Middleware ---

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()
    
    # Log request
    logger.info(
        f"📥 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}"
    )
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s"
    )
    
    return response

# --- Exception Handlers ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(f"Validation error in {request.method} {request.url.path}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation_errors": exc.errors()}
        )
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP exception in {request.method} {request.url.path}: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error_code="HTTP_ERROR",
            message=str(exc.detail),
            status_code=exc.status_code
        )
    )

@app.exception_handler(DokyDocException)
async def dokydoc_exception_handler(request: Request, exc: DokyDocException):
    """Handle custom DokyDoc exceptions."""
    logger.error(f"DokyDoc exception in {request.method} {request.url.path}: {exc.error_code} - {exc.message}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details
        )
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all other exceptions.
    BE-01 FIX: Provides actionable error messages in production without exposing sensitive details.
    """
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}\n"
        f"Traceback: {traceback.format_exc()}"
    )

    # BE-01 FIX: Categorize errors and provide actionable messages
    error_type = type(exc).__name__
    error_message = str(exc)

    # Provide user-friendly messages based on error type
    if "Database" in error_type or "sqlalchemy" in str(type(exc).__module__).lower():
        user_message = "Database operation failed. Please try again in a few moments."
        error_code = "DATABASE_ERROR"
    elif "Connection" in error_type or "Timeout" in error_type:
        user_message = "Service temporarily unavailable. Please try again."
        error_code = "CONNECTION_ERROR"
    elif "Permission" in error_type or "Access" in error_type:
        user_message = "Access denied. Please check your permissions."
        error_code = "PERMISSION_ERROR"
    elif "File" in error_type or "IO" in error_type:
        user_message = "File operation failed. Please check your file and try again."
        error_code = "FILE_ERROR"
    elif "Value" in error_type or "Type" in error_type:
        user_message = "Invalid data provided. Please check your input."
        error_code = "DATA_ERROR"
    else:
        user_message = "An unexpected error occurred. Our team has been notified."
        error_code = "INTERNAL_ERROR"

    # In debug mode, include full error details
    if settings.DEBUG:
        user_message = f"{user_message} (Debug: {error_type}: {error_message})"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            error_code=error_code,
            message=user_message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "error_type": error_type,
                "traceback": traceback.format_exc()
            } if settings.DEBUG else {"error_type": error_type}  # Still provide error type in production
        )
    )

# --- Health Check Endpoints ---

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check including database status."""
    from app.db.session import get_database_info
    
    db_health = check_database_health()
    db_info = get_database_info()
    
    return {
        "status": "healthy" if db_health else "unhealthy",
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_info,
        "timestamp": time.time()
    }

# --- Root Endpoint ---

@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint for the API."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API!",
        "version": settings.PROJECT_VERSION,
        "description": settings.PROJECT_DESCRIPTION,
        "docs": "/docs" if settings.DEBUG else "Not available in production",
        "health": "/health"
    }

# --- API Router Registration ---

# Include the routers from the endpoint modules
app.include_router(
    login.router,
    tags=["Authentication"],
    prefix="/api"
)

# SPRINT 2 Phase 3: Tenant registration and management
app.include_router(
    tenants.router,
    tags=["Tenants"],
    prefix=f"/api/{settings.API_VERSION}/tenants"
)

# SPRINT 2 Phase 5: Tenant user management (RBAC)
app.include_router(
    users.router,
    tags=["User Management"],
    prefix=f"/api/{settings.API_VERSION}/users"
)

app.include_router(
    dashboard.router,
    tags=["Dashboard"],
    prefix="/api/dashboard"
)

app.include_router(
    documents.router, 
    prefix=f"/api/{settings.API_VERSION}/documents", 
    tags=["Documents"]
)

app.include_router(
    code_components.router, 
    prefix=f"/api/{settings.API_VERSION}/code-components", 
    tags=["Code Components"]
)

app.include_router(
    document_code_links.router, 
    prefix=f"/api/{settings.API_VERSION}/links", 
    tags=["Document-Code Links"]
)

app.include_router(
    analysis_results.router, 
    prefix=f"/api/{settings.API_VERSION}/analysis", 
    tags=["Analysis"]
)

app.include_router(
    validation.router,
    prefix=f"/api/{settings.API_VERSION}/validation",
    tags=["Validation"]
)

app.include_router(
    billing.router,
    prefix=f"/api/{settings.API_VERSION}/billing",
    tags=["Billing"]
)

# SPRINT 2 Extended Phase 10: Task Management
app.include_router(
    tasks.router,
    prefix=f"/api/{settings.API_VERSION}/tasks",
    tags=["Tasks"]
)

# SPRINT 3: Business Ontology Engine
app.include_router(
    ontology.router,
    prefix=f"/api/{settings.API_VERSION}/ontology",
    tags=["Ontology"]
)

# SPRINT 3: Initiative Governance
app.include_router(
    initiatives.router,
    prefix=f"/api/{settings.API_VERSION}/initiatives",
    tags=["Initiatives"]
)

# SPRINT 3: Code Analysis Engine — Repository Management
app.include_router(
    repositories.router,
    prefix=f"/api/{settings.API_VERSION}/repositories",
    tags=["Repositories"]
)

# SPRINT 4: Git Webhook Integration (ADHOC-09) — no auth required (signature-verified)
app.include_router(
    webhooks.router,
    prefix=f"/api/{settings.API_VERSION}/webhooks",
    tags=["Webhooks"]
)

# SPRINT 5: Audit Trail
app.include_router(
    audit.router,
    prefix=f"/api/{settings.API_VERSION}/audit",
    tags=["Audit Trail"]
)

# SPRINT 5: Notifications
app.include_router(
    notifications.router,
    prefix=f"/api/{settings.API_VERSION}/notifications",
    tags=["Notifications"]
)

# SPRINT 5: Data Exports
app.include_router(
    exports.router,
    prefix=f"/api/{settings.API_VERSION}/exports",
    tags=["Exports"]
)

# SPRINT 5: Unified Semantic Search
app.include_router(
    search.router,
    prefix=f"/api/{settings.API_VERSION}/search",
    tags=["Search"]
)

# SPRINT 6: Approval Workflow
app.include_router(
    approvals.router,
    prefix=f"/api/{settings.API_VERSION}/approvals",
    tags=["Approvals"]
)

# SPRINT 7: RAG/Chat Assistant
app.include_router(
    chat.router,
    prefix=f"/api/{settings.API_VERSION}/chat",
    tags=["Chat"]
)

# SPRINT 8: API Key Management
app.include_router(
    api_keys.router,
    prefix=f"/api/{settings.API_VERSION}/api-keys",
    tags=["API Keys"]
)

# SPRINT 8: Auto Docs (Module 12)
app.include_router(
    auto_docs.router,
    prefix=f"/api/{settings.API_VERSION}/auto-docs",
    tags=["Auto Docs"]
)

# SPRINT 8: Documentation Integrations (Module 11)
app.include_router(
    integrations.router,
    prefix=f"/api/{settings.API_VERSION}/integrations",
    tags=["Integrations"]
)

# SPRINT 8: Analytics Dashboard
app.include_router(
    analytics.router,
    prefix=f"/api/{settings.API_VERSION}/analytics",
    tags=["Analytics"]
)

# Phase 1: Data Flywheel
app.include_router(
    training_examples.router,
    prefix=f"/api/{settings.API_VERSION}/training-examples",
    tags=["Training Examples"]
)

# --- Startup Event (Legacy support) ---

@app.on_event("startup")
async def startup_event():
    """Legacy startup event for backward compatibility."""
    logger.info("Legacy startup event triggered")

@app.on_event("shutdown")
async def shutdown_event():
    """Legacy shutdown event for backward compatibility."""
    logger.info("Legacy shutdown event triggered")

# --- Application Info ---

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_level=settings.LOG_LEVEL.lower()
    )