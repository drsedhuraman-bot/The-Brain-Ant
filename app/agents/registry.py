from __future__ import annotations
from collections.abc import Callable, Awaitable
from anthropic import AsyncAnthropic
from .base import BaseAnt
from .research_ant import ResearchAnt
from .coder_ant import CoderAnt
from .writer_ant import WriterAnt
from .analyst_ant import AnalystAnt
from .ruflo_ant import RufloAnt
from .ecc_ant import EccAnt
from .my_own_ai_ant import MyOwnAiAnt
from ..models.domain import AntType
from ..models.api import WSMessage


class AntRegistry:
    """Factory for all Ant worker types."""

    _registry: dict[AntType, type[BaseAnt]] = {
        AntType.RESEARCH: ResearchAnt,
        AntType.CODER: CoderAnt,
        AntType.WRITER: WriterAnt,
        AntType.ANALYST: AnalystAnt,
        AntType.RUFLO: RufloAnt,
        AntType.ECC: EccAnt,
        AntType.MY_OWN_AI: MyOwnAiAnt,
    }

    def __init__(self, client: AsyncAnthropic):
        self.client = client

    def create(
        self,
        ant_type: AntType,
        stream_callback: Callable[[WSMessage], Awaitable[None]] | None = None,
    ) -> BaseAnt:
        cls = self._registry.get(ant_type)
        if cls is None:
            raise ValueError(f"Unknown ant type: {ant_type}")
        return cls(client=self.client, stream_callback=stream_callback)

    def available_ants(self) -> list[AntType]:
        return list(self._registry.keys())
