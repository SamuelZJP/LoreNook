"""ComfyUI API-format workflows with {{name}} placeholders, all filled by LoreNook.

`prompt` is the rendered text and is required. `images` is a JSON array of uploaded reference images
inside a string, because ComfyUI reads a real array as a node link. `seed`, `width` and `height` are
numbers. A string that is exactly one placeholder takes the raw value (so a seed stays an integer);
placeholders inside longer strings are replaced as text.
"""

from copy import deepcopy
import re

from pydantic import JsonValue

from backend.illustrations.errors import IllustrationError

PLACEHOLDER = re.compile(r"\{\{\s*((?:image:)?[A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
KNOWN = frozenset({"prompt", "images", "seed", "width", "height"})


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _names(workflow: dict[str, JsonValue]) -> set[str]:
    return {match.group(1) for text in _strings(workflow) for match in PLACEHOLDER.finditer(text)}


def uses_images(workflow: dict[str, JsonValue]) -> bool:
    return "images" in _names(workflow)


def validate_workflow(workflow: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if not workflow:
        raise IllustrationError("工作流不能为空")
    for node in workflow.values():
        if (not isinstance(node, dict) or not isinstance(node.get("class_type"), str)
                or not isinstance(node.get("inputs"), dict)):
            raise IllustrationError("工作流必须是 ComfyUI API 格式：每个节点都有 class_type 和 inputs")
    names = _names(workflow)
    unknown = sorted(names - KNOWN)
    if unknown:
        listed = "、".join(f"{{{{{name}}}}}" for name in unknown)
        raise IllustrationError(f"工作流包含不支持的占位符：{listed}。可用的占位符：prompt、images、seed、width、height")
    if "prompt" not in names:
        raise IllustrationError("工作流需要 {{prompt}} 占位符")
    return workflow


def fill_workflow(workflow: dict[str, JsonValue], values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    def value_of(name: str):
        if name not in values:
            raise IllustrationError(f"工作流占位符 {{{{{name}}}}} 没有对应的值")
        return values[name]

    def fill(value):
        if isinstance(value, str):
            whole = PLACEHOLDER.fullmatch(value)
            if whole:
                return deepcopy(value_of(whole.group(1)))
            return PLACEHOLDER.sub(lambda match: str(value_of(match.group(1))), value)
        if isinstance(value, dict):
            return {key: fill(item) for key, item in value.items()}
        if isinstance(value, list):
            return [fill(item) for item in value]
        return value

    return fill(workflow)
