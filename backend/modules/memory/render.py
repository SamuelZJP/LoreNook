"""Turn a layout into what its readers need; the only place memory becomes text."""

from backend.modules.memory.sources import MemorySources
from backend.schemas.memory import (
    ArchivedRound, FullRoundMemory, MemoryLayout, MemoryMaterials, MemorySettings, MemoryTimeline, RecentRound,
    RoundSummaryMemory,
)
from backend.shared.content import extract_content
from backend.shared.errors import ConflictError, StateUpdateError


def render_round(record: ArchivedRound) -> str:
    """A complete round as text, without stored tags other than the story body's."""
    try:
        content = extract_content(record.ai_output)
    except StateUpdateError:  # Edited or imported rounds may have no valid tag: all of it is the body.
        content = record.ai_output
    tag = f"round_{record.round_no}"
    return f"<{tag}><user_input>{record.user_input}</user_input><content>{content}</content></{tag}>"


def _round_fields(record: ArchivedRound) -> dict:
    return {"id": record.id, "round_no": record.round_no, "user_input": record.user_input, "ai_output": record.ai_output}


def _summary(record: ArchivedRound) -> RoundSummaryMemory:
    if record.summary is None or not record.summary.strip():
        raise ConflictError(f"Round {record.id!r} has no summary")
    return RoundSummaryMemory(id=record.id, round_no=record.round_no, summary=record.summary)


def _memory_item(kind: str, number: int, sources: MemorySources):
    if kind == "episode":
        return sources.episodes[number].model_copy(deep=True)
    if kind == "summary":
        return _summary(sources.rounds[number])
    return FullRoundMemory(**_round_fields(sources.rounds[number]))


def _memory_items(layout: MemoryLayout, sources: MemorySources) -> list:
    return [_memory_item(segment.kind, number, sources) for segment in layout.memory for number in segment.numbers]


def render_materials(layout: MemoryLayout, sources: MemorySources) -> MemoryMaterials:
    """For the writing preset. `memory` carries no tags: the preset defines its own."""
    texts = [render_round(sources.rounds[item.round_no]) if item.kind == "round" else item.summary
             for item in _memory_items(layout, sources)]
    return MemoryMaterials(
        memory="\n".join(texts),
        recent_rounds=[RecentRound(**_round_fields(sources.rounds[number])) for number in layout.recent_rounds],
    )


def render_timeline(layout: MemoryLayout, sources: MemorySources, settings: MemorySettings) -> MemoryTimeline:
    """For display: every round, oldest to newest, in the representation it currently uses."""
    recent = [FullRoundMemory(**_round_fields(sources.rounds[number])) for number in layout.recent_rounds]
    return MemoryTimeline(**settings.model_dump(), total_rounds=len(sources.rounds),
                          items=[*_memory_items(layout, sources), *recent])
