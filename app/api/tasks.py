from fastapi import APIRouter, HTTPException, Request
from ..models.api import SubmitTaskRequest, TaskResponse
from ..models.domain import TaskStatus

router = APIRouter(prefix="/api/tasks")


def _get_session_mgr(request: Request):
    return request.app.state.session_mgr


def _get_engine(request: Request):
    return request.app.state.engine


def _get_db(request: Request):
    return request.app.state.db


@router.post("/", response_model=TaskResponse)
async def submit_task(body: SubmitTaskRequest, request: Request):
    mgr = _get_session_mgr(request)
    engine = _get_engine(request)

    # Verify session exists
    if not _get_db(request).get_session(body.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    task = await mgr.submit_task(
        session_id=body.session_id,
        user_input=body.user_input,
        engine=engine,
    )
    return TaskResponse(
        task_id=task.id,
        session_id=task.session_id,
        status=task.status,
        websocket_url=f"/ws/{task.id}",
    )


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    db = _get_db(request)
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/runs")
async def get_task_runs(task_id: str, request: Request):
    db = _get_db(request)
    return db.get_runs_for_task(task_id)
