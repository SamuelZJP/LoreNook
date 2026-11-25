"""Slows down password guessing: after a few failures a key must wait, longer each time.

Kept in process memory, which matches the single-worker deployment. Keys are a username and a client address.
"""

import threading
import time

FREE_FAILURES = 4  # The fifth failure in a row starts the wait.
FIRST_WAIT = 60.0
MAX_WAIT = 15 * 60.0
FORGET_AFTER = 24 * 3600.0


class LoginThrottle:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.entries: dict[str, tuple[int, float]] = {}  # key → (failures, blocked until)

    def wait_seconds(self, *keys: str) -> int:
        """How long these keys must still wait; 0 when a try is allowed."""
        now = self.clock()
        with self.lock:
            until = max((self.entries.get(key, (0, 0.0))[1] for key in keys), default=0.0)
        return max(0, int(until - now + 0.999))

    def failed(self, *keys: str) -> None:
        now = self.clock()
        with self.lock:
            self._forget_old(now)
            for key in keys:
                failures = self.entries.get(key, (0, 0.0))[0] + 1
                over = failures - FREE_FAILURES
                until = now + min(MAX_WAIT, FIRST_WAIT * 2 ** (over - 1)) if over > 0 else 0.0
                self.entries[key] = (failures, until)

    def succeeded(self, *keys: str) -> None:
        with self.lock:
            for key in keys:
                self.entries.pop(key, None)

    def _forget_old(self, now: float) -> None:
        if len(self.entries) < 10_000:
            return
        self.entries = {key: value for key, value in self.entries.items() if now - value[1] < FORGET_AFTER}
