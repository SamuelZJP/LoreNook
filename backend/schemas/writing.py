from typing import Literal

from backend.schemas.common import Contract, Name
from backend.schemas.memory import MemoryLayout


class WritingInput(Contract):
    user_input: str
    instruction: str = ""
    # Replaces the assembled memory layout for this request.
    layout: MemoryLayout | None = None


class WritingResult(Contract):
    chat_id: str
    preset_id: str
    model_config_id: str
    state_snapshot_id: str
    based_on_round_id: str | None
    status: Literal["awaiting_confirmation"] = "awaiting_confirmation"
    user_input: str
    ai_output: Name
