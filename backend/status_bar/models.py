"""Tables owned by the status bar feature. Core tables never reference them."""

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.repository.models import Base


class CharacterStatusBar(Base):
    """A character's status bar code, copied into chats with the card. Absent row means none."""
    __tablename__ = "character_status_bars"
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(Text)


class ChatStatusBarSettings(Base):
    """Absent row means on: a status bar shows whenever the chat's character has one."""
    __tablename__ = "chat_status_bar_settings"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="enabled_bool"), default=True, server_default="1")
