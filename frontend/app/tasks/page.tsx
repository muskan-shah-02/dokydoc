/**
 * Tasks Page
 * Sprint 2 Extended - Tasks & Project Management
 *
 * Features:
 * - List and Kanban board views
 * - Filters by status, priority, assignee
 * - Create/edit tasks
 * - Task comments
 * - Real-time updates
 */

"use client";

import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  ListTodo,
  Plus,
  Search,
  Filter,
  LayoutList,
  LayoutGrid,
  X,
  Calendar,
  User,
  AlertCircle,
  Clock,
  CheckCircle2,
  MessageSquare,
  Paperclip,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Task types matching backend
interface Task {
  id: number;
  title: string;
  description?: string;
  status: "backlog" | "todo" | "in_progress" | "in_review" | "done" | "blocked" | "cancelled";
  priority: "critical" | "high" | "medium" | "low";
  assigned_to_id?: number;
  assigned_to?: { id: number; email: string };
  due_date?: string;
  tags?: string[];
  created_by_id: number;
  created_at: string;
  comments_count?: number;
}

export default function TasksPage() {
  const { user, hasPermission } = useAuth();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [view, setView] = useState<"list" | "kanban">("list");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterPriority, setFilterPriority] = useState<string>("all");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const canCreate = hasPermission(Permission.TASK_CREATE);
  const canUpdate = hasPermission(Permission.TASK_UPDATE);

  // Load tasks
  useEffect(() => {
    loadTasks();
  }, [filterStatus, filterPriority]);

  const loadTasks = async () => {
    setIsLoading(true);
    try {
      const params: any = {};
      if (filterStatus !== "all") params.status = filterStatus;
      if (filterPriority !== "all") params.priority = filterPriority;

      const response = await api.get<Task[]>("/tasks", params);
      setTasks(response);
    } catch (error) {
      console.error("Failed to load tasks:", error);
      setTasks([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter tasks by search
  const filteredTasks = tasks.filter((task) =>
    task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (task.description && task.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Group tasks by status for Kanban
  const kanbanColumns = {
    backlog: filteredTasks.filter((t) => t.status === "backlog"),
    todo: filteredTasks.filter((t) => t.status === "todo"),
    in_progress: filteredTasks.filter((t) => t.status === "in_progress"),
    in_review: filteredTasks.filter((t) => t.status === "in_review"),
    done: filteredTasks.filter((t) => t.status === "done"),
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Tasks</h1>
            <p className="mt-2 text-gray-600">
              Manage and track your project tasks
            </p>
          </div>

          {canCreate && (
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Task
            </Button>
          )}
        </div>

        {/* Toolbar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <Input
              type="text"
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-11 pl-10"
            />
          </div>

          {/* View Toggle and Filters */}
          <div className="flex items-center space-x-2">
            {/* Filters */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="h-11 rounded-md border border-gray-300 px-3 text-sm"
            >
              <option value="all">All Statuses</option>
              <option value="backlog">Backlog</option>
              <option value="todo">To Do</option>
              <option value="in_progress">In Progress</option>
              <option value="in_review">In Review</option>
              <option value="done">Done</option>
            </select>

            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              className="h-11 rounded-md border border-gray-300 px-3 text-sm"
            >
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            {/* View Toggle */}
            <div className="flex rounded-lg border">
              <button
                onClick={() => setView("list")}
                className={`p-2 ${view === "list" ? "bg-blue-50 text-blue-600" : "text-gray-600"}`}
              >
                <LayoutList className="h-5 w-5" />
              </button>
              <button
                onClick={() => setView("kanban")}
                className={`p-2 ${view === "kanban" ? "bg-blue-50 text-blue-600" : "text-gray-600"}`}
              >
                <LayoutGrid className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <div className="text-center">
              <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600 mx-auto"></div>
              <p className="text-gray-600">Loading tasks...</p>
            </div>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border bg-white p-12">
            <ListTodo className="h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              {searchQuery ? "No tasks found" : "No tasks yet"}
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              {searchQuery
                ? "Try adjusting your search or filters"
                : "Create your first task to get started"}
            </p>
            {canCreate && !searchQuery && (
              <Button onClick={() => setCreateDialogOpen(true)} className="mt-4">
                <Plus className="mr-2 h-4 w-4" />
                Create Task
              </Button>
            )}
          </div>
        ) : view === "list" ? (
          <TaskListView tasks={filteredTasks} onTaskClick={setSelectedTask} />
        ) : (
          <KanbanView columns={kanbanColumns} onTaskClick={setSelectedTask} />
        )}
      </div>

      {/* Create Task Dialog */}
      {createDialogOpen && (
        <CreateTaskDialog
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={() => {
            setCreateDialogOpen(false);
            loadTasks();
          }}
        />
      )}

      {/* Task Detail Dialog */}
      {selectedTask && (
        <TaskDetailDialog
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onUpdate={loadTasks}
        />
      )}
    </AppLayout>
  );
}

// ============================================================================
// List View
// ============================================================================

function TaskListView({ tasks, onTaskClick }: { tasks: Task[]; onTaskClick: (task: Task) => void }) {
  return (
    <div className="rounded-lg border bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Task
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Priority
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Assignee
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Due Date
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {tasks.map((task) => (
              <tr
                key={task.id}
                onClick={() => onTaskClick(task)}
                className="cursor-pointer hover:bg-gray-50"
              >
                <td className="whitespace-nowrap px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div>
                      <div className="font-medium text-gray-900">{task.title}</div>
                      {task.description && (
                        <div className="mt-1 text-sm text-gray-500 line-clamp-1">
                          {task.description}
                        </div>
                      )}
                      {task.tags && task.tags.length > 0 && (
                        <div className="mt-1 flex gap-1">
                          {task.tags.slice(0, 2).map((tag) => (
                            <span
                              key={tag}
                              className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="whitespace-nowrap px-6 py-4">
                  <StatusBadge status={task.status} />
                </td>
                <td className="whitespace-nowrap px-6 py-4">
                  <PriorityBadge priority={task.priority} />
                </td>
                <td className="whitespace-nowrap px-6 py-4">
                  {task.assigned_to ? (
                    <div className="flex items-center space-x-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                        {task.assigned_to.email.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm text-gray-900">
                        {task.assigned_to.email.split("@")[0]}
                      </span>
                    </div>
                  ) : (
                    <span className="text-sm text-gray-500">Unassigned</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                  {task.due_date ? new Date(task.due_date).toLocaleDateString() : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// Kanban View
// ============================================================================

function KanbanView({
  columns,
  onTaskClick,
}: {
  columns: Record<string, Task[]>;
  onTaskClick: (task: Task) => void;
}) {
  const columnConfig = {
    backlog: { label: "Backlog", color: "gray" },
    todo: { label: "To Do", color: "blue" },
    in_progress: { label: "In Progress", color: "yellow" },
    in_review: { label: "In Review", color: "purple" },
    done: { label: "Done", color: "green" },
  };

  return (
    <div className="flex space-x-4 overflow-x-auto pb-4">
      {Object.entries(columnConfig).map(([key, config]) => (
        <div key={key} className="flex-shrink-0 w-80">
          <div className="rounded-lg border bg-white p-4">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">{config.label}</h3>
              <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">
                {columns[key as keyof typeof columns].length}
              </span>
            </div>

            <div className="space-y-3">
              {columns[key as keyof typeof columns].map((task) => (
                <div
                  key={task.id}
                  onClick={() => onTaskClick(task)}
                  className="cursor-pointer rounded-lg border bg-white p-3 hover:shadow-md"
                >
                  <div className="mb-2">
                    <h4 className="font-medium text-gray-900">{task.title}</h4>
                    {task.description && (
                      <p className="mt-1 text-sm text-gray-600 line-clamp-2">
                        {task.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <PriorityBadge priority={task.priority} size="sm" />
                      {task.comments_count && task.comments_count > 0 && (
                        <div className="flex items-center text-gray-500">
                          <MessageSquare className="h-4 w-4" />
                          <span className="ml-1 text-xs">{task.comments_count}</span>
                        </div>
                      )}
                    </div>

                    {task.assigned_to && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                        {task.assigned_to.email.charAt(0).toUpperCase()}
                      </div>
                    )}
                  </div>

                  {task.due_date && (
                    <div className="mt-2 flex items-center text-xs text-gray-500">
                      <Calendar className="mr-1 h-3 w-3" />
                      {new Date(task.due_date).toLocaleDateString()}
                    </div>
                  )}
                </div>
              ))}

              {columns[key as keyof typeof columns].length === 0 && (
                <div className="rounded-lg border-2 border-dashed border-gray-200 p-4 text-center text-sm text-gray-500">
                  No tasks
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Create Task Dialog
// ============================================================================

function CreateTaskDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<string>("medium");
  const [dueDate, setDueDate] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await api.post("/tasks", {
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        due_date: dueDate || undefined,
        status: "todo",
      });

      onSuccess();
    } catch (err: any) {
      setError(err.detail || "Failed to create task");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Create Task</h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              type="text"
              placeholder="Task title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <textarea
              id="description"
              placeholder="Task description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-2 w-full rounded-md border border-gray-300 p-2 text-sm"
              rows={4}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="priority">Priority</Label>
              <select
                id="priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="mt-2 w-full rounded-md border border-gray-300 p-2 text-sm"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div>
              <Label htmlFor="dueDate">Due Date</Label>
              <Input
                id="dueDate"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="flex space-x-3">
            <Button onClick={onClose} variant="outline" className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isLoading} className="flex-1">
              {isLoading ? "Creating..." : "Create Task"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Task Detail Dialog
// ============================================================================

function TaskDetailDialog({
  task,
  onClose,
  onUpdate,
}: {
  task: Task;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const { hasPermission } = useAuth();
  const [comments, setComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  const canUpdate = hasPermission(Permission.TASK_UPDATE);
  const canComment = hasPermission(Permission.TASK_COMMENT);

  // Load comments
  useEffect(() => {
    loadComments();
  }, [task.id]);

  const loadComments = async () => {
    try {
      const response = await api.get<any[]>(`/tasks/${task.id}/comments`);
      setComments(response);
    } catch (error) {
      console.error("Failed to load comments:", error);
    }
  };

  // Add comment
  const handleAddComment = async () => {
    if (!newComment.trim()) return;

    try {
      await api.post(`/tasks/${task.id}/comments`, {
        content: newComment.trim(),
      });
      setNewComment("");
      loadComments();
    } catch (error) {
      console.error("Failed to add comment:", error);
    }
  };

  // Update status
  const handleUpdateStatus = async (newStatus: string) => {
    if (!canUpdate) return;

    setIsUpdating(true);
    try {
      await api.put(`/tasks/${task.id}`, { status: newStatus });
      onUpdate();
      onClose();
    } catch (error) {
      console.error("Failed to update task:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-start justify-between">
          <div className="flex-1">
            <h2 className="text-2xl font-semibold text-gray-900">{task.title}</h2>
            <div className="mt-2 flex items-center space-x-3">
              <StatusBadge status={task.status} />
              <PriorityBadge priority={task.priority} />
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Task Details */}
        <div className="mb-6 space-y-4">
          {task.description && (
            <div>
              <h3 className="text-sm font-medium text-gray-700">Description</h3>
              <p className="mt-1 text-sm text-gray-600">{task.description}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {task.assigned_to && (
              <div>
                <h3 className="text-sm font-medium text-gray-700">Assignee</h3>
                <div className="mt-1 flex items-center space-x-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                    {task.assigned_to.email.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-gray-900">{task.assigned_to.email}</span>
                </div>
              </div>
            )}

            {task.due_date && (
              <div>
                <h3 className="text-sm font-medium text-gray-700">Due Date</h3>
                <p className="mt-1 text-sm text-gray-600">
                  {new Date(task.due_date).toLocaleDateString()}
                </p>
              </div>
            )}
          </div>

          {task.tags && task.tags.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700">Tags</h3>
              <div className="mt-1 flex flex-wrap gap-2">
                {task.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Status Actions */}
        {canUpdate && (
          <div className="mb-6 rounded-lg border bg-gray-50 p-4">
            <h3 className="mb-3 text-sm font-medium text-gray-700">Update Status</h3>
            <div className="flex flex-wrap gap-2">
              {["todo", "in_progress", "in_review", "done"].map((status) => (
                <button
                  key={status}
                  onClick={() => handleUpdateStatus(status)}
                  disabled={isUpdating || task.status === status}
                  className={`rounded-md px-3 py-1 text-sm font-medium ${
                    task.status === status
                      ? "bg-blue-600 text-white"
                      : "bg-white border hover:bg-gray-50"
                  } disabled:opacity-50`}
                >
                  {status.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Comments */}
        <div>
          <h3 className="mb-4 text-lg font-semibold text-gray-900">
            Comments ({comments.length})
          </h3>

          {canComment && (
            <div className="mb-4">
              <textarea
                placeholder="Add a comment..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="w-full rounded-md border border-gray-300 p-2 text-sm"
                rows={3}
              />
              <div className="mt-2 flex justify-end">
                <Button onClick={handleAddComment} disabled={!newComment.trim()}>
                  Add Comment
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {comments.map((comment) => (
              <div key={comment.id} className="rounded-lg border bg-gray-50 p-3">
                <div className="mb-2 flex items-center space-x-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                    {comment.created_by?.email?.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm font-medium text-gray-900">
                    {comment.created_by?.email}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(comment.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{comment.content}</p>
              </div>
            ))}

            {comments.length === 0 && (
              <p className="text-center text-sm text-gray-500 py-4">
                No comments yet
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Utility Components
// ============================================================================

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; color: string }> = {
    backlog: { label: "Backlog", color: "bg-gray-100 text-gray-700" },
    todo: { label: "To Do", color: "bg-blue-100 text-blue-700" },
    in_progress: { label: "In Progress", color: "bg-yellow-100 text-yellow-700" },
    in_review: { label: "In Review", color: "bg-purple-100 text-purple-700" },
    done: { label: "Done", color: "bg-green-100 text-green-700" },
    blocked: { label: "Blocked", color: "bg-red-100 text-red-700" },
    cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-700" },
  };

  const { label, color } = config[status] || config.todo;

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function PriorityBadge({ priority, size = "md" }: { priority: string; size?: "sm" | "md" }) {
  const config: Record<string, { label: string; color: string }> = {
    critical: { label: "Critical", color: "bg-red-100 text-red-700" },
    high: { label: "High", color: "bg-orange-100 text-orange-700" },
    medium: { label: "Medium", color: "bg-blue-100 text-blue-700" },
    low: { label: "Low", color: "bg-gray-100 text-gray-700" },
  };

  const { label, color } = config[priority] || config.medium;

  return (
    <span
      className={`inline-flex items-center rounded-full ${color} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-0.5 text-xs"
      } font-medium`}
    >
      {label}
    </span>
  );
}
