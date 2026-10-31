from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency
from backend.modules.memory.service import MemoryService
from backend.repository.queries import Repository
from backend.schemas.memory import ChatMemory, MemoryMaterials

router = APIRouter(prefix="/api/chats", tags=["memory"])


@router.get("/{chat_id}/memory", response_model=ChatMemory)
def read_memory(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return MemoryService(Repository(session)).timeline(chat_id)


@router.get("/{chat_id}/memory/materials", response_model=MemoryMaterials)
def read_materials(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return MemoryService(Repository(session)).materials(chat_id)
