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
    # This dependency ensures only users with the "Developer" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.DEVELOPER))
) -> Any:
    """
    Get some data that is only visible to developers.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"Developer data accessed by user with roles: {current_user.get('roles', [])}")
    return {"message": "Welcome Developer! Here is your secret data."}

@router.get("/ba-data")
def get_ba_data(
    # This dependency ensures only users with the "BA" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.BA))
) -> Any:
    """
    Get some data that is only visible to Business Analysts.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"BA data accessed by user with roles: {current_user.get('roles', [])}")
    return {"message": "Hello Business Analyst! Here are the project requirements."}

@router.get("/cxo-data")
def get_cxo_data(
    # This dependency ensures only users with the "CXO" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.CXO))
) -> Any:
    """
    Get some data that is only visible to CXOs.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"CXO data accessed by user with roles: {current_user.get('roles', [])}")
    return {"message": "Greetings CXO! Here is the company's financial overview."}

@router.get("/pm-data")
def get_pm_data(
    # This dependency ensures only users with the "Product Manager" role can access this.
    current_user: dict = Depends(deps.get_current_user_with_role(Role.PRODUCT_MANAGER))
) -> Any:
    """
    Get some data that is only visible to PMs.
    """
    logger = dashboard_endpoints.logger
    logger.info(f"PM data accessed by user with roles: {current_user.get('roles', [])}")
    return {"message": "Greetings PMs! Here is the company's financial overview."}