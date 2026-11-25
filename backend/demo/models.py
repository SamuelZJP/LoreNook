"""Tables owned by the demo feature. Core tables never reference them."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.repository.models import Base, Identified, Timestamped, UTCDateTime


class DemoPass(Identified, Timestamped, Base):
    """One demo link. Only the token's hash is stored; the account exists once the link is redeemed."""
    __tablename__ = "demo_passes"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    # An unopened link stops working at this time.
    open_before: Mapped[datetime] = mapped_column(UTCDateTime)
    minutes: Mapped[int] = mapped_column(Integer)
    rounds_limit: Mapped[int] = mapped_column(Integer)
    images_limit: Mapped[int] = mapped_column(Integer)
    rounds_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    images_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    redeemed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), unique=True)
    # When the account's data was removed.
    purged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (
        CheckConstraint("minutes > 0 AND rounds_limit >= 0 AND images_limit >= 0", name="positive_limits"),
        CheckConstraint("(redeemed_at IS NULL) = (expires_at IS NULL) AND (redeemed_at IS NULL) = (user_id IS NULL)",
                        name="redeemed_together"),
    )
