# This is the content for your NEW file at:
# backend/app/api/endpoints/analysis_results.py

from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.document_parser import parser # We need the parser for analysis

router = APIRouter()

# --- This is our new AI analysis background task ---
def perform_analysis(db: Session, document_id: int, analysis_type: str, prompt: str):
    """
    This function runs in the background. It gets the document's text,
    sends it to the Gemini API with a specific prompt for analysis,
    and saves the structured result.
    """
    print(f"Starting analysis '{analysis_type}' for document_id: {document_id}")
    document = crud.document.get(db=db, id=document_id)
    if not document or not document.content:
        print(f"Document {document_id} has no content to analyze.")
        return

    if parser is None:
        print("Parser not available. Skipping analysis.")
        return

    try:
        # Use the same Gemini parser service, but with a specific analysis prompt
        analysis_text = parser.parse(document.storage_path, prompt=prompt)
        
        # The Gemini API should return a JSON string, which we store directly.
        # In a real app, you might parse this string to validate its structure.
        analysis_result_in = schemas.AnalysisResultCreate(
            document_id=document_id,
            analysis_type=analysis_type,
            result_data={"result": analysis_text} # Storing the raw text for now
        )
        crud.analysis_result.create(db=db, obj_in=analysis_result_in)
        print(f"Successfully completed analysis '{analysis_type}' for document {document_id}")

    except Exception as e:
        print(f"An error occurred during analysis for document {document_id}: {e}")


@router.get("/document/{document_id}", response_model=List[schemas.AnalysisResult])
def get_analysis_results_for_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all existing analysis results for a specific document.
    """
    # Verify user owns the document
    document = crud.document.get(db=db, id=document_id)
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found or not authorized")

    return crud.analysis_result.get_multi_by_document(db=db, document_id=document_id)


@router.post("/document/{document_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_new_analysis(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> Any:
    """
    Trigger a new, targeted AI analysis on a document's content.
    This endpoint responds instantly and schedules the analysis to run in the background.
    """
    document = crud.document.get(db=db, id=document_id)
    if not document or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found or not authorized")

    # For our MVP, we will hard-code the prompt for "functional_requirements"
    analysis_type = "functional_requirements"
    prompt = "Analyze the following document text and extract a list of all functional requirements. Return the result as a simple JSON array of strings."

    background_tasks.add_task(
        perform_analysis,
        db=db,
        document_id=document_id,
        analysis_type=analysis_type,
        prompt=prompt
    )

    return {"message": "Analysis has been scheduled to run in the background."}

