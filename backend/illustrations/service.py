from sqlalchemy import select

from backend.illustrations.errors import IllustrationError
from backend.illustrations.models import (
    CastMember, ChatIllustrationSettings, IdentityAppearance, Illustration, ImageWorkflow,
)
from backend.illustrations.placeholders import image_inputs, prompt_fields
from backend.illustrations.schemas import (
    FOCUS_CHAR, FOCUS_USER, AppearanceInput, CastMemberInput, CastMemberRead, FocusOption, FocusOptions,
    IllustrationPatch, IllustrationRead, IllustrationSettings, IllustrationSetup, ImageWorkflowCreate,
    ImageWorkflowPatch, ImageWorkflowRead, Subject,
)
from backend.illustrations.templates import default_template
from backend.modules.chats.service import ChatService
from backend.modules.media import MEDIA_NAME
from backend.repository.models import Character, Chat, ModelConfig, UserIdentity
from backend.repository.queries import Repository
from backend.shared.errors import ConflictError


def read_workflow(record: ImageWorkflow) -> ImageWorkflowRead:
    derived = {"prompt_fields", "image_inputs"}
    fields = {name: getattr(record, name) for name in ImageWorkflowRead.model_fields if name not in derived}
    return ImageWorkflowRead(**fields, prompt_fields=prompt_fields(record.workflow), image_inputs=image_inputs(record.workflow))


def _check_image(name: str | None) -> str | None:
    if name is not None and not MEDIA_NAME.fullmatch(name):
        raise IllustrationError("参考图必须是通过上传得到的图片")
    return name


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
        values = payload.model_dump()
        values["prompt_template"] = values["prompt_template"] or default_template(bool(image_inputs(payload.workflow)))
        return read_workflow(self.repository.add(ImageWorkflow(chat_id=self.chat_id, **values)))

    def update(self, workflow_id: str, payload: ImageWorkflowPatch) -> ImageWorkflowRead:
        record = self.repository.get_owned(ImageWorkflow, workflow_id, self.chat_id)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, name, value)
        if not record.prompt_template:
            record.prompt_template = default_template(bool(image_inputs(record.workflow)))
        self.repository.session.flush()
        return read_workflow(record)

    def delete(self, workflow_id: str) -> None:
        record = self.repository.get_owned(ImageWorkflow, workflow_id, self.chat_id)
        if self.chat_id is not None and IllustrationService(self.repository).settings(self.chat_id).image_workflow_id == workflow_id:
            raise ConflictError("请先在插图设置中切换或清空该图像工作流")
        self.repository.delete(record)

    def import_source(self, source_id: str) -> ImageWorkflowRead:
        source = self.repository.get_owned(ImageWorkflow, source_id, None)
        return read_workflow(self.repository.add(ImageWorkflow(
            chat_id=self.chat_id, name=source.name, base_url=source.base_url, workflow=source.workflow,
            prompt_template=source.prompt_template, width=source.width, height=source.height,
        )))


