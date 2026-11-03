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


class RoundScene(Contract):
    """When and where a round ended, from `世界` of its state. Missing or non-text fields are empty."""
    date: str = ""
    time: str = ""
    place: str = ""

    @classmethod
    def from_world(cls, world: object) -> "RoundScene | None":
        if not isinstance(world, dict):
            return None
        def text(key: str) -> str:
            value = world.get(key)
            return value if isinstance(value, str) else ""
        return cls(date=text("日期"), time=text("时间"), place=text("地点"))


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
    # Absent until the round's state update has run.
    scene: RoundScene | None = None

    @classmethod
    def of(cls, record, world: object) -> "RoundRead":
        return cls.model_validate(record).model_copy(update={"scene": RoundScene.from_world(world)})


class ArchiveProgress(Contract):
    round: RoundRead
    state: StateRead | None
    episode: EpisodeRead | None
