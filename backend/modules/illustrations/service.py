from sqlalchemy import select

from backend.modules.illustrations.workflow import prompt_fields
from backend.repository.models import (
    Chat, ChatIllustrationSettings, Illustration, ImageWorkflow, ModelConfig,
)
from backend.repository.queries import Repository
from backend.schemas.illustrations import (
    IllustrationPatch, IllustrationRead, IllustrationSettings, ImageWorkflowCreate, ImageWorkflowPatch,
    ImageWorkflowRead,
)
from backend.shared.errors import ConflictError


def read_workflow(record: ImageWorkflow) -> ImageWorkflowRead:
    fields = {name: getattr(record, name) for name in ImageWorkflowRead.model_fields if name != "prompt_fields"}
    return ImageWorkflowRead(**fields, prompt_fields=prompt_fields(record.workflow))


class ImageWorkflowService:
    def __init__(self, repository: Repository, chat_id: str | None = None):
        self.repository = repository
        self.chat_id = chat_id
        if chat_id is not None:
            repository.get(Chat, chat_id)

    def list(self) -> list[ImageWorkflowRead]:
        return [read_workflow(record) for record in self.repository.list_owned(ImageWorkflow, self.chat_id)]

    def read(self, workflow_id: str) -> ImageWorkflowRead:
        return read_workflow(self.repository.get_owned(ImageWorkflow, workflow_id, self.chat_id))

    def create(self, payload: ImageWorkflowCreate) -> ImageWorkflowRead:
        return read_workflow(self.repository.add(ImageWorkflow(chat_id=self.chat_id, **payload.model_dump())))

    def update(self, workflow_id: str, payload: ImageWorkflowPatch) -> ImageWorkflowRead:
        record = self.repository.get_owned(ImageWorkflow, workflow_id, self.chat_id)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, name, value)
        self.repository.session.flush()
        return read_workflow(record)

    def delete(self, workflow_id: str) -> None:
        record = self.repository.get_owned(ImageWorkflow, workflow_id, self.chat_id)
        if self.chat_id is not None and IllustrationService(self.repository).settings(self.chat_id).image_workflow_id == workflow_id:
            raise ConflictError("请先在插图设置中切换或清空该图像工作流")
        self.repository.delete(record)


class IllustrationService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def settings(self, chat_id: str) -> IllustrationSettings:
        record = self.repository.session.get(ChatIllustrationSettings, chat_id)
        return IllustrationSettings.model_validate(record) if record is not None else IllustrationSettings()

    def replace_settings(self, chat_id: str, payload: IllustrationSettings) -> None:
        if payload.image_workflow_id is not None:
            self.repository.get_owned(ImageWorkflow, payload.image_workflow_id, chat_id)
        if payload.model_config_id is not None:
            self.repository.get_owned(ModelConfig, payload.model_config_id, chat_id)
        record = self.repository.session.get(ChatIllustrationSettings, chat_id)
        if record is None:
            record = self.repository.add(ChatIllustrationSettings(chat_id=chat_id))
        for name, value in payload.model_dump().items():
            setattr(record, name, value)
        self.repository.session.flush()

    def list(self, chat_id: str) -> list[IllustrationRead]:
        self.repository.get(Chat, chat_id)
        records = self.repository.session.scalars(select(Illustration).where(Illustration.chat_id == chat_id)
                                                  .order_by(Illustration.created_at, Illustration.id))
        return [IllustrationRead.model_validate(record) for record in records]

    def update(self, chat_id: str, illustration_id: str, payload: IllustrationPatch) -> IllustrationRead:
        record = self.repository.get_owned(Illustration, illustration_id, chat_id)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, name, value)
        self.repository.session.flush()
        return IllustrationRead.model_validate(record)
