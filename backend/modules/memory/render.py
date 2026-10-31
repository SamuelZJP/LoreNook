"""Turn a layout into what its readers need; the only place memory becomes text."""

from itertools import groupby

from backend.modules.memory.sources import MemorySources
from backend.schemas.memory import (
    ArchivedRound, EpisodeMemory, FullRoundMemory, MemoryLayout, MemoryMaterials, MemorySettings, MemoryTimeline, RecentRound,
    RoundSummaryMemory,
)
from backend.shared.content import extract_content
from backend.shared.errors import ConflictError, StateUpdateError


def render_round(record: ArchivedRound, user_name: str) -> str:
    """A complete round as text: a time and place header, then the input and the plot, without stored tags."""
    try:
        content = extract_content(record.ai_output)
    except StateUpdateError:  # Edited or imported rounds may have no valid tag: all of it is the body.
        content = record.ai_output
    world = record.world or {}
    user_input = record.user_input.strip()
    return "\n\n".join(filter(None, (
        "—".join(filter(None, (world.get("日期"), world.get("时间"), world.get("地点")))),
        user_input and f"<{user_name}>\n{user_input}\n</{user_name}>",
        f"<plot>\n{content.strip()}\n</plot>",
    )))


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


def render_episode(episode: EpisodeMemory) -> str:
    """The stored summary with its title below the date and location line. Without a title, it stays as stored."""
    if not episode.title.strip():
        return episode.summary
    title = f"【{episode.title.strip()}】"
    header, line_break, body = episode.summary.strip().partition("\n")
    return f"{header.rstrip()}\n{title}\n{body.lstrip()}" if line_break else f"{title}\n{header}"


def _memory_text(layout: MemoryLayout, sources: MemorySources, user_name: str) -> str:
    """Summaries sit on adjacent lines; blank lines set each expanded round apart."""
    blocks = []
    for is_round, items in groupby(_memory_items(layout, sources), key=lambda item: item.kind == "round"):
        if is_round:
            blocks.extend(render_round(sources.rounds[item.round_no], user_name) for item in items)
        else:
            blocks.append("\n".join(render_episode(item) if item.kind == "episode" else item.summary for item in items))
    return "\n\n".join(blocks)


def render_materials(layout: MemoryLayout, sources: MemorySources, user_name: str) -> MemoryMaterials:
    """For the writing preset. `memory` has no outer tags: the preset defines its own."""
    return MemoryMaterials(
        memory=_memory_text(layout, sources, user_name),
        recent_rounds=[RecentRound(**_round_fields(sources.rounds[number])) for number in layout.recent_rounds],
    )


def render_timeline(layout: MemoryLayout, sources: MemorySources, settings: MemorySettings) -> MemoryTimeline:
    """For display: every round, oldest to newest, in the representation it currently uses."""
    recent = [FullRoundMemory(**_round_fields(sources.rounds[number])) for number in layout.recent_rounds]
    return MemoryTimeline(**settings.model_dump(), total_rounds=len(sources.rounds),
                          items=[*_memory_items(layout, sources), *recent])
