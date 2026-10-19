from datetime import datetime
from typing import Literal

from backend.schemas.chats import StateRead
from backend.schemas.common import Contract, Name
from backend.schemas.episode_summary import EpisodeRead

PendingStep = Literal["state_update", "round_summary", "episode_decision", "episode_summary"]
ArchiveStep = Literal["state_update", "round_summary", "episode_decision", "episode_summary", "complete"]


class ArchiveConfirm(Contract):
    user_input: str
    ai_output: Name
    based_on_round_id: str | None


class ArchiveRetry(Contract):
    expected_step: PendingStep


class RoundRead(Contract):
    id: str
    chat_id: str
    round_no: int
    user_input: str
    ai_output: str
    summary: str | None
    archive_step: ArchiveStep
    archive_error: str | None
    episode_required: bool | None
    episode_start_round_id: str | None
    episode_end_round_id: str | None
    created_at: datetime


class ArchiveProgress(Contract):
    round: RoundRead
    state: StateRead | None
    episode: EpisodeRead | None
