"""Read one consistent chat snapshot, then render outside the database transaction."""

from backend.modules.chats.service import ChatService
from backend.modules.definitions.renderer import DefinitionRenderer
from backend.modules.definitions.storage import DefinitionStorage
from backend.repository.database import Database
from backend.repository.models import Character, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.definitions import ChatResolvedDefinitions
from backend.shared.errors import ConflictError


def resolve_chat_definitions(database: Database, chat_id: str) -> ChatResolvedDefinitions:
    with database.read() as session:
        repository = Repository(session)
        chat_service = ChatService(repository)
        character_id = chat_service.owner_id(chat_id, Character)
        identity_id = chat_service.owner_id(chat_id, UserIdentity)
        state = repository.latest_state(character_id)
        if state is None:
            raise ConflictError("Chat has no state snapshot")
        snapshot_id, content = state.id, state.content
        names = {"user_name": repository.get(UserIdentity, identity_id).name,
                 "character_name": repository.get(Character, character_id).name}
        storage = DefinitionStorage(repository)
        character_definitions = storage.read(character_id=character_id)
        user_definitions = storage.read(user_identity_id=identity_id)

    resolved = DefinitionRenderer().resolve(character_definitions, user_definitions, content, **names)
    return ChatResolvedDefinitions(chat_id=chat_id, state_snapshot_id=snapshot_id, **resolved.model_dump())
