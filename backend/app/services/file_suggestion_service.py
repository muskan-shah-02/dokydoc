"""
P5C-01: FileSuggestionService — analyses atom content post-atomization to suggest
which code files a developer should upload for validation coverage.
"""
from sqlalchemy.orm import Session
from app.core.logging import get_logger

logger = get_logger("file_suggestion_service")


class FileSuggestionService:

    async def generate_and_store(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
    ) -> list:
        """
        Called after atomization completes. Fetches all atoms for the document,
        calls Gemini to suggest files, stores results, returns list.
        Non-blocking — caller wraps in try/except.
        """
        from app.services.ai.gemini import call_gemini_for_file_suggestions
        from app.models.file_suggestion import FileSuggestion
        from app.models.requirement_atom import RequirementAtom

        atoms = db.query(RequirementAtom).filter_by(
            document_id=document_id, tenant_id=tenant_id
        ).all()
        if not atoms:
            return []

        atom_dicts = [
            {"atom_id": a.atom_id, "atom_type": a.atom_type, "content": a.content}
            for a in atoms
        ]

        try:
            suggestions = await call_gemini_for_file_suggestions(atom_dicts)
        except Exception as e:
            logger.warning(f"[P5C-01] File suggestion Gemini call failed: {e}")
            return []

        atom_id_to_db_id = {a.atom_id: a.id for a in atoms}

        # Delete existing suggestions for this document (re-atomization case)
        db.query(FileSuggestion).filter_by(
            document_id=document_id, tenant_id=tenant_id
        ).delete()

        stored = []
        for s in suggestions:
            db_ids = [
                atom_id_to_db_id[aid]
                for aid in s.get("atom_ids", [])
                if aid in atom_id_to_db_id
            ]
            obj = FileSuggestion(
                tenant_id=tenant_id,
                document_id=document_id,
                suggested_filename=s["filename"],
                reason=s["reason"],
                atom_ids=db_ids,
                atom_count=len(db_ids),
            )
            db.add(obj)
            stored.append(obj)

        db.commit()

        # Cache summary on document for fast dashboard reads
        try:
            from app.models.document import Document
            doc = db.get(Document, document_id)
            if doc:
                doc.file_suggestion_summary = {
                    "total_suggestions": len(stored),
                    "filenames": [s.suggested_filename for s in stored],
                    "uncovered_atom_count": sum(s.atom_count for s in stored),
                }
                db.add(doc)
                db.commit()
        except Exception:
            pass

        logger.info(f"[P5C-01] Generated {len(stored)} file suggestions for doc {document_id}")
        return stored

    def mark_fulfilled(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        filename: str,
        component_id: int,
    ) -> int:
        """
        Called when a code file is uploaded. Marks matching suggestions as fulfilled.
        Returns number of suggestions updated.
        """
        from app.models.file_suggestion import FileSuggestion

        pending = db.query(FileSuggestion).filter(
            FileSuggestion.document_id == document_id,
            FileSuggestion.tenant_id == tenant_id,
            FileSuggestion.fulfilled_by_component_id.is_(None),
            FileSuggestion.suggested_filename.ilike(f"%{filename}%"),
        ).all()
        for suggestion in pending:
            suggestion.fulfilled_by_component_id = component_id
        if pending:
            db.commit()
        return len(pending)


file_suggestion_service = FileSuggestionService()
