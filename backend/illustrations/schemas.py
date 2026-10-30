from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator

from backend.illustrations.placeholders import validate_workflow
from backend.illustrations.templates import validate_template
from backend.schemas.catalog import DefinitionRead
from backend.schemas.common import Contract, Name, PatchContract
from backend.schemas.models import ModelConnection, validate_base_url

IllustrationMode = Literal["off", "every_round", "scene_change", "manual"]
IllustrationStatus = Literal["pending", "prompting", "rendering", "ready", "failed"]
ACTIVE_STATUSES = ("pending", "prompting", "rendering")
ImageSize = Annotated[int, Field(ge=64, le=8192)]
# A main character is a cast member id, or one of these two.
FOCUS_CHAR, FOCUS_USER = "char", "user"


class ImageWorkflowCreate(Contract):
    name: Name
    base_url: str
    workflow: dict[str, JsonValue]
    # Empty selects the default template for the workflow's kind.
    prompt_template: str = ""
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

    @field_validator("prompt_template")
    @classmethod
    def check_template(cls, value):
        return validate_template(value)


class ImageWorkflowPatch(PatchContract):
    name: Name | None = None
    base_url: str | None = None
    workflow: dict[str, JsonValue] | None = None
    prompt_template: str | None = None
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

    @field_validator("prompt_template")
    @classmethod
    def check_template(cls, value):
        return validate_template(value) if value is not None else value


class ImageWorkflowRead(Contract):
    id: str
    chat_id: str | None
    name: str
    base_url: str
    workflow: dict[str, JsonValue]
    prompt_template: str
    width: int
    height: int
    prompt_fields: list[str]
    # Non-empty means image-to-image.
    image_inputs: list[str]
    created_at: datetime


class ImageWorkflowImport(Contract):
    source_id: str


class DefaultTemplates(Contract):
    text_to_image: str
    image_to_image: str


class IllustrationSettings(Contract):
    mode: IllustrationMode = "off"
    image_workflow_id: str | None = None
    # Model config that turns the round into the workflow's prompt fields.
    model_config_id: str | None = None
    # Main characters; empty means the default. More than two is allowed, the UI warns.
    focus: list[str] = Field(default_factory=list)


class IllustrationSetup(Contract):
    """Library resources for a new chat; the workflow and model config are copied into it."""
    mode: IllustrationMode
    image_workflow_id: str | None = None
    model_config_id: str | None = None


class CastMemberInput(Contract):
    # Present for an existing member, so choices that point at it survive edits.
    id: str | None = None
    name: Name
    appearance: str = ""
    reference_image: str | None = None


class CastMemberRead(Contract):
    id: str
    name: str
    appearance: str
    reference_image: str | None


class CastReplace(Contract):
    members: list[CastMemberInput]


class AppearanceInput(Contract):
    appearance: str = ""
    reference_image: str | None = None


class FocusOption(Contract):
    id: str
    name: str
    has_reference: bool


class FocusOptions(Contract):
    """Everyone who can be a main character in this chat, and who is the current default."""
    options: list[FocusOption]
    default: list[str]


class IllustrationRequest(Contract):
    # Main characters for this attempt only; absent means the chat's choice.
    focus: list[str] | None = None


class IllustrationRead(Contract):
    id: str
    chat_id: str
    round_id: str
    status: IllustrationStatus
    seed: int
    focus: list[dict[str, JsonValue]]
    prompt: dict[str, JsonValue] | None
    error: str | None
    media_type: str | None
    width: int
    height: int
    hidden: bool
    created_at: datetime


class IllustrationProgress(Contract):
    """A running job's live state. Kept in memory only, never in the database."""
    status: IllustrationStatus
    queued: bool = False
    node: str | None = None
    value: int | None = None
    max: int | None = None


class IllustrationPatch(PatchContract):
    hidden: bool | None = None


class IllustrationPrompt(Contract):
    image_workflow_id: str
    focus: list[str]
    fields: dict[str, str]


class Subject(Contract):
    id: str
    name: str
    appearance: str = ""
    reference_image: str | None = None


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
    focus: list[Subject]
    others: list[Subject]
    image_workflow_id: str
    base_url: str
    workflow: dict[str, JsonValue]
    prompt_template: str
    width: int
    height: int
    fields: list[str]
    image_inputs: list[str]
    connection: ModelConnection
