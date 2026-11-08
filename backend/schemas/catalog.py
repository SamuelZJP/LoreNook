from datetime import datetime
from typing import Annotated

from pydantic import Field, JsonValue

from backend.schemas.common import Contract, Name, NonnegativeInt, PatchContract, StateScriptHistory


class DefinitionInput(Contract):
    order: NonnegativeInt = 0
    enabled: bool = True
    has_template: bool = False
    content: str


class DefinitionRead(DefinitionInput):
    id: str
    character_id: str | None
    user_identity_id: str | None


class IdentityCreate(Contract):
    name: Name
    avatar: str | None = None
    description: str = ""
    definitions: list[DefinitionInput] = Field(default_factory=list)


class IdentityPatch(PatchContract):
    nullable_fields = frozenset({"avatar"})
    name: Name | None = None
    avatar: str | None = None
    description: str | None = None
    definitions: list[DefinitionInput] | None = None


class IdentityRead(IdentityCreate):
    id: str
    chat_id: str | None
    created_at: datetime
    definitions: list[DefinitionRead]


class SceneInput(Contract):
    order: NonnegativeInt = 0
    name: Name
    description: str = ""
    first_message: str = ""
    # Partial state; the character's Schema fills defaults and validates the result.
    initial_state: dict[str, JsonValue] = Field(default_factory=dict)


class SceneRead(SceneInput):
    id: str
    character_id: str


Scenes = Annotated[list[SceneInput], Field(min_length=1)]


class CharacterCreate(IdentityCreate):
    scenes: Scenes = Field(default_factory=lambda: [SceneInput(name="默认")])
    state_schema: str = ""
    state_reference: str = ""
    state_update_rules: str = ""
    state_script: str = ""
    state_script_history: StateScriptHistory = 0


class CharacterPatch(IdentityPatch):
    scenes: Scenes | None = None
    state_schema: str | None = None
    state_reference: str | None = None
    state_update_rules: str | None = None
    state_script: str | None = None
    state_script_history: StateScriptHistory | None = None


class CharacterRead(CharacterCreate):
    id: str
    chat_id: str | None
    created_at: datetime
    definitions: list[DefinitionRead]
    scenes: list[SceneRead]


class InitialStatePreview(Contract):
    state_schema: str = ""
    initial_state: dict[str, JsonValue] = Field(default_factory=dict)
