from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from backend.schemas.catalog import CharacterRead, IdentityRead
from backend.schemas.common import Contract, Name, NonnegativeInt, PatchContract
from backend.schemas.presets import PresetRead
from backend.schemas.models import ModelConfigRead

ModelPurpose = Literal["writing", "state_update", "round_summary", "episode_summary"]


class ChatCreate(Contract):
    title: Name
    character_id: str
    # None selects the character's first scene.
    scene_id: str | None = None
    user_identity_id: str
    writing_preset_ids: list[str] = Field(default_factory=list)
    writing_preset_id: str | None = None
    model_config_ids: list[str] = Field(default_factory=list)
    model_bindings: dict[ModelPurpose, str] = Field(default_factory=dict)
    recent_rounds: NonnegativeInt = 5
    min_summaries: NonnegativeInt = 6


class ChatPatch(PatchContract):
    nullable_fields = frozenset({"writing_preset_id"})
    title: Name | None = None
    recent_rounds: NonnegativeInt | None = None
    min_summaries: NonnegativeInt | None = None
    writing_preset_id: str | None = None
    model_bindings: dict[ModelPurpose, str] | None = None


class ChatRead(Contract):
    id: str
    title: str
    writing_preset_id: str | None
    recent_rounds: int
    min_summaries: int
    created_at: datetime


class ChatListItem(ChatRead):
    # The chat's own character avatar.
    avatar: str | None = None


class StateRead(Contract):
    id: str
    character_id: str
    round_id: str | None
    content: dict[str, JsonValue]
    created_at: datetime


class ChatDetail(ChatRead):
    character: CharacterRead
    user_identity: IdentityRead
    writing_presets: list[PresetRead]
    model_configs: list[ModelConfigRead]
    model_bindings: dict[ModelPurpose, str]
    latest_state: StateRead
