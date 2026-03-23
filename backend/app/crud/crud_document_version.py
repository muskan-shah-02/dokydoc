"""
CRUD operations for DocumentVersion model.
Sprint 8: Version Comparison Feature.
"""
import hashlib
import difflib
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.document_version import DocumentVersion


class CRUDDocumentVersion:

    def create(
        self,
        db: Session,
        *,
        document_id: int,
        tenant_id: int,
        content_text: str,
        original_filename: str,
        file_size: Optional[int],
        uploaded_by_id: int,
    ) -> DocumentVersion:
        """Create a new version snapshot. Auto-increments version_number."""
        # Get next version number for this document
        last = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.version_number))
            .first()
        )
        next_version = (last.version_number + 1) if last else 1
        content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        obj = DocumentVersion(
            document_id=document_id,
            tenant_id=tenant_id,
            version_number=next_version,
            content_text=content_text,
            content_hash=content_hash,
            file_size=file_size,
            original_filename=original_filename,
            uploaded_by_id=uploaded_by_id,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get_by_document(
        self, db: Session, *, document_id: int, tenant_id: int
    ) -> List[DocumentVersion]:
        """List all versions for a document, newest first."""
        return (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == document_id,
                DocumentVersion.tenant_id == tenant_id,
            )
            .order_by(desc(DocumentVersion.version_number))
            .all()
        )

    def get_by_version_number(
        self, db: Session, *, document_id: int, tenant_id: int, version_number: int
    ) -> Optional[DocumentVersion]:
        return (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == document_id,
                DocumentVersion.tenant_id == tenant_id,
                DocumentVersion.version_number == version_number,
            )
            .first()
        )

    def get_by_id(
        self, db: Session, *, version_id: int, tenant_id: int
    ) -> Optional[DocumentVersion]:
        return (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.id == version_id,
                DocumentVersion.tenant_id == tenant_id,
            )
            .first()
        )

    def compute_diff(
        self,
        text_a: str,
        text_b: str,
        version_a: int,
        version_b: int,
        document_id: int,
    ) -> dict:
        """
        Compute a line-level diff between two text versions.
        Returns structured data suitable for react-diff-viewer rendering.
        """
        lines_a = text_a.splitlines(keepends=True)
        lines_b = text_b.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
        result_a = []
        result_b = []
        added_count = 0
        removed_count = 0
        unchanged_count = 0

        line_num_a = 1
        line_num_b = 1

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for line in lines_a[i1:i2]:
                    result_a.append({"line_number": line_num_a, "content": line.rstrip("\n"), "change_type": "unchanged"})
                    result_b.append({"line_number": line_num_b, "content": line.rstrip("\n"), "change_type": "unchanged"})
                    line_num_a += 1
                    line_num_b += 1
                    unchanged_count += 1

            elif tag == "replace":
                for line in lines_a[i1:i2]:
                    result_a.append({"line_number": line_num_a, "content": line.rstrip("\n"), "change_type": "removed"})
                    line_num_a += 1
                    removed_count += 1
                for line in lines_b[j1:j2]:
                    result_b.append({"line_number": line_num_b, "content": line.rstrip("\n"), "change_type": "added"})
                    line_num_b += 1
                    added_count += 1

            elif tag == "delete":
                for line in lines_a[i1:i2]:
                    result_a.append({"line_number": line_num_a, "content": line.rstrip("\n"), "change_type": "removed"})
                    line_num_a += 1
                    removed_count += 1

            elif tag == "insert":
                for line in lines_b[j1:j2]:
                    result_b.append({"line_number": line_num_b, "content": line.rstrip("\n"), "change_type": "added"})
                    line_num_b += 1
                    added_count += 1

        total = added_count + removed_count + unchanged_count
        change_pct = round((added_count + removed_count) / max(total, 1) * 100, 1)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "document_id": document_id,
            "lines_a": result_a,
            "lines_b": result_b,
            "stats": {
                "added_count": added_count,
                "removed_count": removed_count,
                "unchanged_count": unchanged_count,
                "change_pct": change_pct,
            },
        }

    def prune_old_versions(
        self, db: Session, *, document_id: int, keep_last_n: int = 20
    ) -> int:
        """Delete versions older than the last N. Returns number deleted."""
        all_versions = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.version_number))
            .all()
        )
        to_delete = all_versions[keep_last_n:]
        for v in to_delete:
            db.delete(v)
        if to_delete:
            db.commit()
        return len(to_delete)


crud_document_version = CRUDDocumentVersion()
