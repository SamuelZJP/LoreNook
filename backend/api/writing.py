from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.schemas.writing import WritingInput, WritingResult
from backend.workflows.writing import generate_writing

router = APIRouter(prefix="/api/chats", tags=["writing"])


@router.post("/{chat_id}/writing", response_model=WritingResult)
def generate(chat_id: str, payload: WritingInput, database: DatabaseDependency, client: ModelClientDependency):
    return generate_writing(database, client, chat_id, payload.user_input, payload.instruction, payload.layout)
