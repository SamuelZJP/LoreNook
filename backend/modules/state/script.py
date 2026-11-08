"""Optional character-authored state script: runs on a generated state with the states before it."""

from copy import deepcopy

from pydantic import JsonValue

from backend.modules.state.schema import json_state, loaded_module
from backend.shared.errors import StateScriptError

FILENAME = "<state_script>"


def _process(module):
    process = getattr(module, "process", None)
    if not callable(process):
        raise ValueError("源码必须定义函数 process(state, previous, history)")
    return process


def check_state_script(source: str) -> None:
    if not source.strip():
        return
    try:
        with loaded_module(source, FILENAME) as module:
            _process(module)
    except Exception as error:
        raise StateScriptError("状态脚本无效：" + str(error)[:1900]) from error


def run_state_script(source: str, state: dict[str, JsonValue], previous: dict[str, JsonValue],
                     history: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Return the script's state; an empty script returns the state unchanged."""
    if not source.strip():
        return state
    try:
        with loaded_module(source, FILENAME) as module:
            result = _process(module)(deepcopy(state), deepcopy(previous), deepcopy(history))
        if not isinstance(result, dict):
            raise ValueError("process 必须返回状态对象")
        return json_state(result)
    except Exception as error:
        raise StateScriptError("状态脚本执行失败：" + (str(error) or type(error).__name__)[:1900]) from error
