"""Raw table contracts: preserve source and state, validate storage types only."""

import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AwareDatetime, BeforeValidator, Field, JsonValue, TypeAdapter

from backend.schemas.archive import ArchiveStep
from backend.schemas.chat_templates import ChatTemplateSettings
from backend.schemas.chats import ModelPurpose
from backend.schemas.common import Contract, Name, NonnegativeInt
from backend.schemas.models import DEFAULT_TIMEOUT_SECONDS, TimeoutSeconds

# Any registered table; data management rejects the rest.
TableName = Name
RecordId = Annotated[Name, Field(max_length=36)]


def _timestamp(value):
    if isinstance(value, str):
        return TypeAdapter(AwareDatetime).validate_json(json.dumps(value), strict=True)
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(_timestamp)]


class IdentifiedRow(Contract):
    id: RecordId = Field(default_factory=lambda: str(uuid4()))


class TimestampedRow(IdentifiedRow):
    created_at: Timestamp = Field(default_factory=lambda: datetime.now(UTC))


class ChatRow(TimestampedRow):
    title: Name
    writing_preset_id: RecordId | None = None
    recent_rounds: NonnegativeInt = 5
    min_summaries: NonnegativeInt = 6


class IdentityRow(TimestampedRow):
    chat_id: RecordId | None = None
    name: Name
    avatar: str | None = None
    description: str = ""


class CharacterRow(IdentityRow):
    state_schema: str = ""
    state_reference: str = ""
    state_update_rules: str = ""


class SceneRow(IdentifiedRow):
    character_id: RecordId
    order: NonnegativeInt = 0
    name: Name
    description: str = ""
    first_message: str = ""
    initial_state: dict[str, JsonValue] = Field(default_factory=dict)


class DefinitionRow(IdentifiedRow):
    character_id: RecordId | None = None
    user_identity_id: RecordId | None = None
    order: NonnegativeInt = 0
    enabled: bool = True
    has_template: bool = False
    content: str


class PresetRow(TimestampedRow):
    chat_id: RecordId | None = None
    name: Name
    source: str


class ModelRow(IdentifiedRow):
    chat_id: RecordId | None = None
    name: Name
    api_type: str
    base_url: str
    api_key: str = ""
    model: str
    default_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    timeout_seconds: TimeoutSeconds = DEFAULT_TIMEOUT_SECONDS


class BindingRow(Contract):
    chat_id: RecordId
    purpose: ModelPurpose
    model_config_id: RecordId


class RoundRow(TimestampedRow):
    chat_id: RecordId
    round_no: Annotated[int, Field(ge=1)]
    user_input: str
    ai_output: str
    summary: Name | None = None
    archive_step: ArchiveStep = "state_update"
    archive_error: str | None = None
    episode_required: bool | None = None
    episode_start_round_id: RecordId | None = None
    episode_end_round_id: RecordId | None = None


class StateRow(TimestampedRow):
    chat_id: RecordId
    character_id: RecordId
    round_id: RecordId | None = None
    content: dict[str, JsonValue]


class EpisodeRow(TimestampedRow):
    title: str = ""
    chat_id: RecordId
    start_round_id: RecordId
    end_round_id: RecordId
    summary: Name
    created_by_round_id: RecordId | None = None


class ChatTemplateRow(TimestampedRow):
    name: Name
    is_default: bool = False
    settings: ChatTemplateSettings = Field(default_factory=ChatTemplateSettings)


class AdminCreate(Contract):
    action: Literal["create"]
    table: TableName
    values: dict[str, JsonValue]


class AdminUpdate(Contract):
    action: Literal["update"]
    table: TableName
    key: dict[str, str]
    values: dict[str, JsonValue]


class AdminDelete(Contract):
    action: Literal["delete"]
    table: TableName
    key: dict[str, str]


AdminOperation = Annotated[AdminCreate | AdminUpdate | AdminDelete, Field(discriminator="action")]


class AdminBatch(Contract):
    expected_revision: Name
    operations: Annotated[list[AdminOperation], Field(min_length=1)]


class AdminSnapshot(Contract):
    revision: str
    tables: dict[str, list[dict[str, JsonValue]]]


class AdminChange(Contract):
    action: Literal["create", "update", "delete"]
    table: TableName
    key: dict[str, str]


class AdminBatchResult(Contract):
    revision: str
    changes: list[AdminChange]


class AdminTableInfo(Contract):
    name: TableName
    primary_key: list[str]
    row_schema: dict[str, JsonValue]


ROW_SCHEMAS = {
    "chats": ChatRow, "characters": CharacterRow, "character_scenes": SceneRow, "user_identities": IdentityRow,
    "definitions": DefinitionRow, "writing_presets": PresetRow, "model_configs": ModelRow,
    "chat_model_bindings": BindingRow, "rounds": RoundRow, "state_snapshots": StateRow, "episodes": EpisodeRow,
    "chat_templates": ChatTemplateRow,
}
