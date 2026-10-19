"""Read memory sources from the caller's consistent database snapshot."""

from backend.modules.memory.assembler import assemble_memory
from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.memory import ArchivedRound, ChatMemory, EpisodeMemory
from backend.shared.errors import ConflictError


class MemoryService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def assemble(self, chat_id: str) -> ChatMemory:
        chat = self.repository.get(Chat, chat_id)
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
        history = assemble_memory(rounds, episodes, recent_rounds=chat.recent_rounds,
                                  min_summaries=chat.min_summaries)
        return ChatMemory(chat_id=chat_id, **history.model_dump(exclude={"uses_compressed_history"}))
