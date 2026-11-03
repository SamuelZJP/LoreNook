from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency
from backend.repository.models import Character
from backend.repository.queries import Repository
from backend.status_bar.schemas import ChatStatusBar, ChatStatusBarPatch, StatusBar
from backend.status_bar.service import StatusBarService

router = APIRouter(prefix="/api", tags=["status-bar"])


@router.get("/characters/{character_id}/status-bar", response_model=StatusBar)
def read(character_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        return StatusBarService(repository).read(repository.get_owned(Character, character_id, None).id)


@router.put("/characters/{character_id}/status-bar", response_model=StatusBar)
def replace(character_id: str, payload: StatusBar, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        return StatusBarService(repository).replace(repository.get_owned(Character, character_id, None).id, payload.code)


@router.get("/chats/{chat_id}/status-bar", response_model=ChatStatusBar)
def read_chat(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return StatusBarService(Repository(session)).read_chat(chat_id)


@router.patch("/chats/{chat_id}/status-bar", response_model=ChatStatusBar)
def update_chat(chat_id: str, payload: ChatStatusBarPatch, database: DatabaseDependency):
    with database.transaction() as session:
        return StatusBarService(Repository(session)).update_chat(chat_id, payload)
