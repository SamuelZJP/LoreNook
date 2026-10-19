"""Strict visible-text extraction for built-in generation modules."""


def deepseek_response_text(response: dict) -> str:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise ValueError
        message = choice["message"]
        if (message.get("role") != "assistant" or message.get("tool_calls")
                or message.get("function_call") or message.get("refusal")):
            raise ValueError
        content = message["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError
        # reasoning_content and all other provider fields remain in the raw call log.
        return content
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("DeepSeek 响应必须是正常完成的单个候选，并提供非空 assistant 文本") from None


def google_response_text(response: dict) -> str:
    try:
        candidates = response["candidates"]
        if (not isinstance(candidates, list) or len(candidates) != 1
                or not isinstance(candidates[0], dict) or candidates[0].get("finishReason") != "STOP"):
            raise ValueError
        parts = candidates[0]["content"]["parts"]
        if not isinstance(parts, list):
            raise ValueError
        texts = []
        for part in parts:
            if not isinstance(part, dict) or "functionCall" in part:
                raise ValueError
            if part.get("thought") is True:
                continue
            if not isinstance(part.get("text"), str):
                raise ValueError
            texts.append(part["text"])
        text = "".join(texts)
        if not text.strip():
            raise ValueError
        return text
    except (KeyError, ValueError, TypeError):
        raise ValueError("模型响应必须是正常完成的单个候选，并提供非空文本") from None
