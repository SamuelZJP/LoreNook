from backend.repository.models import Chat, Round
from backend.repository.queries import Repository
from backend.schemas.round_summary import RoundSummaryRead
from backend.shared.errors import ConflictError, RoundSummaryError


class RoundSummaryService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def read(self, chat_id: str, round_id: str) -> RoundSummaryRead:
        self.repository.get(Chat, chat_id)
        record = self.repository.get_owned(Round, round_id, chat_id)
        if record.summary is None or not record.summary.strip():
            raise ConflictError("本回合尚无已保存摘要")
        return RoundSummaryRead(chat_id=chat_id, round_id=round_id, summary=record.summary)

    def replace(self, chat_id: str, round_id: str, summary: str) -> RoundSummaryRead:
        self.repository.get(Chat, chat_id)
        record = self.repository.get_owned(Round, round_id, chat_id)
        latest = self.repository.latest_round(chat_id)
        if latest is None or latest.id != round_id or record.archive_step != "complete":
            raise ConflictError("只能编辑最新已归档回合的摘要")
        if not summary.strip():
            raise RoundSummaryError("回合摘要不能为空白")
        record.summary = summary
        self.repository.session.flush()
        return self.read(chat_id, round_id)
