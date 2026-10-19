from fastapi import APIRouter, Depends, Response
from backend.llm.recording import recorded_workflow

from backend.api.dependencies import DatabaseDependency, ModelClientDependency
from backend.modules.models.service import ModelService
from backend.repository.queries import Repository
from backend.schemas.models import ModelConfigCreate, ModelConfigPatch, ModelConfigRead, ModelResponse
from backend.schemas.presets import BuiltRequest


def model_router(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["model-configs"])

    def chat_scope(chat_id: str) -> str:
        return chat_id

    def source_scope() -> None:
        return None

    get_scope = chat_scope if "{chat_id}" in prefix else source_scope

    def service(session, chat_id):
        return ModelService(Repository(session), chat_id)

    @router.get("", response_model=list[ModelConfigRead])
    def list_configs(database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).list()

    @router.post("", response_model=ModelConfigRead, status_code=201)
    def create(payload: ModelConfigCreate, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).create(payload)

    @router.get("/{config_id}", response_model=ModelConfigRead)
    def read(config_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).read(config_id)

    @router.patch("/{config_id}", response_model=ModelConfigRead)
    def update(config_id: str, payload: ModelConfigPatch, database: DatabaseDependency,
               chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).update(config_id, payload)

    @router.delete("/{config_id}", status_code=204)
    def delete(config_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            service(session, chat_id).delete(config_id)
        return Response(status_code=204)

    @router.post("/{config_id}/invoke", response_model=ModelResponse)
    @recorded_workflow("direct")
    def invoke(config_id: str, payload: BuiltRequest, database: DatabaseDependency,
               client: ModelClientDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            connection = service(session, chat_id).connection(config_id)
        return client.invoke(connection, payload)

    return router


router = APIRouter()
router.include_router(model_router("/api/model-configs"))
router.include_router(model_router("/api/chats/{chat_id}/model-configs"))
