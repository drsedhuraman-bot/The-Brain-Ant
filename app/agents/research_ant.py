from __future__ import annotations
from anthropic import AsyncAnthropic
from collections.abc import Callable, Awaitable
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessage, WSMessageType
from ..tools.web_search import web_search


class ResearchAnt(BaseAnt):
    ant_type = AntType.RESEARCH
    system_prompt = (
        "You are ResearchAnt — a specialist in finding and summarizing information. "
        "Use the web_search tool to find relevant, up-to-date information. "
        "Always cite the sources you find. Synthesize multiple search results into "
        "a clear, structured, and factual summary. If results are limited, say so honestly."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "web_search",
                "description": "Search the web for current information on a topic.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to fetch",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            }
        ]

    async def run(self, task_description: str, context: dict) -> tuple[str, int]:
        await self._emit(WSMessageType.ANT_STARTED, content=task_description)
        messages = [{"role": "user", "content": task_description}]
        text, tokens = await self._stream_completion(messages, tools=self.get_tools())
        await self._emit(
            WSMessageType.ANT_COMPLETED, metadata={"tokens": tokens}
        )
        return text, tokens

    async def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "web_search":
            return await web_search(
                query=tool_input["query"],
                num_results=tool_input.get("num_results", 5),
            )
        return f"Unknown tool: {tool_name}"
