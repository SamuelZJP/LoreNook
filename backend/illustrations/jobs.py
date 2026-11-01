"""Illustration jobs: prompt text and reference images → ComfyUI → file. Runs after archiving and never touches archive progress."""

from concurrent.futures import Executor, ThreadPoolExecutor
import json
import logging
import secrets

from sqlalchemy import inspect, select, update

from backend.illustrations.comfyui import ComfyUIClient, RenderProgress
from backend.illustrations.errors import IllustrationError
from backend.illustrations.models import Illustration, ImageWorkflow
from backend.illustrations.placeholders import fill_workflow, uses_images, validate_workflow
from backend.illustrations.progress import ProgressBoard
from backend.illustrations.prompt import reference_images, render_prompt
from backend.illustrations.schemas import (
    ACTIVE_STATUSES, IllustrationContext, IllustrationProgress, IllustrationPrompt, IllustrationRead,
)
from backend.illustrations.service import CastService, IllustrationService
from backend.illustrations.storage import ImageStorage
from backend.modules.media import MediaStorage, media_type_of
from backend.repository.database import Database
from backend.repository.models import Chat, Round, StateSnapshot
from backend.repository.queries import Repository
from backend.shared.errors import ConflictError, NotFoundError

logger = logging.getLogger(__name__)

FAILURES = (ConflictError, IllustrationError)


def _context(repository: Repository, chat_id: str, round_id: str, focus_ids: list[str] | None) -> IllustrationContext:
    repository.get(Chat, chat_id)
    settings = IllustrationService(repository).settings(chat_id)
    if settings.mode == "off":
        raise ConflictError("聊天未开启插图")
    if settings.image_workflow_id is None:
        raise ConflictError("请先在插图设置中选择图像工作流")
    record = repository.get_owned(Round, round_id, chat_id)
    if record.archive_step != "complete":
        raise ConflictError("只能为已归档的回合生成插图")
    state = repository.state_for_round(chat_id, round_id)
    if state is None:
        raise ConflictError("回合缺少归档状态")
    workflow = repository.get_owned(ImageWorkflow, settings.image_workflow_id, chat_id)
    focus, others = CastService(repository).resolve_focus(chat_id, settings.focus if focus_ids is None else focus_ids)
    return IllustrationContext(
        user_input=record.user_input, ai_output=record.ai_output, state=state.content, focus=focus, others=others,
        image_workflow_id=workflow.id, base_url=workflow.base_url, workflow=workflow.workflow,
        width=workflow.width, height=workflow.height,
    )


def _inputs(context: IllustrationContext) -> tuple[str, list[str]]:
    """(prompt text, media names). Data management can store anything, so the workflow is checked again here."""
    validate_workflow(context.workflow)
    images = reference_images([*context.focus, *context.others]) if uses_images(context.workflow) else []
    return render_prompt(context, images), images


def preview_prompt(database: Database, chat_id: str, round_id: str, focus: list[str] | None = None) -> IllustrationPrompt:
    """Only render the inputs; nothing is stored or sent to ComfyUI."""
    with database.read() as session:
        context = _context(Repository(session), chat_id, round_id, focus)
    prompt, images = _inputs(context)
    return IllustrationPrompt(image_workflow_id=context.image_workflow_id, focus=[p.name for p in context.focus],
                              prompt=prompt, images=images)


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


def run_illustration(database: Database, comfy: ComfyUIClient, storage: ImageStorage, media: MediaStorage,
                     board: ProgressBoard, illustration_id: str) -> None:
    try:
        with database.read() as session:
            record = session.get(Illustration, illustration_id)
            if record is None or record.status != "pending":
                return
            chat_id, round_id, seed = record.chat_id, record.round_id, record.seed
            focus_ids = [item["id"] for item in record.focus]
            context = _context(Repository(session), chat_id, round_id, focus_ids)
        prompt, images = _inputs(context)
        _advance(database, illustration_id, "pending", status="rendering", prompt={"prompt": prompt})
        board.set(illustration_id, chat_id, IllustrationProgress(status="rendering"))
        uploaded = [comfy.upload_image(context.base_url, name, media.read(name), media_type_of(name)) for name in images]
        workflow = fill_workflow(context.workflow, {"prompt": prompt, "images": json.dumps(uploaded, ensure_ascii=False),
                                                    "seed": seed, "width": context.width, "height": context.height})

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

    def __init__(self, database: Database, comfy: ComfyUIClient, storage: ImageStorage, media: MediaStorage,
                 board: ProgressBoard, executor: Executor | None = None):
        self.database, self.comfy, self.storage, self.media = database, comfy, storage, media
        self.board = board
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="illustration")

    def submit(self, job: IllustrationRead):
        self.board.set(job.id, job.chat_id, IllustrationProgress(status=job.status))
        return self.executor.submit(run_illustration, self.database, self.comfy, self.storage, self.media, self.board, job.id)

    def round_archived(self, chat_id: str, round_id: str) -> None:
        job = auto_illustration(self.database, chat_id, round_id)
        if job is not None:
            self.submit(job)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
