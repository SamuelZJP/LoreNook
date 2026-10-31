"""Illustration jobs: model call → ComfyUI → file. Runs after archiving and never touches archive progress."""

from concurrent.futures import Executor, ThreadPoolExecutor
import logging
import secrets

from sqlalchemy import inspect, select, update

from backend.illustrations.comfyui import ComfyUIClient, RenderProgress
from backend.illustrations.errors import IllustrationError
from backend.illustrations.generate import generate_fields
from backend.illustrations.models import Illustration, ImageWorkflow
from backend.illustrations.placeholders import IMAGE_INPUT, fill_workflow, image_inputs, prompt_fields
from backend.illustrations.schemas import (
    ACTIVE_STATUSES, FOCUS_CHAR, IllustrationContext, IllustrationProgress, IllustrationPrompt, IllustrationRead,
)
from backend.illustrations.progress import ProgressBoard
from backend.illustrations.service import CastService, IllustrationService
from backend.illustrations.storage import ImageStorage
from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.definitions.storage import DefinitionStorage
from backend.modules.media import MediaStorage, media_type_of
from backend.modules.models.service import ModelService
from backend.repository.database import Database
from backend.repository.models import Character, Chat, Round, StateSnapshot, UserIdentity
from backend.repository.queries import Repository
from backend.shared.errors import (
    ConflictError, DefinitionTemplateError, ModelCallError, ModelConfigurationError, NotFoundError,
)

logger = logging.getLogger(__name__)

FAILURES = (ConflictError, DefinitionTemplateError, IllustrationError, ModelCallError, ModelConfigurationError)


def _context(repository: Repository, chat_id: str, round_id: str, focus_ids: list[str] | None) -> IllustrationContext:
    repository.get(Chat, chat_id)
    settings = IllustrationService(repository).settings(chat_id)
    if settings.mode == "off":
        raise ConflictError("聊天未开启插图")
    if settings.image_workflow_id is None or settings.model_config_id is None:
        raise ConflictError("请先在插图设置中选择图像工作流和提示词模型")
    record = repository.get_owned(Round, round_id, chat_id)
    if record.archive_step != "complete":
        raise ConflictError("只能为已归档的回合生成插图")
    character = repository.get(Character, repository.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, repository.owner_id(chat_id, UserIdentity))
    state = repository.state_for_round(chat_id, round_id)
    if state is None:
        raise ConflictError("回合缺少归档状态")
    workflow = repository.get_owned(ImageWorkflow, settings.image_workflow_id, chat_id)
    focus, others = CastService(repository).resolve_focus(chat_id, settings.focus if focus_ids is None else focus_ids)
    storage = DefinitionStorage(repository)
    return IllustrationContext(
        chat_id=chat_id, round_id=round_id, round_no=record.round_no,
        user_input=record.user_input, ai_output=record.ai_output, summary=record.summary, state=state.content,
        character_name=character.name, user_name=identity.name,
        character_definitions=storage.read(character_id=character.id),
        user_definitions=storage.read(user_identity_id=identity.id),
        focus=focus, others=others,
        image_workflow_id=workflow.id, base_url=workflow.base_url, workflow=workflow.workflow,
        prompt_template=workflow.prompt_template, width=workflow.width, height=workflow.height,
        fields=prompt_fields(workflow.workflow), image_inputs=image_inputs(workflow.workflow),
        connection=ModelService(repository, chat_id).connection(settings.model_config_id),
    )


def _reference_images(context: IllustrationContext) -> dict[str, str]:
    """Placeholder → media name. A missing reference fails here, before any model call is spent."""
    references = {}
    for placeholder in context.image_inputs:
        position = int(IMAGE_INPUT.fullmatch(placeholder).group(1))
        if position > len(context.focus):
            raise IllustrationError(f"工作流需要第 {position} 位主要人物的参考图，但本次只有 {len(context.focus)} 位主要人物")
        person = context.focus[position - 1]
        if person.reference_image is None:
            where = "请在角色卡中添加画像人物并上传参考图" if person.id == FOCUS_CHAR else "请先上传参考图"
            raise IllustrationError(f"{person.name} 没有参考图，{where}")
        references[placeholder] = person.reference_image
    return references


