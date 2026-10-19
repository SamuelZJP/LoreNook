from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue

from backend.schemas.common import Contract, Name
from backend.schemas.models import ModelConnection


class EpisodeReplace(Contract):
    summary: Name
    title: Annotated[Name, Field(max_length=20)] | None = None


class GeneratedEpisode(Contract):
    title: Annotated[Name, Field(max_length=20)]
    summary: Name


class EpisodeRead(Contract):
    id: str
    chat_id: str
    start_round_id: str
    end_round_id: str
    summary: Name
    title: str = ""
    created_by_round_id: str | None
    created_at: datetime


class EpisodeSummaryResult(Contract):
    chat_id: str
    round_id: str
    archive_step: Literal["complete"] = "complete"
    episode: EpisodeRead


class EpisodeSourceRound(Contract):
    id: str
    round_no: int
    summary: str
    user_input: str
    ai_output: str
    state_snapshot_id: str
    state: dict[str, JsonValue]


class EpisodeBridgeRound(Contract):
    id: str
    round_no: int
    summary: str
    user_input: str
    ai_output: str


class EpisodeSummaryContext(Contract):
    chat_id: str
    round_id: str
    start_round_id: str
    end_round_id: str
    character_name: str
    user_name: str
    rounds: list[EpisodeSourceRound]
    first_message: str | None = None
    bridge: EpisodeBridgeRound | None = None
    connection: ModelConnection
