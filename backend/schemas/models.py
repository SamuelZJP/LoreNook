from typing import Annotated

from pydantic import Field, JsonValue, SecretStr, field_validator

from backend.schemas.common import Contract, Name, PatchContract
from backend.shared.errors import ModelConfigurationError

DEFAULT_TIMEOUT_SECONDS = 300
TimeoutSeconds = Annotated[int, Field(ge=10, le=1800)]


def validate_base_url(value: str) -> str:
    from urllib.parse import urlsplit
    import httpx

    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or "?" in value or "#" in value
                or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError
        parsed.port
        if not httpx.URL(value).host:
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        raise ModelConfigurationError("base_url 必须是无鉴权、查询参数或片段的 HTTP(S) 接口根地址") from None
    return value


class ModelConfigCreate(Contract):
    name: Name
    api_type: Name
    base_url: str
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    model: Name
    default_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    timeout_seconds: TimeoutSeconds = DEFAULT_TIMEOUT_SECONDS
    streaming: bool = False

    @field_validator("base_url")
    @classmethod
    def check_url(cls, value):
        return validate_base_url(value)


class ModelConfigPatch(PatchContract):
    name: Name | None = None
    api_type: Name | None = None
    base_url: str | None = None
    api_key: SecretStr | None = None
    model: Name | None = None
    default_parameters: dict[str, JsonValue] | None = None
    timeout_seconds: TimeoutSeconds | None = None
    streaming: bool | None = None

    @field_validator("base_url")
    @classmethod
    def check_url(cls, value):
        return validate_base_url(value) if value is not None else value


class ModelConfigRead(Contract):
    id: str
    chat_id: str | None
    name: str
    api_type: str
    base_url: str
    model: str
    default_parameters: dict[str, JsonValue]
    timeout_seconds: int
    streaming: bool
    has_api_key: bool


class ModelConnection(Contract):
    """Detached internal call settings. Never use this as an HTTP response model."""
    api_type: str
    base_url: str
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    model: str
    default_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    streaming: bool = False


class ModelResponse(Contract):
    response: dict[str, JsonValue]
