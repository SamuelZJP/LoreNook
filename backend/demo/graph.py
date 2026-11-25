"""All rows of one account, found through the table metadata, so feature tables are included without listing them.

An account's rows are those with its `owner_id`, plus every row that references one of them, transitively. A
copy gives each `id` a new value and replaces every value equal to an old ID (or the owner's ID), in columns
and inside JSON, so references follow. Only whole values are replaced: an image path containing a chat ID
still points to the original file, which the copy shares and never deletes.

Runs in the system scope, with plain table statements.
"""

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import Table, and_, delete, insert, or_, select, text, tuple_
from sqlalchemy.orm import Session

from backend.repository.models import Base

Rows = dict[Table, list[dict]]


def _key(table: Table, row: dict) -> tuple:
    return tuple(row[column.name] for column in table.primary_key.columns)


def account_rows(session: Session, owner_id: str, tables: Iterable[Table] | None = None) -> Rows:
    tables = list(tables or Base.metadata.sorted_tables)
    rows: Rows = {table: [] for table in tables}
    seen: dict[Table, set] = {table: set() for table in tables}

    def take(table: Table, found) -> bool:
        added = False
        for row in found.mappings():
            key = _key(table, row)
            if key not in seen[table]:
                seen[table].add(key)
                rows[table].append(dict(row))
                added = True
        return added

    for table in tables:
        if "owner_id" in table.c:
            take(table, session.execute(select(table).where(table.c.owner_id == owner_id)))
    changed = True
    while changed:
        changed = False
        for table in tables:
            if "owner_id" in table.c:
                continue  # Its rows were all taken by owner above.
            for foreign_key in table.foreign_key_constraints:
                parent = foreign_key.referred_table
                if parent not in rows or not rows[parent]:
                    continue
                local = list(foreign_key.columns)
                remote = [element.column.name for element in foreign_key.elements]
                values = {tuple(row[name] for name in remote) for row in rows[parent]}
                values = [value for value in values if None not in value]
                for start in range(0, len(values), 400):
                    chunk = values[start:start + 400]
                    condition = (local[0].in_([value[0] for value in chunk]) if len(local) == 1
                                 else tuple_(*local).in_(chunk))
                    changed |= take(table, session.execute(select(table).where(condition)))
    return rows


def _replace(value, mapping: dict[str, str]):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_replace(item, mapping) for item in value]
    if isinstance(value, dict):
        return {_replace(key, mapping): _replace(item, mapping) for key, item in value.items()}
    return value


def copy_rows(session: Session, rows: Rows, from_owner: str, to_owner: str) -> dict[str, str]:
    """Inserts the copy; returns the old → new ID mapping."""
    mapping = {from_owner: to_owner}
    for table, found in rows.items():
        if "id" in table.c and table.c.id.primary_key:
            for row in found:
                mapping[row["id"]] = str(uuid4())
    session.execute(text("PRAGMA defer_foreign_keys=ON"))
    for table, found in rows.items():
        if found:
            session.execute(insert(table), [{name: _replace(value, mapping) for name, value in row.items()}
                                            for row in found])
    return mapping


def delete_rows(session: Session, rows: Rows) -> None:
    session.execute(text("PRAGMA defer_foreign_keys=ON"))
    for table in reversed(list(rows)):
        found = rows[table]
        columns = list(table.primary_key.columns)
        for start in range(0, len(found), 400):
            chunk = found[start:start + 400]
            session.execute(delete(table).where(or_(*(
                and_(*(column == row[column.name] for column in columns)) for row in chunk))))
