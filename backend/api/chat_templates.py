from fastapi import APIRouter, Response

from backend.api.dependencies import DatabaseDependency
from backend.modules.chat_templates.service import ChatTemplateService
from backend.repository.queries import Repository
from backend.schemas.chat_templates import ChatTemplateCreate, ChatTemplatePatch, ChatTemplateRead

router = APIRouter(prefix="/api/chat-templates", tags=["chat-templates"])


@router.get("", response_model=list[ChatTemplateRead])
def list_templates(database: DatabaseDependency):
    with database.read() as session:
        return ChatTemplateService(Repository(session)).list()


@router.post("", response_model=ChatTemplateRead, status_code=201)
def create(payload: ChatTemplateCreate, database: DatabaseDependency):
    with database.transaction() as session:
        return ChatTemplateService(Repository(session)).create(payload)


@router.patch("/{template_id}", response_model=ChatTemplateRead)
def update(template_id: str, payload: ChatTemplatePatch, database: DatabaseDependency):
    with database.transaction() as session:
        return ChatTemplateService(Repository(session)).update(template_id, payload)


@router.delete("/{template_id}", status_code=204)
def delete(template_id: str, database: DatabaseDependency):
    with database.transaction() as session:
        ChatTemplateService(Repository(session)).delete(template_id)
    return Response(status_code=204)