class CastService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def _members(self, character_id: str) -> list[CastMember]:
        return list(self.repository.session.scalars(select(CastMember).where(CastMember.character_id == character_id)
                                                    .order_by(CastMember.order, CastMember.id)))

    def members(self, character_id: str) -> list[CastMemberRead]:
        return [CastMemberRead.model_validate(record) for record in self._members(character_id)]

    def replace(self, character_id: str, members: list[CastMemberInput]) -> list[CastMemberRead]:
        existing = {record.id: record for record in self._members(character_id)}
        kept = {item.id for item in members if item.id is not None}
        if kept - set(existing):
            raise ConflictError("画像人物已变化，请刷新后再保存")
        for record_id, record in existing.items():
            if record_id not in kept:
                self.repository.delete(record)
        for order, item in enumerate(members):
            values = {"order": order, "name": item.name, "appearance": item.appearance,
                      "reference_image": _check_image(item.reference_image)}
            if item.id is None:
                self.repository.add(CastMember(character_id=character_id, **values))
            else:
                for name, value in values.items():
                    setattr(existing[item.id], name, value)
        self.repository.session.flush()
        return self.members(character_id)

    def appearance(self, identity_id: str) -> AppearanceInput:
        record = self.repository.session.get(IdentityAppearance, identity_id)
        return AppearanceInput.model_validate(record) if record is not None else AppearanceInput()

    def set_appearance(self, identity_id: str, payload: AppearanceInput) -> AppearanceInput:
        _check_image(payload.reference_image)
        record = self.repository.session.get(IdentityAppearance, identity_id)
        if record is None:
            record = self.repository.add(IdentityAppearance(user_identity_id=identity_id))
        record.appearance, record.reference_image = payload.appearance, payload.reference_image
        self.repository.session.flush()
        return self.appearance(identity_id)

    def copy_for_chat(self, session, chat_id: str, payload) -> None:
        """Chat-created hook: a chat gets its own copy, like the rest of the character card."""
        service = ChatService(self.repository)
        character_id = service.owner_id(chat_id, Character)
        identity_id = service.owner_id(chat_id, UserIdentity)
        for member in self._members(payload.character_id):
            self.repository.add(CastMember(character_id=character_id, order=member.order, name=member.name,
                                           appearance=member.appearance, reference_image=member.reference_image))
        source = session.get(IdentityAppearance, payload.user_identity_id)
        if source is not None:
            self.repository.add(IdentityAppearance(user_identity_id=identity_id, appearance=source.appearance,
                                                   reference_image=source.reference_image))

    def _subjects(self, chat_id: str) -> tuple[list[Subject], Subject, Subject]:
        """(cast, the character card itself, the user's persona)"""
        service = ChatService(self.repository)
        character = self.repository.get(Character, service.owner_id(chat_id, Character))
        identity = self.repository.get(UserIdentity, service.owner_id(chat_id, UserIdentity))
        cast = [Subject(id=m.id, name=m.name, appearance=m.appearance, reference_image=m.reference_image)
                for m in self._members(character.id)]
        look = self.appearance(identity.id)
        return (cast, Subject(id=FOCUS_CHAR, name=character.name),
                Subject(id=FOCUS_USER, name=identity.name, appearance=look.appearance, reference_image=look.reference_image))

    def focus_options(self, chat_id: str) -> FocusOptions:
        cast, char, user = self._subjects(chat_id)
        # A multi-protagonist card's name is not a person, so it is only offered without a cast.
        people = [*(cast or [char]), user]
        return FocusOptions(options=[FocusOption(id=p.id, name=p.name, has_reference=p.reference_image is not None) for p in people],
                            default=[(cast or [char])[0].id])

    def resolve_focus(self, chat_id: str, requested: list[str]) -> tuple[list[Subject], list[Subject]]:
        """(main characters, everyone else). Choices that no longer exist are dropped."""
        cast, char, user = self._subjects(chat_id)
        people = {p.id: p for p in [*(cast or [char]), user]}
        focus = [people[i] for i in dict.fromkeys(requested) if i in people] or [(cast or [char])[0]]
        chosen = {p.id for p in focus}
        return focus, [p for p in people.values() if p.id not in chosen]


class IllustrationService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def settings(self, chat_id: str) -> IllustrationSettings:
        record = self.repository.session.get(ChatIllustrationSettings, chat_id)
        return IllustrationSettings.model_validate(record) if record is not None else IllustrationSettings()

    def read_settings(self, chat_id: str) -> IllustrationSettings:
        self.repository.get(Chat, chat_id)
        return self.settings(chat_id)

    def replace_settings(self, chat_id: str, payload: IllustrationSettings) -> IllustrationSettings:
        self.repository.get(Chat, chat_id)
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
        return self.settings(chat_id)

    def _chat_model(self, chat_id: str, source_id: str) -> str:
        """A chat copy of a library model config, reusing an identical copy it already has."""
        source = self.repository.get_owned(ModelConfig, source_id, None)
        fields = ("name", "api_type", "base_url", "api_key", "model", "default_parameters")
        for record in self.repository.list_owned(ModelConfig, chat_id):
            if all(getattr(record, name) == getattr(source, name) for name in fields):
                return record.id
        return self.repository.add(ModelConfig(chat_id=chat_id, **{name: getattr(source, name) for name in fields})).id

    def setup(self, chat_id: str, payload: IllustrationSetup) -> IllustrationSettings:
        workflow_id = (ImageWorkflowService(self.repository, chat_id).import_source(payload.image_workflow_id).id
                       if payload.image_workflow_id is not None else None)
        model_id = self._chat_model(chat_id, payload.model_config_id) if payload.model_config_id is not None else None
        return self.replace_settings(chat_id, IllustrationSettings(mode=payload.mode, image_workflow_id=workflow_id,
                                                                   model_config_id=model_id))

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
