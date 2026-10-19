"""Atomic persistence primitives for the future archive workflow.

Call each operation in a fresh Database.transaction(), after model work completes.
No operation commits or calls a model. Repeated/stale step results are rejected.
"""

from copy import deepcopy
from typing import Any

from sqlalchemy import select

from backend.repository.models import Character, Chat, Episode, Round, StateSnapshot
from backend.repository.queries import Repository
from backend.shared.errors import ConflictError


class ArchiveRepository(Repository):
    def create_round(self, chat_id: str, user_input: str, ai_output: str) -> Round:
        self.get(Chat, chat_id)
        latest = self.latest_round(chat_id)
        if latest is not None and latest.archive_step != "complete":
            raise ConflictError("Finish the current archive before creating another round")
        return self.add(Round(chat_id=chat_id, round_no=1 if latest is None else latest.round_no + 1,
                              user_input=user_input, ai_output=ai_output))

    def _at_step(self, round_id: str, expected_step: str) -> Round:
        record = self.get(Round, round_id)
        self.session.refresh(record)
        if record.archive_step != expected_step:
            raise ConflictError(f"Expected {expected_step}, found {record.archive_step}")
        return record

    def _advance(self, record: Round, next_step: str) -> None:
        record.archive_step = next_step
        record.archive_error = None
        self.session.flush()

    def save_state(self, round_id: str, content: dict[str, Any]) -> StateSnapshot:
        record = self._at_step(round_id, "state_update")
        character = self.session.scalar(select(Character).where(Character.chat_id == record.chat_id))
        if character is None:
            raise ConflictError("Chat has no character")
        snapshot = self.add(StateSnapshot(chat_id=record.chat_id, character_id=character.id,
                                          round_id=record.id, content=deepcopy(content)))
        self._advance(record, "round_summary")
        return snapshot

    def save_summary(self, round_id: str, summary: str) -> None:
        if not summary.strip():
            raise ValueError("Round summary must not be empty")
        record = self._at_step(round_id, "round_summary")
        record.summary = summary
        self._advance(record, "episode_decision")

    def save_decision(
        self, round_id: str, *, start_round_id: str | None = None,
        end_round_id: str | None = None,
    ) -> None:
        record = self._at_step(round_id, "episode_decision")
        if (start_round_id is None) != (end_round_id is None):
            raise ValueError("Provide both range endpoints, or neither")
        if start_round_id is None:
            record.episode_required = False
            self._advance(record, "complete")
            return
        self._validate_episode_range(record, start_round_id, end_round_id)
        record.episode_required = True
        record.episode_start_round_id = start_round_id
        record.episode_end_round_id = end_round_id
        self._advance(record, "episode_summary")

    def _validate_episode_range(self, record: Round, start_round_id: str, end_round_id: str):
        candidates = [r for r in self.unrepresented_round_headers(record.chat_id)
                      if r.round_no < record.round_no]
        if not candidates or candidates[0].id != start_round_id:
            raise ConflictError("Episode must begin at the earliest unrepresented round")
        end = next((r for r in candidates if r.id == end_round_id), None)
        if end is None:
            raise ConflictError("Episode endpoint is not an eligible round")
        selected = [r for r in candidates if r.round_no <= end.round_no]
        if ([r.round_no for r in selected] != list(range(selected[0].round_no, end.round_no + 1))
                or any(r.archive_step != "complete" for r in selected)):
            raise ConflictError("Episode must cover consecutive completed rounds")
        return selected

    def pending_episode_range(self, round_id: str):
        record = self._at_step(round_id, "episode_summary")
        if record.episode_required is not True:
            raise ConflictError("Round has no pending episode decision")
        return self._validate_episode_range(record, record.episode_start_round_id, record.episode_end_round_id)

    def save_episode(self, round_id: str, summary: str, *, title: str = "") -> Episode:
        if not summary.strip():
            raise ValueError("Episode summary must not be empty")
        record = self._at_step(round_id, "episode_summary")
        self._validate_episode_range(record, record.episode_start_round_id, record.episode_end_round_id)
        episode = self.add(Episode(chat_id=record.chat_id, start_round_id=record.episode_start_round_id,
                                   end_round_id=record.episode_end_round_id,
                                   created_by_round_id=record.id, summary=summary, title=title))
        self._advance(record, "complete")
        return episode

    def save_error(self, round_id: str, expected_step: str, error: str) -> None:
        if expected_step == "complete":
            raise ConflictError("Completed archives cannot fail")
        if not error.strip():
            raise ValueError("Error message must not be empty")
        record = self._at_step(round_id, expected_step)
        record.archive_error = error
        self.session.flush()
