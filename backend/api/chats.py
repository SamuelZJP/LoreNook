from fastapi import APIRouter, Request, Response

from backend.api.dependencies import DatabaseDependency
from backend.modules.characters.service import CharacterService
from backend.modules.chats.service import ChatService
from backend.modules.users.service import IdentityService
from backend.repository.models import Character, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import CharacterPatch, CharacterRead, IdentityPatch, IdentityRead
from backend.schemas.chats import ChatCreate, ChatDetail, ChatPatch, ChatRead
from backend.workflows.create_chat import create_chat

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=list[ChatRead])
def list_chats(database: DatabaseDependency):
    with database.read() as session:
        return ChatService(Repository(session)).list()


@router.post("", response_model=ChatDetail, status_code=201)
def create(payload: ChatCreate, request: Request, database: DatabaseDependency):
    return create_chat(database, payload, request.app.state.initial_state_factory, request.app.state.hooks.chat_created)


@router.get("/{chat_id}", response_model=ChatDetail)
def read(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return ChatService(Repository(session)).detail(chat_id)


@router.patch("/{chat_id}", response_model=ChatDetail)
def update(chat_id: str, payload: ChatPatch, database: DatabaseDependency):
    with database.transaction() as session:
        return ChatService(Repository(session)).update(chat_id, payload)


@router.delete("/{chat_id}", status_code=204)
def delete(chat_id: str, request: Request, database: DatabaseDependency):
    with database.transaction() as session:
        ChatService(Repository(session)).delete(chat_id)
    hooks = request.app.state.hooks
    hooks.notify(hooks.chat_deleted, chat_id)
    return Response(status_code=204)


@router.get("/{chat_id}/character", response_model=CharacterRead)
def read_character(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        character_id = ChatService(repository).owner_id(chat_id, Character)
        return CharacterService(repository).read(character_id, chat_id)


@router.patch("/{chat_id}/character", response_model=CharacterRead)
def update_character(chat_id: str, payload: CharacterPatch, request: Request, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        character_id = ChatService(repository).owner_id(chat_id, Character)
        return CharacterService(repository, request.app.state.initial_state_factory).update(character_id, payload, chat_id)


@router.get("/{chat_id}/user-identity", response_model=IdentityRead)
def read_identity(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        identity_id = ChatService(repository).owner_id(chat_id, UserIdentity)
        return IdentityService(repository).read(identity_id, chat_id)


@router.patch("/{chat_id}/user-identity", response_model=IdentityRead)
def update_identity(chat_id: str, payload: IdentityPatch, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        identity_id = ChatService(repository).owner_id(chat_id, UserIdentity)
        return IdentityService(repository).update(identity_id, payload, chat_id)
