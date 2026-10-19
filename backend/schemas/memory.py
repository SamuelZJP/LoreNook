"""Database-independent contracts for selecting chronological history."""

from typing import Annotated, Literal

from pydantic import Field, computed_field

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


class FullRoundMemory(Contract):
    kind: Literal["round"] = "round"
    id: str
    round_no: PositiveInt
    user_input: str
    ai_output: str


MemoryItem = Annotated[
    EpisodeMemory | RoundSummaryMemory | FullRoundMemory, Field(discriminator="kind")
]


class MemoryHistory(MemorySettings):
    total_rounds: NonnegativeInt
    items: list[MemoryItem]

    @computed_field
    @property
    def uses_compressed_history(self) -> bool:
        """A preset can use this to decide whether to include First Message."""
        return any(item.kind != "round" for item in self.items)


class ChatMemory(MemoryHistory):
    chat_id: str
