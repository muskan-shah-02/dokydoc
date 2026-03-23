"""
SPRINT 3: Coordinator Service — Celery Task Lifecycle Manager

Provides a clean interface for enqueueing, tracking, and managing
background analysis tasks. Decouples API endpoints from Celery internals.

Usage:
    coordinator = CoordinatorService()
    result = coordinator.enqueue_repo_analysis(db, repo_id, tenant_id, file_list)
    status = coordinator.get_repo_status(db, repo_id, tenant_id)
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app import crud
from app.core.logging import LoggerMixin


class CoordinatorService(LoggerMixin):

    def __init__(self):
        super().__init__()

    # ============================================================
    # REPOSITORY ANALYSIS
    # ============================================================

    def enqueue_repo_analysis(
        self, db: Session, repo_id: int, tenant_id: int, file_list: List[dict]
    ) -> Dict[str, Any]:
        """
        Enqueue a repository analysis task via Celery.

        Args:
            db: Database session
            repo_id: Repository ID
            tenant_id: Tenant ID
            file_list: List of {"path": str, "url": str, "language": str}

        Returns:
            Dict with task_id, status, and file count
        """
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            return {"status": "error", "reason": "Repository not found"}

        if repo.analysis_status == "analyzing":
            return {"status": "already_running", "repo_id": repo_id}

        from app.tasks.code_analysis_tasks import repo_analysis_task
        task = repo_analysis_task.delay(repo_id, tenant_id, file_list)

        self.logger.info(
            f"Coordinator: Repo {repo_id} analysis enqueued "
            f"({len(file_list)} files), celery_task_id={task.id}"
        )

        return {
            "status": "enqueued",
            "repo_id": repo_id,
            "task_id": task.id,
            "total_files": len(file_list),
        }

    def get_repo_status(
        self, db: Session, repo_id: int, tenant_id: int
    ) -> Dict[str, Any]:
        """
        Get the current analysis status for a repository.

        Returns:
            Dict with status, progress, file counts, and error info
        """
        repo = crud.repository.get(db=db, id=repo_id, tenant_id=tenant_id)
        if not repo:
            return {"status": "not_found"}

        progress_pct = 0.0
        if repo.total_files > 0:
            progress_pct = round((repo.analyzed_files / repo.total_files) * 100, 1)

        return {
            "repo_id": repo_id,
            "name": repo.name,
            "analysis_status": repo.analysis_status,
            "progress_percent": progress_pct,
            "total_files": repo.total_files,
            "analyzed_files": repo.analyzed_files,
            "error_message": repo.error_message,
            "last_analyzed_commit": repo.last_analyzed_commit,
        }

    # ============================================================
    # ONTOLOGY EXTRACTION (fire-and-forget after document analysis)
    # ============================================================

    def enqueue_ontology_extraction(
        self, document_id: int, tenant_id: int
    ) -> Dict[str, Any]:
        """
        Enqueue ontology entity extraction for a completed document.
        This is called by the document pipeline after marking status='completed'.
        """
        from app.tasks.ontology_tasks import extract_ontology_entities
        task = extract_ontology_entities.delay(document_id, tenant_id)

        self.logger.info(
            f"Coordinator: Ontology extraction enqueued for doc {document_id}, "
            f"celery_task_id={task.id}"
        )

        return {
            "status": "enqueued",
            "document_id": document_id,
            "task_id": task.id,
        }

    # ============================================================
    # DOCUMENT ANALYSIS STATUS
    # ============================================================

    def get_document_status(
        self, db: Session, document_id: int, tenant_id: int
    ) -> Dict[str, Any]:
        """
        Get combined document analysis + ontology enrichment status.
        """
        doc = crud.document.get(db=db, id=document_id, tenant_id=tenant_id)
        if not doc:
            return {"status": "not_found"}

        # Count ontology concepts for the tenant
        concept_count = crud.ontology_concept.count_by_tenant(
            db=db, tenant_id=tenant_id
        )

        return {
            "document_id": document_id,
            "analysis_status": doc.status,
            "progress": doc.progress,
            "error_message": doc.error_message,
            "ontology_enrichment": {
                "complete": concept_count > 0,
                "concept_count": concept_count,
            },
        }

    # ============================================================
    # BATCH OPERATIONS
    # ============================================================

    def get_tenant_analysis_summary(
        self, db: Session, tenant_id: int
    ) -> Dict[str, Any]:
        """
        Get a high-level summary of all analyses for a tenant.
        Useful for dashboard stats.
        """
        repo_count = crud.repository.count_by_tenant(db=db, tenant_id=tenant_id)
        concept_count = crud.ontology_concept.count_by_tenant(db=db, tenant_id=tenant_id)
        relationship_count = crud.ontology_relationship.count_by_tenant(db=db, tenant_id=tenant_id)

        return {
            "repositories": repo_count,
            "ontology_concepts": concept_count,
            "ontology_relationships": relationship_count,
        }


# Singleton
coordinator_service = CoordinatorService()
