"""Every few minutes: sign out and disable demos that have ended, and remove the data of long-finished ones."""

import logging
import threading

from backend.demo.passes import DemoPasses
from backend.shared import scope as scopes

logger = logging.getLogger(__name__)
INTERVAL_SECONDS = 600


def sweep(database, hooks, clock=None) -> None:
    options = {"clock": clock} if clock else {}
    with scopes.scoped(scopes.SYSTEM):
        with database.transaction() as session:
            DemoPasses(session, **options).close_finished()
        with database.transaction() as session:
            chats = DemoPasses(session, **options).purge_old()
    for chat_id in chats:
        hooks.notify(hooks.chat_deleted, chat_id)


class Sweeper:
    def __init__(self, database, hooks, interval: float = INTERVAL_SECONDS):
        self.database, self.hooks, self.interval = database, hooks, interval
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name="demo-sweeper", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        while not self.stopped.wait(self.interval):
            try:
                sweep(self.database, self.hooks)
            except Exception:
                logger.exception("Demo sweep failed")

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=5)
