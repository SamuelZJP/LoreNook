"""Run the summary step using its exact saved state; commit result and progress together."""

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.models.service import ModelService
from backend.modules.round_summary.generate import generate_summary
from backend.repository.database import Database
from backend.repository.models import Character, Round, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.round_summary import RoundSummaryContext, RoundSummaryResult
from backend.shared.errors import ConflictError, RoundSummaryError
from backend.workflows.archive_step import run_archive_step


def _context(repository: Repository, chat_id: str, round_id: str, window: int) -> RoundSummaryContext:
    character = repository.get(Character, repository.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, repository.owner_id(chat_id, UserIdentity))
    record = repository.get_owned(Round, round_id, chat_id)
    latest = repository.latest_round(chat_id)
    if latest is None or latest.id != round_id or record.archive_step != "round_summary":
        raise ConflictError("只能对最新回合的 round_summary 步骤生成摘要")
    if record.summary is not None:
        raise ConflictError("摘要已存在但步骤尚未推进")
    state = repository.state_for_round(chat_id, round_id)
    if state is None or state.character_id != character.id:
        raise ConflictError("回合摘要缺少本回合更新后的状态")
    return RoundSummaryContext(
        chat_id=chat_id, round_id=round_id, round_no=record.round_no,
        user_input=record.user_input, ai_output=record.ai_output,
        state_snapshot_id=state.id, state=state.content, character_name=character.name, user_name=identity.name,
        summaries=[f"第{r.round_no}回合：{r.summary}" for r in repository.summaries_before(chat_id, record.round_no, window)],
        connection=ModelService(repository, chat_id).for_purpose("round_summary"),
    )


@recorded_workflow("round_summary")
def run_round_summary(database: Database, client: ModelClient, chat_id: str, round_id: str, *,
                      recent_summaries: int = 3) -> RoundSummaryResult:
    def save(repository, summary):
        repository.save_summary(round_id, summary)
        return RoundSummaryResult(chat_id=chat_id, round_id=round_id, summary=summary)

    return run_archive_step(
        database, round_id=round_id, step="round_summary",
        load=lambda repository: _context(repository, chat_id, round_id, recent_summaries),
        generate=lambda context: generate_summary(context, client), save=save,
        failures=(RoundSummaryError,), changed_message="摘要生成期间输入已变化，请重新执行当前步骤",
    )
