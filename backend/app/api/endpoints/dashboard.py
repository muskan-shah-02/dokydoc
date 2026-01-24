# backend/app/api/endpoints/dashboard.py

from fastapi import APIRouter, Depends
from typing import Any
from app.api import deps
from app.schemas.user import Role
from app.core.logging import LoggerMixin

class DashboardEndpoints(LoggerMixin):
    """Dashboard endpoints with enhanced logging and error handling."""
    
    def __init__(self):
        super().__init__()

# Create instance for use in endpoints
dashboard_endpoints = DashboardEndpoints()

router = APIRouter()

@router.get("/developer-data")
def get_developer_data(
    tenant_id: int = Depends(deps.get_tenant_id),
    # This dependency ensures only users with the "Developer" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.DEVELOPER))
) -> Any:
    """
    Get some data that is only visible to developers.

    SPRINT 2: Now includes tenant_id context for multi-tenancy isolation.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"Developer data accessed by user with roles: {current_user.get('roles', [])} (tenant_id={tenant_id})")
    return {"message": "Welcome Developer! Here is your secret data.", "tenant_id": tenant_id}

@router.get("/ba-data")
def get_ba_data(
    tenant_id: int = Depends(deps.get_tenant_id),
    # This dependency ensures only users with the "BA" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.BA))
) -> Any:
    """
    Get some data that is only visible to Business Analysts.

    SPRINT 2: Now includes tenant_id context for multi-tenancy isolation.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"BA data accessed by user with roles: {current_user.get('roles', [])} (tenant_id={tenant_id})")
    return {"message": "Hello Business Analyst! Here are the project requirements.", "tenant_id": tenant_id}

@router.get("/cxo-data")
def get_cxo_data(
    tenant_id: int = Depends(deps.get_tenant_id),
    # This dependency ensures only users with the "CXO" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.CXO))
) -> Any:
    """
    Get some data that is only visible to CXOs.

    SPRINT 2: Now includes tenant_id context for multi-tenancy isolation.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"CXO data accessed by user with roles: {current_user.get('roles', [])} (tenant_id={tenant_id})")
    return {"message": "Greetings CXO! Here is the company's financial overview.", "tenant_id": tenant_id}

@router.get("/pm-data")
def get_pm_data(
    tenant_id: int = Depends(deps.get_tenant_id),
    # This dependency ensures only users with the "Product Manager" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.PRODUCT_MANAGER))
) -> Any:
    """
    Get some data that is only visible to PMs.

    SPRINT 2: Now includes tenant_id context for multi-tenancy isolation.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"PM data accessed by user with roles: {current_user.get('roles', [])} (tenant_id={tenant_id})")
    return {"message": "Greetings PMs! Here is the company's financial overview.", "tenant_id": tenant_id}