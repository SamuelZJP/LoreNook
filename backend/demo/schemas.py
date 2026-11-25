from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from backend.schemas.common import Contract


class RedeemRequest(Contract):
    token: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RedeemResult(Contract):
    # The chat to open; None when the template has none.
    chat_id: str | None


class DemoStatus(Contract):
    expires_at: datetime
    rounds_left: int
    images_left: int
