"""Select exactly one representation per archived round; preserve source text."""

from backend.schemas.memory import (
    ArchivedRound, EpisodeMemory, FullRoundMemory, MemoryHistory, MemorySettings,
    RoundSummaryMemory,
)
from backend.shared.errors import ConflictError


def assemble_memory(
    rounds: list[ArchivedRound], episodes: list[EpisodeMemory], *,
    recent_rounds: int, min_summaries: int,
) -> MemoryHistory:
    settings = MemorySettings(recent_rounds=recent_rounds, min_summaries=min_summaries)
    ordered = sorted(rounds, key=lambda record: record.round_no)
    positions = {record.id: index for index, record in enumerate(ordered)}
    if (len(positions) != len(ordered)
            or len({record.round_no for record in ordered}) != len(ordered)):
        raise ConflictError("History contains duplicate rounds")

    # Validate all saved ranges before selection, including ones not yet eligible.
    ranges = []
    previous_end = -1
    for episode in sorted(episodes, key=lambda record: record.start_round_no):
        start = positions.get(episode.start_round_id)
        end = positions.get(episode.end_round_id)
        if (start is None or end is None or start > end
                or ordered[start].round_no != episode.start_round_no
                or ordered[end].round_no != episode.end_round_no
                or end - start != episode.end_round_no - episode.start_round_no):
            raise ConflictError("Episode must cover consecutive archived rounds")
        if start <= previous_end:
            raise ConflictError("Episode ranges overlap")
        if not episode.summary.strip():
            raise ConflictError("Episode summary must not be empty")
        ranges.append((start, end, episode))
        previous_end = end

    summary_end = max(0, len(ordered) - settings.recent_rounds)
    summary_count = summary_end
    selected = {}
    for start, end, episode in ranges:
        size = end - start + 1
        if end >= summary_end or summary_count - size < settings.min_summaries:
            break
        selected[start] = (end, episode)
        summary_count -= size

    items = []
    index = 0
    while index < len(ordered):
        record = ordered[index]
        if index in selected:
            end, episode = selected[index]
            items.append(episode.model_copy(deep=True))
            index = end + 1
            continue
        if index < summary_end:
            if record.summary is None or not record.summary.strip():
                raise ConflictError(f"Round {record.id!r} has no summary")
            items.append(RoundSummaryMemory(id=record.id, round_no=record.round_no,
                                            summary=record.summary))
        else:
            items.append(FullRoundMemory(id=record.id, round_no=record.round_no,
                                         user_input=record.user_input, ai_output=record.ai_output))
        index += 1
    return MemoryHistory(**settings.model_dump(), total_rounds=len(ordered), items=items)
