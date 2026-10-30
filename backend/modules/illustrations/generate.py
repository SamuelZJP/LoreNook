"""Turn one archived round into the prompt fields an image workflow expects."""

import json

from backend.llm.client import ModelClient
from backend.llm.generation import response_text, text_request
from backend.modules.definitions.renderer import DefinitionRenderer, substitute_names
from backend.modules.illustrations.prompts import SYSTEM, render_prompt
from backend.schemas.illustrations import IllustrationContext
from backend.shared.content import extract_content
from backend.shared.errors import IllustrationError, StateUpdateError


def _parse(text: str, fields: list[str]) -> dict[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        value = json.loads(text)
    except ValueError:
        raise IllustrationError("插图提示词响应必须是 JSON 对象") from None
    if not isinstance(value, dict):
        raise IllustrationError("插图提示词响应必须是 JSON 对象")
    missing = [name for name in fields if not isinstance(value.get(name), str)]
    if missing:
        raise IllustrationError(f"插图提示词响应缺少字符串字段：{'、'.join(missing)}")
    result = {name: value[name] for name in fields}
    if not any(item.strip() for item in result.values()):
        raise IllustrationError("插图提示词全部为空")
    return result


def generate_fields(context: IllustrationContext, client: ModelClient) -> dict[str, str]:
    try:
        content = extract_content(context.ai_output)
    except StateUpdateError as error:
        raise IllustrationError(str(error)) from error
    names = {"user_name": context.user_name, "character_name": context.character_name}
    definitions = DefinitionRenderer().resolve(context.character_definitions, context.user_definitions,
                                               context.state, **names)
    prompt = render_prompt(context, content, definitions, substitute_names(context.instructions, **names))
    request = text_request(context.connection.api_type, SYSTEM, prompt, json_output=True)
    response = client.invoke(context.connection, request).response
    try:
        text = response_text(context.connection.api_type, response)
    except ValueError as error:
        raise IllustrationError("插图提示词响应必须是正常完成的单个候选，并提供非空文本") from error
    return _parse(text, context.fields)
