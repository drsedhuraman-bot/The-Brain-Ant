from __future__ import annotations
import asyncio
from ..models.api import WSMessage


class StreamingCoordinator:
    """Fan-out: task_id → list of per-connection asyncio Queues."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def broadcast(self, task_id: str, message: WSMessage) -> None:
        for queue in self._subscribers.get(task_id, []):
            await queue.put(message)

    async def close(self, task_id: str) -> None:
        """Send sentinel None to all subscribers to signal stream end."""
        for queue in self._subscribers.get(task_id, []):
            await queue.put(None)
