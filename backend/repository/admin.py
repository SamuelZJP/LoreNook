"""Explicit table registry and parameterized raw operations for data management."""

from sqlalchemy import and_, delete, insert, select, text, update
from sqlalchemy.orm import Session

from backend.repository.models import (
    Character, Chat, ChatModelBinding, Definition, Episode, ModelConfig, Round,
    StateSnapshot, UserIdentity, WritingPreset,
)
from backend.shared.errors import AdminDataError, ConflictError, NotFoundError

TABLES = {model.__tablename__: model.__table__ for model in (
    Chat, Character, UserIdentity, Definition, WritingPreset, ModelConfig, ChatModelBinding,
    Round, StateSnapshot, Episode,
)}


class AdminRepository:
    def __init__(self, session: Session):
        self.session = session

    def rows(self) -> dict[str, list[dict]]:
        return {name: [dict(row) for row in self.session.execute(
            select(table).order_by(*table.primary_key.columns)
        ).mappings()] for name, table in TABLES.items()}

    def _where(self, name: str, key: dict[str, str]):
        table = TABLES[name]
        if set(key) != {column.name for column in table.primary_key.columns}:
            raise AdminDataError("key 必须完整且仅包含目标表的主键字段")
        return and_(*(table.c[field] == value for field, value in key.items()))

    def row(self, name: str, key: dict[str, str]) -> dict:
        row = self.session.execute(select(TABLES[name]).where(self._where(name, key))).mappings().first()
        if row is None:
            raise NotFoundError("数据管理目标记录不存在")
        return dict(row)

    def create(self, name: str, values: dict) -> None:
        self.session.execute(insert(TABLES[name]).values(**values))

    def update(self, name: str, key: dict[str, str], values: dict) -> None:
        self.session.execute(update(TABLES[name]).where(self._where(name, key)).values(**values))

    def delete(self, name: str, key: dict[str, str]) -> None:
        self.row(name, key)
        self.session.execute(delete(TABLES[name]).where(self._where(name, key)))

    def defer_references(self) -> None:
        self.session.execute(text("PRAGMA defer_foreign_keys=ON"))

    def check_references(self) -> None:
        if self.session.execute(text("PRAGMA foreign_key_check")).first() is not None:
            raise ConflictError("批量修改后的数据引用不存在或归属不符")
