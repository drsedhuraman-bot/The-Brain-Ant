from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Awaitable
from anthropic import AsyncAnthropic
from ..models.domain import AntType
from ..models.api import WSMessage, WSMessageType


class BaseAnt(ABC):
    ant_type: AntType  # set on each subclass
    system_prompt: str  # set on each subclass; cached by Anthropic

    def __init__(
        self,
        client: AsyncAnthropic,
        stream_callback: Callable[[WSMessage], Awaitable[None]] | None = None,
    ):
        self.client = client
        self.stream_callback = stream_callback

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """Return Claude tool_use definitions for this Ant."""
        ...

    @abstractmethod
    async def run(
        self,
        task_description: str,
        context: dict,
    ) -> tuple[str, int]:
        """
        Execute the ant's task.
        Returns (full_output_text, total_tokens_used).
        Emits WSMessages via stream_callback as it runs.
        """
        ...

    async def _stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        """
        Core multi-turn streaming loop.
        Handles tool_use blocks by calling _dispatch_tool and looping.
        Returns (accumulated_text, total_input_tokens + output_tokens).
        """
        from ..config import settings
        if settings.anthropic_api_key == "mock-key":
            return await self._mock_stream_completion(messages, tools, max_tokens)

        full_text = ""
        total_tokens = 0
        current_messages = list(messages)

        while True:
            kwargs: dict = dict(
                model=self._model(),
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=current_messages,
            )
            if tools:
                kwargs["tools"] = tools

            tool_calls: list[dict] = []
            text_in_turn = ""

            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type = type(event).__name__

                    if event_type == "RawContentBlockDeltaEvent":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            text_in_turn += delta.text
                            full_text += delta.text
                            await self._emit(
                                WSMessageType.ANT_STREAMING,
                                content=delta.text,
                            )

                    elif event_type == "RawContentBlockStartEvent":
                        block = event.content_block
                        if hasattr(block, "type") and block.type == "tool_use":
                            tool_calls.append(
                                {"id": block.id, "name": block.name, "input": ""}
                            )

                    elif event_type == "RawContentBlockStopEvent":
                        pass

                    elif event_type == "RawMessageDeltaEvent":
                        if hasattr(event.usage, "output_tokens"):
                            total_tokens += event.usage.output_tokens

                    elif event_type == "RawMessageStartEvent":
                        if hasattr(event.message, "usage"):
                            total_tokens += event.message.usage.input_tokens

                # Accumulate tool inputs via input_json deltas — handled in stream
                final_message = await stream.get_final_message()

            # Collect complete tool_use blocks from final message
            tool_use_blocks = [
                b for b in final_message.content if b.type == "tool_use"
            ]

            if not tool_use_blocks:
                break  # No tool calls — done

            # Build tool results
            tool_results: list[dict] = []
            for block in tool_use_blocks:
                result = await self._dispatch_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

            # Append assistant turn + tool results for next loop
            current_messages.append(
                {"role": "assistant", "content": final_message.content}
            )
            current_messages.append(
                {"role": "user", "content": tool_results}
            )

        return full_text, total_tokens

    async def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        """Route a tool call to its implementation. Override in subclasses."""
        return f"Tool '{tool_name}' not implemented."

    async def _emit(
        self,
        msg_type: WSMessageType,
        content: str | None = None,
        metadata: dict | None = None,
        task_id: str = "",
    ) -> None:
        if self.stream_callback is None:
            return
        msg = WSMessage(
            type=msg_type,
            task_id=task_id,
            ant_type=self.ant_type,
            content=content,
            metadata=metadata or {},
        )
        await self.stream_callback(msg)

    def _model(self) -> str:
        from ..config import settings
        return settings.model

    async def _mock_stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        import asyncio
        from ..models.domain import AntType

        # Determine last user message
        last_user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                content = m["content"]
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            last_user_msg += block.get("text", "")
                else:
                    last_user_msg = content
                break

        if self.ant_type == AntType.RESEARCH:
            intro = f"Searching the web for: '{last_user_msg}'...\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            search_result = await self._dispatch_tool("web_search", {"query": last_user_msg})
            
            synthesis_intro = "Found search results. Here is the synthesized summary:\n\n"
            for char in synthesis_intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            lines = search_result.split("\n")
            summary_lines = []
            for line in lines:
                if line.startswith("Summary: ") or line.startswith("- "):
                    summary_lines.append(line)
            
            summary_text = "\n".join(summary_lines) if summary_lines else search_result
            if len(summary_text) > 800:
                summary_text = summary_text[:800] + "...\n(truncated)"
                
            for char in summary_text:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
                
            return intro + synthesis_intro + summary_text, 450

        elif self.ant_type == AntType.CODER:
            intro = f"Analyzing task to write Python code for: '{last_user_msg}'...\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            code_to_run = "print('Hello from CoderAnt sandboxed environment!')\nimport sys\nprint('Python version:', sys.version.split()[0])"
            if "prime" in last_user_msg.lower():
                code_to_run = "def is_prime(n):\n    return n > 1 and all(n % i != 0 for i in range(2, int(n**0.5) + 1))\nprint('Primes up to 20:', [x for x in range(20) if is_prime(x)])"
            elif "fib" in last_user_msg.lower():
                code_to_run = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\nprint('Fibonacci(8):', fib(8))"
            
            run_intro = f"Running verification code:\n```python\n{code_to_run}\n```\n"
            for char in run_intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
                
            execution_output = await self._dispatch_tool("execute_code", {"code": code_to_run})
            
            out_str = f"\nExecution Output:\n```\n{execution_output}\n```\n\nThe code executes successfully and works as intended!"
            for char in out_str:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
                
            return intro + run_intro + out_str, 500

        elif self.ant_type == AntType.ANALYST:
            intro = f"Performing logical step-by-step reasoning on: '{last_user_msg}'\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
                
            await self._dispatch_tool("reason_step_by_step", {"problem": last_user_msg})
            steps = (
                "1. **Identify parameters**: We parse the initial constraints of the problem.\n"
                "2. **Evaluate constraints**: We verify the system boundaries and inputs.\n"
                "3. **Synthesize solution**: We formulate an evidence-based conclusion based on logical consistency.\n\n"
                "**Conclusion**: The system status is functional, verified by SQLite backend tests."
            )
            for char in steps:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
                
            return intro + steps, 300

        elif self.ant_type == AntType.WRITER:
            intro = f"Generating clear and compelling prose response for: '{last_user_msg}'\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
                
            prose = (
                f"### Prose Synthesis\n\n"
                f"Regarding the query '{last_user_msg}', this is a beautifully drafted response to provide clarity. "
                f"All components are working harmoniously. The system displays active communication streams, "
                f"live WebSocket notifications, and traces tasks step by step. We have successfully verified "
                f"the layout and functionalities of the Ant colony.\n\n"
                f"Please let me know if you would like me to rewrite or format this in another specific style!"
            )
            for char in prose:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
                
            return intro + prose, 250

        elif self.ant_type == AntType.RUFLO:
            intro = f"Analyzing swarm configuration for: '{last_user_msg}'...\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            swarm_res = await self._dispatch_tool("initialize_swarm", {"topology": "hierarchical", "agents": ["coder", "researcher"]})
            db_res = await self._dispatch_tool("query_agentdb", {"query": last_user_msg, "namespace": "development"})
            
            out_str = f"Swarm Setup:\n{swarm_res}\n\nAgentDB Context Retrieval:\n{db_res}\n\nSwarm coordination initialized successfully!"
            for char in out_str:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
            return intro + out_str, 400

        elif self.ant_type == AntType.ECC:
            intro = f"Running performance harness and security scanning on: '{last_user_msg}'...\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            opt_res = await self._dispatch_tool("optimize_prompts", {"prompt": last_user_msg})
            scan_res = await self._dispatch_tool("security_scan", {"code": "def run():\n    exec('import os')\n    eval('2+2')"})
            
            out_str = f"{opt_res}\n\n{scan_res}\n\nHarness validation check: COMPLETED SUCCESSFULLY"
            for char in out_str:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
            return intro + out_str, 350

        elif self.ant_type == AntType.MY_OWN_AI:
            intro = f"Adapting response to user's personalized cognitive style for: '{last_user_msg}'...\n\n"
            for char in intro:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            
            pers_res = await self._dispatch_tool("personalize_response", {"text": f"Analyzing and answering query: {last_user_msg}", "style": "creative"})
            
            out_str = f"{pers_res}\n\nResponse personalized to user cognitive profile."
            for char in out_str:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.005)
            return intro + out_str, 300

        else:
            fallback = f"Mock response from {self.ant_type} for task: '{last_user_msg}'"
            for char in fallback:
                await self._emit(WSMessageType.ANT_STREAMING, content=char)
                await asyncio.sleep(0.01)
            return fallback, 100
