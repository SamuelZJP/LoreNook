from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.modules.illustrations.service import IllustrationService, ImageWorkflowService
from backend.repository.models import Illustration
from backend.repository.queries import Repository
from backend.schemas.illustrations import (
    IllustrationPatch, IllustrationPrompt, IllustrationRead, ImageWorkflowCreate, ImageWorkflowPatch,
    ImageWorkflowRead,
)
from backend.shared.errors import NotFoundError
from backend.workflows.illustration import preview_prompt, request_illustration


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
router.include_router(workflow_router("/api/image-workflows"))
router.include_router(workflow_router("/api/chats/{chat_id}/image-workflows"))

chat = APIRouter(prefix="/api/chats/{chat_id}", tags=["illustrations"])


@chat.get("/illustrations", response_model=list[IllustrationRead])
def list_illustrations(chat_id: str, database: DatabaseDependency):
    with database.read() as session:
        return IllustrationService(Repository(session)).list(chat_id)


@chat.post("/rounds/{round_id}/illustrations", response_model=IllustrationRead, status_code=202)
def generate(chat_id: str, round_id: str, request: Request, database: DatabaseDependency):
    """Queue a new attempt; earlier attempts are kept and the newest is shown."""
    record = request_illustration(database, chat_id, round_id)
    request.app.state.illustrations.submit(record.id)
    return record


@chat.post("/rounds/{round_id}/illustration-prompt", response_model=IllustrationPrompt)
def prompt(chat_id: str, round_id: str, database: DatabaseDependency, client: ModelClientDependency):
    return preview_prompt(database, client, chat_id, round_id)


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


router.include_router(chat)
