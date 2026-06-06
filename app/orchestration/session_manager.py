from __future__ import annotations
import asyncio
from ..database import DatabaseClient
from ..models.domain import Session, Task, TaskStatus
from ..models.api import WSMessage


class SessionManager:
    def __init__(self, db: DatabaseClient):
        self.db = db
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def create_session(self, title: str = "New Session") -> Session:
        session = Session(title=title)
        self.db.create_session(session.id, session.title)
        return session

    def get_session(self, session_id: str) -> dict | None:
        return self.db.get_session(session_id)

    def list_sessions(self) -> list[dict]:
        return self.db.list_sessions()

    async def submit_task(
        self,
        session_id: str,
        user_input: str,
        engine,  # OrchestrationEngine — avoid circular import at type-hint level
    ) -> Task:
        task = Task(session_id=session_id, user_input=user_input)

        # Persist task + user message
        self.db.create_task(
            {
                "id": task.id,
                "session_id": task.session_id,
                "user_input": task.user_input,
                "status": TaskStatus.PENDING,
            }
        )
        self.db.append_message(
            {
                "session_id": session_id,
                "task_id": task.id,
                "role": "user",
                "content": user_input,
            }
        )

        # Fire-and-forget
        loop_task = asyncio.create_task(engine.run_task(task))
        self._active_tasks[task.id] = loop_task
        loop_task.add_done_callback(lambda _: self._active_tasks.pop(task.id, None))

        return task

    def cancel_task(self, task_id: str) -> bool:
        t = self._active_tasks.get(task_id)
        if t:
            t.cancel()
            return True
        return False
