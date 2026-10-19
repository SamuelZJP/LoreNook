"""Character-authored Python/Pydantic schemas, stored as source in the database."""

from contextlib import contextmanager
from copy import deepcopy
import json
import sys
from types import ModuleType
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, JsonValue, TypeAdapter

from backend.shared.errors import StateInitializationError, StateSchemaError
from backend.modules.state.world import validate_world


class StateValidator(Protocol):
    def __call__(self, source: str, content: dict[str, JsonValue]) -> dict[str, JsonValue]: ...


def json_state(content) -> dict[str, JsonValue]:
    value = TypeAdapter(dict[str, JsonValue]).validate_python(content, strict=True)
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))


@contextmanager
def schema_model(source: str):
    # A unique module gives forward annotations and nested classes a correct namespace.
    # Schema source is ordinary application Python code, not a sandboxed template.
    name = f"lorenook_state_{uuid4().hex}"
    module = ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(source, "<state_schema>", "exec"), module.__dict__)
        model = getattr(module, "Schema", None)
        if not isinstance(model, type) or not issubclass(model, BaseModel) or model is BaseModel:
            raise ValueError("源码必须定义 Pydantic BaseModel 子类 Schema")
        model.model_rebuild(_types_namespace=module.__dict__)
        yield model
    finally:
        sys.modules.pop(name, None)


def validate_state(source: str, content: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        value = json_state(content)
        if not source.strip():
            return validate_world(value)
        with schema_model(source) as model:
            return validate_world(json_state(model.model_validate(deepcopy(value)).model_dump(mode="json", by_alias=True)))
    except Exception as error:
        raise StateSchemaError("状态 Schema 执行失败：" + str(error)[:1900]) from error


def python_initial_state(source: str) -> dict[str, JsonValue]:
    try:
        return validate_state(source, {})
    except StateSchemaError as error:
        raise StateInitializationError(str(error)) from error


def checked_state(validator: StateValidator, source: str, content: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        return validate_world(json_state(validator(source, json_state(content))))
    except StateSchemaError:
        raise
    except Exception as error:
        raise StateSchemaError(str(error)[:2000] or "状态校验失败") from error
