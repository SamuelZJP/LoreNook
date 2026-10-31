"""Read memory sources from the caller's consistent database snapshot."""

from backend.modules.memory.layout import plan_layout
from backend.modules.memory.render import render_materials, render_timeline
from backend.modules.memory.sources import MemorySources
from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.memory import ArchivedRound, ChatMemory, EpisodeMemory, MemoryMaterials, MemorySettings
from backend.shared.errors import ConflictError


class MemoryService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def _sources(self, chat_id: str) -> MemorySources:
        rounds = [ArchivedRound.model_validate(record) for record in
                  self.repository.rounds(chat_id, completed_only=True)]
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

    def _settings(self, chat_id: str) -> MemorySettings:
        chat = self.repository.get(Chat, chat_id)
        return MemorySettings(recent_rounds=chat.recent_rounds, min_summaries=chat.min_summaries)

    def materials(self, chat_id: str) -> MemoryMaterials:
        settings = self._settings(chat_id)
        sources = self._sources(chat_id)
        return render_materials(plan_layout(sources, settings), sources)

    def timeline(self, chat_id: str) -> ChatMemory:
        settings = self._settings(chat_id)
        sources = self._sources(chat_id)
        timeline = render_timeline(plan_layout(sources, settings), sources, settings)
        return ChatMemory(chat_id=chat_id, **timeline.model_dump())
