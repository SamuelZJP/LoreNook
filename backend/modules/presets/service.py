from backend.repository.models import Chat, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.presets import PresetCreate, PresetPatch, PresetRead
from backend.shared.errors import ConflictError


class PresetService:
    def __init__(self, repository: Repository, chat_id: str | None = None):
        self.repository = repository
        self.chat_id = chat_id
        if chat_id is not None:
            repository.get(Chat, chat_id)

    def list(self) -> list[PresetRead]:
        return [PresetRead.model_validate(record) for record in
                self.repository.list_owned(WritingPreset, self.chat_id)]

    def read(self, preset_id: str) -> PresetRead:
        return PresetRead.model_validate(self.repository.get_owned(WritingPreset, preset_id, self.chat_id))

    def create(self, payload: PresetCreate) -> PresetRead:
        return PresetRead.model_validate(self.repository.add(
            WritingPreset(chat_id=self.chat_id, **payload.model_dump())
        ))

    def update(self, preset_id: str, payload: PresetPatch) -> PresetRead:
        record = self.repository.get_owned(WritingPreset, preset_id, self.chat_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, key, value)
        self.repository.session.flush()
        return PresetRead.model_validate(record)

    def delete(self, preset_id: str) -> None:
        record = self.repository.get_owned(WritingPreset, preset_id, self.chat_id)
        if self.chat_id is not None:
            chat = self.repository.get(Chat, self.chat_id)
            if chat.writing_preset_id == preset_id:
                raise ConflictError("请先切换或清空聊天当前选用的写作预设")
        self.repository.delete(record)
