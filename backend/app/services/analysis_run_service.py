from datetime import datetime, timedelta
from typing import Optional, List
import asyncio

from sqlalchemy.orm import Session

from app.core.logging import LoggerMixin
from app import crud, models, schemas
from app.models import AnalysisRun, AnalysisRunStatus, DocumentSegment, SegmentStatus, AnalysisResult, AnalysisResultStatus


class AnalysisRunService(LoggerMixin):
    """
    Service for managing analysis run lifecycle and tracking.
    Replaces the simple in-memory locking with proper database-backed run tracking.
    """
    
    def __init__(self):
        super().__init__()
    
    def create_analysis_run(
        self, 
        db: Session, 
        document_id: int, 
        user_id: int, 
        learning_mode: bool = False
    ) -> AnalysisRun:
        """
        Create a new analysis run and mark it as pending.
        Returns None if a run is already active for this document.
        """
        # Check for existing active runs
        existing_run = self.get_active_run(db, document_id)
        if existing_run:
            self.logger.warning(f"Analysis run already active for document {document_id}: run_id={existing_run.id}")
            raise ValueError(f"Analysis already running for document {document_id}")
        
        # Create new analysis run
        run = AnalysisRun(
            document_id=document_id,
            triggered_by_user_id=user_id,
            status=AnalysisRunStatus.PENDING,
            learning_mode=learning_mode,
            run_metadata={"created_via": "api"}
        )
        
        db.add(run)
        db.commit()
        db.refresh(run)
        
        self.logger.info(f"Created analysis run {run.id} for document {document_id}")
        return run
    
    def get_active_run(self, db: Session, document_id: int) -> Optional[AnalysisRun]:
        """Get any active (pending/running) analysis run for a document."""
        return db.query(AnalysisRun).filter(
            AnalysisRun.document_id == document_id,
            AnalysisRun.status.in_([AnalysisRunStatus.PENDING, AnalysisRunStatus.RUNNING])
        ).first()
    
    def start_run(self, db: Session, run_id: int) -> AnalysisRun:
        """Mark an analysis run as started."""
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise ValueError(f"Analysis run {run_id} not found")
        
        run.status = AnalysisRunStatus.RUNNING
        run.started_at = datetime.now()
        db.commit()
        db.refresh(run)
        
        self.logger.info(f"Started analysis run {run_id}")
        return run
    
    def complete_run(self, db: Session, run_id: int, success: bool = True) -> AnalysisRun:
        """Mark an analysis run as completed or failed."""
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise ValueError(f"Analysis run {run_id} not found")
        
        run.status = AnalysisRunStatus.COMPLETED if success else AnalysisRunStatus.FAILED
        run.completed_at = datetime.now()
        
        # Update segment and result counts
        segments = db.query(DocumentSegment).filter(
            DocumentSegment.analysis_run_id == run_id
        ).all()
        
        run.total_segments = len(segments)
        run.completed_segments = sum(1 for s in segments if s.status == SegmentStatus.COMPLETED)
        run.failed_segments = sum(1 for s in segments if s.status == SegmentStatus.FAILED)
        
        db.commit()
        db.refresh(run)
        
        self.logger.info(f"Completed analysis run {run_id}: {run.completed_segments} succeeded, {run.failed_segments} failed")
        return run
    
    def fail_run(self, db: Session, run_id: int, error_message: str, error_details: dict = None) -> AnalysisRun:
        """Mark an analysis run as failed with error details."""
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise ValueError(f"Analysis run {run_id} not found")
        
        run.status = AnalysisRunStatus.FAILED
        run.completed_at = datetime.now()
        run.error_message = error_message
        run.error_details = error_details or {}
        
        db.commit()
        db.refresh(run)
        
        self.logger.error(f"Failed analysis run {run_id}: {error_message}")
        return run
    
    def update_run_progress(self, db: Session, run_id: int) -> AnalysisRun:
        """Update run progress based on current segment statuses."""
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise ValueError(f"Analysis run {run_id} not found")
        
        segments = db.query(DocumentSegment).filter(
            DocumentSegment.analysis_run_id == run_id
        ).all()
        
        run.total_segments = len(segments)
        run.completed_segments = sum(1 for s in segments if s.status == SegmentStatus.COMPLETED)
        run.failed_segments = sum(1 for s in segments if s.status == SegmentStatus.FAILED)
        
        db.commit()
        db.refresh(run)
        
        return run
    
    def get_run_status(self, db: Session, run_id: int) -> dict:
        """Get comprehensive status of an analysis run."""
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            raise ValueError(f"Analysis run {run_id} not found")
        
        segments = db.query(DocumentSegment).filter(
            DocumentSegment.analysis_run_id == run_id
        ).all()
        
        segment_statuses = {}
        for status in SegmentStatus:
            segment_statuses[status.value] = sum(1 for s in segments if s.status == status)
        
        return {
            "run_id": run.id,
            "document_id": run.document_id,
            "status": run.status.value,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "progress_percentage": run.progress_percentage,
            "total_segments": run.total_segments or 0,
            "completed_segments": run.completed_segments,
            "failed_segments": run.failed_segments,
            "segment_statuses": segment_statuses,
            "error_message": run.error_message,
            "learning_mode": run.learning_mode
        }
    
    def get_recent_runs(self, db: Session, document_id: int, limit: int = 10) -> List[dict]:
        """Get recent analysis runs for a document."""
        runs = db.query(AnalysisRun).filter(
            AnalysisRun.document_id == document_id
        ).order_by(AnalysisRun.created_at.desc()).limit(limit).all()
        
        return [self.get_run_status(db, run.id) for run in runs]
    
    def get_runs_for_document(self, db: Session, document_id: int) -> List[AnalysisRun]:
        """Get all analysis runs for a document."""
        return db.query(AnalysisRun).filter(
            AnalysisRun.document_id == document_id
        ).order_by(AnalysisRun.created_at.desc()).all()
    
    def retry_failed_segments(self, db: Session, run_id: int, max_retries: int = 3) -> List[int]:
        """
        Reset failed segments to pending for retry.
        Returns list of segment IDs that were reset.
        """
        failed_segments = db.query(DocumentSegment).filter(
            DocumentSegment.analysis_run_id == run_id,
            DocumentSegment.status == SegmentStatus.FAILED,
            DocumentSegment.retry_count < max_retries
        ).all()
        
        reset_segment_ids = []
        for segment in failed_segments:
            segment.status = SegmentStatus.PENDING
            segment.retry_count += 1
            segment.last_error = None
            reset_segment_ids.append(segment.id)
        
        if reset_segment_ids:
            db.commit()
            self.logger.info(f"Reset {len(reset_segment_ids)} failed segments for retry in run {run_id}")
        
        return reset_segment_ids
    
    def cleanup_old_runs(self, db: Session, days_to_keep: int = 30) -> int:
        """Clean up analysis runs older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        old_runs = db.query(AnalysisRun).filter(
            AnalysisRun.created_at < cutoff_date,
            AnalysisRun.status.in_([AnalysisRunStatus.COMPLETED, AnalysisRunStatus.FAILED, AnalysisRunStatus.CANCELLED])
        ).all()
        
        count = len(old_runs)
        for run in old_runs:
            db.delete(run)
        
        db.commit()
        self.logger.info(f"Cleaned up {count} old analysis runs")
        return count


# Global instance
analysis_run_service = AnalysisRunService()
