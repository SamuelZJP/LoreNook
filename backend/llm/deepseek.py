"""DeepSeek Chat Completions transport adaptation; streamed chunks are joined into the non-streaming shape."""

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
        # The config's streaming switch owns `stream`; values from presets or parameters are replaced.
        body["stream"] = config.streaming
        if config.streaming:
            options = body.get("stream_options")
            body["stream_options"] = {**(options if isinstance(options, dict) else {}), "include_usage": True}
        else:
            body.pop("stream_options", None)
        key = config.api_key.get_secret_value()
        if key and (not key.isascii() or any(ord(char) < 33 or ord(char) > 126 for char in key)):
            raise ModelConfigurationError("API Key 必须是可见 ASCII 字符，不能包含空格或换行")
        headers = {"authorization": f"Bearer {key}"} if key else {}
        return f"{base}/chat/completions", headers, body

    def join_stream(self, events: list[dict]) -> dict:
        """One `chat.completion` object from its chunks; raises ValueError if any choice never finished."""
        result: dict = {"object": "chat.completion"}
        choices: dict[int, dict] = {}
        for event in events:
            for key in ("id", "created", "model", "system_fingerprint"):
                if event.get(key) is not None:
                    result[key] = event[key]
            if event.get("usage") is not None:
                result["usage"] = event["usage"]
            for chunk in event.get("choices") or []:
                index = chunk.get("index", 0)
                choice = choices.setdefault(index, {"index": index, "message": {"role": "assistant"},
                                                    "finish_reason": None, "logprobs": None})
                _add_delta(choice["message"], chunk.get("delta") or {})
                if chunk.get("finish_reason") is not None:
                    choice["finish_reason"] = chunk["finish_reason"]
                if chunk.get("logprobs") is not None:
                    content = (choice["logprobs"] or {}).get("content") or []
                    choice["logprobs"] = {"content": content + (chunk["logprobs"].get("content") or [])}
        if not choices or any(choice["finish_reason"] is None for choice in choices.values()):
            raise ValueError("stream ended before every choice finished")
        for choice in choices.values():
            choice["message"].setdefault("content", None)
            if "tool_calls" in choice["message"]:
                calls = choice["message"]["tool_calls"]
                choice["message"]["tool_calls"] = [calls[i] for i in sorted(calls)]
        result["choices"] = [choices[i] for i in sorted(choices)]
        return result


def _add_delta(message: dict, delta: dict) -> None:
    for key, value in delta.items():
        if value is None:
            continue
        if key == "role":
            message["role"] = value
        elif key == "tool_calls":
            calls = message.setdefault("tool_calls", {})
            for part in value:
                call = calls.setdefault(part.get("index", len(calls)), {"function": {"arguments": ""}})
                for name in ("id", "type"):
                    if part.get(name) is not None:
                        call[name] = part[name]
                function = part.get("function") or {}
                if function.get("name") is not None:
                    call["function"]["name"] = function["name"]
                call["function"]["arguments"] += function.get("arguments") or ""
        elif isinstance(value, str):
            message[key] = message.get(key, "") + value
        else:
            message[key] = value
