"""Scoped definition management. The caller owns the transaction."""

from __future__ import annotations

from backend.repository.models import Character, Definition, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionInput, DefinitionRead
from backend.schemas.definitions import DefinitionPatch, DefinitionReorder
from backend.shared.errors import ConflictError, NotFoundError


class DefinitionService:
    def __init__(
        self, repository: Repository, *, character_id: str | None = None,
        user_identity_id: str | None = None, chat_id: str | None = None,
    ):
        if (character_id is None) == (user_identity_id is None):
            raise ValueError("Provide exactly one definition owner")
        self.repository = repository
        self.character_id = character_id
        self.user_identity_id = user_identity_id
        if character_id is not None:
            repository.get_owned(Character, character_id, chat_id)
        else:
            repository.get_owned(UserIdentity, user_identity_id, chat_id)

    def _records(self) -> list[Definition]:
        return self.repository.definitions(character_id=self.character_id, user_identity_id=self.user_identity_id)

    def _get(self, definition_id: str) -> Definition:
        record = self.repository.get(Definition, definition_id)
        if record.character_id != self.character_id or record.user_identity_id != self.user_identity_id:
            raise NotFoundError(f"Definition {definition_id!r} does not exist in this scope")
        return record

    def list(self) -> list[DefinitionRead]:
        return [DefinitionRead.model_validate(record) for record in self._records()]

    def read(self, definition_id: str) -> DefinitionRead:
        return DefinitionRead.model_validate(self._get(definition_id))

    def create(self, payload: DefinitionInput) -> DefinitionRead:
        record = self.repository.add(Definition(
            character_id=self.character_id, user_identity_id=self.user_identity_id,
            **payload.model_dump(include=set(DefinitionInput.model_fields)),
        ))
        return DefinitionRead.model_validate(record)

    def update(self, definition_id: str, payload: DefinitionPatch) -> DefinitionRead:
        record = self._get(definition_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        self.repository.session.flush()
        return DefinitionRead.model_validate(record)

    def delete(self, definition_id: str) -> None:
        self.repository.delete(self._get(definition_id))

    def reorder(self, payload: DefinitionReorder) -> list[DefinitionRead]:
        records = {record.id: record for record in self._records()}
        if set(payload.definition_ids) != set(records):
            raise ConflictError("排序列表必须包含当前归属的全部定义，且每条恰好出现一次")
        for order, definition_id in enumerate(payload.definition_ids):
            records[definition_id].order = order
        self.repository.session.flush()
        return self.list()
