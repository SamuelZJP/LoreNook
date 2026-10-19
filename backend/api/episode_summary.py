from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.modules.episode_summary.service import EpisodeService
from backend.repository.queries import Repository
from backend.schemas.episode_summary import EpisodeRead, EpisodeReplace, EpisodeSummaryResult
from backend.workflows.episode_summary import run_episode_summary

router = APIRouter(prefix="/api/chats", tags=["episodes"])


@router.post("/{chat_id}/rounds/{round_id}/episode-summary", response_model=EpisodeSummaryResult)
def generate(chat_id: str, round_id: str, database: DatabaseDependency, client: ModelClientDependency):
    return run_episode_summary(database, client, chat_id, round_id)


@router.get("/{chat_id}/episodes", response_model=list[EpisodeRead])
def list_episodes(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return EpisodeService(Repository(session)).list(chat_id)


@router.get("/{chat_id}/episodes/{episode_id}", response_model=EpisodeRead)
def read(chat_id: str, episode_id: str, database: DatabaseDependency):
    with database.read() as session:
        return EpisodeService(Repository(session)).read(chat_id, episode_id)


@router.put("/{chat_id}/episodes/{episode_id}", response_model=EpisodeRead)
def replace(chat_id: str, episode_id: str, payload: EpisodeReplace, database: DatabaseDependency):
    with database.transaction() as session:
        return EpisodeService(Repository(session)).replace(chat_id, episode_id, payload.summary, title=payload.title)
