"""Summarize only the confirmed current round, using its updated state."""

from backend.llm.client import ModelClient
from backend.llm.generation import text_request, response_text
from backend.modules.round_summary.prompts import SYSTEM, render_prompt
from backend.schemas.round_summary import RoundSummaryContext
from backend.shared.content import extract_content
from backend.shared.errors import RoundSummaryError, StateUpdateError

def generate_summary(context: RoundSummaryContext, client: ModelClient) -> str:
    try:
        content = extract_content(context.ai_output)
    except StateUpdateError as error:
        raise RoundSummaryError(str(error)) from error
    prompt = render_prompt(context, content)
    request = text_request(context.connection.api_type, SYSTEM, prompt)
    response = client.invoke(context.connection, request).response
    try:
        return response_text(context.connection.api_type, response)
    except ValueError as error:
        raise RoundSummaryError("回合摘要响应必须是正常完成的单个候选，并提供非空文本") from error
