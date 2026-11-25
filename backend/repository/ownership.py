"""Row ownership, applied to every session: each user sees and writes only their own rows.

Every ORM statement on an `Owned` table (selects, `session.get`, joins, bulk updates and deletes) gets
`owner_id = <current user>` added; new rows take the current user as owner. Tables without an owner are
reached through an owned parent (a chat, a character), which the API checks first.

Without a scope nothing owned is visible, and querying it raises, so a forgotten scope fails loudly
instead of leaking. The system scope sees everything; it is for administration and startup tasks.
"""

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from backend.repository.models import Owned
from backend.shared import scope as scopes


class ScopeMissingError(RuntimeError):
    """Owned data was touched outside any scope."""


def _is_owned(mapper) -> bool:
    return issubclass(mapper.class_, Owned)


def _filter(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    if state.is_column_load or state.is_relationship_load:
        return  # Follow-up loads of rows the first statement already filtered.
    scope = scopes.current()
    if scope is not None and scope.is_system:
        return
    if scope is None and any(_is_owned(mapper) for mapper in state.all_mappers):
        raise ScopeMissingError("Owned data requires a user or system scope")
    owner = scope.user_id if scope is not None else None
    state.statement = state.statement.options(
        with_loader_criteria(Owned, lambda cls: cls.owner_id == owner, include_aliases=True))


def _assign_owner(session: Session, _context, _instances) -> None:
    for record in session.new:
        if isinstance(record, Owned) and record.owner_id is None:
            scope = scopes.current()
            if scope is None or scope.is_system:
                raise ScopeMissingError(f"A new {type(record).__name__} needs an owner")
            record.owner_id = scope.user_id


def install(sessions: sessionmaker) -> None:
    event.listen(sessions, "do_orm_execute", _filter)
    event.listen(sessions, "before_flush", _assign_owner)
