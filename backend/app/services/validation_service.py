# backend/app/services/validation_service.py

import logging
import asyncio
import httpx
from typing import List
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app import crud, models, schemas
from app.db.session import SessionLocal
# We will upgrade this function in our next step (Task 2.C)
from app.services.ai.gemini import call_gemini_for_validation, ValidationType, ValidationContext
from app.models.document_code_link import DocumentCodeLink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Your semaphore for rate limiting is preserved
GEMINI_API_SEMAPHORE = asyncio.Semaphore(5)

class ValidationService:
    @staticmethod
    @asynccontextmanager
    async def get_db_session():
        """
        Your robust async context manager for database sessions is preserved.
        """
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    async def run_validation_scan(user_id: int, document_ids: List[int]):
        """
        Your top-level orchestration logic is preserved. It correctly filters
        documents and links for the specific user.
        """
        if not document_ids:
            logger.warning(f"No document IDs provided for user {user_id}")
            return

        logger.info(f"Starting validation scan for user_id: {user_id} on documents: {document_ids}")
        async with ValidationService.get_db_session() as db:
            try:
                user_documents = db.query(models.Document).filter(
                    and_(
                        models.Document.owner_id == user_id,
                        models.Document.id.in_(document_ids)
                    )
                ).all()

                found_doc_ids = [doc.id for doc in user_documents]
                if len(found_doc_ids) != len(document_ids):
                    missing_docs = set(document_ids) - set(found_doc_ids)
                    logger.warning(f"Some documents not found or not owned by user {user_id}: {missing_docs}")

                if not found_doc_ids:
                    logger.warning(f"No valid documents found for user {user_id}")
                    return

                links = db.query(models.DocumentCodeLink).join(models.Document).filter(
                    and_(
                        models.Document.owner_id == user_id,
                        models.DocumentCodeLink.document_id.in_(found_doc_ids)
                    )
                ).all()

                if not links:
                    logger.info(f"No document-code links found for documents {found_doc_ids} for user {user_id}")
                    return

                # Your original task processing logic is preserved
                tasks = [ValidationService.validate_single_link(link, user_id) for link in links]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful_validations = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Validation failed for link {links[i].id}: {result}")
                    else:
                        successful_validations += 1

                logger.info(f"Validation completed: {successful_validations}/{len(links)} links processed successfully")

            except Exception as e:
                logger.error(f"Top-level error in validation scan for user {user_id}: {e}", exc_info=True)
                raise
            finally:
                logger.info(f"Validation scan finished for user_id: {user_id}")

    @staticmethod
    async def validate_single_link(link: DocumentCodeLink, user_id: int):
        """
        --- THIS IS THE UPGRADED METHOD ---
        It now performs a multi-pass validation using pre-analyzed structured data.
        """
        async with GEMINI_API_SEMAPHORE:
            async with ValidationService.get_db_session() as db:
                try:
                    # 1. Fetch the linked components
                    document = db.query(models.Document).filter(models.Document.id == link.document_id).first()
                    code_component = db.query(models.CodeComponent).filter(models.CodeComponent.id == link.code_component_id).first()

                    if not document or not code_component:
                        logger.error(f"Missing document or code component for link {link.id}")
                        return
                    
                    # 2. **CRITICAL CHANGE**: Check for pre-existing analysis instead of raw content
                    if not document.analysis_results or not code_component.structured_analysis:
                        logger.warning(f"Skipping link {link.id}: Document or Code Component has not been analyzed yet.")
                        return

                    logger.info(f"Processing link {link.id}: Doc '{document.name}' vs Code '{code_component.name}'")
                    
                    # 3. **NEW**: Clear previous results for this link to ensure a fresh scan
                    crud.mismatch.remove_by_link_id(db=db, link_id=link.id)

                    # 4. **NEW**: Define the validation checks to run for this link
                    validation_passes_to_run = [
                        ValidationType.API_ENDPOINT_MISSING,
                        ValidationType.BUSINESS_LOGIC_MISSING,
                        ValidationType.GENERAL_CONSISTENCY,
                    ]

                    # 5. **NEW**: Build a list of concurrent AI tasks for each check
                    ai_tasks = []
                    for check_type in validation_passes_to_run:
                        context = ValidationContext(
                            focus_area=check_type,
                            document_analysis=document.analysis_results,
                            code_analysis=code_component.structured_analysis,
                        )
                        ai_tasks.append(call_gemini_for_validation(context))

                    # 6. **NEW**: Run all AI validation passes concurrently
                    validation_results = await asyncio.gather(*ai_tasks)

                    # 7. **NEW**: Process and store the aggregated results
                    for mismatches in validation_results:
                        if mismatches:
                            for mismatch_data in mismatches:
                                crud.mismatch.create_with_link(
                                    db=db,
                                    obj_in=mismatch_data,
                                    link_id=link.id,
                                    owner_id=user_id
                                )
                                logger.info(f"Created new mismatch for link {link.id}")

                except Exception as e:
                    logger.error(f"Error validating link {link.id}: {e}", exc_info=True)
                    raise

validation_service = ValidationService()