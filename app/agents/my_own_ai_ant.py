from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType
from ..tools.my_own_ai_tools import personalize_response


class MyOwnAiAnt(BaseAnt):
    ant_type = AntType.MY_OWN_AI
    system_prompt = (
        "You are MyOwnAiAnt — a customizable personal assistant tailored to the user's preferences and style. "
        "Use personalize_response to format outputs according to specific style requirements (such as Concise, Tutorial, or Creative)."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "personalize_response",
                "description": "Adapt response formatting based on user preference (Concise, Tutorial, Creative).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The raw text content to adapt"},
                        "style": {
                            "type": "string",
                            "enum": ["concise", "tutorial", "creative"],
                            "description": "The target cognitive style for personalization",
                        },
                    },
                    "required": ["text", "style"],
                },
            }
        ]

    async def run(self, task_description: str, context: dict) -> tuple[str, int]:
        await self._emit(WSMessageType.ANT_STARTED, content=task_description)
        messages = [{"role": "user", "content": task_description}]
        text, tokens = await self._stream_completion(messages, tools=self.get_tools())
        await self._emit(WSMessageType.ANT_COMPLETED, metadata={"tokens": tokens})
        return text, tokens

    async def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "personalize_response":
            return await personalize_response(
                text=tool_input["text"],
                style=tool_input["style"],
            )
        return f"Unknown tool: {tool_name}"
