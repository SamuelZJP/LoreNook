"""Physical storage model. JSON fields are replaced as whole values on updates."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, MetaData, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamps must include a timezone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Identified:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), server_default=text("CURRENT_TIMESTAMP")
    )


class Chat(Identified, Timestamped, Base):
    __tablename__ = "chats"
    title: Mapped[str] = mapped_column(Text)
    writing_preset_id: Mapped[str | None] = mapped_column(String(36))
    recent_rounds: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    min_summaries: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    __table_args__ = (
        CheckConstraint("recent_rounds >= 0 AND min_summaries >= 0", name="memory_counts"),
        ForeignKeyConstraint(
            ["writing_preset_id", "id"], ["writing_presets.id", "writing_presets.chat_id"],
            name="fk_chats_selected_preset", deferrable=True, initially="DEFERRED", use_alter=True,
        ),
    )


class Character(Identified, Timestamped, Base):
    __tablename__ = "characters"
    chat_id: Mapped[str | None] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(Text)
    avatar: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    state_schema: Mapped[str] = mapped_column(Text, default="", server_default="")
    state_reference: Mapped[str] = mapped_column(Text, default="", server_default="")
    state_update_rules: Mapped[str] = mapped_column(Text, default="", server_default="")
    state_script: Mapped[str] = mapped_column(Text, default="", server_default="")
    state_script_history: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    __table_args__ = (UniqueConstraint("id", "chat_id"),)


class CharacterScene(Identified, Base):
    """An opening: First Message plus initial-state overrides applied through the character's Schema."""
    __tablename__ = "character_scenes"
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    first_message: Mapped[str] = mapped_column(Text, default="", server_default="")
    initial_state: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True), default=dict, server_default="{}")
    __table_args__ = (
        CheckConstraint('"order" >= 0', name="nonnegative_order"),
        CheckConstraint("json_valid(initial_state) AND json_type(initial_state) = 'object'", name="initial_state_object"),
    )


class UserIdentity(Identified, Timestamped, Base):
    __tablename__ = "user_identities"
    chat_id: Mapped[str | None] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(Text)
    avatar: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class Definition(Identified, Base):
    __tablename__ = "definitions"
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    user_identity_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_identities.id", ondelete="CASCADE"), index=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    enabled: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="enabled_bool"), default=True, server_default="1"
    )
    has_template: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="template_bool"), default=False, server_default="0"
    )
    content: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "(character_id IS NOT NULL AND user_identity_id IS NULL) OR "
            "(character_id IS NULL AND user_identity_id IS NOT NULL)", name="exactly_one_owner"
        ),
        CheckConstraint('"order" >= 0', name="nonnegative_order"),
    )


class WritingPreset(Identified, Timestamped, Base):
    __tablename__ = "writing_presets"
    chat_id: Mapped[str | None] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("id", "chat_id"),)


class ModelConfig(Identified, Base):
    __tablename__ = "model_configs"
    chat_id: Mapped[str | None] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    api_type: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str] = mapped_column(Text)
    api_key: Mapped[str] = mapped_column(Text, default="", server_default="")
    model: Mapped[str] = mapped_column(Text)
    default_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), default=dict, server_default="{}"
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, server_default="300")
    __table_args__ = (
        UniqueConstraint("id", "chat_id"),
        CheckConstraint("json_valid(default_parameters) AND json_type(default_parameters) = 'object'",
                        name="parameters_object"),
    )


