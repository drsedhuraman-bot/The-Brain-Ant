from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType


class WriterAnt(BaseAnt):
    ant_type = AntType.WRITER
    system_prompt = (
        "You are WriterAnt — a specialist in prose writing, editing, and formatting. "
        "Produce compelling, clear, and well-structured text tailored to the audience and purpose. "
        "Match tone and style to the context: technical for documentation, conversational for "
        "explanations, persuasive for proposals."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return []  # WriterAnt is pure generation — no external tools

    async def run(self, task_description: str, context: dict) -> tuple[str, int]:
        await self._emit(WSMessageType.ANT_STARTED, content=task_description)
        messages = [{"role": "user", "content": task_description}]
        text, tokens = await self._stream_completion(messages)
        await self._emit(WSMessageType.ANT_COMPLETED, metadata={"tokens": tokens})
        return text, tokens
