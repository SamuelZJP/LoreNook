"""Composable storage operations; the caller owns the transaction."""

from typing import NamedTuple, TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased

from backend.repository.models import (
    Base, Character, CharacterScene, Chat, ChatModelBinding, ChatTemplate, Definition, Episode, ModelConfig, Round,
    StateSnapshot, UserIdentity, WritingPreset,
)
from backend.shared.errors import ConflictError, NotFoundError

Record = TypeVar("Record", bound=Base)


class RoundHeader(NamedTuple):
    id: str
    round_no: int
    archive_step: str


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, model: type[Record], key) -> Record:
        record = self.session.get(model, key)
        if record is None:
            raise NotFoundError(f"{model.__name__} {key!r} does not exist")
        return record

    def add(self, record: Record) -> Record:
        self.session.add(record)
        self.session.flush()
        return record

    def delete(self, record: Base) -> None:
        self.session.delete(record)
        self.session.flush()

    def list_chats(self) -> list[Chat]:
        return list(self.session.scalars(select(Chat).order_by(Chat.created_at.desc(), Chat.id)))

    def chat_character_images(self) -> dict[str, tuple[str | None, str | None]]:
        """Avatar and portrait of each chat's own character."""
        rows = self.session.execute(
            select(Character.chat_id, Character.avatar, Character.portrait).where(Character.chat_id.is_not(None)))
        return {chat_id: (avatar, portrait) for chat_id, avatar, portrait in rows}

    def chat_templates(self) -> list[ChatTemplate]:
        return list(self.session.scalars(select(ChatTemplate).order_by(ChatTemplate.created_at, ChatTemplate.id)))

    def clear_default_template(self) -> None:
        self.session.execute(update(ChatTemplate).where(ChatTemplate.is_default.is_(True)).values(is_default=False))

    def owner_id(self, chat_id: str, model: type[Character | UserIdentity]) -> str:
        """The chat's own character or identity copy."""
        self.get(Chat, chat_id)
        records = self.list_owned(model, chat_id)
        if len(records) != 1:
            raise ConflictError(f"Chat must have exactly one {model.__name__}")
        return records[0].id

    def get_owned(self, model: type[Record], key: str, chat_id: str | None) -> Record:
        record = self.get(model, key)
        if record.chat_id != chat_id:
            raise NotFoundError(f"{model.__name__} {key!r} does not exist in this scope")
        return record

    def model_bindings(self, chat_id: str) -> list[ChatModelBinding]:
        return list(self.session.scalars(select(ChatModelBinding).where(
            ChatModelBinding.chat_id == chat_id
        ).order_by(ChatModelBinding.purpose)))

    def model_binding(self, chat_id: str, purpose: str) -> ChatModelBinding | None:
        return self.session.get(ChatModelBinding, (chat_id, purpose))

    def list_owned(
        self, model: type[Character | UserIdentity | WritingPreset | ModelConfig],
        chat_id: str | None,
    ) -> list:
        """None selects library sources; an ID selects only that chat's copies."""
        return list(self.session.scalars(select(model).where(model.chat_id == chat_id).order_by(model.id)))

    def scenes(self, character_id: str) -> list[CharacterScene]:
        return list(self.session.scalars(select(CharacterScene).where(CharacterScene.character_id == character_id)
                                         .order_by(CharacterScene.order, CharacterScene.id)))

    def opening_scene(self, character_id: str) -> CharacterScene:
        """A chat-owned character keeps exactly the scene selected at chat creation."""
        scenes = self.scenes(character_id)
        if not scenes:
            raise NotFoundError("角色没有开场")
        return scenes[0]

    def definitions(
        self, *, character_id: str | None = None,
        user_identity_id: str | None = None, enabled_only: bool = False,
    ) -> list[Definition]:
        if (character_id is None) == (user_identity_id is None):
            raise ValueError("Provide exactly one definition owner")
        owner = (Definition.character_id == character_id if character_id is not None
                 else Definition.user_identity_id == user_identity_id)
        statement = select(Definition).where(owner)
        if enabled_only:
            statement = statement.where(Definition.enabled.is_(True))
        return list(self.session.scalars(statement.order_by(Definition.order, Definition.id)))

    def rounds(self, chat_id: str, *, completed_only: bool = False) -> list[Round]:
        statement = select(Round).where(Round.chat_id == chat_id)
        if completed_only:
            statement = statement.where(Round.archive_step == "complete")
        return list(self.session.scalars(statement.order_by(Round.round_no)))

    def latest_round(self, chat_id: str) -> Round | None:
        return self.session.scalar(select(Round).where(Round.chat_id == chat_id)
                                   .order_by(Round.round_no.desc()).limit(1))

    def round_header(self, chat_id: str, round_id: str) -> RoundHeader:
        row = self.session.execute(select(Round.id, Round.round_no, Round.archive_step).where(
            Round.chat_id == chat_id, Round.id == round_id,
        )).first()
        if row is None:
            raise NotFoundError(f"Round {round_id!r} does not exist in this scope")
        return RoundHeader(*row)

    def latest_round_header(self, chat_id: str) -> RoundHeader | None:
        row = self.session.execute(select(Round.id, Round.round_no, Round.archive_step).where(
            Round.chat_id == chat_id,
        ).order_by(Round.round_no.desc()).limit(1)).first()
        return RoundHeader(*row) if row is not None else None

    def round_worlds(self, chat_id: str) -> dict:
        return dict(self.session.execute(select(
            StateSnapshot.round_id, StateSnapshot.content["世界"],
        ).where(StateSnapshot.chat_id == chat_id, StateSnapshot.round_id.is_not(None))).all())

    def round_dates(self, chat_id: str, round_ids: list[str]) -> dict:
        if not round_ids:
            return {}
        return dict(self.session.execute(select(
            StateSnapshot.round_id, StateSnapshot.content["世界"]["日期"],
        ).where(StateSnapshot.chat_id == chat_id, StateSnapshot.round_id.in_(round_ids))).all())

    def round_summaries_in_range(self, chat_id: str, start_no: int, end_no: int) -> list[tuple]:
        return [tuple(row) for row in self.session.execute(select(
            Round.id, Round.round_no, Round.summary,
        ).where(Round.chat_id == chat_id, Round.round_no >= start_no, Round.round_no <= end_no)
          .order_by(Round.round_no))]

    def states_for_rounds(self, chat_id: str, round_ids: list[str]) -> list[StateSnapshot]:
        if not round_ids:
            return []
        return list(self.session.scalars(select(StateSnapshot).where(
            StateSnapshot.chat_id == chat_id, StateSnapshot.round_id.in_(round_ids),
        )))

    def rounds_in_range(self, chat_id: str, start_no: int, end_no: int) -> list[Round]:
        return list(self.session.scalars(select(Round).where(
            Round.chat_id == chat_id, Round.round_no >= start_no, Round.round_no <= end_no,
        ).order_by(Round.round_no)))

    def episode_bridge_before(self, chat_id: str, start_no: int) -> Round | None:
        """Only the last covered round before the fixed range may bridge episodes."""
        return self.session.scalar(select(Round).join(Episode, Episode.end_round_id == Round.id).where(
            Round.chat_id == chat_id, Episode.chat_id == chat_id, Round.round_no < start_no,
        ).order_by(Round.round_no.desc()).limit(1))

    def episode_for_round(self, chat_id: str, round_id: str) -> Episode | None:
        return self.session.scalar(select(Episode).where(
            Episode.chat_id == chat_id, Episode.created_by_round_id == round_id,
        ))

    def summaries_before(self, chat_id: str, round_no: int, limit: int) -> list[Round]:
        if limit <= 0:
            return []
        records = list(self.session.scalars(select(Round).where(
            Round.chat_id == chat_id, Round.round_no < round_no, Round.archive_step == "complete",
        ).order_by(Round.round_no.desc()).limit(limit)))
        return list(reversed(records))

    def latest_state(self, character_id: str) -> StateSnapshot | None:
        # Round sequence is authoritative, including when the latest archive is pending.
        return self.session.scalar(
            select(StateSnapshot).outerjoin(Round, StateSnapshot.round_id == Round.id)
            .where(StateSnapshot.character_id == character_id)
            .order_by(Round.round_no.desc().nulls_last()).limit(1)
        )

    def states_before(self, character_id: str, round_no: int, limit: int) -> list[tuple[int, dict]]:
        """Up to `limit` snapshots before `round_no`, oldest first, as (round_no, content); initial is 0."""
        if limit <= 0:
            return []
        rows = self.session.execute(
            select(Round.round_no, StateSnapshot.content).select_from(StateSnapshot)
            .outerjoin(Round, StateSnapshot.round_id == Round.id)
            .where(StateSnapshot.character_id == character_id,
                   (Round.round_no < round_no) | StateSnapshot.round_id.is_(None))
            .order_by(Round.round_no.desc().nulls_last()).limit(limit)
        )
        return [(number or 0, content) for number, content in reversed(list(rows))]

    def state_for_round(self, chat_id: str, round_id: str) -> StateSnapshot | None:
        return self.session.scalar(select(StateSnapshot).where(
            StateSnapshot.chat_id == chat_id, StateSnapshot.round_id == round_id,
        ))

    def episodes(self, chat_id: str) -> list[Episode]:
        return list(self.session.scalars(
            select(Episode).join(Round, Episode.start_round_id == Round.id)
            .where(Episode.chat_id == chat_id).order_by(Round.round_no)
        ))

    def unrepresented_rounds(self, chat_id: str) -> list[Round]:
        """Exclude every saved episode's coverage, using sequence rather than IDs."""
        return list(self.session.scalars(self._unrepresented_statement(chat_id)))

    def unrepresented_round_headers(self, chat_id: str) -> list[RoundHeader]:
        statement = self._unrepresented_statement(chat_id).with_only_columns(
            Round.id, Round.round_no, Round.archive_step,
        )
        return [RoundHeader(*row) for row in self.session.execute(statement)]

    def _unrepresented_statement(self, chat_id: str):
        start, end = aliased(Round), aliased(Round)
        covered = (
            select(Episode.id).join(start, Episode.start_round_id == start.id)
            .join(end, Episode.end_round_id == end.id)
            .where(Episode.chat_id == chat_id, Round.round_no >= start.round_no,
                   Round.round_no <= end.round_no).correlate(Round).exists()
        )
        return select(Round).where(
            Round.chat_id == chat_id, ~covered
        ).order_by(Round.round_no)
