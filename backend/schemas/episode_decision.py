from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from backend.schemas.common import Contract

PositiveInt = Annotated[int, Field(ge=1)]


class EpisodeCandidate(Contract):
    id: str
    round_no: PositiveInt


class EpisodeDecisionContext(Contract):
    current_round_id: str
    candidates: list[EpisodeCandidate]
    dates: dict[str, JsonValue] = Field(default_factory=dict)


class EpisodeDecision(Contract):
    episode_required: bool
    start_round_id: str | None = None
    end_round_id: str | None = None
    start_round_no: PositiveInt | None = None
    end_round_no: PositiveInt | None = None

    @model_validator(mode="after")
    def check_range(self):
        values = (self.start_round_id, self.end_round_id, self.start_round_no, self.end_round_no)
        if self.episode_required:
            if any(value is None for value in values) or self.start_round_no > self.end_round_no:
                raise ValueError("需要情节时必须提供完整且有序的范围")
        elif any(value is not None for value in values):
            raise ValueError("无需情节时范围必须为空")
        return self


class EpisodeDecisionResult(EpisodeDecision):
    chat_id: str
    round_id: str
    archive_step: Literal["complete", "episode_summary"]

    @model_validator(mode="after")
    def check_step(self):
        if self.archive_step != ("episode_summary" if self.episode_required else "complete"):
            raise ValueError("判定结果与归档步骤不一致")
        return self
