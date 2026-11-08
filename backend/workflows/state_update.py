"""Run one persisted round's state step, then save state and progress atomically."""

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.definitions.renderer import substitute_names
from backend.modules.models.service import ModelService
from backend.modules.state.schema import StateValidator, validate_state
from backend.modules.state.update import update_state
from backend.repository.database import Database
from backend.repository.models import Character, Round, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.chats import StateRead
from backend.schemas.state import StateUpdateContext, StateUpdateResult
from backend.shared.errors import ConflictError, StateSchemaError, StateScriptError, StateUpdateError
from backend.workflows.archive_step import run_archive_step


def _context(repository: Repository, chat_id: str, round_id: str, window: int) -> StateUpdateContext:
    character = repository.get(Character, repository.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, repository.owner_id(chat_id, UserIdentity))
    record = repository.get_owned(Round, round_id, chat_id)
    latest = repository.latest_round(chat_id)
    if latest is None or latest.id != round_id or record.archive_step != "state_update":
        raise ConflictError("只能对最新回合的 state_update 步骤执行状态更新")
    state = repository.latest_state(character.id)
    if state is None or state.round_id == round_id:
        raise ConflictError("状态更新缺少合法的上一状态")
    history = [{"round_no": number, "state": content} for number, content in
               repository.states_before(character.id, record.round_no, character.state_script_history)]
    names = {"user_name": identity.name, "character_name": character.name}
    return StateUpdateContext(
        chat_id=chat_id, round_id=round_id, round_no=record.round_no,
        user_input=record.user_input, ai_output=record.ai_output,
        state_snapshot_id=state.id, state=state.content, schema_source=character.state_schema,
        script_source=character.state_script, history=history,
        reference=substitute_names(character.state_reference, **names),
        update_rules=substitute_names(character.state_update_rules, **names), user_name=identity.name,
        summaries=[f"第{r.round_no}回合：{r.summary}" for r in repository.summaries_before(chat_id, record.round_no, window)],
        connection=ModelService(repository, chat_id).for_purpose("state_update"),
    )


@recorded_workflow("state_update")
def run_state_update(database: Database, client: ModelClient, chat_id: str, round_id: str, *,
                     validator: StateValidator = validate_state, recent_summaries: int = 3) -> StateUpdateResult:
    def save(repository, generated):
        state, skipped = generated
        saved = repository.save_state(round_id, state)
        return StateUpdateResult(chat_id=chat_id, round_id=round_id, archive_step="round_summary",
                                 state=StateRead.model_validate(saved), skipped_operations=skipped)

    return run_archive_step(
        database, round_id=round_id, step="state_update",
        load=lambda repository: _context(repository, chat_id, round_id, recent_summaries),
        generate=lambda context: update_state(context, client, validator), save=save,
        failures=(StateSchemaError, StateScriptError, StateUpdateError), changed_message="状态更新期间输入已变化，请重新执行当前步骤",
    )
