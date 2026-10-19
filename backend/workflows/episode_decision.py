"""Compute and persist a deterministic decision within one short write transaction."""

from backend.modules.episode_decision.dispatcher import decide_episode
from backend.modules.episode_decision.service import collect_context
from backend.repository.archive import ArchiveRepository
from backend.repository.database import Database
from backend.schemas.episode_decision import EpisodeDecisionResult
from backend.shared.errors import EpisodeDecisionError


def run_episode_decision(database: Database, chat_id: str, round_id: str, *,
                         method: str | None = None) -> EpisodeDecisionResult:
    failure = None
    result = None
    with database.transaction() as session:
        repository = ArchiveRepository(session)
        context = collect_context(repository, chat_id, round_id)
        try:
            decision = decide_episode(context, method=method)
        except EpisodeDecisionError as error:
            repository.save_error(round_id, "episode_decision", str(error)[:2000])
            failure = error
        else:
            repository.save_decision(round_id, start_round_id=decision.start_round_id,
                                      end_round_id=decision.end_round_id)
            result = EpisodeDecisionResult(
                chat_id=chat_id, round_id=round_id, **decision.model_dump(),
                archive_step="episode_summary" if decision.episode_required else "complete",
            )
    if failure is not None:
        raise failure
    return result
