"""Turn a layout into what its readers need; the only place memory becomes text."""

from backend.modules.memory.sources import MemorySources
from backend.schemas.memory import (
    FullRoundMemory, MemoryLayout, MemoryMaterials, MemoryTimeline, MemorySettings, RecentRound, RoundSummaryMemory,
)
from backend.shared.errors import ConflictError


def _memory_items(layout: MemoryLayout, sources: MemorySources):
    for segment in layout.memory:
        for number in segment.numbers:
            if segment.kind == "episode":
                yield sources.episodes[number].model_copy(deep=True)
                continue
            record = sources.rounds[number]
            if record.summary is None or not record.summary.strip():
                raise ConflictError(f"Round {record.id!r} has no summary")
            yield RoundSummaryMemory(id=record.id, round_no=record.round_no, summary=record.summary)


def _recent_fields(layout: MemoryLayout, sources: MemorySources):
    for number in layout.recent_rounds:
        record = sources.rounds[number]
        yield {"id": record.id, "round_no": record.round_no,
               "user_input": record.user_input, "ai_output": record.ai_output}


def render_materials(layout: MemoryLayout, sources: MemorySources) -> MemoryMaterials:
    """For the writing preset. `memory` carries no tags: the preset defines its own."""
    return MemoryMaterials(
        memory="\n".join(item.summary for item in _memory_items(layout, sources)),
        recent_rounds=[RecentRound(**fields) for fields in _recent_fields(layout, sources)],
    )


def render_timeline(layout: MemoryLayout, sources: MemorySources, settings: MemorySettings) -> MemoryTimeline:
    """For display: every round, oldest to newest, in the representation it currently uses."""
    items = [*_memory_items(layout, sources), *(FullRoundMemory(**fields) for fields in _recent_fields(layout, sources))]
    return MemoryTimeline(**settings.model_dump(), total_rounds=len(sources.rounds), items=items)
