"""Illustration jobs: model call → ComfyUI → file. Runs after archiving and never touches archive progress."""

from concurrent.futures import Executor, ThreadPoolExecutor
import logging
import secrets

from sqlalchemy import inspect, select, update

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.chats.service import ChatService
from backend.modules.definitions.storage import DefinitionStorage
from backend.modules.illustrations.comfyui import ComfyUIClient
from backend.modules.illustrations.generate import generate_fields
from backend.modules.illustrations.service import IllustrationService
from backend.modules.illustrations.storage import ImageStorage
from backend.modules.illustrations.workflow import fill_workflow, prompt_fields
from backend.modules.models.service import ModelService
from backend.repository.database import Database
from backend.repository.models import Character, Chat, Illustration, ImageWorkflow, Round, StateSnapshot, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.illustrations import (
    ACTIVE_STATUSES, IllustrationContext, IllustrationPrompt, IllustrationRead,
)
from backend.shared.errors import (
    ConflictError, DefinitionTemplateError, IllustrationError, ModelCallError, ModelConfigurationError,
    NotFoundError,
)

logger = logging.getLogger(__name__)

FAILURES = (ConflictError, DefinitionTemplateError, IllustrationError, ModelCallError, ModelConfigurationError)


def _context(repository: Repository, chat_id: str, round_id: str) -> IllustrationContext:
    repository.get(Chat, chat_id)
    settings = IllustrationService(repository).settings(chat_id)
    if settings.mode == "off":
        raise ConflictError("聊天未开启插图")
    if settings.image_workflow_id is None or settings.model_config_id is None:
        raise ConflictError("请先在插图设置中选择图像工作流和提示词模型")
    record = repository.get_owned(Round, round_id, chat_id)
    if record.archive_step != "complete":
        raise ConflictError("只能为已归档的回合生成插图")
    service = ChatService(repository)
    character = repository.get(Character, service.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, service.owner_id(chat_id, UserIdentity))
    state = repository.state_for_round(chat_id, round_id)
    if state is None:
        raise ConflictError("回合缺少归档状态")
    workflow = repository.get_owned(ImageWorkflow, settings.image_workflow_id, chat_id)
    storage = DefinitionStorage(repository)
    return IllustrationContext(
        chat_id=chat_id, round_id=round_id, round_no=record.round_no,
        user_input=record.user_input, ai_output=record.ai_output, summary=record.summary, state=state.content,
        character_name=character.name, user_name=identity.name,
        character_definitions=storage.read(character_id=character.id),
        user_definitions=storage.read(user_identity_id=identity.id),
        image_workflow_id=workflow.id, base_url=workflow.base_url, workflow=workflow.workflow,
        instructions=workflow.instructions, width=workflow.width, height=workflow.height,
        fields=prompt_fields(workflow.workflow),
        connection=ModelService(repository, chat_id).connection(settings.model_config_id),
    )


@recorded_workflow("image_prompt")
def _prompt_fields(database: Database, client: ModelClient, chat_id: str, round_id: str,
                   context: IllustrationContext) -> dict[str, str]:
    return generate_fields(context, client)


def preview_prompt(database: Database, client: ModelClient, chat_id: str, round_id: str) -> IllustrationPrompt:
    """Run only the model step; nothing is stored or sent to ComfyUI."""
    with database.read() as session:
        context = _context(Repository(session), chat_id, round_id)
    fields = _prompt_fields(database, client, chat_id, round_id, context)
    return IllustrationPrompt(image_workflow_id=context.image_workflow_id, fields=fields)


def request_illustration(database: Database, chat_id: str, round_id: str) -> IllustrationRead:
    with database.transaction() as session:
        repository = Repository(session)
        context = _context(repository, chat_id, round_id)
        active = session.scalar(select(Illustration.id).where(
            Illustration.round_id == round_id, Illustration.status.in_(ACTIVE_STATUSES)))
        if active is not None:
            raise ConflictError("本回合插图正在生成")
        record = repository.add(Illustration(chat_id=chat_id, round_id=round_id, seed=secrets.randbelow(2 ** 31),
                                             width=context.width, height=context.height))
        return IllustrationRead.model_validate(record)


