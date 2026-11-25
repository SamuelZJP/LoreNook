from backend.modules.characters.code import check_code_allowed
from backend.modules.definitions.storage import DefinitionStorage
from backend.modules.state.initial import InitialStateFactory, build_initial_state
from backend.modules.state.schema import python_initial_state
from backend.modules.state.script import check_state_script
from backend.repository.models import Character, CharacterScene
from backend.repository.queries import Repository
from backend.schemas.catalog import CharacterCreate, CharacterPatch, CharacterRead, SceneInput, SceneRead
from backend.shared.errors import ConflictError, NotFoundError, StateInitializationError


class CharacterService:
    def __init__(self, repository: Repository, initial_state_factory: InitialStateFactory = python_initial_state):
        self.repository = repository
        self.initial_state_factory = initial_state_factory
        self.definitions = DefinitionStorage(repository)

    def read(self, character_id: str, chat_id: str | None = None) -> CharacterRead:
        record = self.repository.get_owned(Character, character_id, chat_id)
        return self._read(record)

    def _read(self, record: Character) -> CharacterRead:
        excluded = {"definitions", "scenes"}
        fields = {name: getattr(record, name) for name in CharacterRead.model_fields if name not in excluded}
        return CharacterRead(**fields, definitions=self.definitions.read(character_id=record.id),
                             scenes=[SceneRead.model_validate(scene) for scene in self.repository.scenes(record.id)])

    def list_library(self) -> list[CharacterRead]:
        return [self._read(record) for record in self.repository.list_owned(Character, None)]

    def _validate_scenes(self, schema: str, scenes: list[SceneInput]) -> None:
        for scene in scenes:
            try:
                build_initial_state(self.initial_state_factory, schema, scene.initial_state)
            except StateInitializationError as error:
                raise StateInitializationError(f"开场「{scene.name}」：{error}") from error

    def create(self, payload: CharacterCreate, chat_id: str | None = None, *, check_scenes: bool = True) -> CharacterRead:
        """`check_scenes=False` is for a card imported without its Schema: creating a chat checks the scene."""
        check_code_allowed(payload.state_schema, payload.state_script)
        if check_scenes:
            self._validate_scenes(payload.state_schema, payload.scenes)
        check_state_script(payload.state_script)
        return self._create(payload, chat_id)

    def _create(self, payload: CharacterCreate, chat_id: str | None) -> CharacterRead:
        record = self.repository.add(Character(chat_id=chat_id, **payload.model_dump(exclude={"definitions", "scenes"})))
        self.definitions.replace(payload.definitions, character_id=record.id)
        self._replace_scenes(record.id, payload.scenes)
        return self._read(record)

    def _replace_scenes(self, character_id: str, scenes: list[SceneInput]) -> None:
        for record in self.repository.scenes(character_id):
            self.repository.delete(record)
        for scene in scenes:
            self.repository.add(CharacterScene(character_id=character_id, **scene.model_dump()))

    def update(self, character_id: str, payload: CharacterPatch, chat_id: str | None = None) -> CharacterRead:
        record = self.repository.get_owned(Character, character_id, chat_id)
        fields = payload.model_fields_set
        check_code_allowed(payload.state_schema, payload.state_script)
        if chat_id is not None and payload.scenes is not None and len(payload.scenes) != 1:
            raise ConflictError("聊天角色只能保留创建时选择的一个开场")
        if fields & {"state_schema", "scenes"}:
            scenes = payload.scenes if payload.scenes is not None else [
                SceneInput.model_validate(scene.model_dump(exclude={"id", "character_id"}))
                for scene in self._read(record).scenes
            ]
            self._validate_scenes(payload.state_schema if payload.state_schema is not None else record.state_schema,
                                  scenes)
        if payload.state_script is not None:
            check_state_script(payload.state_script)
        for name, value in payload.model_dump(exclude_unset=True, exclude={"definitions", "scenes"}).items():
            setattr(record, name, value)
        if "definitions" in fields:
            self.definitions.replace(payload.definitions, character_id=record.id)
        if payload.scenes is not None:
            self._replace_scenes(record.id, payload.scenes)
        self.repository.session.flush()
        return self._read(record)

    def delete_source(self, character_id: str) -> None:
        self.repository.delete(self.repository.get_owned(Character, character_id, None))

    def copy_to_chat(self, source_id: str, chat_id: str, scene_id: str | None = None) -> CharacterRead:
        """Copy the character with only the selected scene (default: the first)."""
        source = self.read(source_id)
        scene = next((s for s in source.scenes if scene_id is None or s.id == scene_id), None)
        if scene is None:
            raise NotFoundError("所选开场不属于该角色")
        payload = CharacterCreate(
            **source.model_dump(include=set(CharacterCreate.model_fields), exclude={"definitions", "scenes"}),
            definitions=source.definitions,
            scenes=[SceneInput.model_validate(scene.model_dump(exclude={"id", "character_id"}) | {"order": 0})],
        )
        # The chat workflow validates the copied configuration when generating its snapshot.
        return self._create(payload, chat_id=chat_id)
