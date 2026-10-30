from backend.modules.characters.service import CharacterService
from backend.modules.illustrations.service import IllustrationService, read_workflow
from backend.modules.users.service import IdentityService
from backend.repository.models import Character, Chat, ChatModelBinding, ImageWorkflow, ModelConfig, UserIdentity, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.chats import ChatDetail, ChatPatch, ChatRead, ModelConfigRead, PresetRead, StateRead
from backend.shared.errors import ConflictError


class ChatService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def list(self) -> list[ChatRead]:
        return [ChatRead.model_validate(record) for record in self.repository.list_chats()]

    def owner_id(self, chat_id: str, model: type[Character | UserIdentity]) -> str:
        self.repository.get(Chat, chat_id)
        records = self.repository.list_owned(model, chat_id)
        if len(records) != 1:
            raise ConflictError(f"Chat must have exactly one {model.__name__}")
        return records[0].id

    def detail(self, chat_id: str) -> ChatDetail:
        chat = self.repository.get(Chat, chat_id)
        character_id = self.owner_id(chat_id, Character)
        identity_id = self.owner_id(chat_id, UserIdentity)
        state = self.repository.latest_state(character_id)
        if state is None:
            raise ConflictError("Chat has no state snapshot")
        configs = []
        for config in self.repository.list_owned(ModelConfig, chat_id):
            fields = {name: getattr(config, name) for name in ModelConfigRead.model_fields if name != "has_api_key"}
            configs.append(ModelConfigRead(**fields, has_api_key=bool(config.api_key)))
        return ChatDetail(
            **ChatRead.model_validate(chat).model_dump(),
            character=CharacterService(self.repository).read(character_id, chat_id),
            user_identity=IdentityService(self.repository).read(identity_id, chat_id),
            writing_presets=[PresetRead.model_validate(record) for record in self.repository.list_owned(WritingPreset, chat_id)],
            model_configs=configs,
            model_bindings={binding.purpose: binding.model_config_id for binding in self.repository.model_bindings(chat_id)},
            image_workflows=[read_workflow(record) for record in self.repository.list_owned(ImageWorkflow, chat_id)],
            illustration=IllustrationService(self.repository).settings(chat_id),
            latest_state=StateRead.model_validate(state),
        )

    def update(self, chat_id: str, payload: ChatPatch) -> ChatDetail:
        chat = self.repository.get(Chat, chat_id)
        if payload.writing_preset_id is not None:
            self.repository.get_owned(WritingPreset, payload.writing_preset_id, chat_id)
        if "model_bindings" in payload.model_fields_set:
            for config_id in set(payload.model_bindings.values()):
                self.repository.get_owned(ModelConfig, config_id, chat_id)
            for binding in self.repository.model_bindings(chat_id):
                self.repository.delete(binding)
            for purpose, config_id in payload.model_bindings.items():
                self.repository.add(ChatModelBinding(chat_id=chat_id, purpose=purpose, model_config_id=config_id))
        if payload.illustration is not None:
            IllustrationService(self.repository).replace_settings(chat_id, payload.illustration)
        for name, value in payload.model_dump(exclude_unset=True, exclude={"model_bindings", "illustration"}).items():
            setattr(chat, name, value)
        self.repository.session.flush()
        return self.detail(chat_id)

    def delete(self, chat_id: str) -> None:
        self.repository.delete(self.repository.get(Chat, chat_id))
