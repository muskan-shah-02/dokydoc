"""
Task Management API Endpoints
Sprint 2 Extended - Phase 10: Tasks Feature

Complete task management system with:
- CRUD operations for tasks
- Task assignment and status updates
- Comments and collaboration
- Filtering, search, and statistics
- Full RBAC protection
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.crud_task import task as task_crud, task_comment as comment_crud
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskAssign,
    TaskStatusUpdate,
    TaskStatisticsResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCommentListResponse,
    TaskCommentUpdate,
)
from app.models.task import TaskStatus, TaskPriority
from app.models.user import User
from app.core.permissions import Permission
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ==================== Task CRUD Endpoints ====================

@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    *,
    db: Session = Depends(deps.get_db),
    task_in: TaskCreate,
    current_user: User = Depends(deps.require_permission(Permission.TASK_CREATE))
) -> TaskResponse:
    """
    Create a new task.

    **Permission Required:** `task:create`

    **Roles:** CXO, BA, Developer, PM

    The task is automatically linked to the current user's tenant.
    """
    logger.info(f"User {current_user.id} creating task: {task_in.title}")

    # Create task
    task = task_crud.create_task(
        db=db,
        obj_in=task_in,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id
    )

    logger.info(f"Task {task.id} created successfully")
    return task


@router.get("/", response_model=TaskListResponse)
def list_tasks(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ)),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    assigned_to_id: Optional[int] = Query(None, description="Filter by assignee ID"),
    created_by_id: Optional[int] = Query(None, description="Filter by creator ID"),
    document_id: Optional[int] = Query(None, description="Filter by linked document"),
    code_component_id: Optional[int] = Query(None, description="Filter by linked code component"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=100, description="Page size")
) -> TaskListResponse:
    """
    List tasks with optional filters.

    **Permission Required:** `task:read`

    **Roles:** All

    All tasks are automatically scoped to the current user's tenant.
    """
    logger.info(f"User {current_user.id} listing tasks with filters")

    # Get tasks
    tasks = task_crud.get_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        status=status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        document_id=document_id,
        code_component_id=code_component_id,
        skip=skip,
        limit=limit
    )

    # Get total count (without pagination)
    total = task_crud.get_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        status=status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        document_id=document_id,
        code_component_id=code_component_id,
        skip=0,
        limit=999999  # Get all for count
    )

    return TaskListResponse(
        tasks=tasks,
        total=len(total),
        skip=skip,
        limit=limit
    )


@router.get("/my-tasks", response_model=TaskListResponse)
def get_my_tasks(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ)),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
) -> TaskListResponse:
    """
    Get tasks assigned to the current user.

    **Permission Required:** `task:read`

    **Roles:** All

    Returns only tasks that are:
    - Assigned to the current user
    - Not completed or cancelled
    - Sorted by priority and due date
    """
    logger.info(f"User {current_user.id} fetching their tasks")

    tasks = task_crud.get_my_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )

    # Get total
    all_tasks = task_crud.get_my_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        skip=0,
        limit=999999
    )

    return TaskListResponse(
        tasks=tasks,
        total=len(all_tasks),
        skip=skip,
        limit=limit
    )


@router.get("/search", response_model=TaskListResponse)
def search_tasks(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ)),
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
) -> TaskListResponse:
    """
    Search tasks by title or description.

    **Permission Required:** `task:read`

    **Roles:** All

    Searches within the current user's tenant only.
    """
    logger.info(f"User {current_user.id} searching tasks: {q}")

    tasks = task_crud.search_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        search_query=q,
        skip=skip,
        limit=limit
    )

    # Get total
    all_tasks = task_crud.search_tasks(
        db=db,
        tenant_id=current_user.tenant_id,
        search_query=q,
        skip=0,
        limit=999999
    )

    return TaskListResponse(
        tasks=tasks,
        total=len(all_tasks),
        skip=skip,
        limit=limit
    )


@router.get("/statistics", response_model=TaskStatisticsResponse)
def get_task_statistics(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ)),
    user_id: Optional[int] = Query(None, description="Get stats for specific user")
) -> TaskStatisticsResponse:
    """
    Get task statistics for the tenant or a specific user.

    **Permission Required:** `task:read`

    **Roles:** All

    Returns counts by status, priority, and overdue tasks.
    """
    logger.info(f"User {current_user.id} fetching task statistics")

    stats = task_crud.get_task_statistics(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=user_id
    )

    return TaskStatisticsResponse(**stats)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ))
) -> TaskResponse:
    """
    Get a single task by ID.

    **Permission Required:** `task:read`

    **Roles:** All

    Returns 404 if task doesn't exist or belongs to another tenant.
    """
    logger.info(f"User {current_user.id} fetching task {task_id}")

    task = task_crud.get_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(deps.require_permission(Permission.TASK_UPDATE))
) -> TaskResponse:
    """
    Update a task.

    **Permission Required:** `task:update`

    **Roles:** CXO, BA, Developer, PM

    Returns 404 if task doesn't exist or belongs to another tenant.
    """
    logger.info(f"User {current_user.id} updating task {task_id}")

    task = task_crud.update_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        obj_in=task_in
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(f"Task {task_id} updated successfully")
    return task


@router.put("/{task_id}/assign", response_model=TaskResponse)
def assign_task(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    assignment: TaskAssign,
    current_user: User = Depends(deps.require_permission(Permission.TASK_ASSIGN))
) -> TaskResponse:
    """
    Assign or reassign a task to a user.

    **Permission Required:** `task:assign`

    **Roles:** CXO, BA

    Set `assigned_to_id` to null to unassign the task.
    """
    logger.info(f"User {current_user.id} assigning task {task_id} to user {assignment.assigned_to_id}")

    task = task_crud.assign_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        assigned_to_id=assignment.assigned_to_id
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(f"Task {task_id} assigned successfully")
    return task


@router.put("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    status_update: TaskStatusUpdate,
    current_user: User = Depends(deps.require_permission(Permission.TASK_UPDATE))
) -> TaskResponse:
    """
    Update task status only.

    **Permission Required:** `task:update`

    **Roles:** CXO, BA, Developer, PM

    Convenience endpoint for quick status changes.
    """
    logger.info(f"User {current_user.id} updating status of task {task_id} to {status_update.status}")

    task_update = TaskUpdate(status=status_update.status)
    task = task_crud.update_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        obj_in=task_update
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    current_user: User = Depends(deps.require_permission(Permission.TASK_DELETE))
) -> None:
    """
    Delete a task.

    **Permission Required:** `task:delete`

    **Roles:** CXO only

    Deletes the task and all its comments (CASCADE).
    """
    logger.info(f"User {current_user.id} deleting task {task_id}")

    deleted = task_crud.delete_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(f"Task {task_id} deleted successfully")


# ==================== Task Comment Endpoints ====================

@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
def add_comment(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    comment_in: TaskCommentCreate,
    current_user: User = Depends(deps.require_permission(Permission.TASK_COMMENT))
) -> TaskCommentResponse:
    """
    Add a comment to a task.

    **Permission Required:** `task:comment`

    **Roles:** All

    The comment is automatically linked to the current user and tenant.
    """
    logger.info(f"User {current_user.id} adding comment to task {task_id}")

    # Verify task exists and belongs to tenant
    task = task_crud.get_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Create comment
    comment = comment_crud.create_comment(
        db=db,
        obj_in=comment_in,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id
    )

    logger.info(f"Comment {comment.id} added to task {task_id}")
    return comment


@router.get("/{task_id}/comments", response_model=TaskCommentListResponse)
def get_comments(
    *,
    db: Session = Depends(deps.get_db),
    task_id: int,
    current_user: User = Depends(deps.require_permission(Permission.TASK_READ)),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
) -> TaskCommentListResponse:
    """
    Get all comments for a task.

    **Permission Required:** `task:read`

    **Roles:** All

    Comments are ordered by creation time (oldest first).
    """
    logger.info(f"User {current_user.id} fetching comments for task {task_id}")

    # Verify task exists and belongs to tenant
    task = task_crud.get_task(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get comments
    comments = comment_crud.get_comments(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit
    )

    # Get total
    all_comments = comment_crud.get_comments(
        db=db,
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        skip=0,
        limit=999999
    )

    return TaskCommentListResponse(
        comments=comments,
        total=len(all_comments),
        task_id=task_id
    )


@router.put("/comments/{comment_id}", response_model=TaskCommentResponse)
def update_comment(
    *,
    db: Session = Depends(deps.get_db),
    comment_id: int,
    comment_update: TaskCommentUpdate,
    current_user: User = Depends(deps.require_permission(Permission.TASK_COMMENT))
) -> TaskCommentResponse:
    """
    Update a comment.

    **Permission Required:** `task:comment`

    **Roles:** All (only the original commenter)

    Only the user who created the comment can edit it.
    """
    logger.info(f"User {current_user.id} updating comment {comment_id}")

    comment = comment_crud.update_comment(
        db=db,
        comment_id=comment_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        content=comment_update.content
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found or you don't have permission to edit it"
        )

    logger.info(f"Comment {comment_id} updated successfully")
    return comment


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    *,
    db: Session = Depends(deps.get_db),
    comment_id: int,
    current_user: User = Depends(deps.require_permission(Permission.TASK_COMMENT))
) -> None:
    """
    Delete a comment.

    **Permission Required:** `task:comment`

    **Roles:** All (only the original commenter)

    Only the user who created the comment can delete it.
    """
    logger.info(f"User {current_user.id} deleting comment {comment_id}")

    deleted = comment_crud.delete_comment(
        db=db,
        comment_id=comment_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Comment not found or you don't have permission to delete it"
        )

    logger.info(f"Comment {comment_id} deleted successfully")
