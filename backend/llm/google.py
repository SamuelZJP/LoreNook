"""Google GenerateContent REST request adaptation; response parsing is the preset's job."""

import re

from backend.schemas.models import ModelConnection, validate_base_url
from backend.shared.errors import ModelConfigurationError

_TEXT_KEYS = {"text", "thought", "thoughtSignature"}


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
        method = "streamGenerateContent?alt=sse" if config.streaming else "generateContent"
        return f"{base}/models/{model}:{method}", headers, body

    def join_stream(self, events: list[dict]) -> dict:
        """One GenerateContentResponse from its chunks; raises ValueError if any candidate never finished."""
        result: dict = {}
        candidates: dict[int, dict] = {}
        for event in events:
            for key, value in event.items():
                if key != "candidates" and value is not None:
                    result[key] = value
            for chunk in event.get("candidates") or []:
                index = chunk.get("index", 0)
                candidate = candidates.setdefault(index, {"content": {"parts": []}})
                for key, value in chunk.items():
                    if key == "content":
                        if value.get("role") is not None:
                            candidate["content"]["role"] = value["role"]
                        for part in value.get("parts") or []:
                            _add_part(candidate["content"]["parts"], part)
                    elif value is not None:
                        candidate[key] = value
        if candidates:
            if any("finishReason" not in candidate for candidate in candidates.values()):
                raise ValueError("stream ended before every candidate finished")
            result["candidates"] = [candidates[i] for i in sorted(candidates)]
        elif "promptFeedback" not in result:
            raise ValueError("stream carried no candidates")
        return result


def _add_part(parts: list, part: dict) -> None:
    """Consecutive text pieces of the same kind form one part, as in a non-streaming response."""
    previous = parts[-1] if parts else None
    if (previous is not None and "text" in part and set(part) <= _TEXT_KEYS and set(previous) <= _TEXT_KEYS
            and "text" in previous and "thoughtSignature" not in previous
            and bool(previous.get("thought")) == bool(part.get("thought"))):
        previous["text"] += part["text"]
        if "thoughtSignature" in part:
            previous["thoughtSignature"] = part["thoughtSignature"]
    else:
        parts.append(dict(part))
