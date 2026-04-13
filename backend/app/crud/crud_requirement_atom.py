from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.requirement_atom import RequirementAtom
from app.schemas.requirement_atom import RequirementAtomCreate, RequirementAtomBase
from app.crud.base import CRUDBase


class CRUDRequirementAtom(CRUDBase[RequirementAtom, RequirementAtomCreate, RequirementAtomBase]):
    """
    CRUD for RequirementAtom — the typed atomic units extracted from BRD documents.

    Atoms are cached per (document_id, document_version). When the document version
    hasn't changed, `get_by_document_version` returns the cached atoms so re-atomization
    is skipped (no AI cost).
    """

    def get_by_document_version(
        self,
        db: Session,
        *,
        document_id: int,
        document_version: str,
    ) -> List[RequirementAtom]:
        """Return cached atoms for a specific document version."""
        return (
            db.query(self.model)
            .filter(
                self.model.document_id == document_id,
                self.model.document_version == document_version,
            )
            .order_by(self.model.atom_id)
            .all()
        )

    def get_by_document(
        self,
        db: Session,
        *,
        document_id: int,
    ) -> List[RequirementAtom]:
        """Return all atoms for a document regardless of version (latest re-atomization)."""
        return (
            db.query(self.model)
            .filter(self.model.document_id == document_id)
            .order_by(self.model.atom_id)
            .all()
        )

    def delete_by_document(self, db: Session, *, document_id: int) -> int:
        """Delete all atoms for a document (called before re-atomization)."""
        n = db.query(self.model).filter(
            self.model.document_id == document_id
        ).delete()
        db.commit()
        return n

    def create_atoms_bulk(
        self,
        db: Session,
        *,
        tenant_id: int,
        document_id: int,
        document_version: str,
        atoms_data: List[dict],
        atomized_at_upload: bool = False,
    ) -> List[RequirementAtom]:
        """
        Bulk-insert RequirementAtom rows in a single transaction.

        atoms_data: list of dicts with keys:
            atom_id (str)      — "REQ-001"
            atom_type (str)    — "API_CONTRACT" | "BUSINESS_RULE" | ...
            content (str)      — the original BRD sentence
            criticality (str)  — "critical" | "standard" | "informational"
        """
        now = datetime.now()
        db_objs = []
        for i, atom in enumerate(atoms_data):
            db_obj = RequirementAtom(
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=document_version,
                atom_id=atom.get("atom_id") or f"REQ-{i+1:03d}",
                atom_type=atom.get("atom_type", "FUNCTIONAL_REQUIREMENT"),
                content=atom.get("content", ""),
                criticality=atom.get("criticality", "standard"),
                atomized_at_upload=atomized_at_upload,  # P4-01
                created_at=now,
                updated_at=now,
            )
            db.add(db_obj)
            db_objs.append(db_obj)

        db.commit()
        for obj in db_objs:
            db.refresh(obj)
        return db_objs

    def count_by_document(self, db: Session, *, document_id: int) -> int:
        """Return total atom count for a document (used by coverage score)."""
        return db.query(self.model).filter(
            self.model.document_id == document_id
        ).count()


requirement_atom = CRUDRequirementAtom(RequirementAtom)
