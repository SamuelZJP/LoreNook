"""DeepSeek Chat Completions transport adaptation (non-streaming)."""

from backend.schemas.models import ModelConnection, validate_base_url
from backend.shared.errors import ModelConfigurationError


class DeepSeekChatCompletions:
    api_type = "deepseek_chat_completions"

    def prepare(self, config: ModelConnection, body: dict) -> tuple[str, dict[str, str], dict]:
        base = validate_base_url(config.base_url).rstrip("/")
        model = body.setdefault("model", config.model)
        if not isinstance(model, str) or not model.strip() or any(ord(c) < 32 for c in model):
            raise ModelConfigurationError("DeepSeek model 必须是非空模型名称")
        if not isinstance(body.get("messages"), list) or not body["messages"]:
            raise ModelConfigurationError("DeepSeek 请求必须提供非空 messages 数组")
        if body.get("stream", False) is not False:
            raise ModelConfigurationError("DeepSeek 当前只支持 stream=false 的非流式请求")
        body.setdefault("stream", False)
        key = config.api_key.get_secret_value()
        if key and (not key.isascii() or any(ord(char) < 33 or ord(char) > 126 for char in key)):
            raise ModelConfigurationError("API Key 必须是可见 ASCII 字符，不能包含空格或换行")
        headers = {"authorization": f"Bearer {key}"} if key else {}
        return f"{base}/chat/completions", headers, body
