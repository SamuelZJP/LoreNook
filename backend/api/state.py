from fastapi import APIRouter, Request

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.modules.state.service import StateService
from backend.repository.queries import Repository
from backend.schemas.chats import StateRead
from backend.schemas.state import StateReplace, StateUpdateResult
from backend.workflows.edit_state import replace_latest_state
from backend.workflows.state_update import run_state_update

router = APIRouter(prefix="/api/chats", tags=["state"])


@router.get("/{chat_id}/state", response_model=StateRead)
def read(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return StateService(Repository(session)).latest(chat_id)


@router.put("/{chat_id}/state", response_model=StateRead)
def replace(chat_id: str, payload: StateReplace, request: Request, database: DatabaseDependency):
    return replace_latest_state(database, chat_id, payload.content, validator=request.app.state.state_validator)


@router.post("/{chat_id}/rounds/{round_id}/state-update", response_model=StateUpdateResult)
def update(chat_id: str, round_id: str, request: Request, database: DatabaseDependency, client: ModelClientDependency):
    return run_state_update(database, client, chat_id, round_id, validator=request.app.state.state_validator,
                            recent_summaries=request.app.state.state_recent_summaries)
