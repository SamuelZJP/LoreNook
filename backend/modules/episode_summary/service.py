from backend.repository.models import Chat, Episode
from backend.repository.queries import Repository
from backend.schemas.episode_summary import EpisodeRead
from backend.shared.errors import ConflictError, EpisodeSummaryError


class EpisodeService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def list(self, chat_id: str) -> list[EpisodeRead]:
        self.repository.get(Chat, chat_id)
        return [EpisodeRead.model_validate(record) for record in self.repository.episodes(chat_id)]

    def read(self, chat_id: str, episode_id: str) -> EpisodeRead:
        self.repository.get(Chat, chat_id)
        return EpisodeRead.model_validate(self.repository.get_owned(Episode, episode_id, chat_id))

    def replace(self, chat_id: str, episode_id: str, summary: str, *, title: str | None = None) -> EpisodeRead:
        self.repository.get(Chat, chat_id)
        record = self.repository.get_owned(Episode, episode_id, chat_id)
        latest = self.repository.latest_round_header(chat_id)
        if latest is None or latest.archive_step != "complete" or latest.id != record.created_by_round_id:
            raise ConflictError("只能编辑最新已归档回合产生的情节")
        if not summary.strip():
            raise EpisodeSummaryError("情节摘要不能为空白")
        record.summary = summary
        if title is not None:
            if not title.strip() or len(title) > 20:
                raise EpisodeSummaryError("情节标题须为1至20个字符")
            record.title = title
        self.repository.session.flush()
        return EpisodeRead.model_validate(record)
