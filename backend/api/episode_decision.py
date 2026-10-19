from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency
from backend.schemas.episode_decision import EpisodeDecisionResult
from backend.workflows.episode_decision import run_episode_decision

router = APIRouter(prefix="/api/chats", tags=["episode-decision"])


@router.post("/{chat_id}/rounds/{round_id}/episode-decision", response_model=EpisodeDecisionResult)
def decide(chat_id: str, round_id: str, database: DatabaseDependency):
    return run_episode_decision(database, chat_id, round_id)