def _scene_changed(repository: Repository, chat_id: str, record: Round) -> bool:
    current = repository.state_for_round(chat_id, record.id)
    previous_round = repository.session.scalar(select(Round).where(
        Round.chat_id == chat_id, Round.round_no == record.round_no - 1))
    if previous_round is not None:
        previous = repository.state_for_round(chat_id, previous_round.id)
    else:
        previous = repository.session.scalar(select(StateSnapshot).where(
            StateSnapshot.chat_id == chat_id, StateSnapshot.round_id.is_(None)))
    if current is None or previous is None:
        return False
    world, before = current.content.get("世界", {}), previous.content.get("世界", {})
    return any(world.get(key) != before.get(key) for key in ("地点", "日期"))


def auto_illustration(database: Database, chat_id: str, round_id: str) -> IllustrationRead | None:
    """Called after an archive completes; returns the queued job or None when the chat's mode skips it."""
    with database.read() as session:
        repository = Repository(session)
        mode = IllustrationService(repository).settings(chat_id).mode
        if mode == "scene_change":
            has_any = session.scalar(select(Illustration.id).where(Illustration.chat_id == chat_id).limit(1))
            record = repository.get_owned(Round, round_id, chat_id)
            if has_any is not None and not _scene_changed(repository, chat_id, record):
                return None
        elif mode != "every_round":
            return None
    try:
        return request_illustration(database, chat_id, round_id)
    except ConflictError:
        return None


def _advance(database: Database, illustration_id: str, expected: str, **values) -> None:
    with database.transaction() as session:
        result = session.execute(update(Illustration).where(
            Illustration.id == illustration_id, Illustration.status == expected).values(**values))
        if result.rowcount != 1:
            raise NotFoundError("插图任务已不存在或已被中断")


def _fail(database: Database, illustration_id: str, message: str) -> None:
    with database.transaction() as session:
        session.execute(update(Illustration).where(
            Illustration.id == illustration_id, Illustration.status.in_(ACTIVE_STATUSES),
        ).values(status="failed", error=message[:2000]))


def run_illustration(database: Database, client: ModelClient, comfy: ComfyUIClient, storage: ImageStorage,
                     illustration_id: str) -> None:
    try:
        with database.read() as session:
            record = session.get(Illustration, illustration_id)
            if record is None or record.status != "pending":
                return
            chat_id, round_id, seed = record.chat_id, record.round_id, record.seed
            context = _context(Repository(session), chat_id, round_id)
        _advance(database, illustration_id, "pending", status="prompting")
        fields = _prompt_fields(database, client, chat_id, round_id, context)
        _advance(database, illustration_id, "prompting", status="rendering", prompt=fields)
        workflow = fill_workflow(context.workflow, {**fields, "seed": seed, "width": context.width,
                                                    "height": context.height})
        image = comfy.render(context.base_url, workflow)
        file_name = storage.save(chat_id, illustration_id, image)
        _advance(database, illustration_id, "rendering", status="ready", file_name=file_name,
                 media_type=image.media_type)
    except NotFoundError:
        return  # The chat, round or job went away meanwhile.
    except FAILURES as error:
        _fail(database, illustration_id, getattr(error, "message", None) or str(error))
    except Exception:
        logger.exception("Illustration %s failed", illustration_id)
        _fail(database, illustration_id, "插图生成发生内部错误")


def interrupt_unfinished(database: Database) -> None:
    """Jobs live in this process only; after a restart they cannot resume."""
    if not inspect(database.engine).has_table(Illustration.__tablename__):
        return  # Not migrated yet.
    with database.transaction() as session:
        session.execute(update(Illustration).where(Illustration.status.in_(ACTIVE_STATUSES))
                        .values(status="failed", error="服务重启，任务已中断"))


class IllustrationRunner:
    """In-process queue: one job at a time, matching a single local ComfyUI."""

    def __init__(self, database: Database, client: ModelClient, comfy: ComfyUIClient, storage: ImageStorage,
                 executor: Executor | None = None):
        self.database, self.client, self.comfy, self.storage = database, client, comfy, storage
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="illustration")

    def submit(self, illustration_id: str):
        return self.executor.submit(run_illustration, self.database, self.client, self.comfy, self.storage,
                                    illustration_id)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
