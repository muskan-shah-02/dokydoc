# backend/app/services/code_analysis_service.py

import httpx
from sqlalchemy.orm import Session
import asyncio

from app import crud
from app.db.session import SessionLocal
# We will create this function in our next step (Task 1.C)
from app.services.ai.gemini import call_gemini_for_code_analysis
from app.services.cache_service import cache_service
from app.services.billing_enforcement_service import billing_enforcement_service, InsufficientBalanceException, MonthlyLimitExceededException  # ✅ SPRINT 2 BILLING FIX
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, AIAnalysisException

class CodeAnalysisService(LoggerMixin):
    
    def __init__(self):
        super().__init__()
    
    def analyze_component_in_background(self, component_id: int, tenant_id: int = None) -> None:
        """
        This is the main entry point that will be called as a background task.
        It's a synchronous function that sets up and runs the main async logic.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            component_id: ID of the code component to analyze
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        self.logger.info(f"Setting up async analysis for component_id: {component_id}, tenant_id: {tenant_id}")
        asyncio.run(self._async_analyze_component(component_id, tenant_id))

    async def _async_analyze_component(self, component_id: int, tenant_id: int = None) -> None:
        """
        This is the core asynchronous logic for analyzing a single code component.
        It handles the entire lifecycle of fetching, analyzing, and storing results.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            component_id: ID of the code component to analyze
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        db: Session = SessionLocal()
        component = None
        try:
            # Retrieve the component from the database
            # SPRINT 2 Phase 6: Filter by tenant_id for isolation
            component = crud.code_component.get(db=db, id=component_id, tenant_id=tenant_id)
            if not component:
                self.logger.error(
                    f"CodeAnalysisService: Component with ID {component_id} not found "
                    f"in tenant {tenant_id}"
                )
                return

            # 1. Update status to 'processing' to give feedback to the UI
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "processing"})
            db.commit()

            # 2. Fetch the raw code content from the provided URL
            self.logger.info(f"Fetching code from URL: {component.location}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(component.location)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                code_content = response.text

            # 3. Try to get cached analysis first (80% cost savings!)
            self.logger.info(f"Checking cache for component {component_id}...")
            cached_result = cache_service.get_cached_analysis(
                content=code_content,
                analysis_type="code_analysis"
            )

            if cached_result:
                # Cache HIT - use cached result (no AI cost!)
                self.logger.info(f"✅ Using cached analysis for component {component_id}")
                analysis_result = cached_result
            else:
                # ✅ BILLING CHECK: Check if tenant can afford this analysis BEFORE calling Gemini
                self.logger.info(f"💰 Checking billing: tenant {tenant_id} for code component {component_id}")
                try:
                    billing_check = billing_enforcement_service.check_can_afford_analysis(
                        db=db,
                        tenant_id=tenant_id,
                        estimated_cost_inr=5.0  # Estimated cost for code analysis
                    )

                    if not billing_check["can_proceed"]:
                        error_msg = f"Insufficient funds: {billing_check['reason']}"
                        self.logger.error(f"❌ {error_msg}")
                        crud.code_component.update(
                            db, db_obj=component,
                            obj_in={"analysis_status": "failed", "analysis_error": error_msg}
                        )
                        db.commit()
                        return

                    self.logger.info(f"✅ Billing check passed for tenant {tenant_id}")

                except (InsufficientBalanceException, MonthlyLimitExceededException) as e:
                    error_msg = str(e)
                    self.logger.error(f"❌ Billing enforcement failed: {error_msg}")
                    crud.code_component.update(
                        db, db_obj=component,
                        obj_in={"analysis_status": "failed", "analysis_error": error_msg}
                    )
                    db.commit()
                    return

                # Cache MISS - call Gemini API
                self.logger.info(f"❌ Cache miss. Sending code for component {component_id} to Gemini for analysis...")
                analysis_result = await call_gemini_for_code_analysis(code_content)

                # Store result in cache for future use
                cache_service.set_cached_analysis(
                    content=code_content,
                    analysis_type="code_analysis",
                    result=analysis_result,
                    ttl_seconds=2592000  # 30 days
                )
                self.logger.info(f"💾 Cached analysis result for component {component_id}")

            # 4. Prepare the data and update the component in the database
            update_data = {
                "summary": analysis_result.get("summary"),
                "structured_analysis": analysis_result.get("structured_analysis"),
                "analysis_status": "completed",
            }
            crud.code_component.update(db, db_obj=component, obj_in=update_data)
            self.logger.info(f"Successfully completed and stored analysis for component_id: {component.id}")

        except httpx.RequestError as e:
            self.logger.error(f"HTTP Error fetching code for component {component_id}: {e}")
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during analysis for component {component_id}: {e}", exc_info=True)
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed", "summary": f"AI analysis failed: {str(e)}"})
        finally:
            # 5. Critically important: ensure the database session is always closed
            if db.is_active:
                db.commit()
            db.close()

# Create a singleton instance for easy importing elsewhere in the app
code_analysis_service = CodeAnalysisService()