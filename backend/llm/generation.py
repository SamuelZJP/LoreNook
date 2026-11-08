"""Native text requests and response dispatch for built-in archive generators."""

from backend.llm.deepseek import DeepSeekChatCompletions
from backend.llm.google import GoogleGenerateContent
from backend.llm.text import deepseek_response_text, google_response_text
from backend.schemas.presets import BuiltRequest
from backend.shared.errors import ModelConfigurationError


def text_request(api_type: str, system: str, prompt: str, *, json_output: bool = False) -> BuiltRequest:
    if api_type == GoogleGenerateContent.api_type:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"candidateCount": 1, "responseMimeType": "application/json" if json_output else "text/plain"},
        }
    elif api_type == DeepSeekChatCompletions.api_type:
        body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object" if json_output else "text"}}
    else:
        raise ModelConfigurationError("内置生成当前仅支持 google_generate_content 和 deepseek_chat_completions")
    return BuiltRequest(api_type=api_type, body=body)


def response_text(api_type: str, response: dict) -> str:
    if api_type == GoogleGenerateContent.api_type:
        return google_response_text(response)
    if api_type == DeepSeekChatCompletions.api_type:
        return deepseek_response_text(response)
    raise ModelConfigurationError("当前不支持该 api_type 的文本解析")