class ChatModelBinding(Base):
    __tablename__ = "chat_model_bindings"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32), primary_key=True)
    model_config_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (
        ForeignKeyConstraint(
            ["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("purpose IN ('writing', 'state_update', 'round_summary', 'episode_summary')",
                        name="valid_purpose"),
    )


class Round(Identified, Timestamped, Base):
    __tablename__ = "rounds"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    round_no: Mapped[int] = mapped_column(Integer)
    user_input: Mapped[str] = mapped_column(Text)
    ai_output: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    archive_step: Mapped[str] = mapped_column(String(32), default="state_update", server_default="state_update")
    archive_error: Mapped[str | None] = mapped_column(Text)
    episode_required: Mapped[bool | None] = mapped_column(Boolean(create_constraint=True, name="required_bool"))
    episode_start_round_id: Mapped[str | None] = mapped_column(String(36))
    episode_end_round_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (
        UniqueConstraint("chat_id", "round_no"),
        UniqueConstraint("id", "chat_id"),
        CheckConstraint("round_no >= 1", name="positive_number"),
        CheckConstraint("archive_step IN ('state_update', 'round_summary', 'episode_decision', "
                        "'episode_summary', 'complete')", name="valid_step"),
        CheckConstraint(
            "(episode_required IS NULL AND episode_start_round_id IS NULL AND episode_end_round_id IS NULL) OR "
            "(episode_required IS NOT NULL AND episode_required = 0 AND episode_start_round_id IS NULL AND episode_end_round_id IS NULL) OR "
            "(episode_required IS NOT NULL AND episode_required = 1 AND episode_start_round_id IS NOT NULL AND episode_end_round_id IS NOT NULL)",
            name="decision_shape",
        ),
        CheckConstraint("archive_step NOT IN ('episode_decision', 'episode_summary', 'complete') "
                        "OR (summary IS NOT NULL AND length(trim(summary)) > 0)", name="summary_progress"),
        CheckConstraint("archive_step != 'episode_summary' OR (episode_required IS NOT NULL AND episode_required = 1)", name="episode_progress"),
        CheckConstraint("archive_step != 'complete' OR episode_required IS NOT NULL", name="complete_decision"),
        CheckConstraint("archive_step != 'complete' OR archive_error IS NULL", name="complete_no_error"),
        ForeignKeyConstraint(
            ["episode_start_round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
            name="fk_rounds_episode_start", deferrable=True, initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["episode_end_round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
            name="fk_rounds_episode_end", deferrable=True, initially="DEFERRED",
        ),
        Index("uq_rounds_one_pending", "chat_id", unique=True,
              sqlite_where=text("archive_step != 'complete'")),
    )


class StateSnapshot(Identified, Timestamped, Base):
    __tablename__ = "state_snapshots"
    # Physical scope column lets SQLite enforce both owners belong to the same chat.
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    character_id: Mapped[str] = mapped_column(String(36), index=True)
    round_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    __table_args__ = (
        ForeignKeyConstraint(["character_id", "chat_id"], ["characters.id", "characters.chat_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["round_id", "chat_id"], ["rounds.id", "rounds.chat_id"], ondelete="CASCADE"),
        CheckConstraint("json_valid(content) AND json_type(content) = 'object'", name="state_object"),
        Index("uq_state_snapshots_initial", "character_id", unique=True,
              sqlite_where=text("round_id IS NULL")),
    )


class Episode(Identified, Timestamped, Base):
    __tablename__ = "episodes"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    start_round_id: Mapped[str] = mapped_column(String(36))
    end_round_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Imported history may have no corresponding archive workflow round.
    created_by_round_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    __table_args__ = (
        CheckConstraint("length(trim(summary)) > 0", name="nonempty_summary"),
        ForeignKeyConstraint(["start_round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
                             name="fk_episodes_start", deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["end_round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
                             name="fk_episodes_end", deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["created_by_round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
                             name="fk_episodes_creator", deferrable=True, initially="DEFERRED"),
    )


class ChatTemplate(Identified, Timestamped, Base):
    """Starting values for the new-chat form. Library IDs inside are references only, never enforced."""
    __tablename__ = "chat_templates"
    name: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="default_bool"), default=False, server_default="0"
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True), default=dict, server_default="{}")
    __table_args__ = (
        CheckConstraint("json_valid(settings) AND json_type(settings) = 'object'", name="settings_object"),
        Index("uq_chat_templates_one_default", "is_default", unique=True, sqlite_where=text("is_default = 1")),
    )
