"""Whose data the current unit of work may see: one user, or the whole system.

Set once per request by the API and per job by background workers; read by the storage layer, which
filters every owned table by it, and by the model client, which decides which addresses it may reach.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    user_id: str | None  # None: the whole system, for administration and startup tasks
    is_admin: bool

    @property
    def is_system(self) -> bool:
        return self.user_id is None


SYSTEM = Scope(user_id=None, is_admin=True)

_current: ContextVar[Scope | None] = ContextVar("lorenook_scope", default=None)


def current() -> Scope | None:
    return _current.get()


def user_scope(user_id: str, is_admin: bool = False) -> Scope:
    return Scope(user_id=user_id, is_admin=is_admin)


@contextmanager
def scoped(scope: Scope | None) -> Iterator[None]:
    token = _current.set(scope)
    try:
        yield
    finally:
        _current.reset(token)


def enter(scope: Scope | None) -> None:
    """Set the scope for the rest of the current context, e.g. a request task or a worker job."""
    _current.set(scope)
