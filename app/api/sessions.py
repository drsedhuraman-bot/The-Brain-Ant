from fastapi import APIRouter, HTTPException, Request
from ..models.domain import Session, Task, Message
from ..models.api import CreateSessionRequest, SessionResponse

router = APIRouter(prefix="/api/sessions")


def _get_session_mgr(request: Request):
    return request.app.state.session_mgr


def _get_db(request: Request):
    return request.app.state.db


@router.post("/", response_model=Session)
async def create_session(body: CreateSessionRequest, request: Request) -> Session:
    mgr = _get_session_mgr(request)
    return await mgr.create_session(title=body.title)


@router.get("/", response_model=list[dict])
async def list_sessions(request: Request):
    db = _get_db(request)
    return db.list_sessions()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request):
    db = _get_db(request)
    session_data = db.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = db.get_messages_for_session(session_id)
    tasks = db.get_tasks_for_session(session_id)
    return {
        "session": session_data,
        "messages": messages,
        "tasks": tasks,
    }
