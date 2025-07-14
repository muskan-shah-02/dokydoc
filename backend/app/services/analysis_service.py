# This is the content for your NEW file at:
# backend/app/services/analysis_service.py

import logging
from sqlalchemy.orm import Session
import json

from app import crud, schemas
from app.services.document_parser import parser

logger = logging.getLogger(__name__)

def run_initial_analysis(db: Session, document_id: int):
    """
    Performs the initial, default analysis on a document's content.
    For our MVP, this will be extracting functional requirements.
    """
    logger.info(f"Starting initial analysis for document_id: {document_id}")
    document = crud.document.get(db=db, id=document_id)

    # Ensure we have a document with content and that the parser is available
    if not document or not document.content:
        logger.warning(f"Document {document_id} has no content to analyze. Skipping.")
        return
    if parser is None:
        logger.error("Parser not available. Skipping analysis.")
        return

    analysis_type = "functional_requirements"
    prompt = "Analyze the following document text. Extract a list of all functional requirements. Return the result as a JSON object with a single key 'requirements' which contains a list of strings."

    try:
        # Use the same Gemini parser service, but with our specific analysis prompt
        # We pass the document content directly, no need to re-upload the file
        response_text = parser.model.generate_content(
            [prompt, document.content]
        ).text
        
        # Clean the response to make sure it's valid JSON
        cleaned_response = response_text.strip().replace("```json", "").replace("```", "")
        
        # Parse the JSON string from the AI into a Python dictionary
        result_json = json.loads(cleaned_response)

        # Create the database record for the analysis result
        analysis_result_in = schemas.AnalysisResultCreate(
            document_id=document_id,
            analysis_type=analysis_type,
            result_data=result_json 
        )
        crud.analysis_result.create(db=db, obj_in=analysis_result_in)
        logger.info(f"Successfully completed analysis '{analysis_type}' for document {document_id}")

    except Exception as e:
        logger.error(f"An error occurred during analysis for document {document_id}: {e}")
        # Optionally, you could create an AnalysisResult with an error state here

