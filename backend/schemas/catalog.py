from datetime import datetime

from pydantic import Field

from backend.schemas.common import Contract, Name, NonnegativeInt, PatchContract


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


class CharacterCreate(IdentityCreate):
    first_message: str = ""
    state_schema: str = ""
    state_reference: str = ""
    state_update_rules: str = ""


class CharacterPatch(IdentityPatch):
    first_message: str | None = None
    state_schema: str | None = None
    state_reference: str | None = None
    state_update_rules: str | None = None


class CharacterRead(CharacterCreate):
    id: str
    chat_id: str | None
    created_at: datetime
    definitions: list[DefinitionRead]
