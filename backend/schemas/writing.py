from typing import Literal

from backend.schemas.common import Contract, Name


class WritingInput(Contract):
    user_input: str


class WritingResult(Contract):
    chat_id: str
    preset_id: str
    model_config_id: str
    state_snapshot_id: str
    based_on_round_id: str | None
    status: Literal["awaiting_confirmation"] = "awaiting_confirmation"
    user_input: str
    ai_output: Name
