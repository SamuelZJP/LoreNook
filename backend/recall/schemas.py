from backend.schemas.common import Contract, NonnegativeInt
from backend.schemas.memory import ChatMemory, MemoryLayout
from backend.schemas.models import ModelConnection

DEFAULT_DEPTH = 3
DEFAULT_EPISODE_LIMIT = 2
DEFAULT_SUMMARY_LIMIT = 5


class RecallSettings(Contract):
    enabled: bool = False
    model_config_id: str | None = None
    # How many latest complete rounds, with the latest input, form the recall basis.
    depth: NonnegativeInt = DEFAULT_DEPTH
    # At most this many expansions per pass. Stated in the prompt, then enforced on the result.
    episode_limit: NonnegativeInt = DEFAULT_EPISODE_LIMIT
    summary_limit: NonnegativeInt = DEFAULT_SUMMARY_LIMIT


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
