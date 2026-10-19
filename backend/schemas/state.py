from pydantic import JsonValue

from backend.schemas.common import Contract, NonnegativeInt
from backend.schemas.chats import StateRead
from backend.schemas.models import ModelConnection


class StateReplace(Contract):
    content: dict[str, JsonValue]


class StateUpdateResult(Contract):
    chat_id: str
    round_id: str
    archive_step: str
    state: StateRead
    skipped_operations: NonnegativeInt


class StateUpdateContext(Contract):
    chat_id: str
    round_id: str
    round_no: int
    user_input: str
    ai_output: str
    state_snapshot_id: str
    state: dict[str, JsonValue]
    schema_source: str
    reference: str
    update_rules: str
    user_name: str
    summaries: list[str]
    connection: ModelConnection
