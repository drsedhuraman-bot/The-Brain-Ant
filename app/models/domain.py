from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AntType(str, Enum):
    BRAIN = "brain"
    RESEARCH = "research"
    CODER = "coder"
    WRITER = "writer"
    ANALYST = "analyst"
    RUFLO = "ruflo"
    ECC = "ecc"
    MY_OWN_AI = "my_own_ai"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_input: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    ant_type: AntType
    input_summary: str
    output_summary: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    tokens_used: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    task_id: str | None = None
    role: str  # "user" | "assistant" | "ant_trace"
    content: str
    ant_type: AntType | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
