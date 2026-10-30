"""Tables owned by the illustration feature. Core tables never reference them."""

from typing import Any

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.repository.models import Base, Identified, Timestamped


class ImageWorkflow(Identified, Timestamped, Base):
    """A ComfyUI API-format workflow with {{placeholders}} and the template that writes its prompts."""
    __tablename__ = "image_workflows"
    chat_id: Mapped[str | None] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str] = mapped_column(Text)
    workflow: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))
    prompt_template: Mapped[str] = mapped_column(Text, default="", server_default="")
    width: Mapped[int] = mapped_column(Integer, default=1344, server_default="1344")
    height: Mapped[int] = mapped_column(Integer, default=768, server_default="768")
    __table_args__ = (
        UniqueConstraint("id", "chat_id"),
        CheckConstraint("json_valid(workflow) AND json_type(workflow) = 'object'", name="workflow_object"),
        CheckConstraint("width BETWEEN 64 AND 8192 AND height BETWEEN 64 AND 8192", name="image_size"),
    )


class ChatIllustrationSettings(Base):
    """Absent row means illustrations are off."""
    __tablename__ = "chat_illustration_settings"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), default="off", server_default="off")
    image_workflow_id: Mapped[str | None] = mapped_column(String(36))
    model_config_id: Mapped[str | None] = mapped_column(String(36))
    # Main character ids chosen by the user; empty means the default.
    focus: Mapped[list[str]] = mapped_column(JSON(none_as_null=True), default=list, server_default="[]")
    __table_args__ = (
        ForeignKeyConstraint(["image_workflow_id", "chat_id"], ["image_workflows.id", "image_workflows.chat_id"]),
        ForeignKeyConstraint(["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"]),
        CheckConstraint("mode IN ('off', 'every_round', 'scene_change', 'manual')", name="valid_mode"),
    )


class CastMember(Identified, Base):
    """Someone who can be drawn. Lives on a character card and is copied into chats with it."""
    __tablename__ = "cast_members"
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    name: Mapped[str] = mapped_column(Text)
    appearance: Mapped[str] = mapped_column(Text, default="", server_default="")
    reference_image: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint('"order" >= 0', name="nonnegative_order"),)


class IdentityAppearance(Base):
    """How the user's persona is drawn. Absent row means no description."""
    __tablename__ = "identity_appearances"
    user_identity_id: Mapped[str] = mapped_column(ForeignKey("user_identities.id", ondelete="CASCADE"), primary_key=True)
    appearance: Mapped[str] = mapped_column(Text, default="", server_default="")
    reference_image: Mapped[str | None] = mapped_column(Text)


class Illustration(Identified, Timestamped, Base):
    """One generation attempt for a round; the newest per round is the one shown."""
    __tablename__ = "illustrations"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    round_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    seed: Mapped[int] = mapped_column(Integer)
    # Main characters of this attempt as [{"id", "name"}], fixed when it is requested.
    focus: Mapped[list[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), default=list, server_default="[]")
    prompt: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    error: Mapped[str | None] = mapped_column(Text)
    # Relative to the image directory.
    file_name: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    hidden: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="hidden_bool"), default=False, server_default="0"
    )
    __table_args__ = (
        ForeignKeyConstraint(["round_id", "chat_id"], ["rounds.id", "rounds.chat_id"], ondelete="CASCADE"),
        CheckConstraint("status IN ('pending', 'prompting', 'rendering', 'ready', 'failed')", name="valid_status"),
        CheckConstraint("status != 'ready' OR (file_name IS NOT NULL AND media_type IS NOT NULL)", name="ready_file"),
        CheckConstraint("status != 'failed' OR error IS NOT NULL", name="failed_error"),
        CheckConstraint("prompt IS NULL OR (json_valid(prompt) AND json_type(prompt) = 'object')", name="prompt_object"),
        Index("uq_illustrations_one_active", "round_id", unique=True,
              sqlite_where=text("status IN ('pending', 'prompting', 'rendering')")),
    )
