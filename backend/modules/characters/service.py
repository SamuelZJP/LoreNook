from backend.modules.definitions.storage import DefinitionStorage
from backend.modules.state.initial import InitialStateFactory, build_initial_state
from backend.modules.state.schema import python_initial_state
from backend.repository.models import Character
from backend.repository.queries import Repository
from backend.schemas.catalog import CharacterCreate, CharacterPatch, CharacterRead


class CharacterService:
    def __init__(self, repository: Repository, initial_state_factory: InitialStateFactory = python_initial_state):
        self.repository = repository
        self.initial_state_factory = initial_state_factory
        self.definitions = DefinitionStorage(repository)

    def read(self, character_id: str, chat_id: str | None = None) -> CharacterRead:
        record = self.repository.get_owned(Character, character_id, chat_id)
        return self._read(record)

    def _read(self, record: Character) -> CharacterRead:
        fields = {name: getattr(record, name) for name in CharacterRead.model_fields if name != "definitions"}
        return CharacterRead(**fields, definitions=self.definitions.read(character_id=record.id))

    def list_library(self) -> list[CharacterRead]:
        return [self._read(record) for record in self.repository.list_owned(Character, None)]

    def create(self, payload: CharacterCreate, chat_id: str | None = None) -> CharacterRead:
        build_initial_state(self.initial_state_factory, payload.state_schema)
        return self._create(payload, chat_id)

    def _create(self, payload: CharacterCreate, chat_id: str | None) -> CharacterRead:
        record = self.repository.add(Character(chat_id=chat_id, **payload.model_dump(exclude={"definitions"})))
        self.definitions.replace(payload.definitions, character_id=record.id)
        return self._read(record)

    def update(self, character_id: str, payload: CharacterPatch, chat_id: str | None = None) -> CharacterRead:
        record = self.repository.get_owned(Character, character_id, chat_id)
        if "state_schema" in payload.model_fields_set:
            build_initial_state(self.initial_state_factory, payload.state_schema)
        for name, value in payload.model_dump(exclude_unset=True, exclude={"definitions"}).items():
            setattr(record, name, value)
        if "definitions" in payload.model_fields_set:
            self.definitions.replace(payload.definitions, character_id=record.id)
        self.repository.session.flush()
        return self._read(record)

    def delete_source(self, character_id: str) -> None:
        self.repository.delete(self.repository.get_owned(Character, character_id, None))

    def copy_to_chat(self, source_id: str, chat_id: str) -> CharacterRead:
        source = self.read(source_id)
        payload = CharacterCreate(
            **source.model_dump(include=set(CharacterCreate.model_fields), exclude={"definitions"}),
            definitions=source.definitions,
        )
        # The chat workflow validates the copied configuration when generating its snapshot.
        return self._create(payload, chat_id=chat_id)
