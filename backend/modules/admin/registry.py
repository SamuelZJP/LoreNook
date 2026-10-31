"""Data management works on registered tables. Features add theirs here, without the core knowing them."""

from backend.repository.admin import TABLES
from backend.schemas.admin import ROW_SCHEMAS


def register_table(model, row_schema) -> None:
    TABLES[model.__tablename__] = model.__table__
    ROW_SCHEMAS[model.__tablename__] = row_schema
