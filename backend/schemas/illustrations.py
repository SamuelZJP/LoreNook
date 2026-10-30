from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator

from backend.modules.illustrations.workflow import validate_workflow
from backend.schemas.catalog import DefinitionRead
from backend.schemas.common import Contract, Name, PatchContract
from backend.schemas.models import ModelConnection, validate_base_url

IllustrationMode = Literal["off", "every_round", "scene_change", "manual"]
IllustrationStatus = Literal["pending", "prompting", "rendering", "ready", "failed"]
ACTIVE_STATUSES = ("pending", "prompting", "rendering")
ImageSize = Annotated[int, Field(ge=64, le=8192)]


class ImageWorkflowCreate(Contract):
    name: Name
    base_url: str
    workflow: dict[str, JsonValue]
    # Prompt style for the image-prompt model: language, tag format, what each field holds.
    instructions: str = ""
    width: ImageSize = 1344
    height: ImageSize = 768

    @field_validator("base_url")
    @classmethod
    def check_url(cls, value):
        return validate_base_url(value)

    @field_validator("workflow")
    @classmethod
    def check_workflow(cls, value):
        return validate_workflow(value)


class ImageWorkflowPatch(PatchContract):
    name: Name | None = None
    base_url: str | None = None
    workflow: dict[str, JsonValue] | None = None
    instructions: str | None = None
    width: ImageSize | None = None
    height: ImageSize | None = None

    @field_validator("base_url")
    @classmethod
    def check_url(cls, value):
        return validate_base_url(value) if value is not None else value

    @field_validator("workflow")
    @classmethod
    def check_workflow(cls, value):
        return validate_workflow(value) if value is not None else value


class ImageWorkflowRead(Contract):
    id: str
    chat_id: str | None
    name: str
    base_url: str
    workflow: dict[str, JsonValue]
    instructions: str
    width: int
    height: int
    prompt_fields: list[str]
    created_at: datetime


class IllustrationSettings(Contract):
    mode: IllustrationMode = "off"
    image_workflow_id: str | None = None
    # Model config that turns the round into the workflow's prompt fields.
    model_config_id: str | None = None


class IllustrationRead(Contract):
    id: str
    chat_id: str
    round_id: str
    status: IllustrationStatus
    seed: int
    prompt: dict[str, JsonValue] | None
    error: str | None
    media_type: str | None
    width: int
    height: int
    hidden: bool
    created_at: datetime


class IllustrationPatch(PatchContract):
    hidden: bool | None = None


class IllustrationPrompt(Contract):
    image_workflow_id: str
    fields: dict[str, str]


class IllustrationContext(Contract):
    """Everything one generation reads, captured in a single database read."""
    chat_id: str
    round_id: str
    round_no: int
    user_input: str
    ai_output: str
    summary: str | None
    state: dict[str, JsonValue]
    character_name: str
    user_name: str
    character_definitions: list[DefinitionRead]
    user_definitions: list[DefinitionRead]
    image_workflow_id: str
    base_url: str
    workflow: dict[str, JsonValue]
    instructions: str
    width: int
    height: int
    fields: list[str]
    connection: ModelConnection
