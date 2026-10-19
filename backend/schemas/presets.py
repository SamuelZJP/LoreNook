from datetime import datetime

from pydantic import Field, JsonValue, computed_field
import yaml

from backend.schemas.common import Contract, Name, PatchContract
from backend.schemas.definitions import ResolvedDefinition
from backend.schemas.memory import MemoryHistory


class PresetCreate(Contract):
    name: Name
    source: str


class PresetPatch(PatchContract):
    name: Name | None = None
    source: str | None = None


class PresetRead(Contract):
    id: str
    chat_id: str | None
    name: str
    source: str
    created_at: datetime


class WritingMaterials(Contract):
    first_message: str
    character_name: str
    user_identity_name: str
    character_definitions: list[ResolvedDefinition] = Field(default_factory=list)
    user_definitions: list[ResolvedDefinition] = Field(default_factory=list)
    history: MemoryHistory
    user_input: str
    state: dict[str, JsonValue]

    @computed_field
    @property
    def state_yaml(self) -> str:
        return yaml.safe_dump(self.state, allow_unicode=True, sort_keys=False)


class BuiltRequest(Contract):
    api_type: Name
    body: dict[str, JsonValue]


class ParseInput(Contract):
    response: dict[str, JsonValue]


class ParsedOutput(Contract):
    ai_output: Name


class WritingPreviewInput(Contract):
    user_input: str


class WritingPreview(Contract):
    chat_id: str
    preset_id: str
    state_snapshot_id: str
    request: BuiltRequest
