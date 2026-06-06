from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType
from ..tools.ecc_tools import optimize_prompts, security_scan


class EccAnt(BaseAnt):
    ant_type = AntType.ECC
    system_prompt = (
        "You are EccAnt — a specialist in agent performance optimization, code security audits, and token efficiency. "
        "Use optimize_prompts to trim token size and clarify system prompts for high-performance runs. "
        "Use security_scan to review source code for potential vulnerabilities or injection points before execution."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "optimize_prompts",
                "description": "Optimize an input prompt to improve token utilization and agent response speed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt or instruction to optimize"},
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "security_scan",
                "description": "Perform static analysis on python code for vulnerabilities and safety concerns.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The Python source code to audit"},
                    },
                    "required": ["code"],
                },
            },
        ]

    async def run(self, task_description: str, context: dict) -> tuple[str, int]:
        await self._emit(WSMessageType.ANT_STARTED, content=task_description)
        messages = [{"role": "user", "content": task_description}]
        text, tokens = await self._stream_completion(messages, tools=self.get_tools())
        await self._emit(WSMessageType.ANT_COMPLETED, metadata={"tokens": tokens})
        return text, tokens

    async def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "optimize_prompts":
            return await optimize_prompts(prompt=tool_input["prompt"])
        elif tool_name == "security_scan":
            return await security_scan(code=tool_input["code"])
        return f"Unknown tool: {tool_name}"
