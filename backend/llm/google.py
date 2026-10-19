"""Google GenerateContent REST request adaptation; response parsing is the preset's job."""

import re

from backend.schemas.models import ModelConnection, validate_base_url
from backend.shared.errors import ModelConfigurationError


class GoogleGenerateContent:
    api_type = "google_generate_content"

    def prepare(self, config: ModelConnection, body: dict) -> tuple[str, dict[str, str], dict]:
        base = validate_base_url(config.base_url).rstrip("/")
        model = body.pop("model", config.model)
        if isinstance(model, str) and model.startswith("models/"):
            model = model[len("models/"):]
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", model):
            raise ModelConfigurationError("Google model 必须是模型名称，可带 models/ 前缀")
        if not isinstance(body.get("contents"), list) or not body["contents"]:
            raise ModelConfigurationError("Google 请求必须提供非空 contents 数组")
        key = config.api_key.get_secret_value()
        if key and (not key.isascii() or any(ord(char) < 33 or ord(char) > 126 for char in key)):
            raise ModelConfigurationError("API Key 必须是可见 ASCII 字符，不能包含空格或换行")
        headers = {"x-goog-api-key": key} if key else {}
        return f"{base}/models/{model}:generateContent", headers, body
