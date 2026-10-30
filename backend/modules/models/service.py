import json

from sqlalchemy.exc import IntegrityError

from backend.repository.models import Chat, ModelConfig
from backend.repository.queries import Repository
from backend.schemas.chats import ModelPurpose
from backend.schemas.models import ModelConfigCreate, ModelConfigPatch, ModelConfigRead, ModelConnection
from backend.shared.errors import ConflictError, ModelConfigurationError


def read_config(record: ModelConfig) -> ModelConfigRead:
    fields = {name: getattr(record, name) for name in ModelConfigRead.model_fields if name != "has_api_key"}
    return ModelConfigRead(**fields, has_api_key=bool(record.api_key))


class ModelService:
    def __init__(self, repository: Repository, chat_id: str | None = None):
        self.repository = repository
        self.chat_id = chat_id
        if chat_id is not None:
            repository.get(Chat, chat_id)

    def list(self) -> list[ModelConfigRead]:
        return [read_config(record) for record in self.repository.list_owned(ModelConfig, self.chat_id)]

    def read(self, config_id: str) -> ModelConfigRead:
        return read_config(self.repository.get_owned(ModelConfig, config_id, self.chat_id))

    def create(self, payload: ModelConfigCreate) -> ModelConfigRead:
        values = self._values(payload)
        return read_config(self.repository.add(ModelConfig(chat_id=self.chat_id, **values)))

    def update(self, config_id: str, payload: ModelConfigPatch) -> ModelConfigRead:
        record = self.repository.get_owned(ModelConfig, config_id, self.chat_id)
        for name, value in self._values(payload, exclude_unset=True).items():
            setattr(record, name, value)
        self.repository.session.flush()
        return read_config(record)

    @staticmethod
    def _values(payload, **kwargs) -> dict:
        values = payload.model_dump(exclude={"api_key"}, **kwargs)
        if "api_key" in payload.model_fields_set or isinstance(payload, ModelConfigCreate):
            values["api_key"] = payload.api_key.get_secret_value()
        if "default_parameters" in values:
            try:
                # Reject nonfinite numbers and detach nested mutable objects.
                values["default_parameters"] = json.loads(json.dumps(values["default_parameters"], allow_nan=False))
            except (ValueError, TypeError, RecursionError):
                raise ModelConfigurationError("默认参数必须是有效 JSON 对象") from None
        return values

    def delete(self, config_id: str) -> None:
        try:
            self.repository.delete(self.repository.get_owned(ModelConfig, config_id, self.chat_id))
        except IntegrityError:
            raise ConflictError("这个模型配置仍被其他设置使用，请先解除") from None

    def connection(self, config_id: str) -> ModelConnection:
        record = self.repository.get_owned(ModelConfig, config_id, self.chat_id)
        return ModelConnection(**{name: getattr(record, name) for name in ModelConnection.model_fields})

    def for_purpose(self, purpose: ModelPurpose) -> ModelConnection:
        if self.chat_id is None:
            raise ConflictError("模型用途只能在聊天内选择")
        binding = self.repository.model_binding(self.chat_id, purpose)
        if binding is None:
            raise ConflictError("聊天尚未绑定该用途的模型配置")
        return self.connection(binding.model_config_id)
