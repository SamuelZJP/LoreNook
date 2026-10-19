"""Summarize a frozen decision range; move coverage only with successful persistence."""

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.chats.service import ChatService
from backend.modules.episode_summary.generate import generate_episode_summary
from backend.modules.models.service import ModelService
from backend.repository.archive import ArchiveRepository
from backend.repository.database import Database
from backend.repository.models import Character, Round, UserIdentity
from backend.schemas.episode_summary import EpisodeBridgeRound, EpisodeRead, EpisodeSourceRound, EpisodeSummaryContext, EpisodeSummaryResult
from backend.shared.errors import ConflictError, EpisodeSummaryError, ModelCallError, ModelConfigurationError


def _context(repository: ArchiveRepository, chat_id: str, round_id: str) -> EpisodeSummaryContext:
    record = repository.get_owned(Round, round_id, chat_id)
    service = ChatService(repository)
    character = repository.get(Character, service.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, service.owner_id(chat_id, UserIdentity))
    latest = repository.latest_round_header(chat_id)
    if latest is None or latest.id != round_id or record.archive_step != "episode_summary":
        raise ConflictError("只能对最新回合的 episode_summary 步骤生成情节摘要")
    if repository.episode_for_round(chat_id, round_id) is not None:
        raise ConflictError("本回合情节已存在但步骤尚未推进")
    selected = repository.pending_episode_range(round_id)
    records = repository.rounds_in_range(chat_id, selected[0].round_no, selected[-1].round_no)
    if [row.id for row in records] != [header.id for header in selected]:
        raise ConflictError("情节范围内回合不完整")
    states = {state.round_id: state for state in repository.states_for_rounds(chat_id, [r.id for r in selected])}
    rounds = []
    for source in records:
        state = states.get(source.id)
        if state is None or state.character_id != character.id:
            raise ConflictError("情节范围内缺少对应回合的状态")
        if source.summary is None or not source.summary.strip():
            raise ConflictError("情节范围内缺少有效回合摘要")
        rounds.append(EpisodeSourceRound(id=source.id, round_no=source.round_no, summary=source.summary,
                                         user_input=source.user_input, ai_output=source.ai_output,
                                         state_snapshot_id=state.id, state=state.content))
    bridge = repository.episode_bridge_before(chat_id, selected[0].round_no)
    return EpisodeSummaryContext(
        chat_id=chat_id, round_id=round_id, start_round_id=record.episode_start_round_id,
        end_round_id=record.episode_end_round_id, character_name=character.name, user_name=identity.name,
        rounds=rounds, first_message=character.first_message if selected[0].round_no == 1 else None,
        bridge=EpisodeBridgeRound.model_validate(bridge) if bridge is not None else None,
        connection=ModelService(repository, chat_id).for_purpose("episode_summary"),
    )


def _unchanged(repository: ArchiveRepository, context: EpisodeSummaryContext) -> None:
    current = _context(repository, context.chat_id, context.round_id)
    if current != context or current.model_dump_json() != context.model_dump_json():
        raise ConflictError("情节摘要生成期间输入已变化，请重新执行当前步骤")


@recorded_workflow("episode_summary")
def run_episode_summary(database: Database, client: ModelClient, chat_id: str, round_id: str) -> EpisodeSummaryResult:
    with database.read() as session:
        context = _context(ArchiveRepository(session), chat_id, round_id)
    try:
        generated = generate_episode_summary(context, client)
    except (EpisodeSummaryError, ModelCallError, ModelConfigurationError) as error:
        with database.transaction() as session:
            repository = ArchiveRepository(session)
            _unchanged(repository, context)
            repository.save_error(round_id, "episode_summary", str(error)[:2000])
        raise
    with database.transaction() as session:
        repository = ArchiveRepository(session)
        _unchanged(repository, context)
        saved = repository.save_episode(round_id, generated.summary, title=generated.title)
        return EpisodeSummaryResult(chat_id=chat_id, round_id=round_id, episode=EpisodeRead.model_validate(saved))
