# This is the updated content for your file at:
# backend/app/services/code_analysis_service.py

import httpx
from sqlalchemy.orm import Session
import logging
import asyncio  # Import asyncio

from app import crud
from app.db.session import SessionLocal
from app.services.ai.gemini import call_gemini_for_code_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeAnalysisService:
    @staticmethod
    def analyze_component(component_id: int) -> None:
        """
        The main service function to orchestrate the analysis of a code component.
        This function now calls the real Gemini API.
        """
        # This function is synchronous, but it calls an async function.
        # We need to run the async part in a new event loop.
        asyncio.run(CodeAnalysisService._async_analyze_component(component_id))

    @staticmethod
    async def _async_analyze_component(component_id: int) -> None:
        """
        Asynchronous part of the analysis logic.
        """
        db: Session = SessionLocal()
        component = None
        try:
            component = crud.code_component.get(db=db, id=component_id)
            if not component:
                logger.error(f"CodeAnalysisService: Component with ID {component_id} not found.")
                return

            logger.info(f"Starting analysis for component_id: {component.id}")
            # Ensure obj_in is a dictionary for the update
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "processing"})
            db.commit() # Commit status change immediately

            logger.info(f"Fetching code from URL: {component.location}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(component.location)
                response.raise_for_status()
                code_content = response.text

            analysis_result = await call_gemini_for_code_analysis(code_content)

            update_data = {
                "summary": analysis_result.get("summary"),
                "structured_analysis": analysis_result.get("structured_analysis"),
                "analysis_status": "completed",
            }
            crud.code_component.update(db, db_obj=component, obj_in=update_data)
            logger.info(f"Successfully completed analysis for component_id: {component.id}")

        except httpx.RequestError as e:
            logger.error(f"HTTP Error fetching code for component {component_id}: {e}")
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
        except Exception as e:
            logger.error(f"An unexpected error occurred during analysis for component {component_id}: {e}", exc_info=True)
            if component:
                crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed", "summary": f"AI analysis failed: {str(e)}"})
        finally:
            if db.is_active:
                db.commit()
            db.close()


code_analysis_service = CodeAnalysisService()