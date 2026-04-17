"""
P5C-08: ComplianceSnapshotService — captures daily compliance score per document.
Uses UPSERT so re-running on same day updates rather than duplicates.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func, distinct
from app.core.logging import get_logger
from app.models.compliance_score_snapshot import ComplianceScoreSnapshot
from app.models.requirement_atom import RequirementAtom
from app.models.mismatch import Mismatch

logger = get_logger("compliance_snapshot_service")


class ComplianceSnapshotService:

    def capture_for_document(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        snapshot_date: Optional[date] = None,
    ) -> ComplianceScoreSnapshot:
        """
        Take a compliance snapshot for one document.
        UPSERT: re-running on same day updates the row rather than inserting a duplicate.
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        total_atoms = db.query(RequirementAtom).filter(
            RequirementAtom.document_id == document_id,
            RequirementAtom.tenant_id == tenant_id,
        ).count()

        uncovered_atom_ids = db.query(distinct(Mismatch.requirement_atom_id)).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status.in_(["open", "in_progress"]),
            Mismatch.requirement_atom_id.isnot(None),
        ).all()
        uncovered_count = len(uncovered_atom_ids)
        covered = max(0, total_atoms - uncovered_count)
        score = round((covered / total_atoms * 100) if total_atoms > 0 else 100.0, 1)

        open_mismatches = db.query(Mismatch).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status == "open",
        ).count()

        critical_mismatches = db.query(Mismatch).filter(
            Mismatch.document_id == document_id,
            Mismatch.tenant_id == tenant_id,
            Mismatch.status == "open",
            Mismatch.severity.in_(["critical", "high"]),
        ).count()

        stmt = pg_insert(ComplianceScoreSnapshot).values(
            tenant_id=tenant_id,
            document_id=document_id,
            score_percentage=score,
            total_atoms=total_atoms,
            covered_atoms=covered,
            open_mismatches=open_mismatches,
            critical_mismatches=critical_mismatches,
            snapshot_date=snapshot_date,
            created_at=datetime.utcnow(),
        ).on_conflict_do_update(
            index_elements=["document_id", "snapshot_date"],
            set_={
                "score_percentage": score,
                "total_atoms": total_atoms,
                "covered_atoms": covered,
                "open_mismatches": open_mismatches,
                "critical_mismatches": critical_mismatches,
                "created_at": datetime.utcnow(),
            }
        )
        db.execute(stmt)
        db.commit()

        obj = db.query(ComplianceScoreSnapshot).filter_by(
            document_id=document_id, snapshot_date=snapshot_date
        ).first()
        return obj

    def capture_all_active_documents(self, db: Session) -> int:
        """
        Snapshot all documents that have atoms. Called by nightly Celery beat task.
        Returns count of documents snapshotted.
        """
        active_doc_ids = db.query(
            RequirementAtom.document_id, RequirementAtom.tenant_id
        ).group_by(
            RequirementAtom.document_id, RequirementAtom.tenant_id
        ).all()

        count = 0
        for doc_id, tenant_id in active_doc_ids:
            try:
                self.capture_for_document(db=db, document_id=doc_id, tenant_id=tenant_id)
                count += 1
            except Exception as e:
                logger.warning(f"Snapshot failed for document {doc_id}: {e}")

        logger.info(f"[P5C-08] Snapshotted {count} documents")
        return count


compliance_snapshot_service = ComplianceSnapshotService()
