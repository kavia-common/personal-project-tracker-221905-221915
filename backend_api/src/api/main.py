from datetime import datetime, date
from typing import List, Optional, Tuple

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
import enum
import os

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data"))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskStatus(str, enum.Enum):
    open = "open"
    done = "done"


# ORM Models
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.open)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")


def init_db():
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic Schemas
class PaginationMeta(BaseModel):
    page: int = Field(..., description="Current page number (1-based).")
    page_size: int = Field(..., description="Number of items per page.")
    total: int = Field(..., description="Total number of items.")
    pages: int = Field(..., description="Total pages.")


class ProjectBase(BaseModel):
    name: str = Field(..., description="Name of the project.")
    description: Optional[str] = Field(None, description="Optional description of the project.")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Updated name of the project.")
    description: Optional[str] = Field(None, description="Updated description of the project.")


class ProjectOut(ProjectBase):
    id: int = Field(..., description="Unique identifier for the project.")
    created_at: datetime = Field(..., description="Creation timestamp (UTC).")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC).")

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    title: str = Field(..., description="Title of the task.")
    description: Optional[str] = Field(None, description="Optional details for the task.")
    status: Optional[TaskStatus] = Field(None, description="Task status (open|done). Defaults to 'open'.")
    due_date: Optional[date] = Field(None, description="Optional due date (YYYY-MM-DD).")

    @validator("title")
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class TaskCreate(TaskBase):
    status: Optional[TaskStatus] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title.")
    description: Optional[str] = Field(None, description="Updated description.")
    status: Optional[TaskStatus] = Field(None, description="Updated status (open|done).")
    due_date: Optional[date] = Field(None, description="Updated due date (YYYY-MM-DD).")


class TaskOut(TaskBase):
    id: int = Field(..., description="Unique identifier for the task.")
    project_id: int = Field(..., description="Project ID this task belongs to.")
    status: TaskStatus = Field(..., description="Task status.")
    created_at: datetime = Field(..., description="Creation timestamp (UTC).")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC).")

    class Config:
        from_attributes = True


class PaginatedProjects(BaseModel):
    items: List[ProjectOut]
    meta: PaginationMeta


class PaginatedTasks(BaseModel):
    items: List[TaskOut]
    meta: PaginationMeta


openapi_tags = [
    {"name": "Health", "description": "Service health checks"},
    {"name": "Projects", "description": "CRUD operations for projects"},
    {"name": "Tasks", "description": "CRUD operations for tasks and completion"},
]

app = FastAPI(
    title="Personal Project Tracker API",
    description="Simple API to manage projects and tasks for personal use.",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# CORS configured to allow frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """Health check endpoint.
    Returns:
        JSON message indicating service is healthy.
    """
    return {"message": "Healthy"}


def _paginate(query, page: int, page_size: int, db: Session) -> Tuple[List, PaginationMeta]:
    total = query.count()
    pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    meta = PaginationMeta(page=page, page_size=page_size, total=total, pages=pages)
    return items, meta


# Projects Endpoints

# PUBLIC_INTERFACE
@app.get(
    "/api/projects",
    response_model=PaginatedProjects,
    tags=["Projects"],
    summary="List projects",
    description="List projects with optional pagination parameters.",
)
def list_projects(
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(20, ge=1, le=100, description="Page size."),
    db: Session = Depends(get_db),
):
    """List projects with pagination.

    Parameters:
        page: Page number (1-based).
        page_size: Items per page.
    Returns:
        PaginatedProjects: Items and pagination metadata.
    """
    query = db.query(Project).order_by(Project.created_at.desc())
    items, meta = _paginate(query, page, page_size, db)
    return {"items": items, "meta": meta}

# PUBLIC_INTERFACE
@app.post(
    "/api/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Projects"],
    summary="Create a project",
)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project.

    Body:
        ProjectCreate: name (required), description (optional)
    Returns:
        ProjectOut
    """
    now = datetime.utcnow()
    project = Project(
        name=payload.name.strip(),
        description=payload.description,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

# PUBLIC_INTERFACE
@app.get(
    "/api/projects/{project_id}",
    response_model=ProjectOut,
    tags=["Projects"],
    summary="Get a project by ID",
)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Fetch a project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# PUBLIC_INTERFACE
@app.put(
    "/api/projects/{project_id}",
    response_model=ProjectOut,
    tags=["Projects"],
    summary="Update a project",
)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Project name cannot be empty")
        project.name = name
    if payload.description is not None:
        project.description = payload.description
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project

# PUBLIC_INTERFACE
@app.delete(
    "/api/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Projects"],
    summary="Delete a project",
)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None


# Tasks Endpoints

# PUBLIC_INTERFACE
@app.get(
    "/api/projects/{project_id}/tasks",
    response_model=PaginatedTasks,
    tags=["Tasks"],
    summary="List tasks for a project",
)
def list_tasks_for_project(
    project_id: int,
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(20, ge=1, le=100, description="Page size."),
    db: Session = Depends(get_db),
):
    """List tasks under a specific project with pagination."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc())
    items, meta = _paginate(query, page, page_size, db)
    return {"items": items, "meta": meta}

# PUBLIC_INTERFACE
@app.post(
    "/api/projects/{project_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
    summary="Create a task under a project",
)
def create_task(project_id: int, payload: TaskCreate, db: Session = Depends(get_db)):
    """Create a task under a specific project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.utcnow()
    status_value = payload.status if payload.status is not None else TaskStatus.open
    task = Task(
        project_id=project_id,
        title=payload.title.strip(),
        description=payload.description,
        status=status_value,
        due_date=payload.due_date,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

# PUBLIC_INTERFACE
@app.get(
    "/api/tasks/{task_id}",
    response_model=TaskOut,
    tags=["Tasks"],
    summary="Get task by ID",
)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Fetch a task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# PUBLIC_INTERFACE
@app.put(
    "/api/tasks/{task_id}",
    response_model=TaskOut,
    tags=["Tasks"],
    summary="Update task by ID",
)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    """Update fields of a task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        task.title = title
    if payload.description is not None:
        task.description = payload.description
    if payload.status is not None:
        task.status = payload.status
    if payload.due_date is not None:
        task.due_date = payload.due_date
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

# PUBLIC_INTERFACE
@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tasks"],
    summary="Delete task by ID",
)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None

# PUBLIC_INTERFACE
@app.post(
    "/api/tasks/{task_id}/complete",
    response_model=TaskOut,
    tags=["Tasks"],
    summary="Mark task as complete",
    description="Marks task status to 'done' and returns updated task.",
)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Mark a task as complete."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.done
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task
