# backend/app/services/validation_service.py

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
from app.core.logging import LoggerMixin
from app.core.exceptions import ValidationException, AIAnalysisException

# Your semaphore for rate limiting is preserved
GEMINI_API_SEMAPHORE = asyncio.Semaphore(5)

class ValidationService(LoggerMixin):
    
    def __init__(self):
        super().__init__()
    
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

    async def run_validation_scan(self, user_id: int, document_ids: List[int], tenant_id: int = None):
        """
        Run validation scan for documents.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            user_id: User ID who triggered the scan
            document_ids: List of document IDs to validate
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        if not document_ids:
            self.logger.warning(f"No document IDs provided for user {user_id}")
            return

        self.logger.info(
            f"Starting validation scan for user_id: {user_id}, tenant_id: {tenant_id} "
            f"on documents: {document_ids}"
        )
        async with ValidationService.get_db_session() as db:
            try:
                # SPRINT 2 Phase 6: Filter by tenant_id for isolation
                filters = [
                    models.Document.owner_id == user_id,
                    models.Document.id.in_(document_ids)
                ]
                if tenant_id:
                    filters.append(models.Document.tenant_id == tenant_id)

                user_documents = db.query(models.Document).filter(and_(*filters)).all()

                found_doc_ids = [doc.id for doc in user_documents]
                if len(found_doc_ids) != len(document_ids):
                    missing_docs = set(document_ids) - set(found_doc_ids)
                    self.logger.warning(f"Some documents not found or not owned by user {user_id}: {missing_docs}")

                if not found_doc_ids:
                    self.logger.warning(f"No valid documents found for user {user_id}")
                    return

                # SPRINT 2 Phase 6: Filter links by tenant_id
                link_filters = [
                    models.Document.owner_id == user_id,
                    models.DocumentCodeLink.document_id.in_(found_doc_ids)
                ]
                if tenant_id:
                    link_filters.append(models.Document.tenant_id == tenant_id)

                links = db.query(models.DocumentCodeLink).join(models.Document).filter(
                    and_(*link_filters)
                ).all()

                if not links:
                    self.logger.info(
                        f"No document-code links found for documents {found_doc_ids} "
                        f"for user {user_id} (tenant_id={tenant_id})"
                    )
                    return

                # SPRINT 2 Phase 6: Pass tenant_id to validate_single_link
                tasks = [self.validate_single_link(link, user_id, tenant_id) for link in links]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful_validations = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Validation failed for link {links[i].id}: {result}")
                    else:
                        successful_validations += 1

                self.logger.info(f"Validation completed: {successful_validations}/{len(links)} links processed successfully")

            except Exception as e:
                self.logger.error(f"Top-level error in validation scan for user {user_id}: {e}", exc_info=True)
                raise
            finally:
                self.logger.info(f"Validation scan finished for user_id: {user_id}")

    async def validate_single_link(self, link: DocumentCodeLink, user_id: int, tenant_id: int = None):
        """
        Validate a single document-code link.

        SPRINT 2 Phase 6: Added tenant_id for multi-tenancy isolation.

        Args:
            link: DocumentCodeLink to validate
            user_id: User ID who owns the link
            tenant_id: Tenant ID for isolation (SPRINT 2)
        """
        async with GEMINI_API_SEMAPHORE:
            async with ValidationService.get_db_session() as db:
                try:
                    # SPRINT 2 Phase 6: Filter by tenant_id
                    doc_filters = [models.Document.id == link.document_id]
                    if tenant_id:
                        doc_filters.append(models.Document.tenant_id == tenant_id)
                    document = db.query(models.Document).filter(and_(*doc_filters)).first()

                    code_filters = [models.CodeComponent.id == link.code_component_id]
                    if tenant_id:
                        code_filters.append(models.CodeComponent.tenant_id == tenant_id)
                    code_component = db.query(models.CodeComponent).filter(and_(*code_filters)).first()

                    if not document or not code_component:
                        self.logger.error(
                            f"Missing document or code component for link {link.id} "
                            f"(tenant_id={tenant_id})"
                        )
                        return

                    # SPRINT 2 Phase 6: Pass tenant_id to CRUD
                    if tenant_id:
                        doc_analysis_objects = crud.analysis_result.get_multi_by_document(
                            db=db, document_id=document.id, tenant_id=tenant_id
                        )
                    else:
                        doc_analysis_objects = crud.analysis_result.get_multi_by_document(
                            db=db, document_id=document.id
                        )

                    if not doc_analysis_objects or not code_component.structured_analysis:
                        self.logger.warning(f"Skipping link {link.id}: Document or Code Component has not been fully analyzed yet.")
                        return

                    # --- THE FINAL FIX IS HERE ---
                    # The column in the AnalysisResult model is named 'result'.
                    document_analysis_data = [res.result_data for res in doc_analysis_objects]

                    self.logger.info(f"Processing link {link.id}: Doc '{document.filename}' vs Code '{code_component.name}'")

                    
                    crud.mismatch.remove_by_link(db=db, document_id=document.id, code_component_id=code_component.id)

                    validation_passes_to_run = [
                        ValidationType.API_ENDPOINT_MISSING,
                        ValidationType.BUSINESS_LOGIC_MISSING,
                        ValidationType.GENERAL_CONSISTENCY,
                    ]

                    ai_tasks = []
                    for check_type in validation_passes_to_run:
                        context = ValidationContext(
                            focus_area=check_type,
                            document_analysis=document_analysis_data,
                            code_analysis=code_component.structured_analysis,
                        )
                        ai_tasks.append(call_gemini_for_validation(context))

                    validation_results = await asyncio.gather(*ai_tasks)

                    for mismatches in validation_results:
                        if mismatches:
                            for mismatch_data in mismatches:
                                crud.mismatch.create_with_link(
                                    db=db,
                                    obj_in=mismatch_data,
                                    link_id=link.id,
                                    owner_id=user_id
                                )
                                self.logger.info(f"Created new mismatch for link {link.id}")

                except Exception as e:
                    self.logger.error(f"Error validating link {link.id}: {e}", exc_info=True)
                    raise

validation_service = ValidationService()