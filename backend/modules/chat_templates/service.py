from backend.repository.models import ChatTemplate
from backend.repository.queries import Repository
from backend.schemas.chat_templates import ChatTemplateCreate, ChatTemplatePatch, ChatTemplateRead


class ChatTemplateService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def list(self) -> list[ChatTemplateRead]:
        return [ChatTemplateRead.model_validate(record) for record in self.repository.chat_templates()]

    def create(self, payload: ChatTemplateCreate) -> ChatTemplateRead:
        if payload.is_default:
            self.repository.clear_default_template()
        record = self.repository.add(ChatTemplate(
            name=payload.name, is_default=payload.is_default, settings=payload.settings.model_dump(mode="json"),
        ))
        return ChatTemplateRead.model_validate(record)

    def update(self, template_id: str, payload: ChatTemplatePatch) -> ChatTemplateRead:
        record = self.repository.get(ChatTemplate, template_id)
        if payload.is_default:
            self.repository.clear_default_template()
        if payload.name is not None:
            record.name = payload.name
        if payload.is_default is not None:
            record.is_default = payload.is_default
        if payload.settings is not None:
            record.settings = payload.settings.model_dump(mode="json")
        self.repository.session.flush()
        return ChatTemplateRead.model_validate(record)

    def delete(self, template_id: str) -> None:
        self.repository.delete(self.repository.get(ChatTemplate, template_id))
