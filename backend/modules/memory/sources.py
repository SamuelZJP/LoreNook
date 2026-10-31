"""Validated source records of one chat's memory, addressable by sequence number."""

from dataclasses import dataclass

from backend.schemas.memory import ArchivedRound, EpisodeMemory
from backend.shared.errors import ConflictError


@dataclass(frozen=True)
class MemorySources:
    """Rounds by `round_no`, episodes by 1-based position in story order."""
    rounds: dict[int, ArchivedRound]
    episodes: dict[int, EpisodeMemory]

    @classmethod
    def build(cls, rounds: list[ArchivedRound], episodes: list[EpisodeMemory]) -> "MemorySources":
        ordered = sorted(rounds, key=lambda record: record.round_no)
        positions = {record.id: index for index, record in enumerate(ordered)}
        if (len(positions) != len(ordered)
                or len({record.round_no for record in ordered}) != len(ordered)):
            raise ConflictError("History contains duplicate rounds")

        # Validate all saved ranges, including ones the layout will not use yet.
        numbered = {}
        previous_end = -1
        for number, episode in enumerate(sorted(episodes, key=lambda record: record.start_round_no), start=1):
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
            numbered[number] = episode
            previous_end = end
        return cls(rounds={record.round_no: record for record in ordered}, episodes=numbered)
