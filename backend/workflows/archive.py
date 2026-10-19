"""Persist confirmation once, then execute only the remaining archive steps."""

from backend.llm.client import ModelClient
from backend.modules.chats.service import ChatService
from backend.modules.state.schema import StateValidator, validate_state
from backend.repository.archive import ArchiveRepository
from backend.repository.database import Database
from backend.repository.models import Character, Chat, Round, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.archive import ArchiveConfirm, ArchiveProgress, RoundRead
from backend.schemas.chats import StateRead
from backend.schemas.episode_summary import EpisodeRead
from backend.shared.content import extract_content
from backend.shared.errors import (
    ArchiveExecutionError, ConflictError, EpisodeDecisionError, EpisodeSummaryError, ModelCallError,
    ModelConfigurationError, NotFoundError, RoundSummaryError, StateSchemaError, StateUpdateError,
)
from backend.workflows.episode_decision import run_episode_decision
from backend.workflows.episode_summary import run_episode_summary
from backend.workflows.round_summary import run_round_summary
from backend.workflows.state_update import run_state_update

STEP_ERRORS = (ConflictError, NotFoundError, StateSchemaError, StateUpdateError, RoundSummaryError,
               EpisodeDecisionError, EpisodeSummaryError, ModelCallError, ModelConfigurationError)


def read_progress(repository: Repository, chat_id: str, round_id: str) -> ArchiveProgress:
    repository.get(Chat, chat_id)
    record = repository.get_owned(Round, round_id, chat_id)
    state = repository.state_for_round(chat_id, round_id)
    episode = repository.episode_for_round(chat_id, round_id)
    return ArchiveProgress(round=RoundRead.model_validate(record),
                           state=StateRead.model_validate(state) if state is not None else None,
                           episode=EpisodeRead.model_validate(episode) if episode is not None else None)


def _run_remaining(database: Database, client: ModelClient, chat_id: str, round_id: str, step: str, *,
                   validator: StateValidator, state_recent_summaries: int, round_recent_summaries: int) -> ArchiveProgress:
    try:
        while step != "complete":
            if step == "state_update":
                result = run_state_update(database, client, chat_id, round_id, validator=validator,
                                          recent_summaries=state_recent_summaries)
            elif step == "round_summary":
                result = run_round_summary(database, client, chat_id, round_id,
                                           recent_summaries=round_recent_summaries)
            elif step == "episode_decision":
                result = run_episode_decision(database, chat_id, round_id)
            elif step == "episode_summary":
                result = run_episode_summary(database, client, chat_id, round_id)
            else:
                raise ConflictError("未知归档步骤")
            # Follow only our successful result; never adopt another request's advanced step.
            step = result.archive_step
    except STEP_ERRORS as error:
        with database.read() as session:
            progress = read_progress(Repository(session), chat_id, round_id)
        raise ArchiveExecutionError(error, progress) from error
    with database.read() as session:
        return read_progress(Repository(session), chat_id, round_id)


def confirm_archive(database: Database, client: ModelClient, chat_id: str, confirmation: ArchiveConfirm, *,
                    validator: StateValidator = validate_state, state_recent_summaries: int = 3,
                    round_recent_summaries: int = 3) -> ArchiveProgress:
    extract_content(confirmation.ai_output)
    with database.transaction() as session:
        repository = ArchiveRepository(session)
        repository.get(Chat, chat_id)
        latest = repository.latest_round_header(chat_id)
        if (latest.id if latest is not None else None) != confirmation.based_on_round_id:
            raise ConflictError("确认所依据的回合已变化，请读取当前归档进度")
        if latest is not None and latest.archive_step != "complete":
            raise ConflictError("请先完成当前回合归档")
        service = ChatService(repository)
        character_id = service.owner_id(chat_id, Character)
        service.owner_id(chat_id, UserIdentity)
        if repository.latest_state(character_id) is None:
            raise ConflictError("聊天缺少初始或上一回合状态")
        record = repository.create_round(chat_id, confirmation.user_input, confirmation.ai_output)
        round_id = record.id
    return _run_remaining(database, client, chat_id, round_id, "state_update", validator=validator,
                          state_recent_summaries=state_recent_summaries, round_recent_summaries=round_recent_summaries)


def retry_archive(database: Database, client: ModelClient, chat_id: str, round_id: str, expected_step: str, *,
                  validator: StateValidator = validate_state, state_recent_summaries: int = 3,
                  round_recent_summaries: int = 3) -> ArchiveProgress:
    with database.read() as session:
        repository = Repository(session)
        repository.get(Chat, chat_id)
        header = repository.round_header(chat_id, round_id)
        latest = repository.latest_round_header(chat_id)
        if latest is None or latest.id != round_id or header.archive_step == "complete":
            raise ConflictError("只能继续最新未完成的归档回合")
        if header.archive_step != expected_step:
            raise ConflictError("归档步骤已变化，请读取当前归档进度")
    return _run_remaining(database, client, chat_id, round_id, expected_step, validator=validator,
                          state_recent_summaries=state_recent_summaries, round_recent_summaries=round_recent_summaries)
