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
