# backend/app/services/code_analysis_service.py

import httpx
from sqlalchemy.orm import Session
import asyncio

from app import crud
from app.db.session import SessionLocal
# We will create this function in our next step (Task 1.C)
from app.services.ai.gemini import call_gemini_for_code_analysis
from app.core.logging import LoggerMixin
from app.core.exceptions import DocumentProcessingException, AIAnalysisException

class CodeAnalysisService(LoggerMixin):
    
    def __init__(self):
        super().__init__()
    
    def analyze_component_in_background(self, component_id: int) -> None:
        """
        This is the main entry point that will be called as a background task.
        It's a synchronous function that sets up and runs the main async logic.
        """
        self.logger.info(f"Setting up async analysis for component_id: {component_id}")
        asyncio.run(self._async_analyze_component(component_id))

    async def _async_analyze_component(self, component_id: int) -> None:
        """
        This is the core asynchronous logic for analyzing a single code component.
        It handles the entire lifecycle of fetching, analyzing, and storing results.
        """
        db: Session = SessionLocal()
        component = None
        try:
            # Retrieve the component from the database
            component = crud.code_component.get(db=db, id=component_id)
            if not component:
                self.logger.error(f"CodeAnalysisService: Component with ID {component_id} not found.")
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

            # 3. Call the Gemini API for a structured analysis (we build this function next)
            self.logger.info(f"Sending code for component {component_id} to Gemini for analysis...")
            analysis_result = await call_gemini_for_code_analysis(code_content)

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