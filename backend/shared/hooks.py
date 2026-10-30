"""Generic extension points, so optional features can follow core events the core knows nothing about."""

from collections.abc import Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppHooks:
    # (chat_id, round_id), after an archive completes. Failures are logged, never raised.
    round_archived: list[Callable[[str, str], None]] = field(default_factory=list)
    # (chat_id), after a chat is deleted. Failures are logged, never raised.
    chat_deleted: list[Callable[[str], None]] = field(default_factory=list)
    # (session, chat_id, payload), inside the transaction creating a chat. Failures abort the creation.
    chat_created: list[Callable] = field(default_factory=list)

    def notify(self, listeners: list[Callable], *args) -> None:
        for listener in listeners:
            try:
                listener(*args)
            except Exception:
                logger.exception("Hook %s failed", getattr(listener, "__qualname__", listener))
