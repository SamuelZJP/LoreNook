"""Tables owned by the recall feature. Core tables never reference them."""

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.repository.models import Base


class ChatRecallSettings(Base):
    """Absent row or no model means recall is off."""
    __tablename__ = "chat_recall_settings"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    model_config_id: Mapped[str | None] = mapped_column(String(36))
    depth: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    __table_args__ = (
        ForeignKeyConstraint(["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"]),
        CheckConstraint("depth >= 0", name="depth_nonnegative"),
    )
