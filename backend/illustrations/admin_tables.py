"""The illustration tables as data management sees them: storage types only."""

from typing import Annotated

from pydantic import Field, JsonValue

from backend.illustrations.models import CastMember, ChatIllustrationSettings, IdentityAppearance, Illustration, ImageWorkflow
from backend.illustrations.schemas import IllustrationMode, IllustrationStatus, ImageSize
from backend.modules.admin.registry import register_table
from backend.schemas.admin import IdentifiedRow, OwnedRow, RecordId, TimestampedRow
from backend.schemas.common import Contract, Name, NonnegativeInt


class ImageWorkflowRow(OwnedRow, TimestampedRow):
    chat_id: RecordId | None = None
    name: Name
    base_url: str
    workflow: dict[str, JsonValue]
    width: ImageSize = 1344
    height: ImageSize = 768


class IllustrationSettingsRow(Contract):
    chat_id: RecordId
    mode: IllustrationMode = "off"
    image_workflow_id: RecordId | None = None
    focus: list[str] = Field(default_factory=list)


class CastMemberRow(IdentifiedRow):
    character_id: RecordId
    order: NonnegativeInt = 0
    name: Name
    appearance: str = ""
    reference_image: str | None = None


class IdentityAppearanceRow(Contract):
    user_identity_id: RecordId
    appearance: str = ""
    reference_image: str | None = None


class IllustrationRow(TimestampedRow):
    chat_id: RecordId
    round_id: RecordId
    status: IllustrationStatus = "pending"
    seed: Annotated[int, Field(ge=0)]
    focus: list[dict[str, JsonValue]] = Field(default_factory=list)
    prompt: dict[str, JsonValue] | None = None
    error: str | None = None
    file_name: str | None = None
    media_type: str | None = None
    width: ImageSize
    height: ImageSize
    hidden: bool = False


def register_admin_tables() -> None:
    for model, row_schema in ((ImageWorkflow, ImageWorkflowRow), (ChatIllustrationSettings, IllustrationSettingsRow),
                              (CastMember, CastMemberRow), (IdentityAppearance, IdentityAppearanceRow),
                              (Illustration, IllustrationRow)):
        register_table(model, row_schema)
