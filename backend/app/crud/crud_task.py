"""
CRUD operations for Task and TaskComment models.
Sprint 2 Extended - Phase 10: Tasks Feature

Provides all database operations for task management including:
- Create, read, update, delete tasks
- Assign/reassign tasks
- Add comments
- Filter and search tasks
- Task statistics
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.task import Task, TaskComment, TaskStatus, TaskPriority
from app.schemas.task import TaskCreate, TaskUpdate, TaskCommentCreate


class CRUDTask(CRUDBase[Task, TaskCreate, TaskUpdate]):
    """
    CRUD operations for Task model.

    All operations are tenant-scoped for multi-tenancy isolation.
    """

    def create_task(
        self,
        db: Session,
        *,
        obj_in: TaskCreate,
        tenant_id: int,
        created_by_id: int
    ) -> Task:
        """
        Create a new task.

        Args:
            db: Database session
            obj_in: Task creation data
            tenant_id: Tenant ID (for isolation)
            created_by_id: User ID of task creator

        Returns:
            Created task
        """
        # Convert Pydantic model to dict
        obj_data = obj_in.model_dump()

        # Add system fields
        obj_data["tenant_id"] = tenant_id
        obj_data["created_by_id"] = created_by_id

        # Create task
        db_obj = Task(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        return db_obj

    def get_task(
        self,
        db: Session,
        *,
        task_id: int,
        tenant_id: int
    ) -> Optional[Task]:
        """
        Get a single task by ID (tenant-scoped).

        Args:
            db: Database session
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)

        Returns:
            Task if found and belongs to tenant, None otherwise
        """
        return (
            db.query(Task)
            .options(
                joinedload(Task.created_by),
                joinedload(Task.assigned_to),
                joinedload(Task.document),
                joinedload(Task.code_component)
            )
            .filter(
                Task.id == task_id,
                Task.tenant_id == tenant_id
            )
            .first()
        )

    def get_tasks(
        self,
        db: Session,
        *,
        tenant_id: int,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        assigned_to_id: Optional[int] = None,
        created_by_id: Optional[int] = None,
        document_id: Optional[int] = None,
        code_component_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """
        Get multiple tasks with optional filters (tenant-scoped).

        Args:
            db: Database session
            tenant_id: Tenant ID (for isolation)
            status: Filter by status
            priority: Filter by priority
            assigned_to_id: Filter by assignee
            created_by_id: Filter by creator
            document_id: Filter by linked document
            code_component_id: Filter by linked code component
            tags: Filter by tags (any match)
            skip: Pagination offset
            limit: Page size

        Returns:
            List of tasks matching filters
        """
        query = db.query(Task).filter(Task.tenant_id == tenant_id)

        # Apply filters
        if status:
            query = query.filter(Task.status == status)

        if priority:
            query = query.filter(Task.priority == priority)

        if assigned_to_id is not None:
            query = query.filter(Task.assigned_to_id == assigned_to_id)

        if created_by_id:
            query = query.filter(Task.created_by_id == created_by_id)

        if document_id:
            query = query.filter(Task.document_id == document_id)

        if code_component_id:
            query = query.filter(Task.code_component_id == code_component_id)

        if tags:
            # Filter tasks that have ANY of the specified tags
            # PostgreSQL JSONB contains operator
            for tag in tags:
                query = query.filter(Task.tags.contains([tag]))

        # Order by: priority (high to low), then due date, then created date
        query = query.order_by(
            Task.priority.desc(),
            Task.due_date.asc().nullslast(),
            Task.created_at.desc()
        )

        return query.offset(skip).limit(limit).all()

    def get_my_tasks(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """
        Get tasks assigned to a specific user.

        Args:
            db: Database session
            tenant_id: Tenant ID (for isolation)
            user_id: User ID to get tasks for
            skip: Pagination offset
            limit: Page size

        Returns:
            List of tasks assigned to user
        """
        return (
            db.query(Task)
            .filter(
                Task.tenant_id == tenant_id,
                Task.assigned_to_id == user_id,
                Task.status != TaskStatus.DONE,
                Task.status != TaskStatus.CANCELLED
            )
            .order_by(
                Task.priority.desc(),
                Task.due_date.asc().nullslast(),
                Task.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_task(
        self,
        db: Session,
        *,
        task_id: int,
        tenant_id: int,
        obj_in: TaskUpdate
    ) -> Optional[Task]:
        """
        Update a task.

        Args:
            db: Database session
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)
            obj_in: Update data

        Returns:
            Updated task or None if not found
        """
        task = self.get_task(db, task_id=task_id, tenant_id=tenant_id)
        if not task:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)

        # If status is changed to DONE, set completed_at
        if "status" in update_data and update_data["status"] == TaskStatus.DONE:
            if task.status != TaskStatus.DONE:  # Only set if changing to DONE
                update_data["completed_at"] = datetime.utcnow()

        # If status is changed from DONE to something else, clear completed_at
        if "status" in update_data and update_data["status"] != TaskStatus.DONE:
            if task.status == TaskStatus.DONE:  # Only clear if was DONE
                update_data["completed_at"] = None

        for field, value in update_data.items():
            setattr(task, field, value)

        db.add(task)
        db.commit()
        db.refresh(task)

        return task

    def assign_task(
        self,
        db: Session,
        *,
        task_id: int,
        tenant_id: int,
        assigned_to_id: Optional[int]
    ) -> Optional[Task]:
        """
        Assign or reassign a task to a user.

        Args:
            db: Database session
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)
            assigned_to_id: User ID to assign to (None to unassign)

        Returns:
            Updated task or None if not found
        """
        task = self.get_task(db, task_id=task_id, tenant_id=tenant_id)
        if not task:
            return None

        task.assigned_to_id = assigned_to_id
        db.add(task)
        db.commit()
        db.refresh(task)

        return task

    def delete_task(
        self,
        db: Session,
        *,
        task_id: int,
        tenant_id: int
    ) -> bool:
        """
        Delete a task (and all its comments via cascade).

        Args:
            db: Database session
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)

        Returns:
            True if deleted, False if not found
        """
        task = self.get_task(db, task_id=task_id, tenant_id=tenant_id)
        if not task:
            return False

        db.delete(task)
        db.commit()

        return True

    def get_task_statistics(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: Optional[int] = None
    ) -> Dict:
        """
        Get task statistics for a tenant or specific user.

        Args:
            db: Database session
            tenant_id: Tenant ID (for isolation)
            user_id: Optional user ID to filter statistics

        Returns:
            Dictionary with task counts by status and priority
        """
        query = db.query(Task).filter(Task.tenant_id == tenant_id)

        if user_id:
            query = query.filter(Task.assigned_to_id == user_id)

        # Count by status
        status_counts = {}
        for status in TaskStatus:
            count = query.filter(Task.status == status).count()
            status_counts[status.value] = count

        # Count by priority
        priority_counts = {}
        for priority in TaskPriority:
            count = query.filter(Task.priority == priority).count()
            priority_counts[priority.value] = count

        # Total tasks
        total = query.count()

        # Overdue tasks (due_date < now and status != DONE/CANCELLED)
        overdue = query.filter(
            Task.due_date < datetime.utcnow(),
            Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
        ).count()

        return {
            "total": total,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "overdue": overdue,
        }

    def search_tasks(
        self,
        db: Session,
        *,
        tenant_id: int,
        search_query: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """
        Search tasks by title or description.

        Args:
            db: Database session
            tenant_id: Tenant ID (for isolation)
            search_query: Search string
            skip: Pagination offset
            limit: Page size

        Returns:
            List of matching tasks
        """
        search_pattern = f"%{search_query}%"

        return (
            db.query(Task)
            .filter(
                Task.tenant_id == tenant_id,
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern)
                )
            )
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class CRUDTaskComment(CRUDBase[TaskComment, TaskCommentCreate, TaskCommentCreate]):
    """
    CRUD operations for TaskComment model.

    All operations are tenant-scoped for multi-tenancy isolation.
    """

    def create_comment(
        self,
        db: Session,
        *,
        obj_in: TaskCommentCreate,
        task_id: int,
        tenant_id: int,
        user_id: int
    ) -> TaskComment:
        """
        Add a comment to a task.

        Args:
            db: Database session
            obj_in: Comment creation data
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)
            user_id: User ID of commenter

        Returns:
            Created comment
        """
        comment = TaskComment(
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            content=obj_in.content
        )

        db.add(comment)
        db.commit()
        db.refresh(comment)

        return comment

    def get_comments(
        self,
        db: Session,
        *,
        task_id: int,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaskComment]:
        """
        Get all comments for a task.

        Args:
            db: Database session
            task_id: Task ID
            tenant_id: Tenant ID (for isolation)
            skip: Pagination offset
            limit: Page size

        Returns:
            List of comments ordered by created_at
        """
        return (
            db.query(TaskComment)
            .options(joinedload(TaskComment.user))
            .filter(
                TaskComment.task_id == task_id,
                TaskComment.tenant_id == tenant_id
            )
            .order_by(TaskComment.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_comment(
        self,
        db: Session,
        *,
        comment_id: int,
        tenant_id: int,
        user_id: int,
        content: str
    ) -> Optional[TaskComment]:
        """
        Update a comment (only by the original commenter).

        Args:
            db: Database session
            comment_id: Comment ID
            tenant_id: Tenant ID (for isolation)
            user_id: User ID (must match original commenter)
            content: New content

        Returns:
            Updated comment or None if not found/not authorized
        """
        comment = (
            db.query(TaskComment)
            .filter(
                TaskComment.id == comment_id,
                TaskComment.tenant_id == tenant_id,
                TaskComment.user_id == user_id  # Only original commenter can edit
            )
            .first()
        )

        if not comment:
            return None

        comment.content = content
        comment.is_edited = 1  # Mark as edited
        db.add(comment)
        db.commit()
        db.refresh(comment)

        return comment

    def delete_comment(
        self,
        db: Session,
        *,
        comment_id: int,
        tenant_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a comment (only by the original commenter).

        Args:
            db: Database session
            comment_id: Comment ID
            tenant_id: Tenant ID (for isolation)
            user_id: User ID (must match original commenter)

        Returns:
            True if deleted, False if not found/not authorized
        """
        comment = (
            db.query(TaskComment)
            .filter(
                TaskComment.id == comment_id,
                TaskComment.tenant_id == tenant_id,
                TaskComment.user_id == user_id  # Only original commenter can delete
            )
            .first()
        )

        if not comment:
            return False

        db.delete(comment)
        db.commit()

        return True


# Singleton instances
task = CRUDTask(Task)
task_comment = CRUDTaskComment(TaskComment)
