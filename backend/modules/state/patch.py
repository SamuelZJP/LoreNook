"""Sequential add/replace/remove JSON Patch; invalid operations are skipped."""

from copy import deepcopy
import re


def _index(token: str, length: int, *, add: bool = False) -> int:
    if add and token == "-":
        return length
    if not re.fullmatch(r"0|[1-9][0-9]*", token):
        raise ValueError("Invalid array index")
    value = int(token)
    if value >= length + int(add):
        raise IndexError(value)
    return value


def _apply(target: dict, operation) -> dict:
    if not isinstance(operation, dict) or operation.get("op") not in {"add", "replace", "remove"}:
        raise ValueError("Unsupported operation")
    path, op = operation.get("path"), operation["op"]
    if not isinstance(path, str) or (path and not path.startswith("/")):
        raise ValueError("Invalid JSON Pointer")
    if op != "remove" and "value" not in operation:
        raise ValueError("Missing value")
    if path == "":
        if op == "remove" or not isinstance(operation["value"], dict):
            raise ValueError("State root must remain an object")
        return deepcopy(operation["value"])
    tokens = path[1:].split("/")
    if any(re.search(r"~(?![01])", token) for token in tokens):
        raise ValueError("Invalid pointer escape")
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in tokens]
    parent = target
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            parent = parent[token]
        elif isinstance(parent, list):
            parent = parent[_index(token, len(parent))]
        else:
            raise TypeError("Invalid parent")
    key = tokens[-1]
    if isinstance(parent, dict):
        if op in {"replace", "remove"} and key not in parent:
            raise KeyError(key)
        if op == "remove":
            del parent[key]
        else:
            parent[key] = deepcopy(operation["value"])
    elif isinstance(parent, list):
        index = _index(key, len(parent), add=op == "add")
        if op == "add":
            parent.insert(index, deepcopy(operation["value"]))
        elif op == "remove":
            del parent[index]
        else:
            parent[index] = deepcopy(operation["value"])
    else:
        raise TypeError("Invalid parent")
    return target


def apply_operations(state: dict, operations: list) -> tuple[dict, int]:
    result, skipped = deepcopy(state), 0
    for operation in operations:
        try:
            result = _apply(result, operation)
        except (KeyError, IndexError, ValueError, TypeError):
            skipped += 1
    return result, skipped
