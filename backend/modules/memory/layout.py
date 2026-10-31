"""Decide which representation each archived round uses. Only numbers here, never text."""

from backend.modules.memory.sources import MemorySources
from backend.schemas.memory import MemoryLayout, MemorySegment, MemorySettings


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

    segments: list[MemorySegment] = []
    def add(kind, number):
        if not segments or segments[-1].kind != kind:
            segments.append(MemorySegment(kind=kind, numbers=[]))
        segments[-1].numbers.append(number)

    covered_until = 0
    for round_no in older:
        if round_no in folded:
            add("episode", folded[round_no])
            covered_until = sources.episodes[folded[round_no]].end_round_no
        elif round_no > covered_until:
            add("summary", round_no)
    return MemoryLayout(memory=segments, recent_rounds=recent)
