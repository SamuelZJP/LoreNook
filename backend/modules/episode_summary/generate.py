"""Generate and validate a structured episode memory for its frozen range."""

import json
import re

from backend.llm.client import ModelClient
from backend.llm.generation import text_request, response_text
from backend.modules.episode_summary.prompts import SYSTEM, render_prompt
from backend.schemas.episode_summary import GeneratedEpisode, EpisodeSummaryContext
from backend.shared.errors import EpisodeSummaryError, StateUpdateError
from backend.shared.content import extract_content
from backend.shared.summary_length import has_numeric_start, minimum_summary_length, summary_length

def parse_episode(text: str) -> GeneratedEpisode:
    payload = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", payload, re.DOTALL | re.IGNORECASE)
    if fence:
        payload = fence[1]

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("重复字段")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("非有限数值")

    try:
        value = json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid_constant)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return GeneratedEpisode.model_validate(value)
    except (ValueError, TypeError, RecursionError) as error:
        raise EpisodeSummaryError("情节摘要必须是仅含非空 title（不超过20字）与 summary 的JSON对象") from error


def generate_episode_summary(context: EpisodeSummaryContext, client: ModelClient) -> GeneratedEpisode:
    if not context.rounds or any(not record.summary.strip() for record in context.rounds):
        raise EpisodeSummaryError("情节范围缺少有效回合摘要")
    try:
        prompt = render_prompt(context)
        sources = [text for record in context.rounds
                   for text in (record.user_input, extract_content(record.ai_output))]
        if context.first_message:
            sources.append(extract_content(context.first_message) if "<content>" in context.first_message
                           else context.first_message)
    except StateUpdateError as error:
        raise EpisodeSummaryError(str(error)) from error
    request = text_request(context.connection.api_type, SYSTEM, prompt, json_output=True)
    response = client.invoke(context.connection, request).response
    try:
        text = response_text(context.connection.api_type, response)
    except ValueError as error:
        raise EpisodeSummaryError("情节摘要响应必须是正常完成的单个候选，并提供非空文本") from error
    generated = parse_episode(text)
    minimum = minimum_summary_length(sources, target_floor=200)
    actual = summary_length(generated.summary)
    if actual < minimum:
        raise EpisodeSummaryError(f"情节摘要内容显著偏少：有效字数 {actual}，最低要求 {minimum}")
    if not has_numeric_start(generated.summary):
        raise EpisodeSummaryError("情节摘要格式无效：summary 去除首尾空白后必须以两位 ASCII 数字开头")
    return generated
