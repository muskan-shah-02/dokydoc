"""
Pydantic schemas for Task and TaskComment models.
Sprint 2 Extended - Phase 10: Tasks Feature

Schemas for request/response validation.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.task import TaskStatus, TaskPriority


# ==================== Task Schemas ====================

class TaskBase(BaseModel):
    """Base task schema with common fields."""
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, description="Detailed task description (markdown supported)")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Task status")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    assigned_to_id: Optional[int] = Field(None, description="User ID of assignee")
    document_id: Optional[int] = Field(None, description="Linked document ID")
    code_component_id: Optional[int] = Field(None, description="Linked code component ID")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    tags: List[str] = Field(default_factory=list, description="Task tags for categorization")
    estimated_hours: Optional[int] = Field(None, ge=0, description="Estimated effort in hours")
    actual_hours: Optional[int] = Field(None, ge=0, description="Actual effort in hours")


class TaskCreate(TaskBase):
    """
    Schema for creating a new task.

    The tenant_id and created_by_id are set automatically from the authenticated user.
    """
    pass


class TaskUpdate(BaseModel):
    """
    Schema for updating a task.

    All fields are optional - only provided fields will be updated.
    """
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to_id: Optional[int] = None
    document_id: Optional[int] = None
    code_component_id: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    estimated_hours: Optional[int] = Field(None, ge=0)
    actual_hours: Optional[int] = Field(None, ge=0)


class TaskAssign(BaseModel):
    """Schema for assigning a task to a user."""
    assigned_to_id: Optional[int] = Field(..., description="User ID to assign to (null to unassign)")


class TaskStatusUpdate(BaseModel):
    """Schema for updating task status only."""
    status: TaskStatus = Field(..., description="New task status")


class TaskResponse(TaskBase):
    """
    Schema for task response.

    Includes all task fields plus system fields.
    """
    id: int
    tenant_id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    # Related objects (simplified)
    created_by: Optional[dict] = Field(None, description="Creator user info")
    assigned_to: Optional[dict] = Field(None, description="Assignee user info")
    document: Optional[dict] = Field(None, description="Linked document info")
    code_component: Optional[dict] = Field(None, description="Linked code component info")

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Schema for paginated task list response."""
    tasks: List[TaskResponse]
    total: int
    skip: int
    limit: int


class TaskStatisticsResponse(BaseModel):
    """Schema for task statistics response."""
    total: int = Field(..., description="Total number of tasks")
    by_status: dict = Field(..., description="Task counts by status")
    by_priority: dict = Field(..., description="Task counts by priority")
    overdue: int = Field(..., description="Number of overdue tasks")


# ==================== TaskComment Schemas ====================

class TaskCommentBase(BaseModel):
    """Base comment schema."""
    content: str = Field(..., min_length=1, description="Comment content (markdown supported)")


class TaskCommentCreate(TaskCommentBase):
    """
    Schema for creating a comment.

    The task_id, tenant_id, and user_id are set automatically.
    """
    pass


class TaskCommentUpdate(BaseModel):
    """Schema for updating a comment."""
    content: str = Field(..., min_length=1, description="Updated comment content")


class TaskCommentResponse(TaskCommentBase):
    """Schema for comment response."""
    id: int
    task_id: int
    user_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    is_edited: bool

    # Related user info
    user: Optional[dict] = Field(None, description="Commenter user info")

    model_config = {"from_attributes": True}


class TaskCommentListResponse(BaseModel):
    """Schema for paginated comment list response."""
    comments: List[TaskCommentResponse]
    total: int
    task_id: int
