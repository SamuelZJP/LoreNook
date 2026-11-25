"""A one-line glimpse of where a chat left off, for chat lists."""

import re

from backend.shared.content import extract_content
from backend.shared.errors import StateUpdateError

TAG = re.compile(r"</?[A-Za-z_][\w\-~.:]*[^>]*>")
# Emphasis and code marks, and leading heading / quote / list marks; the list shows plain text.
MARKS = re.compile(r"\*+|`+|~~")
LEADING = re.compile(r"^(?:#{1,6}|>|[-+]|\d+\.)\s+")
LIMIT = 80


def last_line(ai_output: str) -> str:
    """The last non-empty line of the <content> body (or the whole text), tags and Markdown marks removed, shortened."""
    try:
        body = extract_content(ai_output)
    except StateUpdateError:
        body = ai_output
    lines = [line.strip() for line in TAG.sub("", body).splitlines() if line.strip()]
    if not lines:
        return ""
    line = MARKS.sub("", LEADING.sub("", lines[-1])).strip()
    return line if len(line) <= LIMIT else line[: LIMIT - 1] + "…"
