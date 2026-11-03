from fastapi import APIRouter, Request

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.archive import ArchiveConfirm, ArchiveProgress, ArchiveRetry, RoundRead
from backend.workflows.archive import confirm_archive, read_progress, retry_archive

router = APIRouter(prefix="/api/chats/{chat_id}", tags=["archive"])


def _options(request: Request) -> dict:
    return {"validator": request.app.state.state_validator,
            "state_recent_summaries": request.app.state.state_recent_summaries,
            "round_recent_summaries": request.app.state.round_summary_recent_summaries}


def _notify(request: Request, progress: ArchiveProgress) -> ArchiveProgress:
    if progress.round.archive_step == "complete":
        hooks = request.app.state.hooks
        hooks.notify(hooks.round_archived, progress.round.chat_id, progress.round.id)
    return progress


@router.post("/archive", response_model=ArchiveProgress, status_code=201)
def confirm(chat_id: str, payload: ArchiveConfirm, request: Request,
            database: DatabaseDependency, client: ModelClientDependency):
    return _notify(request, confirm_archive(database, client, chat_id, payload, **_options(request)))


@router.get("/archive", response_model=ArchiveProgress | None)
def latest(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        repository.get(Chat, chat_id)
        header = repository.latest_round_header(chat_id)
        return read_progress(repository, chat_id, header.id) if header is not None else None


@router.post("/rounds/{round_id}/archive/retry", response_model=ArchiveProgress)
def retry(chat_id: str, round_id: str, payload: ArchiveRetry, request: Request,
          database: DatabaseDependency, client: ModelClientDependency):
    return _notify(request, retry_archive(database, client, chat_id, round_id, payload.expected_step, **_options(request)))


@router.get("/rounds", response_model=list[RoundRead])
def list_rounds(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        repository.get(Chat, chat_id)
        worlds = repository.round_worlds(chat_id)
        return [RoundRead.of(record, worlds.get(record.id)) for record in repository.rounds(chat_id)]


@router.get("/rounds/{round_id}", response_model=ArchiveProgress)
def read(chat_id: str, round_id: str, database: DatabaseDependency):
    with database.read() as session:
        return read_progress(Repository(session), chat_id, round_id)
