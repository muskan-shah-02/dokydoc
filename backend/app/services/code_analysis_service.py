# This is the updated content for your file at:
# backend/app/services/code_analysis_service.py

import httpx
from sqlalchemy.orm import Session
import logging

from app import crud
from app.db.session import SessionLocal
# --- UPDATED: Import the real Gemini helper ---
from app.services.ai.gemini import call_gemini_for_code_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeAnalysisService:
    @staticmethod
    async def analyze_component(component_id: int) -> None:
        """
        The main service function to orchestrate the analysis of a code component.
        This function now calls the real Gemini API.
        """
        db: Session = SessionLocal()
        try:
            component = crud.code_component.get(db=db, id=component_id)
            if not component:
                logger.error(f"CodeAnalysisService: Component with ID {component_id} not found.")
                return

            logger.info(f"Starting analysis for component_id: {component.id}")
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "processing"})

            logger.info(f"Fetching code from URL: {component.location}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(component.location)
                response.raise_for_status()
                code_content = response.text

            # --- UPDATED: Use the real AI call ---
            # The mock function has been removed, and we are now calling our real service.
            analysis_result = await call_gemini_for_code_analysis(code_content)

            update_data = {
                "summary": analysis_result.get("summary"),
                "structured_analysis": analysis_result.get("structured_analysis"),
                "analysis_status": "completed",
            }
            crud.code_component.update(db, db_obj=component, obj_in=update_data)
            logger.info(f"Successfully completed analysis for component_id: {component.id}")

        except httpx.RequestError as e:
            logger.error(f"HTTP Error fetching code for component {component.id}: {e}")
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
        except Exception as e:
            logger.error(f"An unexpected error occurred during analysis for component {component.id}: {e}", exc_info=True)
            crud.code_component.update(db, db_obj=component, obj_in={"analysis_status": "failed"})
        finally:
            db.close()

code_analysis_service = CodeAnalysisService()
