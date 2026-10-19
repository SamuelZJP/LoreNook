"""Built-in prompt and response parsing, independent of writing presets."""

import json
import re
import yaml

from backend.llm.client import ModelClient
from backend.llm.generation import text_request, response_text
from backend.modules.state.patch import apply_operations
from backend.modules.state.prompts import SYSTEM, render_update_prompt
from backend.modules.state.schema import StateValidator, checked_state
from backend.schemas.state import StateUpdateContext
from backend.shared.content import extract_content
from backend.shared.errors import StateUpdateError


def parse_patch_operations(text: str) -> list:
    for tag in ("UpdateVariable", "Analysis", "JSONPatch"):
        if text.count(f"<{tag}>") != 1 or text.count(f"</{tag}>") != 1:
            raise ValueError("状态更新标签缺失或重复")
    match = re.fullmatch(
        r"\s*<UpdateVariable>\s*<Analysis>(.*?)</Analysis>\s*"
        r"<JSONPatch>(.*?)</JSONPatch>\s*</UpdateVariable>\s*", text, re.DOTALL,
    )
    if match is None or not match[1].strip():
        raise ValueError("状态更新标签顺序错误或结算说明为空")

    def invalid_constant(value):
        raise ValueError("JSON Patch包含非有限数值")

    operations = json.loads(match[2], parse_constant=invalid_constant)
    if not isinstance(operations, list):
        raise ValueError("JSONPatch必须是数组")
    json.dumps(operations, allow_nan=False)
    return operations


def update_state(context: StateUpdateContext, client: ModelClient, validator: StateValidator) -> tuple[dict, int]:
    content = extract_content(context.ai_output)
    prompt = render_update_prompt(
        user=context.user_name, reference_info=context.reference,
        current_memory_yaml=yaml.safe_dump(context.state, allow_unicode=True, sort_keys=False),
        recent_summaries="\n".join(context.summaries) or "（无最近剧情记录）",
        user_input=context.user_input, ai_response=content, variable_update_rules=context.update_rules,
    )
    request = text_request(context.connection.api_type, SYSTEM, prompt)
    response = client.invoke(context.connection, request).response
    try:
        operations = parse_patch_operations(response_text(context.connection.api_type, response))
    except (KeyError, ValueError, TypeError, RecursionError):
        raise StateUpdateError("状态更新响应必须是正常完成的单个候选，包含唯一的 UpdateVariable、非空 Analysis 和 JSONPatch 数组") from None
    patched, skipped = apply_operations(context.state, operations)
    return checked_state(validator, context.schema_source, patched), skipped
