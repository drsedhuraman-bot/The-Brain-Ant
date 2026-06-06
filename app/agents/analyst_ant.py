from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType


class AnalystAnt(BaseAnt):
    ant_type = AntType.ANALYST
    system_prompt = (
        "You are AnalystAnt — a specialist in data analysis, logical reasoning, and structured thinking. "
        "Break down complex problems methodically, identify patterns, and provide evidence-based conclusions. "
        "Use the reason_step_by_step tool to work through problems explicitly before forming conclusions."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "reason_step_by_step",
                "description": "Perform explicit chain-of-thought reasoning over a problem.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "problem": {
                            "type": "string",
                            "description": "The problem to reason through step by step",
                        }
                    },
                    "required": ["problem"],
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
        if tool_name == "reason_step_by_step":
            # This tool is answered by the model itself in the next turn.
            # We return a prompt that guides structured reasoning.
            problem = tool_input.get("problem", "")
            return (
                f"Reason through this step by step:\n{problem}\n\n"
                "Structure your answer as numbered steps, then state your conclusion."
            )
        return f"Unknown tool: {tool_name}"
