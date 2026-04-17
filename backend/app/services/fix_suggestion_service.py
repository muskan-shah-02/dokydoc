"""
P5C-07: FixSuggestionService — generates AI-powered code fix suggestions for mismatches.
Suggestions are stored lazily in mismatch.details["suggested_fix"] on first request.
Subsequent calls return the cached suggestion without re-calling Gemini.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.mismatch import Mismatch
from app.models.requirement_atom import RequirementAtom

logger = get_logger("fix_suggestion_service")


class FixSuggestionService:

    async def get_or_generate(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
    ) -> dict:
        """
        Return cached fix suggestion if available, otherwise generate and cache.
        Never raises — returns {"error": "..."} on failure so the endpoint stays 200.
        """
        mismatch = db.query(Mismatch).filter(
            Mismatch.id == mismatch_id,
            Mismatch.tenant_id == tenant_id,
        ).first()
        if not mismatch:
            return {"error": "Mismatch not found"}

        # Return cached suggestion if already generated
        existing = (mismatch.details or {}).get("suggested_fix")
        if existing:
            return existing

        # Build code evidence string from details
        details = mismatch.details or {}
        code_evidence_parts = []
        if details.get("code_evidence"):
            for ev in details["code_evidence"]:
                code_evidence_parts.append(
                    f"File: {ev.get('file_path', 'unknown')}\n"
                    f"Lines {ev.get('start_line', '?')}-{ev.get('end_line', '?')}:\n"
                    f"{ev.get('snippet', '')}"
                )
        code_evidence = "\n\n".join(code_evidence_parts) or "No code evidence available."

        # Get atom content
        atom_content = "No atom content available."
        atom_type = mismatch.mismatch_type or "UNKNOWN"
        if mismatch.requirement_atom_id:
            atom = db.get(RequirementAtom, mismatch.requirement_atom_id)
            if atom:
                atom_content = atom.content
                atom_type = atom.atom_type or atom_type

        try:
            from app.services.ai.gemini import call_gemini_for_fix_suggestion
            fix = await call_gemini_for_fix_suggestion(
                atom_content=atom_content,
                atom_type=atom_type,
                mismatch_type=mismatch.mismatch_type or "unknown",
                mismatch_description=mismatch.description or "",
                code_evidence=code_evidence,
            )
        except Exception as e:
            logger.warning(f"[P5C-07] Fix suggestion failed for mismatch {mismatch_id}: {e}")
            fix = {
                "error": "Could not generate suggestion",
                "summary": "Manually review the BRD requirement against the code evidence above.",
                "confidence": "low",
            }

        fix["generated_at"] = datetime.utcnow().isoformat()

        # Cache in mismatch.details
        updated_details = dict(mismatch.details or {})
        updated_details["suggested_fix"] = fix
        mismatch.details = updated_details
        db.add(mismatch)
        db.commit()

        return fix


fix_suggestion_service = FixSuggestionService()
