from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType
from ..tools.code_executor import execute_code


class CoderAnt(BaseAnt):
    ant_type = AntType.CODER
    system_prompt = (
        "You are CoderAnt — a specialist in writing and debugging code. "
        "Produce clean, well-structured, production-ready code. "
        "Use the execute_code tool to verify that your code runs correctly before presenting it. "
        "Always explain what the code does and how to use it."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "execute_code",
                "description": "Execute Python code in a sandboxed environment and return the output.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "language": {
                            "type": "string",
                            "enum": ["python"],
                            "description": "Programming language (only python supported)",
                        },
                    },
                    "required": ["code"],
                },
            }
        ]

    async def run(self, task_description: str, context: dict) -> tuple[str, int]:
        from ..models.api import WSMessageType
        await self._emit(WSMessageType.ANT_STARTED, content=task_description)
        messages = [{"role": "user", "content": task_description}]
        text, tokens = await self._stream_completion(messages, tools=self.get_tools())
        await self._emit(WSMessageType.ANT_COMPLETED, metadata={"tokens": tokens})
        return text, tokens

    async def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "execute_code":
            return await execute_code(
                code=tool_input["code"],
                language=tool_input.get("language", "python"),
            )
        return f"Unknown tool: {tool_name}"
