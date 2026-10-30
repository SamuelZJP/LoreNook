from fastapi import APIRouter, Request

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.archive import ArchiveConfirm, ArchiveProgress, ArchiveRetry, RoundRead
from backend.workflows.archive import confirm_archive, read_progress, retry_archive
from backend.workflows.illustration import auto_illustration

router = APIRouter(prefix="/api/chats/{chat_id}", tags=["archive"])


def _options(request: Request) -> dict:
    return {"validator": request.app.state.state_validator,
            "state_recent_summaries": request.app.state.state_recent_summaries,
            "round_recent_summaries": request.app.state.round_summary_recent_summaries}


def _illustrate(request: Request, database, progress: ArchiveProgress) -> ArchiveProgress:
    if progress.round.archive_step == "complete":
        job = auto_illustration(database, progress.round.chat_id, progress.round.id)
        if job is not None:
            request.app.state.illustrations.submit(job.id)
    return progress


@router.post("/archive", response_model=ArchiveProgress, status_code=201)
def confirm(chat_id: str, payload: ArchiveConfirm, request: Request,
            database: DatabaseDependency, client: ModelClientDependency):
    return _illustrate(request, database, confirm_archive(database, client, chat_id, payload, **_options(request)))


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
    return _illustrate(request, database, retry_archive(database, client, chat_id, round_id, payload.expected_step,
                                                       **_options(request)))


@router.get("/rounds", response_model=list[RoundRead])
def list_rounds(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        repository.get(Chat, chat_id)
        return [RoundRead.model_validate(record) for record in repository.rounds(chat_id)]


@router.get("/rounds/{round_id}", response_model=ArchiveProgress)
def read(chat_id: str, round_id: str, database: DatabaseDependency):
    with database.read() as session:
        return read_progress(Repository(session), chat_id, round_id)
