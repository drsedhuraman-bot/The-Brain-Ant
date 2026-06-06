from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.api.websocket import router as ws_router
from app.orchestration.streaming import StreamingCoordinator
from app.orchestration.engine import OrchestrationEngine
from app.orchestration.session_manager import SessionManager
from app.database import DatabaseClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = DatabaseClient.get()
    streaming = StreamingCoordinator()
    engine = OrchestrationEngine(db, streaming)
    session_mgr = SessionManager(db)

    app.state.db = db
    app.state.streaming = streaming
    app.state.engine = engine
    app.state.session_mgr = session_mgr

    yield


app = FastAPI(title="The Brain Ant", lifespan=lifespan)

app.include_router(api_router)
app.include_router(ws_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("app/static/index.html")
