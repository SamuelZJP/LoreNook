"""Live progress of running jobs: written by the worker thread, streamed to browsers as server-sent events."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
import json
from threading import Lock

from backend.illustrations.schemas import IllustrationProgress

RESEND_SECONDS = 15.0


class ProgressBoard:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, tuple[str, IllustrationProgress]] = {}
        self._listeners: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()

    def _notify(self) -> None:
        for loop, changed in self._listeners:
            loop.call_soon_threadsafe(changed.set)

    def set(self, illustration_id: str, chat_id: str, progress: IllustrationProgress) -> None:
        with self._lock:
            self._jobs[illustration_id] = (chat_id, progress)
            self._notify()

    def clear(self, illustration_id: str) -> None:
        with self._lock:
            self._jobs.pop(illustration_id, None)
            self._notify()

    def jobs(self, chat_id: str) -> dict[str, IllustrationProgress]:
        with self._lock:
            return {key: progress for key, (owner, progress) in self._jobs.items() if owner == chat_id}

    @contextmanager
    def listen(self) -> Iterator[asyncio.Event]:
        entry = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._listeners.add(entry)
        try:
            yield entry[1]
        finally:
            with self._lock:
                self._listeners.discard(entry)


async def progress_events(board: ProgressBoard, chat_id: str) -> AsyncIterator[str]:
    """Each event is the chat's whole state, so a missed one is harmless and a resend doubles as keep-alive.

    Ends once nothing is running: an idle tab holds no connection, and the browser's automatic
    reconnect picks up whatever starts next until the page closes the stream.
    """
    with board.listen() as changed:
        while True:
            changed.clear()
            jobs = board.jobs(chat_id)
            payload = {key: progress.model_dump() for key, progress in jobs.items()}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if not jobs:
                return
            try:
                await asyncio.wait_for(changed.wait(), RESEND_SECONDS)
            except TimeoutError:
                pass
