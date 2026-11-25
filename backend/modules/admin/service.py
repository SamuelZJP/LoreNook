import hashlib
import json
from datetime import datetime

from pydantic import ValidationError

from backend.modules.admin.consistency import check_consistency
from backend.modules.state.world import validate_world
from backend.repository.admin import AdminRepository, TABLES
from backend.schemas.admin import (
    AdminBatch, AdminBatchResult, AdminChange, AdminCreate, AdminDelete,
    AdminSnapshot, AdminTableInfo, ROW_SCHEMAS,
)
from backend.shared.errors import AdminDataError, ConflictError


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("不是可序列化的数据库字段类型")


def _serialized(tables: dict) -> str:
    return json.dumps(tables, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      default=_json_default)


def _revision(tables: dict) -> str:
    return hashlib.sha256(_serialized(tables).encode("utf-8")).hexdigest()


def _validated(name: str, values: dict) -> dict:
    try:
        row = ROW_SCHEMAS[name].model_validate(values).model_dump()
        _serialized(row).encode("utf-8")
        return row
    except (ValidationError, ValueError, TypeError, RecursionError):
        raise AdminDataError(f"{name} 字段名、必填项、类型或 JSON 内容无效") from None


class AdminService:
    def __init__(self, repository: AdminRepository):
        self.repository = repository

    def catalog(self) -> list[AdminTableInfo]:
        return [AdminTableInfo(name=name, primary_key=[column.name for column in table.primary_key.columns],
                               row_schema=ROW_SCHEMAS[name].model_json_schema()) for name, table in TABLES.items()]

    def snapshot(self, *, include_secrets: bool = False) -> AdminSnapshot:
        tables = self.repository.rows()
        revision = _revision(tables)
        if not include_secrets:
            for model in tables["model_configs"]:
                model["has_api_key"] = bool(model.pop("api_key"))
        return AdminSnapshot(revision=revision, tables=json.loads(_serialized(tables)))

    def apply(self, batch: AdminBatch, acting_user_id: str | None = None) -> AdminBatchResult:
        if _revision(self.repository.rows()) != batch.expected_revision:
            raise ConflictError("数据库已变化，请重新读取数据后再提交修改")
        self.repository.defer_references()
        changes = []
        for operation in batch.operations:
            name = operation.table
            if name not in TABLES:
                raise AdminDataError("目标表不存在或不可管理")
            if isinstance(operation, AdminDelete):
                self.repository.delete(name, operation.key)
                key = operation.key
            else:
                if isinstance(operation, AdminCreate):
                    existing = {"owner_id": acting_user_id} if acting_user_id and "owner_id" in TABLES[name].c else {}
                else:
                    existing = self.repository.row(name, operation.key)
                row = _validated(name, {**existing, **operation.values})
                if name == "state_snapshots":
                    try:
                        validate_world(row["content"])
                    except ValueError as error:
                        raise AdminDataError(str(error)) from error
                if isinstance(operation, AdminCreate):
                    self.repository.create(name, row)
                else:
                    self.repository.update(name, operation.key, row)
                key = {column.name: row[column.name] for column in TABLES[name].primary_key.columns}
            changes.append(AdminChange(action=operation.action, table=name, key=key))
        self.repository.check_references()
        tables = self.repository.rows()
        # Check cascades and the final graph, including records not explicitly in the batch.
        for name, rows in tables.items():
            for row in rows:
                _validated(name, row)
        check_consistency(tables)
        return AdminBatchResult(revision=_revision(tables), changes=changes)
