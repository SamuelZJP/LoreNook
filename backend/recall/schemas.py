from backend.schemas.common import Contract, NonnegativeInt
from backend.schemas.memory import ChatMemory, MemoryLayout
from backend.schemas.models import ModelConnection

DEFAULT_DEPTH = 3


class RecallSettings(Contract):
    model_config_id: str | None = None
    # How many latest complete rounds, with the latest input, form the recall basis.
    depth: NonnegativeInt = DEFAULT_DEPTH


class RecallInput(Contract):
    user_input: str
    instruction: str = ""


class RecallResult(Contract):
    """`layout` goes back with the writing request; `timeline` is what the memory panel shows meanwhile."""
    layout: MemoryLayout
    timeline: ChatMemory


class RecallContext(Contract):
    character_name: str
    user_name: str
    basis_rounds: list[str]
    user_input: str
    instruction: str
    connection: ModelConnection
