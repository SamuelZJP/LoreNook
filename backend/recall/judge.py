"""One recall pass: candidates in, chosen numbers out."""

import json
import re

from backend.llm.client import ModelClient
from backend.llm.generation import response_text, text_request
from backend.recall.errors import RecallError
from backend.recall.prompts import SYSTEM, render_prompt
from backend.recall.schemas import RecallContext


def parse_ids(text: str) -> list[str]:
    payload = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", payload, re.DOTALL | re.IGNORECASE)
    if fence:
        payload = fence[1]
    try:
        ids = json.loads(payload)["ids"]
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        raise RecallError("记忆召回响应必须是包含 ids 数组的 JSON 对象") from error
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise RecallError("记忆召回响应的 ids 必须是编号字符串数组")
    return ids


def judge(context: RecallContext, stage: str, candidates: dict[str, str], client: ModelClient) -> set[int]:
    """`candidates` maps a label such as E2 or R15 to its text. No candidates means no model call.
    Returns the chosen numbers; labels the model made up are skipped."""
    if not candidates:
        return set()
    lines = [f"[{label}] {text}" for label, text in candidates.items()]
    request = text_request(context.connection.api_type, SYSTEM, render_prompt(context, stage, lines), json_output=True)
    response = client.invoke(context.connection, request).response
    try:
        text = response_text(context.connection.api_type, response)
    except ValueError as error:
        raise RecallError("记忆召回响应必须是正常完成的单个候选，并提供非空文本") from error
    return {int(label[1:]) for label in parse_ids(text) if label in candidates}
