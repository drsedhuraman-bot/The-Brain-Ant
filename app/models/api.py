from enum import Enum
from pydantic import BaseModel, Field
from .domain import Session, Task, Message, TaskStatus, AntType


class CreateSessionRequest(BaseModel):
    title: str = "New Session"


class SubmitTaskRequest(BaseModel):
    session_id: str
    user_input: str


class TaskResponse(BaseModel):
    task_id: str
    session_id: str
    status: TaskStatus
    websocket_url: str


class SessionResponse(BaseModel):
    session: Session
    messages: list[Message]
    tasks: list[Task]


class WSMessageType(str, Enum):
    BRAIN_THINKING = "brain_thinking"
    ANT_STARTED = "ant_started"
    ANT_STREAMING = "ant_streaming"
    ANT_COMPLETED = "ant_completed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TEXT_DELTA = "text_delta"


class WSMessage(BaseModel):
    type: WSMessageType
    task_id: str
    ant_type: AntType | None = None
    content: str | None = None
    metadata: dict = Field(default_factory=dict)
