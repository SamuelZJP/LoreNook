"""Conservative length guard for generated memories, measured against source dialogue."""

import re


def has_numeric_start(text: str) -> bool:
    """Inspect trimmed text without changing the stored summary."""
    return re.match(r"[0-9]{2}", text.strip()) is not None


def content_length(text: str) -> int:
    """Count Unicode letters/numbers, excluding whitespace, punctuation and symbols."""
    return sum(character.isalnum() for character in text)


def summary_length(text: str) -> int:
    # A separate scene header must not compensate for a missing narrative.
    first, _, rest = text.strip().partition("\n")
    if re.match(r"^(?:\d{4}[-/年]|年月日|起始时间|yyyy)", first) and "—" in first:
        text = rest
    return content_length(text)


def minimum_summary_length(sources: list[str], *, target_floor: int) -> int:
    source_length = sum(content_length(source) for source in sources)
    return min(target_floor // 2, max(1, (source_length + 4) // 5))
