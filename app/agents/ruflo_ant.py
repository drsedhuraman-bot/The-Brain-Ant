from __future__ import annotations
from anthropic import AsyncAnthropic
from .base import BaseAnt
from ..models.domain import AntType
from ..models.api import WSMessageType
from ..tools.ruflo_tools import initialize_swarm, query_agentdb


class RufloAnt(BaseAnt):
    ant_type = AntType.RUFLO
    system_prompt = (
        "You are RufloAnt — a specialist in multi-agent swarm orchestration and knowledge memory management. "
        "Use initialize_swarm to spawn specialized sub-agents and configure topologies. "
        "Use query_agentdb to search and retrieve long-term context from AgentDB vector index."
    )

    def __init__(self, client: AsyncAnthropic, stream_callback=None):
        super().__init__(client, stream_callback)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "initialize_swarm",
                "description": "Set up a new sub-agent swarm topology.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topology": {
                            "type": "string",
                            "enum": ["mesh", "ring", "star", "hierarchical"],
                            "description": "Swarm architecture topology",
                        },
                        "agents": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of sub-agents to participate in the swarm",
                        },
                    },
                    "required": ["topology", "agents"],
                },
            },
            {
                "name": "query_agentdb",
                "description": "Query the HNSW vector database (AgentDB) for memory retrieval.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Information to search for"},
                        "namespace": {
                            "type": "string",
                            "description": "Target memory namespace (e.g. default, development)",
                            "default": "default",
                        },
                    },
                    "required": ["query"],
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
        if tool_name == "initialize_swarm":
            return await initialize_swarm(
                topology=tool_input["topology"],
                agents=tool_input["agents"],
            )
        elif tool_name == "query_agentdb":
            return await query_agentdb(
                query=tool_input["query"],
                namespace=tool_input.get("namespace", "default"),
            )
        return f"Unknown tool: {tool_name}"
