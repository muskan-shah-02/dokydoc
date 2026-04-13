from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.mismatch import Mismatch
from app.models.document_code_link import DocumentCodeLink
from app.schemas.mismatch import MismatchCreate, MismatchUpdate

class CRUDMismatch(CRUDBase[Mismatch, MismatchCreate, MismatchUpdate]):
    """
    CRUD functions for the Mismatch model.
    """

    def create_with_owner(
        self, db: Session, *, obj_in: MismatchCreate, owner_id: int, tenant_id: int
    ) -> Mismatch:
        """
        Create a new mismatch and associate it with an owner.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for mismatch creation")

        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[Mismatch]:
        """
        Retrieve multiple mismatches for a specific owner with eager loading.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_multi_by_owner()")

        return (
            db.query(self.model)
            .filter(
                Mismatch.owner_id == owner_id,
                Mismatch.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
            )
            .options(
                joinedload(self.model.document),
                joinedload(self.model.code_component)
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # --- NEW: Helper method for the ValidationService ---
    def remove_by_link(self, db: Session, *, document_id: int, code_component_id: int, tenant_id: int) -> int:
        """
        Deletes all mismatches associated with a specific document-code link.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.

        Returns the number of mismatches deleted.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for remove_by_link()")

        num_deleted = db.query(self.model).filter(
            self.model.document_id == document_id,
            self.model.code_component_id == code_component_id,
            self.model.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).delete()
        db.commit()
        return num_deleted

    def create_with_link(
        self,
        db: Session,
        *,
        obj_in: dict,
        link_id: int,
        owner_id: int,
        tenant_id: int
    ) -> Mismatch:
        """
        Create mismatch from document-code link.

        SPRINT 2: tenant_id is now REQUIRED for multi-tenancy isolation.
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for create_with_link()")

        link = db.query(DocumentCodeLink).filter(
            DocumentCodeLink.id == link_id,
            DocumentCodeLink.tenant_id == tenant_id  # SPRINT 2: Tenant isolation
        ).first()
        if not link:
            raise ValueError(f"DocumentCodeLink {link_id} not found in tenant {tenant_id}")

        mismatch_schema = MismatchCreate(
            **obj_in,
            document_id=link.document_id,
            code_component_id=link.code_component_id
        )

        db_obj = self.model(**mismatch_schema.model_dump(), owner_id=owner_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def close_for_deleted_atoms(
        self,
        db: Session,
        *,
        deleted_atom_ids: List[int],
        tenant_id: int,
        auto_close_reason: str = "requirement_deleted_from_brd",
    ) -> int:
        """
        P5B-01: Auto-close mismatches whose requirement atom was deleted from BRD.
        Sets status='auto_closed' instead of deleting — preserves audit history.
        Returns count of mismatches closed.
        """
        if not deleted_atom_ids:
            return 0

        num_closed = db.query(self.model).filter(
            self.model.requirement_atom_id.in_(deleted_atom_ids),
            self.model.tenant_id == tenant_id,
            self.model.status.in_(["open", "in_progress", "new"]),
        ).update(
            {
                "status": "auto_closed",
                "resolution_note": auto_close_reason,
                "updated_at": datetime.now(),
            },
            synchronize_session="fetch",
        )
        db.commit()
        return num_closed

    def count_by_document_component(
        self, db: Session, document_id: int, component_id: int, tenant_id: int
    ) -> int:
        """Return count of existing mismatches for a document-component pair."""
        return db.query(self.model).filter(
            self.model.document_id == document_id,
            self.model.code_component_id == component_id,
            self.model.tenant_id == tenant_id,
        ).count()

    def mark_false_positive(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
        reason: str,
        changed_by_user_id: int,
    ) -> Optional[Mismatch]:
        """
        P5B-04: Mark mismatch as false positive with mandatory reason (≥10 chars).
        Optionally creates a TrainingExample with human_label='rejected'.
        """
        if len(reason.strip()) < 10:
            raise ValueError("False positive reason must be at least 10 characters")

        m = db.query(self.model).filter(
            self.model.id == mismatch_id,
            self.model.tenant_id == tenant_id,
        ).first()
        if not m:
            return None

        m.status = "false_positive"
        m.resolution_note = reason.strip()
        m.status_changed_by_id = changed_by_user_id
        m.status_changed_at = datetime.now()
        m.updated_at = datetime.now()
        db.commit()
        db.refresh(m)

        # Best-effort: log training signal
        try:
            from app.models.training_example import TrainingExample
            te = TrainingExample(
                tenant_id=tenant_id,
                mismatch_id=mismatch_id,
                human_label="rejected",
                label_reason=reason.strip(),
                created_at=datetime.now(),
            )
            db.add(te)
            db.commit()
        except Exception:
            pass  # Non-fatal

        return m

    def dispute_false_positive(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
        dispute_reason: str,
        changed_by_user_id: int,
    ) -> Optional[Mismatch]:
        """
        P5B-04: Dispute a false_positive decision — sets status='disputed'.
        Appends dispute reason to existing resolution_note.
        """
        m = db.query(self.model).filter(
            self.model.id == mismatch_id,
            self.model.tenant_id == tenant_id,
            self.model.status == "false_positive",
        ).first()
        if not m:
            return None

        existing_note = m.resolution_note or ""
        m.resolution_note = f"{existing_note}\n[DISPUTED] {dispute_reason.strip()}"
        m.status = "disputed"
        m.status_changed_by_id = changed_by_user_id
        m.status_changed_at = datetime.now()
        m.updated_at = datetime.now()
        db.commit()
        db.refresh(m)
        return m

    def update_status(
        self,
        db: Session,
        *,
        mismatch_id: int,
        tenant_id: int,
        new_status: str,
        changed_by_user_id: int,
        note: Optional[str] = None,
    ) -> Optional[Mismatch]:
        """
        P5B-10: Update mismatch status with transition validation.
        Valid statuses: open, in_progress, resolved, verified, false_positive,
                        auto_closed, disputed
        """
        VALID_STATUSES = {
            "open", "in_progress", "resolved", "verified",
            "false_positive", "auto_closed", "disputed", "new",
        }
        VALID_TRANSITIONS = {
            "new":           {"open", "in_progress", "false_positive"},
            "open":          {"in_progress", "resolved", "false_positive", "auto_closed"},
            "in_progress":   {"open", "resolved", "false_positive"},
            "resolved":      {"verified", "open"},
            "verified":      {"open"},
            "false_positive": {"disputed", "open"},
            "disputed":      {"open", "false_positive"},
            "auto_closed":   {"open"},
        }

        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'")

        m = db.query(self.model).filter(
            self.model.id == mismatch_id,
            self.model.tenant_id == tenant_id,
        ).first()
        if not m:
            return None

        allowed = VALID_TRANSITIONS.get(m.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{m.status}' to '{new_status}'. "
                f"Allowed: {sorted(allowed)}"
            )

        old_status = m.status
        m.status = new_status
        m.status_changed_by_id = changed_by_user_id
        m.status_changed_at = datetime.now()
        m.updated_at = datetime.now()
        if note:
            m.resolution_note = note
        db.commit()
        db.refresh(m)
        return m

    def get_compliance_breakdown(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        code_component_id: Optional[int] = None,
    ) -> dict:
        """
        P5B-02: Returns atom coverage breakdown by atom_type.
        Joins mismatches → requirement_atoms to compute per-type coverage.
        """
        from collections import defaultdict
        from app.models.requirement_atom import RequirementAtom

        ATOM_WEIGHTS = {
            "SECURITY_REQUIREMENT": 3,
            "BUSINESS_RULE": 2,
            "API_CONTRACT": 2,
            "DATA_CONSTRAINT": 1,
            "FUNCTIONAL_REQUIREMENT": 1,
            "WORKFLOW_STEP": 1,
            "ERROR_SCENARIO": 1,
            "NFR": 1,
            "INTEGRATION_POINT": 1,
        }

        all_atoms = db.query(RequirementAtom).filter(
            RequirementAtom.document_id == document_id,
            RequirementAtom.tenant_id == tenant_id,
        ).all()

        if not all_atoms:
            return {"overall_score": None, "message": "No atoms found — run validation first"}

        # Open mismatches (exclude false positives)
        mismatch_filter = [
            self.model.document_id == document_id,
            self.model.tenant_id == tenant_id,
            self.model.status.in_(["open", "in_progress", "new"]),
        ]
        if code_component_id:
            mismatch_filter.append(self.model.code_component_id == code_component_id)
        open_mismatches = db.query(self.model).filter(*mismatch_filter).all()

        atoms_with_mismatch: set = set()
        open_critical_count = 0
        for m in open_mismatches:
            if m.requirement_atom_id:
                atoms_with_mismatch.add(m.requirement_atom_id)
            if m.severity in ("critical", "compliance_risk"):
                open_critical_count += 1

        fp_count = db.query(self.model).filter(
            self.model.document_id == document_id,
            self.model.tenant_id == tenant_id,
            self.model.status == "false_positive",
        ).count()

        # Group atoms by type
        groups: dict = defaultdict(list)
        for a in all_atoms:
            groups[a.atom_type].append(a)

        by_type: dict = {}
        total_atoms = 0
        covered_atoms = 0
        weighted_total = 0
        weighted_covered = 0

        for atom_type, atoms_of_type in sorted(groups.items()):
            type_total = len(atoms_of_type)
            type_covered = sum(1 for a in atoms_of_type if a.id not in atoms_with_mismatch)
            weight = ATOM_WEIGHTS.get(atom_type, 1)

            by_type[atom_type] = {
                "total": type_total,
                "covered": type_covered,
                "score": round(type_covered / type_total, 4) if type_total else 1.0,
                "weight": weight,
            }
            total_atoms += type_total
            covered_atoms += type_covered
            weighted_total += type_total * weight
            weighted_covered += type_covered * weight

        overall_score = round(covered_atoms / total_atoms, 4) if total_atoms else 1.0
        weighted_score = round(weighted_covered / weighted_total, 4) if weighted_total else 1.0

        return {
            "overall_score": overall_score,
            "weighted_score": weighted_score,
            "by_type": by_type,
            "total_atoms": total_atoms,
            "covered_atoms": covered_atoms,
            "open_critical_count": open_critical_count,
            "false_positive_excluded": fp_count,
        }


# A single, reusable instance of our CRUD class.
mismatch = CRUDMismatch(Mismatch)
