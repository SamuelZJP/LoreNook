from backend.modules.definitions.storage import DefinitionStorage
from backend.repository.models import UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import IdentityCreate, IdentityPatch, IdentityRead


class IdentityService:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.definitions = DefinitionStorage(repository)

    def read(self, identity_id: str, chat_id: str | None = None) -> IdentityRead:
        return self._read(self.repository.get_owned(UserIdentity, identity_id, chat_id))

    def _read(self, record: UserIdentity) -> IdentityRead:
        fields = {name: getattr(record, name) for name in IdentityRead.model_fields if name != "definitions"}
        return IdentityRead(**fields, definitions=self.definitions.read(user_identity_id=record.id))

    def list_library(self) -> list[IdentityRead]:
        return [self._read(record) for record in self.repository.list_owned(UserIdentity, None)]

    def create(self, payload: IdentityCreate, chat_id: str | None = None) -> IdentityRead:
        record = self.repository.add(UserIdentity(chat_id=chat_id, **payload.model_dump(exclude={"definitions"})))
        self.definitions.replace(payload.definitions, user_identity_id=record.id)
        return self._read(record)

    def update(self, identity_id: str, payload: IdentityPatch, chat_id: str | None = None) -> IdentityRead:
        record = self.repository.get_owned(UserIdentity, identity_id, chat_id)
        for name, value in payload.model_dump(exclude_unset=True, exclude={"definitions"}).items():
            setattr(record, name, value)
        if "definitions" in payload.model_fields_set:
            self.definitions.replace(payload.definitions, user_identity_id=record.id)
        self.repository.session.flush()
        return self._read(record)

    def delete_source(self, identity_id: str) -> None:
        self.repository.delete(self.repository.get_owned(UserIdentity, identity_id, None))

    def copy_to_chat(self, source_id: str, chat_id: str) -> IdentityRead:
        source = self.read(source_id)
        payload = IdentityCreate(
            **source.model_dump(include=set(IdentityCreate.model_fields), exclude={"definitions"}),
            definitions=source.definitions,
        )
        return self.create(payload, chat_id=chat_id)
