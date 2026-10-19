from fastapi import APIRouter, Depends, Response

from backend.api.dependencies import DatabaseDependency
from backend.modules.presets.runtime import PresetRuntime
from backend.modules.presets.service import PresetService
from backend.repository.queries import Repository
from backend.schemas.presets import (
    BuiltRequest, ParseInput, ParsedOutput, PresetCreate, PresetPatch, PresetRead,
    WritingMaterials, WritingPreview, WritingPreviewInput,
)
from backend.workflows.preview_writing import preview_writing


def preset_router(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["writing-presets"])

    def chat_scope(chat_id: str) -> str:
        return chat_id

    def source_scope() -> None:
        return None

    get_scope = chat_scope if "{chat_id}" in prefix else source_scope

    def service(session, chat_id):
        return PresetService(Repository(session), chat_id)

    @router.get("", response_model=list[PresetRead])
    def list_presets(database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).list()

    @router.post("", response_model=PresetRead, status_code=201)
    def create(payload: PresetCreate, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).create(payload)

    @router.get("/{preset_id}", response_model=PresetRead)
    def read(preset_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            return service(session, chat_id).read(preset_id)

    @router.patch("/{preset_id}", response_model=PresetRead)
    def update(preset_id: str, payload: PresetPatch, database: DatabaseDependency,
               chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            return service(session, chat_id).update(preset_id, payload)

    @router.delete("/{preset_id}", status_code=204)
    def delete(preset_id: str, database: DatabaseDependency, chat_id: str | None = Depends(get_scope)):
        with database.transaction() as session:
            service(session, chat_id).delete(preset_id)
        return Response(status_code=204)

    @router.post("/{preset_id}/build", response_model=BuiltRequest)
    def build(preset_id: str, payload: WritingMaterials, database: DatabaseDependency,
              chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            source = service(session, chat_id).read(preset_id).source
        return PresetRuntime().build(source, payload)

    @router.post("/{preset_id}/parse", response_model=ParsedOutput)
    def parse(preset_id: str, payload: ParseInput, database: DatabaseDependency,
              chat_id: str | None = Depends(get_scope)):
        with database.read() as session:
            source = service(session, chat_id).read(preset_id).source
        return PresetRuntime().parse(source, payload.response)

    return router


router = APIRouter()
router.include_router(preset_router("/api/writing-presets"))
router.include_router(preset_router("/api/chats/{chat_id}/writing-presets"))


@router.post("/api/chats/{chat_id}/writing-preview", response_model=WritingPreview, tags=["writing-presets"])
def preview(chat_id: str, payload: WritingPreviewInput, database: DatabaseDependency):
    return preview_writing(database, chat_id, payload.user_input)
