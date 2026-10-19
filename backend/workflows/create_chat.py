"""Create a complete independent chat bundle in one short transaction."""

from copy import deepcopy

from backend.modules.characters.service import CharacterService
from backend.modules.chats.service import ChatService
from backend.modules.state.initial import InitialStateFactory, build_initial_state
from backend.modules.state.schema import python_initial_state
from backend.modules.users.service import IdentityService
from backend.repository.database import Database
from backend.repository.models import Chat, ChatModelBinding, ModelConfig, StateSnapshot, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.chats import ChatCreate, ChatDetail


def create_chat(
    database: Database, payload: ChatCreate,
    initial_state_factory: InitialStateFactory = python_initial_state,
) -> ChatDetail:
    with database.transaction() as session:
        repository = Repository(session)
        chat = repository.add(Chat(title=payload.title, recent_rounds=payload.recent_rounds,
                                   min_summaries=payload.min_summaries))
        character = CharacterService(repository, initial_state_factory).copy_to_chat(payload.character_id, chat.id)
        IdentityService(repository).copy_to_chat(payload.user_identity_id, chat.id)

        preset_ids = list(payload.writing_preset_ids)
        if payload.writing_preset_id is not None:
            preset_ids.append(payload.writing_preset_id)
        presets = {}
        for source_id in dict.fromkeys(preset_ids):
            source = repository.get_owned(WritingPreset, source_id, None)
            presets[source_id] = repository.add(WritingPreset(chat_id=chat.id, name=source.name, source=source.source)).id
        if payload.writing_preset_id is not None:
            chat.writing_preset_id = presets[payload.writing_preset_id]

        configs = {}
        for source_id in dict.fromkeys([*payload.model_config_ids, *payload.model_bindings.values()]):
            source = repository.get_owned(ModelConfig, source_id, None)
            configs[source_id] = repository.add(ModelConfig(
                chat_id=chat.id, name=source.name, api_type=source.api_type,
                base_url=source.base_url, api_key=source.api_key, model=source.model,
                default_parameters=deepcopy(source.default_parameters),
            )).id
        for purpose, source_id in payload.model_bindings.items():
            repository.add(ChatModelBinding(chat_id=chat.id, purpose=purpose, model_config_id=configs[source_id]))

        state = build_initial_state(initial_state_factory, character.state_schema)
        repository.add(StateSnapshot(chat_id=chat.id, character_id=character.id, content=state))
        return ChatService(repository).detail(chat.id)
