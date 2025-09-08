from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from pydantic import ValidationError

class DokyDocException(Exception):
    """Base exception class for DokyDoc application."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None, 
        status_code: int = 500,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationException(DokyDocException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

class AuthenticationException(DokyDocException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class AuthorizationException(DokyDocException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN
        )

class NotFoundException(DokyDocException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource: str, resource_id: Any = None):
        message = f"{resource} not found"
        if resource_id is not None:
            message += f" with id: {resource_id}"
        
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "resource_id": resource_id}
        )

class ConflictException(DokyDocException):
    """Raised when there's a conflict with existing data."""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )

class RateLimitException(DokyDocException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

class ExternalServiceException(DokyDocException):
    """Raised when external service calls fail."""
    
    def __init__(self, service: str, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=f"{service} service error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service, "original_message": message, **(details or {})}
        )

class DocumentProcessingException(DokyDocException):
    """Raised when document processing fails."""
    
    def __init__(self, message: str, document_id: Optional[int] = None, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="DOCUMENT_PROCESSING_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"document_id": document_id, **(details or {})}
        )

class AIAnalysisException(DokyDocException):
    """Raised when AI analysis fails."""
    
    def __init__(self, message: str, model: str = None, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="AI_ANALYSIS_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"model": model, **(details or {})}
        )

def handle_validation_error(exc: ValidationError) -> HTTPException:
    """Convert Pydantic validation errors to HTTP exceptions."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": errors
        }
    )

def handle_dokydoc_exception(exc: DokyDocException) -> HTTPException:
    """Convert DokyDoc exceptions to HTTP exceptions."""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )

def create_error_response(
    error_code: str,
    message: str,
    status_code: int = 500,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {
        "error": {
            "code": error_code,
            "message": message,
            "status_code": status_code,
            "details": details or {}
        }
    }
