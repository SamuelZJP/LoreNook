from datetime import datetime

from pydantic import Field, JsonValue

from backend.schemas.chats import ModelPurpose
from backend.schemas.common import Contract, Name, NonnegativeInt, PatchContract


class ChatTemplateSettings(Contract):
    """The new-chat form's parameters; field names match `ChatCreate`."""
    writing_preset_id: str | None = None
    writing_preset_ids: list[str] = Field(default_factory=list)
    model_config_ids: list[str] = Field(default_factory=list)
    model_bindings: dict[ModelPurpose, str] = Field(default_factory=dict)
    recent_rounds: NonnegativeInt = 5
    min_summaries: NonnegativeInt = 6
    # One entry per optional feature, written and read only by that feature's new-chat section.
    features: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


class ChatTemplateCreate(Contract):
    name: Name
    is_default: bool = False
    settings: ChatTemplateSettings = Field(default_factory=ChatTemplateSettings)


class ChatTemplatePatch(PatchContract):
    name: Name | None = None
    is_default: bool | None = None
    settings: ChatTemplateSettings | None = None


class ChatTemplateRead(Contract):
    id: str
    name: str
    is_default: bool
    settings: ChatTemplateSettings
    created_at: datetime
