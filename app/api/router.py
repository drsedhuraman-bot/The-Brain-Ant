from fastapi import APIRouter
from .sessions import router as sessions_router
from .tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(sessions_router)
api_router.include_router(tasks_router)
