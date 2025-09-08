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
    document_code_links, analysis_results, validation
)

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

# --- Middleware Configuration ---

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
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]  # Update with actual domain
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
    """Handle all other exceptions."""
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred" if not settings.DEBUG else str(exc),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"traceback": traceback.format_exc()} if settings.DEBUG else None
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