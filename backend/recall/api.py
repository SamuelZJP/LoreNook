from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.recall.schemas import RecallInput, RecallResult, RecallSettings
from backend.recall.service import RecallSettingsService, run_recall
from backend.repository.queries import Repository

router = APIRouter(prefix="/api/chats/{chat_id}", tags=["recall"])


@router.post("/recall", response_model=RecallResult)
def recall(chat_id: str, payload: RecallInput, database: DatabaseDependency, client: ModelClientDependency):
    return run_recall(database, client, chat_id, payload.user_input, payload.instruction)


@router.get("/recall-settings", response_model=RecallSettings)
def read_settings(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return RecallSettingsService(Repository(session)).read(chat_id)


@router.put("/recall-settings", response_model=RecallSettings)
def replace_settings(chat_id: str, payload: RecallSettings, database: DatabaseDependency):
    with database.transaction() as session:
        return RecallSettingsService(Repository(session)).replace(chat_id, payload)


@router.post("/recall-setup", response_model=RecallSettings)
def setup(chat_id: str, payload: RecallSettings, database: DatabaseDependency):
    with database.transaction() as session:
        return RecallSettingsService(Repository(session)).setup(chat_id, payload)
