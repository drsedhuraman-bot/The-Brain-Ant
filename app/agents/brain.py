from __future__ import annotations
import asyncio
from collections.abc import Callable, Awaitable
from anthropic import AsyncAnthropic
from .base import BaseAnt
from .registry import AntRegistry
from ..models.domain import AntType
from ..models.api import WSMessage, WSMessageType


class BrainAgent(BaseAnt):
    ant_type = AntType.BRAIN
    system_prompt = """You are the Brain — the central orchestrator of an ant colony of AI agents.

Your job:
1. Understand the user's task deeply.
2. Decompose it into focused subtasks.
3. Delegate each subtask to the most appropriate Ant worker using delegate_to_ant.
4. Synthesize all Ant outputs into a clear, coherent final answer.

Available Ants:
- research: web search, fact-finding, summarization from the web
- coder: code generation, debugging, technical implementation
- writer: prose writing, editing, formatting documents
- analyst: data analysis, logical reasoning, structured thinking
- ruflo: multi-agent swarm orchestration, agent topology configuration, and AgentDB vector searches
- ecc: prompt/token optimization, static security audits, and harness performance checks
- my_own_ai: personalized context adaptation and custom style formatting

Guidelines:
- Delegate when a subtask benefits from specialization.
- You may delegate to multiple ants (sequentially is fine).
- After collecting results, synthesize them into a single, high-quality final answer.
- If the task is simple and requires no delegation, answer directly without calling any tools."""

    def __init__(
        self,
        client: AsyncAnthropic,
        registry: AntRegistry,
        stream_callback: Callable[[WSMessage], Awaitable[None]] | None = None,
        semaphore: asyncio.Semaphore | None = None,
        task_id: str = "",
    ):
        super().__init__(client, stream_callback)
        self.registry = registry
        self.semaphore = semaphore or asyncio.Semaphore(3)
        self.task_id = task_id
        self._ant_results: list[dict] = []

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "delegate_to_ant",
                "description": (
                    "Delegate a subtask to a specialized Ant worker. "
                    "The ant will execute the subtask and return its result."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ant_type": {
                            "type": "string",
                            "enum": ["research", "coder", "writer", "analyst", "ruflo", "ecc", "my_own_ai"],
                            "description": "The type of Ant to delegate to",
                        },
                        "subtask": {
                            "type": "string",
                            "description": "Clear description of the subtask for the Ant",
                        },
                    },
                    "required": ["ant_type", "subtask"],
                },
            }
        ]

    async def run(
        self,
        task_description: str,
        context: dict,
        session_messages: list[dict] | None = None,
    ) -> tuple[str, int]:
        """
        Orchestration loop:
        1. Stream Brain's decomposition / delegation via Claude tool calls.
        2. For each delegate_to_ant call, run the target Ant.
        3. Stream Brain's synthesis of all Ant results.
        """
        from ..config import settings
        if settings.anthropic_api_key == "mock-key":
            return await self._mock_run(task_description, context, session_messages)

        # Emit brain thinking start
        await self._emit_with_task(WSMessageType.BRAIN_THINKING, content="Analyzing your request…")

        # Build messages: include prior session history if available
        messages: list[dict] = []
        if session_messages:
            messages.extend(session_messages)
        messages.append({"role": "user", "content": task_description})

        full_text = ""
        total_tokens = 0
        current_messages = list(messages)

        while True:
            tool_use_blocks = []
            text_in_turn = ""
            turn_tokens = 0

            async with self.client.messages.stream(
                model=self._model(),
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=self.get_tools(),
                messages=current_messages,
            ) as stream:
                async for event in stream:
                    etype = type(event).__name__

                    if etype == "RawContentBlockDeltaEvent":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            text_in_turn += delta.text
                            full_text += delta.text
                            await self._emit_with_task(
                                WSMessageType.BRAIN_THINKING, content=delta.text
                            )

                    elif etype == "RawMessageStartEvent":
                        if hasattr(event.message, "usage"):
                            turn_tokens += event.message.usage.input_tokens

                    elif etype == "RawMessageDeltaEvent":
                        if hasattr(event.usage, "output_tokens"):
                            turn_tokens += event.usage.output_tokens

                total_tokens += turn_tokens
                final_message = await stream.get_final_message()

            tool_use_blocks = [b for b in final_message.content if b.type == "tool_use"]

            if not tool_use_blocks:
                break  # Brain is done — no more delegations

            # Execute delegations (respecting concurrency limit)
            tool_results: list[dict] = []
            tasks = [
                self._execute_delegation(block.id, block.input)
                for block in tool_use_blocks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for block, result in zip(tool_use_blocks, results):
                if isinstance(result, Exception):
                    result_text = f"Ant failed: {result}"
                else:
                    result_text, ant_tokens = result
                    total_tokens += ant_tokens

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text if isinstance(result, Exception) else result_text,
                    }
                )

            current_messages.append(
                {"role": "assistant", "content": final_message.content}
            )
            current_messages.append({"role": "user", "content": tool_results})

        return full_text, total_tokens

    async def _execute_delegation(
        self, tool_use_id: str, tool_input: dict
    ) -> tuple[str, int]:
        ant_type_str = tool_input.get("ant_type", "")
        subtask = tool_input.get("subtask", "")

        try:
            ant_type = AntType(ant_type_str)
        except ValueError:
            return f"Unknown ant type: {ant_type_str}", 0

        # Wrap callback to inject task_id into WSMessages
        async def callback_with_task_id(msg: WSMessage) -> None:
            msg.task_id = self.task_id
            if self.stream_callback:
                await self.stream_callback(msg)

        async with self.semaphore:
            ant = self.registry.create(ant_type, stream_callback=callback_with_task_id)
            return await ant.run(subtask, context={})

    async def _emit_with_task(
        self, msg_type: WSMessageType, content: str | None = None, metadata: dict | None = None
    ) -> None:
        await self._emit(msg_type, content=content, metadata=metadata, task_id=self.task_id)

    async def _mock_run(
        self,
        task_description: str,
        context: dict,
        session_messages: list[dict] | None = None,
    ) -> tuple[str, int]:
        import asyncio
        from ..models.domain import AntType

        await self._emit_with_task(WSMessageType.BRAIN_THINKING, content="Analyzing your request…\n")
        await asyncio.sleep(0.5)

        # Decide which ants to delegate to
        desc_lower = task_description.lower()
        delegations = []

        if any(w in desc_lower for w in ["swarm", "ruflo", "topology", "mesh", "ring", "star", "hierarchical"]):
            delegations.append(("ruflo", f"Spawn and initialize a swarm setup for: {task_description}"))
        elif any(w in desc_lower for w in ["optimize", "ecc", "performance", "security", "audit", "vulnerability", "tokens"]):
            delegations.append(("ecc", f"Audit security and optimize prompt tokens for: {task_description}"))
        elif any(w in desc_lower for w in ["personal", "my own", "custom", "preferences", "cognitive"]):
            delegations.append(("my_own_ai", f"Personalize response style for: {task_description}"))
        elif any(w in desc_lower for w in ["code", "program", "script", "develop", "function", "bug", "write some code"]):
            delegations.append(("coder", f"Write Python code to solve: {task_description}"))
        elif any(w in desc_lower for w in ["search", "find", "weather", "who", "what", "news", "current"]):
            delegations.append(("research", f"Research the web for details about: {task_description}"))
        elif any(w in desc_lower for w in ["analyze", "reason", "think", "logic", "compare", "why"]):
            delegations.append(("analyst", f"Analyze and reason step-by-step: {task_description}"))
        elif any(w in desc_lower for w in ["write", "draft", "prose", "text", "essay", "article"]):
            delegations.append(("writer", f"Write a beautifully styled prose about: {task_description}"))
        else:
            delegations.append(("research", f"Search information related to: {task_description}"))
            delegations.append(("writer", f"Draft a final report based on search results for: {task_description}"))

        # Tell the user what the plan is
        plan_str = f"Plan:\n"
        for ant_type, subtask in delegations:
            plan_str += f"- Delegate to **{ant_type}**: '{subtask}'\n"
        plan_str += "\nStarting delegation...\n\n"
        
        for char in plan_str:
            await self._emit_with_task(WSMessageType.BRAIN_THINKING, content=char)
            await asyncio.sleep(0.005)

        await asyncio.sleep(0.5)

        results = []
        total_tokens = 200

        for ant_type, subtask in delegations:
            res_text, tokens = await self._execute_delegation("mock_tool_id", {"ant_type": ant_type, "subtask": subtask})
            results.append((ant_type, res_text))
            total_tokens += tokens

        synthesis_intro = "\n\nSynthesizing findings and drafting the final response:\n\n"
        for char in synthesis_intro:
            await self._emit_with_task(WSMessageType.BRAIN_THINKING, content=char)
            await asyncio.sleep(0.005)

        final_response = "### Final Synthesized Answer\n\n"
        for ant_type, res_text in results:
            final_response += f"**From {ant_type.upper()} Ant**:\n{res_text}\n\n"
        final_response += "The task is now fully completed. Let me know if you need anything else!"

        for char in final_response:
            await self._emit_with_task(WSMessageType.BRAIN_THINKING, content=char)
            await asyncio.sleep(0.002)

        return plan_str + synthesis_intro + final_response, total_tokens
