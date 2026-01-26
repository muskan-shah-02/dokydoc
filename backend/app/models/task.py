"""
Task model for project and document management.
Sprint 2 Extended - Phase 10: Tasks Feature

Tasks allow teams to:
- Track action items from document analysis
- Assign work to team members
- Link tasks to documents/code for traceability
- Collaborate with comments
- Manage priorities and deadlines
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base_class import Base


class TaskStatus(str, enum.Enum):
    """Task status workflow stages."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    """Task priority levels."""
    CRITICAL = "critical"  # P0 - Urgent, blocks everything
    HIGH = "high"          # P1 - Important, needs attention soon
    MEDIUM = "medium"      # P2 - Normal priority
    LOW = "low"            # P3 - Nice to have


class Task(Base):
    """
    Task model for project management and document governance.

    Tasks are tenant-scoped and can be linked to documents or code components
    for traceability. They support assignment, priorities, statuses, and
    collaborative comments.

    Multi-Tenancy: All tasks belong to a tenant and are isolated.
    RBAC: Task operations are protected by task:* permissions.
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Task details
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(
        SQLEnum(TaskStatus),
        default=TaskStatus.TODO,
        nullable=False,
        index=True
    )
    priority = Column(
        SQLEnum(TaskPriority),
        default=TaskPriority.MEDIUM,
        nullable=False,
        index=True
    )

    # Relationships - who created and who's assigned
    created_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    assigned_to_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    # Optional links to documents/code for traceability
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    code_component_id = Column(
        Integer,
        ForeignKey("code_components.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Dates
    due_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    completed_at = Column(DateTime, nullable=True)

    # Tags for categorization (JSON array of strings)
    # Example: ["bug", "api", "authentication"]
    tags = Column(JSON, default=list, nullable=False)

    # Estimated effort in hours (optional)
    estimated_hours = Column(Integer, nullable=True)

    # Actual effort in hours (optional, for time tracking)
    actual_hours = Column(Integer, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="tasks")
    created_by = relationship("User", foreign_keys=[created_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    document = relationship("Document", back_populates="tasks")
    code_component = relationship("CodeComponent", back_populates="tasks")
    comments = relationship(
        "TaskComment",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskComment.created_at"
    )

    def __repr__(self):
        return f"<Task {self.id}: {self.title} ({self.status.value})>"

    def to_dict(self):
        """Return dictionary representation."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_by_id": self.created_by_id,
            "assigned_to_id": self.assigned_to_id,
            "document_id": self.document_id,
            "code_component_id": self.code_component_id,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
        }


class TaskComment(Base):
    """
    Comments on tasks for collaboration.

    Allows team members to discuss tasks, provide updates, and share
    information. All comments are tenant-scoped.
    """
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Comment content (supports markdown)
    content = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Is this comment edited?
    is_edited = Column(Integer, default=0, nullable=False)  # Boolean as integer

    # Relationships
    task = relationship("Task", back_populates="comments")
    user = relationship("User")

    def __repr__(self):
        return f"<TaskComment {self.id} on Task {self.task_id}>"

    def to_dict(self):
        """Return dictionary representation."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_edited": bool(self.is_edited),
        }
