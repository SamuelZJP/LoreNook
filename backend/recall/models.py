"""Tables owned by the recall feature. Core tables never reference them."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.repository.models import Base


class ChatRecallSettings(Base):
    """Recall runs only when enabled with a model. Absent row means off."""
    __tablename__ = "chat_recall_settings"
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="enabled_bool"), default=False, server_default="0")
    model_config_id: Mapped[str | None] = mapped_column(String(36))
    depth: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    episode_limit: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    summary_limit: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    __table_args__ = (
        ForeignKeyConstraint(["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"]),
        CheckConstraint("depth >= 0", name="depth_nonnegative"),
        CheckConstraint("episode_limit >= 0 AND summary_limit >= 0", name="limits_nonnegative"),
    )
