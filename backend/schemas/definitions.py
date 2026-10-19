from pydantic import Field, model_validator

from backend.schemas.common import Contract, NonnegativeInt, PatchContract


class DefinitionPatch(PatchContract):
    order: NonnegativeInt | None = None
    enabled: bool | None = None
    has_template: bool | None = None
    content: str | None = None


class DefinitionReorder(Contract):
    definition_ids: list[str]

    @model_validator(mode="after")
    def reject_duplicate_ids(self):
        if len(self.definition_ids) != len(set(self.definition_ids)):
            raise ValueError("Each definition ID must appear exactly once")
        return self


class ResolvedDefinition(Contract):
    id: str
    order: int
    content: str


class ResolvedDefinitions(Contract):
    character_definitions: list[ResolvedDefinition] = Field(default_factory=list)
    user_definitions: list[ResolvedDefinition] = Field(default_factory=list)


class ChatResolvedDefinitions(ResolvedDefinitions):
    chat_id: str
    state_snapshot_id: str
