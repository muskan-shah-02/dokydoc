import logging
from sqlalchemy.orm import Session
from typing import List

from app import crud
from app.schemas.mismatch import MismatchCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationService:
    """
    A service to run validation checks for specific documents against their
    linked code components.
    """

    def run_version_mismatch_check(self, db: Session, document_ids: List[int]):
        """
        Scans a specific list of documents and their linked code components
        for version mismatches.
        """
        if not document_ids:
            logger.warning("Version mismatch scan requested but no document IDs were provided.")
            return

        logger.info(f"Starting version mismatch scan for document IDs: {document_ids}...")
        
        # 1. Get the specific documents requested for the scan
        documents_to_scan = crud.document.get_multi_by_ids(db=db, ids=document_ids)
        
        if not documents_to_scan:
            logger.info("No valid documents found for the provided IDs.")
            return

        mismatches_found = 0
        
        # 2. Iterate through each selected document
        for document in documents_to_scan:
            logger.info(f"Processing document: '{document.filename}' (ID: {document.id}, Version: {document.version})")
            
            # 3. For each document, get the LINK objects using the correct method
            links = crud.document_code_link.get_multi_by_document(
                db=db, document_id=document.id
            )

            if not links:
                logger.info(f"Document '{document.filename}' has no linked code components. Skipping.")
                continue

            logger.info(f"Found {len(links)} links for document '{document.filename}'")

            # 4. For each link, fetch the actual code component and compare versions
            for link in links:
                code_component = crud.code_component.get(db=db, id=link.code_component_id)
                
                if not code_component:
                    logger.warning(f"Code component with ID {link.code_component_id} not found")
                    continue

                logger.info(f"Comparing versions - Document: '{document.version}' vs Code: '{code_component.version}' (Component: {code_component.name})")

                # 5. Compare the versions and create a mismatch if they are different
                if document.version != code_component.version:
                    mismatches_found += 1
                    description = (
                        f"Version mismatch! Document '{document.filename}' (v{document.version}) "
                        f"vs. Code '{code_component.name}' (v{code_component.version})."
                    )
                    
                    logger.warning(description)
                    
                    # 6. Create a new mismatch record in the database
                    mismatch_in = MismatchCreate(
                        mismatch_type="version_mismatch",
                        description=description,
                        document_id=document.id,
                        code_component_id=code_component.id,
                    )
                    
                    # Check if this exact mismatch already exists to avoid duplicates
                    existing = crud.mismatch.get_by_details(db=db, obj_in=mismatch_in)
                    if not existing:
                        crud.mismatch.create(db=db, obj_in=mismatch_in)
                    else:
                        logger.info(f"Mismatch already recorded for doc ID {document.id} and code ID {code_component.id}. Skipping.")

        logger.info(f"Version mismatch scan finished. Found {mismatches_found} potential new mismatches.")

# Create a single instance that we can import and use elsewhere
validation_service = ValidationService()