from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from backend.api.dependencies import DatabaseDependency
from backend.illustrations.jobs import preview_prompt, request_illustration
from backend.illustrations.models import Illustration
from backend.illustrations.progress import progress_events
from backend.illustrations.schemas import (
    AppearanceInput, CastMemberRead, CastReplace, FocusOptions, IllustrationPatch, IllustrationPrompt, IllustrationRead,
    IllustrationRequest, IllustrationSettings, IllustrationSetup, ImageWorkflowCreate, ImageWorkflowImport,
    ImageWorkflowPatch, ImageWorkflowRead,
)
from backend.illustrations.service import CastService, IllustrationService, ImageWorkflowService
from backend.repository.models import Character, Chat, UserIdentity
from backend.repository.queries import Repository
from backend.shared.errors import NotFoundError


def workflow_router(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["image-workflows"])

    def chat_scope(chat_id: str) -> str:
        return chat_id

    def source_scope() -> None:
        return None

    get_scope = chat_scope if "{chat_id}" in prefix else source_scope

    def service(session, chat_id):
        return ImageWorkflowService(Repository(session), chat_id)

    @router.get("", response_model=list[ImageWorkflowRead])
    def list_workflows(database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).list()

    @router.post("", response_model=ImageWorkflowRead, status_code=201)
    def create(payload: ImageWorkflowCreate, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).create(payload)

    @router.get("/{workflow_id}", response_model=ImageWorkflowRead)
    def read(workflow_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).read(workflow_id)

    @router.patch("/{workflow_id}", response_model=ImageWorkflowRead)
    def update(workflow_id: str, payload: ImageWorkflowPatch, database: DatabaseDependency,
               chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).update(workflow_id, payload)

    @router.delete("/{workflow_id}", status_code=204)
    def delete(workflow_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            service(session, chat_id).delete(workflow_id)
        return Response(status_code=204)

    return router


router = APIRouter()


@router.post("/api/chats/{chat_id}/image-workflows/import", response_model=ImageWorkflowRead, status_code=201,
             tags=["image-workflows"])
def import_workflow(chat_id: str, payload: ImageWorkflowImport, database: DatabaseDependency):
    with database.transaction() as session:
        return ImageWorkflowService(Repository(session), chat_id).import_source(payload.source_id)


router.include_router(workflow_router("/api/image-workflows"))
router.include_router(workflow_router("/api/chats/{chat_id}/image-workflows"))

cast = APIRouter(prefix="/api", tags=["illustration-cast"])


def _chat_character(repository: Repository, chat_id: str) -> str:
    return repository.owner_id(chat_id, Character)


def _chat_identity(repository: Repository, chat_id: str) -> str:
    return repository.owner_id(chat_id, UserIdentity)


def _library_character(repository: Repository, character_id: str) -> str:
    return repository.get_owned(Character, character_id, None).id


def _library_identity(repository: Repository, identity_id: str) -> str:
    return repository.get_owned(UserIdentity, identity_id, None).id


@cast.get("/characters/{owner_id}/cast", response_model=list[CastMemberRead])
def read_cast(owner_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        return CastService(repository).members(_library_character(repository, owner_id))


@cast.put("/characters/{owner_id}/cast", response_model=list[CastMemberRead])
def replace_cast(owner_id: str, payload: CastReplace, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        return CastService(repository).replace(_library_character(repository, owner_id), payload.members)


@cast.get("/chats/{owner_id}/cast", response_model=list[CastMemberRead])
def read_chat_cast(owner_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        return CastService(repository).members(_chat_character(repository, owner_id))


@cast.put("/chats/{owner_id}/cast", response_model=list[CastMemberRead])
def replace_chat_cast(owner_id: str, payload: CastReplace, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        return CastService(repository).replace(_chat_character(repository, owner_id), payload.members)


@cast.get("/user-identities/{owner_id}/appearance", response_model=AppearanceInput)
def read_appearance(owner_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        return CastService(repository).appearance(_library_identity(repository, owner_id))


@cast.put("/user-identities/{owner_id}/appearance", response_model=AppearanceInput)
def set_appearance(owner_id: str, payload: AppearanceInput, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        return CastService(repository).set_appearance(_library_identity(repository, owner_id), payload)


@cast.get("/chats/{owner_id}/appearance", response_model=AppearanceInput)
def read_chat_appearance(owner_id: str, database: DatabaseDependency):
    with database.read() as session:
        repository = Repository(session)
        return CastService(repository).appearance(_chat_identity(repository, owner_id))


@cast.put("/chats/{owner_id}/appearance", response_model=AppearanceInput)
def set_chat_appearance(owner_id: str, payload: AppearanceInput, database: DatabaseDependency):
    with database.transaction() as session:
        repository = Repository(session)
        return CastService(repository).set_appearance(_chat_identity(repository, owner_id), payload)


chat = APIRouter(prefix="/api/chats/{chat_id}", tags=["illustrations"])


@chat.get("/focus-options", response_model=FocusOptions)
def focus_options(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return CastService(Repository(session)).focus_options(chat_id)


@chat.get("/illustration-settings", response_model=IllustrationSettings)
def read_settings(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return IllustrationService(Repository(session)).read_settings(chat_id)


@chat.put("/illustration-settings", response_model=IllustrationSettings)
def replace_settings(chat_id: str, payload: IllustrationSettings, database: DatabaseDependency):
    with database.transaction() as session:
        return IllustrationService(Repository(session)).replace_settings(chat_id, payload)


@chat.post("/illustration-setup", response_model=IllustrationSettings)
def setup(chat_id: str, payload: IllustrationSetup, database: DatabaseDependency):
    with database.transaction() as session:
        return IllustrationService(Repository(session)).setup(chat_id, payload)


@chat.get("/illustrations", response_model=list[IllustrationRead])
def list_illustrations(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return IllustrationService(Repository(session)).list(chat_id)


@chat.get("/illustrations/progress", response_class=StreamingResponse)
def progress(chat_id: str, request: Request, database: DatabaseDependency):
    """Server-sent events: {illustration id: IllustrationProgress} for the chat's running jobs."""
    with database.read() as session:
        Repository(session).get(Chat, chat_id)
    # no-transform keeps proxies from compressing, and so holding back, the small events.
    return StreamingResponse(progress_events(request.app.state.illustration_progress, chat_id),
                             media_type="text/event-stream",
                             headers={"cache-control": "no-cache, no-transform", "x-accel-buffering": "no"})


@chat.post("/rounds/{round_id}/illustrations", response_model=IllustrationRead, status_code=202)
def generate(chat_id: str, round_id: str, request: Request, database: DatabaseDependency,
             payload: IllustrationRequest | None = None):
    """Queue a new attempt; earlier attempts are kept and the newest is shown."""
    record = request_illustration(database, chat_id, round_id, payload.focus if payload else None)
    request.app.state.illustrations.submit(record)
    return record


@chat.post("/rounds/{round_id}/illustration-prompt", response_model=IllustrationPrompt)
def prompt(chat_id: str, round_id: str, database: DatabaseDependency, payload: IllustrationRequest | None = None):
    return preview_prompt(database, chat_id, round_id, payload.focus if payload else None)


@chat.patch("/illustrations/{illustration_id}", response_model=IllustrationRead)
def update(chat_id: str, illustration_id: str, payload: IllustrationPatch, database: DatabaseDependency):
    with database.transaction() as session:
        return IllustrationService(Repository(session)).update(chat_id, illustration_id, payload)


@chat.get("/illustrations/{illustration_id}/image")
def image(chat_id: str, illustration_id: str, request: Request, database: DatabaseDependency):
    with database.read() as session:
        record = Repository(session).get_owned(Illustration, illustration_id, chat_id)
        file_name, media_type = record.file_name, record.media_type
    if file_name is None:
        raise NotFoundError("插图尚未生成")
    # Each attempt has its own ID and file, so the bytes behind a URL never change.
    return FileResponse(request.app.state.image_storage.path(file_name), media_type=media_type,
                        headers={"cache-control": "private, max-age=31536000, immutable"})


router.include_router(cast)
router.include_router(chat)
