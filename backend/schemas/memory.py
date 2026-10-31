"""Contracts of the memory pipeline: sources -> layout (numbers) -> rendered output."""

from typing import Annotated, Literal

from pydantic import Field

from backend.schemas.common import Contract, NonnegativeInt

PositiveInt = Annotated[int, Field(ge=1)]


class MemorySettings(Contract):
    recent_rounds: NonnegativeInt
    min_summaries: NonnegativeInt


class ArchivedRound(Contract):
    id: str
    round_no: PositiveInt
    user_input: str
    ai_output: str
    summary: str | None
    world: dict | None = None  # `世界` of the state this round ended in


class EpisodeMemory(Contract):
    kind: Literal["episode"] = "episode"
    id: str
    start_round_id: str
    end_round_id: str
    start_round_no: PositiveInt
    end_round_no: PositiveInt
    summary: str
    title: str = ""


class RoundSummaryMemory(Contract):
    kind: Literal["summary"] = "summary"
    id: str
    round_no: PositiveInt
    summary: str


class RecentRound(Contract):
    id: str
    round_no: PositiveInt
    user_input: str
    ai_output: str


class FullRoundMemory(RecentRound):
    kind: Literal["round"] = "round"


MemoryItem = Annotated[
    EpisodeMemory | RoundSummaryMemory | FullRoundMemory, Field(discriminator="kind")
]


class MemorySegment(Contract):
    """A run of same-kind entries. `numbers` are episode positions or round numbers."""
    kind: Literal["episode", "summary", "round"]
    numbers: list[PositiveInt]


class MemoryLayout(Contract):
    """The decided shape of history, with no text: `memory` in story order, then the full recent rounds."""
    memory: list[MemorySegment]
    recent_rounds: list[PositiveInt]


class MemoryMaterials(Contract):
    """What a writing preset receives. `memory` has no tags; the preset defines its own."""
    memory: str
    recent_rounds: list[RecentRound]


class MemoryTimeline(MemorySettings):
    """What the memory panel shows."""
    total_rounds: NonnegativeInt
    items: list[MemoryItem]


class ChatMemory(MemoryTimeline):
    chat_id: str
