from backend.shared.errors import StateUpdateError


def extract_content(ai_output: str) -> str:
    opening, closing = "<content>", "</content>"
    if ai_output.count(opening) != 1 or ai_output.count(closing) != 1:
        raise StateUpdateError("AI 输出必须具有唯一且闭合的 <content> 正文")
    start, end = ai_output.index(opening) + len(opening), ai_output.index(closing)
    if end < start or not ai_output[start:end].strip():
        raise StateUpdateError("AI 正文为空或标签顺序错误")
    return ai_output[start:end]
