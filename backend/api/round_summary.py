from fastapi import APIRouter, Request

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.modules.round_summary.service import RoundSummaryService
from backend.repository.queries import Repository
from backend.schemas.round_summary import RoundSummaryRead, RoundSummaryReplace, RoundSummaryResult
from backend.workflows.round_summary import run_round_summary

router = APIRouter(prefix="/api/chats/{chat_id}/rounds/{round_id}", tags=["round-summary"])


@router.post("/round-summary", response_model=RoundSummaryResult)
def generate(chat_id: str, round_id: str, request: Request, database: DatabaseDependency, client: ModelClientDependency):
    return run_round_summary(database, client, chat_id, round_id,
                             recent_summaries=request.app.state.round_summary_recent_summaries)


@router.get("/summary", response_model=RoundSummaryRead)
def read(chat_id: str, round_id: str, database: DatabaseDependency):
    with database.read() as session:
        return RoundSummaryService(Repository(session)).read(chat_id, round_id)


@router.put("/summary", response_model=RoundSummaryRead)
def replace(chat_id: str, round_id: str, payload: RoundSummaryReplace, database: DatabaseDependency):
    with database.transaction() as session:
        return RoundSummaryService(Repository(session)).replace(chat_id, round_id, payload.summary)
