"""
Data Flywheel — Capture AI Judgments

Thin helpers that bridge the core services (validation, mapping) to the
training_examples table. Called after every AI decision. Never raises —
capture failures must not interrupt the core workflow.
"""
import json
from sqlalchemy.orm import Session

from app import crud
from app.models.mismatch import Mismatch


def capture_mismatch_judgment(
    db: Session,
    *,
    mismatch: Mismatch,
    tenant_id: int,
) -> None:
    """
    Record one mismatch detection as a training example.

    input_text  = the mismatch description + type (what the model saw)
    ai_output   = structured JSON of the mismatch fields (what model said)
    """
    input_text = (
        f"Mismatch type: {mismatch.mismatch_type}\n"
        f"Description: {mismatch.description or ''}\n"
        f"Severity: {mismatch.severity or ''}"
    )
    ai_output = json.dumps({
        "mismatch_type": mismatch.mismatch_type,
        "severity": mismatch.severity,
        "description": mismatch.description,
        "status": mismatch.status,
        "direction": getattr(mismatch, "direction", None),
    }, default=str)

    crud.training_example.capture(
        db=db,
        tenant_id=tenant_id,
        task_type="mismatch_detection",
        input_text=input_text,
        ai_output=ai_output,
        source_mismatch_id=mismatch.id,
    )


def capture_mapping_judgment(
    db: Session,
    *,
    tenant_id: int,
    document_concept_name: str,
    code_concept_name: str,
    match_score: float,
    match_tier: str,
    model_name: str = None,
) -> None:
    """
    Record one concept mapping decision as a training example.
    Called from mapping_service after a Tier 3 (AI) match is made.
    """
    input_text = (
        f"Document concept: {document_concept_name}\n"
        f"Code concept: {code_concept_name}"
    )
    ai_output = json.dumps({
        "match_score": match_score,
        "match_tier": match_tier,
        "matched": match_score >= 0.5,
    })

    crud.training_example.capture(
        db=db,
        tenant_id=tenant_id,
        task_type="concept_mapping",
        input_text=input_text,
        ai_output=ai_output,
        ai_confidence=match_score,
        model_name=model_name,
    )
