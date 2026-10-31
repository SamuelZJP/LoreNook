"""Read memory sources from the caller's consistent database snapshot."""

from dataclasses import dataclass

from backend.modules.memory.layout import plan_layout, validate_layout
from backend.modules.memory.render import render_materials, render_timeline
from backend.modules.memory.sources import MemorySources
from backend.repository.models import Chat, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.memory import (
    ArchivedRound, ChatMemory, EpisodeMemory, MemoryLayout, MemoryMaterials, MemorySettings,
)
from backend.shared.errors import ConflictError


@dataclass(frozen=True)
class MemorySnapshot:
    """Plain data, still usable after the session closes. `layout` is the assembled one."""
    settings: MemorySettings
    sources: MemorySources
    layout: MemoryLayout


class MemoryService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def _sources(self, chat_id: str) -> MemorySources:
        worlds = self.repository.round_worlds(chat_id)
        rounds = [ArchivedRound.model_validate(record).model_copy(update={"world": worlds.get(record.id)})
                  for record in self.repository.rounds(chat_id, completed_only=True)]
        by_id = {record.id: record for record in rounds}
        episodes = []
        for record in self.repository.episodes(chat_id):
            start, end = by_id.get(record.start_round_id), by_id.get(record.end_round_id)
            if start is None or end is None:
                raise ConflictError("Episode endpoints must belong to archived history")
            episodes.append(EpisodeMemory(
                id=record.id, start_round_id=start.id, end_round_id=end.id,
                start_round_no=start.round_no, end_round_no=end.round_no, summary=record.summary, title=record.title,
            ))
        return MemorySources.build(rounds, episodes)

    def snapshot(self, chat_id: str) -> MemorySnapshot:
        chat = self.repository.get(Chat, chat_id)
        settings = MemorySettings(recent_rounds=chat.recent_rounds, min_summaries=chat.min_summaries)
        sources = self._sources(chat_id)
        return MemorySnapshot(settings, sources, plan_layout(sources, settings))

    def materials(self, chat_id: str, layout: MemoryLayout | None = None) -> MemoryMaterials:
        """`layout` lets a caller replace the assembled layout for one request."""
        snapshot = self.snapshot(chat_id)
        if layout is not None:
            validate_layout(layout, snapshot.layout, snapshot.sources)
        identity = self.repository.get(UserIdentity, self.repository.owner_id(chat_id, UserIdentity))
        return render_materials(layout or snapshot.layout, snapshot.sources, identity.name)

    def timeline(self, chat_id: str) -> ChatMemory:
        snapshot = self.snapshot(chat_id)
        timeline = render_timeline(snapshot.layout, snapshot.sources, snapshot.settings)
        return ChatMemory(chat_id=chat_id, **timeline.model_dump())
