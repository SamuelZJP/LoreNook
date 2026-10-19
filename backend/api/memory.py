from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency
from backend.modules.memory.service import MemoryService
from backend.repository.queries import Repository
from backend.schemas.memory import ChatMemory

router = APIRouter(prefix="/api/chats", tags=["memory"])


@router.get("/{chat_id}/memory", response_model=ChatMemory)
def read_memory(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return MemoryService(Repository(session)).assemble(chat_id)
