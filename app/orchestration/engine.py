from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from ..config import settings
from ..database import DatabaseClient
from ..models.domain import Task, TaskStatus, AntType
from ..models.api import WSMessage, WSMessageType
from ..agents.brain import BrainAgent
from ..agents.registry import AntRegistry
from .streaming import StreamingCoordinator


class OrchestrationEngine:
    def __init__(self, db: DatabaseClient, streaming: StreamingCoordinator):
        self.db = db
        self.streaming = streaming
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.semaphore = asyncio.Semaphore(settings.max_ant_concurrency)

    async def run_task(self, task: Task) -> None:
        """Full task lifecycle: DB bookkeeping + Brain execution + streaming."""
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.update_task(task.id, {"status": TaskStatus.RUNNING})

        # Record Brain agent run
        run_record = self.db.create_agent_run(
            {
                "task_id": task.id,
                "ant_type": AntType.BRAIN,
                "input_summary": task.user_input[:500],
                "status": TaskStatus.RUNNING,
            }
        )

        try:
            session_messages = self._build_session_messages(task.session_id)

            async def stream_callback(msg: WSMessage) -> None:
                msg.task_id = task.id
                await self.streaming.broadcast(task.id, msg)

            registry = AntRegistry(self.client)
            brain = BrainAgent(
                client=self.client,
                registry=registry,
                stream_callback=stream_callback,
                semaphore=self.semaphore,
                task_id=task.id,
            )

            result_text, total_tokens = await asyncio.wait_for(
                brain.run(task.user_input, context={}, session_messages=session_messages),
                timeout=settings.task_timeout_seconds,
            )

            # Persist result
            completed_at = datetime.now(timezone.utc).isoformat()
            self.db.update_task(
                task.id,
                {
                    "status": TaskStatus.COMPLETED,
                    "result": result_text,
                    "completed_at": completed_at,
                },
            )
            self.db.update_agent_run(
                run_record["id"],
                {
                    "status": TaskStatus.COMPLETED,
                    "output_summary": result_text[:500],
                    "tokens_used": total_tokens,
                    "completed_at": completed_at,
                },
            )
            self.db.append_message(
                {
                    "session_id": task.session_id,
                    "task_id": task.id,
                    "role": "assistant",
                    "content": result_text,
                    "ant_type": AntType.BRAIN,
                }
            )
            self.db.update_session(task.session_id, {})  # triggers updated_at

            await self.streaming.broadcast(
                task.id,
                WSMessage(
                    type=WSMessageType.TASK_COMPLETED,
                    task_id=task.id,
                    metadata={"total_tokens": total_tokens},
                ),
            )

        except Exception as exc:
            err_msg = str(exc)
            self.db.update_task(task.id, {"status": TaskStatus.FAILED, "error": err_msg})
            self.db.update_agent_run(
                run_record["id"],
                {"status": TaskStatus.FAILED, "output_summary": err_msg[:500]},
            )
            await self.streaming.broadcast(
                task.id,
                WSMessage(
                    type=WSMessageType.TASK_FAILED,
                    task_id=task.id,
                    content=err_msg,
                ),
            )

        finally:
            await self.streaming.close(task.id)

    def _build_session_messages(self, session_id: str) -> list[dict]:
        """Format prior session messages for Claude's messages array."""
        raw = self.db.get_messages_for_session(session_id)
        messages: list[dict] = []
        for m in raw:
            role = m["role"]
            if role == "ant_trace":
                continue  # skip internal trace messages
            messages.append({"role": role, "content": m["content"]})
        return messages
