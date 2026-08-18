

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = FastAPI(
    title="Task Management API",
    description="A lightweight microservice for managing tasks.",
    version="1.0.0",
)


# --------------------------------------------------------------------------
# Enums & Pydantic Models
# --------------------------------------------------------------------------

class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class TaskCreate(BaseModel):
    """Payload for creating a new task. Strictly validated."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100, examples=["Write report"])
    description: str | None = Field(
        default=None, max_length=1000, examples=["Quarterly summary for finance"]
    )
    status: TaskStatus = Field(default=TaskStatus.pending)


class TaskResponse(BaseModel):
    """Response model returned to clients. Controls serialization shape."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime


# --------------------------------------------------------------------------
# In-memory data store (swap for a real DB in production)
# --------------------------------------------------------------------------

_tasks_db: dict[UUID, TaskResponse] = {}


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/tasks", response_model=list[TaskResponse], tags=["Tasks"])
def list_tasks() -> list[TaskResponse]:
    """Return all tasks."""
    return list(_tasks_db.values())


@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
def get_task(task_id: UUID) -> TaskResponse:
    """Return a single task by its ID."""
    task = _tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
)
def create_task(payload: TaskCreate) -> TaskResponse:
    """Create a new task from a validated payload."""
    new_task = TaskResponse(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        status=payload.status,
        created_at=datetime.utcnow(),
    )
    _tasks_db[new_task.id] = new_task
    return new_task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
def delete_task(task_id: UUID) -> None:
    """Delete a task by its ID."""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    del _tasks_db[task_id]


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}