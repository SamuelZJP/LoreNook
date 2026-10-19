from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.episode_decision import EpisodeCandidate, EpisodeDecisionContext
from backend.shared.errors import ConflictError


def collect_context(repository: Repository, chat_id: str, round_id: str) -> EpisodeDecisionContext:
    repository.get(Chat, chat_id)
    current = repository.round_header(chat_id, round_id)
    latest = repository.latest_round_header(chat_id)
    if latest is None or latest.id != round_id or current.archive_step != "episode_decision":
        raise ConflictError("只能对最新回合的 episode_decision 步骤执行情节判定")
    headers = repository.unrepresented_round_headers(chat_id)
    if any(record.id != round_id and record.archive_step != "complete" for record in headers):
        raise ConflictError("最新回合之前的情节候选必须完成归档")
    candidates = [EpisodeCandidate(id=record.id, round_no=record.round_no) for record in headers]
    # Only read candidate dates; already covered rounds are never extra context.
    dates = repository.round_dates(chat_id, [r.id for r in candidates[-2:]]) if len(candidates) >= 2 else {}
    return EpisodeDecisionContext(current_round_id=round_id, candidates=candidates, dates=dates)