@recorded_workflow("image_prompt")
def _prompt_fields(database: Database, client: ModelClient, chat_id: str, round_id: str,
                   context: IllustrationContext) -> dict[str, str]:
    return generate_fields(context, client)


def preview_prompt(database: Database, client: ModelClient, chat_id: str, round_id: str,
                   focus: list[str] | None = None) -> IllustrationPrompt:
    """Run only the model step; nothing is stored or sent to ComfyUI."""
    with database.read() as session:
        context = _context(Repository(session), chat_id, round_id, focus)
    fields = _prompt_fields(database, client, chat_id, round_id, context)
    return IllustrationPrompt(image_workflow_id=context.image_workflow_id, focus=[p.name for p in context.focus], fields=fields)


def request_illustration(database: Database, chat_id: str, round_id: str, focus: list[str] | None = None) -> IllustrationRead:
    with database.transaction() as session:
        repository = Repository(session)
        context = _context(repository, chat_id, round_id, focus)
        active = session.scalar(select(Illustration.id).where(
            Illustration.round_id == round_id, Illustration.status.in_(ACTIVE_STATUSES)))
        if active is not None:
            raise ConflictError("本回合插图正在生成")
        record = repository.add(Illustration(
            chat_id=chat_id, round_id=round_id, seed=secrets.randbelow(2 ** 31), width=context.width, height=context.height,
            focus=[{"id": person.id, "name": person.name} for person in context.focus],
        ))
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
    """After an archive completes: the queued job, or None when the chat's mode skips this round."""
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
                     media: MediaStorage, board: ProgressBoard, illustration_id: str) -> None:
    try:
        with database.read() as session:
            record = session.get(Illustration, illustration_id)
            if record is None or record.status != "pending":
                return
            chat_id, round_id, seed = record.chat_id, record.round_id, record.seed
            focus_ids = [item["id"] for item in record.focus]
            context = _context(Repository(session), chat_id, round_id, focus_ids)
        references = _reference_images(context)
        _advance(database, illustration_id, "pending", status="prompting")
        board.set(illustration_id, chat_id, IllustrationProgress(status="prompting"))
        fields = _prompt_fields(database, client, chat_id, round_id, context)
        _advance(database, illustration_id, "prompting", status="rendering", prompt=fields)
        board.set(illustration_id, chat_id, IllustrationProgress(status="rendering"))
        uploaded = {placeholder: comfy.upload_image(context.base_url, name, media.read(name), media_type_of(name))
                    for placeholder, name in references.items()}
        workflow = fill_workflow(context.workflow, {**fields, **uploaded, "seed": seed, "width": context.width,
                                                    "height": context.height})

        def report(progress: RenderProgress) -> None:
            board.set(illustration_id, chat_id, IllustrationProgress(
                status="rendering", queued=progress.queued, node=progress.node, value=progress.value, max=progress.max))

        image = comfy.render(context.base_url, workflow, report)
        file_name = storage.save(chat_id, illustration_id, image)
        _advance(database, illustration_id, "rendering", status="ready", file_name=file_name,
                 media_type=image.media_type)
    except NotFoundError as error:
        # Usually the chat went away, and then this changes nothing; otherwise a resource is missing.
        _fail(database, illustration_id, str(error))
    except FAILURES as error:
        _fail(database, illustration_id, getattr(error, "message", None) or str(error))
    except Exception:
        logger.exception("Illustration %s failed", illustration_id)
        _fail(database, illustration_id, "插图生成发生内部错误")
    finally:
        # After the final status is committed, so a browser reacting to this reads the outcome.
        board.clear(illustration_id)


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
                 media: MediaStorage, board: ProgressBoard, executor: Executor | None = None):
        self.database, self.client, self.comfy, self.storage, self.media = database, client, comfy, storage, media
        self.board = board
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="illustration")

    def submit(self, job: IllustrationRead):
        self.board.set(job.id, job.chat_id, IllustrationProgress(status=job.status))
        return self.executor.submit(run_illustration, self.database, self.client, self.comfy, self.storage, self.media,
                                    self.board, job.id)

    def round_archived(self, chat_id: str, round_id: str) -> None:
        job = auto_illustration(self.database, chat_id, round_id)
        if job is not None:
            self.submit(job)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
