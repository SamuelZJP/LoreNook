from typing import Literal

from pydantic import JsonValue

from backend.schemas.common import Contract, Name
from backend.schemas.models import ModelConnection


class RoundSummaryReplace(Contract):
    summary: Name


class RoundSummaryRead(Contract):
    chat_id: str
    round_id: str
    summary: Name


class RoundSummaryResult(RoundSummaryRead):
    archive_step: Literal["episode_decision"] = "episode_decision"


class RoundSummaryContext(Contract):
    chat_id: str
    round_id: str
    round_no: int
    user_input: str
    ai_output: str
    state_snapshot_id: str
    state: dict[str, JsonValue]
    character_name: str
    user_name: str
    summaries: list[str]
    connection: ModelConnection
