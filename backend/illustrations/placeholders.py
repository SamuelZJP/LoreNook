"""ComfyUI API-format workflows with {{name}} placeholders.

`seed`, `width` and `height` are filled by LoreNook. `image:focus_N` is the reference image of main
character N, uploaded to ComfyUI first; a workflow using one is image-to-image. Every other name is a
prompt field the model must return. A string that is exactly one placeholder takes the raw value (so
a seed stays an integer); placeholders inside longer strings are replaced as text.
"""

from copy import deepcopy
import re

from pydantic import JsonValue

from backend.illustrations.errors import IllustrationError

PLACEHOLDER = re.compile(r"\{\{\s*((?:image:)?[A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
IMAGE_INPUT = re.compile(r"image:focus_([1-9][0-9]*)")
BUILTINS = frozenset({"seed", "width", "height"})


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


def prompt_fields(workflow: dict[str, JsonValue]) -> list[str]:
    return sorted(name for name in _names(workflow) - BUILTINS if not name.startswith("image:"))


def image_inputs(workflow: dict[str, JsonValue]) -> list[str]:
    """Image placeholders in main-character order, e.g. ['image:focus_1', 'image:focus_2']."""
    names = [name for name in _names(workflow) if name.startswith("image:")]
    return sorted(names, key=lambda name: int(IMAGE_INPUT.fullmatch(name).group(1)) if IMAGE_INPUT.fullmatch(name) else 0)


def validate_workflow(workflow: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if not workflow:
        raise IllustrationError("工作流不能为空")
    for node in workflow.values():
        if (not isinstance(node, dict) or not isinstance(node.get("class_type"), str)
                or not isinstance(node.get("inputs"), dict)):
            raise IllustrationError("工作流必须是 ComfyUI API 格式：每个节点都有 class_type 和 inputs")
    for name in image_inputs(workflow):
        if not IMAGE_INPUT.fullmatch(name):
            raise IllustrationError(f"图像占位符只能是 image:focus_1、image:focus_2 这样的形式，不支持 {name}")
    if not prompt_fields(workflow):
        raise IllustrationError("工作流至少需要一个提示词占位符，例如 {{prompt}}")
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
