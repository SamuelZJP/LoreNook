"""Injectable initial-state boundary and JSON result validation."""

import json
from typing import Protocol

from pydantic import JsonValue, TypeAdapter, ValidationError

from backend.shared.errors import StateInitializationError
from backend.modules.state.world import validate_world


class InitialStateFactory(Protocol):
    def __call__(self, schema_source: str) -> dict[str, JsonValue]:
        """Pure local computation: apply defaults and schema validation/correction."""
        ...


def empty_schema_state(schema_source: str) -> dict[str, JsonValue]:
    if schema_source.strip():
        raise StateInitializationError("当前注入的空状态工厂仅支持空白 Schema")
    return {}


def build_initial_state(factory: InitialStateFactory, schema_source: str) -> dict[str, JsonValue]:
    try:
        state = TypeAdapter(dict[str, JsonValue]).validate_python(factory(schema_source), strict=True)
        # Reject NaN/infinity and detach mutable objects retained by an implementation.
        return validate_world(json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False).encode("utf-8")))
    except StateInitializationError:
        raise
    except (ValidationError, ValueError, TypeError) as error:
        raise StateInitializationError("初始状态无效：" + str(error)[:1900]) from error
