"""Decide which representation each archived round uses. Only numbers here, never text."""

from collections.abc import Collection

from backend.modules.memory.sources import MemorySources
from backend.schemas.memory import MemoryLayout, MemorySegment, MemorySettings
from backend.shared.errors import ConflictError


def _fold_episodes(older: list[int], sources: MemorySources, settings: MemorySettings) -> dict[int, int]:
    """Episode by its first round. Oldest first, stopping before too few summaries would remain."""
    available = set(older)
    summary_count = len(older)
    folded = {}
    for number, episode in sources.episodes.items():
        size = episode.end_round_no - episode.start_round_no + 1
        if episode.end_round_no not in available or summary_count - size < settings.min_summaries:
            break
        folded[episode.start_round_no] = number
        summary_count -= size
    return folded


def plan_layout(sources: MemorySources, settings: MemorySettings) -> MemoryLayout:
    round_numbers = list(sources.rounds)
    boundary = max(0, len(round_numbers) - settings.recent_rounds)
    older, recent = round_numbers[:boundary], round_numbers[boundary:]
    folded = _fold_episodes(older, sources, settings)

    entries = []
    covered_until = 0
    for round_no in older:
        if round_no in folded:
            entries.append(("episode", folded[round_no]))
            covered_until = sources.episodes[folded[round_no]].end_round_no
        elif round_no > covered_until:
            entries.append(("summary", round_no))
    return MemoryLayout(memory=_group(entries), recent_rounds=recent)


def _flatten(memory: list[MemorySegment]) -> list[tuple[str, int]]:
    return [(segment.kind, number) for segment in memory for number in segment.numbers]


def _group(entries: list[tuple[str, int]]) -> list[MemorySegment]:
    segments: list[MemorySegment] = []
    for kind, number in entries:
        if not segments or segments[-1].kind != kind:
            segments.append(MemorySegment(kind=kind, numbers=[]))
        segments[-1].numbers.append(number)
    return segments


def expand_layout(layout: MemoryLayout, sources: MemorySources, *,
                  episodes: Collection[int] = (), summaries: Collection[int] = ()) -> MemoryLayout:
    """Expand in place: an episode becomes its summaries, a summary becomes its round. Nothing else moves."""
    entries = []
    for kind, number in _flatten(layout.memory):
        if kind == "episode" and number in episodes:
            episode = sources.episodes[number]
            entries.extend(("summary", round_no) for round_no in range(episode.start_round_no, episode.end_round_no + 1))
        elif kind == "summary" and number in summaries:
            entries.append(("round", number))
        else:
            entries.append((kind, number))
    return layout.model_copy(update={"memory": _group(entries)})


def validate_layout(layout: MemoryLayout, planned: MemoryLayout, sources: MemorySources) -> None:
    """A layout from outside must still fit this history: every round once, in order, recent rounds untouched."""
    covered = []
    try:
        for kind, number in _flatten(layout.memory):
            if kind == "episode":
                episode = sources.episodes[number]
                covered.extend(range(episode.start_round_no, episode.end_round_no + 1))
            else:
                sources.rounds[number]
                covered.append(number)
    except KeyError:
        raise ConflictError("记忆布局已过期，请重新生成") from None
    if layout.recent_rounds != planned.recent_rounds or covered + layout.recent_rounds != list(sources.rounds):
        raise ConflictError("记忆布局已过期，请重新生成")
