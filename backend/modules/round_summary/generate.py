"""Summarize only the confirmed current round, using its updated state."""

from backend.llm.client import ModelClient
from backend.llm.generation import text_request, response_text
from backend.modules.round_summary.prompts import SYSTEM, render_prompt
from backend.schemas.round_summary import RoundSummaryContext
from backend.shared.content import extract_content
from backend.shared.errors import RoundSummaryError, StateUpdateError
from backend.shared.summary_length import has_numeric_start, minimum_summary_length, summary_length

def generate_summary(context: RoundSummaryContext, client: ModelClient) -> str:
    try:
        content = extract_content(context.ai_output)
    except StateUpdateError as error:
        raise RoundSummaryError(str(error)) from error
    prompt = render_prompt(context, content)
    request = text_request(context.connection.api_type, SYSTEM, prompt)
    response = client.invoke(context.connection, request).response
    try:
        summary = response_text(context.connection.api_type, response)
    except ValueError as error:
        raise RoundSummaryError("回合摘要响应必须是正常完成的单个候选，并提供非空文本") from error
    minimum = minimum_summary_length([context.user_input, content], target_floor=150)
    actual = summary_length(summary)
    if actual < minimum:
        raise RoundSummaryError(f"回合摘要内容显著偏少：有效字数 {actual}，最低要求 {minimum}")
    if not has_numeric_start(summary):
        raise RoundSummaryError("回合摘要格式无效：去除首尾空白后必须以两位 ASCII 数字开头")
    return summary
