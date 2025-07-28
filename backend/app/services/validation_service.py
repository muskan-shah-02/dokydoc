# This is the corrected content for your file at:
# backend/app/services/validation_service.py

import logging
import asyncio
from typing import List
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
# --- Import `and_` for combining filters ---
from sqlalchemy import and_

from app import crud, models, schemas
from app.db.session import SessionLocal
from app.services.ai.gemini import call_gemini_for_validation, ValidationType, ValidationContext
from app.models.document_code_link import DocumentCodeLink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_SEMAPHORE = asyncio.Semaphore(5)

class ValidationService:
    @staticmethod
    @asynccontextmanager
    async def get_db_session():
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    async def run_validation_scan(user_id: int, document_ids: List[int]):
        """
        Runs a validation scan for a specific list of documents linked to a user's code.
        """
        if not document_ids:
            logger.warning(f"No document IDs provided for user {user_id}")
            return
            
        logger.info(f"Starting validation scan for user_id: {user_id} on documents: {document_ids}")
        async with ValidationService.get_db_session() as db:
            try:
                # First, validate that all requested documents belong to the user
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

                # Fetch only the links related to the selected documents that belong to the user
                links = db.query(models.DocumentCodeLink).join(models.Document).filter(
                    and_(
                        models.Document.owner_id == user_id,
                        models.DocumentCodeLink.document_id.in_(found_doc_ids)
                    )
                ).all()

                logger.info(f"Found {len(links)} links to validate for the selected documents.")
                if not links:
                    logger.info(f"No document-code links found for documents {found_doc_ids} for user {user_id}")
                    return

                # Process validation tasks
                tasks = [ValidationService.validate_single_link(link, user_id) for link in links]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Log any exceptions that occurred
                successful_validations = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Validation failed for link {links[i].id}: {result}")
                    else:
                        successful_validations += 1
                
                logger.info(f"Validation completed: {successful_validations}/{len(links)} links processed successfully")

            except Exception as e:
                logger.error(f"Top-level error in validation scan for user {user_id}: {e}", exc_info=True)
                raise  # Re-raise to let the API endpoint handle it
            finally:
                logger.info(f"Validation scan finished for user_id: {user_id}")
    
    @staticmethod
    async def validate_single_link(link: DocumentCodeLink, user_id: int):
        """
        Validates a single document-code link using Gemini AI.
        """
        async with GEMINI_API_SEMAPHORE:
            try:
                async with ValidationService.get_db_session() as db:
                    # Fetch the document and code component
                    document = db.query(models.Document).filter(models.Document.id == link.document_id).first()
                    code_component = db.query(models.CodeComponent).filter(models.CodeComponent.id == link.code_component_id).first()
                    
                    if not document or not code_component:
                        logger.error(f"Missing document or code component for link {link.id}")
                        return
                    
                    if not document.content:
                        logger.warning(f"Document {document.id} has no content to validate")
                        return
                    
                    logger.info(f"Validating link {link.id}: {document.filename} <-> {code_component.name}")
                    
                    # Create validation context
                    context = ValidationContext(
                        document_content=document.content,
                        code_content=code_component.content, # Corrected: 'content' instead of 'location'
                        document_type=document.document_type,
                        validation_type=ValidationType.CONSISTENCY_CHECK
                    )
                    
                    # Call Gemini for validation
                    validation_result = await call_gemini_for_validation(context)
                    
                    if validation_result and validation_result.has_mismatch:
                        # Create mismatch record
                        mismatch_data = {
                            "document_id": document.id,
                            "code_component_id": code_component.id,
                            "mismatch_type": validation_result.mismatch_type,
                            "description": validation_result.description,
                            "severity": validation_result.severity,
                            "confidence": validation_result.confidence,
                            "details": {
                                "expected": validation_result.expected_value,
                                "actual": validation_result.actual_value,
                                "evidence_document": validation_result.document_evidence,
                                "evidence_code": validation_result.code_evidence,
                                "suggested_action": validation_result.suggested_action
                            },
                            "status": "open"
                        }
                        
                        # Save mismatch to database
                        mismatch = crud.mismatch.create_with_owner(
                            db=db, 
                            obj_in=schemas.MismatchCreate(**mismatch_data), 
                            owner_id=user_id
                        )
                        
                        logger.info(f"Created mismatch {mismatch.id} for link {link.id}")
                    else:
                        logger.info(f"No mismatch found for link {link.id}")
                        
            except Exception as e:
                logger.error(f"Error validating link {link.id}: {e}", exc_info=True)
                raise

def run_validation_scan_sync(user_id: int, document_ids: List[int]):
    """
    Synchronous wrapper for the async validation scan.
    """
    logger.info(f"Initiating sync wrapper for validation scan for user_id: {user_id}")
    asyncio.run(ValidationService.run_validation_scan(user_id, document_ids))

validation_service = ValidationService()